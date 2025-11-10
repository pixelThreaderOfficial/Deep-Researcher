# Research Agent Output Schema Documentation

## Overview

The Deep Research Agent now generates structured, comprehensive research reports with the following components:

## Research Flow

```
[START RESEARCH]
1. Generate Sub-Questions
2. Web Search & Scraping
3. Image Search (3 images)
4. RAG Knowledge Base Query
5. YouTube Video Search (2 relevant videos)
6. News Search (recent updates)
7. Generate Structured Report
[END RESEARCH]
```

## Output Schema

### Main Response Structure

```json
{
  "type": "result",
  "data": {
    "answer": "string (markdown formatted)",
    "sub_questions": ["array of strings"],
    "sources": ["array of URLs"],
    "references": [{...}],  // NEW: Structured references
    "images": [{...}],
    "youtube": {...},
    "news": {...},
    "rag_results": [{...}],
    "research_slug": "string",
    "metadata": {...}
  }
}
```

## Detailed Field Descriptions

### 1. `answer` (string)

Structured markdown content in the following format:

```markdown
[START RESEARCH]

## Introduction

- Clear, engaging introduction (2-3 paragraphs)
- Context setting
- Topic importance explanation

## Main Analysis

- Detailed comprehensive analysis
- Addresses user query and sub-questions
- Key concepts and definitions
- Detailed explanations
- Important facts and data
- Expert insights from sources
- Practical applications/examples
- Natural source citations

## YouTube Resources

We found 2 highly relevant videos:

1. **Video Title** by Channel Name

   - Description (200 chars)...
   - Watch: [URL]

2. **Video Title** by Channel Name
   - Description (200 chars)...
   - Watch: [URL]

## Related News

Recent developments and news:

1. **News Title** - Source Name
   Summary (150 chars)...

2. **News Title** - Source Name
   Summary (150 chars)...

## Conclusion

- Summary of key findings
- Clear answer to original query
- Actionable insights/recommendations
- Next steps or areas for further exploration

[END RESEARCH]
```

### 2. `sub_questions` (array)

AI-generated sub-questions for comprehensive research:

```json
[
  "What are the main components of [topic]?",
  "How does [topic] impact [related area]?",
  "What are the latest developments in [topic]?",
  "What are best practices for [topic]?",
  "What are common challenges with [topic]?"
]
```

**Count:** 3-5 questions

### 3. `sources` (array)

URLs of scraped web pages:

```json
[
  "https://example.com/page1",
  "https://example.com/page2",
  "https://example.com/page3"
]
```

**Count:** Up to 5 URLs

### 4. `references` (array) ⭐ NEW

Structured list of all references with metadata for easy frontend manipulation:

```json
[
  {
    "id": 1,
    "url": "https://example.com/article",
    "title": "Understanding Machine Learning",
    "type": "web",
    "snippet": "Article summary or excerpt..."
  },
  {
    "id": 2,
    "url": "https://example.com/guide",
    "title": "Complete ML Guide",
    "type": "web",
    "snippet": "Comprehensive guide to..."
  },
  {
    "id": 3,
    "url": "https://youtube.com/watch?v=abc123",
    "title": "ML Explained",
    "type": "youtube",
    "channel": "Tech Education",
    "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg"
  },
  {
    "id": 4,
    "url": "https://technews.com/ml-breakthrough",
    "title": "New ML Breakthrough",
    "type": "news",
    "source": "Tech News",
    "date": "2025-11-10"
  }
]
```

**Types:**

- `web` - Web article/page
- `youtube` - YouTube video
- `news` - News article

**Common Fields:**

- `id`: Sequential reference number
- `url`: Reference URL
- `title`: Reference title
- `type`: Reference type (web/youtube/news)

**Type-Specific Fields:**

**Web:**

- `snippet`: Article excerpt (200 chars)

**YouTube:**

- `channel`: Channel name
- `thumbnail`: Video thumbnail URL

**News:**

- `source`: News source name
- `date`: Publication date

### 5. `images` (object array)

Relevant images with metadata:

```json
[
  {
    "url": "https://example.com/image1.jpg",
    "file_url": "/bucket/_generated/images/20251110_123456_abc123.jpg",
    "file_id": "uuid",
    "title": "Image description"
  },
  {
    "url": "https://example.com/image2.jpg",
    "file_url": "/bucket/_generated/images/20251110_123457_def456.jpg",
    "file_id": "uuid",
    "title": "Image description"
  },
  {
    "url": "https://example.com/image3.jpg",
    "file_url": "/bucket/_generated/images/20251110_123458_ghi789.jpg",
    "file_id": "uuid",
    "title": "Image description"
  }
]
```

