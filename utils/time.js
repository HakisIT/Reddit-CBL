/**
 * Converts Reddit timestamp strings to minutes
 * @param {string} timeStr - Reddit time string (e.g., "2 hours ago", "37 minutes ago", "just now")
 * @returns {number} - Age in minutes
 */
export function parseRedditTime(timeStr) {
  if (!timeStr) return 0;
  
  const normalized = timeStr.toLowerCase().trim();
  
  // Handle "just now" or empty
  if (normalized === 'just now' || normalized === 'now') {
    return 0;
  }
  
  // Extract number and unit
  const match = normalized.match(/(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago?/i);
  
  if (!match) {
    // Try to parse as "X ago" without explicit unit (assume minutes)
    const numMatch = normalized.match(/(\d+)/);
    if (numMatch) {
      return parseInt(numMatch[1], 10);
    }
    return 0;
  }
  
  const value = parseInt(match[1], 10);
  const unit = match[2].toLowerCase();
  
  // Convert to minutes
  const multipliers = {
    second: 1 / 60,
    minute: 1,
    hour: 60,
    day: 1440,
    week: 10080,
    month: 43200, // Approximate
    year: 525600 // Approximate
  };
  
  return Math.floor(value * (multipliers[unit] || 1));
}

/**
 * Gets current timestamp in minutes (since epoch)
 * @returns {number}
 */
export function getCurrentTimeMinutes() {
  return Math.floor(Date.now() / 60000);
}

