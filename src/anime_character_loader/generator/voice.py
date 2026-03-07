"""Voice prompt generation utilities.

API-agnostic structured output for downstream TTS / voice-cloning systems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


DEFAULT_BANNED_TRAITS = [
    "robotic monotone",
    "overacted anime squealing",
    "uncontrolled shouting",
    "flat sentence endings",
    "accent drift between lines",
]


@dataclass
class VoicePrompt:
    character: str
    source_work: str
    tone: List[str] = field(default_factory=list)
    pace: str = "steady"
    emotion_range: str = "balanced, with controlled peaks"
    pause_style: str = "brief reflective pauses before emphasis"
    banned_traits: List[str] = field(default_factory=lambda: list(DEFAULT_BANNED_TRAITS))
    delivery_notes: List[str] = field(default_factory=list)
    sample_lines: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character,
            "source_work": self.source_work,
            "tone": self.tone,
            "pace": self.pace,
            "emotion_range": self.emotion_range,
            "pause_style": self.pause_style,
            "banned_traits": self.banned_traits,
            "delivery_notes": self.delivery_notes,
            "sample_lines": self.sample_lines,
        }


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _pick_tone(description: str) -> List[str]:
    desc = description.lower()
    tones: List[str] = []

    mappings = [
        ("calm", "calm"),
        ("composed", "composed"),
        ("quiet", "soft-spoken"),
        ("shy", "hesitant warmth"),
        ("confident", "confident"),
        ("sarcastic", "dry sarcasm"),
        ("sharp tongue", "sharp-edged wit"),
        ("gentle", "gentle"),
        ("cheerful", "bright"),
        ("serious", "serious"),
        ("intelligent", "articulate"),
        ("tsundere", "guarded tenderness"),
        ("kuudere", "cool restraint"),
        ("warm", "warm"),
    ]

    for needle, label in mappings:
        if needle in desc and label not in tones:
            tones.append(label)

    if not tones:
        tones.extend(["grounded", "character-faithful"])

    return tones[:4]


def _pick_pace(description: str) -> str:
    desc = description.lower()
    if any(word in desc for word in ["energetic", "genki", "cheerful", "excited"]):
        return "lightly brisk, but still intelligible"
    if any(word in desc for word in ["calm", "quiet", "composed", "shy"]):
        return "measured and steady"
    if any(word in desc for word in ["sarcastic", "intelligent", "serious"]):
        return "controlled mid-tempo with deliberate emphasis"
    return "steady conversational pace"


def _pick_emotion_range(description: str) -> str:
    desc = description.lower()
    if any(word in desc for word in ["shy", "quiet", "kuudere"]):
        return "narrow-to-medium range; subtle shifts matter more than volume"
    if any(word in desc for word in ["cheerful", "playful", "genki"]):
        return "medium-to-wide range with lively upward turns"
    if any(word in desc for word in ["sarcastic", "sharp tongue", "tsundere"]):
        return "medium range; quick switches between restraint, irritation, and hidden warmth"
    return "balanced range with clear but controlled emotional transitions"


def _pick_pause_style(description: str) -> str:
    desc = description.lower()
    if any(word in desc for word in ["calm", "composed", "intelligent"]):
        return "clean clause breaks; pause briefly before key observations"
    if any(word in desc for word in ["shy", "hesitant"]):
        return "short hesitant pauses before vulnerable or personal phrases"
    if any(word in desc for word in ["sarcastic", "sharp tongue"]):
        return "brief beat before punchlines or cutting remarks"
    return "natural short pauses between thought units"


def _pick_delivery_notes(description: str, source_work: str) -> List[str]:
    notes = [
        f"Keep delivery consistent with the dramatic tone of {source_work}." if source_work else "Keep delivery consistent with the source material.",
        "Prioritize intelligibility and stable pronunciation over exaggerated performance.",
        "Maintain the same vocal identity across neutral lines, emotional lines, and short acknowledgements.",
    ]

    desc = description.lower()
    if "sarcastic" in desc or "sharp tongue" in desc:
        notes.append("Let sarcasm come from timing and stress, not from cartoonish pitch spikes.")
    if "shy" in desc or "quiet" in desc:
        notes.append("Keep softer entries audible; do not fade into breathy mumbling.")
    if "confident" in desc or "serious" in desc:
        notes.append("Use crisp endings and stable breath support for declarative statements.")

    return notes[:5]


def _build_sample_lines(character: str) -> List[Dict[str, str]]:
    safe_character = character or "Character"
    return [
        {
            "intent": "neutral_greeting",
            "text": f"Hello. I'm {safe_character}. Let's keep this simple and honest.",
            "delivery_target": "baseline identity and neutral cadence",
        },
        {
            "intent": "gentle_reassurance",
            "text": "It's fine. Take a breath first, then tell me what actually happened.",
            "delivery_target": "warmth without melodrama",
        },
        {
            "intent": "mild_irritation",
            "text": "Honestly... if you're going to do that again, at least think it through first.",
            "delivery_target": "controlled annoyance; no yelling",
        },
        {
            "intent": "vulnerable_confession",
            "text": "I don't say this often, so listen carefully... I really do care.",
            "delivery_target": "softened intensity with clear articulation",
        },
    ]


def build_voice_prompt(character: str, source_work: str, description: str) -> VoicePrompt:
    description = _normalize_text(description)
    return VoicePrompt(
        character=character,
        source_work=source_work,
        tone=_pick_tone(description),
        pace=_pick_pace(description),
        emotion_range=_pick_emotion_range(description),
        pause_style=_pick_pause_style(description),
        delivery_notes=_pick_delivery_notes(description, source_work),
        sample_lines=_build_sample_lines(character),
    )


def render_voice_prompt_markdown(prompt: VoicePrompt) -> str:
    lines: List[str] = [
        "## Voice Prompt",
        "",
        f"- character: {prompt.character}",
        f"- source_work: {prompt.source_work}",
        f"- tone: {', '.join(prompt.tone)}",
        f"- pace: {prompt.pace}",
        f"- emotion_range: {prompt.emotion_range}",
        f"- pause_style: {prompt.pause_style}",
        "- banned_traits:",
    ]

    for trait in prompt.banned_traits:
        lines.append(f"  - {trait}")

    lines.append("- delivery_notes:")
    for note in prompt.delivery_notes:
        lines.append(f"  - {note}")

    lines.extend(["", "### Voice Calibration Sample Lines", ""])
    for idx, sample in enumerate(prompt.sample_lines, start=1):
        lines.append(f"{idx}. [{sample['intent']}] {sample['text']}")
        lines.append(f"   - target: {sample['delivery_target']}")

    return "\n".join(lines)
