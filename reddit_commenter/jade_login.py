"""One-time script to capture Jade's Reddit login session."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    """
    Launch Playwright browser and capture login session.
    
    Opens Reddit login page, waits for manual login, then saves
    the session state to storage_state.json.
    """
    # Path to save storage state (in reddit_commenter directory)
    storage_path = Path(__file__).parent / "storage_state.json"
    
    print("🚀 Launching Playwright browser for Reddit login...")
    print(f"📁 Session will be saved to: {storage_path.absolute()}")
    print()
    
    async with async_playwright() as p:
        # Launch browser in non-headless mode so user can see and interact
        browser = await p.chromium.launch(headless=False)
        
        # Create a new context (no existing storage state)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Navigate to Reddit
        print("🌐 Opening Reddit...")
        await page.goto("https://www.reddit.com/login", wait_until="networkidle")
        
        print()
        print("=" * 60)
        print("👤 Please log in as Jade in the browser window that opened.")
        print("   Once you're logged in and see the Reddit homepage,")
        print("   come back here and press Enter to save the session.")
        print("=" * 60)
        print()
        
        # Wait for user to press Enter
        input("Press Enter after you've logged in...")
        
        # Save the storage state (cookies, localStorage, etc.)
        print(f"💾 Saving session state to {storage_path}...")
        await context.storage_state(path=str(storage_path))
        
        print("✅ Session saved successfully!")
        print(f"   You can now use this session with jade_commenter.py")
        
        # Close browser
        await browser.close()
        
        print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())

