import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import asyncpg
from playwright.async_api import async_playwright, Page

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
    "GirlsWithGuns",
    "CountryGirls",
    "CamoGirls",
    "TacticalGirls",
    "Outdoors",
    "Bushcraft",
]

DB_CONFIG = {
    "user": "postgres",
    "password": "225225225asS",
    "database": "cbl",
    "host": "91.98.162.31",
    "port": 5432
}

STORAGE_STATE = os.getenv("PLAYWRIGHT_STORAGE_STATE")



def _validated_db_config() -> Dict[str, str]:
    missing = [key for key, value in DB_CONFIG.items() if value in (None, "")]
    if missing:
        raise RuntimeError(f"Missing DB config environment variables: {', '.join(missing)}")
    return DB_CONFIG  # type: ignore[return-value]


async def connect_db():
    return await asyncpg.connect(**_validated_db_config())


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


def parse_score_text(score_text: str) -> int:
    cleaned = score_text.strip().lower().replace("points", "").replace("point", "")
    cleaned = cleaned.replace("votes", "").replace("vote", "").strip()
    if not cleaned or cleaned in {"•"}:
        return 0
    multiplier = 1
    if cleaned.endswith("k"):
        multiplier = 1000
        cleaned = cleaned[:-1]
    try:
        value = float(cleaned)
        return int(value * multiplier)
    except ValueError:
        return 0


def parse_age_text(age_text: str) -> Optional[datetime]:
    text = age_text.strip().lower()
    now = datetime.utcnow()
    if not text:
        return None
    if text in {"just now", "moments ago"}:
        return now
    parts = text.split()
    if not parts:
        return None
    try:
        amount_str = parts[0]
        if amount_str in {"a", "an"}:
            amount = 1
        else:
            amount = float(amount_str)
    except ValueError:
        return None
    unit = parts[1] if len(parts) > 1 else ""
    if "min" in unit:
        delta = timedelta(minutes=amount)
    elif "hour" in unit or unit == "h":
        delta = timedelta(hours=amount)
    elif "sec" in unit or unit == "s":
        delta = timedelta(seconds=amount)
    else:
        return None
    return now - delta


async def load_additional_posts(page: Page, scroll_times: int = 3):
    for _ in range(scroll_times):
        await page.mouse.wheel(0, 2000)
        await asyncio.sleep(random.uniform(0.8, 1.4))


async def scrape_subreddit(conn, page: Page, subreddit: str):
    print(f"\n🔍 Scraping r/{subreddit} ...")
    url = f"https://www.reddit.com/r/{subreddit}/hot/"

    try:
        await page.goto(url, timeout=60000, wait_until="networkidle")

        # New Reddit layout: posts are <shreddit-post> elements
        post_selector = "shreddit-post"
        await page.wait_for_selector(post_selector, timeout=30000)

        # Scroll a bit to load more posts
        await load_additional_posts(page)

        posts = await page.query_selector_all(post_selector)
        valid_count = 0

        for post in posts:
            # ---- basic attributes directly on <shreddit-post> ----
            permalink = await post.get_attribute("permalink")
            title = await post.get_attribute("post-title")
            created_raw = await post.get_attribute("created-timestamp")
            score_raw = await post.get_attribute("score")
            id_attr = await post.get_attribute("id")  # e.g. "t3_1p1n96a"

            if not permalink or not title or not created_raw:
                # Skip incomplete posts
                continue

            title = title.strip()
            if not title:
                continue

            # ---- build full URL ----
            if permalink.startswith("/"):
                post_url = f"https://www.reddit.com{permalink}"
            else:
                post_url = permalink

            # ---- post_id: use ID attr if available, else parse from URL ----
            post_id = id_attr or "unknown"
            if not post_id and "/comments/" in post_url:
                try:
                    post_id = post_url.split("/comments/")[1].split("/")[0]
                except IndexError:
                    post_id = post_url

            # ---- created_at: parse created-timestamp ----
            # example: "2025-11-19T23:20:32.653000+0000"  (no colon in timezone)
            created_str = created_raw
            if created_str.endswith("+0000"):
                created_str = created_str[:-5] + "+00:00"

            try:
                datetime_value = datetime.fromisoformat(created_str)
            except ValueError:
                # fallback: try time element inside faceplate-timeago, or skip
                time_el = await post.query_selector("faceplate-timeago time")
                datetime_value = None
                if time_el:
                    dt_attr = await time_el.get_attribute("datetime")
                    if dt_attr:
                        try:
                            datetime_value = datetime.fromisoformat(
                                dt_attr.replace("Z", "+00:00")
                            )
                        except ValueError:
                            datetime_value = None

            if not datetime_value:
                print("⛔ No timestamp")
                continue

            age_hours = (
                datetime.utcnow() - datetime_value.replace(tzinfo=None)
            ).total_seconds() / 3600.0
            if age_hours > POST_MAX_AGE_HOURS:
                print(f"⛔ Too old ({round(age_hours)}h)")
                continue

            # ---- score ----
            score = 0
            if score_raw:
                try:
                    score = int(score_raw)
                except ValueError:
                    score = parse_score_text(score_raw)

            print(f"✅ Valid new post: {post_url}")
            await insert_reddit_post(
                conn,
                subreddit,
                post_id,
                post_url,
                score,
                datetime_value.replace(tzinfo=None),
            )
            valid_count += 1

        if valid_count == 0:
            print(f"⚠ No suitable posts found for r/{subreddit}")

    except Exception as e:
        print(f"❌ Error scraping r/{subreddit}: {e}")
        await page.screenshot(path=f"debug_error_{subreddit}.png", full_page=True)


async def get_subreddits_for_this_loop() -> List[str]:
    if not SUBREDDITS:
        return []
    batch_size = min(len(SUBREDDITS), random.randint(BATCH_MIN, BATCH_MAX))
    selected = random.sample(SUBREDDITS, batch_size)
    return selected


async def run_scraper():
    conn = await connect_db()
    print("✅ DB connected!\n")

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

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context_args = {}
            if STORAGE_STATE:
                context_args["storage_state"] = STORAGE_STATE
            context = await browser.new_context(**context_args)
            page = await context.new_page()

            for subreddit in subreddits:
                try:
                    await scrape_subreddit(conn, page, subreddit)
                except Exception as e:
                    print(f"⚠ Error on r/{subreddit}: {e}")

                wait_s = random.randint(SUBREDDIT_COOLDOWN_MIN_SEC, SUBREDDIT_COOLDOWN_MAX_SEC)
                print(f"⏳ Cooldown: {wait_s}s\n")
                await asyncio.sleep(wait_s)

            await context.close()
            await browser.close()

        loop_wait = random.randint(LOOP_DELAY_MIN_SEC, LOOP_DELAY_MAX_SEC)
        mins = round(loop_wait / 60, 1)
        print(f"✅ Run finished. Next loop in ~{mins} min ({loop_wait}s)\n")
        await asyncio.sleep(loop_wait)


if __name__ == "__main__":
    print("🚀 Starting Reddit subreddit scraper...")
    asyncio.run(run_scraper())

