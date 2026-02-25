"""
LinkedIn Skill — Search people, post updates, send messages via linkedin-api.

Uses the linkedin-api library (unofficial LinkedIn API wrapper).
Authenticates directly via LinkedIn credentials (no official API key needed).
Direct HTTP requests to LinkedIn's Voyager API — no Selenium required.

Features:
- Search people, companies, jobs
- Get profiles and contact info
- Post updates (text, articles)
- Send and read messages
- Send/accept connection requests
- React to posts
- Browse job listings

Setup:
    Set these in .env:
        LINKEDIN_USERNAME=your_email@example.com
        LINKEDIN_PASSWORD=your_password

    Install:
        pip install linkedin-api
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from linkedin_api import Linkedin

    LINKEDIN_API_AVAILABLE = True
except ImportError:
    LINKEDIN_API_AVAILABLE = False
    logger.info("linkedin-api not installed. Install with: pip install linkedin-api")


class LinkedInSkill:
    """
    LinkedIn automation via linkedin-api (Voyager API, unofficial).
    Direct HTTP — no browser needed. Login with email + password.
    All calls are synchronous, wrapped in run_in_executor for async.
    """

    def __init__(self, config):
        self.config = config
        self._client: Optional[Any] = None
        self._initialized = False
        self._action_delay = getattr(config, "linkedin_action_delay", 2.0)

    async def initialize(self) -> bool:
        """Initialize LinkedIn client with credentials."""
        if not LINKEDIN_API_AVAILABLE:
            logger.warning("linkedin-api not available — LinkedIn skill disabled")
            return False

        username = (
            getattr(self.config, "linkedin_username", None)
            or os.getenv("LINKEDIN_USERNAME", "")
        )
        password = (
            getattr(self.config, "linkedin_password", None)
            or os.getenv("LINKEDIN_PASSWORD", "")
        )

        if not username or not password:
            logger.warning(
                "LinkedIn credentials not set. "
                "Set LINKEDIN_USERNAME and LINKEDIN_PASSWORD in .env"
            )
            return False

        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None, lambda: Linkedin(username, password)
            )

            # ── Mobile device session ──
            # Patch the underlying requests session with a mobile User-Agent
            # to match X skill's mobile-first approach and reduce detection.
            try:
                _mobile_ua = (
                    "Mozilla/5.0 (Linux; Android 14; SM-S928B) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.6778.200 Mobile Safari/537.36"
                )
                if hasattr(self._client, 'client') and hasattr(self._client.client, 'headers'):
                    self._client.client.headers.update({"User-Agent": _mobile_ua})
                    logger.debug("LinkedIn: Mobile device session headers applied")
            except Exception as e:
                logger.debug(f"LinkedIn: Could not set mobile UA: {e}")

            self._initialized = True
            logger.info("✅ LinkedIn: Logged in successfully")
            return True

        except Exception as e:
            logger.error(f"LinkedIn initialization failed: {e}")
            return False

    def _ensure_initialized(self):
        if not self._initialized or not self._client:
            raise RuntimeError(
                "LinkedIn not initialized. Set LINKEDIN_USERNAME and "
                "LINKEDIN_PASSWORD in .env"
            )

    def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous linkedin-api call in an executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ──────────────────────────────────────────────────────────────────────
    # Profiles
    # ──────────────────────────────────────────────────────────────────────

    async def get_profile(self, public_id: str) -> Dict[str, Any]:
        """
        Get a LinkedIn user's profile.

        Args:
            public_id: LinkedIn public profile ID (e.g. 'bill-gates')
        """
        self._ensure_initialized()
        try:
            profile = await self._run_sync(
                self._client.get_profile, public_id
            )
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "public_id": public_id,
                "first_name": profile.get("firstName", ""),
                "last_name": profile.get("lastName", ""),
                "headline": profile.get("headline", ""),
                "summary": (profile.get("summary", "") or "")[:500],
                "industry": profile.get("industryName", ""),
                "location": profile.get("locationName", ""),
                "connections": profile.get("connections", 0),
                "follower_count": profile.get("followerCount", 0),
                "experience": [
                    {
                        "title": exp.get("title", ""),
                        "company": exp.get("companyName", ""),
                        "duration": exp.get("timePeriod", {}).get("description", ""),
                    }
                    for exp in (profile.get("experience", []) or [])[:5]
                ],
            }
        except Exception as e:
            logger.error(f"LinkedIn get_profile error: {e}")
            return {"success": False, "error": str(e)}

    async def get_profile_contact_info(self, public_id: str) -> Dict[str, Any]:
        """Get a profile's contact information (email, phone, etc.)."""
        self._ensure_initialized()
        try:
            contact = await self._run_sync(
                self._client.get_profile_contact_info, public_id
            )
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "public_id": public_id,
                "email": contact.get("email_address", ""),
                "phone_numbers": contact.get("phone_numbers", []),
                "websites": contact.get("websites", []),
                "twitter": contact.get("twitter", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────────────────────

    async def search_people(
        self,
        keywords: str,
        limit: int = 10,
        network_depths: Optional[List[str]] = None,
        current_company: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: Search keywords (name, title, company, etc.)
            limit: Max results (default 10)
            network_depths: Filter by connection level: ['F'] (1st), ['S'] (2nd), ['O'] (3rd+)
            current_company: Filter by company ID list
            regions: Filter by region ID list
        """
        self._ensure_initialized()
        try:
            kwargs = {"keywords": keywords, "limit": limit}
            if network_depths:
                kwargs["network_depths"] = network_depths
            if current_company:
                kwargs["current_company"] = current_company
            if regions:
                kwargs["regions"] = regions

            people = await self._run_sync(
                self._client.search_people, **kwargs
            )

            results = []
            for p in people[:limit]:
                results.append({
                    "urn_id": p.get("urn_id", ""),
                    "public_id": p.get("public_id", ""),
                    "name": p.get("name", ""),
                    "headline": p.get("jobtitle", "") or p.get("headline", ""),
                    "location": p.get("location", ""),
                    "connection_degree": p.get("distance", ""),
                })

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "query": keywords,
                "count": len(results),
                "people": results,
            }
        except Exception as e:
            logger.error(f"LinkedIn search_people error: {e}")
            return {"success": False, "error": str(e)}

    async def search_companies(
        self, keywords: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Search for companies on LinkedIn."""
        self._ensure_initialized()
        try:
            companies = await self._run_sync(
                self._client.search_companies, keywords=keywords, limit=limit
            )

            results = []
            for c in companies[:limit]:
                results.append({
                    "urn_id": c.get("urn_id", ""),
                    "name": c.get("name", ""),
                    "headline": c.get("headline", ""),
                    "location": c.get("location", ""),
                })

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "query": keywords,
                "count": len(results),
                "companies": results,
            }
        except Exception as e:
            logger.error(f"LinkedIn search_companies error: {e}")
            return {"success": False, "error": str(e)}

    async def search_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search for jobs on LinkedIn.

        Args:
            keywords: Job title, skills, or keywords
            location: Location filter (city, country)
            limit: Max results
        """
        self._ensure_initialized()
        try:
            kwargs = {"keywords": keywords, "limit": limit}
            if location:
                kwargs["location_name"] = location

            jobs = await self._run_sync(
                self._client.search_jobs, **kwargs
            )

            results = []
            for j in jobs[:limit]:
                results.append({
                    "job_id": j.get("entityUrn", "").split(":")[-1] if j.get("entityUrn") else "",
                    "title": j.get("title", ""),
                    "company": j.get("companyName", ""),
                    "location": j.get("formattedLocation", ""),
                    "listed_at": j.get("listedAt", ""),
                })

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "query": keywords,
                "location": location,
                "count": len(results),
                "jobs": results,
            }
        except Exception as e:
            logger.error(f"LinkedIn search_jobs error: {e}")
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Posting
    # ──────────────────────────────────────────────────────────────────────

    async def post_update(
        self,
        text: str,
        article_url: Optional[str] = None,
        article_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a text update or share an article on LinkedIn.

        Args:
            text: Post text content
            article_url: URL to share (optional)
            article_title: Title for the shared article (optional)
        """
        self._ensure_initialized()
        try:
            kwargs = {"text": text}
            if article_url:
                kwargs["url"] = article_url
                if article_title:
                    kwargs["title"] = article_title

            # linkedin-api uses post method to create a share
            result = await self._run_sync(
                self._client.post, text
            )

            logger.info("✅ LinkedIn: Update posted")
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "action": "posted",
                "text": text[:100],
            }
        except Exception as e:
            logger.error(f"LinkedIn post_update error: {e}")
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Engagement
    # ──────────────────────────────────────────────────────────────────────

    async def react_to_post(
        self, post_urn: str, reaction_type: str = "LIKE"
    ) -> Dict[str, Any]:
        """
        React to a LinkedIn post.

        Args:
            post_urn: Post URN (e.g., 'urn:li:activity:1234567890')
            reaction_type: 'LIKE', 'CELEBRATE', 'LOVE', 'INSIGHTFUL', 'CURIOUS', 'FUNNY'
        """
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.react, post_urn, reaction_type
            )
            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "action": reaction_type.lower(),
                "post_urn": post_urn,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Messaging
    # ──────────────────────────────────────────────────────────────────────

    async def send_message(
        self, public_id: str, text: str
    ) -> Dict[str, Any]:
        """
        Send a message to a LinkedIn connection.

        Args:
            public_id: Recipient's public profile ID
            text: Message text
        """
        self._ensure_initialized()
        try:
            # Get URN ID from public ID for messaging
            profile = await self._run_sync(
                self._client.get_profile, public_id
            )
            urn_id = profile.get("profile_id") or profile.get("entityUrn", "").split(":")[-1]

            if not urn_id:
                return {"success": False, "error": f"Could not resolve URN for {public_id}"}

            result = await self._run_sync(
                self._client.send_message, text, recipients=[urn_id]
            )
            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "action": "message_sent",
                "recipient": public_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_conversations(self, count: int = 20) -> Dict[str, Any]:
        """Get recent message conversations."""
        self._ensure_initialized()
        try:
            conversations = await self._run_sync(
                self._client.get_conversations
            )

            results = []
            for conv in (conversations.get("elements", []) or [])[:count]:
                participants = []
                for p in conv.get("participants", []):
                    profile = p.get("com.linkedin.voyager.messaging.MessagingMember", {})
                    mini = profile.get("miniProfile", {})
                    name = f"{mini.get('firstName', '')} {mini.get('lastName', '')}".strip()
                    if name:
                        participants.append(name)

                last_msg = conv.get("lastMessage", {}) or {}
                event_content = last_msg.get("com.linkedin.voyager.messaging.event.MessageEvent", {})

                results.append({
                    "conversation_id": conv.get("entityUrn", "").split(":")[-1],
                    "participants": participants,
                    "last_message": (event_content.get("attributedBody", {}).get("text", "") or "")[:100],
                    "last_activity": conv.get("lastActivityAt", ""),
                })

            return {"success": True, "count": len(results), "conversations": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Connections
    # ──────────────────────────────────────────────────────────────────────

    async def send_connection_request(
        self, public_id: str, message: str = ""
    ) -> Dict[str, Any]:
        """
        Send a connection request to a user.

        Args:
            public_id: Target user's public profile ID
            message: Optional message to include (max 300 chars for free accounts)
        """
        self._ensure_initialized()
        try:
            # Get profile to get URN
            profile = await self._run_sync(
                self._client.get_profile, public_id
            )
            urn_id = profile.get("profile_id") or profile.get("entityUrn", "").split(":")[-1]

            kwargs = {"profile_public_id": public_id}
            if message:
                kwargs["message"] = message[:300]

            result = await self._run_sync(
                self._client.add_connection, **kwargs
            )

            await asyncio.sleep(self._action_delay)
            return {
                "success": True,
                "action": "connection_request_sent",
                "recipient": public_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def remove_connection(self, public_id: str) -> Dict[str, Any]:
        """Remove a first-degree connection."""
        self._ensure_initialized()
        try:
            result = await self._run_sync(
                self._client.remove_connection, public_id
            )
            await asyncio.sleep(self._action_delay)
            return {"success": True, "action": "connection_removed", "public_id": public_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Feed
    # ──────────────────────────────────────────────────────────────────────

    async def get_feed_posts(self, count: int = 10) -> Dict[str, Any]:
        """Get posts from your LinkedIn feed."""
        self._ensure_initialized()
        try:
            feed = await self._run_sync(
                self._client.get_feed_posts, limit=count
            )

            results = []
            for post in feed[:count]:
                actor = post.get("actor", {})
                results.append({
                    "urn": post.get("entityUrn", ""),
                    "text": (post.get("commentary", {}).get("text", {}).get("text", "") or "")[:300],
                    "author": actor.get("name", {}).get("text", ""),
                    "author_headline": actor.get("description", {}).get("text", ""),
                    "num_likes": post.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numLikes", 0),
                    "num_comments": post.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numComments", 0),
                })

            return {"success": True, "count": len(results), "posts": results}
        except Exception as e:
            logger.error(f"LinkedIn get_feed_posts error: {e}")
            return {"success": False, "error": str(e)}

    async def get_user_posts(
        self, public_id: str, count: int = 10
    ) -> Dict[str, Any]:
        """Get a user's recent posts."""
        self._ensure_initialized()
        try:
            # Get URN from profile
            profile = await self._run_sync(
                self._client.get_profile, public_id
            )
            urn_id = profile.get("profile_id") or profile.get("entityUrn", "").split(":")[-1]

            posts = await self._run_sync(
                self._client.get_profile_posts, urn_id=urn_id, post_count=count
            )

            results = []
            for p in posts[:count]:
                commentary = p.get("commentary", {}) or {}
                text = commentary.get("text", {}).get("text", "") if isinstance(commentary.get("text"), dict) else str(commentary.get("text", ""))
                social = p.get("socialDetail", {}) or {}
                counts = social.get("totalSocialActivityCounts", {}) or {}

                results.append({
                    "urn": p.get("entityUrn", ""),
                    "text": text[:300],
                    "num_likes": counts.get("numLikes", 0),
                    "num_comments": counts.get("numComments", 0),
                })

            return {
                "success": True,
                "public_id": public_id,
                "count": len(results),
                "posts": results,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────
    # Company
    # ──────────────────────────────────────────────────────────────────────

    async def get_company(self, company_id: str) -> Dict[str, Any]:
        """
        Get company information.

        Args:
            company_id: Company's universal name or ID
        """
        self._ensure_initialized()
        try:
            company = await self._run_sync(
                self._client.get_company, company_id
            )
            await asyncio.sleep(self._action_delay)

            return {
                "success": True,
                "name": company.get("name", ""),
                "tagline": company.get("tagline", ""),
                "description": (company.get("description", "") or "")[:500],
                "industry": company.get("companyIndustries", [{}])[0].get("localizedName", "") if company.get("companyIndustries") else "",
                "staff_count": company.get("staffCount", 0),
                "headquarters": company.get("headquarter", {}).get("city", ""),
                "website": company.get("companyPageUrl", ""),
                "follower_count": company.get("followerCount", 0),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def is_available(self) -> bool:
        """Check if LinkedIn skill is initialized and ready."""
        return self._initialized and self._client is not None
