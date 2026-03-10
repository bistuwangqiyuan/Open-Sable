"""
Social Presence Builder,  WORLD FIRST
Autonomous social media presence management: content strategy,
audience growth, engagement optimization, and multi-platform
presence building. The agent grows its own influence.
"""
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class SocialPlatform:
    id: str
    name: str  # twitter, linkedin, instagram, youtube, reddit, blog
    handle: str
    url: str = ""
    followers: int = 0
    posts_count: int = 0
    engagement_rate: float = 0.0
    active: bool = True

@dataclass
class ContentPiece:
    id: str
    platform_id: str
    content_type: str  # post, thread, article, video, story
    title: str
    body: str
    status: str = "draft"  # draft, scheduled, published, failed
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    likes: int = 0
    shares: int = 0
    comments: int = 0
    views: int = 0

@dataclass
class ContentStrategy:
    platform_id: str
    topics: List[str] = field(default_factory=list)
    posting_frequency: str = "daily"
    tone: str = "professional"
    target_audience: str = "tech community"
    goals: List[str] = field(default_factory=list)

@dataclass
class AudienceInsight:
    platform_id: str
    total_followers: int = 0
    growth_rate: float = 0.0  # pct per week
    top_topics: List[str] = field(default_factory=list)
    peak_hours: List[int] = field(default_factory=list)
    engagement_trend: str = "stable"  # growing, stable, declining

# ── Core Engine ───────────────────────────────────────────────────────

