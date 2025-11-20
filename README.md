# Reddit CBL Scraper

A modular, production-ready scraper for the Reddit Comment Boost Ladder (CBL) automation system.

## Features

- ✅ Fetches raw HTML from Reddit subreddits (no API required)
- ✅ Parses posts using Cheerio
- ✅ Extracts metadata (id, title, score, age, image, link, flair)
- ✅ Computes ranking scores (score/minute × subreddit priority)
- ✅ Filters low-quality or old posts
- ✅ Maintains a local task queue
- ✅ Runs continuously on configurable intervals

## Project Structure

```
reddit-cbl/
├── scraper/
│   ├── fetchHtml.js      # HTML fetcher
│   ├── parsePosts.js     # HTML parser
│   ├── rankPosts.js      # Post ranking
│   ├── filterPosts.js    # Post filtering
│   ├── taskQueue.js      # Task queue manager
│   └── index.js          # Main run loop
├── config/
│   └── subreddits.json   # Subreddit configuration
├── utils/
│   ├── time.js           # Time parsing utilities
│   └── logger.js         # Logging utilities
└── package.json
```

## Installation

```bash
npm install
```

This will install:
- `axios` - HTTP client for fetching HTML
- `cheerio` - HTML parsing
- `dayjs` - Date/time utilities

## Configuration

Edit `config/subreddits.json` to configure:

- `scrape_interval_seconds`: How often to scrape (default: 30)
- `subreddits`: Array of subreddits with priorities

Example:
```json
{
  "scrape_interval_seconds": 30,
  "subreddits": [
    { "name": "GirlsWithGuns", "priority": 1 },
    { "name": "CountryGirls", "priority": 2 }
  ]
}
```

## Usage

Start the scraper:

```bash
npm start
```

Or directly:

```bash
node scraper/index.js
```

The scraper will:
1. Load configuration from `config/subreddits.json`
2. Fetch HTML from each subreddit
3. Parse and extract post metadata
4. Filter posts (age, quality, duplicates)
5. Rank posts by score/minute × priority
6. Add top candidates to the task queue
7. Repeat every N seconds (as configured)

## How It Works

### Ranking Formula

```
score_per_minute = upvotes / age_in_minutes
total_rank = score_per_minute × subreddit_priority
```

### Filtering Criteria

- Posts older than 180 minutes (configurable)
- Posts with missing titles
- Posts already in the task queue

### Task Queue

The in-memory task queue provides:
- `addTask(post)` - Add a post to the queue
- `getTask()` - Get and remove next task
- `hasTask(postId)` - Check if post exists in queue

## Logging

The scraper provides detailed logs:

```
[SCRAPER] Fetching r/GirlsWithGuns...
[SCRAPER] Successfully fetched r/GirlsWithGuns (45231 bytes)
[SCRAPER] Found 12 posts from r/GirlsWithGuns
[SCRAPER] Filtered 12 posts down to 8 candidates
[SCRAPER] Candidate: "Range day!" (rank: 14.7)
[SCRAPER] Added task: abc123 - "Range day!"
```

## Error Handling

- Network errors are caught and logged (continues with next subreddit)
- Malformed HTML is handled gracefully
- Invalid posts are skipped
- The scraper continues running even if individual subreddits fail

## Future Modules

This is Step 1 of the CBL system. Future modules will include:
- Puppeteer commenter
- Backend API
- AI comment generator

## Notes

- Reddit's HTML structure may change. The parser uses multiple selector fallbacks for robustness.
- Rate limiting: The scraper includes 1-second delays between subreddits to avoid overwhelming Reddit.
- The task queue is currently in-memory. Future versions will use a persistent queue (Redis, database, etc.).

