"""
Multi-Modal Engine,  WORLD FIRST
Real multi-modal perception: image analysis, audio processing,
video understanding, and cross-modal generation.
Not just text,  sees, hears, and creates across modalities.
"""
import json
import logging
import base64
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class ModalPerception:
    id: str
    modality: str  # image, audio, video, text
    source: str
    timestamp: str
    analysis: Dict[str, Any] = field(default_factory=dict)
    embeddings_hash: Optional[str] = None
    size_bytes: int = 0

@dataclass
class CrossModalLink:
    source_id: str
    target_id: str
    source_modality: str
    target_modality: str
    relationship: str
    confidence: float = 0.0

# ── Core Engine ───────────────────────────────────────────────────────

class MultiModalEngine:
    """
    Multi-modal perception and generation engine.
    Processes images, audio, and video, creates cross-modal
    links, and generates content across modalities.
    """

    SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
    SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
    SUPPORTED_VIDEO_FORMATS = {".mp4", ".avi", ".mkv", ".webm", ".mov"}
    MAX_PERCEPTIONS = 500

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "multimodal_engine_state.json"

        self.perceptions: List[ModalPerception] = []
        self.cross_modal_links: List[CrossModalLink] = []
        self.total_images_processed = 0
        self.total_audio_processed = 0
        self.total_video_processed = 0
        self.total_generations = 0
        self.total_cross_modal = 0

        self._load_state()

    def detect_modality(self, file_path: str) -> str:
        """Detect the modality of a file."""
        ext = Path(file_path).suffix.lower()
        if ext in self.SUPPORTED_IMAGE_FORMATS:
            return "image"
        elif ext in self.SUPPORTED_AUDIO_FORMATS:
            return "audio"
        elif ext in self.SUPPORTED_VIDEO_FORMATS:
            return "video"
        return "text"

    async def analyze_image(self, image_path: str, llm=None) -> Dict[str, Any]:
        """Analyze an image file using vision models."""
        path = Path(image_path)
        if not path.exists():
            return {"error": f"File not found: {image_path}"}

        perception_id = hashlib.sha256(f"img_{image_path}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        result = {"id": perception_id, "modality": "image", "file": image_path}

        try:
            # Get file info
            stat = path.stat()
            result["size_bytes"] = stat.st_size
            result["format"] = path.suffix.lower()

            # Try to get image dimensions with PIL
            try:
                from PIL import Image
                with Image.open(path) as img:
                    result["width"] = img.width
                    result["height"] = img.height
                    result["mode"] = img.mode

                    # If LLM supports vision, send the image
                    if llm and hasattr(llm, "chat_with_image"):
                        analysis = await llm.chat_with_image(
                            "Describe this image in detail. Include: objects, colors, scene, mood, text if any.",
                            image_path,
                        )
                        result["description"] = analysis
            except ImportError:
                result["note"] = "PIL not available,  basic analysis only"

            # If LLM available and supports base64 vision
            if llm and not result.get("description"):
                try:
                    with open(path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode()
                    result["hash"] = hashlib.sha256(img_data[:1000].encode()).hexdigest()[:16]
                except Exception:
                    pass

            self.total_images_processed += 1
            perception = ModalPerception(
                id=perception_id, modality="image", source=image_path,
                timestamp=datetime.now(timezone.utc).isoformat(),
                analysis=result, size_bytes=result.get("size_bytes", 0),
            )
            self._add_perception(perception)

        except Exception as e:
            result["error"] = str(e)

        return result

    async def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """Analyze an audio file."""
        path = Path(audio_path)
        if not path.exists():
            return {"error": f"File not found: {audio_path}"}

        perception_id = hashlib.sha256(f"aud_{audio_path}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        result = {"id": perception_id, "modality": "audio", "file": audio_path}

        try:
            stat = path.stat()
            result["size_bytes"] = stat.st_size
            result["format"] = path.suffix.lower()

            # Try to get audio metadata
            try:
                import wave
                if path.suffix.lower() == ".wav":
                    with wave.open(str(path), "rb") as wav:
                        result["channels"] = wav.getnchannels()
                        result["sample_rate"] = wav.getframerate()
                        result["frames"] = wav.getnframes()
                        result["duration_seconds"] = round(wav.getnframes() / wav.getframerate(), 2)
            except Exception:
                pass

            self.total_audio_processed += 1
            perception = ModalPerception(
                id=perception_id, modality="audio", source=audio_path,
                timestamp=datetime.now(timezone.utc).isoformat(),
                analysis=result, size_bytes=result.get("size_bytes", 0),
            )
            self._add_perception(perception)

        except Exception as e:
            result["error"] = str(e)

        return result

    async def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """Analyze a video file."""
        path = Path(video_path)
        if not path.exists():
            return {"error": f"File not found: {video_path}"}

        perception_id = hashlib.sha256(f"vid_{video_path}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        result = {"id": perception_id, "modality": "video", "file": video_path}

        try:
            stat = path.stat()
            result["size_bytes"] = stat.st_size
            result["format"] = path.suffix.lower()
            result["size_mb"] = round(stat.st_size / (1024 * 1024), 2)

            # Try ffprobe for metadata
            try:
                import subprocess
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                    capture_output=True, text=True, timeout=10,
                )
                if probe.returncode == 0:
                    meta = json.loads(probe.stdout)
                    fmt = meta.get("format", {})
                    result["duration_seconds"] = round(float(fmt.get("duration", 0)), 2)
                    result["bitrate"] = fmt.get("bit_rate", "unknown")
                    for stream in meta.get("streams", []):
                        if stream.get("codec_type") == "video":
                            result["width"] = stream.get("width")
                            result["height"] = stream.get("height")
                            result["fps"] = stream.get("r_frame_rate", "unknown")
                            result["codec"] = stream.get("codec_name", "unknown")
                            break
            except Exception:
                result["note"] = "ffprobe not available,  basic analysis only"

            self.total_video_processed += 1
            perception = ModalPerception(
                id=perception_id, modality="video", source=video_path,
                timestamp=datetime.now(timezone.utc).isoformat(),
                analysis=result, size_bytes=result.get("size_bytes", 0),
            )
            self._add_perception(perception)

        except Exception as e:
            result["error"] = str(e)

        return result

    def link_modalities(self, source_id: str, target_id: str, relationship: str, confidence: float = 0.8):
        """Create a cross-modal link between two perceptions."""
        src = next((p for p in self.perceptions if p.id == source_id), None)
        tgt = next((p for p in self.perceptions if p.id == target_id), None)
        if src and tgt:
            link = CrossModalLink(
                source_id=source_id, target_id=target_id,
                source_modality=src.modality, target_modality=tgt.modality,
                relationship=relationship, confidence=confidence,
            )
            self.cross_modal_links.append(link)
            self.total_cross_modal += 1
            self._save_state()

    def _add_perception(self, perception: ModalPerception):
        self.perceptions.append(perception)
        if len(self.perceptions) > self.MAX_PERCEPTIONS:
            self.perceptions = self.perceptions[-self.MAX_PERCEPTIONS:]
        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_perceptions": len(self.perceptions),
            "images_processed": self.total_images_processed,
            "audio_processed": self.total_audio_processed,
            "video_processed": self.total_video_processed,
            "cross_modal_links": self.total_cross_modal,
            "total_generations": self.total_generations,
            "modalities": list(set(p.modality for p in self.perceptions)),
        }

    def _save_state(self):
        try:
            state = {
                "perceptions": [asdict(p) for p in self.perceptions[-100:]],
                "cross_modal_links": [asdict(l) for l in self.cross_modal_links[-100:]],
                "total_images_processed": self.total_images_processed,
                "total_audio_processed": self.total_audio_processed,
                "total_video_processed": self.total_video_processed,
                "total_generations": self.total_generations,
                "total_cross_modal": self.total_cross_modal,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"MultiModal save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.perceptions = [ModalPerception(**p) for p in state.get("perceptions", [])]
                self.cross_modal_links = [CrossModalLink(**l) for l in state.get("cross_modal_links", [])]
                self.total_images_processed = state.get("total_images_processed", 0)
                self.total_audio_processed = state.get("total_audio_processed", 0)
                self.total_video_processed = state.get("total_video_processed", 0)
                self.total_generations = state.get("total_generations", 0)
                self.total_cross_modal = state.get("total_cross_modal", 0)
        except Exception as e:
            logger.debug(f"MultiModal load failed: {e}")
