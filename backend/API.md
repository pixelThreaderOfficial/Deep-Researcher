# Deep Researcher — Backend API Reference

**Base URL:** `http://localhost:8000`
**Protocol:** HTTP/1.1 · REST
**Content-Type:** `application/json` (all endpoints except file upload, which uses `multipart/form-data`)
**CORS allowed origins:** `http://localhost:3000`, `http://127.0.0.1:3000`

---

## Error Response Shape

Every non-2xx response returns:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning                                        |
| ------ | ---------------------------------------------- |
| `400`  | Bad request / validation error                 |
| `404`  | Resource not found                             |
| `409`  | Conflict (e.g. settings record already exists) |
| `500`  | Internal server error                          |
| `204`  | Success with no body (DELETE responses)        |

---

## Health Check

### `GET /health`

Returns server liveness.

**Response `200`**

```json
{ "status": "ok" }
```

---

---

# 1. Workspace API

**Prefix:** `/workspace`

---

### `GET /workspace/`

List all workspaces.

**Query params:**

| Param               | Type                                         | Default        | Notes                                         |
| ------------------- | -------------------------------------------- | -------------- | --------------------------------------------- |
| `page`              | int                                          | `1`            | ≥ 1                                           |
| `size`              | int                                          | `200`          | 1–500                                         |
| `nameContains`      | string                                       | —              | case-insensitive workspace name search        |
| `descContains`      | string                                       | —              | case-insensitive workspace description search |
| `aiConfig`          | `"auto"` \| `"local"` \| `"online"`          | —              | exact match                                   |
| `connectedBucketId` | string                                       | —              | exact match                                   |
| `sortBy`            | `"updated_at"` \| `"created_at"` \| `"name"` | `"updated_at"` |                                               |
| `sortOrder`         | `"asc"` \| `"desc"`                          | `"desc"`       |                                               |

**Response `200`** — `WorkspaceListResponse`

