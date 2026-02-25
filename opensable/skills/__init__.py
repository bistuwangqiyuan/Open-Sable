"""Skills package for Open-Sable - High-level wrappers for all advanced capabilities"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceSkill:
    """Voice capabilities wrapper"""

    def __init__(self, config):
        self.config = config
        self._tts_engine = None
        self._stt_engine = None

    async def initialize(self):
        """Initialize voice engines"""
        try:
            from .voice_skill import TTSEngine, STTEngine

            self._tts_engine = TTSEngine(self.config)
            self._stt_engine = STTEngine(self.config)
            await self._tts_engine.initialize()
            await self._stt_engine.initialize()
            logger.info("Voice skill initialized")
        except Exception as e:
            logger.warning(f"Voice skill init failed: {e}")

    async def speak(self, text: str, output_file: Optional[str] = None) -> str:
        """Text-to-speech"""
        if not self._tts_engine:
            raise RuntimeError("Voice not initialized")
        return await self._tts_engine.synthesize(text, output_file)

    async def listen(self, audio_file: str = None, language: Optional[str] = None) -> str:
        """Speech-to-text"""
        if not self._stt_engine:
            raise RuntimeError("Voice not initialized")
        return await self._stt_engine.transcribe(audio_file, language=language)


class ImageSkill:
    """Image generation and analysis wrapper"""

    def __init__(self, config):
        self.config = config
        self._generator = None
        self._analyzer = None

    async def initialize(self):
        """Initialize image engines"""
        try:
            from .image_skill import ImageGenerator, ImageAnalyzer

            self._generator = ImageGenerator(
                provider=getattr(self.config, "image_api", "stable-diffusion"),
                api_key=getattr(self.config, "openai_api_key", None),
            )
            self._analyzer = ImageAnalyzer()
            logger.info("Image skill initialized")
        except Exception as e:
            logger.warning(f"Image skill init failed: {e}")

    async def generate(
        self,
        prompt: str,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        output_path: str = "image.png",
    ) -> dict:
        """Generate image from prompt"""
        if not self._generator:
            return {"success": False, "error": "Image generator not initialized"}

        try:
            result = await self._generator.generate(prompt=prompt, model=model, size=size)

            if result.success:
                result.save(output_path)
                return {"success": True, "path": output_path, "prompt": prompt}
            else:
                return {"success": False, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def analyze(self, image_path: str) -> dict:
        """Analyze image content"""
        if not self._analyzer:
            return {"success": False, "error": "Image analyzer not initialized"}

        try:
            result = await self._analyzer.analyze(image_path)
            if result.success:
                return {
                    "success": True,
                    "labels": result.labels,
                    "description": result.description,
                    "objects": result.objects,
                }
            else:
                return {"success": False, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def ocr(self, image_path: str, language: str = "eng") -> dict:
        """Extract text from image"""
        try:
            from .image_skill import perform_ocr

            result = perform_ocr(image_path, language)
            if result.success:
                return {"success": True, "text": result.text, "confidence": result.confidence}
            else:
                return {"success": False, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}


class DatabaseSkill:
    """Database query wrapper"""

    def __init__(self, config):
        self.config = config
        self._connections = {}

    async def initialize(self):
        """Initialize database connections"""
        logger.info("Database skill ready")

    async def execute(
        self,
        query: str,
        db_type: str = "sqlite",
        database: str = "default.db",
        params: tuple = None,
    ) -> dict:
        """Execute SQL query"""
        try:
            from .database_skill import DatabaseManager, DatabaseConfig

            db_config = DatabaseConfig(type=db_type, database=database)

            db_manager = DatabaseManager(db_config)
            result = await db_manager.execute(query, params)

            if result.success:
                return {"success": True, "rows": result.rows, "row_count": result.row_count}
            else:
                return {"success": False, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}


class RAGSkill:
    """Vector search / RAG wrapper"""

    def __init__(self, config):
        self.config = config
        self._store = None

    async def initialize(self):
        """Initialize vector store"""
        try:
            from .rag_skill import RAGSystem

            persist_dir = str(getattr(self.config, "vector_db_path", "./data/vectordb"))
            self._store = RAGSystem(persist_directory=persist_dir)
            logger.info("RAG skill initialized")
        except Exception as e:
            logger.warning(f"RAG skill init failed: {e}")

    async def search(self, query: str, collection: str = "default", top_k: int = 5) -> list:
        """Semantic search"""
        if not self._store:
            return []

        try:
            results = await self._store.search(query=query, top_k=top_k)
            return [
                {"content": r.document.content, "score": r.score, "metadata": r.document.metadata}
                for r in results
            ]
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return []


class CodeExecutor:
    """Code execution wrapper"""

    def __init__(self, config):
        self.config = config

    async def execute(self, code: str, language: str = "python", timeout: int = 30) -> dict:
        """Execute code safely using subprocess"""
        import subprocess
        import tempfile
        import os

        try:
            if language in ("python", "py"):
                with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                    f.write(code)
                    tmp_path = f.name
                try:
                    proc = subprocess.run(
                        ["python3", tmp_path],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=os.getcwd(),
                    )
                    if proc.returncode == 0:
                        return {
                            "success": True,
                            "output": proc.stdout.strip(),
                            "return_value": None,
                        }
                    else:
                        return {
                            "success": False,
                            "error": proc.stderr.strip() or f"Exit code {proc.returncode}",
                        }
                finally:
                    os.unlink(tmp_path)
            elif language in ("bash", "sh", "shell"):
                proc = subprocess.run(
                    ["bash", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=os.getcwd(),
                )
                if proc.returncode == 0:
                    return {"success": True, "output": proc.stdout.strip(), "return_value": None}
                else:
                    return {
                        "success": False,
                        "error": proc.stderr.strip() or f"Exit code {proc.returncode}",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Language '{language}' not supported. Use python or bash.",
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Execution timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class APIClient:
    """HTTP API client wrapper"""

    def __init__(self, config):
        self.config = config

    async def request(
        self, url: str, method: str = "GET", headers: dict = None, data: any = None
    ) -> dict:
        """Make HTTP request"""
        try:
            from .api_client import APIClient as APIClientImpl

            client = APIClientImpl(
                base_url=getattr(self.config, "api_base_url", "") or url.rsplit("/", 1)[0],
            )
            result = await client.request(
                method=method,
                url=url,
                headers=headers or {},
                json=data if isinstance(data, dict) else None,
                data=data if not isinstance(data, dict) else None,
            )

            if result.success:
                return {"success": True, "data": result.data, "status_code": result.status_code}
            else:
                return {"success": False, "error": result.error}
        except Exception as e:
            return {"success": False, "error": str(e)}


# X (Twitter) & Grok skills
class XSkill:
    """X/Twitter automation wrapper — ALL API calls go through a global FIFO queue.
    
    Every call from anywhere (autoposter, Telegram, autonomous mode) is enqueued.
    The queue processes them ONE AT A TIME with adaptive cooldowns that learn
    from success/failure. Like a real human: one action, wait, next action.
    """

    _queue_initialized = False

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def _get_queue(self):
        """Get (or create) the singleton queue and ensure it has our impl."""
        from opensable.core.x_api_queue import XApiQueue
        q = XApiQueue.get_instance()
        if self._impl and q._impl is None:
            q.set_impl(self._impl)
        return q

    async def initialize(self):
        try:
            from .x_skill import XSkill as XSkillImpl
            self._impl = XSkillImpl(self.config)
            result = await self._impl.initialize()
            # Register impl with the queue
            from opensable.core.x_api_queue import XApiQueue
            XApiQueue.get_instance().set_impl(self._impl)
            logger.info("📋 X API queue linked to XSkill")
            return result
        except Exception as e:
            logger.warning(f"X skill init failed: {e}")
            return False

    async def post_tweet(self, text, **kwargs):
        q = await self._get_queue()
        return await q.enqueue("post_tweet", text, **kwargs)

    async def post_thread(self, tweets):
        q = await self._get_queue()
        return await q.enqueue("post_thread", tweets)

    async def search_tweets(self, query, **kwargs):
        q = await self._get_queue()
        return await q.enqueue("search_tweets", query, **kwargs)

    async def get_trends(self, category="trending"):
        q = await self._get_queue()
        return await q.enqueue("get_trends", category)

    async def like_tweet(self, tweet_id):
        q = await self._get_queue()
        return await q.enqueue("like_tweet", tweet_id)

    async def retweet(self, tweet_id):
        q = await self._get_queue()
        return await q.enqueue("retweet", tweet_id)

    async def reply(self, tweet_id, text):
        q = await self._get_queue()
        return await q.enqueue("reply", tweet_id, text)

    async def get_user(self, username):
        q = await self._get_queue()
        return await q.enqueue("get_user", username)

    async def get_user_tweets(self, username, **kwargs):
        q = await self._get_queue()
        return await q.enqueue("get_user_tweets", username, **kwargs)

    async def follow_user(self, username):
        q = await self._get_queue()
        return await q.enqueue("follow_user", username)

    async def send_dm(self, user_id, text):
        q = await self._get_queue()
        return await q.enqueue("send_dm", user_id, text)

    async def delete_tweet(self, tweet_id):
        q = await self._get_queue()
        return await q.enqueue("delete_tweet", tweet_id)

    def is_available(self):
        return self._impl is not None and self._impl.is_available()


class GrokSkill:
    """Grok AI via X account wrapper — ALL calls go through the X API queue.
    
    Grok uses the same X session/cookies, so concurrent Grok + X API calls
    look like parallel automation to X's detection systems.
    """

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .grok_skill import GrokSkill as GrokSkillImpl
            self._impl = GrokSkillImpl(self.config)
            result = await self._impl.initialize()
            # Register impl with the queue
            from opensable.core.x_api_queue import XApiQueue
            XApiQueue.get_instance().set_grok_impl(self._impl)
            logger.info("📋 X API queue linked to Grok")
            return result
        except Exception as e:
            logger.warning(f"Grok skill init failed: {e}")
            return False

    async def _get_queue(self):
        from opensable.core.x_api_queue import XApiQueue
        q = XApiQueue.get_instance()
        if self._impl and q._grok_impl is None:
            q.set_grok_impl(self._impl)
        return q

    async def chat(self, message, **kwargs):
        q = await self._get_queue()
        return await q.enqueue("grok_chat", message, **kwargs)

    async def analyze_image(self, image_paths, prompt="Describe these images.", **kwargs):
        q = await self._get_queue()
        return await q.enqueue("grok_analyze", image_paths, prompt, **kwargs)

    async def generate_image(self, prompt, **kwargs):
        q = await self._get_queue()
        return await q.enqueue("grok_generate", prompt, **kwargs)


# ── Social media skills (Instagram, Facebook, LinkedIn, TikTok) ──────

class InstagramSkill:
    """Instagram automation wrapper — uses instagrapi (unofficial Private API)."""

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .instagram_skill import InstagramSkill as InstagramSkillImpl
            self._impl = InstagramSkillImpl(self.config)
            return await self._impl.initialize()
        except Exception as e:
            logger.warning(f"Instagram skill init failed: {e}")
            return False

    async def upload_photo(self, path, caption="", **kwargs):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_photo(path, caption, **kwargs)

    async def upload_video(self, path, caption="", **kwargs):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_video(path, caption, **kwargs)

    async def upload_reel(self, path, caption="", **kwargs):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_reel(path, caption, **kwargs)

    async def upload_story(self, path, caption="", **kwargs):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_story(path, caption, **kwargs)

    async def upload_album(self, paths, caption=""):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_album(paths, caption)

    async def search_users(self, query, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_users(query, count)

    async def search_hashtags(self, query, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_hashtags(query, count)

    async def get_user_info(self, username):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_user_info(username)

    async def get_user_medias(self, username, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_user_medias(username, count)

    async def get_timeline(self, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_timeline(count)

    async def like_media(self, media_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.like_media(media_id)

    async def comment(self, media_id, text):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.comment(media_id, text)

    async def follow_user(self, username):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.follow_user(username)

    async def unfollow_user(self, username):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.unfollow_user(username)

    async def send_dm(self, username, text):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.send_dm(username, text)

    async def get_direct_threads(self, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_direct_threads(count)

    async def delete_media(self, media_pk):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.delete_media(media_pk)

    async def get_hashtag_medias(self, hashtag, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_hashtag_medias(hashtag, count)

    async def get_user_stories(self, username):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_user_stories(username)

    async def download_media(self, media_pk, folder="/tmp"):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.download_media(media_pk, folder)

    def is_available(self):
        return self._impl is not None and self._impl.is_available()


class FacebookSkill:
    """Facebook Graph API wrapper — uses facebook-sdk."""

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .facebook_skill import FacebookSkill as FacebookSkillImpl
            self._impl = FacebookSkillImpl(self.config)
            return await self._impl.initialize()
        except Exception as e:
            logger.warning(f"Facebook skill init failed: {e}")
            return False

    async def post(self, message, link=None, use_page=False):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.post(message, link, use_page)

    async def upload_photo(self, path, caption="", use_page=False):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_photo(path, caption, use_page)

    async def get_feed(self, count=10, use_page=False):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_feed(count, use_page)

    async def get_post(self, post_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_post(post_id)

    async def like_post(self, post_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.like_post(post_id)

    async def comment_on_post(self, post_id, message):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.comment_on_post(post_id, message)

    async def get_comments(self, post_id, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_comments(post_id, count)

    async def get_profile(self):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_profile()

    async def get_page_info(self, page_id=None):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_page_info(page_id)

    async def search(self, query, search_type="page", count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search(query, search_type, count)

    async def delete_post(self, post_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.delete_post(post_id)

    def is_available(self):
        return self._impl is not None and self._impl.is_available()


class LinkedInSkill:
    """LinkedIn automation wrapper — uses linkedin-api (Voyager API, unofficial)."""

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .linkedin_skill import LinkedInSkill as LinkedInSkillImpl
            self._impl = LinkedInSkillImpl(self.config)
            return await self._impl.initialize()
        except Exception as e:
            logger.warning(f"LinkedIn skill init failed: {e}")
            return False

    async def get_profile(self, public_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_profile(public_id)

    async def search_people(self, keywords, limit=10, **kwargs):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_people(keywords, limit, **kwargs)

    async def search_companies(self, keywords, limit=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_companies(keywords, limit)

    async def search_jobs(self, keywords, location=None, limit=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_jobs(keywords, location, limit)

    async def post_update(self, text, **kwargs):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.post_update(text, **kwargs)

    async def react_to_post(self, post_urn, reaction_type="LIKE"):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.react_to_post(post_urn, reaction_type)

    async def send_message(self, public_id, text):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.send_message(public_id, text)

    async def get_conversations(self, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_conversations(count)

    async def send_connection_request(self, public_id, message=""):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.send_connection_request(public_id, message)

    async def remove_connection(self, public_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.remove_connection(public_id)

    async def get_feed_posts(self, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_feed_posts(count)

    async def get_user_posts(self, public_id, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_user_posts(public_id, count)

    async def get_company(self, company_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_company(company_id)

    def is_available(self):
        return self._impl is not None and self._impl.is_available()


class TikTokSkill:
    """TikTok data retrieval wrapper — uses TikTokApi (read-only, no posting)."""

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .tiktok_skill import TikTokSkill as TikTokSkillImpl
            self._impl = TikTokSkillImpl(self.config)
            return await self._impl.initialize()
        except Exception as e:
            logger.warning(f"TikTok skill init failed: {e}")
            return False

    async def get_trending_videos(self, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_trending_videos(count)

    async def search_videos(self, query, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_videos(query, count)

    async def search_users(self, query, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_users(query, count)

    async def get_user_info(self, username):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_user_info(username)

    async def get_user_videos(self, username, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_user_videos(username, count)

    async def get_video_info(self, video_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_video_info(video_id)

    async def get_video_comments(self, video_id, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_video_comments(video_id, count)

    async def get_hashtag_info(self, hashtag):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_hashtag_info(hashtag)

    async def get_hashtag_videos(self, hashtag, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_hashtag_videos(hashtag, count)

    async def download_video(self, video_id, path="/tmp"):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.download_video(video_id, path)

    def is_available(self):
        return self._impl is not None and self._impl.is_available()


class YouTubeSkill:
    """YouTube wrapper — uses python-youtube (pyyoutube) for YouTube Data API v3."""

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .youtube_skill import YouTubeSkill as YouTubeSkillImpl
            self._impl = YouTubeSkillImpl(self.config)
            return await self._impl.initialize()
        except Exception as e:
            logger.warning(f"YouTube skill init failed: {e}")
            return False

    async def search_videos(self, query, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_videos(query, count)

    async def search_channels(self, query, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.search_channels(query, count)

    async def get_channel_info(self, channel_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_channel_info(channel_id)

    async def get_channel_videos(self, channel_id, count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_channel_videos(channel_id, count)

    async def get_video_info(self, video_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_video_info(video_id)

    async def get_video_comments(self, video_id, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_video_comments(video_id, count)

    async def comment_on_video(self, video_id, text):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.comment_on_video(video_id, text)

    async def get_playlist_items(self, playlist_id, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_playlist_items(playlist_id, count)

    async def rate_video(self, video_id, rating="like"):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.rate_video(video_id, rating)

    async def subscribe(self, channel_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.subscribe(channel_id)

    async def get_my_subscriptions(self, count=20):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_my_subscriptions(count)

    async def upload_video(self, file_path, title="", description="", tags=None, privacy="private"):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.upload_video(file_path, title, description, tags, privacy)

    async def get_trending(self, region_code="US", count=10):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_trending(region_code, count)

    async def get_captions(self, video_id):
        if not self._impl: return {"success": False, "error": "Not initialized"}
        return await self._impl.get_captions(video_id)

    def is_available(self):
        return self._impl is not None and self._impl.is_available()


__all__ = [
    "VoiceSkill", "ImageSkill", "DatabaseSkill", "RAGSkill",
    "CodeExecutor", "APIClient", "XSkill", "GrokSkill",
    "InstagramSkill", "FacebookSkill", "LinkedInSkill", "TikTokSkill",
    "YouTubeSkill",
]
