"""Main commenter script for Jade Marston."""
import asyncio
import random
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

from .ai_client import generate_jade_comment
from .config import get_commenter_config, get_db_config
from .db import (
    create_pool,
    fetch_next_posts_to_comment,
    mark_commented,
    mark_failed,
)


# Path to storage state (login session)
_STORAGE_STATE_PATH = Path(__file__).parent / "storage_state.json"

# Warm-up / browsing behavior configuration
WARMUP_ENABLED = True
WARMUP_HOME_URLS = [
    "https://www.reddit.com/",
    "https://www.reddit.com/r/Outdoors/",
    "https://www.reddit.com/r/interestingasfuck/",
]
WARMUP_MIN_TOTAL_SCROLL_SEC = 20
WARMUP_MAX_TOTAL_SCROLL_SEC = 45
WARMUP_MIN_SCROLL_DELTA = 300
WARMUP_MAX_SCROLL_DELTA = 900
WARMUP_MIN_SCROLL_PAUSE_SEC = 0.8
WARMUP_MAX_SCROLL_PAUSE_SEC = 2.0
WARMUP_POST_CLICK_PROBABILITY = 0.5

MICRO_BROWSE_ENABLED = True
MICRO_BROWSE_MIN_SCROLLS = 1
MICRO_BROWSE_MAX_SCROLLS = 3
MICRO_BROWSE_MIN_SCROLL_DELTA = 200
MICRO_BROWSE_MAX_SCROLL_DELTA = 700
MICRO_BROWSE_MIN_TOTAL_SEC = 5
MICRO_BROWSE_MAX_TOTAL_SEC = 15
MICRO_BROWSE_CLICK_PROBABILITY = 0.25


async def _scroll_page(
    page: Page,
    min_delta: int,
    max_delta: int,
) -> None:
    delta = random.randint(min_delta, max_delta)
    await page.mouse.wheel(0, delta)


async def _pause(min_sec: float, max_sec: float) -> float:
    pause = random.uniform(min_sec, max_sec)
    await asyncio.sleep(pause)
    return pause


async def _open_random_feed_post(page: Page) -> bool:
    selectors = [
        "a[data-testid='post-title']:visible",
        "a[href^='https://www.reddit.com/r/']:visible",
        "a[href^='/r/']:visible",
    ]

    for selector in selectors:
        locator = page.locator(selector)
        count = await locator.count()
        if count == 0:
            continue

        target_index = random.randint(0, count - 1)
        link = locator.nth(target_index)
        try:
            await link.scroll_into_view_if_needed(timeout=5000)
            await asyncio.sleep(0.5)
            await link.click()
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            print(f"      ⚠️ Failed to open feed link ({selector}): {e}")
            continue

    return False