```json
{
  "items": [
    {
      "id": "uuid-string",
      "name": "My Workspace",
      "desc": "A research workspace",
      "icon": null,
      "accent_clr": "#6366f1",
      "banner_img": null,
      "connected_bucket_id": null,
      "ai_config": "auto",
      "workspace_resources_id": null,
      "workspace_research_agents": true,
      "workspace_chat_agents": true,
      "created_at": "2026-03-14 10:30:00 AM",
      "updated_at": "2026-03-14 10:30:00 AM",
      "resource_count": 0
    }
  ],
  "page": 1,
  "size": 200,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

| Response Field           | Type                  | Notes                                            |
| ------------------------ | --------------------- | ------------------------------------------------ |
| `items`                  | `WorkspaceListItem[]` | paginated workspace rows                         |
| `items[].resource_count` | int                   | exact non-deleted files linked to that workspace |
| `page`                   | int                   | current page                                     |
| `size`                   | int                   | requested page size                              |
| `total_items`            | int                   | total matching workspaces before pagination      |
| `total_pages`            | int                   | total available pages                            |
| `offset`                 | int                   | zero-based starting index for this page          |

> Note: `created_at` and `updated_at` are returned in IST 12-hour format (`YYYY-MM-DD HH:MM:SS AM/PM`).
> Note: `resource_count` is workspace-specific even if multiple workspaces share the same bucket.

---

### `GET /workspace/{workspace_id}`

Get a single workspace by ID.

**Path params:**

- `workspace_id` — UUID string

**Response `200`** — `WorkspaceOut`  
**Response `404`** — Workspace not found

---

### `GET /workspace/{workspace_id}/resources/stats`

Get the exact resource count for a workspace even when its connected bucket is shared with other workspaces.

This endpoint counts only bucket items whose `connected_workspace_ids` contains the requested `workspace_id`.

**Path params:**

- `workspace_id` — UUID string

**Response `200`** — `WorkspaceResourceStats`

```json
{
  "workspace_id": "workspace-uuid",
  "connected_bucket_id": "bucket-uuid",
  "resource_count": 3,
  "total_size": 928374,
  "bucket_total_files": 11,
  "bucket_total_size": 5829104
}
```

| Field                 | Type         | Notes                                                      |
| --------------------- | ------------ | ---------------------------------------------------------- |
| `workspace_id`        | string       | requested workspace id                                     |
| `connected_bucket_id` | string\|null | workspace's connected bucket                               |
| `resource_count`      | int          | exact number of non-deleted files linked to this workspace |
| `total_size`          | int          | total bytes for this workspace's linked files              |
| `bucket_total_files`  | int          | total files in the connected bucket                        |
| `bucket_total_size`   | int          | total bytes in the connected bucket                        |

**Behavior notes:**

1. If the workspace has no connected bucket, the response returns zero counts.
2. If the bucket is shared, `resource_count` is still workspace-specific.
3. Only files linked through `connected_workspace_ids` are counted.

---

### `POST /workspace/`

Create a new workspace.

**Request body** — `WorkspaceCreate`

```json
{
  "name": "Research Hub",
  "desc": "Primary research workspace",
  "icon": "🔬",
  "accent_clr": "#6366f1",
  "banner_img": null,
  "connected_bucket_id": null,
  "ai_config": "auto",
  "workspace_research_agents": true,
  "workspace_chat_agents": true
}
```

| Field                       | Type                                | Required | Notes                        |
| --------------------------- | ----------------------------------- | -------- | ---------------------------- |
| `name`                      | string                              | ✅       | 2–100 chars                  |
| `desc`                      | string                              | ✅       | 2–500 chars                  |
| `icon`                      | string\|null                        | ❌       | max 200 chars                |
| `accent_clr`                | string\|null                        | ❌       | max 20 chars, e.g. hex color |
| `banner_img`                | string\|null                        | ❌       | URL or path                  |
| `connected_bucket_id`       | string\|null                        | ❌       | bucket UUID                  |
| `ai_config`                 | `"auto"` \| `"local"` \| `"online"` | ❌       | default `"auto"`             |
| `workspace_research_agents` | boolean                             | ❌       | default `true`               |
| `workspace_chat_agents`     | boolean                             | ❌       | default `true`               |

**Response `201`** — `WorkspaceOut`

---

### `PUT /workspace/{workspace_id}`

Fully replace a workspace (all fields required).

**Request body** — same as `POST /workspace/`  
**Response `200`** — `WorkspaceOut`  
**Response `404`** — Not found

---

### `PATCH /workspace/{workspace_id}`

Partially update a workspace (only send fields to change).

**Request body** — `WorkspacePatch` (all fields optional)

```json
{
  "name": "Updated Name",
  "accent_clr": "#ec4899"
}
```

**Response `200`** — `WorkspaceOut`  
**Response `404`** — Not found

---

### `DELETE /workspace/{workspace_id}`

Delete a workspace.

**Response `204`** — No content  
**Response `404`** — Not found

---

## Workspace Asset Upload APIs

Workspace image uploads are handled via separate APIs. Files are stored as:

- `src/store/bucket/workspace/banner/<unique_md5>.<ext>`
- `src/store/bucket/workspace/icons/<unique_md5>.<ext>`

Uploaded filenames are replaced with a unique MD5 hash. Saved values in workspace fields (`banner_img`, `icon`) are API asset URLs.

### `POST /workspace/create-with-assets`

Create workspace and upload banner, icon, **and resource files** in the same multipart request (best for first-time create flow when `workspace_id` is not available yet).

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field                       | Type                                | Required | Notes                                                      |
| --------------------------- | ----------------------------------- | -------- | ---------------------------------------------------------- |
| `name`                      | string                              | ✅       | workspace name                                             |
| `desc`                      | string                              | ✅       | workspace description                                      |
| `icon`                      | string\|null                        | ❌       | optional text icon value                                   |
| `accent_clr`                | string\|null                        | ❌       | color                                                      |
| `banner_img`                | string\|null                        | ❌       | optional pre-set URL/text                                  |
| `connected_bucket_id`       | string\|null                        | ❌       | required if uploading resource files                       |
| `ai_config`                 | `"auto"` \| `"local"` \| `"online"` | ❌       | default `auto`                                             |
| `workspace_resources_id`    | string\|null                        | ❌       |                                                            |
| `workspace_research_agents` | boolean                             | ❌       | default `true`                                             |
| `workspace_chat_agents`     | boolean                             | ❌       | default `true`                                             |
| `banner_file`               | file                                | ❌       | uploaded banner image                                      |
| `icon_file`                 | file                                | ❌       | uploaded icon image                                        |
| `resource_files`            | file[] (multi)                      | ❌       | resource files to store in connected bucket; type-checked  |
| `resource_created_by`       | string                              | ❌       | creator identifier for resource items (default `"system"`) |
| `resource_source`           | string\|null                        | ❌       | optional source label for resource items                   |
| `resource_summary`          | string\|null                        | ❌       | optional summary applied to all resource items             |

> **Type validation:** Each file in `resource_files` must belong to a type category
> permitted by the connected bucket's `allowed_file_types`. All files are validated
> before any are written to disk (all-or-nothing). If `connected_bucket_id` is absent,
> `resource_files` is silently ignored.

**Response `201`** — `WorkspaceOut`

**Recommended flow:**

1. Use this endpoint for first-time workspace creation when ID does not exist yet.
2. If `banner_file` and/or `icon_file` are included, the response already contains updated `banner_img`/`icon` asset URLs.
3. Pass `resource_files` (multiple) along with `connected_bucket_id` to pre-populate the bucket in a single call.
4. Use the dedicated resource upload APIs only after workspace is created (edit mode).

---

### `POST /workspace/{workspace_id}/resources/upload`

Upload a **single resource file** to the workspace's connected bucket and register it as a `BucketItem` linked to this workspace.

The file type is validated against the bucket's `allowed_file_types` before saving.
Returns `400` if the workspace has no connected bucket or if the file type is rejected.

**Content-Type:** `multipart/form-data`

| Field  | Type | Required |
| ------ | ---- | -------- |
| `file` | file | ✅       |

**Query params:**

| Param       | Type   | Required | Notes                              |
| ----------- | ------ | -------- | ---------------------------------- |
| `createdBy` | string | ✅       | creator identifier                 |
| `source`    | string | ❌       | origin label (URL, app name, etc.) |
| `summary`   | string | ❌       | short description of the resource  |

**Response `201`** — `BucketItemRecord`

---

### `POST /workspace/{workspace_id}/resources/upload/bulk`

Upload **multiple resource files** to the workspace's connected bucket in one request.
All file types are validated against the bucket's `allowed_file_types` **before any file is saved** (all-or-nothing).
Returns `400` if the workspace has no connected bucket or if any file type is rejected.

**Content-Type:** `multipart/form-data`

| Field   | Type   | Required |
| ------- | ------ | -------- |
| `files` | file[] | ✅       |

**Query params:**

| Param       | Type   | Required | Notes                      |
| ----------- | ------ | -------- | -------------------------- |
| `createdBy` | string | ✅       | creator identifier         |
| `source`    | string | ❌       | origin label               |
| `summary`   | string | ❌       | short description (shared) |

**Response `201`** — `BucketItemRecord[]`

---

### `POST /workspace/{workspace_id}/upload/banner`

Upload workspace banner image and update `banner_img` with accessible URL.

**Content-Type:** `multipart/form-data`

| Field  | Type | Required |
| ------ | ---- | -------- |
| `file` | file | ✅       |

**Response `200`** — `WorkspaceOut`

---

### `POST /workspace/{workspace_id}/upload/icon`

Upload workspace icon and update `icon` with accessible URL.

**Content-Type:** `multipart/form-data`

| Field  | Type | Required |
| ------ | ---- | -------- |
| `file` | file | ✅       |

**Response `200`** — `WorkspaceOut`

---

# 2. Research API

**Prefix:** `/research`

---

## Research Records

### `GET /research/`

List all research records with filtering and pagination.

**Query params:**

| Param                  | Type                                    | Default  | Notes                                            |
| ---------------------- | --------------------------------------- | -------- | ------------------------------------------------ |
| `page`                 | int                                     | `1`      | ≥ 1                                              |
| `size`                 | int                                     | `20`     | 1–200                                            |
| `workspaceId`          | string                                  | —        | filter by workspace                              |
| `titleContains`        | string                                  | —        | case-insensitive substring search on title       |
| `descContains`         | string                                  | —        | case-insensitive substring search on description |
| `promptContains`       | string                                  | —        | case-insensitive substring search on prompt      |
| `chatAccess`           | boolean                                 | —        | exact match                                      |
| `backgroundProcessing` | boolean                                 | —        | exact match                                      |
| `sortBy`               | `"id"` \| `"title"` \| `"workspace_id"` | `"id"`   |                                                  |
| `sortOrder`            | `"asc"` \| `"desc"`                     | `"desc"` |                                                  |

**Response `200`** — `ResearchListResponse`

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "AI Market Analysis 2026",
      "desc": "A deep dive into AI market trends",
      "prompt": "Research the latest AI market trends",
      "sources": null,
      "workspace_id": "workspace-uuid",
      "artifacts": null,
      "chat_access": true,
      "background_processing": true,
      "research_template_id": null,
      "custom_instructions": null,
      "prompt_order": null
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /research/{research_id}`

