import { log } from '../utils/logger.js';

/**
 * Ranks posts by score per minute multiplied by subreddit priority
 * @param {Array<Object>} posts - Array of post objects
 * @param {number} subredditPriority - Priority weight for this subreddit
 * @param {number} topN - Number of top posts to return (default: 3)
 * @returns {Array<Object>} - Top N ranked posts with rank scores
 */
export function rankPosts(posts, subredditPriority, topN = 3) {
  if (posts.length === 0) {
    return [];
  }
  
  // Calculate rank for each post
  const ranked = posts.map(post => {
    // Avoid division by zero
    const ageMinutes = Math.max(post.ageMinutes, 1);
    
    // Calculate score per minute
    const scorePerMinute = post.score / ageMinutes;
    
    // Calculate total rank
    const totalRank = scorePerMinute * subredditPriority;
    
    return {
      ...post,
      scorePerMinute: scorePerMinute,
      rank: totalRank
    };
  });
  
  // Sort by rank (descending)
  ranked.sort((a, b) => b.rank - a.rank);
  
  // Return top N
  const topPosts = ranked.slice(0, topN);
  
  // Log top candidates
  topPosts.forEach(post => {
    log(`Candidate: "${post.title.substring(0, 50)}${post.title.length > 50 ? '...' : ''}" (rank: ${post.rank.toFixed(2)})`);
  });
  
  return topPosts;
}

