"""
Logger utility for Deep Researcher.
This module provides the DRLogger class and a singleton instance for logging messages
into the logs database using the DBManager module.
"""

import datetime
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

LogType = Literal["success", "error", "warning", "info"]
LogOrigin = Literal["system", "user"]
LogUrgency = Literal["none", "moderate", "critical"]

VALID_MODULES: List[str] = ["AGENTS", "UTILS", "CRAWLER", "DB", "AI"]


class DRLogger:
    """
    Logger class handling safe persistence of logs to SQLite database.

    Purpose:
        Provides structured logging across multiple modules. Logs are stored in separate
        tables per module. Lazily initializes SQLite connection to avoid circular dependencies.

    Args:
        None

    Returns:
        None

    Raises:
        None

    Side Effects:
        Modifies the underlying logs.db.sqlite3 database by inserting rows
        and creating tables if they do not exist.

    Debug Notes:
        Check SQLite files in the store/database directory if logs aren't persisting.

    Customization Notes:
        Add items to VALID_MODULES to expand the app's logged components.
    """

    def __init__(self):
        """
        Initializes the logger database schema configuration.
        """
        self.schema: Dict[str, str] = {
            "logNo": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "logId": "TEXT UNIQUE",
            "type": "TEXT",
            "message": "TEXT",
            "timestamp": "TEXT",
            "origin": "TEXT",
            "module": "VARCHAR(255)",
            "urgency": "TEXT",
            "app_version": "TEXT",
        }
        self.logs_db_manager = None

    def _get_db(self):
        """
        Lazily initialize the SQLiteManager for logs to prevent circular dependencies
        since DBManager uses DRLogger too.
        """
        if self.logs_db_manager is None:
            # NOTE: Import inside the method to avoid a circular import:
            # AgentLogger -> AgentDB -> AgentLogger
            from utils.db.AgentDB import SQLiteManager

            current_dir = Path(__file__).parent
            src_dir = current_dir.parent
            if str(src_dir) not in sys.path:
                sys.path.append(str(src_dir))

            # IMPORTANT: AgentDB initializes the logs DB at `utils/db/database/logs.db.sqlite3`.
            # Keep both logger and DB manager writing to the same file, otherwise
            # you end up with an "empty" DB being inspected while logging writes elsewhere.
            db_dir = src_dir / "db" / "database"
            db_dir.mkdir(parents=True, exist_ok=True)
            logs_db_path = db_dir / "logs.db.sqlite3"

            self.logs_db_manager = SQLiteManager(logs_db_path)
            self._ensure_tables()

        return self.logs_db_manager

    def _ensure_tables(self) -> None:
        """
        Ensures that tables for all valid modules exist in the logs database.
        """
        assert self.logs_db_manager is not None
        for module in VALID_MODULES:
            table_name = f"{module.lower()}_logs"
            self.logs_db_manager.create_table(table_name, self.schema)

    def log(
        self,
        log_type: LogType,
        message: Any,
        origin: LogOrigin,
        module: Union[str, List[str]],
        urgency: LogUrgency,
        app_version: str,
    ) -> Dict[str, Any]:
        """
        Records a log entry into the appropriate module table(s).

        Purpose:
            Safely logs a single application message. Everything is cast to strings.
            Type safety is intentionally relaxed for module and message as requested.

        Args:
            log_type (str): Severity/type of the log (success|error|warning|info).
            message (Any): Descriptive message, any type (converted to string).
            origin (str): Source of the log message (system|user).
            module (Union[str, List[str]]): Target module(s) to log this message under.
            urgency (str): Level of urgency (none|moderate|critical).
            app_version (str): The version parameter log tracking.


            ```python
            VALID_MODULES: List[str] = [
                "AGENTS",
                "UTILS",
                "CRAWLER",
                "DB",
                "AI"
            ]
            ```

        Returns:
            Dict[str, Any]: Results keyed by the target module, indicating success/failure.
        """
        db_mgr = self._get_db()

        try:
            timestamp = str(datetime.datetime.now(datetime.timezone.utc).isoformat())
        except AttributeError:
            timestamp = str(datetime.datetime.utcnow().isoformat())

        log_id = uuid.uuid4().hex

        # Cast to strings to ensure schema matching without artificial type restrictions
        safe_type = str(log_type).strip()
        safe_message = str(message)
        safe_origin = str(origin).strip()
        safe_urgency = str(urgency).strip()
        safe_app_version = str(app_version).strip()

        modules_list = [module] if isinstance(module, str) else module

        results: Dict[str, Any] = {}

        for mod in modules_list:
            safe_mod = str(mod).strip().upper()

            if safe_mod not in VALID_MODULES:
                results[safe_mod] = {
                    "success": False,
                    "message": f"Module '{safe_mod}' is not in VALID_MODULES",
                    "data": None,
                }
                continue

            table_name = f"{safe_mod.lower()}_logs"

            data_to_insert = {
                "logId": log_id,
                "type": safe_type,
                "message": safe_message,
                "timestamp": timestamp,
                "origin": safe_origin,
                "module": safe_mod,
                "urgency": safe_urgency,
                "app_version": safe_app_version,
            }

            res = db_mgr.insert(table_name, data_to_insert)
            results[safe_mod] = res

        return results


# Singleton instance to be exported for usage SDK style
dr_logger = DRLogger()


def quickLog(
    message: str,
    level: Literal["success", "error", "warning", "info"] = "info",
    urgency: Literal["none", "moderate", "critical"] = "none",
    module: Optional[
        Union[str, List[Literal["UTILS", "DB", "AGENTS", "CRAWLER", "AI"]]]
    ] = None,
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
    # 1. Handle the Optional/Default logic
    # 2. Force the type to List[str] to satisfy the invariant 'log' parameter
    if module is None:
        target_module: Union[str, List[str]] = ["UTILS"]
    elif isinstance(module, list):
        # We cast or explicitly type to widen from Literal back to base str
        target_module = list(module)
    else:
        target_module = module

    dr_logger.log(
        log_type=level,
        message=message,
        origin="system",
        urgency=urgency,
        module=target_module,
        app_version="1.0.0",
    )