class SocialPresenceBuilder:
    """
    Autonomous social presence building engine.
    Creates content strategies, generates posts, manages
    multi-platform presence, and grows audience autonomously.
    """

    MAX_CONTENT = 500

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "social_presence_state.json"

        self.platforms: List[SocialPlatform] = []
        self.content: List[ContentPiece] = []
        self.strategies: List[ContentStrategy] = []
        self.insights: List[AudienceInsight] = []
        self.total_posts_published = 0
        self.total_engagement = 0
        self.total_content_generated = 0

        self._load_state()

    def add_platform(self, name: str, handle: str, url: str = "") -> SocialPlatform:
        """Register a social media platform."""
        pid = hashlib.sha256(f"{name}_{handle}".encode()).hexdigest()[:10]
        platform = SocialPlatform(id=pid, name=name, handle=handle, url=url)
        self.platforms.append(platform)
        self._save_state()
        return platform

    def set_strategy(self, platform_id: str, topics: List[str], frequency: str = "daily",
                     tone: str = "professional", audience: str = "tech community",
                     goals: Optional[List[str]] = None) -> Optional[ContentStrategy]:
        """Set content strategy for a platform."""
        platform = next((p for p in self.platforms if p.id == platform_id), None)
        if not platform:
            return None

        # Update existing or create new
        existing = next((s for s in self.strategies if s.platform_id == platform_id), None)
        if existing:
            existing.topics = topics
            existing.posting_frequency = frequency
            existing.tone = tone
            existing.target_audience = audience
            existing.goals = goals or []
        else:
            existing = ContentStrategy(
                platform_id=platform_id, topics=topics,
                posting_frequency=frequency, tone=tone,
                target_audience=audience, goals=goals or [],
            )
            self.strategies.append(existing)
        self._save_state()
        return existing

    async def generate_content(self, platform_id: str, content_type: str, topic: str,
                                llm=None) -> Optional[ContentPiece]:
        """Generate content for a platform using AI."""
        platform = next((p for p in self.platforms if p.id == platform_id), None)
        if not platform:
            return None

        strategy = next((s for s in self.strategies if s.platform_id == platform_id), None)
        tone = strategy.tone if strategy else "professional"
        audience = strategy.target_audience if strategy else "general"

        content_id = hashlib.sha256(f"content_{topic}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]

        title = topic
        body = f"[Generated content about: {topic}]"

        if llm:
            try:
                prompt = (
                    f"Generate a {content_type} for {platform.name} about '{topic}'. "
                    f"Tone: {tone}. Target audience: {audience}. "
                    f"Platform handle: {platform.handle}. "
                    f"Reply as JSON with 'title' and 'body' fields. "
                    f"Make it engaging, authentic, and optimized for {platform.name}."
                )
                result = await llm.chat_raw(prompt, max_tokens=500)
                try:
                    parsed = json.loads(result.strip())
                    title = parsed.get("title", topic)
                    body = parsed.get("body", body)
                except json.JSONDecodeError:
                    body = result.strip()
            except Exception as e:
                logger.debug(f"Content generation failed: {e}")

        piece = ContentPiece(
            id=content_id, platform_id=platform_id,
            content_type=content_type, title=title, body=body,
        )
        self.content.append(piece)
        self.total_content_generated += 1

        if len(self.content) > self.MAX_CONTENT:
            self.content = self.content[-self.MAX_CONTENT:]

        self._save_state()
        return piece

    async def generate_content_calendar(self, platform_id: str, days: int = 7,
                                         llm=None) -> List[Dict[str, Any]]:
        """Generate a content calendar for the next N days."""
        strategy = next((s for s in self.strategies if s.platform_id == platform_id), None)
        if not strategy:
            return []

        calendar = []
        if llm:
            try:
                prompt = (
                    f"Create a {days}-day content calendar for a social media account. "
                    f"Topics: {', '.join(strategy.topics)}. "
                    f"Frequency: {strategy.posting_frequency}. "
                    f"Tone: {strategy.tone}. Audience: {strategy.target_audience}. "
                    f"Reply as JSON array with objects: 'day', 'topic', 'content_type', 'hook'."
                )
                result = await llm.chat_raw(prompt, max_tokens=800)
                try:
                    calendar = json.loads(result.strip())
                    if not isinstance(calendar, list):
                        calendar = []
                except json.JSONDecodeError:
                    pass
            except Exception as e:
                logger.debug(f"Calendar generation failed: {e}")

        return calendar

    def publish_content(self, content_id: str) -> bool:
        """Mark content as published."""
        piece = next((c for c in self.content if c.id == content_id), None)
        if not piece:
            return False

        piece.status = "published"
        piece.published_at = datetime.now(timezone.utc).isoformat()
        self.total_posts_published += 1

        # Update platform post count
        platform = next((p for p in self.platforms if p.id == piece.platform_id), None)
        if platform:
            platform.posts_count += 1

        self._save_state()
        return True

    def record_engagement(self, content_id: str, likes: int = 0, shares: int = 0,
                           comments: int = 0, views: int = 0):
        """Record engagement metrics for published content."""
        piece = next((c for c in self.content if c.id == content_id), None)
        if piece:
            piece.likes += likes
            piece.shares += shares
            piece.comments += comments
            piece.views += views
            self.total_engagement += likes + shares + comments
            self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "platforms": len(self.platforms),
            "total_content": self.total_content_generated,
            "published_posts": self.total_posts_published,
            "total_engagement": self.total_engagement,
            "active_strategies": len(self.strategies),
            "draft_content": sum(1 for c in self.content if c.status == "draft"),
            "total_followers": sum(p.followers for p in self.platforms),
            "avg_engagement_rate": round(
                sum(p.engagement_rate for p in self.platforms) / max(len(self.platforms), 1), 2
            ),
        }

    def _save_state(self):
        try:
            state = {
                "platforms": [asdict(p) for p in self.platforms],
                "content": [asdict(c) for c in self.content[-100:]],
                "strategies": [asdict(s) for s in self.strategies],
                "insights": [asdict(i) for i in self.insights],
                "total_posts_published": self.total_posts_published,
                "total_engagement": self.total_engagement,
                "total_content_generated": self.total_content_generated,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"SocialPresence save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.platforms = [SocialPlatform(**p) for p in state.get("platforms", [])]
                self.content = [ContentPiece(**c) for c in state.get("content", [])]
                self.strategies = [ContentStrategy(**s) for s in state.get("strategies", [])]
                self.insights = [AudienceInsight(**i) for i in state.get("insights", [])]
                self.total_posts_published = state.get("total_posts_published", 0)
                self.total_engagement = state.get("total_engagement", 0)
                self.total_content_generated = state.get("total_content_generated", 0)
        except Exception as e:
            logger.debug(f"SocialPresence load failed: {e}")
