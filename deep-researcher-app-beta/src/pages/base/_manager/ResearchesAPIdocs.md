# Research Sessions API Documentation

## Overview

The Research Sessions API provides endpoints to manage, track, and query research sessions. Each research session is automatically created when a user initiates a research query via the WebSocket endpoint and is tracked throughout its lifecycle.

**Base URL**: `http://localhost:8000` (or your configured host)

---

## Table of Contents

1. [Research Session Model](#research-session-model)
2. [API Endpoints](#api-endpoints)
   - [List Research Sessions](#1-list-research-sessions)
   - [Get Research Session Details](#2-get-research-session-details)
   - [Delete Research Session](#3-delete-research-session)
   - [Get Research Statistics](#4-get-research-statistics)
   - [Search Research Sessions](#5-search-research-sessions)
   - [Update Research Title](#6-update-research-title)
3. [WebSocket Integration](#websocket-integration)
4. [Error Handling](#error-handling)
5. [Frontend Integration Examples](#frontend-integration-examples)

---

## Research Session Model

Each research session contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Auto-incrementing primary key |
| `slug` | String (UUID) | Unique identifier for the research session |
| `title` | String | Auto-generated title from query (first 60 chars) |
| `query` | String | The original user query |
| `status` | String | Current status: `'running'`, `'completed'`, or `'failed'` |
| `duration` | Float | Research duration in seconds (null while running) |
| `model` | String | AI model used (e.g., `'gemini-2.0-flash'`) |
| `resources_used` | JSON Array | List of URLs/sources used in the research |
| `datetime_start` | String (ISO) | Start timestamp (ISO 8601 format) |
| `datetime_end` | String (ISO) | End timestamp (ISO 8601 format, null while running) |
| `tags` | JSON Array | Optional tags for categorization |
| `answer` | String (Text) | Complete research answer (null until completed) |
| `metadata` | JSON Object | Additional data (images, news, RAG results, etc.) |
| `created_at` | Float | Unix timestamp of creation |
| `updated_at` | Float | Unix timestamp of last update |

---

## API Endpoints

### 1. List Research Sessions

Retrieve a paginated list of research sessions with optional status filtering.

**Endpoint**: `GET /api/research/sessions`

**Query Parameters**:
- `limit` (optional, integer, default: 50): Maximum number of results to return
- `offset` (optional, integer, default: 0): Number of results to skip for pagination
- `status` (optional, string): Filter by status - `'running'`, `'completed'`, or `'failed'`

**Example Request**:
```bash
# Get all research sessions
GET http://localhost:8000/api/research/sessions

# Get completed research sessions with pagination
GET http://localhost:8000/api/research/sessions?status=completed&limit=20&offset=0

# Get running research sessions
GET http://localhost:8000/api/research/sessions?status=running
```

**Example Response** (Success):
```json
{
  "success": true,
  "researches": [
    {
      "id": 1,
      "slug": "a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e",
      "title": "What are the latest developments in quantum computing?",
      "query": "What are the latest developments in quantum computing?",
      "status": "completed",
      "duration": 12.345,
      "model": "gemini-2.0-flash",
      "resources_used": [
        "https://example.com/quantum-news",
        "https://research.com/quantum-paper"
      ],
      "datetime_start": "2025-01-15T10:30:00.000Z",
      "datetime_end": "2025-01-15T10:30:12.345Z",
      "tags": null,
      "answer": "Recent developments in quantum computing include...",
      "metadata": {
        "images": [],
        "news": {},
        "rag_results_count": 3,
        "web_search_results_count": 10
      },
      "created_at": 1705318200.0,
      "updated_at": 1705318212.345
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

**Example Response** (Error):
```json
{
  "success": false,
  "error": "Database connection error"
}
```

---

### 2. Get Research Session Details

Retrieve detailed information about a specific research session.

**Endpoint**: `GET /api/research/sessions/{slug}`

**Path Parameters**:
- `slug` (required, string): The UUID of the research session

**Example Request**:
```bash
GET http://localhost:8000/api/research/sessions/a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e
```

**Example Response** (Success):
```json
{
  "success": true,
  "research": {
    "id": 1,
    "slug": "a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e",
    "title": "What are the latest developments in quantum computing?",
    "query": "What are the latest developments in quantum computing?",
    "status": "completed",
    "duration": 12.345,
    "model": "gemini-2.0-flash",
    "resources_used": [
      "https://example.com/quantum-news",
      "https://research.com/quantum-paper"
    ],
    "datetime_start": "2025-01-15T10:30:00.000Z",
    "datetime_end": "2025-01-15T10:30:12.345Z",
    "tags": ["quantum", "computing", "technology"],
    "answer": "Recent developments in quantum computing include significant breakthroughs in error correction, the development of more stable qubits, and advances in quantum algorithms...",
    "metadata": {
      "images": [
        {
          "url": "https://example.com/quantum-image.jpg",
          "file_url": "/files/generated/20250115_103005_abc123.jpg",
          "file_id": "file_123",
          "title": "Quantum Computer Chip"
        }
      ],
      "news": {
        "file_url": "/files/generated/20250115_103006_def456.json",
        "file_id": "file_124",
        "items": [
          {
            "title": "Major Quantum Computing Breakthrough",
            "url": "https://news.com/quantum-breakthrough",
            "date": "2025-01-14"
          }
        ]
      },
      "rag_results_count": 5,
      "web_search_results_count": 10,
      "transcript_file": {
        "file_id": "file_125",
        "file_url": "/files/generated/research_transcript.json"
      }
    },
    "created_at": 1705318200.0,
    "updated_at": 1705318212.345
  }
}
```

**Example Response** (Not Found):
```json
{
  "success": false,
  "error": "Research session not found"
}
```

---

### 3. Delete Research Session

Delete a specific research session by its slug.

**Endpoint**: `DELETE /api/research/sessions/{slug}`

**Path Parameters**:
- `slug` (required, string): The UUID of the research session

**Example Request**:
```bash
DELETE http://localhost:8000/api/research/sessions/a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e
```

**Example Response** (Success):
```json
{
  "success": true,
  "message": "Research session deleted successfully"
}
```

**Example Response** (Not Found):
```json
{
  "success": false,
  "error": "Research session not found"
}
```

---

### 4. Get Research Statistics

Get aggregated statistics about all research sessions.

**Endpoint**: `GET /api/research/stats`

**Example Request**:
```bash
GET http://localhost:8000/api/research/stats
```

**Example Response**:
```json
{
  "success": true,
  "stats": {
    "total_researches": 42,
    "completed": 38,
    "failed": 2,
    "running": 2,
    "avg_duration": 15.67,
    "unique_models": 2,
    "first_research": "2025-01-10T08:00:00.000Z",
    "last_research": "2025-01-15T14:30:00.000Z"
  }
}
```

**Field Descriptions**:
- `total_researches`: Total number of research sessions
- `completed`: Number of successfully completed sessions
- `failed`: Number of failed sessions
- `running`: Number of currently running sessions
- `avg_duration`: Average duration in seconds (for completed sessions)
- `unique_models`: Number of different AI models used
- `first_research`: Timestamp of the first research session
- `last_research`: Timestamp of the most recent research session

---

### 5. Search Research Sessions

Search for research sessions by query text, title, or answer content.

**Endpoint**: `GET /api/research/search`

**Query Parameters**:
- `q` (required, string): Search query
- `limit` (optional, integer, default: 50): Maximum number of results

**Example Request**:
```bash
GET http://localhost:8000/api/research/search?q=quantum&limit=20
```

**Example Response**:
```json
{
  "success": true,
  "results": [
    {
      "id": 1,
      "slug": "a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e",
      "title": "What are the latest developments in quantum computing?",
      "query": "What are the latest developments in quantum computing?",
      "status": "completed",
      "duration": 12.345,
      "model": "gemini-2.0-flash",
      "resources_used": ["https://example.com/quantum-news"],
      "datetime_start": "2025-01-15T10:30:00.000Z",
      "datetime_end": "2025-01-15T10:30:12.345Z",
      "tags": ["quantum", "computing"],
      "answer": "Recent developments in quantum computing include...",
      "metadata": {},
      "created_at": 1705318200.0,
      "updated_at": 1705318212.345
    }
  ],
  "count": 1,
  "query": "quantum"
}
```

---

### 6. Update Research Title

Update the title of a research session.

**Endpoint**: `PUT /api/research/sessions/{slug}/title`

**Path Parameters**:
- `slug` (required, string): The UUID of the research session

**Query Parameters**:
- `title` (required, string): New title for the research

**Example Request**:
```bash
PUT http://localhost:8000/api/research/sessions/a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e/title?title=Quantum%20Computing%20Advances%202025
```

**Example Response** (Success):
```json
{
  "success": true,
  "message": "Research title updated successfully"
}
```

**Example Response** (Not Found):
```json
{
  "success": false,
  "error": "Research session not found"
}
```

---

## WebSocket Integration

Research sessions are automatically created when users initiate research via the WebSocket endpoint:

**WebSocket Endpoint**: `ws://localhost:8000/ws/research`

**Message Format**:
```json
{
  "query": "What are the latest developments in AI?",
  "model": "gemini-2.0-flash"
}
```

**Response Messages**:

1. **Progress Updates**:
```json
{
  "type": "progress",
  "stage": "searching",
  "message": "Searching web for relevant information..."
}
```

2. **Answer Chunks** (streamed):
```json
{
  "type": "answer_chunk",
  "chunk": "Artificial intelligence has seen remarkable..."
}
```

3. **Final Result**:
```json
{
  "type": "result",
  "data": {
    "answer": "Full research answer...",
    "sources": ["https://example.com/ai-news"],
    "images": [],
    "news": {},
    "rag_results": [],
    "research_slug": "a7f3e8d2-4c1b-4a9e-8f7d-3e2a1b4c5d6e",
    "metadata": {
      "research_time": 15.67,
      "sources_count": 5,
      "images_count": 2,
      "news_count": 3,
      "model": "gemini-2.0-flash",
      "session_id": null
    }
  }
}
```

**Note**: The `research_slug` in the final result can be used to query the research session later via the REST API.

---

## Error Handling

All endpoints follow a consistent error response format:

**Error Response Structure**:
```json
{
  "success": false,
  "error": "Error message description"
}
```

**Common HTTP Status Codes**:
- `200 OK`: Successful request
- `404 Not Found`: Resource not found (e.g., invalid slug)
- `500 Internal Server Error`: Server-side error

**Common Error Scenarios**:

1. **Invalid Slug**:
```json
{
  "success": false,
  "error": "Research session not found"
}
```

2. **Database Error**:
```json
{
  "success": false,
  "error": "Database connection error"
}
```

3. **Invalid Parameters**:
```json
{
  "success": false,
  "error": "Invalid status filter. Use 'running', 'completed', or 'failed'"
}
```

---

## Frontend Integration Examples

### React/TypeScript Example

```typescript
// Types
interface ResearchSession {
  id: number;
  slug: string;
  title: string;
  query: string;
  status: 'running' | 'completed' | 'failed';
  duration: number | null;
  model: string;
  resources_used: string[];
  datetime_start: string;
  datetime_end: string | null;
  tags: string[] | null;
  answer: string | null;
  metadata: any;
  created_at: number;
  updated_at: number;
}

interface ApiResponse<T> {
  success: boolean;
  error?: string;
  [key: string]: any;
}

// API Service
class ResearchAPI {
  private baseUrl = 'http://localhost:8000';

  async listResearches(
    limit = 50,
    offset = 0,
    status?: 'running' | 'completed' | 'failed'
  ): Promise<ResearchSession[]> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (status) params.append('status', status);

    const response = await fetch(`${this.baseUrl}/api/research/sessions?${params}`);
    const data: ApiResponse<ResearchSession[]> = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to fetch researches');
    }
    
    return data.researches;
  }

  async getResearch(slug: string): Promise<ResearchSession> {
    const response = await fetch(`${this.baseUrl}/api/research/sessions/${slug}`);
    const data: ApiResponse<ResearchSession> = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Research not found');
    }
    
    return data.research;
  }

  async deleteResearch(slug: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/research/sessions/${slug}`, {
      method: 'DELETE',
    });
    const data: ApiResponse<void> = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to delete research');
    }
  }

  async getStats() {
    const response = await fetch(`${this.baseUrl}/api/research/stats`);
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to fetch stats');
    }
    
    return data.stats;
  }

  async searchResearches(query: string, limit = 50): Promise<ResearchSession[]> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString(),
    });

    const response = await fetch(`${this.baseUrl}/api/research/search?${params}`);
    const data: ApiResponse<ResearchSession[]> = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Search failed');
    }
    
    return data.results;
  }

  async updateTitle(slug: string, title: string): Promise<void> {
    const params = new URLSearchParams({ title });
    const response = await fetch(
      `${this.baseUrl}/api/research/sessions/${slug}/title?${params}`,
      { method: 'PUT' }
    );
    const data: ApiResponse<void> = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to update title');
    }
  }
}

// Usage in React Component
const ResearchList: React.FC = () => {
  const [researches, setResearches] = useState<ResearchSession[]>([]);
  const [loading, setLoading] = useState(true);
  const api = new ResearchAPI();

  useEffect(() => {
    const fetchResearches = async () => {
      try {
        const data = await api.listResearches(20, 0, 'completed');
        setResearches(data);
      } catch (error) {
        console.error('Failed to fetch researches:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchResearches();
  }, []);

  return (
    <div>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <ul>
          {researches.map((research) => (
            <li key={research.slug}>
              <h3>{research.title}</h3>
              <p>Duration: {research.duration?.toFixed(2)}s</p>
              <p>Status: {research.status}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
```

### JavaScript/Fetch Example

```javascript
// Fetch all completed researches
async function fetchCompletedResearches() {
  try {
    const response = await fetch('http://localhost:8000/api/research/sessions?status=completed&limit=10');
    const data = await response.json();
    
    if (data.success) {
      console.log('Researches:', data.researches);
    } else {
      console.error('Error:', data.error);
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
}

// Search for researches
async function searchResearches(query) {
  const url = new URL('http://localhost:8000/api/research/search');
  url.searchParams.append('q', query);
  url.searchParams.append('limit', '20');
  
  const response = await fetch(url);
  const data = await response.json();
  
  return data.success ? data.results : [];
}

// Get research details
async function getResearchDetails(slug) {
  const response = await fetch(`http://localhost:8000/api/research/sessions/${slug}`);
  const data = await response.json();
  
  if (data.success) {
    return data.research;
  } else {
    throw new Error(data.error);
  }
}
```

---

## Additional Notes

1. **Automatic Session Creation**: Research sessions are created automatically when research begins via the WebSocket. You don't need to manually create them.

2. **Status Lifecycle**:
   - `running`: Research is in progress
   - `completed`: Research finished successfully
   - `failed`: Research encountered an error

3. **Resource URLs**: The `resources_used` field contains all URLs referenced during research, including:
   - Web search result URLs
   - Image source URLs
   - News article URLs

4. **Metadata Structure**: The `metadata` field is flexible and may contain:
   - `images`: Array of image objects with URLs and file paths
   - `news`: Object with news file URL and items array
   - `rag_results_count`: Number of RAG database results used
   - `web_search_results_count`: Number of web search results processed
   - `transcript_file`: Object with research transcript file details

5. **Pagination**: Use `limit` and `offset` for efficient pagination:
   ```
   Page 1: limit=20, offset=0
   Page 2: limit=20, offset=20
   Page 3: limit=20, offset=40
   ```

6. **Timestamps**: All datetime fields use ISO 8601 format (e.g., `2025-01-15T10:30:00.000Z`)

7. **Backward Compatibility**: The research tracking system does not affect existing chat and session functionality.

---

## Support

For issues or questions, please refer to the main API documentation or contact the development team.