**Count:** Up to 3 images (when query needs images)

**Fields:**

- `url`: Original image URL
- `file_url`: Saved file location in bucket
- `file_id`: Database ID
- `title`: Image title/description

### 6. `youtube` (object)

YouTube video data with metadata:

```json
{
  "file_url": "/bucket/_generated/docs/youtube_20251110_123456_abc123.json",
  "file_id": "uuid",
  "videos": [
    {
      "url": "https://youtube.com/watch?v=abc123",
      "title": "Video Title",
      "description": "Full video description...",
      "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg",
      "channel": "Channel Name",
      "views": "1.2M",
      "duration": "15:30",
      "published": "2 days ago",
      "has_transcript": true
    },
    {
      "url": "https://youtube.com/watch?v=def456",
      "title": "Another Video Title",
      "description": "Full video description...",
      "thumbnail": "https://i.ytimg.com/vi/def456/maxresdefault.jpg",
      "channel": "Another Channel",
      "views": "850K",
      "duration": "22:45",
      "published": "1 week ago",
      "has_transcript": false
    }
  ]
}
```

**Count:** 2 most relevant videos

**Video Fields:**

- `url`: YouTube video URL
- `title`: Video title
- `description`: Full description
- `thumbnail`: Thumbnail image URL
- `channel`: Channel/creator name
- `views`: View count
- `duration`: Video length
- `published`: Upload date/time
- `has_transcript`: Boolean - transcript availability

### 7. `news` (object)

Recent news articles:

```json
{
  "file_url": "/bucket/_generated/docs/20251110_123456_abc123.json",
  "file_id": "uuid",
  "items": [
    {
      "title": "News Article Title",
      "url": "https://news.com/article1",
      "body": "Article summary or excerpt...",
      "source": "News Source Name",
      "date": "2025-11-10",
      "image": "https://news.com/image.jpg"
    },
    {
      "title": "Another News Title",
      "url": "https://news.com/article2",
      "body": "Article summary or excerpt...",
      "source": "Another News Source",
      "date": "2025-11-09",
      "image": "https://news.com/image2.jpg"
    }
  ]
}
```

**Count:** Up to 5 news items (when query needs news)

**News Item Fields:**

- `title`: Article headline
- `url`: Article URL
- `body`: Summary/excerpt
- `source`: News source name
- `date`: Publication date
- `image`: Article image URL

### 8. `rag_results` (array)

Knowledge base query results:

```json
[
  {
    "content": "Relevant text chunk from knowledge base...",
    "metadata": {
      "source": "URL or document name",
      "chunk_id": "uuid"
    },
    "score": 0.85
  }
]
```

**Count:** Up to 5 results

### 9. `research_slug` (string)

Unique identifier for this research session:

```
"research_2025-11-10_abc123def456"
```

### 10. `metadata` (object)

Research session metadata:

```json
{
  "research_time": 45.67,
  "sources_count": 5,
  "images_count": 3,
  "youtube_count": 2,
  "news_count": 5,
  "sub_questions_count": 4,
  "model": "gemini-2.0-flash",
  "session_id": "optional_session_id",
  "transcript_file": {
    "file_id": "uuid",
    "file_url": "/bucket/_generated/docs/research_transcript.json",
    "success": true,
    "error": null
  }
}
```

**Fields:**

- `research_time`: Total seconds spent on research
- `sources_count`: Number of web sources scraped
- `images_count`: Number of images found
- `youtube_count`: Number of videos found
- `news_count`: Number of news items found
- `sub_questions_count`: Number of sub-questions generated
- `model`: AI model used
- `session_id`: Optional user session ID
- `transcript_file`: Complete research transcript file info

## Streaming Updates

During research, the agent sends progress updates:

### Progress Update

```json
{
  "type": "progress",
  "stage": "searching|scraping|saving|youtube_search|generating",
  "message": "Human-readable progress message"
}
```

**Stages:**

1. `analyzing` - Content safety & query analysis
2. `planning` - Generating sub-questions
3. `searching` - Web search
4. `scraping` - URL scraping
5. `saving` - Saving to RAG
6. `rag_query` - Querying knowledge base
7. `image_search` - Searching images
8. `news_search` - Searching news
9. `youtube_search` - Searching YouTube
10. `analyzing_data` - Processing collected data
11. `generating` - Generating final report

### Answer Chunks

```json
{
  "type": "answer_chunk",
  "chunk": "Partial answer text..."
}
```

### Error

```json
{
  "type": "error",
  "message": "Error description"
}
```

## Frontend Integration Guide

### 1. Handle Streaming Updates