Get a single research record.

**Response `200`** — `ResearchRecord`  
**Response `404`** — Not found

---

### `POST /research/`

Create a research record.

**Request body** — `ResearchCreate`

```json
{
  "title": "AI Market Analysis 2026",
  "desc": "A deep dive into AI market trends",
  "prompt": "Research the latest AI market trends in 2026",
  "workspace_id": "workspace-uuid",
  "chat_access": true,
  "background_processing": true
}
```

| Field                   | Type         | Required          |
| ----------------------- | ------------ | ----------------- |
| `title`                 | string\|null | ❌                |
| `desc`                  | string\|null | ❌                |
| `prompt`                | string\|null | ❌                |
| `sources`               | string\|null | ❌                |
| `workspace_id`          | string\|null | ❌                |
| `artifacts`             | string\|null | ❌                |
| `chat_access`           | boolean      | ❌ default `true` |
| `background_processing` | boolean      | ❌ default `true` |
| `research_template_id`  | string\|null | ❌                |
| `custom_instructions`   | string\|null | ❌                |
| `prompt_order`          | string\|null | ❌                |

**Response `201`** — `ResearchRecord`

---

### `PUT /research/{research_id}`

Fully replace a research record.

**Request body** — same as `POST /research/`  
**Response `200`** — `ResearchRecord`  
**Response `404`** — Not found

---

### `PATCH /research/{research_id}`

Partially update a research record.

**Request body** — `ResearchPatch` (all fields optional, same fields as create)  
**Response `200`** — `ResearchRecord`

---

### `DELETE /research/{research_id}`

Delete a research record.

**Response `204`** — No content  
**Response `404`** — Not found

---

## Research Sources

### `GET /research/urls`

List research source URLs with filtering.

**Query params:**

| Param         | Type                | Default        | Notes                                                                  |
| ------------- | ------------------- | -------------- | ---------------------------------------------------------------------- |
| `page`        | int                 | `1`            |                                                                        |
| `size`        | int                 | `20`           |                                                                        |
| `researchId`  | string              | —              | filter by parent research                                              |
| `createdFrom` | ISO datetime        | —              |                                                                        |
| `createdTo`   | ISO datetime        | —              |                                                                        |
| `updatedFrom` | ISO datetime        | —              |                                                                        |
| `updatedTo`   | ISO datetime        | —              |                                                                        |
| `sourceType`  | string              | —              | e.g. `"web"`, `"file"`                                                 |
| `urlContains` | string              | —              | substring match on source URL                                          |
| `sortBy`      | string              | `"created_at"` | `created_at`, `updated_at`, `research_id`, `source_type`, `source_url` |
| `sortOrder`   | `"asc"` \| `"desc"` | `"desc"`       |                                                                        |

**Response `200`** — `ResearchSourceListResponse`

