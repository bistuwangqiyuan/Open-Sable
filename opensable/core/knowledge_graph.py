"""
Knowledge Graph Engine

Real graph-based knowledge storage with NetworkX.
Entity extraction from conversations, relationship inference,
causal chain reasoning, and multi-hop question answering.

Features:
  1. Entity extraction — Identify people, places, concepts, events from text
  2. Relationship inference — LLM discovers connections between entities
  3. Graph traversal — Multi-hop reasoning across relationships
  4. Temporal awareness — Track when relationships were established/changed
  5. Causal chains — Follow cause→effect paths through the graph
  6. Community detection — Find clusters of related concepts
  7. Graph queries — Natural language queries over the knowledge graph
  8. JSON persistence — Serializable graph with full node/edge attributes
"""
import json
import logging
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Set, Tuple

logger = logging.getLogger(__name__)

# Try networkx but don't fail if not installed
try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False


# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class Entity:
    """A node in the knowledge graph."""
    entity_id: str
    name: str
    entity_type: str = "concept"    # person, place, concept, event, object, organization
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    first_seen: str = ""
    last_updated: str = ""
    mention_count: int = 0
    source: str = ""               # conversation, web, file, etc.
    importance: float = 0.5        # 0-1 scale

@dataclass
class Relationship:
    """An edge in the knowledge graph."""
    source_id: str
    target_id: str
    relation_type: str = "related_to"   # e.g. works_at, located_in, causes, part_of
    description: str = ""
    weight: float = 1.0
    confidence: float = 0.8
    established: str = ""
    last_confirmed: str = ""
    evidence: List[str] = field(default_factory=list)


# ── Core Engine ───────────────────────────────────────────────────────

