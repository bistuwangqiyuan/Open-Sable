"""
Complete Multimodal Voice-Enabled Agentic AI Example

Demonstrates:
- Voice commands with STT/TTS
- Image understanding
- Multi-device sync
- Skills marketplace
- Full Agentic AI integration
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime

from opensable.core.agi_integration import AGIAgent
from opensable.core.voice_interface import VoiceInterface, WhisperModel, TTSVoice
from opensable.core.multimodal_agi import MultimodalAGI, MultimodalInput, VisionTask
from opensable.core.multi_device_sync import MultiDeviceSync, SyncScope
from opensable.core.skills_marketplace import SkillManager, SkillRegistry, SkillCategory
from opensable.core.goal_system import GoalPriority

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def demo_voice_controlled_agi():
    """Demo: Voice-controlled Agentic AI with multimodal capabilities."""

    print("\n" + "=" * 60)
    print("1. VOICE-CONTROLLED MULTIMODAL AGENTIC AI")
    print("=" * 60)

    # Initialize voice interface
    print("\n🎤 Initializing voice interface...")
    voice = VoiceInterface(
        whisper_model=WhisperModel.BASE, tts_voice=TTSVoice.EN_US_FEMALE, language="en"
    )

    # Initialize multimodal Agentic AI
    print("🧠 Initializing multimodal Agentic AI...")
    agi = MultimodalAGI(device="cpu")

    # Voice command handler that uses AGI
    async def voice_agi_handler(text: str) -> str:
        """Handle voice commands with Agentic AI."""
        text_lower = text.lower()

        if "analyze image" in text_lower or "what do you see" in text_lower:
            test_image = "./test_image.jpg"
            if Path(test_image).exists():
                caption = await agi.vision.analyze_image(test_image, VisionTask.IMAGE_CAPTION)
                return f"I see {caption.caption}"
            return "I don't have any image to analyze right now."

        elif "set goal" in text_lower or "create goal" in text_lower:
            return "Goal system activated. What would you like to accomplish?"

        elif "help" in text_lower:
            return "I can help you with voice commands, image analysis, goal setting, and more. What do you need?"

        else:
            return f"I heard you say: {text}. How can I help you with that?"

    # Simulate voice command
    print("\n💬 Simulating voice command...")
    print("  User: 'What can you help me with?'")

    response = await voice_agi_handler("What can you help me with?")
    print(f"  Sable: {response}")

    # Synthesize voice response
    print("\n🔊 Generating voice response...")
    synthesis = await voice.tts.synthesize(response)
    print(f"  ✅ Generated {synthesis.duration:.2f}s of audio")

    print("\n✅ Voice-controlled Agentic AI demo complete")


async def demo_multimodal_reasoning():
    """Demo: Multimodal reasoning with image + text."""

    print("\n" + "=" * 60)
    print("2. MULTIMODAL REASONING")
    print("=" * 60)

    print("\n🔀 Processing multimodal input...")

    agi = MultimodalAGI(device="cpu")

    # Create multimodal input
    multimodal_input = MultimodalInput(
        text="Analyze this scene and tell me what's happening",
        image=None,  # Would be actual image bytes
        metadata={"timestamp": datetime.utcnow().isoformat()},
    )

    # Process
    result = await agi.process_multimodal_input(
        multimodal_input, task_description="Provide detailed scene analysis"
    )

    print(f"  📝 Response: {result.text_response[:150]}...")
    print(f"  🎯 Confidence: {result.confidence:.2%}")
    if result.cross_modal_insights:
        print(f"  💡 Insights: {len(result.cross_modal_insights)} generated")

    print("\n✅ Multimodal reasoning demo complete")


async def demo_multi_device_voice_sync():
    """Demo: Voice commands synced across devices."""

    print("\n" + "=" * 60)
    print("3. MULTI-DEVICE VOICE SYNC")
    print("=" * 60)

    # Initialize sync for two devices
    print("\n📱 Initializing devices...")

    desktop_sync = MultiDeviceSync(device_name="Desktop")
    mobile_sync = MultiDeviceSync(device_name="Mobile")

    # Register and trust devices
    await desktop_sync.register_device("Mobile", "mobile")
    await mobile_sync.register_device("Desktop", "desktop")
    await desktop_sync.trust_device(mobile_sync.device_id)
    await mobile_sync.trust_device(desktop_sync.device_id)

    print("  ✅ Devices paired and trusted")

    # Sync voice settings
    print("\n🔧 Syncing voice preferences...")

    voice_settings = {
        "preferred_voice": "en_US-lessac-medium",
        "speech_rate": 1.0,
        "volume": 0.8,
        "auto_listen": True,
    }

    await desktop_sync.sync_item(
        scope=SyncScope.SETTINGS, item_id="voice_preferences", data=voice_settings, version=1
    )

    print("  ✅ Voice settings synced to all devices")

    # Sync conversation
    print("\n💬 Syncing conversation...")

    conversation = {
        "messages": [
            {
                "role": "user",
                "content": "What is the weather like?",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "role": "assistant",
                "content": "I can check the weather for you.",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]
    }

    await mobile_sync.sync_item(
        scope=SyncScope.CONVERSATIONS, item_id="conv_voice_001", data=conversation, version=1
    )

    print("  ✅ Conversation synced across devices")

    # Show sync status
    desktop_status = desktop_sync.get_sync_status()
    mobile_status = mobile_sync.get_sync_status()

    print("\n📊 Sync Status:")
    print(f"  Desktop: {desktop_status['pending_items']} pending")
    print(f"  Mobile: {mobile_status['pending_items']} pending")

    print("\n✅ Multi-device sync demo complete")


async def demo_skills_marketplace_for_voice():
    """Demo: Install voice-related skills from marketplace."""

    print("\n" + "=" * 60)
    print("4. SKILLS MARKETPLACE FOR VOICE")
    print("=" * 60)

    # Initialize marketplace
    print("\n🏪 Initializing marketplace...")

    registry = SkillRegistry()
    manager = SkillManager(registry=registry)

    # Search for voice-related skills
    print("\n🔍 Searching for voice skills...")

    voice_skills = await registry.search_skills(tags=["voice", "speech", "audio"])

    # Create mock voice skill
    from core.skills_marketplace import SkillMetadata

    voice_skill = SkillMetadata(
        skill_id="voice-commands-pro",
        name="Voice Commands Pro",
        version="1.0.0",
        author="Voice Labs",
        description="Advanced voice command recognition with custom wake words",
        category=SkillCategory.PRODUCTIVITY,
        tags=["voice", "commands", "wake-word"],
        dependencies=["pvporcupine", "webrtcvad"],
        rating=4.7,
        reviews_count=85,
        downloads=920,
        verified=True,
    )

    print(f"  Found skill: {voice_skill.name}")
    print(f"    Rating: ⭐ {voice_skill.rating}")
    print(f"    Description: {voice_skill.description}")

    # Install skill
    print(f"\n📥 Installing {voice_skill.name}...")

    installed = await manager.install_skill(voice_skill.skill_id)
    print(f"  ✅ Installed: {installed.metadata.name} v{installed.metadata.version}")

    print("\n✅ Skills marketplace demo complete")


async def demo_complete_voice_agi_workflow():
    """Demo: Complete workflow combining all features."""

    print("\n" + "=" * 60)
    print("5. COMPLETE VOICE AGENTIC AI WORKFLOW")
    print("=" * 60)

    print("\n🚀 Initializing complete Agentic AI system...")

    # Initialize all components
    agi_agent = AGIAgent()
    voice = VoiceInterface(whisper_model=WhisperModel.BASE)
    multimodal = MultimodalAGI()
    sync = MultiDeviceSync(device_name="Main Device")

    print("  ✅ All components initialized")

    # Scenario: User gives voice command to analyze image and set goal
    print("\n📖 Scenario: Voice-driven multimodal task")
    print("  User says: 'Look at this image and create a goal to improve similar images'")

    # Step 1: Voice to text (simulated)
    user_command = "Look at this image and create a goal to improve similar images"
    print(f"\n1️⃣  Speech recognized: '{user_command}'")

    # Step 2: Analyze image
    print("2️⃣  Analyzing image...")
    test_image = "./test_image.jpg"

    if Path(test_image).exists():
        caption = await multimodal.vision.analyze_image(test_image, VisionTask.IMAGE_CAPTION)
        objects = await multimodal.vision.analyze_image(test_image, VisionTask.OBJECT_DETECTION)

        print(f"    Image analysis: {caption.caption}")
        if objects.objects:
            print(f"    Objects found: {len(objects.objects)}")
    else:
        print("    (Using mock image analysis)")
        caption_text = "A scenic landscape with mountains"

    # Step 3: Create goal using Agentic AI
    print("3️⃣  Creating goal...")

    goal = await agi_agent.set_goal(
        description="Enhance image quality and composition",
        success_criteria=["Image brightness optimized", "Composition balanced", "Colors enhanced"],
        priority=GoalPriority.MEDIUM,
        auto_execute=False,
    )

    print(f"    ✅ Goal created: {goal['goal_id']}")
    print(f"    Sub-goals: {goal['sub_goals']}")

    # Step 4: Generate voice response
    print("4️⃣  Generating voice response...")

    response_text = f"I've analyzed the image and created a goal to enhance it. The image shows {caption_text if 'caption_text' in locals() else 'an interesting scene'}. I'll work on improving the brightness, composition, and colors."

    synthesis = await voice.tts.synthesize(response_text)
    print(f"    🔊 Voice response: {synthesis.duration:.2f}s audio")
    print(f"    💬 Text: '{response_text[:80]}...'")

    # Step 5: Sync to other devices
    print("5️⃣  Syncing to other devices...")

    await sync.sync_item(
        scope=SyncScope.GOALS,
        item_id=goal["goal_id"],
        data={
            "description": "Enhance image quality and composition",
            "status": "created",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    print("    ✅ Goal synced across devices")

    # Step 6: Store in memory
    print("6️⃣  Storing in memory...")

    agi_agent.memory.store_experience(
        event="User requested image enhancement via voice command",
        context={
            "image_analysis": caption_text if "caption_text" in locals() else "scene",
            "goal_created": goal["goal_id"],
            "interaction_type": "voice",
        },
        importance=agi_agent.memory.MemoryImportance.HIGH,
    )

    print("    ✅ Experience stored in episodic memory")

    print("\n✨ Complete workflow finished!")
    print("\n📊 System state:")
    status = agi_agent.get_status()
    print(
        f"  • Active goals: {len(status['subsystems']['goals'].get('by_status', {}).get('ACTIVE', []))}"
    )
    print(f"  • Memories: {status['subsystems']['memory']['episodic_count']} episodic")
    print(f"  • Sync pending: {sync.get_sync_status()['pending_items']} items")

    print("\n✅ Complete voice Agentic AI workflow demo finished")


async def main():
    """Run all demonstrations."""

    print("=" * 60)
    print("🎙️  SABLECORE - COMPLETE MULTIMODAL VOICE AGENTIC AI")
    print("=" * 60)
    print("\nDemonstrating:")
    print("  ✅ Voice interface (STT + TTS)")
    print("  ✅ Multimodal Agentic AI (vision + audio)")
    print("  ✅ Multi-device sync")
    print("  ✅ Skills marketplace")
    print("  ✅ Full Agentic AI integration")

    # Run demos
    await demo_voice_controlled_agi()
    await demo_multimodal_reasoning()
    await demo_multi_device_voice_sync()
    await demo_skills_marketplace_for_voice()
    await demo_complete_voice_agi_workflow()

    print("\n" + "=" * 60)
    print("🎉 ALL DEMONSTRATIONS COMPLETE")
    print("=" * 60)

    print("\n🚀 Open-Sable is now fully equipped with:")
    print("  🎤 Voice interface (Whisper STT + Piper TTS)")
    print("  👁️  Vision processing (BLIP, YOLO, OCR)")
    print("  🎵 Audio analysis (emotion, classification)")
    print("  🔀 Multimodal reasoning")
    print("  📱 Multi-device sync")
    print("  🏪 Skills marketplace")
    print("  🧠 Complete Agentic AI capabilities")

    print("\n💡 Next steps:")
    print("  • Install dependencies: pip install -r requirements.txt")
    print("  • Run voice interface: python -m core.voice_interface")
    print("  • Try examples: python examples/multimodal_voice_example.py")
    print("  • Build mobile app with Expo (coming soon)")


if __name__ == "__main__":
    asyncio.run(main())
