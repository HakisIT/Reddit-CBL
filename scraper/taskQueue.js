import { log } from '../utils/logger.js';

/**
 * Simple in-memory task queue
 */
class TaskQueue {
  constructor() {
    this.tasks = [];
    this.taskIds = new Set();
  }
  
  /**
   * Adds a task to the queue
   * @param {Object} post - Post object to add
   * @returns {boolean} - True if added, false if already exists
   */
  addTask(post) {
    if (!post || !post.id) {
      log('WARN: Attempted to add invalid task (missing id)');
      return false;
    }
    
    if (this.taskIds.has(post.id)) {
      log(`Task ${post.id} already in queue, skipping`);
      return false;
    }
    
    this.tasks.push({
      ...post,
      addedAt: new Date().toISOString()
    });
    
    this.taskIds.add(post.id);
    log(`Added task: ${post.id} - "${post.title.substring(0, 50)}${post.title.length > 50 ? '...' : ''}"`);
    
    return true;
  }
  
  /**
   * Gets and removes the next task from the queue
   * @returns {Object|null} - Next task or null if queue is empty
   */
  getTask() {
    if (this.tasks.length === 0) {
      return null;
    }
    
    const task = this.tasks.shift();
    this.taskIds.delete(task.id);
    return task;
  }
  
  /**
   * Checks if a task with the given ID exists in the queue
   * @param {string} postId - Post ID to check
   * @returns {boolean}
   */
  hasTask(postId) {
    return this.taskIds.has(postId);
  }
  
  /**
   * Gets the current queue size
   * @returns {number}
   */
  size() {
    return this.tasks.length;
  }
  
  /**
   * Clears all tasks from the queue
   */
  clear() {
    this.tasks = [];
    this.taskIds.clear();
    log('Task queue cleared');
  }
}

// Export singleton instance
export const taskQueue = new TaskQueue();

