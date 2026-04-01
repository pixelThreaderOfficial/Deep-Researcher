import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from main.apis.models.workspaces import (
    WorkspaceCreate,
    WorkspaceListItem,
    WorkspaceListResponse,
    WorkspaceOut,
    WorkspacePatch,
    WorkspaceResourceStats,
)
from main.src.store.DBManager import buckets_db_manager, main_db_manager
from main.src.bucket.bucket_store import bucket_store
from main.src.utils.DRLogger import dr_logger
from main.src.utils.version_constants import get_raw_version

# Logger
LOG_SOURCE = "system"


def _nullish_to_none(value: object) -> object:
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none"}:
        return None
    return value


def _log_system_workspace_event(
    message: str,
    level: Literal["success", "error", "warning", "info"] = "info",
    urgency: Literal["none", "moderate", "critical"] = "none",
) -> None:
    """
    ## Description

    metadata. Ensures all secret-related operations are tracked with appropriate
    Internal utility function for logging secret management events with structured
    urgency levels and log sources.

    ## Parameters

    - `level` (`Literal["success", "error", "warning", "info"]`)
      - Description: Log severity level indicating the nature of the event.
      - Constraints: Must be one of: "success", "error", "warning", "info".
      - Example: "error"

    - `message` (`str`)
      - Description: Human-readable description of the secret event.
      - Constraints: Must be non-empty. Should not contain sensitive data (API keys, tokens).
      - Example: ".env file not found at /path/to/.env"

    - `urgency` (`Literal["none", "moderate", "critical"]`, optional)
      - Description: Priority indicator for the logged event.
      - Constraints: Must be one of: "none", "moderate", "critical".
      - Default: "none"
      - Example: "critical"

    ## Returns

    `None`

    ## Side Effects

    - Writes log entry to the DRLogger system.
    - Includes application version in all log entries.
    - Tags all events with "SECRETS_MANAGEMENT" for filtering.

    ## Debug Notes

    - Ensure messages do NOT contain sensitive information (API keys, tokens).
    - Use appropriate urgency levels: "critical" for missing keys, "moderate" for fallbacks.
    - Check logger output in application logs directory.

    ## Customization

    To change log source or tags globally, modify the module-level constants:
    - `LOG_SOURCE`: Change from "system" to custom value
    """
    dr_logger.log(
        log_type=level,
        message=message,
        origin=LOG_SOURCE,
        urgency=urgency,
        module="MAIN",
        app_version=get_raw_version(),
    )


