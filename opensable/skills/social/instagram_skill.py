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

            # Try loading saved session first
            if self._session_path.exists():
                try:
                    await loop.run_in_executor(
                        None, self._client.load_settings, str(self._session_path)
                    )
                    await loop.run_in_executor(
                        None, self._client.login, username, password
                    )
                    # Verify session is valid
                    await loop.run_in_executor(None, self._client.get_timeline_feed)
                    self._initialized = True
                    logger.info("✅ Instagram: Logged in via saved session")
                    return True
                except (LoginRequired, Exception) as e:
                    logger.info(f"Instagram session expired, re-logging: {e}")
                    self._client = InstaClient()

            # Fresh login
            await loop.run_in_executor(
                None, self._client.login, username, password
            )
            # Save session for next time
            await loop.run_in_executor(
                None, self._client.dump_settings, str(self._session_path)
            )
            self._initialized = True
            logger.info("✅ Instagram: Fresh login successful")
            return True

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
        except Exception as e:
            logger.error(f"Instagram initialization failed: {e}")
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
