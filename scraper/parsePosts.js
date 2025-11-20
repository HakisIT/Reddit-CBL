import * as cheerio from 'cheerio';
import { parseRedditTime } from '../utils/time.js';
import { log, error } from '../utils/logger.js';

/**
 * Extracts post metadata from Reddit HTML
 * @param {string} html - Raw HTML content
 * @param {string} subreddit - Subreddit name for context
 * @returns {Array<Object>} - Array of post objects
 */
export function parsePosts(html, subreddit) {
  try {
    const $ = cheerio.load(html);
    const posts = [];
    
    // Reddit uses various selectors depending on the page structure
    // Try multiple selectors to find posts
    const postSelectors = [
      'div[data-testid="post-container"]',
      'div[data-subreddit]',
      'shreddit-post',
      'div.Post'
    ];
    
    let $posts = $();
    for (const selector of postSelectors) {
      $posts = $(selector);
      if ($posts.length > 0) break;
    }
    
    // Fallback: look for elements with post-like structure
    if ($posts.length === 0) {
      $posts = $('div').filter((i, el) => {
        const $el = $(el);
        return $el.attr('data-testid')?.includes('post') || 
               $el.attr('data-subreddit') === subreddit;
      });
    }
    
    // If still no posts, try to find any post-like divs with links
    if ($posts.length === 0) {
      $posts = $('a[data-click-id="body"]').parent().parent();
    }
    
    $posts.each((index, element) => {
      try {
        const $post = $(element);
        
        // Extract post ID - try multiple attributes
        const postId = $post.attr('data-fullname') || 
                      $post.attr('id')?.replace('t3_', '') ||
                      $post.find('[data-testid="post-content"]').attr('data-fullname')?.replace('t3_', '') ||
                      $post.closest('[data-fullname]').attr('data-fullname')?.replace('t3_', '') ||
                      null;
        
        if (!postId) {
          // Skip if we can't find an ID
          return;
        }
        
        // Extract title
        const title = $post.find('h3').first().text().trim() ||
                     $post.find('[data-testid="post-title"]').text().trim() ||
                     $post.find('a[data-click-id="body"]').text().trim() ||
                     $post.find('a[href*="/r/"]').first().text().trim() ||
                     '';
        
        // Extract score
        const scoreText = $post.find('[data-testid="vote-arrows"]').next().text().trim() ||
                         $post.find('button[aria-label*="vote"]').parent().text().trim() ||
                         $post.find('span').filter((i, el) => {
                           const text = $(el).text().trim();
                           return /^\d+[km]?$/i.test(text);
                         }).first().text().trim() ||
                         '0';
        
        const score = parseScore(scoreText);
        
        // Extract timestamp
        const timeText = $post.find('time').attr('title') ||
                        $post.find('time').text().trim() ||
                        $post.find('[data-testid="post_timestamp"]').text().trim() ||
                        $post.find('a[href*="/comments/"]').parent().find('span').last().text().trim() ||
                        '';
        
        const ageMinutes = parseRedditTime(timeText);
        
        // Extract image thumbnail
        const image = $post.find('img[src*="preview"]').attr('src') ||
                     $post.find('img[src*="thumbnail"]').attr('src') ||
                     $post.find('img').not('[alt*="icon"]').not('[alt*="avatar"]').first().attr('src') ||
                     $post.find('a[href*="preview"] img').attr('src') ||
                     null;
        
        // Extract direct link
        const link = $post.find('a[data-click-id="body"]').attr('href') ||
                    $post.find('a[href*="/r/"]').first().attr('href') ||
                    $post.find('a[href*="/comments/"]').first().attr('href') ||
                    '';
        
        // Make link absolute if relative
        const fullLink = link.startsWith('http') ? link : `https://www.reddit.com${link}`;
        
        // Extract flair
        const flair = $post.find('[data-testid="post-flair"]').text().trim() ||
                     $post.find('span[class*="flair"]').text().trim() ||
                     $post.find('.flair').text().trim() ||
                     null;
        
        // Only add post if it has essential data
        if (title && postId) {
          posts.push({
            id: postId,
            title: title,
            score: score,
            ageMinutes: ageMinutes,
            image: image,
            link: fullLink,
            flair: flair,
            subreddit: subreddit
          });
        }
      } catch (err) {
        // Skip malformed posts
        error(`Error parsing individual post: ${err.message}`);
      }
    });
    
    log(`Found ${posts.length} posts from r/${subreddit}`);
    return posts;
    
  } catch (err) {
    error(`Error parsing HTML for r/${subreddit}`, err);
    return [];
  }
}

/**
 * Parses score text (handles "1.2k", "500", etc.)
 * @param {string} scoreText 
 * @returns {number}
 */
function parseScore(scoreText) {
  if (!scoreText) return 0;
  
  const cleaned = scoreText.trim().replace(/[^\d.kKmM]/g, '');
  
  if (!cleaned) return 0;
  
  const num = parseFloat(cleaned);
  if (isNaN(num)) return 0;
  
  // Handle k (thousands) and m (millions)
  if (cleaned.toLowerCase().includes('k')) {
    return Math.floor(num * 1000);
  }
  if (cleaned.toLowerCase().includes('m')) {
    return Math.floor(num * 1000000);
  }
  
  return Math.floor(num);
}

