"""Character relationship graph module.

Models major relationships around each character to improve realism
and long-form personality coherence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class RelationshipType(Enum):
    """Types of relationships between characters."""
    FAMILY = "family"
    RIVALRY = "rivalry"
    ROMANCE = "romance"
    LOYALTY = "loyalty"
    CONFLICT = "conflict"
    FRIENDSHIP = "friendship"
    MENTOR = "mentor"
    PROTEGE = "protege"
    ALLIANCE = "alliance"
    NEUTRAL = "neutral"


class RelationshipStage(Enum):
    """Stages of relationship development."""
    INITIAL = "initial"
    DEVELOPING = "developing"
    PEAK = "peak"
    STRAINED = "strained"
    RESOLVED = "resolved"
    BROKEN = "broken"


@dataclass
class Relationship:
    """A single relationship between two characters."""
    target_character: str
    target_work: str
    relationship_type: RelationshipType
    description: str
    stage: RelationshipStage = RelationshipStage.INITIAL
    stage_notes: List[str] = field(default_factory=list)
    key_moments: List[str] = field(default_factory=list)
    dynamics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_character": self.target_character,
            "target_work": self.target_work,
            "relationship_type": self.relationship_type.value,
            "description": self.description,
            "stage": self.stage.value,
            "stage_notes": self.stage_notes,
            "key_moments": self.key_moments,
            "dynamics": self.dynamics,
        }


@dataclass
class RelationshipGraph:
    """Complete relationship graph for a character."""
    character: str
    source_work: str
    relationships: List[Relationship] = field(default_factory=list)
    relationship_summary: str = ""
    narrative_arc_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character,
            "source_work": self.source_work,
            "relationship_summary": self.relationship_summary,
            "relationship_count": len(self.relationships),
            "relationships": [r.to_dict() for r in self.relationships],
            "narrative_arc_notes": self.narrative_arc_notes,
        }

    def get_by_type(self, rel_type: RelationshipType) -> List[Relationship]:
        """Get all relationships of a specific type."""
        return [r for r in self.relationships if r.relationship_type == rel_type]

    def get_by_stage(self, stage: RelationshipStage) -> List[Relationship]:
        """Get all relationships at a specific stage."""
        return [r for r in self.relationships if r.stage == stage]


def _extract_relationships_from_description(
    character: str, source_work: str, description: str
) -> List[Relationship]:
    """Extract relationship hints from character description."""
    relationships: List[Relationship] = []
    desc_lower = description.lower()

    # Pattern matching for common relationship indicators
    relationship_patterns = [
        ("childhood friend", RelationshipType.FRIENDSHIP, "Long-standing friendship from childhood"),
        ("best friend", RelationshipType.FRIENDSHIP, "Close trusted friend"),
        ("classmate", RelationshipType.FRIENDSHIP, "School acquaintance with potential for deeper bond"),
        ("rival", RelationshipType.RIVALRY, "Competitive relationship driving growth"),
        ("competitor", RelationshipType.RIVALRY, "Professional or personal competition"),
        ("love interest", RelationshipType.ROMANCE, "Romantic tension or relationship"),
        ("girlfriend", RelationshipType.ROMANCE, "Romantic partner"),
        ("boyfriend", RelationshipType.ROMANCE, "Romantic partner"),
        ("sister", RelationshipType.FAMILY, "Sibling bond"),
        ("brother", RelationshipType.FAMILY, "Sibling bond"),
        ("mother", RelationshipType.FAMILY, "Parental relationship"),
        ("father", RelationshipType.FAMILY, "Parental relationship"),
        ("senpai", RelationshipType.MENTOR, "Senior/junior dynamic with guidance"),
        ("kohai", RelationshipType.PROTEGE, "Junior looked after by senior"),
        ("master", RelationshipType.MENTOR, "Teacher or mentor figure"),
        ("student", RelationshipType.PROTEGE, "Learning relationship"),
        ("enemy", RelationshipType.CONFLICT, "Opposition or antagonism"),
        ("antagonist", RelationshipType.CONFLICT, "Source of conflict"),
        ("ally", RelationshipType.ALLIANCE, "Cooperative partnership"),
        ("partner", RelationshipType.ALLIANCE, "Collaborative relationship"),
    ]

    for pattern, rel_type, default_desc in relationship_patterns:
        if pattern in desc_lower:
            # Extract context around the pattern
            idx = desc_lower.find(pattern)
            context_start = max(0, idx - 50)
            context_end = min(len(description), idx + len(pattern) + 50)
            context = description[context_start:context_end]

            # Try to extract target character name
            target = _extract_target_name(context, pattern)

            rel = Relationship(
                target_character=target or f"Unknown {pattern.title()}",
                target_work=source_work,
                relationship_type=rel_type,
                description=default_desc,
                dynamics=[f"Dynamic centered around {pattern}"],
            )
            relationships.append(rel)

    return relationships


def _extract_target_name(context: str, pattern: str) -> Optional[str]:
    """Try to extract a name from relationship context."""
    # Simple heuristic: look for capitalized words before the pattern
    words = context.split()
    for i, word in enumerate(words):
        if pattern in word.lower():
            # Check previous words for potential names
            for j in range(max(0, i - 3), i):
                candidate = words[j].strip(",.()[]'\"")
                if candidate and candidate[0].isupper() and len(candidate) > 1:
                    return candidate
    return None


def _build_relationship_summary(graph: RelationshipGraph) -> str:
    """Generate a narrative summary of character's relationships."""
    if not graph.relationships:
        return f"{graph.character} has no documented significant relationships."

    type_counts: Dict[RelationshipType, int] = {}
    for rel in graph.relationships:
        type_counts[rel.relationship_type] = type_counts.get(rel.relationship_type, 0) + 1

    parts = [f"{graph.character}'s relationship landscape:"]
    for rel_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        parts.append(f"- {count} {rel_type.value}(s)")

    return "\n".join(parts)


