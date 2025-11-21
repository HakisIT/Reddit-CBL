import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List

import asyncpg
import aiohttp

# ====== Human-like rotation config ======
BATCH_MIN = 13
BATCH_MAX = 31

LOOP_DELAY_MIN_SEC = 6 * 60
LOOP_DELAY_MAX_SEC = 18 * 60

SUBREDDIT_COOLDOWN_MIN_SEC = 13
SUBREDDIT_COOLDOWN_MAX_SEC = 31

POST_MAX_AGE_HOURS = 4
# ========================================

SUBREDDITS = [
    "Outdoors",
    "Bushcraft",
    "countrygirlsgonewild"
]

DB_CONFIG = {
    "user": "postgres",
    "password": "225225225asS",
    "database": "cbl",
    "host": "91.98.162.31",
    "port": 5432
}

# Realistic user agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _validated_db_config() -> Dict[str, str]:
    missing = [key for key, value in DB_CONFIG.items() if value in (None, "")]
    if missing:
        raise RuntimeError(f"Missing DB config environment variables: {', '.join(missing)}")
    return DB_CONFIG  # type: ignore[return-value]


async def connect_db():
    return await asyncpg.connect(**_validated_db_config())

async def upsert_subreddit_description(conn, subreddit: str, description: str):
    """Insert or update subreddit description text."""
    query = """
        INSERT INTO reddit_subreddits (subreddit, description, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (subreddit) DO UPDATE
        SET description = EXCLUDED.description,
            updated_at = NOW();
    """
    await conn.execute(query, subreddit, description)
    print(f"📝 Updated description for r/{subreddit} ({len(description)} chars)")

async def fetch_subreddit_description(conn, session: aiohttp.ClientSession, subreddit: str):
    """Fetch subreddit description from Reddit's about.json and store it."""
    url = f"https://www.reddit.com/r/{subreddit}/about.json"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with session.get(url, headers=headers, timeout=15) as response:
            if response.status == 403:
                print(f"🚫 Forbidden while fetching about.json for r/{subreddit}")
                return
            if response.status == 429:
                print(f"🚫 Rate limited on about.json for r/{subreddit}")
                return
            if response.status != 200:
                print(f"❌ Unexpected status {response.status} for about.json r/{subreddit}")
                return

            data = await response.json()
            sub_data = data.get("data", {}) if isinstance(data, dict) else {}

            desc = sub_data.get("public_description") or sub_data.get("description") or ""
            desc = desc.strip()

            if not desc:
                print(f"⚠️ No description found for r/{subreddit}")
                return

            await upsert_subreddit_description(conn, subreddit, desc)

    except asyncio.TimeoutError:
        print(f"⏱️ Timeout while fetching about.json for r/{subreddit}")
    except Exception as e:
        print(f"❌ Error fetching about.json for r/{subreddit}: {e}")

async def insert_reddit_post(
    conn,
    subreddit: str,
    post_id: str,
    post_url: str,
    score: int,
    created_at: datetime,
):
    query = """
        INSERT INTO reddit_posts (subreddit, post_id, post_url, score, created_at, seen_at, commented)
        VALUES ($1, $2, $3, $4, $5, NOW(), FALSE)
        ON CONFLICT (post_id) DO NOTHING;
    """
    await conn.execute(query, subreddit, post_id, post_url, score, created_at)
    print(f"✅ Saved Reddit post {post_id} from r/{subreddit}")