async def warmup_session(page: Page) -> None:
    """Perform a pre-comment browsing warm-up to mimic natural behavior."""
    if not WARMUP_ENABLED:
        return

    for url in WARMUP_HOME_URLS:
        print(f"🧊 Warm-up: opening {url} ...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"   ⚠️ Warm-up navigation failed for {url}: {e}")
            continue

        total_target = random.uniform(
            WARMUP_MIN_TOTAL_SCROLL_SEC,
            WARMUP_MAX_TOTAL_SCROLL_SEC,
        )
        elapsed = 0.0

        while elapsed < total_target:
            try:
                await _scroll_page(page, WARMUP_MIN_SCROLL_DELTA, WARMUP_MAX_SCROLL_DELTA)
            except Exception as e:
                print(f"   ⚠️ Warm-up scroll error: {e}")
                break

            pause = await _pause(WARMUP_MIN_SCROLL_PAUSE_SEC, WARMUP_MAX_SCROLL_PAUSE_SEC)
            elapsed += pause

        # Optionally open a random post and browse briefly
        if random.random() < WARMUP_POST_CLICK_PROBABILITY:
            try:
                print("   🔗 Warm-up: opening a random post...")
                opened = await _open_random_feed_post(page)
                if opened:
                    mini_target = random.uniform(5, 10)
                    mini_elapsed = 0.0
                    while mini_elapsed < mini_target:
                        await _scroll_page(page, WARMUP_MIN_SCROLL_DELTA, WARMUP_MAX_SCROLL_DELTA)
                        pause = await _pause(0.7, 1.5)
                        mini_elapsed += pause
                    await page.go_back(wait_until="domcontentloaded")
            except Exception as e:
                print(f"   ⚠️ Warm-up post browse failed: {e}")
                try:
                    await page.go_back(wait_until="domcontentloaded")
                except Exception:
                    pass


async def micro_browse_between_comments(page: Page) -> None:
    """Perform a short scrolling session between comments."""
    if not MICRO_BROWSE_ENABLED:
        return

    print("   👀 Micro browse between comments...")
    total_target = random.uniform(MICRO_BROWSE_MIN_TOTAL_SEC, MICRO_BROWSE_MAX_TOTAL_SEC)
    elapsed = 0.0
    scrolls = random.randint(MICRO_BROWSE_MIN_SCROLLS, MICRO_BROWSE_MAX_SCROLLS)

    for _ in range(scrolls):
        if elapsed >= total_target:
            break

        try:
            await _scroll_page(page, MICRO_BROWSE_MIN_SCROLL_DELTA, MICRO_BROWSE_MAX_SCROLL_DELTA)
        except Exception as e:
            print(f"      ⚠️ Micro browse scroll error: {e}")
            break

        pause = random.uniform(0.5, 2.0)
        await asyncio.sleep(pause)
        elapsed += pause

    if random.random() < MICRO_BROWSE_CLICK_PROBABILITY:
        try:
            print("      🔗 Micro browse: opening a quick related post...")
            opened = await _open_random_feed_post(page)
            if opened:
                mini_elapsed = 0.0
                mini_target = random.uniform(3, 6)
                while mini_elapsed < mini_target:
                    await _scroll_page(page, MICRO_BROWSE_MIN_SCROLL_DELTA, MICRO_BROWSE_MAX_SCROLL_DELTA)
                    pause = await _pause(0.5, 1.0)
                    mini_elapsed += pause
                await page.go_back(wait_until="domcontentloaded")
        except Exception as e:
            print(f"      ⚠️ Micro browse post open failed: {e}")
            try:
                await page.go_back(wait_until="domcontentloaded")
            except Exception:
                pass


async def open_composer(page: Page) -> bool:
    """
    Open the Reddit comment composer by clicking the trigger button.
    
    Args:
        page: Playwright page object.
        
    Returns:
        True if composer was opened successfully, False otherwise.
    """
    print("   🔍 Looking for comment composer trigger...")
    
    # Scroll down to ensure comment area is visible
    for attempt in range(1, 5):
        try:
            # Wait for the comment-composer-host to be ready
            # This ensures the async bundle has loaded
            await page.wait_for_selector(
                "comment-composer-host[slot='ready']",
                timeout=5000,
                state="visible"
            )
            
            # Now find the trigger button within the ready composer host
            # Use a more specific selector that targets the functional trigger
            trigger = await page.wait_for_selector(
                "comment-composer-host[slot='ready'] faceplate-textarea-input[data-testid='trigger-button']",
                timeout=3000,
                state="visible"
            )
            
            # Scroll the trigger into view
            await trigger.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            print(f"   👆 Clicking composer trigger...")
            await trigger.click()
            
            # Wait for the faceplate-form and shreddit-composer to appear
            await page.wait_for_selector(
                "comment-composer-host faceplate-form shreddit-composer",
                timeout=5000,
                state="visible"
            )
            
            print(f"   ✅ Composer opened successfully")
            return True
            
        except Exception as e:
            if attempt < 4:
                print(f"   ⚠️ Attempt {attempt} failed, scrolling and retrying...")
                await page.mouse.wheel(0, 600)
                await asyncio.sleep(1)
            else:
                print(f"   ❌ Could not open composer: {e}")
                return False
    
    return False

async def focus_and_type_comment(page: Page, text: str) -> bool:
    """
    Focus the Lexical editor and type the comment text with human-like delays.
    
    Args:
        page: Playwright page object.
        text: Comment text to type.
        
    Returns:
        True if typing succeeded, False otherwise.
    """
    try:
        # Find the Lexical editor within shreddit-composer
        editor_selector = "shreddit-composer div[role='textbox'][data-lexical-editor='true']"
        
        print("   🎯 Focusing editor...")
        editor = await page.wait_for_selector(
            editor_selector,
            timeout=5000,
            state="visible"
        )
        
        # Click to focus the editor
        await editor.click()
        await asyncio.sleep(0.3)
        
        print(f"   ⌨️ Typing comment ({len(text)} chars)...")
        
        # Type character by character with human-like delays
        for i, char in enumerate(text):
            # Use page.keyboard.type() for Lexical editors
            await page.keyboard.type(char)
            
            # Variable delay between characters
            delay_ms = random.randint(40, 140)
            await asyncio.sleep(delay_ms / 1000)
            
            # Occasional longer pause (simulating thinking)
            if random.random() < 0.05:  # 5% chance
                await asyncio.sleep(random.uniform(0.2, 0.5))
        
        print(f"   ✅ Typed {len(text)} characters")
        return True
        
    except Exception as e:
        print(f"   ❌ Error typing comment: {e}")
        return False


async def submit_comment(page: Page) -> tuple[bool, Optional[str]]:
    """
    Submit the comment by clicking the Comment button within the composer.
    
    Args:
        page: Playwright page object.
        
    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        print(f"   📤 Looking for submit button...")
        
        # Strategy 1: Find the button with slot="submit-button" inside shreddit-composer
        submit_selector = "shreddit-composer button[slot='submit-button']"
        
        try:
            submit_button = await page.wait_for_selector(
                submit_selector,
                timeout=3000,
                state="visible"
            )
            
            print(f"   🖱️ Clicking Comment button...")
            await submit_button.click()
            
            # Wait a moment and check if submission worked
            await asyncio.sleep(2)
            
            # Check if composer disappeared (sign of successful submission)
            composer_still_visible = await page.locator("shreddit-composer").is_visible()
            
            if not composer_still_visible:
                print(f"   ✅ Comment submitted successfully!")
                return True, None
            else:
                # Composer still there - might be an error or still processing
                await asyncio.sleep(2)
                composer_still_visible = await page.locator("shreddit-composer").is_visible()
                
                if not composer_still_visible:
                    return True, None
                else:
                    return False, "Composer still visible after submit"
                    
        except Exception as e:
            # Fallback: Try finding button by type within shreddit-composer
            try:
                fallback_selector = "shreddit-composer button[type='submit']"
                submit_button = await page.wait_for_selector(
                    fallback_selector,
                    timeout=2000,
                    state="visible"
                )
                await submit_button.click()
                await asyncio.sleep(3)
                return True, None
            except Exception:
                return False, f"Could not find submit button: {str(e)[:100]}"
    
    except Exception as e:
        return False, f"Submit error: {str(e)[:100]}"


async def comment_on_post(
    page: Page,
    post_url: str,
    subreddit: str,
    title: str,
    post_id: str,
) -> tuple[bool, Optional[str]]:
    """
    Attempt to comment on a Reddit post using Jade's account.

    Args:
        page: Playwright page object.
        post_url: Full URL of the Reddit post.
        subreddit: Subreddit name.
        title: Post title (can be empty).
        post_id: Reddit post ID (e.g. '1p2dz4v').

    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        print(f"   🌐 Navigating to post...")

        # Navigate to the post (be lenient with loading)
        try:
            await page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)  # Give Reddit a moment to render
        except PlaywrightTimeoutError:
            print("   ⚠️ Page.goto timed out, trying to continue...")
            await asyncio.sleep(2)

        # Step 1: Open the composer
        if not await open_composer(page):
            return False, "Could not open comment composer"

        # Step 2: Generate comment text
        print(f"   ✍️ Generating comment...")
        comment_text = await generate_jade_comment(subreddit, title, post_url)
        print(f"   💬 Comment preview: {comment_text[:80]}{'...' if len(comment_text) > 80 else ''}")

        # Step 3: Focus editor and type the comment
        if not await focus_and_type_comment(page, comment_text):
            return False, "Could not type comment into editor"

        # Give a moment before submitting
        await asyncio.sleep(1)

        # Step 4: Submit the comment
        success, error = await submit_comment(page)
        
        if success:
            # Extra wait to ensure submission completed
            await asyncio.sleep(2)
            return True, None
        else:
            return False, error or "Failed to submit comment"

    except PlaywrightTimeoutError as e:
        return False, f"Timeout: {str(e)[:200]}"
    except Exception as e:
        return False, f"Error: {str(e)[:200]}"


