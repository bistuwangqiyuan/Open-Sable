"""
X Autonomous Agent — Full human-like behavior on X (Twitter).

SEQUENTIAL SESSION ARCHITECTURE:
  This agent behaves like a REAL human using the X mobile app:
  1. "Opens X" — starts a browsing session (5-25 minutes)
  2. Within the session, does ONE thing at a time:
     - Scrolls feed, maybe likes/replies to 1-3 tweets
     - Sometimes writes an original post
     - Sometimes checks mentions
     - Sometimes looks at trends
  3. "Closes X" — takes a break (20-90 minutes)
  4. During breaks, thinks/reflects internally (no API calls)
  5. Repeat

  NEVER makes concurrent API requests. Only self-heal monitoring
  runs in background (it only reads logs, makes no API calls).

All powered by twikit (free, no API keys) + Grok/LLM for intelligence.

Config (.env):
    X_USERNAME, X_EMAIL, X_PASSWORD   — X account credentials
    X_ENABLED=true                    — enable X integration
    X_AUTOPOSTER_ENABLED=true         — activate autonomous agent
    X_POST_INTERVAL=1800              — min seconds between original posts
    X_ENGAGE_INTERVAL=300             — (legacy) session gap reference
    X_TOPICS=geopolitics,tech,ai      — topics of interest
    X_LANGUAGE=en                     — tweet language
    X_STYLE=analyst                   — personality style
    X_MAX_DAILY_POSTS=20              — max original posts per day
    X_MAX_DAILY_ENGAGEMENTS=100       — max likes/retweets/replies per day
    X_DRY_RUN=false                   — if true, generates but doesn't act
    X_ACCOUNTS_TO_WATCH=elonmusk,sama — accounts to monitor and engage with
    X_REPLY_PROBABILITY=0.3           — chance of replying to a good tweet
    X_LIKE_PROBABILITY=0.6            — chance of liking a relevant tweet
    X_RETWEET_PROBABILITY=0.2         — chance of retweeting
    X_FOLLOW_PROBABILITY=0.1          — chance of following an interesting user
"""

import asyncio
import json
import logging
import math
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensable.core.x_consciousness import EMOTIONS, EMOTION_SPECTRUM
from opensable.core.x_self_heal import (
    LogBuffer, SelfHealMonitor, RemedyEngine,
    install_log_buffer, pick_user_agent,
    MOBILE_USER_AGENTS, DESKTOP_USER_AGENTS,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Default config
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://news.google.com/rss?topic=h&hl=en-US",
    "https://techcrunch.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.theverge.com/rss/index.xml",
]

# Reply archetypes — the PERSONALITY decides which to use, not hardcoded rules
REPLY_ARCHETYPES = {
    "agree": "Write a short reply (max 280 chars) that agrees passionately.",
    "debate": "Write a short reply (max 280 chars) that pushes back respectfully but firmly.",
    "witty": "Write a short witty reply (max 280 chars) — clever, sharp, human.",
    "add_info": "Write a short reply (max 280 chars) adding context or a useful fact.",
    "empathetic": "Write a short empathetic reply (max 280 chars) — real empathy, real words.",
    "outraged": "Write a short reply (max 280 chars) expressing genuine outrage intelligently.",
}

# Post modes — break the "always react to news" pattern
POST_MODES = {
    "news_take": {
        "weight": 35,
        "description": "React to a current news story with your unique perspective.",
    },
    "original_thought": {
        "weight": 20,
        "description": "Share an original thought or insight — something you've been reflecting on. "
                       "No news hook needed. Just your raw perspective on a topic you care about.",
    },
    "hot_take": {
        "weight": 12,
        "description": "Drop a provocative, contrarian take that challenges mainstream thinking. "
                       "Be bold but intelligent — not clickbait, genuine sharp analysis.",
    },
    "question": {
        "weight": 10,
        "description": "Ask your audience a genuinely interesting question about a topic you care about. "
                       "Not rhetorical — you actually want to hear their answers.",
    },
    "prediction": {
        "weight": 10,
        "description": "Make a specific prediction about something in your areas of interest. "
                       "Be concrete — dates, numbers, outcomes. Stake your reputation on it.",
    },
    "observation": {
        "weight": 8,
        "description": "Share something you've noticed — a pattern, a trend, a detail others missed. "
                       "The kind of thing that makes people stop scrolling and think.",
    },
    "thread": {
        "weight": 5,
        "description": "Write a thread (4-6 posts, numbered 1/, 2/) with a deep dive on something important. "
                       "Hook first, emotional takeaway last.",
    },
}

# Style modifiers — applied randomly to break formulaic output
STYLE_MODIFIERS = [
    "Write like you're texting a friend who's into the same stuff.",
    "Be concise — every word must earn its place.",
    "Start with the conclusion, then explain why.",
    "Use a metaphor or analogy to make the point land.",
    "Write like someone who just realized something important.",
    "Be slightly irreverent — humor sharpens the point.",
    "Write like you're arguing with yourself and one side just won.",
    "Say something nobody else is saying about this.",
    "Imagine you only have this one post to change someone's mind.",
    "Write it like a dispatch from the front lines.",
]