```json
{
  "items": [
    {
      "id": "uuid",
      "research_id": "research-uuid",
      "source_url": "https://example.com/article",
      "source_type": "web",
      "created_at": "2026-03-14T10:00:00+00:00",
      "updated_at": "2026-03-14T10:00:00+00:00"
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /research/sources/{source_id}`

Get a single research source record.

**Response `200`** — `ResearchSourceRecord`  
**Response `404`** — Not found

---

### `POST /research/sources`

Create a research source.

**Request body** — `ResearchSourceCreate`

```json
{
  "research_id": "research-uuid",
  "source_url": "https://example.com/article",
  "source_type": "web"
}
```

**Response `201`** — `ResearchSourceRecord`

---

### `PATCH /research/sources/{source_id}`

Partially update a research source.

**Request body** — `ResearchSourcePatch` (all fields optional)  
**Response `200`** — `ResearchSourceRecord`

---

### `DELETE /research/sources/{source_id}`

Delete a research source.

**Response `204`** — No content  
**Response `404`** — Not found

---

---

# 3. History API

**Prefix:** `/history`

---

### `GET /history/`

List history items with filtering and pagination.

**Query params:**

| Param              | Type                                                        | Default       | Notes                               |
| ------------------ | ----------------------------------------------------------- | ------------- | ----------------------------------- |
| `page`             | int                                                         | `1`           |                                     |
| `size`             | int                                                         | `10`          | 1–200                               |
| `itemType`         | HistoryType                                                 | —             | See enum below                      |
| `workspaceId`      | string                                                      | —             | filter by workspace                 |
| `userId`           | string                                                      | —             | filter by user                      |
| `include_deleted`  | boolean                                                     | `false`       | include soft-deleted items          |
| `activityContains` | string                                                      | —             | case-insensitive activity search    |
| `urlContains`      | string                                                      | —             | case-insensitive URL search         |
| `createdFrom`      | ISO datetime                                                | —             | include records created at/after    |
| `createdTo`        | ISO datetime                                                | —             | include records created at/before   |
| `lastSeenFrom`     | ISO datetime                                                | —             | include records last seen at/after  |
| `lastSeenTo`       | ISO datetime                                                | —             | include records last seen at/before |
| `sortBy`           | `"last_seen"` \| `"created_at"` \| `"activity"` \| `"type"` | `"last_seen"` |                                     |
| `sortOrder`        | `"asc"` \| `"desc"`                                         | `"desc"`      |                                     |

**`HistoryType` enum values:** `"usage"`, `"research"`, `"chat"`, `"version"`, `"token"`, `"ai_summary"`, `"bucket"`, `"search"`, `"export"`, `"download"`, `"upload"`, `"generation"`

**Response `200`** — `HistoryItemResponse`

```json
{
  "history_items": [
    {
      "id": "uuid",
      "user_id": "user-123",
      "workspace_id": "workspace-uuid",
      "activity": "Started research on AI trends",
      "type": "research",
      "created_at": "2026-03-14T10:00:00+00:00",
      "last_seen": "2026-03-14T10:00:00+00:00",
      "actions": null,
      "url": "/research/uuid"
    }
  ],
  "page": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /history/{history_id}`

Get a single history item.

**Response `200`** — `HistoryItem`  
**Response `404`** — Not found

---

### `POST /history/`

Create a history item.

**Request body** — `HistoryItem`

```json
{
  "user_id": "user-123",
  "workspace_id": "workspace-uuid",
  "activity": "Uploaded a file to bucket",
  "type": "upload",
  "url": "/bucket/uuid"
}
```

| Field          | Type               | Required                    |
| -------------- | ------------------ | --------------------------- |
| `user_id`      | string\|null       | ❌                          |
| `workspace_id` | string\|null       | ❌                          |
| `activity`     | string\|null       | ❌                          |
| `type`         | string\|null       | ❌ use `HistoryType` values |
| `last_seen`    | ISO datetime\|null | ❌                          |
| `actions`      | string\|null       | ❌                          |
| `url`          | string\|null       | ❌                          |

**Response `201`** — `HistoryItem`

---

### `PUT /history/{history_id}`

Fully replace a history item.

**Request body** — `HistoryItem`  
**Response `200`** — `HistoryItem`  
**Response `404`** — Not found

---

### `PATCH /history/{history_id}`

Partially update a history item.

**Request body** — `HistoryItemPatch` (all fields optional, same fields as create)  
**Response `200`** — `HistoryItem`

---

### `DELETE /history/{history_id}`

Delete a history item.

**Response `204`** — No content  
**Response `404`** — Not found

---

### `POST /history/{history_id}/action`

Perform a named action on a history item.

**Query params:**

| Param    | Type       | Required | Notes                               |
| -------- | ---------- | -------- | ----------------------------------- |
| `action` | `"delete"` | ✅       | Only `"delete"` supported currently |

**Response `200`** — `HistoryItem` (soft-deleted item)

---

---

# 4. Chats API

**Prefix:** `/chats`

---

## Chat Threads

### `GET /chats/threads`

List all chat threads.

**Query params:**

| Param                 | Type                                                                     | Default        | Notes                         |
| --------------------- | ------------------------------------------------------------------------ | -------------- | ----------------------------- |
| `page`                | int                                                                      | `1`            |                               |
| `size`                | int                                                                      | `20`           | 1–200                         |
| `workspaceId`         | string                                                                   | —              | filter by workspace           |
| `userId`              | string                                                                   | —              | filter by thread owner        |
| `createdBy`           | string                                                                   | —              | filter by creator             |
| `isPinned`            | boolean                                                                  | —              | exact match                   |
| `threadTitleContains` | string                                                                   | —              | case-insensitive title search |
| `sortBy`              | `"updated_at"` \| `"created_at"` \| `"thread_title"` \| `"pinned_order"` | `"updated_at"` |                               |
| `sortOrder`           | `"asc"` \| `"desc"`                                                      | `"desc"`       |                               |

