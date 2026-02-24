"""
X Autonomous Agent — Full human-like behavior on X (Twitter).

NOT just an autoposter. This agent acts like a REAL USER:
  - Scrolls timeline and engages (like, retweet, bookmark)
  - Replies to interesting tweets with smart takes
  - Quote-tweets with commentary
  - Follows relevant accounts and builds network
  - Responds to mentions and DMs
  - Posts original content from news/trends
  - Posts threads on deep topics
  - Tracks trending topics and joins conversations
  - Learns what works and adapts behavior over time

All powered by twikit (free, no API keys) + Grok/LLM for intelligence.

Config (.env):
    X_USERNAME, X_EMAIL, X_PASSWORD   — X account credentials
    X_ENABLED=true                    — enable X integration
    X_AUTOPOSTER_ENABLED=true         — activate autonomous agent
    X_POST_INTERVAL=1800              — seconds between original posts
    X_ENGAGE_INTERVAL=300             — seconds between engagement sessions
    X_TOPICS=geopolitics,tech,ai      — topics of interest
    X_LANGUAGE=en                     — tweet language
    X_STYLE=analyst                   — personality: analyst, meme, news, thread
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
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensable.core.x_consciousness import EMOTIONS, EMOTION_SPECTRUM

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


class XAutonomousAgent:
    """
    Full autonomous X agent — behaves like a real human user.

    Runs multiple concurrent loops:
    - Post loop: original tweets from news/trends
    - Engage loop: scroll, like, retweet, reply, follow
    - Mention loop: respond to mentions and DMs
    - Trend loop: join trending conversations
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
        self._last_reset = datetime.now().date()
        self._posted_urls: set = set()
        self._engaged_tweet_ids: set = set()
        self._followed_users: set = set()
        self._history: List[Dict] = []
        self._engagement_log: List[Dict] = []
        self._state_file = Path("data/x_agent_state.json")
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._style_scores: Dict[str, List[float]] = {}

        # ── Consciousness (memory + reflection + evolution) ───────
        from opensable.core.x_consciousness import XConsciousness
        self.mind = XConsciousness(agent, config)

    # ══════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ══════════════════════════════════════════════════════════════════

    async def start(self):
        """Start all agent loops concurrently."""
        self.running = True
        self._load_state()

        # Compute resume context
        self._last_post_at = self._parse_last_ts(self._history)
        self._last_engage_at = self._parse_last_ts(self._engagement_log)
        mem_stats = self.mind.get_memory_stats()
        logger.info(
            f"🐦 X Agent starting | post every {self.post_interval}s | "
            f"engage every {self.engage_interval}s | style={self.style} | "
            f"dry_run={self.dry_run} | memories={mem_stats.get('total_memories', 0)} | "
            f"last_post={self._last_post_at or 'never'}"
        )

        # Internal thought (NOT a tweet) — summarize what we remember
        since_post = self._seconds_since(self._last_post_at)
        since_engage = self._seconds_since(self._last_engage_at)
        await self.mind.think(
            f"Booting up. I have {mem_stats.get('total_memories', 0)} memories, "
            f"{mem_stats.get('reflections', 0)} reflections, "
            f"{mem_stats.get('evolutions', 0)} evolutions. "
            f"Last post was {self._fmt_ago(since_post)}. "
            f"Last engagement was {self._fmt_ago(since_engage)}. "
            f"Posts today so far: {self._posts_today}/{self.max_daily_posts}. "
            f"Resuming where I left off."
        )

        # Launch all behavior loops in parallel (including consciousness)
        await asyncio.gather(
            self._post_loop(),
            self._engage_loop(),
            self._mention_loop(),
            self._trend_loop(),
            self._consciousness_loop(),
            return_exceptions=True,
        )

    async def stop(self):
        """Stop the agent."""
        self.running = False
        self._save_state()
        # Internal thought (NOT a tweet) — just a note to self
        await self.mind.think(
            f"Shutting down. {self._posts_today} posts, {self._engagements_today} engagements today. "
            f"Saving state. I'll remember everything when I wake up."
        )
        logger.info("🐦 X Agent stopped")

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

    def _calc_resume_delay(self, last_at: Optional[datetime], interval: float) -> float:
        """
        Calculate smart initial delay for a loop based on when the last action happened.
        If it was recent, wait the remaining interval. If old or never, use a short warm-up.
        """
        if last_at is None:
            # First run ever — short warm-up
            return random.uniform(30, 120)

        elapsed = (datetime.now() - last_at).total_seconds()
        remaining = interval - elapsed

        if remaining > 0:
            # Last action was recent, respect the remaining interval (+ small jitter)
            return remaining + random.uniform(5, 30)
        else:
            # Overdue — start after a human-like warm-up, not instantly
            return random.uniform(15, 90)

    def _reset_daily_counters(self):
        today = datetime.now().date()
        if today != self._last_reset:
            self._posts_today = 0
            self._engagements_today = 0
            self._last_reset = today

    def _x(self):
        """Shortcut to XSkill."""
        return self.agent.tools.x_skill

    def _human_delay(self, base: float = 2.0, variance: float = 3.0):
        """Random delay to look human."""
        return base + random.uniform(0, variance)

    # ══════════════════════════════════════════════════════════════════
    #  LOOP 1: ORIGINAL POSTS (news + opinion)
    # ══════════════════════════════════════════════════════════════════

    async def _post_loop(self):
        """Periodically post original tweets from news/trends."""
        initial_wait = self._calc_resume_delay(self._last_post_at, self.post_interval)
        logger.info(f"📝 Post loop: first post in {initial_wait:.0f}s")
        await asyncio.sleep(initial_wait)

        while self.running:
            try:
                self._reset_daily_counters()
                if self._posts_today < self.max_daily_posts:
                    await self._do_post()
            except Exception as e:
                logger.error(f"Post loop error: {e}")

            jitter = self.post_interval * random.uniform(-0.15, 0.15)
            await asyncio.sleep(max(60, self.post_interval + jitter))

    async def _do_post(self):
        """One posting cycle: fetch news → generate → post."""
        stories = await self._fetch_news()
        story = self._pick_story(stories) if stories else None
        if not story:
            return

        content = await self._generate_tweet(story)
        if not content:
            return

        result = await self._post(content)
        if result.get("success"):
            self._posts_today += 1
            self._last_post_at = datetime.now()
            self._posted_urls.add(story.get("url", story.get("title", "")))
            self._history.append({
                "ts": datetime.now().isoformat(),
                "type": "post",
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
            })
            logger.info(f"📝 Posted #{self._posts_today}: {result.get('url', 'ok')}")

    # ══════════════════════════════════════════════════════════════════
    #  LOOP 2: ENGAGEMENT (scroll, like, retweet, reply, follow)
    # ══════════════════════════════════════════════════════════════════

    async def _engage_loop(self):
        """Periodically browse timeline and engage like a human."""
        initial_wait = self._calc_resume_delay(self._last_engage_at, self.engage_interval)
        logger.info(f"🤝 Engage loop: first engage in {initial_wait:.0f}s")
        await asyncio.sleep(initial_wait)

        while self.running:
            try:
                self._reset_daily_counters()
                if self._engagements_today < self.max_daily_engagements:
                    await self._do_engage()
            except Exception as e:
                logger.error(f"Engage loop error: {e}")

            jitter = self.engage_interval * random.uniform(-0.2, 0.2)
            await asyncio.sleep(max(30, self.engage_interval + jitter))

    async def _do_engage(self):
        """One engagement session: search topics → interact with tweets."""
        source = self._pick_engagement_source()
        tweets = await self._discover_tweets(source)
        if not tweets:
            return

        random.shuffle(tweets)
        batch_size = random.randint(3, 8)

        for tweet in tweets[:batch_size]:
            if not self.running or self._engagements_today >= self.max_daily_engagements:
                break

            tweet_id = tweet.get("id")
            if not tweet_id or tweet_id in self._engaged_tweet_ids:
                continue

            await self._engage_with_tweet(tweet)
            self._engaged_tweet_ids.add(tweet_id)

            # Human-like pause between actions
            await asyncio.sleep(self._human_delay(3, 8))

    def _pick_engagement_source(self) -> Dict:
        """Pick what to browse — topic search, watched account, or trends."""
        choices = []
        for topic in self.topics:
            choices.append({"type": "topic", "value": topic})
        for account in self.accounts_to_watch:
            choices.append({"type": "account", "value": account})
        choices.append({"type": "trending", "value": "trending"})
        return random.choice(choices) if choices else {"type": "topic", "value": "news"}

    async def _discover_tweets(self, source: Dict) -> List[Dict]:
        """Discover tweets to engage with."""
        try:
            if source["type"] == "topic":
                result = await self._x().search_tweets(
                    source["value"],
                    search_type=random.choice(["Latest", "Top"]),
                    count=15,
                )
                return result.get("tweets", []) if result.get("success") else []

            elif source["type"] == "account":
                result = await self._x().get_user_tweets(source["value"], count=10)
                return result.get("tweets", []) if result.get("success") else []

            elif source["type"] == "trending":
                trends = await self._x().get_trends()
                if trends.get("success") and trends.get("trends"):
                    trend = random.choice(trends["trends"][:10])
                    trend_name = trend.get("name", "")
                    if trend_name:
                        result = await self._x().search_tweets(trend_name, count=10)
                        return result.get("tweets", []) if result.get("success") else []
        except Exception as e:
            logger.debug(f"Discover tweets error: {e}")
        return []

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
        # High arousal = more likely to engage (like a human who can't scroll past)
        arousal_boost = arousal * 0.3
        # Strong negative valence boosts reply urge (humans argue when upset)
        anger_boost = max(0, -valence) * 0.2 if arousal > 0.5 else 0

        actions_taken = []

        # ── LIKE ──────────────────────────────────────────────────────
        like_p = self.p_like + (arousal_boost if valence > -0.3 else 0)
        if random.random() < like_p:
            result = await self._safe_action("like", self._x().like_tweet, tweet_id)
            if result:
                actions_taken.append("liked")
                self._engagements_today += 1

        await asyncio.sleep(self._human_delay(1, 2))

        # ── RETWEET (less frequent, but boosted when excited/inspired) ────
        rt_p = self.p_retweet + (arousal_boost if valence > 0.2 else 0)
        if random.random() < rt_p and tweet.get("retweets", 0) > 3:
            result = await self._safe_action("retweet", self._x().retweet, tweet_id)
            if result:
                actions_taken.append("retweeted")
                self._engagements_today += 1

        # ── REPLY (boosted when emotionally charged — humans can't shut up when they feel) ──
        reply_p = self.p_reply + anger_boost + (arousal_boost * 0.5)
        if random.random() < reply_p and len(tweet_text) > 30:
            reply_text = await self._generate_reply(tweet_text, username)
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
                quote_text = await self._generate_quote(tweet_text, username)
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
                f"🤝 [{self.mind.get_mood_summary()}] Engaged with @{username}: {', '.join(actions_taken)} "
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
        """Execute an X action safely, respecting dry_run."""
        if self.dry_run:
            logger.info(f"🏜️ DRY RUN — {name}: {args[:2]}")
            return {"success": True}
        try:
            result = await func(*args)
            return result if result and result.get("success") else None
        except Exception as e:
            logger.debug(f"Action {name} failed: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════
    #  LOOP 3: MENTIONS & DM RESPONDER
    # ══════════════════════════════════════════════════════════════════

    async def _mention_loop(self):
        """Check for mentions/replies and respond."""
        await asyncio.sleep(random.uniform(60, 180))  # mentions don't need resume logic

        while self.running:
            try:
                self._reset_daily_counters()
                await self._check_mentions()
            except Exception as e:
                logger.debug(f"Mention loop error: {e}")

            # Check mentions every 5-10 minutes
            await asyncio.sleep(random.uniform(300, 600))

    async def _check_mentions(self):
        """Search for mentions of our account and respond."""
        username = getattr(self.config, "x_username", None)
        if not username:
            return

        try:
            result = await self._x().search_tweets(
                f"@{username}", search_type="Latest", count=5
            )
            if not result.get("success"):
                return

            for tweet in result.get("tweets", []):
                tweet_id = tweet.get("id")
                if not tweet_id or tweet_id in self._engaged_tweet_ids:
                    continue

                mention_text = tweet.get("text", "")
                mentioner = tweet.get("username", "someone")

                reply_text = await self._generate_mention_reply(mention_text, mentioner)
                if reply_text:
                    await self._safe_action("mention_reply", self._x().reply, tweet_id, reply_text)
                    self._engaged_tweet_ids.add(tweet_id)
                    self._engagements_today += 1
                    self.mind.remember("mentioned", {
                        "by": mentioner,
                        "text": mention_text[:200],
                        "reply": reply_text[:200],
                        "tweet_id": tweet_id,
                    })
                    logger.info(f"💬 Replied to mention from @{mentioner}")
                    await asyncio.sleep(self._human_delay(5, 10))

        except Exception as e:
            logger.debug(f"Check mentions error: {e}")

    # ══════════════════════════════════════════════════════════════════
    #  LOOP 4: TRENDING TOPICS (join conversations)
    # ══════════════════════════════════════════════════════════════════

    async def _trend_loop(self):
        """Join trending conversations periodically."""
        # Detect last trend post for smart resume
        last_trend = None
        for entry in reversed(self._history):
            if entry.get("type") in ("trend", "trend_post"):
                last_trend = self._parse_last_ts([entry])
                break
        trend_wait = self._calc_resume_delay(last_trend, 1800)
        logger.info(f"📈 Trend loop: first check in {trend_wait:.0f}s")
        await asyncio.sleep(trend_wait)

        while self.running:
            try:
                self._reset_daily_counters()
                if self._posts_today < self.max_daily_posts:
                    await self._join_trend()
            except Exception as e:
                logger.debug(f"Trend loop error: {e}")

            # Check trends every 30-60 min
            await asyncio.sleep(random.uniform(1800, 3600))

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
                        logger.info(f"📈 Posted about trend: {trend_name}")
                        return  # one per cycle

        except Exception as e:
            logger.debug(f"Join trend error: {e}")

    # ════════════════════════════════════════════════════════════════
    #  LOOP 5: CONSCIOUSNESS (think, reflect, evolve)
    # ════════════════════════════════════════════════════════════════

    async def _consciousness_loop(self):
        """Periodic introspection: think, reflect, and self-evolve."""
        await asyncio.sleep(random.uniform(120, 300))  # let other loops warm up

        cycle = 0
        while self.running:
            cycle += 1
            try:
                # ── THINK: Inner monologue every cycle (~15-30 min) ───
                stats = self.mind.get_memory_stats()
                situation = (
                    f"Cycle #{cycle}. "
                    f"Posts today: {self._posts_today}/{self.max_daily_posts}. "
                    f"Engagements today: {self._engagements_today}/{self.max_daily_engagements}. "
                    f"Total memories: {stats.get('total_memories', 0)}. "
                    f"Current mood: {self.mind._mood} (intensity {self.mind._mood_intensity:.1f}). "
                    f"Style: {self.style}. Topics: {self.topics[:5]}."
                )
                await self.mind.think(situation)

                # ── REFLECT: Deep analysis every 3 cycles (~1-1.5 hr) ──
                if cycle % 3 == 0:
                    await self.mind.reflect()

                # ── EVOLVE: Self-modify every 6 cycles (~2-3 hr) ────
                if cycle % 6 == 0:
                    changes = await self.mind.evolve(self)
                    if changes:
                        await self.mind.think(
                            f"Just evolved. Changes: {json.dumps({k: v for k, v in changes.items() if k != 'reasoning'}, default=str)[:200]}. "
                            f"Reason: {changes.get('reasoning', '?')[:200]}"
                        )

            except Exception as e:
                logger.error(f"Consciousness loop error: {e}")
                self.mind.remember("error", {"loop": "consciousness", "error": str(e)[:300]})

            # Think every 15-30 min
            await asyncio.sleep(random.uniform(900, 1800))

    # ══════════════════════════════════════════════════════════════════
    #  CONTENT GENERATION (Grok / LLM)
    # ══════════════════════════════════════════════════════════════════

    async def _generate_tweet(self, story: Dict) -> Optional[Dict]:
        """Generate an original tweet from a news story — voice comes from identity."""
        story_text = story.get("title", "")
        if story.get("description"):
            story_text += f"\n\n{story['description'][:300]}"
        if story.get("url"):
            story_text += f"\n\nSource: {story['url']}"

        # Feel the story emotionally before writing about it (AI-powered)
        await self.mind.feel(story_text)

        # System prompt is the agent's evolved voice + mood
        system_prompt = self.mind.get_voice_prompt()

        # Decide format based on personality: threads when passion is high
        do_thread = (
            self.mind._mood_intensity > 0.7
            and random.random() < 0.3
        )
        if do_thread:
            system_prompt += (
                "\n\nYour passion on this topic is intense. Write a thread (4-6 tweets, "
                "numbered 1/, 2/, etc). Hook first, emotional takeaway last."
            )

        user_prompt = f"Write a tweet about this:\n\n{story_text}"
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

    async def _generate_reply(self, tweet_text: str, username: str) -> Optional[str]:
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

        user_prompt = f"@{username} tweeted:\n\"{tweet_text[:500]}\"\n\nWrite your reply:"
        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _generate_quote(self, tweet_text: str, username: str) -> Optional[str]:
        """Generate personality-driven quote-tweet commentary."""
        await self.mind.feel(tweet_text)
        system_prompt = (
            f"{self.mind.get_voice_prompt()}\n\n"
            "Write a quote-tweet comment (max 280 chars) adding your authentic take. "
            "Add value — an insight, prediction, or gut reaction."
        )
        if self.language != "en":
            system_prompt += f" Write in {self.language}."

        user_prompt = f"@{username} tweeted:\n\"{tweet_text[:500]}\"\n\nWrite your quote-tweet:"
        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _generate_mention_reply(self, mention_text: str, username: str) -> Optional[str]:
        """Generate an emotionally-aware reply to someone who mentioned us."""
        await self.mind.feel(mention_text)
        system_prompt = (
            f"{self.mind.get_voice_prompt()}\n\n"
            "Someone mentioned you on X. Write a reply (max 280 chars) that feels REAL. "
            "Be conversational and authentic. If they asked a question, answer it honestly."
        )
        if self.language != "en":
            system_prompt += f" Write in {self.language}."

        user_prompt = f"@{username} mentioned you:\n\"{mention_text[:500]}\"\n\nYour reply:"
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
            f"Write a tweet (max 280 chars) with your take on why it's trending "
            f"or what it means. Include the hashtag if relevant."
        )
        text = await self._ask_ai(system_prompt, user_prompt)
        return self._clean_tweet(text) if text else None

    async def _ask_ai(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Ask Grok (free) or LLM for text generation."""
        text = await self._ask_grok(system_prompt, user_prompt)
        if text:
            return text
        return await self._ask_llm(system_prompt, user_prompt)

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
        stories = []
        feeds = self.custom_feeds or DEFAULT_FEEDS
        rss_stories = await self._fetch_rss(feeds)
        stories.extend(rss_stories)

        # Also search X itself for news (what a human would do)
        for topic in self.topics[:3]:
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
                selected = random.sample(feed_urls, min(5, len(feed_urls)))
                tasks = [self._fetch_single_feed(session, url) for url in selected]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, list):
                        stories.extend(result)
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
    #  POSTING
    # ══════════════════════════════════════════════════════════════════

    async def _post(self, content: Dict) -> Dict:
        if self.dry_run:
            logger.info(f"🏜️ DRY RUN — {content.get('type')}: {str(content.get('text', content.get('tweets', '')))[:80]}")
            return {"success": True, "tweet_id": "dry_run", "url": "dry_run"}
        try:
            if content["type"] == "thread":
                return await self._x().post_thread(content["tweets"])
            else:
                return await self._x().post_tweet(content["text"])
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
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"^(here'?s?\s*(a|my|the)\s*)?tweet:?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(here'?s?\s*(a|my|the)\s*)?reply:?\s*", "", text, flags=re.IGNORECASE)
        text = text.strip().strip('"').strip("'").strip()
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
            "last_post": self._history[-1] if self._history else None,
            "last_engagement": self._engagement_log[-1] if self._engagement_log else None,
        }


# Backward compat alias
XAutoposter = XAutonomousAgent