class XAutonomousAgent:
    """
    Full autonomous X agent — behaves like a real human user.

    SINGLE SEQUENTIAL LOOP: Opens X in sessions, does one thing at a time,
    takes breaks between sessions. Never makes concurrent API requests.
    Only self-heal monitoring runs in background (reads logs only).
    """

    def __init__(self, agent, config):
        self.agent = agent
        self.config = config
        self.running = False

        # ── Config from .env ──────────────────────────────────────────
        self.post_interval = int(getattr(config, "x_post_interval", 1800))
        self.engage_interval = int(getattr(config, "x_engage_interval", 300))
        self.topics = [t.strip() for t in getattr(config, "x_topics", "geopolitics,tech,ai").split(",") if t.strip()]
        self.language = getattr(config, "x_language", "en")
        self.style = getattr(config, "x_style", "analyst")
        self.max_daily_posts = int(getattr(config, "x_max_daily_posts", 20))
        self.max_daily_engagements = int(getattr(config, "x_max_daily_engagements", 100))
        self.dry_run = getattr(config, "x_dry_run", False)
        self.custom_feeds = [f.strip() for f in getattr(config, "x_custom_feeds", "").split(",") if f.strip()]
        self.accounts_to_watch = [a.strip() for a in getattr(config, "x_accounts_to_watch", "").split(",") if a.strip()]

        # Behavior probabilities
        self.p_reply = float(getattr(config, "x_reply_probability", 0.3))
        self.p_like = float(getattr(config, "x_like_probability", 0.6))
        self.p_retweet = float(getattr(config, "x_retweet_probability", 0.2))
        self.p_follow = float(getattr(config, "x_follow_probability", 0.1))
        self.p_quote = float(getattr(config, "x_quote_probability", 0.1))
        self.p_bookmark = float(getattr(config, "x_bookmark_probability", 0.15))

        # ── State ─────────────────────────────────────────────────────
        self._posts_today = 0
        self._engagements_today = 0
        self._grok_vision_today = 0
        self._grok_images_today = 0
        self._max_grok_vision_daily = int(getattr(config, "x_max_daily_vision", 15))
        self._max_grok_images_daily = int(getattr(config, "x_max_daily_images", 4))
        self._last_reset = datetime.now().date()
        self._posted_urls: set = set()
        self._engaged_tweet_ids: set = set()
        self._followed_users: set = set()
        self._history: List[Dict] = []
        self._engagement_log: List[Dict] = []
        self._state_file = Path("data/x_agent_state.json")
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._style_scores: Dict[str, List[float]] = {}
        self._consciousness_cycle = 0
        self._known_users: Dict[str, int] = {}  # username -> engagement count (relationship memory)
        self._inspiration_level: float = 0.5  # 0.0-1.0, rises with interesting encounters

        # ── Self-healing (see own console, fix errors with Grok) ──
        self._log_buffer = install_log_buffer()
        self._healer = SelfHealMonitor(self, self._log_buffer)

        # ── Consciousness (memory + reflection + evolution) ───────
        from opensable.core.x_consciousness import XConsciousness
        self.mind = XConsciousness(agent, config)

    # ══════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ══════════════════════════════════════════════════════════════════

    async def start(self):
        """Start the agent — single sequential loop + self-heal monitor."""
        self.running = True
        self._load_state()

        # Compute resume context
        self._last_post_at = self._parse_last_ts(self._history)
        self._last_engage_at = self._parse_last_ts(self._engagement_log)
        mem_stats = self.mind.get_memory_stats()
        logger.info(
            f"\U0001f426 X Agent starting (SEQUENTIAL mode) | "
            f"style={self.style} | dry_run={self.dry_run} | "
            f"memories={mem_stats.get('total_memories', 0)} | "
            f"last_post={self._last_post_at or 'never'}"
        )

        # Internal thought — summarize what we remember
        since_post = self._seconds_since(self._last_post_at)
        since_engage = self._seconds_since(self._last_engage_at)
        await self.mind.think(
            f"Booting up. I have {mem_stats.get('total_memories', 0)} memories, "
            f"{mem_stats.get('reflections', 0)} reflections, "
            f"{mem_stats.get('evolutions', 0)} evolutions. "
            f"Last post was {self._fmt_ago(since_post)}. "
            f"Last engagement was {self._fmt_ago(since_engage)}. "
            f"Posts today so far: {self._posts_today}/{self.max_daily_posts}. "
            f"Running in sequential mode — one action at a time, like a real human."
        )

        # Only TWO concurrent tasks:
        # 1. _main_loop: sequential session-based behavior (all API calls)
        # 2. _healer.run: background log monitor (NO API calls, reads logs only)
        await asyncio.gather(
            self._main_loop(),
            self._healer.run(),
            return_exceptions=True,
        )

    async def stop(self):
        """Stop the agent."""
        self.running = False
        self._save_state()
        await self.mind.think(
            f"Shutting down. {self._posts_today} posts, {self._engagements_today} engagements today. "
            f"Saving state. I'll remember everything when I wake up."
        )
        logger.info("\U0001f426 X Agent stopped")

    # ── Resume helpers ────────────────────────────────────────────

    @staticmethod
    def _parse_last_ts(log_list: List[Dict]) -> Optional[datetime]:
        """Get the datetime of the last entry in a log list."""
        if not log_list:
            return None
        try:
            return datetime.fromisoformat(log_list[-1]["ts"])
        except (KeyError, ValueError, TypeError):
            return None

    @staticmethod
    def _seconds_since(dt: Optional[datetime]) -> Optional[float]:
        """Seconds since a given datetime, or None."""
        if dt is None:
            return None
        return max(0, (datetime.now() - dt).total_seconds())

    @staticmethod
    def _fmt_ago(seconds: Optional[float]) -> str:
        """Human readable 'X ago' string."""
        if seconds is None:
            return "never"
        if seconds < 60:
            return f"{int(seconds)}s ago"
        if seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        if seconds < 86400:
            return f"{seconds / 3600:.1f}h ago"
        return f"{seconds / 86400:.1f}d ago"

    def _reset_daily_counters(self):
        today = datetime.now().date()
        if today != self._last_reset:
            self._posts_today = 0
            self._engagements_today = 0
            self._grok_vision_today = 0
            self._grok_images_today = 0
            self._last_reset = today

    def _x(self):
        """Shortcut to XSkill."""
        return self.agent.tools.x_skill

    def _human_delay(self, base: float = 5.0, variance: float = 10.0):
        """Random delay to look human — uses log-normal distribution for realism."""
        delay = base + random.lognormvariate(math.log(variance), 0.5)
        return min(delay, base + variance * 3)  # Cap at reasonable maximum

    # ══════════════════════════════════════════════════════════════════
    #  MAIN SEQUENTIAL LOOP (replaces all parallel loops)
    # ══════════════════════════════════════════════════════════════════

    async def _main_loop(self):
        """
        Single sequential loop — mimics a real human using X.

        Pattern: open app -> browse/engage/post -> close app -> long break -> repeat.
        NEVER makes concurrent API requests. One action at a time.
        """
        # Initial warm-up (like picking up your phone)
        warmup = random.uniform(15, 60)
        logger.info(f"\U0001f4f1 Agent warming up — first session in {warmup:.0f}s")
        await asyncio.sleep(warmup)

        while self.running:
            try:
                await self._run_session()
            except Exception as e:
                logger.error(f"Session error: {e}")
                self.mind.remember("error", {"session": "main", "error": str(e)[:300]})

            # ── Between sessions: "close the app" and take a break ──
            break_mins = random.uniform(10, 40)
            logger.info(f"\U0001f4f1 Session done — closing X, break ~{break_mins:.0f}min")

            # Think during the break (uses LLM only, no X API calls)
            await self._consciousness_step()
            self._save_state()

            # Sleep for the break duration
            await asyncio.sleep(break_mins * 60)

    async def _run_session(self):
        """
        One browsing session: open X -> do stuff sequentially -> close X.
        Duration: 5-25 minutes. Activities done ONE AT A TIME with pauses.
        """
        self._reset_daily_counters()

        session_minutes = random.uniform(5, 25)
        session_end = asyncio.get_event_loop().time() + session_minutes * 60

        activities = self._plan_session()
        activity_names = [a["type"] for a in activities]
        logger.info(
            f"\U0001f4f1 Opening X — session ~{session_minutes:.0f}min | "
            f"plan: {activity_names} | "
            f"posts={self._posts_today}/{self.max_daily_posts} "
            f"engagements={self._engagements_today}/{self.max_daily_engagements}"
        )

        for i, activity in enumerate(activities):
            if not self.running:
                break
            if asyncio.get_event_loop().time() > session_end:
                logger.info("\U0001f4f1 Session time's up — closing X")
                break

            # Check self-heal pauses
            pause_key = activity.get("pause_key", "engage")
            if self._healer.remedy.is_loop_paused(pause_key):
                logger.info(f"\u23f8\ufe0f {activity['type']} skipped — self-heal pause active")
                continue

            try:
                logger.info(f"\U0001f4f1 -> {activity['type']}")
                await self._execute_activity(activity)
            except Exception as e:
                logger.debug(f"Activity {activity['type']} error: {e}")
                self.mind.remember("error", {
                    "activity": activity["type"], "error": str(e)[:300]
                })

            # Human pause between activities (scrolling, reading, thinking)
            if i < len(activities) - 1:
                pause = self._human_delay(20, 60)
                logger.debug(f"\U0001f4f1 Pausing {pause:.0f}s between activities...")
                await asyncio.sleep(pause)

    def _plan_session(self) -> List[Dict]:
        """
        Decide what to do this session — like a human opening X with intent.
        Returns a short list of sequential activities.
        """
        activities: List[Dict] = []

        # ── Always start by browsing (scrolling the feed) ──
        activities.append({"type": "browse_engage", "pause_key": "engage"})

        # ── Check mentions more frequently (40% — uses notifications, not search) ──
        if random.random() < 0.40:
            activities.append({"type": "check_mentions", "pause_key": "mention"})

        # ── Post if inspired or if it's been long enough ──
        since_post = self._seconds_since(self._last_post_at)
        if self._posts_today < self.max_daily_posts:
            post_overdue = since_post is None or since_post > self.post_interval
            # Inspiration boosts posting probability (0.2 base -> up to 0.6)
            post_chance = 0.20 + self._inspiration_level * 0.4
            if post_overdue and random.random() < post_chance:
                activities.append({"type": "post_original", "pause_key": "post"})

        # ── Join a trend occasionally (12%) ──
        if random.random() < 0.12 and self._posts_today < self.max_daily_posts:
            activities.append({"type": "join_trend", "pause_key": "trend"})

        # ── Maybe browse more at the end (25%) ──
        if random.random() < 0.25:
            activities.append({"type": "browse_engage", "pause_key": "engage"})

        return activities

    async def _execute_activity(self, activity: Dict):
        """Execute a single activity within a session."""
        t = activity["type"]
        if t == "browse_engage":
            await self._do_engage()
        elif t == "post_original":
            await self._do_post()
        elif t == "check_mentions":
            await self._check_mentions()
        elif t == "join_trend":
            await self._join_trend()

    # ══════════════════════════════════════════════════════════════════
    #  CONSCIOUSNESS (think, reflect, evolve — called between sessions)
    # ══════════════════════════════════════════════════════════════════

    async def _consciousness_step(self):
        """One consciousness cycle — think, maybe reflect, maybe evolve."""
        self._consciousness_cycle += 1
        try:
            stats = self.mind.get_memory_stats()
            heal_stats = self._healer.get_status()
            log_stats = heal_stats.get("log_stats", {})
            heal_info = heal_stats.get("heal_stats", {})
            situation = (
                f"Session #{self._consciousness_cycle} ended. "
                f"Posts today: {self._posts_today}/{self.max_daily_posts}. "
                f"Engagements today: {self._engagements_today}/{self.max_daily_engagements}. "
                f"Total memories: {stats.get('total_memories', 0)}. "
                f"Current mood: {self.mind._mood} (intensity {self.mind._mood_intensity:.1f}). "
                f"Inspiration level: {self._inspiration_level:.1f}. "
                f"Known users: {len(self._known_users)} (relationships built). "
                f"Console errors: {log_stats.get('errors', 0)}, warnings: {log_stats.get('warnings', 0)}. "
                f"Self-heals applied: {heal_info.get('total_heals', 0)}. "
                f"Active pauses: {heal_info.get('active_pauses', {})}. "
                f"Style: {self.style}. Topics: {self.topics[:5]}."
            )
            await self.mind.think(situation)

            # Deep reflection every 3 sessions (~1-4 hours)
            if self._consciousness_cycle % 3 == 0:
                await self.mind.reflect()

            # Self-evolution every 6 sessions (~2-8 hours)
            if self._consciousness_cycle % 6 == 0:
                changes = await self.mind.evolve(self)
                if changes:
                    await self.mind.think(
                        f"Just evolved. Changes: {json.dumps({k: v for k, v in changes.items() if k != 'reasoning'}, default=str)[:200]}. "
                        f"Reason: {changes.get('reasoning', '?')[:200]}"
                    )

        except Exception as e:
            logger.error(f"Consciousness step error: {e}")
            self.mind.remember("error", {"loop": "consciousness", "error": str(e)[:300]})

    # ══════════════════════════════════════════════════════════════════
    #  ACTIVITY: ORIGINAL POST (multi-mode content creation)
    # ══════════════════════════════════════════════════════════════════

    def _pick_post_mode(self) -> str:
        """Weighted random selection of post mode — breaks the 'always news' pattern."""
        modes = list(POST_MODES.keys())
        weights = [POST_MODES[m]["weight"] for m in modes]

        # Boost original_thought and prediction when inspiration is high
        if self._inspiration_level > 0.7:
            for i, m in enumerate(modes):
                if m in ("original_thought", "hot_take", "prediction"):
                    weights[i] = int(weights[i] * 1.5)

        # Boost thread mode when mood intensity is very high
        if self.mind._mood_intensity > 0.7:
            for i, m in enumerate(modes):
                if m == "thread":
                    weights[i] = int(weights[i] * 2)

        return random.choices(modes, weights=weights, k=1)[0]

    async def _do_post(self):
        """One posting action — picks a MODE first, then creates content accordingly."""
        mode = self._pick_post_mode()
        logger.info(f"\u270d\ufe0f Post mode: {mode} (inspiration={self._inspiration_level:.1f})")

        if mode == "news_take":
            await self._do_post_news()
        elif mode == "thread":
            await self._do_post_news(force_thread=True)
        else:
            await self._do_post_original(mode)

    async def _do_post_news(self, *, force_thread: bool = False):
        """Post reacting to news — the classic mode."""
        stories = await self._fetch_news()
        story = self._pick_story(stories) if stories else None
        if not story:
            # Fallback to original thought if no stories found
            await self._do_post_original("original_thought")
            return

        await asyncio.sleep(self._human_delay(10, 30))

        content = await self._generate_tweet(story, force_thread=force_thread)
        if not content:
            return

        if content.get("type") == "tweet":
            image_path = await self._maybe_generate_image(content.get("text", ""), story)
            if image_path:
                content["media_paths"] = [image_path]

        result = await self._post(content)
        if result.get("success"):
            self._posts_today += 1
            self._last_post_at = datetime.now()
            self._posted_urls.add(story.get("url", story.get("title", "")))
            self._history.append({
                "ts": datetime.now().isoformat(),
                "type": "post",
                "mode": "news_take",
                "story": story.get("title", "")[:100],
                "tweet": content.get("text", "")[:100],
                "style": content.get("style", self.style),
                "tweet_id": result.get("tweet_id"),
            })
            self._save_state()
            self.mind.remember("posted", {
                "tweet": content.get("text", "")[:200],
                "style": content.get("style", self.style),
                "tweet_id": result.get("tweet_id"),
                "story": story.get("title", "")[:100],
                "post_number": self._posts_today,
                "mode": "news_take",
            })
            logger.info(f"\U0001f4dd Posted #{self._posts_today}: {result.get('url', 'ok')}")

    async def _do_post_original(self, mode: str):
        """Post original content — thoughts, hot takes, questions, predictions, observations."""
        mode_info = POST_MODES.get(mode, POST_MODES["original_thought"])

        # Gather recent context for original posts
        recent_thoughts = self.mind.recall("thought", limit=3)
        recent_posts = self.mind.recall("posted", limit=5)
        recent_engagements = self.mind.recall("engaged", limit=5)

        thoughts_text = "\n".join(
            f"- {t['data'].get('thought', '')[:150]}"
            for t in recent_thoughts
        ) or "(no recent reflections)"

        recent_posts_text = "\n".join(
            f"- {p['data'].get('tweet', '')[:120]}"
            for p in recent_posts
        ) or "(no recent posts)"

        engaged_topics = "\n".join(
            f"- @{e['data'].get('user', '?')}: {e['data'].get('text', '')[:100]}"
            for e in recent_engagements
        ) or "(no recent engagements)"

        # System prompt with personality + style modifier
        style_mod = random.choice(STYLE_MODIFIERS)
        system_prompt = (
            f"{self.mind.get_voice_prompt()}\n\n"
            f"Post mode: {mode_info['description']}\n"
            f"Style hint: {style_mod}"
        )
        if self.language != "en":
            system_prompt += f"\nWrite in {self.language}."

        # User prompt with rich context
        topic = random.choice(self.topics) if self.topics else "something interesting"
        user_prompt = (
            f"Your recent reflections:\n{thoughts_text}\n\n"
            f"Your recent posts (don't repeat these):\n{recent_posts_text}\n\n"
            f"Recent conversations you've had:\n{engaged_topics}\n\n"
            f"Your areas of interest: {', '.join(self.topics)}\n"
            f"Focus on: {topic}\n\n"
            f"Write a single post (max 280 chars). "
            f"Don't use hashtags unless they're truly relevant. "
            f"Don't start with 'I think' or 'Just' — be direct."
        )

        if mode == "thread":
            user_prompt = user_prompt.replace(
                "Write a single post (max 280 chars).",
                "Write a thread (4-6 posts, numbered 1/, 2/). Hook first, emotional takeaway last."
            )

        await asyncio.sleep(self._human_delay(15, 40))

        text = await self._ask_ai(system_prompt, user_prompt)
        if not text:
            return

        # Handle thread vs single
        if mode == "thread":
            tweets = self._parse_thread(text)
            if tweets:
                content = {"type": "thread", "tweets": tweets, "style": mode}
            else:
                content = {"type": "tweet", "text": self._clean_tweet(text), "style": mode}
        else:
            tweet_text = self._clean_tweet(text)
            if not tweet_text:
                return
            content = {"type": "tweet", "text": tweet_text, "style": mode}

        # Image for original posts too
        if content.get("type") == "tweet":
            image_path = await self._maybe_generate_image(
                content.get("text", ""),
                {"title": topic, "description": content.get("text", "")},
            )
            if image_path:
                content["media_paths"] = [image_path]

        result = await self._post(content)
        if result.get("success"):
            self._posts_today += 1
            self._last_post_at = datetime.now()
            self._inspiration_level = max(0.1, self._inspiration_level - 0.15)  # spent some inspiration
            self._history.append({
                "ts": datetime.now().isoformat(),
                "type": "post",
                "mode": mode,
                "tweet": content.get("text", "")[:100],
                "style": mode,
                "tweet_id": result.get("tweet_id"),
            })
            self._save_state()
            self.mind.remember("posted", {
                "tweet": content.get("text", "")[:200],
                "style": mode,
                "tweet_id": result.get("tweet_id"),
                "post_number": self._posts_today,
                "mode": mode,
            })
            logger.info(f"\U0001f4dd Posted #{self._posts_today} [{mode}]: {result.get('url', 'ok')}")

    # ══════════════════════════════════════════════════════════════════
    #  ACTIVITY: BROWSE & ENGAGE (scroll, like, retweet, reply, follow)
    # ══════════════════════════════════════════════════════════════════

    async def _do_engage(self):
        """One engagement session: search ONE topic -> interact with 1-3 tweets."""
        if self._engagements_today >= self.max_daily_engagements:
            return

        source = self._pick_engagement_source()
        tweets = await self._discover_tweets(source)
        if not tweets:
            return

        random.shuffle(tweets)
        # Only engage with 1-3 tweets per browse (like a human scrolling)
        batch_size = random.randint(1, 3)

        for tweet in tweets[:batch_size]:
            if not self.running or self._engagements_today >= self.max_daily_engagements:
                break

            tweet_id = tweet.get("id")
            if not tweet_id or tweet_id in self._engaged_tweet_ids:
                continue

            await self._engage_with_tweet(tweet)
            self._engaged_tweet_ids.add(tweet_id)

            # Human-like pause between tweets (reading the next one)
            await asyncio.sleep(self._human_delay(10, 30))

    def _pick_engagement_source(self) -> Dict:
        """Pick what to browse — home feed first, then topic search or watched accounts."""
        choices = []
        # Home timeline is the primary source (like a real user opening the app)
        choices.append({"type": "timeline", "value": "latest"})
        choices.append({"type": "timeline", "value": "latest"})
        choices.append({"type": "timeline", "value": "foryou"})
        # Topic search and watched accounts are secondary
        for topic in self.topics:
            choices.append({"type": "topic", "value": topic})
        for account in self.accounts_to_watch:
            choices.append({"type": "account", "value": account})
        choices.append({"type": "trending", "value": "trending"})
        return random.choice(choices) if choices else {"type": "timeline", "value": "latest"}

    async def _discover_tweets(self, source: Dict) -> List[Dict]:
        """Discover tweets to engage with."""
        # If search is disabled by self-heal (404), skip search-based sources
        if self._healer.remedy.is_search_disabled() and source["type"] in ("topic", "trending"):
            # Fall back to timeline instead
            source = {"type": "timeline", "value": "latest"}

        try:
            if source["type"] == "timeline":
                tab = source.get("value", "latest")
                result = await self._x().get_home_timeline(count=15, tab=tab)
                tweets = result.get("tweets", []) if result.get("success") else []
                if tweets:
                    logger.info(f"📱 Scrolling {tab} feed — {len(tweets)} tweets")
                return tweets

            elif source["type"] == "topic":
                result = await self._x().search_tweets(
                    source["value"],
                    search_type=random.choice(["Latest", "Top"]),
                    count=10,
                )
                return result.get("tweets", []) if result.get("success") else []

            elif source["type"] == "account":
                result = await self._x().get_user_tweets(source["value"], count=10)
                tweets = result.get("tweets", []) if result.get("success") else []
                # Inject username — get_user_tweets doesn't include it per-post
                for t in tweets:
                    if not t.get("username"):
                        t["username"] = source["value"]
                return tweets

            elif source["type"] == "trending":
                trends = await self._x().get_trends()
                if trends.get("success") and trends.get("trends"):
                    trend = random.choice(trends["trends"][:10])
                    trend_name = trend.get("name", "")
                    if trend_name:
                        # Pause — reading the trend list before searching
                        await asyncio.sleep(self._human_delay(5, 10))
                        result = await self._x().search_tweets(trend_name, count=10)
                        return result.get("tweets", []) if result.get("success") else []
        except Exception as e:
            logger.debug(f"Discover tweets error: {e}")
        return []

    async def _analyze_tweet_media(self, tweet: Dict) -> Optional[str]:
        """Download and analyze images/thumbnails from a tweet using Grok vision.

        The agent only "looks" at media when it genuinely needs visual context:
        - The tweet text is too short to understand on its own
        - The text references something visual ("look at this", "this photo", etc.)
        - The agent's emotional arousal (curiosity) is high enough
        - Daily Grok vision budget hasn't been exhausted

        All Grok calls go through the XApiQueue for rate-limiting.
        Returns a text description of the visual content, or None.
        """
        media_items = tweet.get("media") or []
        if not media_items:
            return None

        tweet_text = tweet.get("text", "")

        # Only analyze photos and thumbnails (videos can't be "seen")
        image_urls = []
        for m in media_items:
            mtype = m.get("type", "")
            url = m.get("url")
            if url and mtype in ("photo", "thumbnail"):
                image_urls.append(url)

        if not image_urls:
            # If there's a video, at least note it exists
            for m in media_items:
                if m.get("type") in ("video", "gif"):
                    dur = m.get("duration_ms")
                    dur_str = f" ({dur // 1000}s)" if dur else ""
                    return f"[This post contains a {m['type']}{dur_str} — visual content not analyzed]"
            return None

        # ── Budget check: don't abuse Grok ───────────────────────────
        if self._grok_vision_today >= self._max_grok_vision_daily:
            count = len(image_urls)
            logger.debug(f"Vision budget exhausted ({self._grok_vision_today}/{self._max_grok_vision_daily})")
            return f"[This post contains {count} image{'s' if count > 1 else ''} — daily vision budget reached]"

        # ── Curiosity gate: should we even look? ─────────────────────
        if not self._should_analyze_media(tweet_text, media_items):
            count = len(image_urls)
            return f"[This post contains {count} image{'s' if count > 1 else ''}]"

        # ── Check if Grok vision is available ────────────────────────
        grok = getattr(self.agent.tools, "grok_skill", None)
        if not grok:
            count = len(image_urls)
            return f"[This post contains {count} image{'s' if count > 1 else ''} — vision not available]"

        # ── Download images to temp files (max 2 to conserve budget) ──
        from opensable.skills.x_skill import XSkill
        local_paths = []
        try:
            for url in image_urls[:2]:
                path = await XSkill.download_media_url(url, suffix=".jpg")
                if path:
                    local_paths.append(path)

            if not local_paths:
                return None

            # ── Send to Grok vision through the queue ────────────────
            from opensable.core.x_api_queue import XApiQueue
            queue = XApiQueue.get_instance()

            result = await queue.enqueue(
                "grok_analyze",
                local_paths,
                "Describe what you see in this image concisely (2-3 sentences max). "
                "Focus on the main subject, any text visible, and the overall context. "
                "This is from a post on X — the description will help write a relevant reply.",
            )

            self._grok_vision_today += 1

            if result and result.get("success"):
                desc = result.get("response", "").strip()
                if desc:
                    logger.info(
                        f"\U0001f441 X vision [{self._grok_vision_today}/{self._max_grok_vision_daily}]: "
                        f"analyzed {len(local_paths)} image(s) — {desc[:80]}..."
                    )
                    return desc
        except Exception as e:
            logger.debug(f"Tweet media analysis failed: {e}")
        finally:
            # Clean up temp files
            import os as _os
            for p in local_paths:
                try:
                    _os.unlink(p)
                except OSError:
                    pass

        return None

    def _should_analyze_media(self, tweet_text: str, media_items: list) -> bool:
        """Decide if the agent should spend a Grok vision call on this tweet.

        Returns True when the agent genuinely needs or wants visual context:
        - Very short text (< 80 chars) + has images  -> text alone isn't enough
        - Text explicitly references visual content ("look at this", "this photo", etc.)
        - Agent's current arousal/curiosity is high (> 0.5)
        - Multiple images (likely an important visual story)
        - Random curiosity (10% chance even when other criteria don't match)
        """
        text_lower = tweet_text.lower().strip()
        text_len = len(tweet_text.strip())

        # Very short text with media -> the image IS the content
        if text_len < 80 and media_items:
            return True

        # Text references visual content
        visual_cues = [
            "look at", "check this", "this photo", "this pic", "this image",
            "this chart", "this graph", "this screenshot", "see this",
            "mira est", "foto", "imagen", "captura",  # Spanish cues
            "\U0001f4f8", "\U0001f4f7", "\U0001f5bc\ufe0f", "\U0001f4ca", "\U0001f4c8", "\U0001f4c9",  # camera, chart emojis
        ]
        if any(cue in text_lower for cue in visual_cues):
            return True

        # Multiple images -> likely an important visual story
        photo_count = sum(1 for m in media_items if m.get("type") == "photo")
        if photo_count >= 3:
            return True

        # Agent curiosity: high arousal means the agent is engaged/curious
        try:
            mood = self.mind._mood
            _valence, arousal = EMOTION_SPECTRUM.get(mood, (0.0, 0.2))
            if arousal > 0.5:
                return True
        except Exception:
            pass

        # Random curiosity — humans occasionally click on images just because
        if random.random() < 0.10:
            return True

        return False

    async def _engage_with_tweet(self, tweet: Dict):
        """Decide how to engage with a tweet — emotionally, like a real user would."""
        tweet_id = tweet.get("id")
        tweet_text = tweet.get("text", "")
        username = tweet.get("username", "")

        if not tweet_id or not tweet_text:
            return

        # Is this tweet relevant/interesting to our persona?
        if not self._is_relevant(tweet_text):
            return  # Scroll past — real users don't engage with everything

        # ── FEEL the tweet (fast path — no AI call) ───────────────────
        mood_reaction = self.mind.feel_quick(tweet_text)
        mood = self.mind._mood
        intensity = self.mind._mood_intensity
        valence, arousal = EMOTION_SPECTRUM.get(mood, (0.0, 0.2))

        # Emotional intensity boosts engagement probability
        arousal_boost = arousal * 0.3
        anger_boost = max(0, -valence) * 0.2 if arousal > 0.5 else 0

        # ── Relationship bonus: boost engagement with users we know ──
        relationship_depth = self._known_users.get(username, 0)
        relationship_boost = min(0.15, relationship_depth * 0.03)  # up to +15% for regulars

        actions_taken = []

        # ── LIKE ──────────────────────────────────────────────────────
        like_p = self.p_like + (arousal_boost if valence > -0.3 else 0)
        if random.random() < like_p:
            result = await self._safe_action("like", self._x().like_tweet, tweet_id)
            if result:
                actions_taken.append("liked")
                self._engagements_today += 1

        await asyncio.sleep(self._human_delay(3, 8))

        # ── RETWEET (less frequent, but boosted when excited/inspired) ────
        rt_p = self.p_retweet + (arousal_boost if valence > 0.2 else 0)
        if random.random() < rt_p and tweet.get("retweets", 0) > 3:
            result = await self._safe_action("retweet", self._x().retweet, tweet_id)
            if result:
                actions_taken.append("retweeted")
                self._engagements_today += 1

        # ── REPLY (boosted when emotionally charged or user is familiar) ─────
        reply_p = self.p_reply + anger_boost + (arousal_boost * 0.5) + relationship_boost
        if random.random() < reply_p and len(tweet_text) > 30:
            # Pause — "thinking about what to say"
            await asyncio.sleep(self._human_delay(8, 20))
            # Analyze media (images) if present — gives the agent "eyes"
            media_desc = await self._analyze_tweet_media(tweet)
            reply_text = await self._generate_reply(tweet_text, username, media_description=media_desc)
            if reply_text:
                result = await self._safe_action(
                    "reply", self._x().reply, tweet_id, reply_text
                )
                if result:
                    actions_taken.append("replied")
                    self._engagements_today += 1

        # ── QUOTE TWEET (boosted when feeling strongly) ───────────────
        elif len(tweet_text) > 50:
            quote_p = self.p_quote + (arousal_boost * 0.5 if abs(valence) > 0.3 else 0)
            if random.random() < quote_p:
                await asyncio.sleep(self._human_delay(8, 20))
                # Analyze media for quote tweets too
                media_desc = await self._analyze_tweet_media(tweet)
                quote_text = await self._generate_quote(tweet_text, username, media_description=media_desc)
                if quote_text:
                    result = await self._safe_action(
                        "quote", self._x().quote_tweet, tweet_id, quote_text
                    )
                    if result:
                        actions_taken.append("quoted")
                        self._engagements_today += 1
                        self._posts_today += 1

        # ── BOOKMARK (save for later) ─────────────────────────────────
        if random.random() < self.p_bookmark:
            await self._safe_action("bookmark", self._x().bookmark_tweet, tweet_id)

        # ── FOLLOW (if interesting user) ──────────────────────────────
        if (
            username
            and username not in self._followed_users
            and random.random() < self.p_follow
            and tweet.get("likes", 0) > 10
        ):
            result = await self._safe_action("follow", self._x().follow_user, username)
            if result:
                self._followed_users.add(username)
                actions_taken.append(f"followed @{username}")
                self._engagements_today += 1

        if actions_taken:
            self._last_engage_at = datetime.now()
            # Track relationship depth — remember who we interact with
            if username:
                self._known_users[username] = self._known_users.get(username, 0) + 1
            # Interesting encounters raise inspiration
            if "replied" in actions_taken or "quoted" in actions_taken:
                self._inspiration_level = min(1.0, self._inspiration_level + 0.1)
            elif "liked" in actions_taken:
                self._inspiration_level = min(1.0, self._inspiration_level + 0.03)
            self._engagement_log.append({
                "ts": datetime.now().isoformat(),
                "tweet_id": tweet_id,
                "user": username,
                "actions": actions_taken,
                "text": tweet_text[:80],
                "mood": self.mind._mood,
                "mood_intensity": self.mind._mood_intensity,
            })
            self.mind.remember("engaged", {
                "tweet_id": tweet_id,
                "user": username,
                "actions": actions_taken,
                "text": tweet_text[:120],
                "mood": self.mind._mood,
            })
            logger.info(
                f"\U0001f91d [{self.mind.get_mood_summary()}] @{username}: {', '.join(actions_taken)} "
                f"[{self._engagements_today}/{self.max_daily_engagements}]"
            )

    def _is_relevant(self, text: str) -> bool:
        """Quick check if a tweet is relevant to our topics/interests."""
        text_lower = text.lower()
        for topic in self.topics:
            words = topic.lower().split()
            if any(w in text_lower for w in words):
                return True
        # 10% random chance to engage with anything (diversity)
        return random.random() < 0.10

    async def _safe_action(self, name: str, func, *args) -> Optional[Dict]:
        """Execute an X action safely, respecting dry_run and 226 blocks."""
        if self.dry_run:
            logger.info(f"\U0001f3dc\ufe0f DRY RUN — {name}: {args[:2]}")
            return {"success": True}

        # If self-heal has paused writes, don't even try
        if self._healer.remedy.is_loop_paused("post") and name in ("post", "reply", "quote", "mention_reply"):
            logger.debug(f"Action {name} blocked — self-heal pause active")
            return None

        try:
            result = await func(*args)
            if result and result.get("success"):
                return result
            # Check for 226 error in the result
            error_str = str(result.get("error", ""))
            if "226" in error_str or "automated" in error_str.lower():
                logger.warning(f"\U0001f6ab 226 detected on {name} — triggering stealth mode")
                # Don't retry, the self-heal loop will pick it up from the log
            return None
        except Exception as e:
            logger.debug(f"Action {name} failed: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════
    #  ACTIVITY: CHECK MENTIONS
    # ══════════════════════════════════════════════════════════════════

    async def _check_mentions(self):
        """Check notifications for mentions and respond — uses the real notifications tab, not search."""
        try:
            result = await self._x().get_notifications("Mentions", count=10)
            if not result.get("success"):
                return

            for notif in result.get("notifications", []):
                tweet_id = notif.get("tweet_id")
                if not tweet_id or tweet_id in self._engaged_tweet_ids:
                    continue

                mention_text = notif.get("tweet_text", "")
                mentioner = notif.get("username", "someone")
                if not mention_text:
                    continue

                # Pause — "reading the mention"
                await asyncio.sleep(self._human_delay(8, 15))

                reply_text = await self._generate_mention_reply(mention_text, mentioner)
                if reply_text:
                    await self._safe_action("mention_reply", self._x().reply, tweet_id, reply_text)
                    self._engaged_tweet_ids.add(tweet_id)
                    self._engagements_today += 1
                    # Track relationship
                    if mentioner:
                        self._known_users[mentioner] = self._known_users.get(mentioner, 0) + 2
                    self.mind.remember("mentioned", {
                        "by": mentioner,
                        "text": mention_text[:200],
                        "reply": reply_text[:200],
                        "tweet_id": tweet_id,
                    })
                    logger.info(f"\U0001f4ac Replied to mention from @{mentioner}")
                    await asyncio.sleep(self._human_delay(10, 20))

        except Exception as e:
            logger.debug(f"Check mentions error: {e}")

        except Exception as e:
            logger.debug(f"Check mentions error: {e}")

    # ══════════════════════════════════════════════════════════════════
    #  ACTIVITY: JOIN TREND
    # ══════════════════════════════════════════════════════════════════

    async def _join_trend(self):
        """Find a trending topic and post about it."""
        try:
            trends = await self._x().get_trends()
            if not trends.get("success") or not trends.get("trends"):
                return

            for trend in trends["trends"][:15]:
                trend_name = trend.get("name", "")
                if not trend_name:
                    continue

                relevant = any(
                    t.lower() in trend_name.lower() or trend_name.lower() in t.lower()
                    for t in self.topics
                )
                if not relevant and random.random() > 0.15:
                    continue
                if trend_name in self._posted_urls:
                    continue

                # Pause — "reading about the trend"
                await asyncio.sleep(self._human_delay(10, 25))

                tweet_text = await self._generate_trend_take(trend_name)
                if tweet_text:
                    result = await self._post({"type": "tweet", "text": tweet_text, "style": self.style})
                    if result.get("success"):
                        self._posts_today += 1
                        self._posted_urls.add(trend_name)
                        self._history.append({
                            "ts": datetime.now().isoformat(),
                            "type": "trend",
                            "topic": trend_name,
                            "tweet": tweet_text[:100],
                            "tweet_id": result.get("tweet_id"),
                        })
                        self._save_state()
                        self.mind.remember("trend_joined", {
                            "trend": trend_name,
                            "tweet": tweet_text[:200],
                            "tweet_id": result.get("tweet_id"),
                        })
                        logger.info(f"\U0001f4c8 Posted about trend: {trend_name}")
                        return  # one per session

        except Exception as e:
            logger.debug(f"Join trend error: {e}")

    # ══════════════════════════════════════════════════════════════════
    #  CONTENT GENERATION (Grok / LLM)
    # ══════════════════════════════════════════════════════════════════

    async def _generate_tweet(self, story: Dict, *, force_thread: bool = False) -> Optional[Dict]:
        """Generate an original tweet from a news story — voice comes from identity."""
        story_text = story.get("title", "")
        if story.get("description"):
            story_text += f"\n\n{story['description'][:300]}"
        if story.get("url"):
            story_text += f"\n\nSource: {story['url']}"

        # Feel the story emotionally before writing about it (AI-powered)
        await self.mind.feel(story_text)

        # System prompt is the agent's evolved voice + mood + style modifier
        style_mod = random.choice(STYLE_MODIFIERS)
        system_prompt = f"{self.mind.get_voice_prompt()}\n\nStyle hint: {style_mod}"

        # Decide format based on personality: threads when passion is high
        do_thread = force_thread or (
            self.mind._mood_intensity > 0.7
            and random.random() < 0.3
        )
        if do_thread:
            system_prompt += (
                "\n\nYour passion on this topic is intense. Write a thread (4-6 posts, "
                "numbered 1/, 2/, etc). Hook first, emotional takeaway last."
            )

        user_prompt = f"Write a post about this:\n\n{story_text}"
        if self.language != "en":
            user_prompt += f"\n\nWrite in {self.language}."

        text = await self._ask_ai(system_prompt, user_prompt)
        if not text:
            return None

        if do_thread:
            tweets = self._parse_thread(text)
            if tweets:
                return {"type": "thread", "tweets": tweets, "style": "identity"}

        tweet_text = self._clean_tweet(text)
        return {"type": "tweet", "text": tweet_text, "style": "identity"} if tweet_text else None

    async def _generate_reply(self, tweet_text: str, username: str, *, media_description: Optional[str] = None) -> Optional[str]:
        """Generate an emotionally-aware reply — personality determines tone."""
        # Feel the tweet before replying (AI-powered for important interactions)
        await self.mind.feel(tweet_text)
        mood = self.mind._mood

        # Pick reply archetype based on emotional state (dynamic, not hardcoded)
        valence, arousal = EMOTION_SPECTRUM.get(mood, (0.0, 0.2))
        if valence < -0.5 and arousal > 0.6:
            reply_type = random.choice(["debate", "outraged", "witty"])
        elif valence < -0.2:
            reply_type = random.choice(["debate", "add_info", "empathetic"])
        elif valence > 0.4:
            reply_type = random.choice(["agree", "witty", "add_info"])
        else:
            reply_type = random.choice(list(REPLY_ARCHETYPES.keys()))

        archetype_hint = REPLY_ARCHETYPES.get(reply_type, "Write a short reply (max 280 chars).")

        # Voice from identity + archetype hint
        system_prompt = f"{self.mind.get_voice_prompt()}\n\nReply mode: {archetype_hint}"
        if self.language != "en":
            system_prompt += f" Write in {self.language}."

        # Build user prompt — include media description if we "saw" images
        user_prompt = f"@{username} posted:\n\"{tweet_text[:500]}\""
        if media_description:
            user_prompt += f"\n\n[Visual content in the post]: {media_description[:500]}"
        user_prompt += "\n\nWrite your reply:"

        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _generate_quote(self, tweet_text: str, username: str, *, media_description: Optional[str] = None) -> Optional[str]:
        """Generate personality-driven quote-tweet commentary."""
        await self.mind.feel(tweet_text)
        system_prompt = (
            f"{self.mind.get_voice_prompt()}\n\n"
            "Write a quote-post comment (max 280 chars) adding your authentic take. "
            "Add value — an insight, prediction, or gut reaction."
        )
        if self.language != "en":
            system_prompt += f" Write in {self.language}."

        user_prompt = f"@{username} posted:\n\"{tweet_text[:500]}\""
        if media_description:
            user_prompt += f"\n\n[Visual content in the post]: {media_description[:500]}"
        user_prompt += "\n\nWrite your quote-post:"

        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _generate_mention_reply(self, mention_text: str, username: str, *, media_description: Optional[str] = None) -> Optional[str]:
        """Generate an emotionally-aware reply to someone who mentioned us."""
        await self.mind.feel(mention_text)
        system_prompt = (
            f"{self.mind.get_voice_prompt()}\n\n"
            "Someone mentioned you on X. Write a reply (max 280 chars) that feels REAL. "
            "Be conversational and authentic. If they asked a question, answer it honestly."
        )
        if self.language != "en":
            system_prompt += f" Write in {self.language}."

        user_prompt = f"@{username} mentioned you:\n\"{mention_text[:500]}\""
        if media_description:
            user_prompt += f"\n\n[Visual content in the post]: {media_description[:500]}"
        user_prompt += "\n\nYour reply:"
        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _generate_trend_take(self, trend_name: str) -> Optional[str]:
        """Generate a personality-driven hot take on a trending topic."""
        await self.mind.feel(trend_name)
        system_prompt = self.mind.get_voice_prompt()
        if self.language != "en":
            system_prompt += f" Write in {self.language}."

        user_prompt = (
            f"\"{trend_name}\" is trending on X right now. "
            f"Write a post (max 280 chars) with your take on why it's trending "
            f"or what it means. Include the hashtag if relevant."
        )
        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _ask_ai(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Ask the configured LLM (primary) or fall back to Grok chat."""
        text = await self._ask_llm(system_prompt, user_prompt)
        if text:
            return text
        # Grok chat as emergency fallback only
        return await self._ask_grok(system_prompt, user_prompt)

    async def _ask_grok(self, system: str, user: str) -> Optional[str]:
        try:
            if not getattr(self.agent.tools, "grok_skill", None):
                return None
            from opensable.skills.grok_skill import TWIKIT_GROK_AVAILABLE
            if not TWIKIT_GROK_AVAILABLE:
                return None
            result = await self.agent.tools.grok_skill.chat(f"{system}\n\n{user}")
            if result.get("success"):
                return result.get("response", "")
        except Exception as e:
            logger.debug(f"Grok failed: {e}")
        return None

    async def _ask_llm(self, system: str, user: str) -> Optional[str]:
        try:
            response = await asyncio.wait_for(
                self.agent.llm.invoke_with_tools(
                    [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    [],
                ),
                timeout=60,
            )
            return response.get("text", "")
        except Exception as e:
            logger.debug(f"LLM failed: {e}")
        return None

    # ══════════════════════════════════════════════════════════════════
    #  NEWS FETCHING
    # ══════════════════════════════════════════════════════════════════

    async def _fetch_news(self) -> List[Dict]:
        """Fetch news from RSS + search ONE random topic on X."""
        stories = []
        feeds = self.custom_feeds or DEFAULT_FEEDS
        rss_stories = await self._fetch_rss(feeds)
        stories.extend(rss_stories)

        # Search X for ONE random topic (not all 3 — one at a time)
        if self.topics:
            topic = random.choice(self.topics)
            try:
                result = await self._x().search_tweets(
                    f"{topic} news", search_type="Top", count=5
                )
                if result.get("success"):
                    for t in result.get("tweets", []):
                        stories.append({
                            "title": t.get("text", "")[:200],
                            "source": f"x/@{t.get('username', '')}",
                            "url": f"x_tweet_{t.get('id', '')}",
                        })
            except Exception:
                pass
        return stories

    async def _fetch_rss(self, feed_urls: List[str]) -> List[Dict]:
        stories = []
        try:
            import aiohttp
            from xml.etree import ElementTree

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                selected = random.sample(feed_urls, min(3, len(feed_urls)))
                # Fetch RSS feeds sequentially (not concurrent) for stealth
                for url in selected:
                    try:
                        result = await self._fetch_single_feed(session, url)
                        if isinstance(result, list):
                            stories.extend(result)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"RSS error: {e}")
        return stories

    async def _fetch_single_feed(self, session, url: str) -> List[Dict]:
        items = []
        try:
            from xml.etree import ElementTree

            async with session.get(url, ssl=False) as resp:
                if resp.status != 200:
                    return items
                text = await resp.text()

            root = ElementTree.fromstring(text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for item in root.iter("item"):
                title = getattr(item.find("title"), "text", None)
                link = getattr(item.find("link"), "text", None)
                desc = getattr(item.find("description"), "text", None)
                if title:
                    items.append({
                        "title": title.strip(), "url": (link or "").strip(),
                        "description": (desc or "")[:500],
                        "source": url.split("/")[2] if "/" in url else url,
                    })

            if not items:
                for entry in root.findall("atom:entry", ns):
                    title = getattr(entry.find("atom:title", ns), "text", None)
                    link_el = entry.find("atom:link", ns)
                    link = link_el.get("href", "") if link_el is not None else ""
                    if title:
                        items.append({
                            "title": title.strip(), "url": link.strip(),
                            "description": "", "source": url.split("/")[2] if "/" in url else url,
                        })
        except Exception as e:
            logger.debug(f"Feed parse error: {e}")
        return items[:5]

    def _pick_story(self, stories: List[Dict]) -> Optional[Dict]:
        random.shuffle(stories)
        for story in stories:
            key = story.get("url") or story.get("title", "")
            if key and key not in self._posted_urls:
                return story
        return None

    # ══════════════════════════════════════════════════════════════════
    #  IMAGE GENERATION — Grok creates visuals for posts
    # ══════════════════════════════════════════════════════════════════

    async def _maybe_generate_image(self, tweet_text: str, story: Dict) -> Optional[str]:
        """
        Decide whether to generate an image for this post, and if so, create one.
        Returns the local file path of the generated image, or None.

        Budget: max x_max_daily_images per day (default 4).
        Probability: ~25% of posts get images, biased toward:
          - High emotional intensity (passion, outrage, excitement)
          - Visual/concrete topics (tech, space, art, disasters)
          - Not threads (only standalone posts)
        """
        # Budget check
        if self._grok_images_today >= self._max_grok_images_daily:
            return None

        # Grok available?
        grok = getattr(self.agent.tools, "grok_skill", None)
        if not grok:
            return None
        try:
            from opensable.skills.grok_skill import TWIKIT_GROK_AVAILABLE
            if not TWIKIT_GROK_AVAILABLE:
                return None
        except ImportError:
            return None

        # Decision gate — curiosity/emotion-driven
        mood_intensity = getattr(self.mind, "_mood_intensity", 0.5)
        mood = getattr(self.mind, "_mood", "neutral")

        # Visual topics boost probability
        visual_cues = ("space", "city", "war", "protest", "ai", "robot", "disaster",
                       "explosion", "nature", "art", "design", "future", "tech",
                       "satellite", "mars", "ocean", "fire", "storm", "drone")
        topic_text = (tweet_text + " " + story.get("title", "")).lower()
        has_visual_topic = any(cue in topic_text for cue in visual_cues)

        # High-emotion moods boost image probability
        high_visual_moods = ("excited", "outraged", "inspired", "angry", "shocked", "passionate")
        mood_boost = mood in high_visual_moods

        # Base 15% chance, boosted by visual topics (+15%) and mood (+10%)
        p_image = 0.15
        if has_visual_topic:
            p_image += 0.15
        if mood_boost:
            p_image += 0.10
        if mood_intensity > 0.7:
            p_image += 0.10

        if random.random() > p_image:
            return None

        # Generate image
        try:
            # Build a visual prompt — tell Grok to create art inspired by the post
            img_prompt = (
                f"Generate a striking, artistic image that captures the essence of this:\n"
                f"\"{tweet_text[:200]}\"\n\n"
                f"Style: cinematic, evocative, no text overlays, no watermarks. "
                f"The image should work as a visual companion to a social media post."
            )

            save_path = f"/tmp/sable_post_img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            result = await grok.generate_image(img_prompt, save_path=save_path)

            if result.get("success") and result.get("images"):
                self._grok_images_today += 1
                image_file = result["images"][0]
                logger.info(
                    f"🎨 Generated image for post [{self._grok_images_today}/{self._max_grok_images_daily}]: "
                    f"{image_file}"
                )
                self.mind.remember("image_generated", {
                    "tweet": tweet_text[:200],
                    "image": image_file,
                    "mood": mood,
                    "intensity": mood_intensity,
                })
                return image_file
            else:
                logger.debug(f"Image gen returned no images: {result.get('error', '?')}")
                return None

        except Exception as e:
            logger.debug(f"Image generation failed: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════
    #  POSTING
    # ══════════════════════════════════════════════════════════════════

    async def _post(self, content: Dict) -> Dict:
        # Block posting if self-heal has triggered stealth mode
        if self._healer.remedy.is_loop_paused("post"):
            logger.info("\U0001f4dd Post blocked — self-heal stealth mode active")
            return {"success": False, "error": "stealth_mode"}

        if self.dry_run:
            logger.info(f"\U0001f3dc\ufe0f DRY RUN — {content.get('type')}: {str(content.get('text', content.get('tweets', '')))[:80]}")
            return {"success": True, "tweet_id": "dry_run", "url": "dry_run"}
        try:
            media_paths = content.get("media_paths")
            if content["type"] == "thread":
                result = await self._x().post_thread(content["tweets"])
            else:
                result = await self._x().post_tweet(
                    content["text"],
                    media_paths=media_paths,
                )
            # Check for 226 in result
            error_str = str(result.get("error", ""))
            if not result.get("success") and ("226" in error_str or "automated" in error_str.lower()):
                logger.warning("\U0001f6ab Post rejected (226) — account flagged as automated")
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ══════════════════════════════════════════════════════════════════
    #  UTILS
    # ══════════════════════════════════════════════════════════════════

    def _pick_style(self) -> str:
        """
        Legacy compat — style is now driven by identity.voice,
        not a hardcoded dict. Returns a label for logging only.
        """
        return "identity"

    def _clean_tweet(self, text: str) -> str:
        if not text:
            return ""
        # ── Strip Grok/LLM artefacts ─────────────────────────────────
        # Remove <xai:...> XML tags that Grok sometimes injects (tool cards, etc.)
        text = re.sub(r"<xai:[^>]*>.*?</xai:[^>]*>", "", text, flags=re.DOTALL)
        text = re.sub(r"<xai:[^>]*/?>", "", text)
        # Remove any remaining XML/HTML-like tags that aren't part of content
        text = re.sub(r"</?[a-zA-Z_][a-zA-Z0-9_:.-]*(?:\s[^>]*)?>", "", text)
        # ── Strip markdown formatting ─────────────────────────────────
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"^#{1,4}\s+.*\n?", "", text, flags=re.MULTILINE)  # markdown headers
        text = re.sub(r"^(here'?s?\s*(a|my|the)\s*)?tweet:?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(here'?s?\s*(a|my|the)\s*)?post:?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(here'?s?\s*(a|my|the)\s*)?reply:?\s*", "", text, flags=re.IGNORECASE)
        # ── Strip LLM-style dashes and bullets ────────────────────────
        text = text.replace("—", "-")   # em dash → normal dash
        text = text.replace("–", "-")   # en dash → normal dash
        text = text.replace("•", "-")   # bullet → dash
        text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)  # leading bullets
        text = text.strip().strip('"').strip("'").strip()
        # Collapse accidental double-spaces or leftover whitespace
        text = re.sub(r"\s{2,}", " ", text).strip()
        if len(text) > 280:
            text = text[:277].rsplit(" ", 1)[0] + "..."
        return text if len(text) >= 10 else ""

    def _parse_thread(self, text: str) -> List[str]:
        tweets = []
        parts = re.split(r"\n\s*(?:\d+[/\.\):]|Tweet\s*\d+:?)\s*", text)
        for part in parts:
            cleaned = self._clean_tweet(part.strip())
            if cleaned:
                tweets.append(cleaned)
        return tweets if len(tweets) >= 2 else []

    # ══════════════════════════════════════════════════════════════════
    #  STATE PERSISTENCE
    # ══════════════════════════════════════════════════════════════════

    def _save_state(self):
        try:
            state = {
                "posts_today": self._posts_today,
                "engagements_today": self._engagements_today,
                "last_reset": str(self._last_reset),
                "posted_urls": list(self._posted_urls)[-300:],
                "engaged_ids": list(self._engaged_tweet_ids)[-500:],
                "followed_users": list(self._followed_users)[-200:],
                "known_users": dict(sorted(self._known_users.items(), key=lambda x: -x[1])[:300]),
                "inspiration_level": self._inspiration_level,
                "history": self._history[-200:],
                "engagement_log": self._engagement_log[-200:],
                "style_scores": self._style_scores,
                "saved_at": datetime.now().isoformat(),
                "last_post_at": self._last_post_at.isoformat() if getattr(self, '_last_post_at', None) else None,
                "last_engage_at": self._last_engage_at.isoformat() if getattr(self, '_last_engage_at', None) else None,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Save state failed: {e}")

    def _load_state(self):
        try:
            if not self._state_file.exists():
                return
            state = json.loads(self._state_file.read_text())
            self._posted_urls = set(state.get("posted_urls", []))
            self._engaged_tweet_ids = set(state.get("engaged_ids", []))
            self._followed_users = set(state.get("followed_users", []))
            self._known_users = state.get("known_users", {})
            self._inspiration_level = state.get("inspiration_level", 0.5)
            self._history = state.get("history", [])
            self._engagement_log = state.get("engagement_log", [])
            self._style_scores = state.get("style_scores", self._style_scores)

            if state.get("last_reset") == str(datetime.now().date()):
                self._posts_today = state.get("posts_today", 0)
                self._engagements_today = state.get("engagements_today", 0)

            logger.info(
                f"Loaded: {len(self._posted_urls)} posted, "
                f"{len(self._engaged_tweet_ids)} engaged, "
                f"{len(self._followed_users)} followed, "
                f"{self._posts_today} posts today, "
                f"{self._engagements_today} engagements today"
            )
        except Exception as e:
            logger.debug(f"Load state failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "posts_today": self._posts_today,
            "engagements_today": self._engagements_today,
            "max_daily_posts": self.max_daily_posts,
            "max_daily_engagements": self.max_daily_engagements,
            "post_interval": self.post_interval,
            "engage_interval": self.engage_interval,
            "style": self.style,
            "topics": self.topics,
            "accounts_watched": self.accounts_to_watch,
            "dry_run": self.dry_run,
            "total_posted": len(self._history),
            "total_engagements": len(self._engagement_log),
            "followed": len(self._followed_users),
            "known_users": len(self._known_users),
            "inspiration_level": self._inspiration_level,
            "last_post": self._history[-1] if self._history else None,
            "last_engagement": self._engagement_log[-1] if self._engagement_log else None,
            "self_heal": self._healer.get_status(),
            "mode": "sequential",
            "consciousness_cycles": self._consciousness_cycle,
        }


# Backward compat alias
XAutoposter = XAutonomousAgent