**Response `200`** — `ChatThreadListResponse`

```json
{
  "items": [
    {
      "thread_id": "uuid",
      "thread_title": "AI Research Discussion",
      "workspace_id": "workspace-uuid",
      "user_id": "user-123",
      "metadata": null,
      "token_count": null,
      "is_pinned": false,
      "pinned_at": null,
      "pinned_order": null,
      "created_by": "user-123",
      "created_at": "2026-03-14T10:00:00+00:00",
      "updated_at": "2026-03-14T10:00:00+00:00"
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /chats/threads/{thread_id}`

Get a single thread.

**Response `200`** — `ChatThreadRecord`  
**Response `404`** — Not found

---

### `POST /chats/threads`

Create a chat thread.

**Request body** — `ChatThreadCreate`

```json
{
  "thread_title": "New Chat",
  "workspace_id": "workspace-uuid",
  "user_id": "user-123",
  "created_by": "user-123"
}
```

| Field          | Type               | Required       |
| -------------- | ------------------ | -------------- |
| `thread_title` | string\|null       | ❌             |
| `workspace_id` | string\|null       | ❌             |
| `user_id`      | string\|null       | ❌             |
| `metadata`     | string\|null       | ❌ JSON string |
| `token_count`  | int\|null          | ❌             |
| `is_pinned`    | boolean\|null      | ❌             |
| `pinned_at`    | ISO datetime\|null | ❌             |
| `pinned_order` | int\|null          | ❌             |
| `created_by`   | string\|null       | ❌             |

**Response `201`** — `ChatThreadRecord`

---

### `PUT /chats/threads/{thread_id}`

Fully replace a thread.

**Request body** — `ChatThreadCreate`  
**Response `200`** — `ChatThreadRecord`

---

### `PATCH /chats/threads/{thread_id}`

Partially update a thread.

**Request body** — `ChatThreadPatch` (all fields optional)  
**Response `200`** — `ChatThreadRecord`

---

### `DELETE /chats/threads/{thread_id}`

Delete a chat thread.

**Response `204`** — No content

---

## Chat Messages

### `GET /chats/messages`

List chat messages.

**Query params:**

| Param             | Type                                                | Default         | Notes                                |
| ----------------- | --------------------------------------------------- | --------------- | ------------------------------------ |
| `page`            | int                                                 | `1`             |                                      |
| `size`            | int                                                 | `20`            | 1–200                                |
| `threadId`        | string                                              | —               | filter by thread                     |
| `role`            | string                                              | —               | exact match                          |
| `parentId`        | string                                              | —               | exact match                          |
| `contentContains` | string                                              | —               | case-insensitive message text search |
| `createdFrom`     | ISO datetime                                        | —               | include records created at/after     |
| `createdTo`       | ISO datetime                                        | —               | include records created at/before    |
| `sortBy`          | `"message_seq"` \| `"created_at"` \| `"updated_at"` | `"message_seq"` |                                      |
| `sortOrder`       | `"asc"` \| `"desc"`                                 | `"asc"`         |                                      |

**Response `200`** — `ChatMessageListResponse`

```json
{
  "items": [
    {
      "message_id": "uuid",
      "thread_id": "thread-uuid",
      "message_seq": 1,
      "parent_id": null,
      "role": "user",
      "content": "What are the latest AI trends?",
      "citations": null,
      "token_count": 12,
      "attachments": null,
      "created_at": "2026-03-14T10:00:00+00:00",
      "updated_at": "2026-03-14T10:00:00+00:00"
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /chats/messages/{message_id}`

Get a single message.

**Response `200`** — `ChatMessageRecord`

---

### `POST /chats/messages`

Create a message.

**Request body** — `ChatMessageCreate`

```json
{
  "thread_id": "thread-uuid",
  "message_seq": 1,
  "role": "user",
  "content": "What are the latest AI trends?",
  "token_count": 12
}
```

| Field         | Type         | Notes                               |
| ------------- | ------------ | ----------------------------------- |
| `thread_id`   | string\|null | parent thread UUID                  |
| `message_seq` | int\|null    | sequence number in thread           |
| `parent_id`   | string\|null | UUID for reply threading            |
| `role`        | string\|null | `"user"`, `"assistant"`, `"system"` |
| `content`     | string\|null | message text                        |
| `citations`   | string\|null | JSON string of citations            |
| `token_count` | int\|null    |                                     |
| `attachments` | string\|null | JSON string of attachment refs      |

**Response `201`** — `ChatMessageRecord`

---

### `PATCH /chats/messages/{message_id}`

Partially update a message.

**Request body** — `ChatMessagePatch` (all fields optional)  
**Response `200`** — `ChatMessageRecord`

---

### `DELETE /chats/messages/{message_id}`

Delete a message.

**Response `204`** — No content

---

## Chat Attachments

### `GET /chats/attachments`

List attachments.

**Query params:**