async def run_commenter_batch() -> None:
    """
    Run a single batch of commenting tasks.
    
    Fetches posts from DB, comments on them using Playwright,
    and updates the DB with results.
    """
    # Load configuration
    try:
        db_config = get_db_config()
        commenter_config = get_commenter_config()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return
    
    # Check if storage state exists
    if not _STORAGE_STATE_PATH.exists():
        print(f"❌ Storage state not found at {_STORAGE_STATE_PATH.absolute()}")
        print(f"   Please run: python -m reddit_commenter.jade_login")
        return
    
    print("🚀 Starting Jade commenter...")
    print(f"   Max comments per run: {commenter_config.max_comments_per_run}")
    print(f"   Post max age: {commenter_config.post_max_age_hours} hours")
    print(f"   Delay range: {commenter_config.min_delay_sec}-{commenter_config.max_delay_sec} seconds")
    print()
    
    # Create DB pool
    try:
        pool = await create_pool(db_config)
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return
    
    # Fetch posts to comment on
    print(f"📋 Fetching posts to comment on...")
    try:
        posts = await fetch_next_posts_to_comment(
            pool,
            limit=commenter_config.max_comments_per_run,
            post_max_age_hours=commenter_config.post_max_age_hours,
        )
        print(f"   Found {len(posts)} posts to comment on")
    except Exception as e:
        print(f"❌ Error fetching posts: {e}")
        await pool.close()
        return
    
    if not posts:
        print("✅ No posts to comment on. Exiting.")
        await pool.close()
        return
    
    # Launch Playwright with saved session
    print(f"🌐 Launching browser with saved session...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        
        # Load saved storage state (login session)
        context = await browser.new_context(
            storage_state=str(_STORAGE_STATE_PATH),
        )
        page = await context.new_page()
        
        print("✅ Browser ready")
        print()

        if WARMUP_ENABLED:
            print("🧊 Running warm-up browsing before commenting...")
            try:
                await warmup_session(page)
            except Exception as e:
                print(f"⚠️ Warm-up failed (continuing anyway): {e}")
        
        # Process each post
        processed = 0
        for i, post in enumerate(posts, 1):
            post_id = post["post_id"]
            subreddit = post["subreddit"]

            # Handle NULL titles gracefully
            raw_title = post.get("title")
            title = raw_title or ""
            title_for_log = title if title else "(no title)"

            post_url = post["post_url"]
            row_id = post["id"]
            
            print(f"[{i}/{len(posts)}] Processing: r/{subreddit} - {title_for_log[:50]}...")
            
            success, error_msg = await comment_on_post(
                page,
                post_url,
                subreddit,
                title,
                post_id,
            )
            
            if success:
                try:
                    await mark_commented(pool, row_id)
                    print(f"   ✅ Marked as commented in DB")
                except Exception as e:
                    print(f"   ⚠️ Error updating DB: {e}")
            else:
                try:
                    await mark_failed(pool, row_id, error_msg or "Unknown error")
                    print(f"   ❌ Marked as failed: {error_msg}")
                except Exception as e:
                    print(f"   ⚠️ Error updating DB: {e}")
            
            processed += 1
            
            # Random delay between comments (except after the last one)
            if i < len(posts):
                try:
                    await micro_browse_between_comments(page)
                except Exception as e:
                    print(f"⚠️ Micro browse failed (continuing anyway): {e}")

                delay = random.uniform(
                    commenter_config.min_delay_sec,
                    commenter_config.max_delay_sec,
                )
                mins = round(delay / 60, 1)
                print(f"   ⏳ Waiting {mins} min ({int(delay)}s) before next comment...")
                await asyncio.sleep(delay)
                print()
        
        # Close browser
        await browser.close()
    
    # Close DB pool
    await pool.close()
    
    print()
    print(f"✅ Batch complete! Processed {processed}/{len(posts)} posts.")


async def main() -> None:
    """Main entry point."""
    try:
        await run_commenter_batch()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())