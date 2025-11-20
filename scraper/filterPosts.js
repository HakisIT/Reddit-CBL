import { log } from '../utils/logger.js';

/**
 * Filters posts based on quality and age criteria
 * @param {Array<Object>} posts - Array of post objects
 * @param {Object} options - Filter options
 * @param {number} options.maxAgeMinutes - Maximum age in minutes (default: 180)
 * @param {Function} options.hasTask - Function to check if post is already in queue
 * @returns {Array<Object>} - Filtered posts
 */
export function filterPosts(posts, options = {}) {
  const {
    maxAgeMinutes = 180,
    hasTask = () => false
  } = options;
  
  const filtered = posts.filter(post => {
    // Filter out posts older than maxAgeMinutes
    if (post.ageMinutes > maxAgeMinutes) {
      return false;
    }
    
    // Filter out posts with missing titles
    if (!post.title || post.title.trim().length === 0) {
      return false;
    }
    
    // Filter out posts already in task queue
    if (hasTask(post.id)) {
      return false;
    }
    
    // Note: We don't require images as some posts might be text-only
    // but still valuable. If you want to require images, uncomment:
    // if (!post.image) {
    //   return false;
    // }
    
    return true;
  });
  
  log(`Filtered ${posts.length} posts down to ${filtered.length} candidates`);
  return filtered;
}

