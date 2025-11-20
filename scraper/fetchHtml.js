import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { log, error, warn } from '../utils/logger.js';

// Use stealth plugin to avoid detection
puppeteer.use(StealthPlugin());

/**
 * Detects if Reddit has blocked the request
 * @param {string} html - HTML content to check
 * @returns {boolean}
 */
function isBlocked(html) {
  if (!html || html.length === 0) {
    return true;
  }
  
  const lowerHtml = html.toLowerCase();
  
  // Check for blocked indicators
  if (lowerHtml.includes('blocked') || 
      lowerHtml.includes('access denied') ||
      lowerHtml.includes('varnish') ||
      (lowerHtml.includes('cloudflare') && lowerHtml.includes('checking'))) {
    return true;
  }
  
  // Check for empty body
  if (html.includes('<body></body>') || html.includes('<body> </body>')) {
    return true;
  }
  
  // Check for generic Reddit title without content
  if (html.includes('<title>reddit.com</title>') && html.length < 5000) {
    return true;
  }
  
  return false;
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
 * Performs human-like scrolling on the page
 * @param {Page} page - Puppeteer page object
 */
async function humanScroll(page) {
  try {
    await page.evaluate(() => {
      window.scrollBy(0, Math.random() * 800);
    });
    await sleep(100 + Math.random() * 200);
  } catch (err) {
    // Ignore scroll errors
  }
}

/**
 * Fetches raw HTML from a Reddit subreddit using Puppeteer with anti-detection measures
 * @param {string} subreddit - Subreddit name (without r/)
 * @param {number} maxRetries - Maximum number of retries (default: 3)
 * @returns {Promise<string|null>} - Raw HTML content or null if blocked/failed
 */
export async function fetchSubredditHtml(subreddit, maxRetries = 3) {
  let browser = null;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      // Random delay before request to reduce bot detection
      if (attempt === 1) {
        const delay = 300 + Math.random() * 500;
        await sleep(delay);
      }
      
      log(`Fetching r/${subreddit}... (attempt ${attempt}/${maxRetries})`);
      
      // Determine headless mode from environment variable
      const headless = process.env.PUPPETEER_HEADLESS !== 'false';
      
      // Launch browser with anti-detection settings
      browser = await puppeteer.launch({
        headless: headless,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-blink-features=AutomationControlled',
          '--disable-dev-shm-usage',
          '--disable-accelerated-2d-canvas',
          '--no-first-run',
          '--no-zygote',
          '--single-process',
          '--disable-gpu'
        ],
        ignoreHTTPSErrors: true,
        defaultViewport: {
          width: 1920,
          height: 1080
        }
      });
      
      const page = await browser.newPage();
      
      // Set realistic browser headers and user agent
      await page.setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
      );
      
      // Set extra headers to mimic real browser
      await page.setExtraHTTPHeaders({
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.reddit.com/',
        'sec-ch-ua': '"Chromium";v="125", "Google Chrome";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'DNT': '1'
      });
      
      // Try /hot/ first, fallback to /new/ if needed
      const urls = [
        `https://www.reddit.com/r/${subreddit}/hot/`,
        `https://www.reddit.com/r/${subreddit}/new/`
      ];
      
      let html = null;
      let navigationSuccess = false;
      
      for (const url of urls) {
        try {
          log(`Navigating to ${url}...`);
          
          // Navigate with networkidle2 to ensure page is fully loaded
          await page.goto(url, {
            waitUntil: 'networkidle2',
            timeout: 30000
          });
          
          // Wait a bit more for dynamic content
          await sleep(300 + Math.random() * 500);
          
          // Human-like scroll behavior
          await humanScroll(page);
          
          // Get the full HTML content
          html = await page.content();
          
          // Check if navigation was successful
          const pageTitle = await page.title().catch(() => '');
          if (pageTitle && !pageTitle.toLowerCase().includes('error')) {
            navigationSuccess = true;
            break;
          }
          
        } catch (navErr) {
          warn(`Navigation to ${url} failed: ${navErr.message}`);
          // Try next URL
          continue;
        }
      }
      
      // Close page
      await page.close().catch(() => {});
      
      // Check if navigation failed
      if (!navigationSuccess || !html) {
        warn(`Failed to navigate to r/${subreddit}. Retrying...`);
        if (browser) {
          await browser.close().catch(() => {});
          browser = null;
        }
        if (attempt < maxRetries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 1000, 5000);
          await sleep(backoffDelay);
          continue;
        }
        return null;
      }
      
      // Check if HTML is empty
      if (!html || html.length === 0) {
        warn(`Empty HTML response for r/${subreddit}. Retrying...`);
        if (browser) {
          await browser.close().catch(() => {});
          browser = null;
        }
        if (attempt < maxRetries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 1000, 5000);
          await sleep(backoffDelay);
          continue;
        }
        return null;
      }
      
      // Check if blocked by content analysis
      if (isBlocked(html)) {
        warn(`Blocked by Reddit (403 fallback) for r/${subreddit}. Retrying...`);
        if (browser) {
          await browser.close().catch(() => {});
          browser = null;
        }
        if (attempt < maxRetries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 1000, 5000);
          await sleep(backoffDelay);
          continue;
        }
        return null;
      }
      
      // Success! Close browser and return HTML
      if (browser) {
        await browser.close().catch(() => {});
        browser = null;
      }
      
      log(`Successfully fetched r/${subreddit} (${html.length} bytes)`);
      return html;
      
    } catch (err) {
      // Clean up browser on error
      if (browser) {
        try {
          await browser.close();
        } catch (closeErr) {
          // Ignore close errors
        }
        browser = null;
      }
      
      // Handle timeout errors
      if (err.name === 'TimeoutError' || err.message.includes('timeout')) {
        warn(`Timeout fetching r/${subreddit}. Retrying...`);
        if (attempt < maxRetries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 1000, 5000);
          await sleep(backoffDelay);
          continue;
        }
        return null;
      }
      
      // Handle navigation errors
      if (err.message.includes('Navigation') || err.message.includes('net::')) {
        warn(`Navigation error for r/${subreddit}: ${err.message}. Retrying...`);
        if (attempt < maxRetries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 1000, 5000);
          await sleep(backoffDelay);
          continue;
        }
        return null;
      }
      
      // Other errors
      error(`Failed to fetch r/${subreddit} (attempt ${attempt}/${maxRetries})`, err);
      if (attempt < maxRetries) {
        const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 1000, 5000);
        await sleep(backoffDelay);
        continue;
      }
      return null;
    }
  }
  
  // All retries exhausted
  error(`Failed to fetch r/${subreddit} after ${maxRetries} attempts`);
  return null;
}
