"""
Instagram Skill — Post, search, interact on Instagram using instagrapi.

Uses the instagrapi library (unofficial Instagram Private API wrapper).
Authenticates with your Instagram account credentials (username + password).
Supports session persistence to avoid repeated logins.

Features:
- Upload photos, videos, reels, stories, albums
- Search users, hashtags, locations
- Like, comment, follow/unfollow
- Get user profiles and feeds
- Send/read Direct Messages
- Get insights and story data
- Download media content

Setup:
    Set these in .env:
        INSTAGRAM_USERNAME=your_ig_username
        INSTAGRAM_PASSWORD=your_ig_password

    Install:
        pip install instagrapi
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensable.core.paths import opensable_home

logger = logging.getLogger(__name__)

try:
    from instagrapi import Client as InstaClient
    from instagrapi.exceptions import (
        LoginRequired,
        ChallengeRequired,
        TwoFactorRequired,
    )

    INSTAGRAPI_AVAILABLE = True
except ImportError:
    INSTAGRAPI_AVAILABLE = False
    logger.info("instagrapi not installed. Install with: pip install instagrapi")


class InstagramSkill:
    """
    Full Instagram automation via instagrapi (unofficial Private API).
    Mirrors the XSkill architecture: config-driven init, session persistence,
    rate-limit delays, and graceful error handling.
    """

    def __init__(self, config):
        self.config = config
        self._client: Optional[Any] = None
        self._initialized = False
        self._action_delay = getattr(config, "instagram_action_delay", 2.0)
        self._session_path = opensable_home() / "ig_session.json"
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        # Serialize ALL IG API calls — never make concurrent requests
        self._api_lock = asyncio.Lock()

    async def initialize(self) -> bool:
        """Initialize Instagram client with credentials and session persistence."""
        if not INSTAGRAPI_AVAILABLE:
            logger.warning("instagrapi not available — Instagram skill disabled")
            return False

        username = (
            getattr(self.config, "instagram_username", None)
            or os.getenv("INSTAGRAM_USERNAME", "")
        )
        password = (
            getattr(self.config, "instagram_password", None)
            or os.getenv("INSTAGRAM_PASSWORD", "")
        )

        if not username or not password:
            logger.warning(
                "Instagram credentials not set. "
                "Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env"
            )
            return False

        try:
            loop = asyncio.get_event_loop()
            self._client = InstaClient()

            # ── Mobile device session ──
            # instagrapi uses Instagram's Private/Mobile API by default.
            # We explicitly set a realistic Android device to match X skill's
            # mobile-first approach and reduce detection risk.
            try:
                self._client.set_device({
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
                self._client.set_user_agent(
                    "Instagram 269.0.0.18.75 Android "
                    "(34/14; 560dpi; 1440x3120; Google; Pixel 8 Pro; "
                    "husky; qcom; en_US; 314665256)"
                )
                logger.debug("Instagram: Mobile device session configured (Pixel 8 Pro / Android 14)")
            except Exception as e:
                logger.debug(f"Instagram: Could not set mobile device: {e}")

            # ── Disable instagrapi's internal challenge retry loop ──
            # By default instagrapi retries challenge/ 8 times → spams the API
            # and gets the account flagged.  We raise immediately instead.
            def _no_challenge_handler(username: str, choice=None):
                raise ChallengeRequired(
                    "challenge_required — manual verification needed"
                )
            try:
                self._client.challenge_code_handler = _no_challenge_handler
            except Exception:
                pass

            # ── Login strategy ──
            # PRIORITY: Use saved cookies. NEVER do password login if cookies exist.
            # Password login from a "new device" triggers Instagram challenges.
            # Cookie-based session restore does NOT trigger challenges.
            logged_in = False

            # Attempt 1: Saved session with cookies — NO password login
            if self._session_path.exists():
                try:
                    await loop.run_in_executor(
                        None, self._client.load_settings, str(self._session_path)
                    )

                    # Read sessionid from saved data
                    session_id = ""
                    try:
                        with open(self._session_path) as f:
                            saved = json.load(f)
                        session_id = saved.get("authorization_data", {}).get("sessionid", "")
                        # Also check in cookies dict
                        if not session_id:
                            session_id = saved.get("cookies", {}).get("sessionid", "")
                    except Exception:
                        pass

                    if session_id:
                        logger.info("Instagram: Restoring session from cookies (no password login)...")
                        try:
                            await loop.run_in_executor(
                                None, self._client.login_by_sessionid, session_id
                            )
                            # Verify the session actually works with a lightweight call
                            try:
                                await loop.run_in_executor(
                                    None, self._client.account_info
                                )
                                logged_in = True
                                logger.info("✅ Instagram: Session restored and verified")
                            except Exception as verify_err:
                                logger.warning(
                                    f"Instagram: Session restored but verification failed ({verify_err}). "
                                    "Deleting stale session — will try password login..."
                                )
                                self._session_path.unlink(missing_ok=True)
                                logged_in = False
                        except Exception as e:
                            err = str(e).lower()
                            # Only trust session on clearly transient network errors
                            _transient = (
                                "timeout" in err
                                or "connectionerror" in err
                                or "connection reset" in err
                                or "429" in err
                                or "too many requests" in err
                                or "please wait" in err
                            )
                            if _transient:
                                logger.warning(
                                    f"Instagram: Transient error ({e}) — trusting session"
                                )
                                logged_in = True
                            else:
                                # JSON error, challenge, 400/412 etc — session is dead
                                logger.warning(
                                    f"Instagram: Session invalid ({e}). "
                                    "Deleting stale session — will try password login..."
                                )
                                self._session_path.unlink(missing_ok=True)
                                logged_in = False
                    else:
                        logger.info("Instagram: No sessionid in saved data, will do fresh login...")

                except Exception as e:
                    logger.info(f"Instagram: Could not load session file: {e}")
                    logged_in = False

            # Attempt 2: Fresh password login — ONLY if no saved session
            if not logged_in:
                try:
                    await loop.run_in_executor(
                        None, self._client.login, username, password
                    )
                    logged_in = True
                    logger.info("✅ Instagram: Fresh login successful")
                except (json.JSONDecodeError, ChallengeRequired) as e:
                    # Challenge flow — Instagram wants verification.
                    # Try relogin first, then browser fallback.
                    logger.warning(f"Instagram: Challenge/JSON error on login: {e}")
                    await asyncio.sleep(3)
                    try:
                        self._client = InstaClient()
                        await loop.run_in_executor(
                            None, self._client.login, username, password, True
                        )
                        logged_in = True
                        logger.info("✅ Instagram: Relogin successful after challenge")
                    except Exception as e2:
                        logger.warning(
                            f"Instagram: Relogin also failed: {e2}. "
                            "Attempting browser-based login..."
                        )
                        # Attempt 3: Browser-based login (extracts cookies)
                        browser_ok = await self._browser_login_fallback(username, password)
                        if browser_ok:
                            logged_in = True
                        else:
                            logger.error(
                                "Instagram: All login methods failed. "
                                "Run manually: python scripts/ig_browser_login.py"
                            )
                            return False

            if logged_in:
                # Save session for next time
                try:
                    await loop.run_in_executor(
                        None, self._client.dump_settings, str(self._session_path)
                    )
                except Exception as e:
                    logger.debug(f"Instagram: Could not save session: {e}")
                self._initialized = True
                return True

            return False

        except ChallengeRequired:
            logger.error(
                "Instagram: Challenge required — verify your account in the app/browser first"
            )
            return False
        except TwoFactorRequired:
            logger.error(
                "Instagram: 2FA required — set INSTAGRAM_2FA_CODE or disable 2FA"
            )
            return False
        except json.JSONDecodeError as e:
            logger.warning(
                f"Instagram: JSON error ({e}). Attempting browser login..."
            )
            browser_ok = await self._browser_login_fallback(username, password)
            if browser_ok:
                return True
            logger.error(
                "Instagram: All login methods failed. "
                "Run manually: python scripts/ig_browser_login.py"
            )
            return False
        except Exception as e:
            logger.error(f"Instagram initialization failed: {e}")
            return False

    async def _browser_login_fallback(self, username: str, password: str) -> bool:
        """Open a browser for manual Instagram login, extract cookies, and save session.

        This is the automatic fallback when Instagram requires a challenge
        (device verification, 2FA confirmation, etc). A Chromium window
        opens so the user can complete the challenge, then the cookies
        are extracted and saved as an instagrapi session.

        Returns True if the session was saved successfully.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(
                "Instagram: playwright not installed — cannot open browser login. "
                "Install with: pip install playwright && playwright install chromium"
            )
            return False

        loop = asyncio.get_event_loop()
        logger.info(
            "📸 Instagram: Opening browser for manual login — "
            "please log in and handle any verification..."
        )

        def _do_browser_login() -> bool:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
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
                page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")

                import time as _time
                _time.sleep(2)

                # Accept cookies dialog if present
                try:
                    accept_btn = page.locator(
                        "button:has-text('Allow'), "
                        "button:has-text('Accept'), "
                        "button:has-text('Permitir'), "
                        "button:has-text('Aceptar')"
                    )
                    if accept_btn.count() > 0:
                        accept_btn.first.click()
                        _time.sleep(1)
                except Exception:
                    pass

                # Pre-fill username if we can
                try:
                    user_input = page.locator('input[name="username"]')
                    if user_input.count() > 0:
                        user_input.fill(username)
                    pass_input = page.locator('input[name="password"]')
                    if pass_input.count() > 0:
                        pass_input.fill(password)
                except Exception:
                    pass

                # Wait for sessionid cookie — poll every 3 seconds for up to 5 min
                max_wait = 300  # 5 minutes
                elapsed = 0
                while elapsed < max_wait:
                    _time.sleep(3)
                    elapsed += 3
                    cookies = context.cookies("https://www.instagram.com")
                    cookie_dict = {c["name"]: c["value"] for c in cookies}
                    if "sessionid" in cookie_dict:
                        logger.info("✅ Instagram: Browser login successful — sessionid obtained!")
                        # Build and save session
                        import os as _os
                        session_data = {
                            "uuids": {
                                "phone_id": f"android-{_os.urandom(8).hex()}",
                                "uuid": f"{_os.urandom(4).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(6).hex()}",
                                "client_session_id": f"{_os.urandom(4).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(6).hex()}",
                                "advertising_id": f"{_os.urandom(4).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(6).hex()}",
                                "android_device_id": f"android-{_os.urandom(8).hex()}",
                                "request_id": f"{_os.urandom(4).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(6).hex()}",
                                "tray_session_id": f"{_os.urandom(4).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(2).hex()}-{_os.urandom(6).hex()}",
                            },
                            "cookies": cookie_dict,
                            "last_login": _time.time(),
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
                                "ds_user_id": cookie_dict.get("ds_user_id", ""),
                                "sessionid": cookie_dict.get("sessionid", ""),
                                "mid": cookie_dict.get("mid", ""),
                                "ig_did": cookie_dict.get("ig_did", ""),
                                "csrftoken": cookie_dict.get("csrftoken", ""),
                                "rur": cookie_dict.get("rur", ""),
                            },
                        }
                        self._session_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(self._session_path, "w") as f:
                            json.dump(session_data, f, indent=2)
                        browser.close()
                        return True

                # Timeout
                logger.warning("Instagram: Browser login timed out (5 min) — no sessionid obtained")
                browser.close()
                return False

        try:
            ok = await loop.run_in_executor(None, _do_browser_login)
            if ok:
                # Reload session into client
                self._client = InstaClient()
                try:
                    with open(self._session_path) as f:
                        saved = json.load(f)
                    session_id = saved.get("authorization_data", {}).get("sessionid", "")
                    if session_id:
                        await loop.run_in_executor(
                            None, self._client.login_by_sessionid, session_id
                        )
                        self._initialized = True
                        logger.info("✅ Instagram: Initialized with browser session")
                        return True
                except Exception as e:
                    logger.error(f"Instagram: Session reload failed: {e}")
                    return False
            return False
        except Exception as e:
            logger.error(f"Instagram: Browser login error: {e}")
            return False

    def _ensure_initialized(self):
        if not self._initialized or not self._client:
            raise RuntimeError(
                "Instagram not initialized. Check credentials in .env "
                "(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)"
            )

    def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous instagrapi call in an executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ──────────────────────────────────────────────────────────────────────
    # Posting
    # ──────────────────────────────────────────────────────────────────────

    async def upload_photo(
        self,
        path: str,
        caption: str = "",
        location: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Upload a photo to Instagram feed.

        Args:
            path: Local file path to the image
            caption: Post caption text
            location: Optional location dict with 'name', 'lat', 'lng'
        """
        self._ensure_initialized()
        async with self._api_lock:  # ONE IG API call at a time
            try:
                kwargs = {"path": Path(path), "caption": caption}
                media = await self._run_sync(self._client.photo_upload, **kwargs)

                media_id = getattr(media, "pk", None) or str(media)
                code = getattr(media, "code", "")
                logger.info(f"✅ Instagram: Photo uploaded — {code}")
                await asyncio.sleep(self._action_delay)

                return {
                    "success": True,
                    "media_id": str(media_id),
                    "code": code,
                    "url": f"https://www.instagram.com/p/{code}/" if code else None,
                    "caption": caption[:100],
                }
            except ChallengeRequired:
                logger.warning("Instagram upload_photo: challenge_required — session needs manual verification")
                return {"success": False, "error": "challenge_required"}
            except Exception as e:
                logger.error(f"Instagram upload_photo error: {e}")
                return {"success": False, "error": str(e)}

    async def upload_video(
        self,
        path: str,
        caption: str = "",
        thumbnail: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a video to Instagram feed.

        Args:
            path: Local file path to the video
            caption: Post caption text
            thumbnail: Optional thumbnail image path
        """
        self._ensure_initialized()
        async with self._api_lock:
            try:
                kwargs = {"path": Path(path), "caption": caption}
                if thumbnail:
                    kwargs["thumbnail"] = Path(thumbnail)

                media = await self._run_sync(self._client.video_upload, **kwargs)
                media_id = getattr(media, "pk", None) or str(media)
                code = getattr(media, "code", "")
                logger.info(f"✅ Instagram: Video uploaded — {code}")
                await asyncio.sleep(self._action_delay)

                return {
                    "success": True,
                    "media_id": str(media_id),
                    "code": code,
                    "url": f"https://www.instagram.com/p/{code}/" if code else None,
                }
            except ChallengeRequired:
                logger.warning("Instagram upload_video: challenge_required")
                return {"success": False, "error": "challenge_required"}
            except Exception as e:
                logger.error(f"Instagram upload_video error: {e}")
                return {"success": False, "error": str(e)}

    async def upload_reel(
        self,
        path: str,
        caption: str = "",
        thumbnail: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a Reel (short video) to Instagram.

        Args:
            path: Local file path to the video
            caption: Reel caption text
            thumbnail: Optional thumbnail image path
        """
        self._ensure_initialized()
        async with self._api_lock:
            try:
                kwargs = {"path": Path(path), "caption": caption}
                if thumbnail:
                    kwargs["thumbnail"] = Path(thumbnail)

                media = await self._run_sync(self._client.clip_upload, **kwargs)
                media_id = getattr(media, "pk", None) or str(media)
                code = getattr(media, "code", "")
                logger.info(f"✅ Instagram: Reel uploaded — {code}")
                await asyncio.sleep(self._action_delay)

                return {
                    "success": True,
                    "media_id": str(media_id),
                    "code": code,
                    "url": f"https://www.instagram.com/reel/{code}/" if code else None,
                }
            except ChallengeRequired:
                logger.warning("Instagram upload_reel: challenge_required")
                return {"success": False, "error": "challenge_required"}
            except Exception as e:
                logger.error(f"Instagram upload_reel error: {e}")
                return {"success": False, "error": str(e)}

    async def upload_story(
        self,
        path: str,
        caption: str = "",
        mentions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Upload a story (photo or video).

        Args:
            path: Local file path to the image or video
            caption: Story caption (optional)
            mentions: List of usernames to mention (optional)
        """
        self._ensure_initialized()
        async with self._api_lock:
            try:
                file_path = Path(path)
                suffix = file_path.suffix.lower()

                if suffix in (".mp4", ".mov", ".avi", ".mkv"):
                    media = await self._run_sync(
                        self._client.video_upload_to_story, file_path, caption
                    )
                else:
                    media = await self._run_sync(
                        self._client.photo_upload_to_story, file_path, caption
                    )

                media_id = getattr(media, "pk", None) or str(media)
                logger.info(f"✅ Instagram: Story uploaded — {media_id}")
                await asyncio.sleep(self._action_delay)

                return {
                    "success": True,
                    "media_id": str(media_id),
                    "type": "video" if suffix in (".mp4", ".mov") else "photo",
                }
            except ChallengeRequired:
                logger.warning("Instagram upload_story: challenge_required")
                return {"success": False, "error": "challenge_required"}
            except Exception as e:
                logger.error(f"Instagram upload_story error: {e}")
                return {"success": False, "error": str(e)}

    async def upload_album(
        self,
        paths: List[str],
        caption: str = "",
    ) -> Dict[str, Any]:
        """
        Upload a carousel/album (multiple photos/videos).

        Args:
            paths: List of file paths (photos and/or videos)
            caption: Album caption text
        """
        self._ensure_initialized()
        async with self._api_lock:
            try:
                file_paths = [Path(p) for p in paths]
                media = await self._run_sync(
                    self._client.album_upload, file_paths, caption
                )

                media_id = getattr(media, "pk", None) or str(media)
                code = getattr(media, "code", "")
                logger.info(f"✅ Instagram: Album uploaded ({len(paths)} items) — {code}")
                await asyncio.sleep(self._action_delay)

                return {
                    "success": True,
                    "media_id": str(media_id),
                    "code": code,
                    "url": f"https://www.instagram.com/p/{code}/" if code else None,
                    "item_count": len(paths),
                }
            except ChallengeRequired:
                logger.warning("Instagram upload_album: challenge_required")
                return {"success": False, "error": "challenge_required"}
            except Exception as e:
                logger.error(f"Instagram upload_album error: {e}")
                return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Search & Discovery
    # ──────────────────────────────────────────────────────────────────────

    async def search_users(
        self, query: str, count: int = 10
    ) -> Dict[str, Any]:
        """Search for users by username or name."""
        self._ensure_initialized()
        try:
            users = await self._run_sync(self._client.search_users, query)
            results = []
            for u in users[:count]:
                results.append({
                    "pk": str(getattr(u, "pk", "")),
                    "username": getattr(u, "username", ""),
                    "full_name": getattr(u, "full_name", ""),
                    "is_private": getattr(u, "is_private", False),
                    "is_verified": getattr(u, "is_verified", False),
                    "profile_pic_url": str(getattr(u, "profile_pic_url", "")),
                })

            await asyncio.sleep(self._action_delay)
            return {"success": True, "query": query, "count": len(results), "users": results}
        except Exception as e:
            logger.error(f"Instagram search_users error: {e}")
            return {"success": False, "error": str(e)}

    async def search_hashtags(
        self, query: str, count: int = 10
    ) -> Dict[str, Any]:
        """Search for hashtags."""
        self._ensure_initialized()
        try:
            hashtags = await self._run_sync(self._client.search_hashtags, query)
            results = []
            for h in hashtags[:count]:
                results.append({
                    "id": str(getattr(h, "id", "")),
                    "name": getattr(h, "name", ""),
                    "media_count": getattr(h, "media_count", 0),
                })

            await asyncio.sleep(self._action_delay)
            return {"success": True, "query": query, "count": len(results), "hashtags": results}
        except Exception as e:
            logger.error(f"Instagram search_hashtags error: {e}")
            return {"success": False, "error": str(e)}

    async def get_hashtag_medias(
        self, hashtag: str, count: int = 20
    ) -> Dict[str, Any]:
        """Get recent posts for a hashtag."""
        self._ensure_initialized()
        try:
            medias = await self._run_sync(
                self._client.hashtag_medias_recent, hashtag, count
            )
            results = []
            for m in medias[:count]:
                results.append({
                    "pk": str(getattr(m, "pk", "")),
                    "code": getattr(m, "code", ""),
                    "caption": str(getattr(m, "caption_text", ""))[:200],
                    "like_count": getattr(m, "like_count", 0),
                    "comment_count": getattr(m, "comment_count", 0),
                    "media_type": str(getattr(m, "media_type", "")),
                    "user": getattr(getattr(m, "user", None), "username", ""),
                })

            return {"success": True, "hashtag": hashtag, "count": len(results), "medias": results}
        except Exception as e:
            logger.error(f"Instagram get_hashtag_medias error: {e}")
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Users
    # ──────────────────────────────────────────────────────────────────────

    async def get_user_info(self, username: str) -> Dict[str, Any]:
        """Get a user's profile information."""
        self._ensure_initialized()
        try:
            user_id = await self._run_sync(
                self._client.user_id_from_username, username
            )
            user = await self._run_sync(self._client.user_info, user_id)
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "pk": str(getattr(user, "pk", "")),
                "username": getattr(user, "username", username),
                "full_name": getattr(user, "full_name", ""),
                "bio": getattr(user, "biography", ""),
                "followers": getattr(user, "follower_count", 0),
                "following": getattr(user, "following_count", 0),
                "media_count": getattr(user, "media_count", 0),
                "is_private": getattr(user, "is_private", False),
                "is_verified": getattr(user, "is_verified", False),
                "external_url": str(getattr(user, "external_url", "") or ""),
                "profile_pic_url": str(getattr(user, "profile_pic_url_hd", "")),
            }
        except Exception as e:
            logger.error(f"Instagram get_user_info error: {e}")
            return {"success": False, "error": str(e)}

    async def get_user_medias(
        self, username: str, count: int = 20
    ) -> Dict[str, Any]:
        """Get a user's recent posts."""
        self._ensure_initialized()
        try:
            user_id = await self._run_sync(
                self._client.user_id_from_username, username
            )
            medias = await self._run_sync(
                self._client.user_medias, user_id, count
            )

            results = []
            for m in medias[:count]:
                results.append({
                    "pk": str(getattr(m, "pk", "")),
                    "code": getattr(m, "code", ""),
                    "caption": str(getattr(m, "caption_text", ""))[:200],
                    "like_count": getattr(m, "like_count", 0),
                    "comment_count": getattr(m, "comment_count", 0),
                    "media_type": str(getattr(m, "media_type", "")),
                    "taken_at": str(getattr(m, "taken_at", "")),
                    "url": f"https://www.instagram.com/p/{getattr(m, 'code', '')}/",
                })

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "username": username,
                "count": len(results),
                "medias": results,
            }
        except Exception as e:
            logger.error(f"Instagram get_user_medias error: {e}")
            return {"success": False, "error": str(e)}

    async def get_timeline(self, count: int = 20) -> Dict[str, Any]:
        """Get the home timeline feed."""
        self._ensure_initialized()
        try:
            feed = await self._run_sync(self._client.get_timeline_feed)
            items = feed.get("feed_items", []) if isinstance(feed, dict) else []
            results = []
            for item in items[:count]:
                media = item.get("media_or_ad", {}) if isinstance(item, dict) else {}
                if not media:
                    continue
                user = media.get("user", {})
                caption = media.get("caption", {}) or {}
                results.append({
                    "pk": str(media.get("pk", "")),
                    "code": media.get("code", ""),
                    "username": user.get("username", ""),
                    "caption": (caption.get("text", "") or "")[:200],
                    "like_count": media.get("like_count", 0),
                    "comment_count": media.get("comment_count", 0),
                })

            await asyncio.sleep(self._action_delay)
            return {"success": True, "count": len(results), "items": results}
        except Exception as e:
            logger.error(f"Instagram get_timeline error: {e}")
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Engagement
    # ──────────────────────────────────────────────────────────────────────

    async def like_media(self, media_id: str) -> Dict[str, Any]:
        """Like a post by media ID or URL shortcode."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(self._client.media_like, media_id)
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "liked", "media_id": media_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unlike_media(self, media_id: str) -> Dict[str, Any]:
        """Unlike a post."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(self._client.media_unlike, media_id)
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "unliked", "media_id": media_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def comment(self, media_id: str, text: str) -> Dict[str, Any]:
        """Comment on a post."""
        self._ensure_initialized()
        try:
            comment = await self._run_sync(
                self._client.media_comment, media_id, text
            )
            comment_id = getattr(comment, "pk", None) or str(comment)
            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "action": "commented",
                "media_id": media_id,
                "comment_id": str(comment_id),
                "text": text[:100],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def follow_user(self, username: str) -> Dict[str, Any]:
        """Follow a user by username."""
        self._ensure_initialized()
        try:
            user_id = await self._run_sync(
                self._client.user_id_from_username, username
            )
            result = await self._run_sync(self._client.user_follow, user_id)
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "followed", "username": username}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unfollow_user(self, username: str) -> Dict[str, Any]:
        """Unfollow a user by username."""
        self._ensure_initialized()
        try:
            user_id = await self._run_sync(
                self._client.user_id_from_username, username
            )
            result = await self._run_sync(self._client.user_unfollow, user_id)
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "unfollowed", "username": username}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Direct Messages
    # ──────────────────────────────────────────────────────────────────────

    async def send_dm(self, username: str, text: str) -> Dict[str, Any]:
        """Send a direct message to a user."""
        self._ensure_initialized()
        try:
            user_id = await self._run_sync(
                self._client.user_id_from_username, username
            )
            result = await self._run_sync(
                self._client.direct_send, text, [int(user_id)]
            )
            await asyncio.sleep(self._action_delay)
            return {"success": True, "action": "dm_sent", "username": username}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_direct_threads(self, count: int = 20) -> Dict[str, Any]:
        """Get direct message threads (inbox)."""
        self._ensure_initialized()
        try:
            threads = await self._run_sync(self._client.direct_threads, count)
            results = []
            for t in threads[:count]:
                users = getattr(t, "users", [])
                user_names = [getattr(u, "username", "") for u in users]
                last_msg = getattr(t, "messages", [])
                last_text = ""
                if last_msg:
                    last_text = getattr(last_msg[0], "text", "") or ""
                results.append({
                    "thread_id": str(getattr(t, "id", "")),
                    "users": user_names,
                    "last_message": last_text[:100],
                    "is_group": getattr(t, "is_group", False),
                })

            return {"success": True, "count": len(results), "threads": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Media Download
    # ──────────────────────────────────────────────────────────────────────

    async def download_media(
        self, media_pk: str, folder: str = "/tmp"
    ) -> Dict[str, Any]:
        """Download a media item (photo or video) by its PK."""
        self._ensure_initialized()
        try:
            media_info = await self._run_sync(self._client.media_info, media_pk)
            media_type = getattr(media_info, "media_type", 1)

            if media_type == 2:  # Video
                path = await self._run_sync(
                    self._client.video_download, media_pk, folder
                )
            else:  # Photo
                path = await self._run_sync(
                    self._client.photo_download, media_pk, folder
                )

            return {
                "success": True,
                "path": str(path),
                "media_type": "video" if media_type == 2 else "photo",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Media Info
    # ──────────────────────────────────────────────────────────────────────

    async def get_media_info(self, media_pk: str) -> Dict[str, Any]:
        """Get detailed info about a media post."""
        self._ensure_initialized()
        try:
            m = await self._run_sync(self._client.media_info, media_pk)
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "pk": str(getattr(m, "pk", "")),
                "code": getattr(m, "code", ""),
                "media_type": str(getattr(m, "media_type", "")),
                "caption": str(getattr(m, "caption_text", ""))[:500],
                "like_count": getattr(m, "like_count", 0),
                "comment_count": getattr(m, "comment_count", 0),
                "taken_at": str(getattr(m, "taken_at", "")),
                "user": getattr(getattr(m, "user", None), "username", ""),
                "url": f"https://www.instagram.com/p/{getattr(m, 'code', '')}/",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_media_comments(
        self, media_pk: str, count: int = 20
    ) -> Dict[str, Any]:
        """Get comments on a media post."""
        self._ensure_initialized()
        try:
            comments = await self._run_sync(
                self._client.media_comments, media_pk, count
            )
            results = []
            for c in comments[:count]:
                results.append({
                    "pk": str(getattr(c, "pk", "")),
                    "text": getattr(c, "text", ""),
                    "username": getattr(getattr(c, "user", None), "username", ""),
                    "created_at": str(getattr(c, "created_at_utc", "")),
                    "like_count": getattr(c, "like_count", 0),
                })

            return {"success": True, "count": len(results), "comments": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Stories
    # ──────────────────────────────────────────────────────────────────────

    async def get_user_stories(self, username: str) -> Dict[str, Any]:
        """Get a user's active stories."""
        self._ensure_initialized()
        try:
            user_id = await self._run_sync(
                self._client.user_id_from_username, username
            )
            stories = await self._run_sync(self._client.user_stories, user_id)

            results = []
            for s in stories:
                results.append({
                    "pk": str(getattr(s, "pk", "")),
                    "media_type": str(getattr(s, "media_type", "")),
                    "taken_at": str(getattr(s, "taken_at", "")),
                })

            return {
                "success": True,
                "username": username,
                "count": len(results),
                "stories": results,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────────────────────────────

    async def delete_media(self, media_pk: str) -> Dict[str, Any]:
        """Delete one of your own posts."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(self._client.media_delete, media_pk)
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "deleted", "media_pk": media_pk}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_media_pk_from_url(self, url: str) -> Dict[str, Any]:
        """Extract media PK from an Instagram URL."""
        self._ensure_initialized()
        try:
            pk = await self._run_sync(self._client.media_pk_from_url, url)
            return {"success": True, "media_pk": str(pk)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def is_available(self) -> bool:
        """Check if Instagram skill is initialized and ready."""
        return self._initialized and self._client is not None
