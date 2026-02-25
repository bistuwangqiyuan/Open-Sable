"""
Grok AI Skill — Free Grok access via X (Twitter) account using twikit_grok.

Uses the twikit_grok library to interact with Grok AI through your X account.
No paid API keys required — Grok is free for all X members.

Features:
- Chat with Grok (streaming and non-streaming)
- Image analysis via Grok vision
- Image generation via Grok
- Conversation management (create, continue, list)
- Rate-limit aware with automatic delays

Setup:
    Set these in .env:
        X_USERNAME=your_x_username
        X_EMAIL=your_x_email
        X_PASSWORD=your_x_password
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from twikit_grok import Client as GrokClient

    TWIKIT_GROK_AVAILABLE = True
except ImportError:
    TWIKIT_GROK_AVAILABLE = False
    logger.info("twikit_grok not installed. Install with: pip install twikit_grok")


class GrokSkill:
    """
    Interact with Grok AI through your X account — free, no API keys.

    Uses twikit_grok which handles authentication via X cookies.
    """

    def __init__(self, config):
        self.config = config
        self._client: Optional[Any] = None
        self._conversations: Dict[str, Any] = {}
        self._cookies_path = Path.home() / ".opensable" / "x_cookies.json"
        self._cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize and authenticate with X for Grok access."""
        if not TWIKIT_GROK_AVAILABLE:
            logger.warning("twikit_grok not available — Grok skill disabled")
            return False

        try:
            self._client = GrokClient("en-US")

            # Try loading saved cookies first
            if self._cookies_path.exists():
                self._client.load_cookies(str(self._cookies_path))
                logger.info("✅ Grok: Loaded saved X cookies")
                self._initialized = True
                return True

            # Otherwise, login with credentials
            username = getattr(self.config, "x_username", None) or os.getenv("X_USERNAME")
            email = getattr(self.config, "x_email", None) or os.getenv("X_EMAIL")
            password = getattr(self.config, "x_password", None) or os.getenv("X_PASSWORD")

            if not all([username, password]):
                logger.warning(
                    "Grok: Missing X credentials. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
                )
                return False

            await self._client.login(
                auth_info_1=username,
                auth_info_2=email,
                password=password,
            )

            # Save cookies for next time
            self._client.save_cookies(str(self._cookies_path))
            logger.info("✅ Grok: Authenticated with X and cookies saved")
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Grok initialization failed: {e}")
            return False

    def _ensure_initialized(self):
        """Raise if not initialized."""
        if not self._initialized or not self._client:
            raise RuntimeError(
                "Grok not initialized. Check X credentials in .env "
                "(X_USERNAME, X_EMAIL, X_PASSWORD)"
            )

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a message to Grok AI.

        Args:
            message: The message/prompt to send
            conversation_id: Continue an existing conversation (optional)
            stream: If True, returns chunks as they arrive

        Returns:
            Dict with 'response', 'conversation_id', and optional 'attachments'
        """
        self._ensure_initialized()

        try:
            # Get or create conversation
            if conversation_id and conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
            else:
                conversation = await self._client.create_grok_conversation()
                conv_id = str(id(conversation))
                self._conversations[conv_id] = conversation
                conversation_id = conv_id

            if stream:
                # Streaming response
                chunks = []
                async for chunk in conversation.stream(message):
                    chunks.append(str(chunk))
                full_response = "".join(chunks)
            else:
                # Non-streaming response
                content = await conversation.generate(message)
                full_response = content.message

            # Small delay to be respectful to rate limits
            await asyncio.sleep(1)

            return {
                "success": True,
                "response": full_response,
                "conversation_id": conversation_id,
            }

        except Exception as e:
            logger.error(f"Grok chat error: {e}")
            return {"success": False, "error": str(e)}

    async def analyze_image(
        self,
        image_paths: List[str],
        prompt: str = "Please describe these images in detail.",
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send images to Grok for analysis.

        Args:
            image_paths: List of local image file paths
            prompt: Question/instruction about the images
            conversation_id: Continue existing conversation (optional)
        """
        self._ensure_initialized()

        try:
            # Get or create conversation
            if conversation_id and conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
            else:
                conversation = await self._client.create_grok_conversation()
                conv_id = str(id(conversation))
                self._conversations[conv_id] = conversation
                conversation_id = conv_id

            # Upload attachments
            attachments = []
            for path in image_paths:
                attachment = await self._client.upload_grok_attachment(path)
                attachments.append(attachment)

            # Send with attachments
            chunks = []
            async for chunk in conversation.stream(prompt, attachments):
                chunks.append(str(chunk))

            full_response = "".join(chunks)
            await asyncio.sleep(1)

            return {
                "success": True,
                "response": full_response,
                "conversation_id": conversation_id,
            }

        except Exception as e:
            logger.error(f"Grok image analysis error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_image(
        self,
        prompt: str,
        save_path: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ask Grok to generate images.

        Args:
            prompt: Image generation prompt (e.g. "generate an image of a cat in space")
            save_path: Optional path to save the generated image
            conversation_id: Continue existing conversation (optional)
        """
        self._ensure_initialized()

        try:
            if conversation_id and conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
            else:
                conversation = await self._client.create_grok_conversation()
                conv_id = str(id(conversation))
                self._conversations[conv_id] = conversation
                conversation_id = conv_id

            content = await conversation.generate(prompt)

            saved_files = []
            if content.attachments:
                for i, attachment in enumerate(content.attachments):
                    if save_path:
                        # If save_path provided, use it (with index for multiple)
                        out = save_path if len(content.attachments) == 1 else f"{save_path}_{i}.jpg"
                    else:
                        out = f"/tmp/grok_image_{conversation_id}_{i}.jpg"
                    await attachment.download(out)
                    saved_files.append(out)

            await asyncio.sleep(1)

            return {
                "success": True,
                "message": content.message if hasattr(content, "message") else "",
                "images": saved_files,
                "conversation_id": conversation_id,
            }

        except Exception as e:
            logger.error(f"Grok image generation error: {e}")
            return {"success": False, "error": str(e)}

    async def new_conversation(self) -> str:
        """Create a new Grok conversation and return its ID."""
        self._ensure_initialized()
        conversation = await self._client.create_grok_conversation()
        conv_id = str(id(conversation))
        self._conversations[conv_id] = conversation
        return conv_id

    def list_conversations(self) -> List[str]:
        """List active conversation IDs."""
        return list(self._conversations.keys())

    def clear_conversations(self):
        """Clear all tracked conversations."""
        self._conversations.clear()
        logger.info("Grok: All conversations cleared")
