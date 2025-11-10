# Files API

This backend exposes a complete Files API for the Files tab. It surfaces uploads, downloads (including web crawls), and generated artifacts stored under the `bucket/` folder and tracked in `bucket/bucket.sqlite3`.

Base path: `/api/files`

## Object shape (mapped for UI)

Each file is returned with at least:

- file_id: string (stable id)
- document_name: string (original filename)
- document_type: string (category: documents|images|audios|videos|crawls|docs)
- mime_type: string|null
- chat_id: string|null (from metadata if provided)
- size_bytes: number
- date_created: ISO string
- io_tag: uploaded|downloaded|generated|unknown (derived from source_type)
- type: uploads|downloads|generated
- file_url: public serving URL (GET /files/{type}/{filename})
- serve_path: path used by serving route (e.g., `downloads/filename.ext`)
- stored_filename: filename saved on disk
- tags: string[]
- content, content_mode: only when explicitly requested

## Endpoints

- GET `/api/files`

  - Query: `type`, `category`, `q`, `limit`, `offset`, `include_content`, `content_mode`, `content_limit`
  - Returns: `{ success, count, files: File[] }`

- GET `/api/files/{file_id}`

  - Query: `include_content`, `content_mode`, `content_limit`
  - Returns: `{ success, file: File }`

- GET `/api/files/{file_id}/download`

  - Returns raw file as an attachment.

- GET `/api/files/{file_id}/content`

  - Query: `mode=auto|text|base64`, `limit`
  - Returns: `{ success, mode, mime_type, content|content_base64 }`

- POST `/api/files/upload`

  - Form: `files: UploadFile[]`, optional `chat_id`, `content_description`, `tags` (JSON string)
  - Uses bucket storage; metadata saved with file.

- PUT `/api/files/{file_id}`

  - Query/Form: `content_description`, `tags` (repeatable), `is_active`, `chat_id` (merged into metadata)

- DELETE `/api/files/{file_id}`

  - Query: `hard=false` (soft delete by default)

- GET `/api/files/stats`

  - Returns bucket-wide stats (uploads/downloads/generated sizes and counts).

- GET `/api/files/{file_id}/stats`

  - Query: `days=30` access stats.

- GET `/api/files/search`

  - Query: `q`, `type`, `category`, `limit`, `offset`
  - Searches original/stored filename, tags, and source_metadata.

- POST `/api/files/sync-crawls`
  - Query: `dry_run=false`, `max_import=200`
  - Imports entries from Crawl4AI database (`bucket/_downloads/crawls/crawls.sqlite3`) into the bucket files DB so crawled markdown appears in Files tab. Metadata includes url, title, favicon, status_code, word_count, crawl_duration, original_crawl_path, timestamp.

## Serving static files

- GET `/files/{type}/{filename}` -> streams file by metadata lookup, logs access.

## Notes

- Web crawls created by Crawl4AI are stored as markdown files under `bucket/_downloads/crawls/YYYY-MM-DD-<day>/`. Run `/api/files/sync-crawls` to import any legacy entries into the main files database.
- To associate files with a chat, pass `chat_id` on upload or update later via PUT; it is stored in `source_metadata.chat_id`.
- Text content is auto-detected for text/\*, json, csv, md; others are provided as base64 when using `/content`.
