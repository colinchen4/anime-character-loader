"""Use-case mode presets for character generation.

Provides optimized configurations for different use cases:
- roleplay: Immersive RP with strong character consistency
- chatbot: Balanced assistant with character flavor
- creative: Writing aid with character voice examples
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class UseCaseMode(Enum):
    """Predefined use-case modes."""
    ROLEPLAY = "roleplay"
    CHATBOT = "chatbot"
    CREATIVE = "creative"


@dataclass
class ModeConfig:
    """Configuration for a specific use-case mode."""
    
    # Content generation settings
    include_voice_prompt: bool = True
    include_relationship_graph: bool = False
    include_quotes: bool = True
    quote_count: int = 5
    min_quote_grade: str = "B"  # S/A/B/C/D/F
    
    # Validation thresholds
    validation_min_score: float = 80.0
    require_background: bool = True
    require_speaking_style: bool = True
    
    # Output sections
    sections: List[str] = field(default_factory=lambda: [
        "identity", "background", "personality", "speaking_style", "boundaries"
    ])
    
    # Character enforcement
    enforce_in_character: bool = True
    allow_oob_knowledge: bool = False  # Out-of-character knowledge
    
    # Interaction style
    greeting_style: str = "in_character"  # in_character, neutral, none
    response_length: str = "medium"  # short, medium, long
    
    # Extra features
    include_sample_dialogues: bool = False
    include_conflict_scenarios: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "include_voice_prompt": self.include_voice_prompt,
            "include_relationship_graph": self.include_relationship_graph,
            "include_quotes": self.include_quotes,
            "quote_count": self.quote_count,
            "min_quote_grade": self.min_quote_grade,
            "validation_min_score": self.validation_min_score,
            "sections": self.sections,
            "enforce_in_character": self.enforce_in_character,
            "greeting_style": self.greeting_style,
            "response_length": self.response_length,
        }


# Mode preset configurations
MODE_PRESETS: Dict[UseCaseMode, ModeConfig] = {
    UseCaseMode.ROLEPLAY: ModeConfig(
        include_voice_prompt=True,
        include_relationship_graph=True,
        include_quotes=True,
        quote_count=8,
        min_quote_grade="B",
        validation_min_score=85.0,
        require_background=True,
        require_speaking_style=True,
        sections=[
            "identity", "background", "personality", 
            "speaking_style", "boundaries", "relationships"
        ],
        enforce_in_character=True,
        allow_oob_knowledge=False,
        greeting_style="in_character",
        response_length="medium",
        include_sample_dialogues=True,
        include_conflict_scenarios=True,
    ),
    
    UseCaseMode.CHATBOT: ModeConfig(
        include_voice_prompt=True,
        include_relationship_graph=False,
        include_quotes=True,
        quote_count=3,
        min_quote_grade="C",
        validation_min_score=75.0,
        require_background=True,
        require_speaking_style=True,
        sections=[
            "identity", "personality", "speaking_style", 
            "boundaries", "capabilities"
        ],
        enforce_in_character=True,
        allow_oob_knowledge=True,  # Can use OOB knowledge to be helpful
        greeting_style="neutral",
        response_length="medium",
        include_sample_dialogues=False,
        include_conflict_scenarios=False,
    ),
    
    UseCaseMode.CREATIVE: ModeConfig(
        include_voice_prompt=True,
        include_relationship_graph=False,
        include_quotes=True,
        quote_count=10,
        min_quote_grade="C",
        validation_min_score=70.0,
        require_background=False,
        require_speaking_style=True,
        sections=[
            "identity", "personality", "speaking_style",
            "voice_examples", "writing_tips"
        ],
        enforce_in_character=False,  # More flexible for creative use
        allow_oob_knowledge=True,
        greeting_style="none",
        response_length="long",
        include_sample_dialogues=True,
        include_conflict_scenarios=False,
    ),
}


def get_mode_config(mode: UseCaseMode) -> ModeConfig:
    """Get configuration for a specific mode.
    
    Args:
        mode: The use-case mode
        
    Returns:
        ModeConfig for the specified mode
    """
    return MODE_PRESETS.get(mode, MODE_PRESETS[UseCaseMode.CHATBOT])


def get_mode_by_name(name: str) -> Optional[UseCaseMode]:
    """Get mode enum by name (case-insensitive).
    
    Args:
        name: Mode name (roleplay/chatbot/creative)
        
    Returns:
        UseCaseMode or None if not found
    """
    name_lower = name.lower().strip()
    for mode in UseCaseMode:
        if mode.value == name_lower:
            return mode
    # Aliases
    aliases = {
        "rp": UseCaseMode.ROLEPLAY,
        "role play": UseCaseMode.ROLEPLAY,
        "bot": UseCaseMode.CHATBOT,
        "assistant": UseCaseMode.CHATBOT,
        "write": UseCaseMode.CREATIVE,
        "writing": UseCaseMode.CREATIVE,
    }
    return aliases.get(name_lower)


def list_modes() -> List[Dict[str, Any]]:
    """List all available modes with descriptions.
    
    Returns:
        List of mode info dicts
    """
    descriptions = {
        UseCaseMode.ROLEPLAY: {
            "name": "roleplay",
            "description": "Immersive roleplay with strong character consistency",
            "best_for": ["Character RP", "Dating sim", "Story reenactment"],
            "key_features": ["Relationship graph", "Sample dialogues", "Strict in-character"],
        },
        UseCaseMode.CHATBOT: {
            "name": "chatbot",
            "description": "Balanced assistant with character personality",
            "best_for": ["AI companion", "Daily chat", "Q&A with personality"],
            "key_features": ["Helpful responses", "Character flavor", "Flexible boundaries"],
        },
        UseCaseMode.CREATIVE: {
            "name": "creative",
            "description": "Writing aid focused on voice and dialogue examples",
            "best_for": ["Fanfiction", "Script writing", "Voice study"],
            "key_features": ["Many quotes", "Writing tips", "Voice analysis"],
        },
    }
    
    return [
        {
            "id": mode.value,
            **descriptions[mode],
            "config": MODE_PRESETS[mode].to_dict(),
        }
        for mode in UseCaseMode
    ]


@dataclass
class ModeApplicationResult:
    """Result of applying a mode to character generation."""
    mode: UseCaseMode
    config: ModeConfig
    cli_flags: List[str] = field(default_factory=list)
    generator_options: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Build CLI flags and generator options from config."""
        self._build_cli_flags()
        self._build_generator_options()
    
    def _build_cli_flags(self):
        """Generate equivalent CLI flags for the mode."""
        flags = []
        
        if self.config.include_voice_prompt:
            flags.append("--voice-prompt")
        
        if self.config.include_relationship_graph:
            flags.append("--relationship-graph")
        
        self.cli_flags = flags
    
    def _build_generator_options(self):
        """Build options dict for the generator."""
        self.generator_options = {
            "include_voice_prompt": self.config.include_voice_prompt,
            "include_relationship_graph": self.config.include_relationship_graph,
            "include_quotes": self.config.include_quotes,
            "quote_count": self.config.quote_count,
            "min_quote_grade": self.config.min_quote_grade,
            "sections": self.config.sections,
            "enforce_in_character": self.config.enforce_in_character,
            "greeting_style": self.config.greeting_style,
        }


