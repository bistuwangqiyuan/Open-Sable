#!/usr/bin/env python3
"""
Instagram Browser Login — Extract session cookies for instagrapi.

Opens a Chromium browser to Instagram login page.
You log in manually (handle any challenge/2FA in the browser).
Once logged in, the script extracts the session cookies and saves
them as an instagrapi-compatible session file.

Usage:
    python scripts/ig_browser_login.py [--profile sable]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright


def get_session_path(profile: str = "") -> Path:
    """Mirror opensable_home() logic."""
    base = Path.home() / ".opensable"
    if profile:
        base = base / profile
    base.mkdir(parents=True, exist_ok=True)
    return base / "ig_session.json"


def main():
    parser = argparse.ArgumentParser(description="Instagram browser login → instagrapi session")
    parser.add_argument("--profile", default="sable", help="Agent profile name (default: sable)")
    parser.add_argument("--headless", action="store_true", help="Run headless (not recommended)")
    args = parser.parse_args()

    session_path = get_session_path(args.profile)
    print(f"📸 Instagram Browser Login")
    print(f"   Profile : {args.profile}")
    print(f"   Session : {session_path}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True,
        )

        page = context.new_page()

        print("🌐 Opening Instagram login page...")
        page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")
        time.sleep(2)

        # Accept cookies dialog if present
        try:
            accept_btn = page.locator("button:has-text('Allow'), button:has-text('Accept'), button:has-text('Permitir')")
            if accept_btn.count() > 0:
                accept_btn.first.click()
                time.sleep(1)
        except Exception:
            pass

        print()
        print("=" * 60)
        print("  Log in to Instagram in the browser window.")
        print("  Handle any verification/challenge that appears.")
        print("  Once you see your feed, come back here and press Enter.")
        print("=" * 60)
        print()

        # Wait for user to log in — poll for sessionid cookie
        logged_in = False
        while not logged_in:
            input("Press Enter when you're logged in (or Ctrl+C to cancel)... ")

            cookies = context.cookies("https://www.instagram.com")
            cookie_dict = {c["name"]: c["value"] for c in cookies}

            if "sessionid" in cookie_dict:
                logged_in = True
                print(f"✅ sessionid found!")
            else:
                print("❌ No sessionid cookie yet. Make sure you're fully logged in.")
                print(f"   Cookies found: {list(cookie_dict.keys())}")

        # Extract all relevant cookies
        cookies = context.cookies("https://www.instagram.com")
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        # Get user info from page
        user_id = ""
        username = ""
        try:
            ds_user_id = cookie_dict.get("ds_user_id", "")
            if ds_user_id:
                user_id = ds_user_id
            # Try to get username from page
            username_el = page.evaluate("""
                () => {
                    try {
                        const data = window._sharedData || {};
                        return data.config?.viewer?.username || '';
                    } catch { return ''; }
                }
            """)
            if username_el:
                username = username_el
        except Exception:
            pass

        if not username:
            username = input("Enter your Instagram username: ").strip()

        # Build instagrapi-compatible session
        session_data = {
            "uuids": {
                "phone_id": f"android-{os.urandom(8).hex()}",
                "uuid": f"{os.urandom(4).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(6).hex()}",
                "client_session_id": f"{os.urandom(4).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(6).hex()}",
                "advertising_id": f"{os.urandom(4).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(6).hex()}",
                "android_device_id": f"android-{os.urandom(8).hex()}",
                "request_id": f"{os.urandom(4).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(6).hex()}",
                "tray_session_id": f"{os.urandom(4).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(2).hex()}-{os.urandom(6).hex()}",
            },
            "cookies": {c["name"]: c["value"] for c in cookies},
            "last_login": time.time(),
            "device_settings": {
                "app_version": "269.0.0.18.75",
                "android_version": 34,
                "android_release": "14",
                "dpi": "560dpi",
                "resolution": "1440x3120",
                "manufacturer": "Google",
                "device": "husky",
                "model": "Pixel 8 Pro",
                "cpu": "qcom",
                "version_code": "314665256",
            },
            "user_agent": (
                "Instagram 269.0.0.18.75 Android "
                "(34/14; 560dpi; 1440x3120; Google; Pixel 8 Pro; "
                "husky; qcom; en_US; 314665256)"
            ),
            "authorization_data": {
                "ds_user_id": cookie_dict.get("ds_user_id", user_id),
                "sessionid": cookie_dict.get("sessionid", ""),
                "mid": cookie_dict.get("mid", ""),
                "ig_did": cookie_dict.get("ig_did", ""),
                "csrftoken": cookie_dict.get("csrftoken", ""),
                "rur": cookie_dict.get("rur", ""),
            },
        }

        # Save session
        session_path.parent.mkdir(parents=True, exist_ok=True)
        with open(session_path, "w") as f:
            json.dump(session_data, f, indent=2)

        print()
        print(f"✅ Session saved to: {session_path}")
        print(f"   Username  : {username}")
        print(f"   User ID   : {cookie_dict.get('ds_user_id', '?')}")
        print(f"   Session ID: {cookie_dict.get('sessionid', '?')[:20]}...")
        print(f"   CSRF Token: {cookie_dict.get('csrftoken', '?')[:20]}...")
        print()
        print("🔄 Now restart the agent and IG should use this session.")

        browser.close()


if __name__ == "__main__":
    main()
