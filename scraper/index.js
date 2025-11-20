import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { fetchSubredditHtml } from './fetchHtml.js';
import { parsePosts } from './parsePosts.js';
import { filterPosts } from './filterPosts.js';
import { rankPosts } from './rankPosts.js';
import { taskQueue } from './taskQueue.js';
import { log, error } from '../utils/logger.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Loads subreddit configuration from JSON file
 * @returns {Object} - Configuration object
 */
function loadConfig() {
  try {
    const configPath = join(__dirname, '..', 'config', 'subreddits.json');
    const configData = readFileSync(configPath, 'utf-8');
    return JSON.parse(configData);
  } catch (err) {
    error('Failed to load config/subreddits.json', err);
    throw err;
  }
}

/**
 * Sleeps for specified milliseconds
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise}
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Processes a single subreddit
 * @param {Object} subredditConfig - Subreddit configuration
 */
async function processSubreddit(subredditConfig) {
  const { name, priority } = subredditConfig;
  
  try {
    // Fetch HTML
    const html = await fetchSubredditHtml(name);
    
    // Check if fetch was blocked or failed
    if (!html) {
      log(`Failed to fetch r/${name}, skipping`);
      return;
    }
    
    // Parse posts
    const posts = parsePosts(html, name);
    
    if (posts.length === 0) {
      log(`No posts found for r/${name}, skipping`);
      return;
    }
    
    // Filter posts
    const filtered = filterPosts(posts, {
      hasTask: (postId) => taskQueue.hasTask(postId)
    });
    
    if (filtered.length === 0) {
      log(`No valid candidates after filtering for r/${name}`);
      return;
    }
    
    // Rank posts
    const topPosts = rankPosts(filtered, priority, 3);
    
    // Add top posts to queue
    let addedCount = 0;
    for (const post of topPosts) {
      if (taskQueue.addTask(post)) {
        addedCount++;
      }
    }
    
    log(`Added ${addedCount} tasks from r/${name} to queue (queue size: ${taskQueue.size()})`);
    
  } catch (err) {
    error(`Error processing r/${name}`, err);
    // Continue with next subreddit even if one fails
  }
}

/**
 * Main scraper loop
 */
async function main() {
  log('Starting Reddit CBL Scraper...');
  
  const config = loadConfig();
  const { subreddits, scrape_interval_seconds } = config;
  
  log(`Loaded ${subreddits.length} subreddits`);
  log(`Scrape interval: ${scrape_interval_seconds} seconds`);
  
  // Initial scrape
  log('Performing initial scrape...');
  for (const subreddit of subreddits) {
    await processSubreddit(subreddit);
    // Small delay between subreddits to avoid rate limiting
    await sleep(1000);
  }
  
  // Continuous loop
  log(`Starting continuous scrape loop (every ${scrape_interval_seconds} seconds)...`);
  
  while (true) {
    await sleep(scrape_interval_seconds * 1000);
    
    log('--- Starting scrape cycle ---');
    
    for (const subreddit of subreddits) {
      await processSubreddit(subreddit);
      // Small delay between subreddits
      await sleep(1000);
    }
    
    log(`--- Scrape cycle complete (queue size: ${taskQueue.size()}) ---`);
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  log('Received SIGINT, shutting down gracefully...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  log('Received SIGTERM, shutting down gracefully...');
  process.exit(0);
});

// Start the scraper
main().catch(err => {
  error('Fatal error in main loop', err);
  process.exit(1);
});