| Param               | Type                                                    | Default        | Notes                                   |
| ------------------- | ------------------------------------------------------- | -------------- | --------------------------------------- |
| `page`              | int                                                     | `1`            |                                         |
| `size`              | int                                                     | `20`           | 1–200                                   |
| `messageId`         | string                                                  | —              | filter by message                       |
| `attachmentType`    | string                                                  | —              | exact match                             |
| `minAttachmentSize` | int                                                     | —              | bytes (>=)                              |
| `maxAttachmentSize` | int                                                     | —              | bytes (<=)                              |
| `pathContains`      | string                                                  | —              | case-insensitive attachment path search |
| `sortBy`            | `"created_at"` \| `"updated_at"` \| `"attachment_size"` | `"created_at"` |                                         |
| `sortOrder`         | `"asc"` \| `"desc"`                                     | `"desc"`       |                                         |

**Response `200`** — `ChatAttachmentListResponse`

```json
{
  "items": [
    {
      "attachment_id": "uuid",
      "message_id": "message-uuid",
      "attachment_type": "image",
      "attachment_path": "/bucket/uuid/image/photo.png",
      "attachment_size": 204800,
      "created_at": "2026-03-14T10:00:00+00:00",
      "updated_at": "2026-03-14T10:00:00+00:00"
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /chats/attachments/{attachment_id}`

Get a single attachment.

**Response `200`** — `ChatAttachmentRecord`

---

### `POST /chats/attachments`

Create an attachment record.

**Request body** — `ChatAttachmentCreate`

```json
{
  "message_id": "message-uuid",
  "attachment_type": "image",
  "attachment_path": "bucket-uuid/image/photo.png",
  "attachment_size": 204800
}
```

**Response `201`** — `ChatAttachmentRecord`

---

### `PATCH /chats/attachments/{attachment_id}`

Partially update an attachment.

**Request body** — `ChatAttachmentPatch`  
**Response `200`** — `ChatAttachmentRecord`

---

### `DELETE /chats/attachments/{attachment_id}`

Delete an attachment.

**Response `204`** — No content

---

---

# 5. Bucket API

**Prefix:** `/bucket`

Buckets are named storage containers. Each bucket maps to a physical directory on disk structured as:

```
src/store/bucket/<bucket_id>/
  image/
  audio/
  video/
    files/
  other/
```

File format is auto-detected from the extension and routed to the correct subfolder. The stored `file_path` (relative path) is saved in the DB and can be used to construct download URLs.

---

## Buckets

## Asset Access URL

Any stored bucket/workspace asset can be fetched using this endpoint.

### `GET /bucket/assets/{asset_path}`

`asset_path` should be the stored DB path, for example:

- `bucket-uuid/image/photo.png`
- `workspace/banner/9bd4d6b7a6f5f5ad4f23a31b5ab4f89b.png`

**Response `200`** — file stream  
**Response `404`** — file not found

---

### `GET /bucket/`

List all buckets.

**Query params:**

| Param           | Type                                                                              | Default        | Notes                               |
| --------------- | --------------------------------------------------------------------------------- | -------------- | ----------------------------------- |
| `page`          | int                                                                               | `1`            |                                     |
| `size`          | int                                                                               | `20`           | 1–200                               |
| `createdBy`     | string                                                                            | —              | filter by creator                   |
| `nameContains`  | string                                                                            | —              | case-insensitive bucket name search |
| `status`        | boolean                                                                           | —              | exact match                         |
| `deletable`     | boolean                                                                           | —              | exact match                         |
| `minTotalFiles` | int                                                                               | —              | minimum file count                  |
| `maxTotalFiles` | int                                                                               | —              | maximum file count                  |
| `minTotalSize`  | int                                                                               | —              | minimum bytes                       |
| `maxTotalSize`  | int                                                                               | —              | maximum bytes                       |
| `sortBy`        | `"updated_at"` \| `"created_at"` \| `"name"` \| `"total_files"` \| `"total_size"` | `"updated_at"` |                                     |
| `sortOrder`     | `"asc"` \| `"desc"`                                                               | `"desc"`       |                                     |

**Response `200`** — `BucketListResponse`

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Research Assets",
      "allowed_file_types": "pdf,png,jpg",
      "description": "Main research bucket",
      "deletable": true,
      "status": true,
      "total_files": 5,
      "total_size": 1048576,
      "created_by": "user-123",
      "created_at": "2026-03-14T10:00:00+00:00",
      "updated_at": "2026-03-14T10:00:00+00:00"
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /bucket/{bucket_id}`

Get a single bucket.

**Response `200`** — `BucketRecord`  
**Response `404`** — Not found

---

### `POST /bucket/`

Create a bucket. This also creates the physical directory tree on disk.

**Request body** — `BucketCreate`

```json
{
  "name": "Research Assets",
  "allowed_file_types": "pdf,png,jpg,mp4",
  "description": "Stores all research files",
  "deletable": true,
  "status": true,
  "created_by": "user-123"
}
```

| Field                | Type         | Required | Notes                      |
| -------------------- | ------------ | -------- | -------------------------- |
| `name`               | string       | ✅       | 2–100 chars                |
| `allowed_file_types` | string       | ✅       | comma-separated extensions |
| `description`        | string\|null | ❌       |                            |
| `deletable`          | boolean      | ❌       | default `true`             |
| `status`             | boolean      | ❌       | default `true` (active)    |
| `created_by`         | string       | ✅       | user identifier            |

**Response `201`** — `BucketRecord`

---

### `PUT /bucket/{bucket_id}`

Fully replace a bucket record.

**Request body** — same as `POST /bucket/`  
**Response `200`** — `BucketRecord`

---

### `PATCH /bucket/{bucket_id}`

Partially update a bucket.

**Request body** — `BucketPatch` (all fields optional)

```json
{
  "name": "Updated Bucket Name",
  "status": false
}
```

**Response `200`** — `BucketRecord`

---

### `DELETE /bucket/{bucket_id}`

Delete a bucket, all its item DB records, and the physical directory on disk.

**Response `204`** — No content  
**Response `404`** — Not found

---

## File Upload

### `POST /bucket/{bucket_id}/upload`

Upload a **single file** to a bucket. The file is saved to disk and a `bucket_items` record is created with the stored relative path. The bucket's `total_files` and `total_size` are updated automatically.

**Content-Type:** `multipart/form-data`

**Form field:**

| Field  | Type | Required |
| ------ | ---- | -------- |
| `file` | file | ✅       |

**Query params:**

| Param                   | Type   | Required | Notes                           |
| ----------------------- | ------ | -------- | ------------------------------- |
| `created_by`            | string | ✅       | user identifier                 |
| `source`                | string | ❌       | origin of the file              |
| `summary`               | string | ❌       | description of the file         |
| `connectedWorkspaceIds` | string | ❌       | comma-separated workspace UUIDs |

**Example (fetch):**

```js
const form = new FormData();
form.append("file", fileInput.files[0]);

