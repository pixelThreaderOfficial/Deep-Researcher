# Deep Researcher v2 — Agent Server API

> **Base URL:** `http://localhost:8001`
>
> **Streaming Endpoints:** Return `text/event-stream` (SSE). Each packet is prefixed with `data: ` followed by a JSON object.
> **Standard Endpoints:** Return `application/json` upon completion (no streaming).
>
> **Performance Edge:** The `crawl4ai` headless browser context is initialized natively on server startup. The headless engine remains hot in memory across requests, making URL scraping practically instantaneous.

---

## Table of Contents

- [SSE Protocol](#sse-protocol)
- [1. Event Bus (Live Updates)](#1-event-bus--live-updates)
- [2. Scrape URLs](#2-scrape-urls)
- [3. Search & Scrape](#3-search--scrape)
- [4. Web Search](#4-web-search)
- [5. Summarize](#5-summarize)
- [6. Query Validate](#6-query-validate)
- [7. Process Document (PDF/DOCX)](#7-process-document-pdf--docx)
- [8. Image Search](#8-image-search)
- [9. News Search](#9-news-search)
- [10. YouTube Search](#10-youtube-search)
- [Integration Code Examples](#integration-code-examples)

---

## SSE Protocol

Every streaming endpoint follows a standard lifecycle:

```
START  →  [PROGRESS / RESULT ITEMS]  →  DONE
                                      or
                                    ERROR
```

Each SSE line (`data: {...}`) contains a JSON object with at least:

| Field     | Type    | Description                                       |
| --------- | ------- | ------------------------------------------------- |
| `success` | boolean | `true` if the event represents normal operation   |
| `type`    | string  | One of: `start`, `progress`, `result`, `done`, `error` |
| `message` | string  | Human-readable status or error description        |

---

## 1. Event Bus — Live Updates

A persistent SSE channel that receives global real-time broadcast messages from background agents (e.g. YouTube scrapers, web crawlers, search engines).

| | |
|---|---|
| **Method** | `GET` |
| **Path** | `/events/{client_id}` |
| **Content-Type** | `text/event-stream` |

### Path Parameters

| Parameter   | Type   | Required | Description                  |
| ----------- | ------ | -------- | ---------------------------- |
| `client_id` | string | ✅       | Unique identifier for your frontend session |

### Live Event Example

```json
{ "msg": "Searching YouTube for 'Bali 2026'..." }
{ "msg": "Found videos! Analyzing the top 3..." }
{ "msg": "Successfully processed video: TOP 10 Best Luxury Re..." }
{ "msg": "I'm on the internet..." }
{ "msg": "Summarizing the content..." }
```

> **Pro Tip:** Subscribe to this endpoint when the user hits the page, and display these messages in a live "Agent Activity Log".

---

## 2. Scrape URLs

Scrape specific URLs directly using the pre-warmed `crawl4ai` engine.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/scrape/urls` |
| **Content-Type** | `application/json` |
| **Response**     | `text/event-stream` |

### Payload

```json
{
  "urls": ["https://example.com"],
  "max_urls": null,
  "max_concurrent_scrape_batches": 3,
  "origin_research_id": null
}
```

### Response Flow

1. **`start` event**
2. **`item` event** (for every scraped page):
```json
{
  "success": true,
  "url": "https://example.com",
  "content": "Page markdown...",
  "scrape_duration": 1.1,
  "title": "Example",
  "favicon": "https://example.com/favicon.ico",
  "metadata": {...}
}
```
3. **`done` event**

---

## 3. Search & Scrape

Search through SearXNG, then automatically scrape the resulting URLs.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/scrape/search` |
| **Content-Type** | `application/json` |
| **Response**     | `text/event-stream` |

### Payload

```json
{
  "query": "quantum computing latest 2026",
  "max_no_url": 10,
  "max_concurrent_scrape_batches": 3,
  "origin_research_id": null
}
```

---

## 4. Web Search

Syntactic sugar proxy identical to `/scrape/search`. Used for general web queries.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/webSearch` |
| **Content-Type** | `application/json` |
| **Response**     | `text/event-stream` |

### Payload

```json
{
  "query": "best programming languages 2026",
  "max_no_url": 10
}
```

---

## 5. Summarize

Summarize raw text via Gemini given a research query.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/summarize` |
| **Content-Type** | `application/json` |
| **Response**     | `text/event-stream` |

### Payload

```json
{
  "query": "What are the key themes?",
  "content": "Raw giant text here...",
  "api_key": "your-gemini-key"
}
```

### Event Output (type: "result")

```json
{
  "success": true,
  "type": "result",
  "summary": "This text discusses..."
}
```

---

## 6. Query Validate

Mitigate prompt injections, check for safety, and normalize casing/grammar.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/query/validate` |
| **Content-Type** | `application/json` |
| **Response**     | `text/event-stream` |

### Payload

```json
{
  "query": "What is the capital of Japan?",
  "api_key": "your-gemini-key"
}
```

### Event Output (type: "result")

```json
{
  "success": true,
  "type": "result",
  "is_safe": true,
  "issue": [],
  "safe_prompt": "Answer safely: what is the capital of japan?"
}
```

---

## 7. Process Document (PDF / DOCX)

Upload a file, parse it into markdown, and (optionally) instruct Ollama to summarize the raw extracted text using your local or remote LLM endpoint.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/process-document` |
| **Content-Type** | `multipart/form-data` |
| **Response**     | `text/event-stream` |

### Form Fields 

| Form Data Key | Required | Default | Description |
| ------------- | -------- | ------- | ----------- |
| `file`        | ✅       | —       | The binary PDF or DOCX file object. |
| `filetype`    | ✅       | —       | `pdf` or `docx` |
| `summarize`   | ❌       | `false` | Pass `true` to have Ollama summarize the document right after parsing. |
| `ollama_url`  | ❌       | `http://localhost:11434/api/generate` | Adjust if Ollama runs remotely. |

### Event Output (type: "result")

```json
{
  "success": true,
  "type": "result",
  "filename": "report.pdf",
  "filetype": "pdf",
  "summarized": true,
  "summary": "This document covers quarterly earnings...",
  // NOTE: If summarize=false, it returns "content" instead of "summary"
}
```

---

## 8. Image Search

Query SearXNG exclusively to fetch a portfolio of image references.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/imageSearch` |
| **Content-Type** | `application/json` |
| **Response**     | `application/json` (NOT Streaming) |

### Payload

```json
{
  "query": "Cyberpunk City",
  "num_results": 5
}
```

### Response

```json
{
  "success": true,
  "query": "Cyberpunk City",
  "results": [
    { "title": "City 1", "url": "https://img.com/...", "source": "Bing", "img_src": "..." }
  ]
}
```

---

## 9. News Search

Execute a targeted Search specifically geared toward current News. The endpoint scrapes and returns the top articles formatted beautifully as markdown strings.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/newsSearch` |
| **Content-Type** | `application/json` |
| **Response**     | `application/json` (NOT Streaming) |

### Payload

```json
{
  "query": "OpenAI breakthroughs 2026",
  "num_results": 5
}
```

---

## 10. YouTube Search

Our ultra-resilient YouTube module. Performs heavy-lifting directly: searching data, downloading metadata, mapping transcripts, and generating dense summaries using Ollama. (Any error on a single video is gracefully isolated and skipped so the API never fails unpredictably).

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/youtubeSearch` |
| **Content-Type** | `application/json` |
| **Response**     | `application/json` (NOT Streaming) |

### Payload

```json
{
  "query": "Best resorts in Bali 2026",
  "mode": "summarize",
  "max_videos": 3,
  "summarize": false,
  "ollama_url": "http://localhost:11434/api/generate",
  "ollama_model": "qwen3.5:9b"
}
```

| Parameter    | Required | Default | Description |
| ------------ | -------- | ------- | ----------- |
| `query`      | ✅       | —       | The search prompt. |
| `mode`       | ❌       | `summarize` | Available: `summarize`, `search_only`, `video_data`, `transcript`, `full_bundle`. |
| `max_videos` | ❌       | `5`     | Number of videos to scrape concurrently. |
| `summarize`  | ❌       | `false` | Fast mode is false (returns raw giant transcript mapped to "summary"). Set to true to execute slow LLM inference constraint via Ollama. |

### Response (summarize mode)

```json
{
  "success": true,
  "mode": "summarize",
  "query": "Best resorts in Bali 2026",
  "results": [
    {
      "id": "lAVTJFqogok",
      "title": "TOP 10 Best Luxury Resorts...",
      "desc": "",
      "thumbnail": "https://i.ytimg.com/vi/...",
      "summary": "Hi guys, today we are returning... ",
      "channelName": "Travallion",
      "channelImage": ""
    }
  ]
}
```

---

## Integration Code Examples

### Full TypeScript SSE Fetch Consumer Example

```ts
const consumeSSE = async (url: string, payload: any, onEvent: (data: any) => void) => {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  if (!reader) return;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      let chunk = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);

      if (chunk.startsWith('data: ')) {
        const jsonStr = chunk.replace('data: ', '').trim();
        try {
          const data = JSON.parse(jsonStr);
          onEvent(data);
        } catch (e) {
          console.error("SSE parse error", e, jsonStr);
        }
      }
      
      boundary = buffer.indexOf('\n\n');
    }
  }
};
```

### Hooking up the Document Parser `multipart/form-data`

```javascript
const uploadDocumentAndSummarize = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('filetype', file.name.endsWith('.pdf') ? 'pdf' : 'docx');
  formData.append('summarize', 'false'); // Quick parse

  const response = await fetch('http://localhost:8001/process-document', {
    method: 'POST',
    body: formData // Note: Content-Type is inferred dynamically by browser
  });

  // Decode SSE as shown in the function above manually!
}
```