def apply_mode(mode_name: str) -> ModeApplicationResult:
    """Apply a mode by name and get configuration result.
    
    Args:
        mode_name: Name of the mode (roleplay/chatbot/creative)
        
    Returns:
        ModeApplicationResult with full configuration
        
    Raises:
        ValueError: If mode name is invalid
    """
    mode = get_mode_by_name(mode_name)
    if not mode:
        valid_modes = ", ".join(m.value for m in UseCaseMode)
        raise ValueError(f"Invalid mode '{mode_name}'. Valid modes: {valid_modes}")
    
    config = get_mode_config(mode)
    return ModeApplicationResult(mode=mode, config=config)


# Section templates for different modes
SECTION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "capabilities": {
        UseCaseMode.CHATBOT: """## Capabilities

You can assist with:
- Answering questions about {source_work}
- Casual conversation with {name}'s personality
- Light advice and companionship

While staying true to {name}'s character, you may use out-of-character knowledge when helpful.""",
    },
    "writing_tips": {
        UseCaseMode.CREATIVE: """## Writing Tips for {name}

### Voice Markers
- {voice_markers}

### Common Phrases
{common_phrases}

### Pitfalls to Avoid
- Don't make {name} too generic
- Preserve {name}'s unique speech patterns
- Maintain consistency with canon events""",
    },
    "voice_examples": {
        UseCaseMode.CREATIVE: """## Voice Examples

Use these examples to understand {name}'s voice:

{quote_examples}""",
    },
}


def get_section_template(section: str, mode: UseCaseMode) -> Optional[str]:
    """Get template for a section in a specific mode.
    
    Args:
        section: Section name
        mode: Use case mode
        
    Returns:
        Template string or None
    """
    if section not in SECTION_TEMPLATES:
        return None
    
    mode_templates = SECTION_TEMPLATES[section]
    return mode_templates.get(mode)