def _generate_narrative_notes(graph: RelationshipGraph) -> List[str]:
    """Generate narrative arc notes based on relationships."""
    notes: List[str] = []

    # Check for complex relationship patterns
    has_romance = any(r.relationship_type == RelationshipType.ROMANCE for r in graph.relationships)
    has_rivalry = any(r.relationship_type == RelationshipType.RIVALRY for r in graph.relationships)
    has_family = any(r.relationship_type == RelationshipType.FAMILY for r in graph.relationships)

    if has_romance and has_rivalry:
        notes.append("Character navigates both romantic and competitive dynamics; watch for jealousy or distraction.")

    if has_family and not has_romance:
        notes.append("Family-centered character; may prioritize blood ties over new connections.")

    rivalries = graph.get_by_type(RelationshipType.RIVALRY)
    for rival in rivalries:
        if rival.stage == RelationshipStage.DEVELOPING:
            notes.append(f"Rivalry with {rival.target_character} is escalating; monitor for turning points.")

    return notes


def build_relationship_graph(
    character: str,
    source_work: str,
    description: str,
    known_relationships: Optional[List[Dict[str, Any]]] = None,
) -> RelationshipGraph:
    """Build a complete relationship graph for a character.

    Args:
        character: Character name
        source_work: Source anime/manga title
        description: Character description text
        known_relationships: Optional pre-defined relationships

    Returns:
        Populated RelationshipGraph
    """
    relationships: List[Relationship] = []

    # Extract from description
    relationships.extend(_extract_relationships_from_description(character, source_work, description))

    # Add known relationships if provided
    if known_relationships:
        for rel_data in known_relationships:
            rel = Relationship(
                target_character=rel_data["target_character"],
                target_work=rel_data.get("target_work", source_work),
                relationship_type=RelationshipType(rel_data.get("relationship_type", "neutral")),
                description=rel_data.get("description", ""),
                stage=RelationshipStage(rel_data.get("stage", "initial")),
                stage_notes=rel_data.get("stage_notes", []),
                key_moments=rel_data.get("key_moments", []),
                dynamics=rel_data.get("dynamics", []),
            )
            relationships.append(rel)

    graph = RelationshipGraph(
        character=character,
        source_work=source_work,
        relationships=relationships,
    )

    graph.relationship_summary = _build_relationship_summary(graph)
    graph.narrative_arc_notes = _generate_narrative_notes(graph)

    return graph


def render_relationship_graph_markdown(graph: RelationshipGraph) -> str:
    """Render relationship graph as markdown."""
    lines: List[str] = [
        "## Relationship Graph",
        "",
        f"**Character:** {graph.character}",
        f"**Source:** {graph.source_work}",
        "",
        f"### Summary",
        graph.relationship_summary,
        "",
        f"### Relationships ({len(graph.relationships)})",
        "",
    ]

    for idx, rel in enumerate(graph.relationships, start=1):
        lines.append(f"#### {idx}. {rel.target_character}")
        lines.append(f"- **Type:** {rel.relationship_type.value}")
        lines.append(f"- **Stage:** {rel.stage.value}")
        lines.append(f"- **Description:** {rel.description}")
        if rel.dynamics:
            lines.append(f"- **Dynamics:** {', '.join(rel.dynamics)}")
        if rel.stage_notes:
            lines.append("- **Stage Notes:**")
            for note in rel.stage_notes:
                lines.append(f"  - {note}")
        if rel.key_moments:
            lines.append("- **Key Moments:**")
            for moment in rel.key_moments:
                lines.append(f"  - {moment}")
        lines.append("")

    if graph.narrative_arc_notes:
        lines.append("### Narrative Arc Notes")
        lines.append("")
        for note in graph.narrative_arc_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)