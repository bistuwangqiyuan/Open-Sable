"""
Facebook Skill,  Interact with Facebook via the facebook-sdk (Graph API).

Uses the official Facebook Graph API through the facebook-sdk library.
Requires a Facebook App access token (User Token or Page Token).

Features:
- Post to your profile or pages
- Read feed, posts, comments
- Like/react to posts
- Get user/page info
- Upload photos/videos
- Manage page posts
- Read and reply to comments

Setup:
    Set these in .env:
        FACEBOOK_ACCESS_TOKEN=your_access_token
        FACEBOOK_PAGE_ID=your_page_id  (optional, for page management)

    Get an access token:
        1. Go to https://developers.facebook.com/tools/explorer/
        2. Select your app and generate a User Token
        3. For long-lived tokens, exchange via the API

    Install:
        pip install facebook-sdk requests
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import facebook

    FACEBOOK_SDK_AVAILABLE = True
except ImportError:
    FACEBOOK_SDK_AVAILABLE = False
    logger.info("facebook-sdk not installed. Install with: pip install facebook-sdk")


class FacebookSkill:
    """
    Facebook Graph API automation via facebook-sdk.
    Works with User Access Tokens or Page Access Tokens.
    All Graph API calls are synchronous, wrapped with run_in_executor for async.
    """

    def __init__(self, config):
        self.config = config
        self._graph: Optional[Any] = None
        self._initialized = False
        self._action_delay = getattr(config, "facebook_action_delay", 1.5)
        self._page_id = None
        self._page_graph = None  # Separate graph for page-level actions

    async def initialize(self) -> bool:
        """Initialize Facebook Graph API client."""
        if not FACEBOOK_SDK_AVAILABLE:
            logger.warning("facebook-sdk not available,  Facebook skill disabled")
            return False

        access_token = (
            getattr(self.config, "facebook_access_token", None)
            or os.getenv("FACEBOOK_ACCESS_TOKEN", "")
        )

        if not access_token:
            logger.warning(
                "Facebook access token not set. "
                "Set FACEBOOK_ACCESS_TOKEN in .env"
            )
            return False

        try:
            self._graph = facebook.GraphAPI(
                access_token=access_token, version="3.1"
            )

            # ── Mobile device session ──
            # Patch the underlying requests session with a mobile User-Agent
            # to match X skill's mobile-first approach.
            try:
                import requests as _requests
                _mobile_ua = (
                    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.6778.200 Mobile Safari/537.36"
                )
                if hasattr(self._graph, 'session'):
                    self._graph.session.headers.update({"User-Agent": _mobile_ua})
                elif hasattr(self._graph, 'request'):
                    # facebook-sdk v3 uses urllib, inject via opener
                    pass
                logger.debug("Facebook: Mobile device session headers applied")
            except Exception as e:
                logger.debug(f"Facebook: Could not set mobile UA: {e}")

            # Verify token works
            loop = asyncio.get_event_loop()
            me = await loop.run_in_executor(
                None, self._graph.get_object, "me"
            )

            self._page_id = (
                getattr(self.config, "facebook_page_id", None)
                or os.getenv("FACEBOOK_PAGE_ID", "")
            )

            # If page ID provided, get page access token
            if self._page_id:
                try:
                    accounts = await loop.run_in_executor(
                        None,
                        lambda: self._graph.get_connections("me", "accounts"),
                    )
                    for page in accounts.get("data", []):
                        if page.get("id") == self._page_id:
                            page_token = page.get("access_token")
                            if page_token:
                                self._page_graph = facebook.GraphAPI(
                                    access_token=page_token, version="3.1"
                                )
                                logger.info(
                                    f"✅ Facebook: Page '{page.get('name')}' linked"
                                )
                            break
                except Exception as e:
                    logger.warning(f"Facebook page setup failed: {e}")

            self._initialized = True
            logger.info(
                f"✅ Facebook: Logged in as {me.get('name', 'Unknown')}"
            )
            return True

        except Exception as e:
            logger.error(f"Facebook initialization failed: {e}")
            return False

    def _ensure_initialized(self):
        if not self._initialized or not self._graph:
            raise RuntimeError(
                "Facebook not initialized. Set FACEBOOK_ACCESS_TOKEN in .env"
            )

    def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous facebook-sdk call in an executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _active_graph(self, use_page: bool = False):
        """Return page graph if available and requested, else user graph."""
        if use_page and self._page_graph:
            return self._page_graph
        return self._graph

    # ──────────────────────────────────────────────────────────────────────
    # Posting
    # ──────────────────────────────────────────────────────────────────────

    async def post(
        self,
        message: str,
        link: Optional[str] = None,
        use_page: bool = False,
    ) -> Dict[str, Any]:
        """
        Post a status update to your profile or page.

        Args:
            message: Post text
            link: Optional URL to attach
            use_page: If True and page is set up, post as page
        """
        self._ensure_initialized()
        try:
            graph = self._active_graph(use_page)
            target = self._page_id if (use_page and self._page_id) else "me"

            kwargs = {"message": message}
            if link:
                kwargs["link"] = link

            result = await self._run_sync(
                graph.put_object, target, "feed", **kwargs
            )

            post_id = result.get("id", "")
            logger.info(f"✅ Facebook: Posted,  {post_id}")
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "post_id": post_id,
                "message": message[:100],
                "as_page": use_page and self._page_graph is not None,
            }
        except Exception as e:
            logger.error(f"Facebook post error: {e}")
            return {"success": False, "error": str(e)}

    async def upload_photo(
        self,
        path: str,
        caption: str = "",
        use_page: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload a photo to your profile or page.

        Args:
            path: Local file path to the image
            caption: Photo caption
            use_page: Post as page if True
        """
        self._ensure_initialized()
        try:
            graph = self._active_graph(use_page)
            target = self._page_id if (use_page and self._page_id) else "me"

            with open(path, "rb") as img:
                result = await self._run_sync(
                    graph.put_photo, img, message=caption, album_path=f"{target}/photos"
                )

            post_id = result.get("id", "") or result.get("post_id", "")
            logger.info(f"✅ Facebook: Photo uploaded,  {post_id}")
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "post_id": post_id,
                "caption": caption[:100],
            }
        except Exception as e:
            logger.error(f"Facebook upload_photo error: {e}")
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Reading
    # ──────────────────────────────────────────────────────────────────────

    async def get_feed(
        self, count: int = 10, use_page: bool = False
    ) -> Dict[str, Any]:
        """
        Get the feed (your posts or page posts).

        Args:
            count: Number of posts to retrieve
            use_page: Get page feed if True
        """
        self._ensure_initialized()
        try:
            graph = self._active_graph(use_page)
            target = self._page_id if (use_page and self._page_id) else "me"

            feed = await self._run_sync(
                graph.get_connections, target, "feed",
                **{"limit": count}
            )

            results = []
            for post in feed.get("data", [])[:count]:
                results.append({
                    "id": post.get("id", ""),
                    "message": post.get("message", "")[:200],
                    "created_time": post.get("created_time", ""),
                    "type": post.get("type", "status"),
                    "link": post.get("link", ""),
                })

            await asyncio.sleep(self._action_delay)
            return {"success": True, "count": len(results), "posts": results}
        except Exception as e:
            logger.error(f"Facebook get_feed error: {e}")
            return {"success": False, "error": str(e)}

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        """Get details about a specific post."""
        self._ensure_initialized()
        try:
            post = await self._run_sync(
                self._graph.get_object,
                post_id,
                **{"fields": "id,message,created_time,from,likes.summary(true),comments.summary(true),shares,type,link"}
            )

            likes = post.get("likes", {}).get("summary", {})
            comments = post.get("comments", {}).get("summary", {})

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "id": post.get("id", ""),
                "message": post.get("message", "")[:500],
                "created_time": post.get("created_time", ""),
                "from": post.get("from", {}).get("name", ""),
                "like_count": likes.get("total_count", 0),
                "comment_count": comments.get("total_count", 0),
                "shares": post.get("shares", {}).get("count", 0),
                "type": post.get("type", ""),
                "link": post.get("link", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Engagement
    # ──────────────────────────────────────────────────────────────────────

    async def like_post(self, post_id: str) -> Dict[str, Any]:
        """Like a post."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._graph.put_like, post_id
            )
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "liked", "post_id": post_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def comment_on_post(
        self, post_id: str, message: str
    ) -> Dict[str, Any]:
        """Comment on a post."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._graph.put_comment, post_id, message=message
            )
            comment_id = result.get("id", "") if isinstance(result, dict) else str(result)
            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "action": "commented",
                "post_id": post_id,
                "comment_id": comment_id,
                "message": message[:100],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_comments(
        self, post_id: str, count: int = 20
    ) -> Dict[str, Any]:
        """Get comments on a post."""
        self._ensure_initialized()
        try:
            comments = await self._run_sync(
                self._graph.get_connections,
                post_id, "comments",
                **{"limit": count}
            )

            results = []
            for c in comments.get("data", [])[:count]:
                results.append({
                    "id": c.get("id", ""),
                    "message": c.get("message", ""),
                    "from": c.get("from", {}).get("name", ""),
                    "created_time": c.get("created_time", ""),
                })

            return {"success": True, "count": len(results), "comments": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # User / Page Info
    # ──────────────────────────────────────────────────────────────────────

    async def get_profile(self) -> Dict[str, Any]:
        """Get your own profile info."""
        self._ensure_initialized()
        try:
            me = await self._run_sync(
                self._graph.get_object,
                "me",
                **{"fields": "id,name,email,link,picture"}
            )
            return {
                "success": True,
                "id": me.get("id", ""),
                "name": me.get("name", ""),
                "email": me.get("email", ""),
                "link": me.get("link", ""),
                "picture": me.get("picture", {}).get("data", {}).get("url", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_info(self, page_id: Optional[str] = None) -> Dict[str, Any]:
        """Get info about a Facebook page."""
        self._ensure_initialized()
        try:
            pid = page_id or self._page_id
            if not pid:
                return {"success": False, "error": "No page ID provided"}

            page = await self._run_sync(
                self._graph.get_object,
                pid,
                **{"fields": "id,name,about,fan_count,link,website,category,picture"}
            )

            return {
                "success": True,
                "id": page.get("id", ""),
                "name": page.get("name", ""),
                "about": page.get("about", ""),
                "fan_count": page.get("fan_count", 0),
                "link": page.get("link", ""),
                "website": page.get("website", ""),
                "category": page.get("category", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search(
        self,
        query: str,
        search_type: str = "page",
        count: int = 10,
    ) -> Dict[str, Any]:
        """
        Search Facebook (pages, places, etc.).

        Args:
            query: Search query
            search_type: 'page', 'place', 'event'
            count: Max results
        """
        self._ensure_initialized()
        try:
            results_raw = await self._run_sync(
                self._graph.request,
                f"/search?q={query}&type={search_type}&limit={count}"
            )

            results = []
            for item in results_raw.get("data", [])[:count]:
                results.append({
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "category": item.get("category", ""),
                    "link": item.get("link", ""),
                })

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "query": query,
                "type": search_type,
                "count": len(results),
                "results": results,
            }
        except Exception as e:
            logger.error(f"Facebook search error: {e}")
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Delete
    # ──────────────────────────────────────────────────────────────────────

    async def delete_post(self, post_id: str) -> Dict[str, Any]:
        """Delete one of your own posts."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._graph.delete_object, post_id
            )
            await asyncio.sleep(self._action_delay)
            return {"success": bool(result), "action": "deleted", "post_id": post_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def is_available(self) -> bool:
        """Check if Facebook skill is initialized and ready."""
        return self._initialized and self._graph is not None