async def scrape_subreddit_json(conn, session: aiohttp.ClientSession, subreddit: str):
    """Scrape subreddit using Reddit's JSON API"""
    print(f"\n🔍 Scraping r/{subreddit} ...")
    await fetch_subreddit_description(conn, session, subreddit)
    
    # Reddit JSON API endpoint - add .json to any Reddit URL
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    params = {
        "limit": 100,  # Get up to 100 posts
        "raw_json": 1,  # Don't HTML-escape the JSON
    }
    
    try:
        async with session.get(url, headers=headers, params=params, timeout=30) as response:
            print(f"📡 Response status: {response.status}")
            
            if response.status == 429:
                print("🚫 Rate limited! Need to wait longer between requests")
                return
            elif response.status == 403:
                print("🚫 Access forbidden - may need to adjust user agent or IP")
                return
            elif response.status != 200:
                print(f"❌ Unexpected status code: {response.status}")
                return
            
            data = await response.json()
            
            if "data" not in data or "children" not in data["data"]:
                print("⚠️ Unexpected JSON structure")
                return
            
            posts = data["data"]["children"]
            print(f"📦 Found {len(posts)} posts in API response")
            
            valid_count = 0
            now_utc = datetime.utcnow()
            
            for post_data in posts:
                try:
                    if post_data.get("kind") != "t3":  # t3 = link/post
                        continue
                    
                    post = post_data.get("data", {})
                    
                    # Extract post data
                    post_id = post.get("id")
                    title = post.get("title", "").strip()
                    permalink = post.get("permalink", "")
                    score = post.get("score", 0)
                    created_utc = post.get("created_utc")
                    
                    if not post_id or not title or not permalink:
                        continue
                    
                    # Build full URL
                    post_url = f"https://www.reddit.com{permalink}"
                    
                    # Parse timestamp (created_utc is Unix timestamp)
                    if not created_utc:
                        continue
                    
                    created_datetime = datetime.utcfromtimestamp(created_utc)
                    
                    # Check age
                    age_hours = (now_utc - created_datetime).total_seconds() / 3600.0
                    
                    if age_hours > POST_MAX_AGE_HOURS:
                        print(f"⛔ Too old ({round(age_hours, 1)}h): {post_id}")
                        continue
                    
                    print(f"✅ Valid post: {title[:50]}... (score: {score}, age: {round(age_hours, 1)}h)")
                    
                    await insert_reddit_post(
                        conn,
                        subreddit,
                        post_id,
                        post_url,
                        score,
                        created_datetime,
                    )
                    valid_count += 1
                    
                except Exception as e:
                    print(f"⚠️ Error processing post: {e}")
                    continue
            
            if valid_count == 0:
                print(f"⚠️ No suitable posts found for r/{subreddit}")
            else:
                print(f"✅ Found {valid_count} valid posts in r/{subreddit}")
    
    except asyncio.TimeoutError:
        print(f"⏱️ Timeout while fetching r/{subreddit}")
    except Exception as e:
        print(f"❌ Error scraping r/{subreddit}: {e}")


async def get_subreddits_for_this_loop() -> List[str]:
    if not SUBREDDITS:
        return []
    batch_size = min(len(SUBREDDITS), random.randint(BATCH_MIN, BATCH_MAX))
    selected = random.sample(SUBREDDITS, batch_size)
    return selected


async def run_scraper():
    conn = await connect_db()
    print("✅ DB connected!\n")
    
    # Create persistent HTTP session
    timeout = aiohttp.ClientTimeout(total=30)
    
    while True:
        print("⏱️ Checking new reddit posts...\n")
        
        subreddits = await get_subreddits_for_this_loop()
        if not subreddits:
            backoff = random.randint(120, 240)
            print(f"😴 No subreddits configured. Sleeping {backoff}s...\n")
            await asyncio.sleep(backoff)
            continue
        
        random.shuffle(subreddits)
        print(f"🎯 This run will scrape {len(subreddits)} subreddits.\n")
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for subreddit in subreddits:
                try:
                    await scrape_subreddit_json(conn, session, subreddit)
                except Exception as e:
                    print(f"⚠️ Error on r/{subreddit}: {e}")
                
                wait_s = random.randint(SUBREDDIT_COOLDOWN_MIN_SEC, SUBREDDIT_COOLDOWN_MAX_SEC)
                print(f"⏳ Cooldown: {wait_s}s\n")
                await asyncio.sleep(wait_s)
        
        loop_wait = random.randint(LOOP_DELAY_MIN_SEC, LOOP_DELAY_MAX_SEC)
        mins = round(loop_wait / 60, 1)
        print(f"✅ Run finished. Next loop in ~{mins} min ({loop_wait}s)\n")
        await asyncio.sleep(loop_wait)


if __name__ == "__main__":
    print("🚀 Starting Reddit JSON API scraper...")
    asyncio.run(run_scraper())