```javascript
const processResearchStream = async (query) => {
  let fullAnswer = "";
  let metadata = null;

  for await (const update of researchStream(query)) {
    if (update.type === "progress") {
      updateProgressUI(update.stage, update.message);
    } else if (update.type === "answer_chunk") {
      fullAnswer += update.chunk;
      updateAnswerDisplay(fullAnswer);
    } else if (update.type === "result") {
      metadata = update.data;
      displayFinalResults(metadata);
    } else if (update.type === "error") {
      showError(update.message);
    }
  }
};
```

### 2. Parse Structured Answer

```javascript
const parseStructuredAnswer = (answer) => {
  const sections = {
    introduction: "",
    mainAnalysis: "",
    youtubeResources: "",
    relatedNews: "",
    conclusion: "",
  };

  // Split by markdown headers
  const parts = answer.split(/^## /gm);

  parts.forEach((part) => {
    if (part.startsWith("Introduction")) {
      sections.introduction = part.replace("Introduction\n", "");
    } else if (part.startsWith("Main Analysis")) {
      sections.mainAnalysis = part.replace("Main Analysis\n", "");
    } else if (part.startsWith("YouTube Resources")) {
      sections.youtubeResources = part.replace("YouTube Resources\n", "");
    } else if (part.startsWith("Related News")) {
      sections.relatedNews = part.replace("Related News\n", "");
    } else if (part.startsWith("Conclusion")) {
      sections.conclusion = part.replace("Conclusion\n", "");
    }
  });

  return sections;
};
```

### 3. Display Components

```javascript
const displayResearchResults = (data) => {
  const sections = parseStructuredAnswer(data.answer);

  // Display sub-questions
  renderSubQuestions(data.sub_questions);

  // Display introduction
  renderSection("introduction", sections.introduction);

  // Display images (3 images)
  renderImages(data.images);

  // Display main analysis
  renderSection("main-analysis", sections.mainAnalysis);

  // Display YouTube videos (2 videos with descriptions)
  renderYouTubeVideos(data.youtube.videos);

  // Display news
  renderNews(data.news.items);

  // Display conclusion
  renderSection("conclusion", sections.conclusion);

  // Display references (NEW: structured references)
  renderReferences(data.references);

  // Display metadata
  renderMetadata(data.metadata);
};
```

### 4. References Component Example ⭐ NEW

```javascript
const renderReferences = (references) => {
  const webRefs = references.filter((ref) => ref.type === "web");
  const youtubeRefs = references.filter((ref) => ref.type === "youtube");
  const newsRefs = references.filter((ref) => ref.type === "news");

  let html = '<div class="references-section">';

  // Web sources
  if (webRefs.length > 0) {
    html += '<h3>Web Sources</h3><ul class="references-list">';
    webRefs.forEach((ref) => {
      html += `
        <li class="reference-item">
          <span class="ref-number">[${ref.id}]</span>
          <a href="${ref.url}" target="_blank" class="ref-link">
            ${ref.title}
          </a>
          ${ref.snippet ? `<p class="ref-snippet">${ref.snippet}</p>` : ""}
        </li>
      `;
    });
    html += "</ul>";
  }

  // YouTube sources
  if (youtubeRefs.length > 0) {
    html += '<h3>Video Resources</h3><ul class="references-list">';
    youtubeRefs.forEach((ref) => {
      html += `
        <li class="reference-item">
          <span class="ref-number">[${ref.id}]</span>
          <a href="${ref.url}" target="_blank" class="ref-link">
            <img src="${ref.thumbnail}" alt="${ref.title}" class="ref-thumbnail">
            ${ref.title}
          </a>
          <span class="ref-channel">by ${ref.channel}</span>
        </li>
      `;
    });
    html += "</ul>";
  }

  // News sources
  if (newsRefs.length > 0) {
    html += '<h3>News Articles</h3><ul class="references-list">';
    newsRefs.forEach((ref) => {
      html += `
        <li class="reference-item">
          <span class="ref-number">[${ref.id}]</span>
          <a href="${ref.url}" target="_blank" class="ref-link">
            ${ref.title}
          </a>
          <span class="ref-meta">${ref.source} - ${ref.date}</span>
        </li>
      `;
    });
    html += "</ul>";
  }

  html += "</div>";
  document.getElementById("references-container").innerHTML = html;
};

// Quick access functions
const getWebSources = (references) =>
  references.filter((r) => r.type === "web");
const getVideoSources = (references) =>
  references.filter((r) => r.type === "youtube");
const getNewsSources = (references) =>
  references.filter((r) => r.type === "news");
const getReferenceById = (references, id) =>
  references.find((r) => r.id === id);
```

### 5. YouTube Video Component Example

