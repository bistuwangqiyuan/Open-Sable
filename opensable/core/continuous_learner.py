"""
Continuous Learner — WORLD FIRST
Continuous learning from every interaction, permanently adapting
behavior, knowledge, and strategies. The agent evolves after
every single conversation and action.
"""
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
from collections import Counter

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class LearningEvent:
    id: str
    event_type: str  # interaction, error, success, feedback, observation
    source: str
    lesson: str
    confidence: float = 0.5
    timestamp: str = ""
    applied_count: int = 0
    tags: List[str] = field(default_factory=list)

@dataclass
class BehaviorRule:
    id: str
    condition: str
    action: str
    priority: int = 50  # 0-100, higher = more important
    success_count: int = 0
    failure_count: int = 0
    created_at: str = ""
    source_event_id: str = ""

@dataclass
class KnowledgeNode:
    id: str
    topic: str
    content: str
    confidence: float = 0.5
    access_count: int = 0
    last_accessed: str = ""
    related_nodes: List[str] = field(default_factory=list)

@dataclass
class AdaptationMetric:
    metric: str
    before_value: float = 0.0
    after_value: float = 0.0
    improvement_pct: float = 0.0
    timestamp: str = ""

# ── Core Engine ───────────────────────────────────────────────────────

class ContinuousLearner:
    """
    Continuous learning engine that evolves with every interaction.
    Extracts lessons from experience, builds behavior rules,
    grows knowledge graphs, and permanently adapts the agent.
    """

    MAX_EVENTS = 1000
    MAX_RULES = 200
    MAX_KNOWLEDGE = 500
    CONFIDENCE_DECAY = 0.01  # Confidence decays slightly over time for unused knowledge
    CONFIDENCE_BOOST = 0.05  # Confidence increases when knowledge is accessed/validated

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "continuous_learner_state.json"

        self.events: List[LearningEvent] = []
        self.rules: List[BehaviorRule] = []
        self.knowledge: List[KnowledgeNode] = []
        self.adaptations: List[AdaptationMetric] = []
        self.total_lessons = 0
        self.total_rules_created = 0
        self.total_adaptations = 0
        self.interaction_count = 0
        self.topic_frequency: Dict[str, int] = {}

        self._load_state()

    async def learn_from_interaction(self, user_input: str, agent_response: str,
                                      outcome: str = "unknown", llm=None) -> LearningEvent:
        """Learn from a single interaction."""
        self.interaction_count += 1
        event_id = hashlib.sha256(
            f"learn_{self.interaction_count}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        lesson = f"Interaction #{self.interaction_count}"
        tags = []
        confidence = 0.5

        if llm:
            try:
                prompt = (
                    f"Extract a concise, actionable lesson from this interaction.\n"
                    f"User: {user_input[:300]}\n"
                    f"Agent: {agent_response[:300]}\n"
                    f"Outcome: {outcome}\n\n"
                    f"Reply as JSON: {{'lesson': '...', 'tags': ['...'], 'confidence': 0.0-1.0}}"
                )
                result = await llm.chat_raw(prompt, max_tokens=200)
                try:
                    parsed = json.loads(result.strip())
                    lesson = parsed.get("lesson", lesson)
                    tags = parsed.get("tags", [])
                    confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.5))))
                except json.JSONDecodeError:
                    lesson = result.strip()[:200]
            except Exception as e:
                logger.debug(f"Learning extraction failed: {e}")

        event = LearningEvent(
            id=event_id, event_type="interaction", source="conversation",
            lesson=lesson, confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(), tags=tags,
        )

        self.events.append(event)
        self.total_lessons += 1

        # Update topic frequency
        for tag in tags:
            self.topic_frequency[tag] = self.topic_frequency.get(tag, 0) + 1

        self._trim_events()
        self._save_state()
        return event

    def learn_from_error(self, error: str, context: str, fix: str = "") -> LearningEvent:
        """Learn from an error that occurred."""
        event_id = hashlib.sha256(f"err_{error}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        lesson = f"Error: {error[:100]}. Context: {context[:100]}."
        if fix:
            lesson += f" Fix: {fix[:100]}"

        event = LearningEvent(
            id=event_id, event_type="error", source="system",
            lesson=lesson, confidence=0.7,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tags=["error", "debugging"],
        )
        self.events.append(event)
        self.total_lessons += 1
        self._trim_events()
        self._save_state()
        return event

    def learn_from_success(self, action: str, result: str) -> LearningEvent:
        """Learn from a successful action."""
        event_id = hashlib.sha256(f"ok_{action}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        event = LearningEvent(
            id=event_id, event_type="success", source="agent",
            lesson=f"Success: {action[:100]} => {result[:100]}",
            confidence=0.8,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tags=["success", "reinforcement"],
        )
        self.events.append(event)
        self.total_lessons += 1
        self._trim_events()
        self._save_state()
        return event

    async def create_behavior_rule(self, condition: str, action: str,
                                    priority: int = 50, source_event_id: str = "") -> BehaviorRule:
        """Create a new behavior rule from learning."""
        rule_id = hashlib.sha256(f"rule_{condition}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        rule = BehaviorRule(
            id=rule_id, condition=condition, action=action,
            priority=priority, source_event_id=source_event_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.rules.append(rule)
        self.total_rules_created += 1

        # Sort by priority
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        if len(self.rules) > self.MAX_RULES:
            self.rules = self.rules[:self.MAX_RULES]

        self._save_state()
        return rule

    def find_applicable_rules(self, context: str) -> List[BehaviorRule]:
        """Find behavior rules applicable to the current context."""
        applicable = []
        context_lower = context.lower()
        for rule in self.rules:
            if any(word in context_lower for word in rule.condition.lower().split()):
                applicable.append(rule)
        return applicable[:10]

    def record_rule_outcome(self, rule_id: str, success: bool):
        """Record the outcome of applying a rule."""
        rule = next((r for r in self.rules if r.id == rule_id), None)
        if rule:
            if success:
                rule.success_count += 1
                rule.priority = min(100, rule.priority + 1)
            else:
                rule.failure_count += 1
                rule.priority = max(0, rule.priority - 2)
            self._save_state()

    def add_knowledge(self, topic: str, content: str, confidence: float = 0.5,
                       related: Optional[List[str]] = None) -> KnowledgeNode:
        """Add a knowledge node to the graph."""
        node_id = hashlib.sha256(f"know_{topic}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        # Check for existing knowledge on same topic
        existing = next((k for k in self.knowledge if k.topic.lower() == topic.lower()), None)
        if existing:
            # Merge knowledge
            existing.content = f"{existing.content}\n---\n{content}"
            existing.confidence = min(1.0, existing.confidence + self.CONFIDENCE_BOOST)
            existing.access_count += 1
            existing.last_accessed = datetime.now(timezone.utc).isoformat()
            if related:
                existing.related_nodes.extend(r for r in related if r not in existing.related_nodes)
            self._save_state()
            return existing

        node = KnowledgeNode(
            id=node_id, topic=topic, content=content,
            confidence=confidence,
            last_accessed=datetime.now(timezone.utc).isoformat(),
            related_nodes=related or [],
        )
        self.knowledge.append(node)
        if len(self.knowledge) > self.MAX_KNOWLEDGE:
            # Remove lowest confidence nodes
            self.knowledge.sort(key=lambda k: k.confidence, reverse=True)
            self.knowledge = self.knowledge[:self.MAX_KNOWLEDGE]
        self._save_state()
        return node

    def query_knowledge(self, query: str, top_k: int = 5) -> List[KnowledgeNode]:
        """Search knowledge nodes by keyword matching."""
        query_lower = query.lower()
        scored = []
        for node in self.knowledge:
            score = 0
            if query_lower in node.topic.lower():
                score += 3
            if query_lower in node.content.lower():
                score += 1
            score += node.confidence
            if score > 0:
                scored.append((score, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [node for _, node in scored[:top_k]]

        # Boost confidence of accessed nodes
        for node in results:
            node.access_count += 1
            node.confidence = min(1.0, node.confidence + self.CONFIDENCE_BOOST)
            node.last_accessed = datetime.now(timezone.utc).isoformat()

        if results:
            self._save_state()
        return results

    async def synthesize_learnings(self, llm=None) -> Dict[str, Any]:
        """Synthesize recent learnings into insights and new rules."""
        synthesis = {
            "total_lessons": self.total_lessons,
            "interaction_count": self.interaction_count,
            "top_topics": dict(Counter(self.topic_frequency).most_common(10)),
            "rules_count": len(self.rules),
            "knowledge_nodes": len(self.knowledge),
            "insights": [],
        }

        if llm and self.events:
            try:
                recent = self.events[-15:]
                lessons = [{"type": e.event_type, "lesson": e.lesson, "conf": e.confidence} for e in recent]
                prompt = (
                    f"Synthesize these recent learning events into 3 key insights. "
                    f"For each insight, suggest a behavior rule (condition -> action). "
                    f"Reply as JSON array of {{'insight': '...', 'condition': '...', 'action': '...'}}.\n\n"
                    f"{json.dumps(lessons)}"
                )
                result = await llm.chat_raw(prompt, max_tokens=500)
                try:
                    insights = json.loads(result.strip())
                    if isinstance(insights, list):
                        synthesis["insights"] = insights[:5]
                        for ins in insights[:3]:
                            if ins.get("condition") and ins.get("action"):
                                await self.create_behavior_rule(
                                    ins["condition"], ins["action"], priority=60,
                                )
                except json.JSONDecodeError:
                    synthesis["insights"] = [result.strip()[:300]]
            except Exception as e:
                logger.debug(f"Synthesis failed: {e}")

        self.total_adaptations += 1
        self._save_state()
        return synthesis

    def _trim_events(self):
        if len(self.events) > self.MAX_EVENTS:
            self.events = self.events[-self.MAX_EVENTS:]

    def get_stats(self) -> Dict[str, Any]:
        avg_confidence = (
            sum(e.confidence for e in self.events[-50:]) / min(len(self.events), 50)
            if self.events else 0
        )
        return {
            "total_lessons": self.total_lessons,
            "interaction_count": self.interaction_count,
            "behavior_rules": len(self.rules),
            "knowledge_nodes": len(self.knowledge),
            "total_adaptations": self.total_adaptations,
            "avg_confidence": round(avg_confidence, 3),
            "top_topics": dict(Counter(self.topic_frequency).most_common(5)),
            "rules_effectiveness": round(
                sum(r.success_count for r in self.rules) /
                max(sum(r.success_count + r.failure_count for r in self.rules), 1) * 100, 1
            ),
        }

    def _save_state(self):
        try:
            state = {
                "events": [asdict(e) for e in self.events[-200:]],
                "rules": [asdict(r) for r in self.rules],
                "knowledge": [asdict(k) for k in self.knowledge],
                "adaptations": [asdict(a) for a in self.adaptations[-50:]],
                "total_lessons": self.total_lessons,
                "total_rules_created": self.total_rules_created,
                "total_adaptations": self.total_adaptations,
                "interaction_count": self.interaction_count,
                "topic_frequency": dict(Counter(self.topic_frequency).most_common(100)),
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"ContinuousLearner save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.events = [LearningEvent(**e) for e in state.get("events", [])]
                self.rules = [BehaviorRule(**r) for r in state.get("rules", [])]
                self.knowledge = [KnowledgeNode(**k) for k in state.get("knowledge", [])]
                self.adaptations = [AdaptationMetric(**a) for a in state.get("adaptations", [])]
                self.total_lessons = state.get("total_lessons", 0)
                self.total_rules_created = state.get("total_rules_created", 0)
                self.total_adaptations = state.get("total_adaptations", 0)
                self.interaction_count = state.get("interaction_count", 0)
                self.topic_frequency = state.get("topic_frequency", {})
        except Exception as e:
            logger.debug(f"ContinuousLearner load failed: {e}")
