"""
YouTube Skill,  Search, browse, upload and interact on YouTube via python-youtube.

Uses the python-youtube (pyyoutube) library wrapping the official YouTube Data API V3.
Supports both read-only (API key) and write (OAuth access token) operations.
All requests use mobile device session headers for consistency.

Features (Read,  API key only):
- Search videos, channels, playlists
- Get channel details and videos
- Get video details, captions, comments
- Get playlist items
- Get trending videos

Features (Write,  OAuth token required):
- Upload videos
- Post comments and replies
- Like/dislike videos
- Subscribe to channels
- Create/manage playlists

Setup:
    Set these in .env:
        YOUTUBE_API_KEY=your_api_key            (required for read)
        YOUTUBE_ACCESS_TOKEN=your_access_token  (optional, for write actions)

    Get an API key:
        1. Go to https://console.cloud.google.com/
        2. Enable YouTube Data API v3
        3. Create credentials → API key

    Get an access token (for write operations):
        1. Create OAuth 2.0 Client ID in Google Cloud Console
        2. Use the OAuth flow or set YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET
           and call the generate_auth_url() method

    Install:
        pip install python-youtube
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from pyyoutube import Client as YouTubeClient

    PYYOUTUBE_AVAILABLE = True
except ImportError:
    PYYOUTUBE_AVAILABLE = False
    logger.info("python-youtube not installed. Install with: pip install python-youtube")

# Mobile user-agent for YouTube API requests
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.6778.200 Mobile Safari/537.36"
)


class YouTubeSkill:
    """
    YouTube Data API v3 automation via python-youtube (pyyoutube).
    Uses official Google API,  API key for read, OAuth token for write.
    All calls are synchronous (httpx), wrapped in run_in_executor for async.
    Mobile device headers applied for session consistency.
    """

    def __init__(self, config):
        self.config = config
        self._client: Optional[Any] = None
        self._write_client: Optional[Any] = None  # Separate client with OAuth
        self._initialized = False
        self._action_delay = getattr(config, "youtube_action_delay", 1.0)

    async def initialize(self) -> bool:
        """Initialize YouTube API client with API key and optional OAuth token."""
        if not PYYOUTUBE_AVAILABLE:
            logger.warning("python-youtube not available,  YouTube skill disabled")
            return False

        api_key = (
            getattr(self.config, "youtube_api_key", None)
            or os.getenv("YOUTUBE_API_KEY", "")
        )
        access_token = (
            getattr(self.config, "youtube_access_token", None)
            or os.getenv("YOUTUBE_ACCESS_TOKEN", "")
        )

        if not api_key and not access_token:
            logger.warning(
                "YouTube credentials not set. "
                "Set YOUTUBE_API_KEY (read) and/or YOUTUBE_ACCESS_TOKEN (write) in .env"
            )
            return False

        try:
            # Read client (API key),  for search, get info, etc.
            if api_key:
                self._client = YouTubeClient(api_key=api_key)
                self._apply_mobile_session(self._client)

            # Write client (OAuth token),  for upload, comment, like, subscribe
            if access_token:
                self._write_client = YouTubeClient(access_token=access_token)
                self._apply_mobile_session(self._write_client)
                # If no API key client, use the OAuth client for reads too
                if not self._client:
                    self._client = self._write_client

            # Verify the client works with a test call
            loop = asyncio.get_event_loop()
            test = await loop.run_in_executor(
                None,
                lambda: self._client.videos.list(
                    video_id="dQw4w9WgXcQ",
                    return_json=True,
                ),
            )
            if test and "items" in test:
                self._initialized = True
                mode = "read+write" if self._write_client else "read-only"
                logger.info(f"✅ YouTube: Initialized ({mode})")
                return True
            else:
                logger.warning("YouTube: API key/token invalid or quota exceeded")
                return False

        except Exception as e:
            logger.error(f"YouTube initialization failed: {e}")
            return False

    def _apply_mobile_session(self, client):
        """Set mobile User-Agent on the pyyoutube Client's HTTP session."""
        try:
            # pyyoutube Client uses an internal _requester with httpx
            if hasattr(client, "_requester") and hasattr(client._requester, "_client"):
                client._requester._client.headers["User-Agent"] = _MOBILE_UA
                logger.debug("YouTube: Mobile UA applied via _requester._client")
            elif hasattr(client, "_session"):
                client._session.headers["User-Agent"] = _MOBILE_UA
                logger.debug("YouTube: Mobile UA applied via _session")
        except Exception as e:
            logger.debug(f"YouTube: Could not set mobile UA: {e}")

    def _ensure_initialized(self):
        if not self._initialized or not self._client:
            raise RuntimeError(
                "YouTube not initialized. Set YOUTUBE_API_KEY in .env"
            )

    def _ensure_write(self):
        if not self._write_client:
            raise RuntimeError(
                "YouTube write access requires OAuth. "
                "Set YOUTUBE_ACCESS_TOKEN in .env"
            )

    def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous pyyoutube call in an executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ──────────────────────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────────────────────

    async def search_videos(self, query: str, count: int = 10) -> Dict[str, Any]:
        """
        Search YouTube videos by keyword.

        Args:
            query: Search query string
            count: Max results (default: 10, max: 50)
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.search.list,
                q=query,
                type="video",
                max_results=min(count, 50),
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            videos = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                videos.append({
                    "video_id": item.get("id", {}).get("videoId", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "url": f"https://youtube.com/watch?v={item.get('id', {}).get('videoId', '')}",
                })

            return {"success": True, "videos": videos, "total": result.get("pageInfo", {}).get("totalResults", 0)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_channels(self, query: str, count: int = 10) -> Dict[str, Any]:
        """
        Search YouTube channels by keyword.

        Args:
            query: Search query string
            count: Max results
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.search.list,
                q=query,
                type="channel",
                max_results=min(count, 50),
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            channels = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                channels.append({
                    "channel_id": item.get("id", {}).get("channelId", ""),
                    "title": snippet.get("channelTitle", "") or snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                })

            return {"success": True, "channels": channels}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Channel info
    # ──────────────────────────────────────────────────────────────────────

    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Get detailed info about a YouTube channel.

        Args:
            channel_id: YouTube channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.channels.list,
                channel_id=channel_id,
                parts="snippet,statistics,contentDetails,brandingSettings",
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            items = result.get("items", [])
            if not items:
                return {"success": False, "error": f"Channel '{channel_id}' not found"}

            ch = items[0]
            snippet = ch.get("snippet", {})
            stats = ch.get("statistics", {})

            return {
                "success": True,
                "channel": {
                    "id": ch.get("id", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "custom_url": snippet.get("customUrl", ""),
                    "country": snippet.get("country", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "subscriber_count": stats.get("subscriberCount", "0"),
                    "video_count": stats.get("videoCount", "0"),
                    "view_count": stats.get("viewCount", "0"),
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_channel_videos(
        self, channel_id: str, count: int = 10
    ) -> Dict[str, Any]:
        """
        Get recent videos from a YouTube channel.

        Args:
            channel_id: YouTube channel ID
            count: Max videos to return
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.search.list,
                channel_id=channel_id,
                type="video",
                order="date",
                max_results=min(count, 50),
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            videos = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                vid_id = item.get("id", {}).get("videoId", "")
                videos.append({
                    "video_id": vid_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "url": f"https://youtube.com/watch?v={vid_id}",
                })

            return {"success": True, "videos": videos}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Video info
    # ──────────────────────────────────────────────────────────────────────

    async def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get detailed info about a YouTube video.

        Args:
            video_id: YouTube video ID (e.g. dQw4w9WgXcQ)
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.videos.list,
                video_id=video_id,
                parts="snippet,statistics,contentDetails",
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            items = result.get("items", [])
            if not items:
                return {"success": False, "error": f"Video '{video_id}' not found"}

            vid = items[0]
            snippet = vid.get("snippet", {})
            stats = vid.get("statistics", {})
            content = vid.get("contentDetails", {})

            return {
                "success": True,
                "video": {
                    "id": vid.get("id", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "tags": snippet.get("tags", []),
                    "category_id": snippet.get("categoryId", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("maxres", snippet.get("thumbnails", {}).get("high", {})).get("url", ""),
                    "duration": content.get("duration", ""),
                    "view_count": stats.get("viewCount", "0"),
                    "like_count": stats.get("likeCount", "0"),
                    "comment_count": stats.get("commentCount", "0"),
                    "url": f"https://youtube.com/watch?v={vid.get('id', '')}",
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Comments
    # ──────────────────────────────────────────────────────────────────────

    async def get_video_comments(
        self, video_id: str, count: int = 20
    ) -> Dict[str, Any]:
        """
        Get top comments on a YouTube video.

        Args:
            video_id: YouTube video ID
            count: Max comments to return
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.commentThreads.list,
                video_id=video_id,
                max_results=min(count, 100),
                order="relevance",
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            comments = []
            for item in result.get("items", []):
                top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                comments.append({
                    "comment_id": item.get("id", ""),
                    "author": top.get("authorDisplayName", ""),
                    "text": top.get("textDisplay", ""),
                    "like_count": top.get("likeCount", 0),
                    "published_at": top.get("publishedAt", ""),
                    "reply_count": item.get("snippet", {}).get("totalReplyCount", 0),
                })

            return {"success": True, "comments": comments}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def comment_on_video(
        self, video_id: str, text: str
    ) -> Dict[str, Any]:
        """
        Post a comment on a YouTube video (requires OAuth).

        Args:
            video_id: YouTube video ID
            text: Comment text
        """
        self._ensure_initialized()
        self._ensure_write()
        try:
            body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": text,
                        }
                    },
                }
            }
            result = await self._run_sync(
                self._write_client.commentThreads.insert,
                body=body,
                parts="snippet",
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            comment_id = result.get("id", "")
            return {"success": True, "comment_id": comment_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Playlists
    # ──────────────────────────────────────────────────────────────────────

    async def get_playlist_items(
        self, playlist_id: str, count: int = 20
    ) -> Dict[str, Any]:
        """
        Get videos in a YouTube playlist.

        Args:
            playlist_id: YouTube playlist ID
            count: Max items to return
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.playlistItems.list,
                playlist_id=playlist_id,
                max_results=min(count, 50),
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            items = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                vid_id = snippet.get("resourceId", {}).get("videoId", "")
                items.append({
                    "video_id": vid_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "position": snippet.get("position", 0),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "url": f"https://youtube.com/watch?v={vid_id}",
                })

            return {"success": True, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Engagement (OAuth required)
    # ──────────────────────────────────────────────────────────────────────

    async def rate_video(
        self, video_id: str, rating: str = "like"
    ) -> Dict[str, Any]:
        """
        Like or dislike a YouTube video (requires OAuth).

        Args:
            video_id: YouTube video ID
            rating: 'like', 'dislike', or 'none' (remove rating)
        """
        self._ensure_initialized()
        self._ensure_write()
        try:
            await self._run_sync(
                self._write_client.videos.rate,
                video_id=video_id,
                rating=rating,
            )
            await asyncio.sleep(self._action_delay)
            return {"success": True, "rating": rating}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def subscribe(self, channel_id: str) -> Dict[str, Any]:
        """
        Subscribe to a YouTube channel (requires OAuth).

        Args:
            channel_id: YouTube channel ID to subscribe to
        """
        self._ensure_initialized()
        self._ensure_write()
        try:
            body = {
                "snippet": {
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": channel_id,
                    }
                }
            }
            result = await self._run_sync(
                self._write_client.subscriptions.insert,
                body=body,
                parts="snippet",
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            sub_id = result.get("id", "")
            return {"success": True, "subscription_id": sub_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_my_subscriptions(self, count: int = 20) -> Dict[str, Any]:
        """
        Get your YouTube subscriptions (requires OAuth).

        Args:
            count: Max subscriptions to return
        """
        self._ensure_initialized()
        self._ensure_write()
        try:
            result = await self._run_sync(
                self._write_client.subscriptions.list,
                mine=True,
                max_results=min(count, 50),
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            subs = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                res = snippet.get("resourceId", {})
                subs.append({
                    "subscription_id": item.get("id", ""),
                    "channel_id": res.get("channelId", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                })

            return {"success": True, "subscriptions": subs}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Upload (OAuth required)
    # ──────────────────────────────────────────────────────────────────────

    async def upload_video(
        self,
        file_path: str,
        title: str = "Uploaded via Open-Sable",
        description: str = "",
        tags: Optional[List[str]] = None,
        privacy: str = "private",
        category_id: str = "22",
    ) -> Dict[str, Any]:
        """
        Upload a video to YouTube (requires OAuth).

        Args:
            file_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            privacy: 'private', 'public', or 'unlisted'
            category_id: YouTube category ID (22 = People & Blogs)
        """
        self._ensure_initialized()
        self._ensure_write()
        try:
            from pathlib import Path

            video_path = Path(file_path)
            if not video_path.exists():
                return {"success": False, "error": f"Video file not found: {file_path}"}

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags or [],
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }

            result = await self._run_sync(
                self._write_client.videos.insert,
                body=body,
                media=str(video_path),
                parts="snippet,status",
                notify_subscribers=True,
            )
            await asyncio.sleep(self._action_delay)

            # MediaUpload returns the video resource after completion
            video_id = ""
            if hasattr(result, "body") and isinstance(result.body, dict):
                video_id = result.body.get("id", "")
            elif isinstance(result, dict):
                video_id = result.get("id", "")

            return {
                "success": True,
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}" if video_id else "",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Trending
    # ──────────────────────────────────────────────────────────────────────

    async def get_trending(
        self, region_code: str = "US", count: int = 10
    ) -> Dict[str, Any]:
        """
        Get trending YouTube videos by region.

        Args:
            region_code: ISO 3166-1 alpha-2 country code (default: US)
            count: Max videos
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.videos.list,
                chart="mostPopular",
                region_code=region_code,
                max_results=min(count, 50),
                parts="snippet,statistics",
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            videos = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                videos.append({
                    "video_id": item.get("id", ""),
                    "title": snippet.get("title", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "view_count": stats.get("viewCount", "0"),
                    "like_count": stats.get("likeCount", "0"),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "url": f"https://youtube.com/watch?v={item.get('id', '')}",
                })

            return {"success": True, "videos": videos}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Captions
    # ──────────────────────────────────────────────────────────────────────

    async def get_captions(self, video_id: str) -> Dict[str, Any]:
        """
        List available captions/subtitles for a YouTube video.

        Args:
            video_id: YouTube video ID
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.captions.list,
                video_id=video_id,
                return_json=True,
            )
            await asyncio.sleep(self._action_delay)

            captions = []
            for item in result.get("items", []):
                snippet = item.get("snippet", {})
                captions.append({
                    "caption_id": item.get("id", ""),
                    "language": snippet.get("language", ""),
                    "name": snippet.get("name", ""),
                    "track_kind": snippet.get("trackKind", ""),
                    "is_auto_synced": snippet.get("isAutoSynced", False),
                })

            return {"success": True, "captions": captions}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if YouTube skill is available and initialized."""
        return self._initialized and self._client is not None

    def has_write_access(self) -> bool:
        """Check if YouTube skill has OAuth write access."""
        return self._write_client is not None
