"""Tests for relationship graph module."""

import pytest
from src.anime_character_loader.generator.relationship import (
    RelationshipType,
    RelationshipStage,
    Relationship,
    RelationshipGraph,
    build_relationship_graph,
    render_relationship_graph_markdown,
)


def test_build_relationship_graph_basic():
    """Test basic relationship graph generation."""
    graph = build_relationship_graph(
        character="Test Character",
        source_work="Test Work",
        description="A character with a rival and best friend.",
    )
    
    assert graph.character == "Test Character"
    assert graph.source_work == "Test Work"
    assert len(graph.relationships) > 0
    assert graph.relationship_summary != ""


def test_relationship_graph_contains_expected_types():
    """Test that expected relationship types are detected."""
    graph = build_relationship_graph(
        character="Hero",
        source_work="Anime",
        description="Has a rival who is also a childhood friend. Love interest is a classmate.",
    )
    
    # Should detect rivalry and friendship
    types = [r.relationship_type for r in graph.relationships]
    assert RelationshipType.RIVALRY in types or RelationshipType.FRIENDSHIP in types


def test_render_relationship_graph_markdown_structure():
    """Test markdown output structure."""
    graph = build_relationship_graph(
        character="Test",
        source_work="Test",
        description="A character with a best friend.",
    )
    
    markdown = render_relationship_graph_markdown(graph)
    
    assert "## Relationship Graph" in markdown
    assert "**Character:**" in markdown
    assert "**Source:**" in markdown
    assert "### Summary" in markdown


def test_relationship_to_dict():
    """Test relationship serialization."""
    rel = Relationship(
        target_character="Friend",
        target_work="Same Anime",
        relationship_type=RelationshipType.FRIENDSHIP,
        description="Best friends since childhood",
        stage=RelationshipStage.PEAK,
    )
    
    data = rel.to_dict()
    assert data["target_character"] == "Friend"
    assert data["relationship_type"] == "friendship"
    assert data["stage"] == "peak"


def test_graph_to_dict():
    """Test graph serialization."""
    graph = build_relationship_graph(
        character="Test",
        source_work="Test",
        description="A character with a rival.",
    )
    
    data = graph.to_dict()
    assert data["character"] == "Test"
    assert "relationships" in data
    assert "relationship_count" in data


def test_get_by_type():
    """Test filtering relationships by type."""
    graph = build_relationship_graph(
        character="Test",
        source_work="Test",
        description="Has both a rival and a love interest.",
    )
    
    # Add a known relationship
    graph.relationships.append(Relationship(
        target_character="Rival",
        target_work="Test",
        relationship_type=RelationshipType.RIVALRY,
        description="Main rival",
    ))
    
    rivalries = graph.get_by_type(RelationshipType.RIVALRY)
    assert len(rivalries) >= 1


def test_narrative_notes_generation():
    """Test that narrative arc notes are generated."""
    graph = build_relationship_graph(
        character="Test",
        source_work="Test",
        description="Has a rival and a love interest.",
    )
    
    # Add both types to trigger the narrative note
    graph.relationships.append(Relationship(
        target_character="Rival",
        target_work="Test",
        relationship_type=RelationshipType.RIVALRY,
        description="Rival",
    ))
    graph.relationships.append(Relationship(
        target_character="Love",
        target_work="Test",
        relationship_type=RelationshipType.ROMANCE,
        description="Love interest",
    ))
    
    # Regenerate narrative notes
    from src.anime_character_loader.generator.relationship import _generate_narrative_notes
    notes = _generate_narrative_notes(graph)
    
    assert len(notes) > 0