```javascript
const renderYouTubeVideos = (videos) => {
  videos.forEach((video, index) => {
    const videoCard = `
      <div class="youtube-video-card">
        <img src="${video.thumbnail}" alt="${video.title}">
        <h3>${index + 1}. ${video.title}</h3>
        <p class="channel">by ${video.channel}</p>
        <p class="description">${video.description.substring(0, 200)}...</p>
        <div class="meta">
          <span>${video.views} views</span>
          <span>${video.duration}</span>
          <span>${video.published}</span>
          ${
            video.has_transcript
              ? '<span class="badge">Transcript Available</span>'
              : ""
          }
        </div>
        <a href="${video.url}" target="_blank" class="watch-btn">Watch Video</a>
      </div>
    `;
    document.getElementById("youtube-section").innerHTML += videoCard;
  });
};
```

## Example Complete Response

```json
{
  "type": "result",
  "data": {
    "answer": "[START RESEARCH]\n\n## Introduction\n...[full markdown]...\n[END RESEARCH]",
    "sub_questions": [
      "What are the core principles of deep learning?",
      "How does deep learning differ from traditional machine learning?",
      "What are the main applications of deep learning?",
      "What are current challenges in deep learning?"
    ],
    "sources": [
      "https://example.com/deep-learning-guide",
      "https://research.example.com/dl-paper",
      "https://blog.example.com/dl-tutorial"
    ],
    "references": [
      {
        "id": 1,
        "url": "https://example.com/deep-learning-guide",
        "title": "Complete Guide to Deep Learning",
        "type": "web",
        "snippet": "This comprehensive guide covers all aspects of deep learning..."
      },
      {
        "id": 2,
        "url": "https://research.example.com/dl-paper",
        "title": "Deep Learning Research Paper",
        "type": "web",
        "snippet": "Academic paper discussing recent advances in deep learning..."
      },
      {
        "id": 3,
        "url": "https://youtube.com/watch?v=abc123",
        "title": "Deep Learning Explained",
        "type": "youtube",
        "channel": "AI Education",
        "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg"
      },
      {
        "id": 4,
        "url": "https://technews.com/article",
        "title": "Breakthrough in Deep Learning Research",
        "type": "news",
        "source": "Tech News",
        "date": "2025-11-10"
      }
    ],
    "images": [
      {
        "url": "https://images.example.com/neural-network.png",
        "file_url": "/bucket/_generated/images/20251110_123456_abc123.png",
        "file_id": "img-uuid-1",
        "title": "Neural Network Architecture"
      }
    ],
    "youtube": {
      "file_url": "/bucket/_generated/docs/youtube_20251110_123456_xyz789.json",
      "file_id": "yt-uuid-1",
      "videos": [
        {
          "url": "https://youtube.com/watch?v=abc123",
          "title": "Deep Learning Explained",
          "description": "Comprehensive introduction to deep learning...",
          "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg",
          "channel": "AI Education",
          "views": "2.5M",
          "duration": "18:45",
          "published": "3 days ago",
          "has_transcript": true
        }
      ]
    },
    "news": {
      "file_url": "/bucket/_generated/docs/20251110_123456_news789.json",
      "file_id": "news-uuid-1",
      "items": [
        {
          "title": "Breakthrough in Deep Learning Research",
          "url": "https://technews.com/article",
          "body": "Researchers announce major advancement...",
          "source": "Tech News",
          "date": "2025-11-10"
        }
      ]
    },
    "rag_results": [...],
    "research_slug": "research_2025-11-10_abc123",
    "metadata": {
      "research_time": 42.5,
      "sources_count": 3,
      "images_count": 3,
      "youtube_count": 2,
      "news_count": 5,
      "sub_questions_count": 4,
      "model": "gemini-2.0-flash",
      "session_id": null,
      "transcript_file": {
        "file_id": "transcript-uuid",
        "file_url": "/bucket/_generated/docs/research_transcript.json",
        "success": true,
        "error": null
      }
    }
  }
}
```

## Storage Locations

1. **Images**: `bucket/_generated/images/`
2. **YouTube Data**: `bucket/_generated/docs/youtube_*.json`
3. **News Data**: `bucket/_generated/docs/*_news.json`
4. **Transcripts**: `bucket/_generated/docs/research_transcript.json`
5. **Scraped Pages**: `bucket/_downloads/crawls/YYYY-MM-DD-Day/*.md`
6. **RAG Vector DB**: `gemini/rag_store/rag_vector_db/chroma.sqlite3`

## API Endpoint Example

```python
@app.post("/research")
async def research_endpoint(query: str):
    async def stream_generator():
        async for update in research_agent_stream(query):
            yield json.dumps(update) + "\n"

    return StreamingResponse(
        stream_generator(),
        media_type="application/x-ndjson"
    )
```
