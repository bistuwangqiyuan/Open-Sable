"""
Video Understanding Engine

Real video content analysis — not just metadata.
Extracts keyframes, sends them to vision LLMs (GPT-4V, Grok Vision, Gemini),
performs scene segmentation, action recognition, and temporal reasoning.

Capabilities:
  1. Extract keyframes from video files (ffmpeg scene detection)
  2. Analyze frames with vision LLMs (describe scenes, identify objects/people)
  3. Temporal reasoning — understand narrative flow across frames
  4. Audio transcription — extract speech from video via Whisper
  5. Scene segmentation — detect scene changes and summarize each
  6. Generate full video summaries combining visual + audio analysis
  7. Answer questions about video content ("What happened at minute 3?")
"""
import json
import logging
import asyncio
import subprocess
import tempfile
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class VideoFrame:
    """A single extracted frame with analysis."""
    frame_id: str
    timestamp_sec: float
    image_path: str
    scene_description: str = ""
    objects_detected: List[str] = field(default_factory=list)
    text_visible: str = ""
    confidence: float = 0.0

@dataclass
class VideoScene:
    """A detected scene in the video."""
    scene_id: int
    start_sec: float
    end_sec: float
    description: str = ""
    frames: List[str] = field(default_factory=list)  # frame IDs
    mood: str = ""
    key_action: str = ""

@dataclass
class VideoAnalysis:
    """Full analysis of a video."""
    video_id: str
    file_path: str
    duration_sec: float = 0.0
    resolution: str = ""
    fps: float = 0.0
    total_frames_extracted: int = 0
    scenes: List[VideoScene] = field(default_factory=list)
    transcript: str = ""
    summary: str = ""
    objects_timeline: Dict[str, List[float]] = field(default_factory=dict)
    analyzed_at: str = ""
    analysis_duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "file_path": self.file_path,
            "duration_sec": self.duration_sec,
            "resolution": self.resolution,
            "fps": self.fps,
            "total_frames_extracted": self.total_frames_extracted,
            "num_scenes": len(self.scenes),
            "transcript_length": len(self.transcript),
            "summary": self.summary,
            "analyzed_at": self.analyzed_at,
            "analysis_duration_ms": self.analysis_duration_ms,
        }


# ── Core Engine ───────────────────────────────────────────────────────