class WorkspaceOrchestrator:
    def __init__(self):
        self.table_name = "workspaces"

    def _format_row_to_workspace_out(self, row: dict) -> WorkspaceOut:
        """Helper to convert a DB row dictionary to a WorkspaceOut Pydantic model"""
        # Keep compatibility with legacy records that may have unexpected ai_config values.
        allowed_ai_config = {"auto", "local", "online"}
        ai_config_value = row.get("ai_config")
        if not isinstance(ai_config_value, str):
            row["ai_config"] = "auto"
        else:
            normalized_ai_config = ai_config_value.strip().lower()
            row["ai_config"] = (
                normalized_ai_config
                if normalized_ai_config in allowed_ai_config
                else "auto"
            )

        # Boolean mapping from SQLite 0/1
        row["workspace_research_agents"] = bool(
            row.get("workspace_research_agents", True)
        )
        row["workspace_chat_agents"] = bool(row.get("workspace_chat_agents", True))

        return WorkspaceOut(**row)

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
        return datetime.min

    def _parse_connected_workspace_ids(self, value: object) -> set[str]:
        if value is None:
            return set()
        if not isinstance(value, str):
            return set()

        normalized = value.strip()
        if not normalized:
            return set()

        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            return {item.strip() for item in normalized.split(",") if item.strip()}

        if isinstance(parsed, list):
            return {str(item).strip() for item in parsed if str(item).strip()}
        if isinstance(parsed, str):
            return {item.strip() for item in parsed.split(",") if item.strip()}
        return set()

    def _paginate(
        self, items: list[Any], page: int, size: int
    ) -> tuple[list[Any], int, int, int]:
        total_items = len(items)
        total_pages = math.ceil(total_items / size) if total_items > 0 else 0
        offset = (page - 1) * size
        return items[offset : offset + size], total_items, total_pages, offset

    def _build_workspace_resource_count_lookup(
        self, workspaces: list[WorkspaceOut]
    ) -> dict[str, int]:
        workspace_ids = {workspace.id for workspace in workspaces}
        if not workspace_ids:
            return {}

        bucket_ids = {
            workspace.connected_bucket_id
            for workspace in workspaces
            if workspace.connected_bucket_id
        }
        if not bucket_ids:
            return {workspace_id: 0 for workspace_id in workspace_ids}

        counts = {workspace_id: 0 for workspace_id in workspace_ids}
        for bucket_id in bucket_ids:
            items_result = buckets_db_manager.fetch_all(
                "bucket_items", where={"bucket_id": bucket_id}
            )
            if not items_result.get("success"):
                raise ValueError(
                    items_result.get("message")
                    or "Failed to fetch workspace resource counts"
                )

            for item in items_result.get("data") or []:
                if bool(item.get("is_deleted", False)):
                    continue
                linked_workspace_ids = self._parse_connected_workspace_ids(
                    item.get("connected_workspace_ids")
                )
                for linked_workspace_id in linked_workspace_ids & workspace_ids:
                    counts[linked_workspace_id] += 1

        return counts

    def _set_workspace_asset_url(
        self,
        workspace_id: str,
        field_name: Literal["banner_img", "icon"],
        asset_url: str,
    ) -> WorkspaceOut:
        self.getWorkspace(workspace_id)

        result = main_db_manager.update(
            self.table_name,
            {
                field_name: asset_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            {"id": workspace_id},
        )
        if not result.get("success"):
            raise ValueError(
                result.get("message") or "Failed to update workspace asset"
            )
        return self.getWorkspace(workspace_id)

    def uploadWorkspaceBanner(
        self,
        workspace_id: str,
        file_name: str,
        content: bytes,
    ) -> WorkspaceOut:
        if not content:
            raise ValueError("Banner image is empty")

        stored_path = bucket_store.save_workspace_asset(
            asset_type="banner",
            original_file_name=file_name,
            content=content,
        )
        asset_url = bucket_store.build_asset_url(stored_path)
        return self._set_workspace_asset_url(
            workspace_id=workspace_id,
            field_name="banner_img",
            asset_url=asset_url,
        )

    def uploadWorkspaceIcon(
        self,
        workspace_id: str,
        file_name: str,
        content: bytes,
    ) -> WorkspaceOut:
        if not content:
            raise ValueError("Workspace icon is empty")

        stored_path = bucket_store.save_workspace_asset(
            asset_type="icons",
            original_file_name=file_name,
            content=content,
        )
        asset_url = bucket_store.build_asset_url(stored_path)
        return self._set_workspace_asset_url(
            workspace_id=workspace_id,
            field_name="icon",
            asset_url=asset_url,
        )

    def createWorkspace(self, workspace_data: WorkspaceCreate) -> WorkspaceOut:
        _log_system_workspace_event(
            f"Attempting to create workspace: {workspace_data.name}"
        )

        # Prepare data for insertion (Pydantic model dump)
        db_data = workspace_data.model_dump(exclude_unset=True)

        # Normalize null-like payload values coming from UI/swagger clients.
        db_data["id"] = _nullish_to_none(db_data.get("id"))
        db_data["connected_bucket_id"] = _nullish_to_none(
            db_data.get("connected_bucket_id")
        )
        db_data["workspace_resources_id"] = _nullish_to_none(
            db_data.get("workspace_resources_id")
        )

        # Generate essential IDs if not set by the model defaults
        if not db_data.get("id"):
            db_data["id"] = str(uuid.uuid4())

        # Add timestamps
        now = datetime.now(timezone.utc).isoformat()
        db_data["created_at"] = now
        db_data["updated_at"] = now

        result = main_db_manager.insert(self.table_name, db_data)

        if not result.get("success"):
            _log_system_workspace_event(
                f"Failed to create workspace: {result.get('message')}",
                level="error",
                urgency="critical",
            )
            raise ValueError(f"Failed to create workspace: {result.get('message')}")

        _log_system_workspace_event(
            f"Successfully created workspace {db_data['id']}", level="success"
        )
        created_workspace_id = db_data.get("id")
        if not isinstance(created_workspace_id, str):
            raise ValueError("Workspace id generation failed")
        return self.getWorkspace(created_workspace_id)

    def getWorkspace(self, workspace_id: str) -> WorkspaceOut:
        _log_system_workspace_event(f"Fetching workspace {workspace_id}")

        result = main_db_manager.fetch_one(self.table_name, {"id": workspace_id})

        if not result.get("success") or not result.get("data"):
            _log_system_workspace_event(
                f"Workspace {workspace_id} not found",
                level="warning",
                urgency="moderate",
            )
            raise KeyError(f"Workspace {workspace_id} not found")

        _log_system_workspace_event(
            f"Successfully fetched workspace {workspace_id}", level="success"
        )
        return self._format_row_to_workspace_out(result["data"])

    def getWorkspaceResourceStats(self, workspace_id: str) -> WorkspaceResourceStats:
        workspace = self.getWorkspace(workspace_id)

        if not workspace.connected_bucket_id:
            return WorkspaceResourceStats(workspace_id=workspace_id)

        bucket_result = buckets_db_manager.fetch_one(
            "buckets", {"id": workspace.connected_bucket_id}
        )
        if not bucket_result.get("success"):
            raise ValueError(
                bucket_result.get("message") or "Failed to fetch connected bucket"
            )

        bucket_row = bucket_result.get("data")
        if bucket_row is None:
            raise KeyError(
                f"Connected bucket {workspace.connected_bucket_id} not found"
            )

        items_result = buckets_db_manager.fetch_all(
            "bucket_items", where={"bucket_id": workspace.connected_bucket_id}
        )
        if not items_result.get("success"):
            raise ValueError(
                items_result.get("message") or "Failed to fetch workspace resources"
            )

        resource_count = 0
        total_size = 0
        for item in items_result.get("data") or []:
            if bool(item.get("is_deleted", False)):
                continue
            linked_workspace_ids = self._parse_connected_workspace_ids(
                item.get("connected_workspace_ids")
            )
            if workspace_id not in linked_workspace_ids:
                continue
            resource_count += 1
            try:
                total_size += int(item.get("file_size") or 0)
            except (TypeError, ValueError):
                continue

        return WorkspaceResourceStats(
            workspace_id=workspace_id,
            connected_bucket_id=workspace.connected_bucket_id,
            resource_count=resource_count,
            total_size=total_size,
            bucket_total_files=int(bucket_row.get("total_files") or 0),
            bucket_total_size=int(bucket_row.get("total_size") or 0),
        )

    def getAllWorkspaces(
        self,
        page: int = 1,
        size: int = 200,
        name_contains: str | None = None,
        desc_contains: str | None = None,
        ai_config: Literal["auto", "local", "online"] | None = None,
        connected_bucket_id: str | None = None,
        sort_by: Literal["updated_at", "created_at", "name"] = "updated_at",
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> WorkspaceListResponse:
        _log_system_workspace_event("Fetching all workspaces")

        where: dict[str, Any] = {}
        if ai_config is not None:
            where["ai_config"] = ai_config
        if connected_bucket_id is not None:
            where["connected_bucket_id"] = _nullish_to_none(connected_bucket_id)

        result = main_db_manager.fetch_all(self.table_name, where=where)

        if not result.get("success"):
            _log_system_workspace_event(
                f"Failed to fetch workspaces: {result.get('message')}",
                level="error",
                urgency="critical",
            )
            raise ValueError(f"Failed to fetch workspaces: {result.get('message')}")

        workspaces = [
            self._format_row_to_workspace_out(row) for row in result.get("data", [])
        ]

        if name_contains:
            term = name_contains.strip().lower()
            workspaces = [
                workspace
                for workspace in workspaces
                if term in (workspace.name or "").lower()
            ]
        if desc_contains:
            term = desc_contains.strip().lower()
            workspaces = [
                workspace
                for workspace in workspaces
                if term in (workspace.desc or "").lower()
            ]

        reverse_order = sort_order == "desc"
        if sort_by == "created_at":
            workspaces.sort(
                key=lambda workspace: self._parse_datetime(workspace.created_at),
                reverse=reverse_order,
            )
        elif sort_by == "name":
            workspaces.sort(
                key=lambda workspace: (workspace.name or "").lower(),
                reverse=reverse_order,
            )
        else:
            workspaces.sort(
                key=lambda workspace: self._parse_datetime(workspace.updated_at),
                reverse=reverse_order,
            )

        paged_workspaces, total_items, total_pages, offset = self._paginate(
            workspaces, page, size
        )
        resource_counts = self._build_workspace_resource_count_lookup(paged_workspaces)
        items = [
            WorkspaceListItem(
                **workspace.model_dump(mode="python"),
                resource_count=resource_counts.get(workspace.id, 0),
            )
            for workspace in paged_workspaces
        ]

        _log_system_workspace_event(
            f"Successfully fetched {len(items)} workspaces", level="success"
        )

        return WorkspaceListResponse(
            items=items,
            page=page,
            size=size,
            total_items=total_items,
            total_pages=total_pages,
            offset=offset,
        )

    def updateWorkspace(
        self, workspace_id: str, workspace_data: WorkspaceCreate
    ) -> WorkspaceOut:
        _log_system_workspace_event(
            f"Attempting to completely update workspace {workspace_id}"
        )

        # Verify exists
        self.getWorkspace(workspace_id)

        update_data = workspace_data.model_dump(exclude_unset=True)
        update_data["id"] = _nullish_to_none(update_data.get("id"))
        update_data["connected_bucket_id"] = _nullish_to_none(
            update_data.get("connected_bucket_id")
        )
        update_data["workspace_resources_id"] = _nullish_to_none(
            update_data.get("workspace_resources_id")
        )

        # Prevent primary-key changes when replacing a workspace record.
        update_data.pop("id", None)

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = main_db_manager.update(
            self.table_name, update_data, {"id": workspace_id}
        )

        if not result.get("success"):
            _log_system_workspace_event(
                f"Failed to update workspace {workspace_id}: {result.get('message')}",
                level="error",
                urgency="critical",
            )
            raise ValueError(f"Failed to update workspace: {result.get('message')}")

        _log_system_workspace_event(
            f"Successfully updated workspace {workspace_id}", level="success"
        )
        return self.getWorkspace(workspace_id)

    def patchWorkspace(
        self, workspace_id: str, workspace_data: WorkspacePatch
    ) -> WorkspaceOut:
        _log_system_workspace_event(f"Attempting to patch workspace {workspace_id}")

        # Verify exists
        self.getWorkspace(workspace_id)

        patch_data = workspace_data.model_dump(exclude_unset=True)
        if not patch_data:
            return self.getWorkspace(workspace_id)

        patch_data["connected_bucket_id"] = _nullish_to_none(
            patch_data.get("connected_bucket_id")
        )
        patch_data["workspace_resources_id"] = _nullish_to_none(
            patch_data.get("workspace_resources_id")
        )

        patch_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = main_db_manager.update(
            self.table_name, patch_data, {"id": workspace_id}
        )

        if not result.get("success"):
            _log_system_workspace_event(
                f"Failed to patch workspace {workspace_id}: {result.get('message')}",
                level="error",
                urgency="critical",
            )
            raise ValueError(f"Failed to patch workspace: {result.get('message')}")

        _log_system_workspace_event(
            f"Successfully patched workspace {workspace_id}", level="success"
        )
        return self.getWorkspace(workspace_id)

    def deleteWorkspace(self, workspace_id: str) -> None:
        _log_system_workspace_event(
            f"Attempting to delete workspace {workspace_id}", urgency="moderate"
        )

        # Verify exists
        self.getWorkspace(workspace_id)

        result = main_db_manager.delete(self.table_name, {"id": workspace_id})

        if not result.get("success"):
            _log_system_workspace_event(
                f"Failed to delete workspace {workspace_id}: {result.get('message')}",
                level="error",
                urgency="critical",
            )
            raise ValueError(f"Failed to delete workspace: {result.get('message')}")

        _log_system_workspace_event(
            f"Successfully deleted workspace {workspace_id}", level="success"
        )
