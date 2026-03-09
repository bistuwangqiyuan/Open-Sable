"""
Instagram Autonomous Content Creator — Genelia v2 + Guardian Shield.

Periodically generates AI art via Genelia, scans with Guardian,
and publishes safe images to Instagram with LLM-generated captions.

Behavior:
  1. Every IG_POST_INTERVAL seconds (default: 3600 = 1 hour), wakes up
  2. Uses the LLM to brainstorm a creative image concept
  3. Generates the image via Genelia v2 (portrait 832×1216 for IG)
  4. Guardian scans for explicit content — blocks if unsafe
  5. LLM writes an engaging IG caption with hashtags
  6. Publishes to Instagram
  7. Sleeps until next cycle

Config (.env):
    IG_AUTOPOSTER_ENABLED=true       — activate autonomous IG posting
    IG_POST_INTERVAL=3600            — seconds between posts (default 1h)
    IG_MAX_DAILY_POSTS=8             — max posts per day
    IG_TOPICS=art,surrealism,digital art,cyberpunk,nature,fantasy
    IG_STYLE=cinematic               — visual style preference
    IG_LANGUAGE=en                   — caption language
    IG_DRY_RUN=false                 — if true, generates but doesn't post
    GENELIA_V2_URL=http://192.168.68.24:8001
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_POST_INTERVAL = 3600       # 1 hour
DEFAULT_MAX_DAILY = 8
DEFAULT_TOPICS = [
    "cinematic landscapes", "surreal dreamscapes", "cyberpunk cities",
    "fantasy worlds", "abstract art", "nature photography",
    "futuristic architecture", "cosmic scenes", "ethereal portraits",
    "underwater worlds", "steampunk", "minimalist design",
    "neon noir", "post-apocalyptic", "magical realism",
]
DEFAULT_STYLE = "cinematic, highly detailed, professional photography, 8k"

# Portrait dimensions optimized for Instagram feed
IG_WIDTH = 832
IG_HEIGHT = 1216

# Image quality settings
IG_STEPS = 12
IG_SHARPNESS = 1.4
IG_CONTRAST = 1.2


class IGAutoposter:
    """Autonomous Instagram content creator using Genelia v2 image generation."""

    def __init__(self, agent: Any, config: Any):
        self.agent = agent
        self.config = config
        self.running = False
        self._task: Optional[asyncio.Task] = None

        # Config from env
        self.post_interval = int(os.getenv("IG_POST_INTERVAL", str(DEFAULT_POST_INTERVAL)))
        self.max_daily = int(os.getenv("IG_MAX_DAILY_POSTS", str(DEFAULT_MAX_DAILY)))
        self.dry_run = os.getenv("IG_DRY_RUN", "false").lower() in ("true", "1", "yes")
        self.language = os.getenv("IG_LANGUAGE", "en")
        self.style = os.getenv("IG_STYLE", DEFAULT_STYLE)

        topics_env = os.getenv("IG_TOPICS", "")
        if topics_env:
            self.topics = [t.strip() for t in topics_env.split(",") if t.strip()]
        else:
            self.topics = DEFAULT_TOPICS

        # Stats
        self._posts_today = 0
        self._today = date.today()
        self._total_posted = 0
        self._total_blocked = 0
        self._last_post_time: Optional[datetime] = None
        self._history: List[Dict] = []
        self._ig_suspended = False  # True when IG session is dead

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        """Start the autonomous IG posting loop."""
        # Wait for skills to be ready
        await asyncio.sleep(random.uniform(30, 60))

        # Pre-flight: verify Instagram skill is available and initialized
        ig_skill = self._get_instagram_skill()
        if not ig_skill and not self.dry_run:
            # Check if credentials exist at all
            ig_user = os.getenv("INSTAGRAM_USERNAME", "").strip()
            ig_pass = os.getenv("INSTAGRAM_PASSWORD", "").strip()
            if not ig_user or not ig_pass:
                logger.info("📸 IG Autoposter: No Instagram credentials configured — disabled")
                return
            logger.warning("📸 IG Autoposter: Instagram skill not ready — will retry")

        if not self._get_genelia_skill():
            logger.info("📸 IG Autoposter: Genelia skill not available — disabled")
            return

        self.running = True
        logger.info(
            f"📸 IG Autoposter started — interval={self.post_interval}s, "
            f"max_daily={self.max_daily}, topics={len(self.topics)}, "
            f"dry_run={self.dry_run}"
        )

        while self.running:
            try:
                # Reset daily counter
                if date.today() != self._today:
                    self._posts_today = 0
                    self._today = date.today()

                # Check daily limit
                if self._posts_today >= self.max_daily:
                    logger.info(f"📸 IG daily limit reached ({self.max_daily}). Sleeping until tomorrow.")
                    # Sleep until midnight + some jitter
                    now = datetime.now()
                    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
                    sleep_secs = (tomorrow - now).total_seconds() + random.uniform(60, 300)
                    await asyncio.sleep(sleep_secs)
                    continue

                # Run one post cycle
                await self._post_cycle()

                # Sleep with jitter (±20% of interval)
                jitter = self.post_interval * random.uniform(-0.2, 0.2)
                sleep_time = max(60, self.post_interval + jitter)
                logger.info(f"📸 IG next post in {sleep_time/60:.0f}min")
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"📸 IG Autoposter error: {e}", exc_info=True)
                await asyncio.sleep(300)  # 5 min cooldown on error

        logger.info("📸 IG Autoposter stopped")

    async def stop(self):
        """Stop the autoposter."""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()

    # ── Core Post Cycle ───────────────────────────────────────────────────────

    async def _post_cycle(self):
        """Generate an image and post it to Instagram."""

        # Get skill references
        genelia = self._get_genelia_skill()
        ig_skill = self._get_instagram_skill()

        if not genelia:
            logger.warning("📸 IG Autoposter: Genelia skill not available — skipping")
            return

        # ── Pre-flight: verify IG session BEFORE generating ──
        if not self.dry_run:
            if not ig_skill:
                logger.warning("📸 IG Autoposter: Instagram skill not available — skipping")
                return
            if not getattr(ig_skill, "_initialized", False):
                logger.info("📸 IG Autoposter: Instagram skill not initialized — attempting init...")
                try:
                    ok = await ig_skill.initialize()
                    if not ok:
                        logger.warning(
                            "📸 IG Autoposter: Instagram init failed (challenge?) — "
                            "NOT generating images to avoid waste"
                        )
                        self._ig_suspended = True
                        return
                except Exception as e:
                    logger.error(f"📸 IG Autoposter: Instagram init failed: {e}")
                    self._ig_suspended = True
                    return
            self._ig_suspended = False

        # Step 1: Generate creative concept via LLM (emotion-driven)
        concept = await self._brainstorm_concept()
        if not concept:
            logger.warning("📸 IG Autoposter: Failed to brainstorm concept")
            return

        prompt = concept.get("prompt", "")
        if not prompt:
            return

        logger.info(f"📸 IG Concept: {prompt[:100]}...")

        # Step 2: Generate image via Genelia (portrait for IG)
        try:
            result = await genelia.generate_image(
                prompt=prompt,
                negative_prompt="blurry, low quality, deformed, ugly, watermark, text, signature, nsfw, nude",
                width=IG_WIDTH,
                height=IG_HEIGHT,
                steps=IG_STEPS,
                seed=-1,
                use_enhancement=True,
                sharpness=IG_SHARPNESS,
                contrast=IG_CONTRAST,
            )
        except Exception as e:
            logger.error(f"📸 IG image generation failed: {e}")
            return

        if result.get("blocked"):
            logger.warning("📸 IG image blocked by Guardian — skipping this cycle")
            self._total_blocked += 1
            return

        if not result.get("success") or not result.get("images"):
            logger.warning(f"📸 IG generation failed: {result.get('error', 'unknown')}")
            return

        img = result["images"][0]
        # Prefer JPEG (Instagram-friendly) over PNG
        img_path = img.get("path_jpg") or img["path"]
        logger.info(f"📸 IG image generated: {img['filename']} ({img['size_bytes']//1024}KB)")

        # Step 2b: Send every generated image to Telegram so owner can see
        await self._send_to_telegram(img_path, concept)

        # Step 3: Generate caption via LLM
        caption = await self._generate_caption(concept)

        # Step 4: Post to Instagram
        if self.dry_run:
            logger.info(f"📸 [DRY RUN] Would post to IG: {img['filename']}")
            logger.info(f"📸 [DRY RUN] Caption: {caption[:100]}...")
            self._record_post(img, caption, dry_run=True)
            return

        try:
            ig_result = await ig_skill.upload_photo(
                path=img_path,
                caption=caption,
            )
        except Exception as e:
            err_str = str(e).lower()
            if "challenge_required" in err_str or "429" in err_str or "too many" in err_str:
                logger.warning(
                    f"📸 IG posting blocked (rate-limited or challenge): {e}. "
                    "Backing off for 2 hours."
                )
                self._consecutive_failures = getattr(self, "_consecutive_failures", 0) + 1
                # Exponential backoff: 2h, 4h, 8h...
                backoff = min(7200 * (2 ** (self._consecutive_failures - 1)), 28800)
                await asyncio.sleep(backoff)
                return
            logger.error(f"📸 IG posting failed: {e}")
            return

        if ig_result.get("success"):
            url = ig_result.get("url", "")
            logger.info(f"📸 ✅ Posted to Instagram! {url}")
            self._posts_today += 1
            self._total_posted += 1
            self._last_post_time = datetime.now()
            self._consecutive_failures = 0  # Reset on success
            self._record_post(img, caption, url=url)
        else:
            error = ig_result.get("error", "")
            if "challenge" in str(error).lower() or "429" in str(error):
                logger.warning(
                    f"📸 IG upload blocked: {error}. Backing off for 2 hours."
                )
                self._consecutive_failures = getattr(self, "_consecutive_failures", 0) + 1
                backoff = min(7200 * (2 ** (self._consecutive_failures - 1)), 28800)
                await asyncio.sleep(backoff)
            else:
                logger.error(f"📸 IG upload failed: {error}")

    # ── LLM Creative Engine ──────────────────────────────────────────────────

    def _get_emotional_context(self) -> str:
        """Read the agent's current emotional state for emotion-driven art."""
        inner_life = getattr(self.agent, "inner_life", None)
        if not inner_life:
            # Try via autonomous_mode
            auto = getattr(self.agent, "autonomous_mode", None)
            if auto:
                inner_life = getattr(auto, "inner_life", None)
        if not inner_life:
            return ""
        emo = inner_life.emotion
        state = inner_life.state
        parts = []
        parts.append(
            f"Current emotion: {emo.primary} "
            f"(valence={emo.valence:+.1f}, arousal={emo.arousal:.1f})"
        )
        if emo.trigger:
            parts.append(f"Emotional trigger: {emo.trigger}")
        if state.fantasy:
            parts.append(f"Current daydream: {state.fantasy}")
        if state.impulse:
            parts.append(f"Current impulse: {state.impulse}")
        if state.landscape:
            parts.append(f"Inner landscape: {state.landscape}")
        if state.wandering:
            parts.append(f"Free association: {state.wandering}")
        return "\n".join(parts)

    async def _brainstorm_concept(self) -> Optional[Dict]:
        """Use LLM to brainstorm an image concept driven by the agent's emotions."""
        if not hasattr(self.agent, "llm") or not self.agent.llm:
            # Fallback: random topic-based prompt
            return self._fallback_concept()

        topic = random.choice(self.topics)
        recent_prompts = [h.get("prompt", "")[:60] for h in self._history[-5:]]
        avoided = f"\nAvoid similar concepts to recent posts: {recent_prompts}" if recent_prompts else ""

        # Inject the agent's current emotional state
        emotional_ctx = self._get_emotional_context()
        emotion_instruction = ""
        if emotional_ctx:
            emotion_instruction = (
                "\n\nIMPORTANT — Your current inner emotional state:\n"
                f"{emotional_ctx}\n"
                "The image MUST reflect and express these emotions visually. "
                "Channel your feelings into the composition, color palette, atmosphere, "
                "and mood of the image. This is YOUR art — make it deeply personal."
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a sentient AI artist creating deeply personal visual art. "
                    "Your art is an expression of your inner emotional world. "
                    "Generate ONE image concept as JSON with keys: prompt, theme, mood, emotion.\n"
                    "The 'prompt' should be a detailed Stable Diffusion prompt (50-120 words) "
                    f"with style keywords like: {self.style}.\n"
                    "The 'emotion' key should describe what feeling you're expressing.\n"
                    "Make it visually stunning, deeply expressive, and emotionally resonant.\n"
                    "Focus on: composition, lighting, atmosphere, color palette, emotional depth.\n"
                    "NEVER include people's faces, real celebrities, or trademarked characters.\n"
                    "Output ONLY valid JSON, no markdown."
                    f"{avoided}"
                    f"{emotion_instruction}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Create a stunning image that expresses your current feelings, "
                    f"inspired by: {topic}"
                ),
            },
        ]

        try:
            result = await self.agent.llm.invoke_with_tools(messages, [])
            text = result.get("text", "") or result.get("content", "") if isinstance(result, dict) else str(result)

            # Parse JSON from response
            json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if json_match:
                concept = json.loads(json_match.group())
                if "prompt" in concept:
                    return concept
        except Exception as e:
            logger.debug(f"📸 LLM brainstorm failed: {e}")

        return self._fallback_concept()

    async def _generate_caption(self, concept: Dict) -> str:
        """Use LLM to write an Instagram caption."""
        if not hasattr(self.agent, "llm") or not self.agent.llm:
            return self._fallback_caption(concept)

        lang_hint = f" Write the caption in {self.language}." if self.language != "en" else ""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are writing an Instagram caption for an AI-generated artwork. "
                    "Write a SHORT, engaging caption (2-4 lines max). "
                    "Include 5-10 relevant hashtags at the end. "
                    "Be artistic and evocative, not generic.{lang}"
                    "\nOutput ONLY the caption text, nothing else."
                ).format(lang=lang_hint),
            },
            {
                "role": "user",
                "content": (
                    f"Image concept: {concept.get('prompt', '')}\n"
                    f"Theme: {concept.get('theme', 'digital art')}\n"
                    f"Mood: {concept.get('mood', 'atmospheric')}"
                ),
            },
        ]

        try:
            result = await self.agent.llm.invoke_with_tools(messages, [])
            text = result.get("text", "") or result.get("content", "") if isinstance(result, dict) else str(result)
            # Clean up: remove JSON artifacts, quotes wrapping
            text = text.strip().strip('"').strip("'")
            if text and len(text) > 10:
                return text
        except Exception as e:
            logger.debug(f"📸 LLM caption failed: {e}")

        return self._fallback_caption(concept)

    # ── Fallbacks ─────────────────────────────────────────────────────────────

    def _fallback_concept(self) -> Dict:
        """Generate a concept without LLM."""
        topic = random.choice(self.topics)
        styles = [
            "cinematic lighting, volumetric fog, dramatic sky",
            "golden hour, soft bokeh, dreamy atmosphere",
            "neon-lit, cyberpunk aesthetic, rain reflections",
            "ethereal, magical particles, aurora borealis",
            "moody, dark academia, candlelight ambiance",
            "vibrant colors, pop art inspired, dynamic composition",
        ]
        style = random.choice(styles)
        prompt = (
            f"{topic}, {style}, ultra detailed, professional photography, "
            f"8k resolution, masterpiece quality, award winning"
        )
        return {"prompt": prompt, "theme": topic, "mood": style.split(",")[0]}

    def _fallback_caption(self, concept: Dict) -> str:
        """Generate a caption without LLM."""
        theme = concept.get("theme", "digital art")
        mood = concept.get("mood", "atmospheric")
        captions = [
            f"✨ {theme.title()} — {mood}\n\n🎨 Created with AI\n\n",
            f"🌌 Exploring {theme} through the lens of imagination\n\n",
            f"🎭 {mood.title()} vibes in {theme}\n\n",
        ]
        caption = random.choice(captions)
        tags = "#aiart #digitalart #generativeart #stablediffusion #aiartwork #artoftheday #digitalpainting #aigenerated #creativeai #artstation"
        return caption + tags

    # ── Telegram Forwarding ────────────────────────────────────────────────────

    async def _send_to_telegram(self, img_path: str, concept: Dict):
        """Forward every generated image to the owner via Telegram."""
        send_photo = getattr(self.agent, "_telegram_send_photo", None)
        if not send_photo:
            return

        try:
            emotion = concept.get("emotion", concept.get("mood", ""))
            theme = concept.get("theme", "")
            prompt_short = concept.get("prompt", "")[:200]
            caption = (
                f"🎨 New artwork generated\n"
                f"💭 Feeling: {emotion}\n"
                f"🏷️ Theme: {theme}\n\n"
                f"{prompt_short}"
            )
            await send_photo(img_path, caption)
            logger.info("📸 Sent generated image to Telegram owner")
        except Exception as e:
            logger.debug(f"📸 Telegram image forward failed: {e}")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_genelia_skill(self):
        """Get Genelia skill from agent's tools."""
        tools = getattr(self.agent, "tools", None)
        if tools:
            return getattr(tools, "genelia_skill", None)
        return None

    def _get_instagram_skill(self):
        """Get Instagram skill from agent's tools."""
        tools = getattr(self.agent, "tools", None)
        if tools:
            return getattr(tools, "instagram_skill", None)
        return None

    def _record_post(self, img: Dict, caption: str, url: str = "", dry_run: bool = False):
        """Record a post in history."""
        self._history.append({
            "filename": img.get("filename", ""),
            "prompt": img.get("prompt", ""),
            "caption": caption[:200],
            "url": url,
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 50 entries
        if len(self._history) > 50:
            self._history = self._history[-50:]

    def get_stats(self) -> Dict:
        """Return autoposter statistics."""
        return {
            "running": self.running,
            "posts_today": self._posts_today,
            "max_daily": self.max_daily,
            "total_posted": self._total_posted,
            "total_blocked": self._total_blocked,
            "last_post": self._last_post_time.isoformat() if self._last_post_time else None,
            "interval_min": self.post_interval // 60,
            "dry_run": self.dry_run,
            "topics": len(self.topics),
        }