class KnowledgeGraphEngine:
    """
    Real knowledge graph with NetworkX for graph algorithms.
    Extracts entities from conversations, infers relationships,
    supports multi-hop reasoning and causal chain queries.
    """

    MAX_ENTITIES = 10000
    MAX_RELATIONSHIPS = 50000

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "knowledge_graph_state.json"

        # Initialize graph
        if NX_AVAILABLE:
            self.graph = nx.DiGraph()
        else:
            self.graph = None

        # Entity/relationship stores (for serialization)
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []

        self._llm = None  # Set externally by agent

        # Stats
        self.total_entities_added = 0
        self.total_relationships_added = 0
        self.total_queries = 0
        self.total_extractions = 0
        self.total_traversals = 0

        self._load_state()

    def set_llm(self, llm):
        """Set LLM for entity extraction and relationship inference."""
        self._llm = llm

    # ── Entity Management ─────────────────────────────────────────────

    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        description: str = "",
        properties: Optional[Dict] = None,
        source: str = "conversation",
        importance: float = 0.5,
    ) -> Entity:
        """Add or update an entity in the graph."""
        entity_id = self._make_id(name)
        now = datetime.now(timezone.utc).isoformat()

        if entity_id in self.entities:
            # Update existing
            ent = self.entities[entity_id]
            ent.mention_count += 1
            ent.last_updated = now
            if description and len(description) > len(ent.description):
                ent.description = description
            if properties:
                ent.properties.update(properties)
            ent.importance = min(1.0, ent.importance + 0.05)
        else:
            # Create new
            ent = Entity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                description=description,
                properties=properties or {},
                first_seen=now,
                last_updated=now,
                mention_count=1,
                source=source,
                importance=importance,
            )
            self.entities[entity_id] = ent
            self.total_entities_added += 1

            # Add to NetworkX graph
            if self.graph is not None:
                self.graph.add_node(entity_id, **{
                    "name": name,
                    "type": entity_type,
                    "importance": importance,
                })

        # Enforce limit
        if len(self.entities) > self.MAX_ENTITIES:
            self._prune_entities()

        return ent

    def get_entity(self, name: str) -> Optional[Entity]:
        """Get entity by name."""
        return self.entities.get(self._make_id(name))

    def search_entities(self, query: str, limit: int = 10) -> List[Entity]:
        """Search entities by name or description."""
        query_lower = query.lower()
        scored = []
        for ent in self.entities.values():
            score = 0
            if query_lower in ent.name.lower():
                score += 3
            if query_lower in ent.description.lower():
                score += 1
            for prop_val in ent.properties.values():
                if query_lower in str(prop_val).lower():
                    score += 0.5
            if score > 0:
                scored.append((score * ent.importance, ent))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [e for _, e in scored[:limit]]

    # ── Relationship Management ───────────────────────────────────────

    def add_relationship(
        self,
        source_name: str,
        target_name: str,
        relation_type: str = "related_to",
        description: str = "",
        weight: float = 1.0,
        confidence: float = 0.8,
        evidence: Optional[List[str]] = None,
    ) -> Relationship:
        """Add a relationship between two entities (creates entities if needed)."""
        source_ent = self.add_entity(source_name)
        target_ent = self.add_entity(target_name)
        now = datetime.now(timezone.utc).isoformat()

        rel = Relationship(
            source_id=source_ent.entity_id,
            target_id=target_ent.entity_id,
            relation_type=relation_type,
            description=description,
            weight=weight,
            confidence=confidence,
            established=now,
            last_confirmed=now,
            evidence=evidence or [],
        )

        # Check for duplicate
        existing = self._find_relationship(source_ent.entity_id, target_ent.entity_id, relation_type)
        if existing:
            existing.weight += 0.1
            existing.last_confirmed = now
            existing.confidence = min(1.0, existing.confidence + 0.05)
            if evidence:
                existing.evidence.extend(evidence)
                existing.evidence = existing.evidence[-10:]  # Keep last 10
            return existing

        self.relationships.append(rel)
        self.total_relationships_added += 1

        # Add to NetworkX
        if self.graph is not None:
            self.graph.add_edge(
                source_ent.entity_id, target_ent.entity_id,
                relation=relation_type, weight=weight, confidence=confidence,
            )

        # Enforce limit
        if len(self.relationships) > self.MAX_RELATIONSHIPS:
            self.relationships = sorted(
                self.relationships, key=lambda r: r.confidence, reverse=True
            )[:self.MAX_RELATIONSHIPS]

        return rel

    def _find_relationship(self, src_id: str, tgt_id: str, rtype: str) -> Optional[Relationship]:
        for r in self.relationships:
            if r.source_id == src_id and r.target_id == tgt_id and r.relation_type == rtype:
                return r
        return None

    def get_connections(self, name: str, depth: int = 1) -> Dict[str, Any]:
        """Get all entities connected to the given entity up to N hops."""
        entity_id = self._make_id(name)
        if entity_id not in self.entities:
            return {"error": f"Entity '{name}' not found"}

        self.total_traversals += 1

        if self.graph is not None and entity_id in self.graph:
            # Use NetworkX BFS
            visited = set()
            layers = {}
            current = {entity_id}

            for d in range(depth):
                next_layer = set()
                layer_data = []
                for node in current:
                    if node in visited:
                        continue
                    visited.add(node)
                    for neighbor in list(self.graph.successors(node)) + list(self.graph.predecessors(node)):
                        if neighbor not in visited:
                            next_layer.add(neighbor)
                            edge = self.graph.get_edge_data(node, neighbor) or self.graph.get_edge_data(neighbor, node) or {}
                            ent = self.entities.get(neighbor)
                            layer_data.append({
                                "entity": ent.name if ent else neighbor,
                                "type": ent.entity_type if ent else "unknown",
                                "relation": edge.get("relation", "related_to"),
                                "confidence": edge.get("confidence", 0),
                            })
                layers[f"hop_{d + 1}"] = layer_data
                current = next_layer

            return {
                "center": name,
                "total_connections": sum(len(v) for v in layers.values()),
                "layers": layers,
            }
        else:
            # Fallback: manual traversal
            results = []
            for r in self.relationships:
                if r.source_id == entity_id or r.target_id == entity_id:
                    other_id = r.target_id if r.source_id == entity_id else r.source_id
                    other_ent = self.entities.get(other_id)
                    results.append({
                        "entity": other_ent.name if other_ent else other_id,
                        "relation": r.relation_type,
                        "confidence": r.confidence,
                    })
            return {"center": name, "total_connections": len(results), "connections": results}

    # ── Graph Algorithms ─────────────────────────────────────────────

    def find_path(self, from_name: str, to_name: str) -> List[str]:
        """Find shortest path between two entities."""
        if self.graph is None:
            return []
        src = self._make_id(from_name)
        tgt = self._make_id(to_name)
        try:
            path = nx.shortest_path(self.graph, src, tgt)
            return [self.entities[n].name if n in self.entities else n for n in path]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Try undirected
            try:
                path = nx.shortest_path(self.graph.to_undirected(), src, tgt)
                return [self.entities[n].name if n in self.entities else n for n in path]
            except Exception:
                return []

    def find_communities(self, min_size: int = 3) -> List[List[str]]:
        """Find clusters of related entities."""
        if self.graph is None or len(self.graph) < min_size:
            return []
        try:
            undirected = self.graph.to_undirected()
            communities = list(nx.connected_components(undirected))
            result = []
            for comm in communities:
                if len(comm) >= min_size:
                    names = [self.entities[n].name if n in self.entities else n for n in comm]
                    result.append(sorted(names))
            return sorted(result, key=len, reverse=True)
        except Exception:
            return []

    def get_most_connected(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get the most connected entities (highest degree centrality)."""
        if self.graph is None or len(self.graph) == 0:
            return []
        try:
            centrality = nx.degree_centrality(self.graph)
            top = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
            return [
                {
                    "entity": self.entities[n].name if n in self.entities else n,
                    "centrality": round(c, 4),
                    "connections": self.graph.degree(n),
                }
                for n, c in top
            ]
        except Exception:
            return []

    def get_causal_chain(self, entity_name: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Follow cause→effect chains from an entity."""
        entity_id = self._make_id(entity_name)
        chain = []
        visited = set()
        current = entity_id

        for _ in range(max_depth):
            if current in visited:
                break
            visited.add(current)
            # Find causal outgoing edges
            causal_rels = [
                r for r in self.relationships
                if r.source_id == current and r.relation_type in ("causes", "leads_to", "triggers", "results_in")
            ]
            if not causal_rels:
                break
            best = max(causal_rels, key=lambda r: r.confidence)
            target_ent = self.entities.get(best.target_id)
            chain.append({
                "from": self.entities[current].name if current in self.entities else current,
                "relation": best.relation_type,
                "to": target_ent.name if target_ent else best.target_id,
                "confidence": best.confidence,
            })
            current = best.target_id

        return chain

    # ── Entity Extraction (LLM) ──────────────────────────────────────

    async def extract_from_text(self, text: str, source: str = "conversation") -> Dict[str, Any]:
        """Extract entities and relationships from text using LLM."""
        self.total_extractions += 1

        if self._llm:
            return await self._llm_extract(text, source)
        else:
            return self._heuristic_extract(text, source)

    async def _llm_extract(self, text: str, source: str) -> Dict[str, Any]:
        """Use LLM to extract entities and relationships."""
        prompt = (
            "Extract entities and relationships from this text. "
            "Return valid JSON with this structure:\n"
            '{"entities": [{"name": "...", "type": "person|place|concept|event|organization|object", '
            '"description": "..."}], '
            '"relationships": [{"source": "...", "target": "...", "relation": "...", "description": "..."}]}\n\n'
            f"Text: {text[:2000]}\n\nJSON:"
        )

        try:
            resp = await self._llm.invoke_with_tools(
                [{"role": "user", "content": prompt}], []
            )
            raw = resp.get("text", "")

            # Parse JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                data = json.loads(json_match.group())
                entities_added = 0
                rels_added = 0

                for ent_data in data.get("entities", []):
                    self.add_entity(
                        name=ent_data.get("name", ""),
                        entity_type=ent_data.get("type", "concept"),
                        description=ent_data.get("description", ""),
                        source=source,
                    )
                    entities_added += 1

                for rel_data in data.get("relationships", []):
                    self.add_relationship(
                        source_name=rel_data.get("source", ""),
                        target_name=rel_data.get("target", ""),
                        relation_type=rel_data.get("relation", "related_to"),
                        description=rel_data.get("description", ""),
                        evidence=[text[:200]],
                    )
                    rels_added += 1

                self._save_state()
                return {"entities_added": entities_added, "relationships_added": rels_added}

        except Exception as e:
            logger.debug(f"[KnowledgeGraph] LLM extraction failed: {e}")

        return self._heuristic_extract(text, source)

    def _heuristic_extract(self, text: str, source: str) -> Dict[str, Any]:
        """Fallback: extract entities using simple heuristics."""
        import re
        entities_added = 0

        # Extract capitalized multi-word phrases (likely proper nouns)
        proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        for noun in set(proper_nouns):
            if len(noun) > 2 and noun not in ("The", "This", "That", "These", "Those"):
                self.add_entity(name=noun, entity_type="concept", source=source)
                entities_added += 1

        self._save_state()
        return {"entities_added": entities_added, "relationships_added": 0, "method": "heuristic"}

    # ── Natural Language Queries ──────────────────────────────────────

    async def query(self, question: str) -> str:
        """Answer a question using the knowledge graph."""
        self.total_queries += 1

        # Try to find relevant entities
        words = question.lower().split()
        relevant = []
        for word in words:
            if len(word) > 3:
                relevant.extend(self.search_entities(word, limit=3))

        if not relevant:
            return f"No relevant entities found in the knowledge graph for: {question}"

        # Build context from graph
        context_parts = []
        for ent in relevant[:5]:
            context_parts.append(f"Entity: {ent.name} ({ent.entity_type}) — {ent.description}")
            conns = self.get_connections(ent.name, depth=1)
            for layer_data in conns.get("layers", {}).values():
                for conn in layer_data[:5]:
                    context_parts.append(
                        f"  → {conn['relation']} → {conn['entity']} ({conn['type']})"
                    )

        context = "\n".join(context_parts)

        if self._llm:
            prompt = (
                f"Using this knowledge graph data, answer the question.\n\n"
                f"Graph data:\n{context}\n\n"
                f"Question: {question}\nAnswer:"
            )
            try:
                resp = await self._llm.invoke_with_tools(
                    [{"role": "user", "content": prompt}], []
                )
                return resp.get("text", context)
            except Exception:
                pass

        return f"Found {len(relevant)} relevant entities:\n{context}"

    # ── Utilities ─────────────────────────────────────────────────────

    def _make_id(self, name: str) -> str:
        return hashlib.sha256(name.lower().strip().encode()).hexdigest()[:16]

    def _prune_entities(self):
        """Remove least important entities when over limit."""
        sorted_ents = sorted(
            self.entities.values(),
            key=lambda e: e.importance * e.mention_count,
            reverse=True,
        )
        keep_ids = {e.entity_id for e in sorted_ents[:self.MAX_ENTITIES]}
        self.entities = {eid: e for eid, e in self.entities.items() if eid in keep_ids}
        self.relationships = [
            r for r in self.relationships
            if r.source_id in keep_ids and r.target_id in keep_ids
        ]

    # ── Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "entities": {eid: asdict(e) for eid, e in self.entities.items()},
                "relationships": [asdict(r) for r in self.relationships],
                "total_entities_added": self.total_entities_added,
                "total_relationships_added": self.total_relationships_added,
                "total_queries": self.total_queries,
                "total_extractions": self.total_extractions,
                "total_traversals": self.total_traversals,
            }
            self.state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.error(f"[KnowledgeGraph] Save failed: {e}")

    def _load_state(self):
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))

                for eid, ed in state.get("entities", {}).items():
                    self.entities[eid] = Entity(**{k: v for k, v in ed.items() if k in Entity.__dataclass_fields__})

                for rd in state.get("relationships", []):
                    self.relationships.append(
                        Relationship(**{k: v for k, v in rd.items() if k in Relationship.__dataclass_fields__})
                    )

                self.total_entities_added = state.get("total_entities_added", 0)
                self.total_relationships_added = state.get("total_relationships_added", 0)
                self.total_queries = state.get("total_queries", 0)
                self.total_extractions = state.get("total_extractions", 0)
                self.total_traversals = state.get("total_traversals", 0)

                # Rebuild NetworkX graph
                if self.graph is not None:
                    for eid, ent in self.entities.items():
                        self.graph.add_node(eid, name=ent.name, type=ent.entity_type, importance=ent.importance)
                    for rel in self.relationships:
                        self.graph.add_edge(
                            rel.source_id, rel.target_id,
                            relation=rel.relation_type, weight=rel.weight, confidence=rel.confidence,
                        )

                logger.info(f"[KnowledgeGraph] Loaded {len(self.entities)} entities, {len(self.relationships)} relationships")
            except Exception as e:
                logger.error(f"[KnowledgeGraph] Load failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "total_entities_added": self.total_entities_added,
            "total_relationships_added": self.total_relationships_added,
            "total_queries": self.total_queries,
            "total_extractions": self.total_extractions,
            "total_traversals": self.total_traversals,
            "networkx_available": NX_AVAILABLE,
            "graph_nodes": self.graph.number_of_nodes() if self.graph is not None else 0,
            "graph_edges": self.graph.number_of_edges() if self.graph is not None else 0,
            "entity_types": dict(defaultdict(int, {
                e.entity_type: sum(1 for x in self.entities.values() if x.entity_type == e.entity_type)
                for e in list(self.entities.values())[:100]
            })) if self.entities else {},
            "communities": len(self.find_communities()) if self.graph is not None and len(self.entities) > 5 else 0,
        }
