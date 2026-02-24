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
    """Grok AI via X account wrapper"""

    def __init__(self, config):
        self.config = config
        self._impl = None

    async def initialize(self):
        try:
            from .grok_skill import GrokSkill as GrokSkillImpl
            self._impl = GrokSkillImpl(self.config)
            return await self._impl.initialize()
        except Exception as e:
            logger.warning(f"Grok skill init failed: {e}")
            return False

    async def chat(self, message, **kwargs):
        if not self._impl: raise RuntimeError("Grok not initialized")
        return await self._impl.chat(message, **kwargs)

    async def analyze_image(self, image_paths, prompt="Describe these images.", **kwargs):
        if not self._impl: raise RuntimeError("Grok not initialized")
        return await self._impl.analyze_image(image_paths, prompt, **kwargs)

    async def generate_image(self, prompt, **kwargs):
        if not self._impl: raise RuntimeError("Grok not initialized")
        return await self._impl.generate_image(prompt, **kwargs)


__all__ = ["VoiceSkill", "ImageSkill", "DatabaseSkill", "RAGSkill", "CodeExecutor", "APIClient", "XSkill", "GrokSkill"]