const res = await fetch(`/bucket/${bucketId}/upload?created_by=user-123`, {
  method: "POST",
  body: form,
});
const item = await res.json();
```

**Response `201`** — `BucketItemRecord`

```json
{
  "id": "uuid",
  "bucket_id": "bucket-uuid",
  "connected_workspace_ids": null,
  "source": null,
  "file_name": "report.pdf",
  "file_path": "bucket-uuid/files/report.pdf",
  "file_format": "pdf",
  "file_size": 204800,
  "summary": null,
  "is_deleted": false,
  "created_by": "user-123",
  "created_at": "2026-03-14T10:00:00+00:00",
  "updated_at": "2026-03-14T10:00:00+00:00"
}
```

> `file_path` is the relative path from the bucket store root. Use it to reference the file in your app.
>
> Asset URL format: `/bucket/assets/{file_path}`

---

### `POST /bucket/{bucket_id}/upload/bulk`

Upload **multiple files** in a single request. Files are saved and each gets a DB record. Stats are synced once at the end.

**Content-Type:** `multipart/form-data`

**Form field:**

| Field   | Type   | Required | Notes          |
| ------- | ------ | -------- | -------------- |
| `files` | file[] | ✅       | multiple files |

**Query params:** same as single upload (`created_by`, `source`, `summary`, `connectedWorkspaceIds`)

**Example (fetch):**

```js
const form = new FormData();
for (const file of fileInput.files) {
  form.append("files", file);
}

