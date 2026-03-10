#!/usr/bin/env python3
"""
Instagram Challenge Resolver,  Fix "challenge_required" blocks.

When Instagram blocks an account with "challenge_required", this script
resolves it by:
1. Logging in with credentials
2. Requesting the challenge code (email or SMS)
3. You enter the code
4. Saves the verified session for the agent to use

Usage:
    python scripts/ig_resolve_challenge.py
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired


def get_code_from_user(username, choice):
    """Interactive prompt for the verification code."""
    print()
    print(f"📧 Instagram sent a verification code via {choice} to your account ({username})")
    print()
    while True:
        code = input("Enter the 6-digit code: ").strip()
        if code and code.isdigit() and len(code) == 6:
            return code
        print("❌ Invalid code. Must be exactly 6 digits.")


def main():
    # Load credentials from env or profile
    profile = os.environ.get("_SABLE_PROFILE", "sable")
    profile_env = Path(f"agents/{profile}/profile.env")

    if profile_env.exists():
        print(f"Loading credentials from {profile_env}...")
        with open(profile_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

    username = os.getenv("INSTAGRAM_USERNAME", "").strip()
    password = os.getenv("INSTAGRAM_PASSWORD", "").strip()

    if not username or not password:
        username = input("Instagram username: ").strip()
        password = input("Instagram password: ").strip()

    print(f"\n📸 Instagram Challenge Resolver")
    print(f"   Account: {username}")
    print(f"   Profile: {profile}")
    print()

    # Session path
    session_dir = Path.home() / ".opensable" / profile
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / "ig_session.json"

    cl = Client()

    # Set mobile device
    cl.set_device({
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
    })
    cl.set_user_agent(
        "Instagram 269.0.0.18.75 Android "
        "(34/14; 560dpi; 1440x3120; Google; Pixel 8 Pro; "
        "husky; qcom; en_US; 314665256)"
    )

    # Set the challenge code handler to our interactive prompt
    cl.challenge_code_handler = get_code_from_user

    # Load existing session if available
    if session_path.exists():
        print(f"Loading saved session from {session_path}...")
        try:
            cl.load_settings(str(session_path))
        except Exception as e:
            print(f"⚠️  Could not load session: {e}")

    print(f"\n🔐 Logging in as {username}...")
    print("   (If Instagram sends a challenge, you'll be prompted for the code)")
    print()

    try:
        cl.login(username, password)
        print("\n✅ Login successful!")

        # Verify by fetching timeline
        print("🔍 Verifying session...")
        try:
            cl.get_timeline_feed()
            print("✅ Timeline access confirmed,  session is fully active!")
        except Exception as e:
            print(f"⚠️  Timeline check failed: {e}")
            print("   Session may still work for uploads.")

        # Save session
        cl.dump_settings(str(session_path))
        print(f"\n💾 Session saved to: {session_path}")
        print("\n🔄 Restart the agent now,  Instagram should work!")

    except ChallengeRequired as e:
        print(f"\n⚠️  Challenge required: {e}")
        print("Attempting to resolve challenge...")

        try:
            # This will trigger the challenge_code_handler callback
            cl.challenge_resolve(cl.last_json)
            print("✅ Challenge resolved!")

            # Re-login after challenge
            cl.login(username, password)
            cl.dump_settings(str(session_path))
            print(f"💾 Session saved to: {session_path}")
            print("\n🔄 Restart the agent,  Instagram should work now!")

        except Exception as e2:
            print(f"❌ Challenge resolution failed: {e2}")
            print("\nTry these alternatives:")
            print("  1. Open Instagram app on your phone and approve the login")
            print("  2. Check your email for a verification link")
            print("  3. Run: python scripts/ig_browser_login.py")

    except Exception as e:
        print(f"\n❌ Login failed: {e}")
        print(f"   Error type: {type(e).__name__}")


if __name__ == "__main__":
    main()
