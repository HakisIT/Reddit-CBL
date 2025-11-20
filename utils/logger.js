/**
 * Simple logger utility
 */

const PREFIX = '[SCRAPER]';

/**
 * Logs an info message
 * @param {string} message 
 */
export function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`${timestamp} ${PREFIX} ${message}`);
}

/**
 * Logs an error message
 * @param {string} message 
 * @param {Error} error 
 */
export function error(message, error = null) {
  const timestamp = new Date().toISOString();
  console.error(`${timestamp} ${PREFIX} ERROR: ${message}`);
  if (error) {
    console.error(error);
  }
}

/**
 * Logs a warning message
 * @param {string} message 
 */
export function warn(message) {
  const timestamp = new Date().toISOString();
  console.warn(`${timestamp} ${PREFIX} WARN: ${message}`);
}