const res = await fetch(`/bucket/${bucketId}/upload/bulk?created_by=user-123`, {
  method: "POST",
  body: form,
});
const items = await res.json(); // BucketItemRecord[]
```

**Response `201`** — `BucketItemRecord[]`

---

## Bucket Items

### `GET /bucket/items`

List bucket items.

**Query params:**

| Param              | Type                                                               | Default        | Notes                            |
| ------------------ | ------------------------------------------------------------------ | -------------- | -------------------------------- |
| `page`             | int                                                                | `1`            |                                  |
| `size`             | int                                                                | `20`           | 1–200                            |
| `bucketId`         | string                                                             | —              | filter by bucket                 |
| `workspaceId`      | string                                                             | —              | filter by linked workspace id    |
| `fileFormat`       | string                                                             | —              | exact extension match            |
| `source`           | string                                                             | —              | exact match                      |
| `createdBy`        | string                                                             | —              | exact match                      |
| `isDeleted`        | boolean                                                            | —              | exact match                      |
| `minFileSize`      | int                                                                | —              | bytes (>=)                       |
| `maxFileSize`      | int                                                                | —              | bytes (<=)                       |
| `fileNameContains` | string                                                             | —              | case-insensitive filename search |
| `filePathContains` | string                                                             | —              | case-insensitive path search     |
| `sortBy`           | `"updated_at"` \| `"created_at"` \| `"file_name"` \| `"file_size"` | `"updated_at"` |                                  |
| `sortOrder`        | `"asc"` \| `"desc"`                                                | `"desc"`       |                                  |

**Response `200`** — `BucketItemListResponse`

```json
{
  "items": [
    {
      "id": "uuid",
      "bucket_id": "bucket-uuid",
      "connected_workspace_ids": "ws-uuid-1,ws-uuid-2",
      "source": "upload",
      "file_name": "diagram.png",
      "file_path": "bucket-uuid/image/diagram.png",
      "file_format": "png",
      "file_size": 51200,
      "summary": null,
      "is_deleted": false,
      "created_by": "user-123",
      "created_at": "2026-03-14T10:00:00+00:00",
      "updated_at": "2026-03-14T10:00:00+00:00"
    }
  ],
  "page": 1,
  "size": 20,
  "total_items": 1,
  "total_pages": 1,
  "offset": 0
}
```

---

### `GET /bucket/items/{item_id}`

Get a single bucket item.

**Response `200`** — `BucketItemRecord`  
**Response `404`** — Not found

---

### `GET /bucket/items/{item_id}/asset`

Get the actual uploaded file stream for a bucket item by item id.

**Response `200`** — file stream  
**Response `404`** — item or file not found

---

### `POST /bucket/items`

Manually register a bucket item (without uploading — for items already on disk or at external URLs).

**Request body** — `BucketItemCreate`

```json
{
  "bucket_id": "bucket-uuid",
  "file_name": "report.pdf",
  "file_path": "bucket-uuid/files/report.pdf",
  "file_format": "pdf",
  "file_size": 204800,
  "created_by": "user-123"
}
```

| Field                     | Type         | Required                      |
| ------------------------- | ------------ | ----------------------------- |
| `bucket_id`               | string       | ✅                            |
| `file_name`               | string       | ✅                            |
| `file_path`               | string       | ✅ relative or absolute path  |
| `file_format`             | string       | ✅ file extension without dot |
| `file_size`               | int          | ✅ bytes                      |
| `created_by`              | string       | ✅                            |
| `source`                  | string\|null | ❌                            |
| `summary`                 | string\|null | ❌                            |
| `connected_workspace_ids` | string\|null | ❌ comma-separated            |
| `is_deleted`              | boolean      | ❌ default `false`            |

**Response `201`** — `BucketItemRecord`

---

### `PUT /bucket/items/{item_id}`

Fully replace a bucket item record.

**Request body** — `BucketItemCreate`  
**Response `200`** — `BucketItemRecord`

---

### `PATCH /bucket/items/{item_id}`

Partially update a bucket item.

**Request body** — `BucketItemPatch` (all fields optional)

```json
{
  "summary": "Annual report for Q1 2026",
  "is_deleted": false
}
```

**Response `200`** — `BucketItemRecord`

---

### `DELETE /bucket/items/{item_id}`

Delete a bucket item DB record and remove its physical file from disk. Updates bucket stats.

**Response `204`** — No content  
**Response `404`** — Not found

---

---

# 6. Settings API

**Prefix:** `/settings`

Settings is a **singleton** — there is at most one row in the DB. All endpoints operate on that single record.

---

### `GET /settings/`

Get the current settings.

**Response `200`** — `SettingsRecord`

```json
{
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "user_bio": null,
  "theme": "dark",
  "color_mode": "default",
  "max_depth_search": null,
  "default_report_fmt": "md",
  "default_research_template": "quick_summary",
  "default_bucket": null,
  "notification_on_complete_research": true,
  "show_error_on_alerts": true,
  "sound_effect": true,
  "default_model": null,
  "ai_name": null,
  "ai_personality": null,
  "ai_custom_prompt": null,
  "stream_response": true,
  "show_citations": true,
  "thinking_in_chats": true,
  "keep_backup": true,
  "temperory_data_retention": 30
}
```

**Response `404`** — No settings exist yet (use `POST` to create)

---

### `POST /settings/`

Create the settings record (only once — use `PUT`/`PATCH` to update afterwards).

**Request body** — `SettingsRecord` (all fields optional)

```json
{
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "theme": "dark",
  "color_mode": "default",
  "default_report_fmt": "md",
  "default_research_template": "quick_summary",
  "stream_response": true
}
```

**Enum values:**

| Field                       | Values                                                                                                                                       |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `theme`                     | `"system"`, `"light"`, `"dark"`                                                                                                              |
| `color_mode`                | `"default"`, `"coffee"`, `"fresh"`, `"nerd"`, `"smooth"`                                                                                     |
| `default_report_fmt`        | `"md"`, `"html"`, `"pdf"`, `"docx"`                                                                                                          |
| `default_research_template` | `"comprehensive"`, `"quick_summary"`, `"academic"`, `"market_analysis"`, `"technical_insights"`, `"comparative_study"`, `"vacation_planner"` |

**Response `201`** — `SettingsRecord`  
**Response `409`** — Settings already exist

---

### `PUT /settings/`

Fully replace settings (overwrites the entire row).

**Request body** — `SettingsRecord`  
**Response `200`** — `SettingsRecord`

---

### `PATCH /settings/`

Partially update settings (only send fields to change).

**Request body** — `SettingsPatch` (all fields optional)

```json
{
  "theme": "light",
  "sound_effect": false
}
```

**Response `200`** — `SettingsRecord`

---

### `DELETE /settings/`

Delete the settings record.

**Response `204`** — No content

---

---

# Pagination Shape (Common)

All paginated list responses share this envelope:

```json
{
  "items": [ ... ],
  "page": 1,
  "size": 20,
  "total_items": 42,
  "total_pages": 3,
  "offset": 0
}
```

> `HistoryItemResponse` uses `history_items` instead of `items`, and omits `size` and `total_items`.

---

# File Format → Subfolder Routing

When uploading files, the backend automatically places them in the correct subfolder:

| Extensions                                                                   | Subfolder |
| ---------------------------------------------------------------------------- | --------- |
| jpg, jpeg, png, gif, webp, svg, bmp, tiff, ico                               | `image/`  |
| mp4, avi, mov, mkv, wmv, flv, webm                                           | `video/`  |
| mp3, wav, ogg, flac, aac, m4a                                                | `audio/`  |
| pdf, doc, docx, xls, xlsx, ppt, pptx, txt, csv, json, xml, zip, tar, gz, rar | `files/`  |
| anything else                                                                | `other/`  |

---

# Common ID Format

All resource IDs are **UUID v4 strings** generated server-side. You never need to generate them on the frontend — just omit the `id` field and the server will create one.

---