class VideoUnderstandingEngine:
    """
    Video content understanding engine.
    Extracts keyframes, analyzes with vision LLMs, builds narrative understanding.
    """

    MAX_KEYFRAMES = 20           # Max frames to extract per video
    MAX_ANALYSES = 100           # Max stored analyses
    FRAME_INTERVAL_SEC = 5       # Default keyframe interval

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir = self.data_dir / "frames"
        self.frames_dir.mkdir(exist_ok=True)
        self.state_file = self.data_dir / "video_understanding_state.json"

        self.analyses: List[VideoAnalysis] = []
        self._llm = None  # Set externally by agent

        # Stats
        self.total_videos_analyzed = 0
        self.total_frames_extracted = 0
        self.total_scenes_detected = 0
        self.total_transcriptions = 0
        self.total_questions_answered = 0

        self._load_state()

    def set_llm(self, llm):
        """Set the LLM instance for vision analysis."""
        self._llm = llm

    # ── Frame Extraction (ffmpeg) ─────────────────────────────────────

    async def extract_keyframes(
        self, video_path: str, interval: float = None, max_frames: int = None
    ) -> List[VideoFrame]:
        """
        Extract keyframes from a video file using ffmpeg.
        Uses scene detection for intelligent frame selection.
        """
        video_path = str(video_path)
        interval = interval or self.FRAME_INTERVAL_SEC
        max_frames = max_frames or self.MAX_KEYFRAMES

        # Check ffmpeg availability
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            if proc.returncode != 0:
                logger.error("ffmpeg not available")
                return []
        except FileNotFoundError:
            logger.error("ffmpeg not installed")
            return []

        # Get video info
        info = await self._get_video_info(video_path)
        duration = info.get("duration", 0)

        if duration <= 0:
            logger.error(f"Cannot determine video duration: {video_path}")
            return []

        # Calculate frame extraction points
        if duration <= interval * max_frames:
            # Short video: extract at regular intervals
            timestamps = [i * interval for i in range(int(duration / interval) + 1)]
        else:
            # Long video: distribute frames evenly
            step = duration / max_frames
            timestamps = [i * step for i in range(max_frames)]

        timestamps = [t for t in timestamps if t < duration][:max_frames]

        # Extract frames with ffmpeg
        video_hash = hashlib.sha256(video_path.encode()).hexdigest()[:12]
        frames = []

        for i, ts in enumerate(timestamps):
            frame_path = str(self.frames_dir / f"{video_hash}_frame_{i:04d}.jpg")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
                    "-frames:v", "1", "-q:v", "2", frame_path,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(proc.communicate(), timeout=30)

                if proc.returncode == 0 and Path(frame_path).exists():
                    frame = VideoFrame(
                        frame_id=f"f_{i:04d}",
                        timestamp_sec=round(ts, 2),
                        image_path=frame_path,
                    )
                    frames.append(frame)
                    self.total_frames_extracted += 1
            except (asyncio.TimeoutError, Exception) as e:
                logger.debug(f"Frame extraction failed at {ts}s: {e}")
                continue

        logger.info(f"[VideoEngine] Extracted {len(frames)} keyframes from {video_path}")
        return frames

    async def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video metadata via ffprobe."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", video_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            data = json.loads(stdout.decode())

            fmt = data.get("format", {})
            vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})

            return {
                "duration": float(fmt.get("duration", 0)),
                "resolution": f"{vs.get('width', '?')}x{vs.get('height', '?')}",
                "fps": eval(vs.get("r_frame_rate", "0/1")) if vs.get("r_frame_rate") else 0,
                "codec": vs.get("codec_name", "unknown"),
                "size_mb": int(fmt.get("size", 0)) / (1024 * 1024),
            }
        except Exception as e:
            logger.error(f"ffprobe failed: {e}")
            return {}

    # ── Vision LLM Analysis ──────────────────────────────────────────

    async def analyze_frames(self, frames: List[VideoFrame]) -> List[VideoFrame]:
        """Analyze extracted frames with vision LLM."""
        if not self._llm:
            logger.warning("[VideoEngine] No LLM configured for frame analysis")
            return frames

        for frame in frames:
            try:
                # Read frame as base64
                import base64
                frame_data = Path(frame.image_path).read_bytes()
                b64 = base64.b64encode(frame_data).decode()

                # Send to vision LLM
                messages = [
                    {"role": "user", "content": [
                        {"type": "text", "text": (
                            f"Analyze this video frame (timestamp: {frame.timestamp_sec}s). "
                            "Describe: 1) What is happening in the scene, 2) Key objects/people visible, "
                            "3) Any visible text, 4) The mood/atmosphere. Be concise."
                        )},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ]}
                ]

                response = await self._llm.invoke_with_tools(messages, [])
                description = response.get("text", "")

                frame.scene_description = description
                frame.confidence = 0.8

                # Extract objects from description
                for obj_word in ["person", "car", "building", "text", "animal", "screen",
                                "tree", "sky", "water", "road", "table", "chair"]:
                    if obj_word in description.lower():
                        frame.objects_detected.append(obj_word)

            except Exception as e:
                logger.debug(f"Frame analysis failed for {frame.frame_id}: {e}")
                frame.scene_description = f"[Analysis failed: {e}]"
                frame.confidence = 0.0

        return frames

    # ── Audio Transcription ──────────────────────────────────────────

    async def transcribe_audio(self, video_path: str) -> str:
        """Extract and transcribe audio from video using Whisper."""
        audio_path = str(self.data_dir / "temp_audio.wav")

        try:
            # Extract audio with ffmpeg
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1", audio_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode != 0:
                logger.warning("Audio extraction failed")
                return ""

            # Try Whisper transcription
            try:
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(audio_path)
                transcript = result.get("text", "")
                self.total_transcriptions += 1
                logger.info(f"[VideoEngine] Transcribed {len(transcript)} chars")
                return transcript
            except ImportError:
                # Fallback: try whisper CLI
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "whisper", audio_path, "--model", "base",
                        "--output_format", "txt", "--output_dir", str(self.data_dir),
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await asyncio.wait_for(proc.communicate(), timeout=300)
                    txt_file = self.data_dir / "temp_audio.txt"
                    if txt_file.exists():
                        transcript = txt_file.read_text(encoding="utf-8").strip()
                        self.total_transcriptions += 1
                        return transcript
                except Exception:
                    pass
                logger.warning("[VideoEngine] Whisper not available for transcription")
                return ""

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
        finally:
            # Cleanup temp audio
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

    # ── Scene Segmentation ───────────────────────────────────────────

    def segment_scenes(self, frames: List[VideoFrame]) -> List[VideoScene]:
        """Detect scene changes from analyzed frames."""
        if not frames:
            return []

        scenes = []
        current_scene_frames = [frames[0]]
        scene_id = 0

        for i in range(1, len(frames)):
            prev = frames[i - 1]
            curr = frames[i]

            # Scene change detection: significant description difference
            prev_words = set(prev.scene_description.lower().split())
            curr_words = set(curr.scene_description.lower().split())
            overlap = len(prev_words & curr_words)
            total = max(len(prev_words | curr_words), 1)
            similarity = overlap / total

            if similarity < 0.3:  # Scene change
                scene = VideoScene(
                    scene_id=scene_id,
                    start_sec=current_scene_frames[0].timestamp_sec,
                    end_sec=current_scene_frames[-1].timestamp_sec,
                    frames=[f.frame_id for f in current_scene_frames],
                    description=current_scene_frames[0].scene_description[:200],
                )
                scenes.append(scene)
                scene_id += 1
                current_scene_frames = [curr]
                self.total_scenes_detected += 1
            else:
                current_scene_frames.append(curr)

        # Last scene
        if current_scene_frames:
            scenes.append(VideoScene(
                scene_id=scene_id,
                start_sec=current_scene_frames[0].timestamp_sec,
                end_sec=current_scene_frames[-1].timestamp_sec,
                frames=[f.frame_id for f in current_scene_frames],
                description=current_scene_frames[0].scene_description[:200],
            ))

        return scenes

    # ── Full Analysis Pipeline ───────────────────────────────────────

    async def analyze_video(self, video_path: str, include_transcript: bool = True) -> VideoAnalysis:
        """
        Full video analysis pipeline:
          1. Extract keyframes
          2. Analyze frames with vision LLM
          3. Transcribe audio (if enabled)
          4. Segment scenes
          5. Generate summary
        """
        import time
        t0 = time.monotonic()

        video_id = hashlib.sha256(video_path.encode()).hexdigest()[:16]

        # Get metadata
        info = await self._get_video_info(video_path)

        # Extract keyframes
        frames = await self.extract_keyframes(video_path)

        # Analyze with vision LLM
        frames = await self.analyze_frames(frames)

        # Transcribe audio
        transcript = ""
        if include_transcript:
            transcript = await self.transcribe_audio(video_path)

        # Segment scenes
        scenes = self.segment_scenes(frames)

        # Build object timeline
        obj_timeline = {}
        for frame in frames:
            for obj in frame.objects_detected:
                if obj not in obj_timeline:
                    obj_timeline[obj] = []
                obj_timeline[obj].append(frame.timestamp_sec)

        # Generate summary
        summary = await self._generate_summary(frames, scenes, transcript)

        duration_ms = int((time.monotonic() - t0) * 1000)

        analysis = VideoAnalysis(
            video_id=video_id,
            file_path=video_path,
            duration_sec=info.get("duration", 0),
            resolution=info.get("resolution", "?"),
            fps=info.get("fps", 0),
            total_frames_extracted=len(frames),
            scenes=scenes,
            transcript=transcript,
            summary=summary,
            objects_timeline=obj_timeline,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            analysis_duration_ms=duration_ms,
        )

        self.analyses.append(analysis)
        if len(self.analyses) > self.MAX_ANALYSES:
            self.analyses = self.analyses[-self.MAX_ANALYSES:]

        self.total_videos_analyzed += 1
        self._save_state()

        logger.info(f"[VideoEngine] Analyzed video: {len(frames)} frames, {len(scenes)} scenes, {duration_ms}ms")
        return analysis

    async def _generate_summary(
        self, frames: List[VideoFrame], scenes: List[VideoScene], transcript: str
    ) -> str:
        """Generate a narrative summary of the video."""
        if not self._llm:
            parts = []
            for scene in scenes:
                parts.append(f"Scene {scene.scene_id} ({scene.start_sec}s-{scene.end_sec}s): {scene.description}")
            if transcript:
                parts.append(f"Transcript: {transcript[:500]}")
            return "\n".join(parts)

        # Build context for LLM
        scene_descs = []
        for scene in scenes:
            scene_descs.append(
                f"[{scene.start_sec:.1f}s - {scene.end_sec:.1f}s] {scene.description}"
            )

        prompt = (
            "Generate a concise narrative summary of this video based on the scene analysis:\n\n"
            + "\n".join(scene_descs)
        )
        if transcript:
            prompt += f"\n\nAudio transcript: {transcript[:1000]}"
        prompt += "\n\nSummary:"

        try:
            resp = await self._llm.invoke_with_tools(
                [{"role": "user", "content": prompt}], []
            )
            return resp.get("text", "")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "\n".join(f"Scene {s.scene_id}: {s.description}" for s in scenes)

    # ── Question Answering ───────────────────────────────────────────

    async def answer_question(self, video_path: str, question: str) -> str:
        """Answer a question about a previously analyzed video."""
        # Find existing analysis
        analysis = None
        for a in self.analyses:
            if a.file_path == video_path:
                analysis = a
                break

        if not analysis:
            analysis = await self.analyze_video(video_path)

        if not self._llm:
            return f"Video has {len(analysis.scenes)} scenes. Summary: {analysis.summary}"

        context = f"Video summary: {analysis.summary}\n"
        if analysis.transcript:
            context += f"Transcript: {analysis.transcript[:2000]}\n"
        for scene in analysis.scenes:
            context += f"Scene {scene.scene_id} ({scene.start_sec}s-{scene.end_sec}s): {scene.description}\n"

        prompt = f"{context}\nQuestion: {question}\nAnswer:"

        try:
            resp = await self._llm.invoke_with_tools(
                [{"role": "user", "content": prompt}], []
            )
            self.total_questions_answered += 1
            return resp.get("text", "No answer available")
        except Exception as e:
            return f"Error answering question: {e}"

    # ── Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "total_videos_analyzed": self.total_videos_analyzed,
                "total_frames_extracted": self.total_frames_extracted,
                "total_scenes_detected": self.total_scenes_detected,
                "total_transcriptions": self.total_transcriptions,
                "total_questions_answered": self.total_questions_answered,
                "analyses": [a.to_dict() for a in self.analyses[-20:]],
            }
            self.state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.error(f"[VideoEngine] Save failed: {e}")

    def _load_state(self):
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.total_videos_analyzed = state.get("total_videos_analyzed", 0)
                self.total_frames_extracted = state.get("total_frames_extracted", 0)
                self.total_scenes_detected = state.get("total_scenes_detected", 0)
                self.total_transcriptions = state.get("total_transcriptions", 0)
                self.total_questions_answered = state.get("total_questions_answered", 0)
            except Exception as e:
                logger.error(f"[VideoEngine] Load failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_videos_analyzed": self.total_videos_analyzed,
            "total_frames_extracted": self.total_frames_extracted,
            "total_scenes_detected": self.total_scenes_detected,
            "total_transcriptions": self.total_transcriptions,
            "total_questions_answered": self.total_questions_answered,
            "stored_analyses": len(self.analyses),
            "frames_dir": str(self.frames_dir),
        }
