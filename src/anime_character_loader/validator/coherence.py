"""Character coherence checker.

Validates character consistency across generated content,
detecting contradictions, OOC (out-of-character) moments,
and maintaining personality integrity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class CoherenceIssueType(Enum):
    """Types of coherence issues."""
    CONTRADICTION = "contradiction"
    OOC_BEHAVIOR = "ooc_behavior"
    INCONSISTENT_TONE = "inconsistent_tone"
    KNOWLEDGE_MISMATCH = "knowledge_mismatch"
    NAME_INCONSISTENCY = "name_inconsistency"
    TRAIT_VIOLATION = "trait_violation"
    TEMPORAL_ERROR = "temporal_error"


class Severity(Enum):
    """Severity levels for coherence issues."""
    CRITICAL = "critical"  # Breaks character completely
    MAJOR = "major"        # Significant deviation
    MINOR = "minor"        # Slight inconsistency
    NOTICE = "notice"      # Worth reviewing


@dataclass
class CoherenceIssue:
    """A single coherence issue."""
    issue_type: CoherenceIssueType
    severity: Severity
    description: str
    location: str  # Section or line reference
    suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.issue_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "location": self.location,
            "suggestion": self.suggestion,
        }


@dataclass
class CoherenceReport:
    """Full coherence check report."""
    character_name: str
    source_work: str
    issues: List[CoherenceIssue] = field(default_factory=list)
    score: float = 100.0  # 0-100
    passed: bool = True
    checks_performed: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate score based on issues."""
        self._calculate_score()
    
    def _calculate_score(self):
        """Calculate coherence score."""
        deductions = {
            Severity.CRITICAL: 25,
            Severity.MAJOR: 15,
            Severity.MINOR: 5,
            Severity.NOTICE: 1,
        }
        
        total_deduction = sum(
            deductions.get(issue.severity, 5) 
            for issue in self.issues
        )
        
        self.score = max(0, 100 - total_deduction)
        self.passed = self.score >= 80 and not any(
            i.severity == Severity.CRITICAL for i in self.issues
        )
    
    def get_issues_by_severity(self, severity: Severity) -> List[CoherenceIssue]:
        """Get issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity]
    
    def get_issues_by_type(self, issue_type: CoherenceIssueType) -> List[CoherenceIssue]:
        """Get issues of a specific type."""
        return [i for i in self.issues if i.issue_type == issue_type]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character_name,
            "source_work": self.source_work,
            "score": self.score,
            "passed": self.passed,
            "issue_count": len(self.issues),
            "issues_by_severity": {
                s.value: len(self.get_issues_by_severity(s))
                for s in Severity
            },
            "issues": [i.to_dict() for i in self.issues],
            "checks_performed": self.checks_performed,
        }


@dataclass
class CharacterProfile:
    """Extracted character profile for coherence checking."""
    name: str
    source_work: str
    aliases: List[str] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    background_facts: List[str] = field(default_factory=list)
    speech_patterns: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    boundaries: List[str] = field(default_factory=list)
    
    @classmethod
    def from_soul_content(cls, content: str) -> CharacterProfile:
        """Extract profile from SOUL.md content."""
        profile = cls(name="", source_work="")
        
        # Extract name
        name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if name_match:
            profile.name = name_match.group(1).strip()
        
        # Extract source work
        source_match = re.search(r'\*\*Source:\*\*\s*(.+)', content)
        if source_match:
            profile.source_work = source_match.group(1).strip()
        
        # Extract aliases
        alias_match = re.search(r'\*\*Also Known As:\*\*\s*(.+)', content)
        if alias_match:
            profile.aliases = [
                a.strip() for a in alias_match.group(1).split(',')
            ]
        
        # Extract traits from personality section
        personality_match = re.search(
            r'## Personality\s*\n\n(.+?)(?=\n##|\Z)', 
            content, re.DOTALL
        )
        if personality_match:
            traits_text = personality_match.group(1)
            profile.traits = [
                line.lstrip('- ').strip()
                for line in traits_text.split('\n')
                if line.strip().startswith('-')
            ]
        
        # Extract background facts
        background_match = re.search(
            r'## Background\s*\n\n(.+?)(?=\n##|\Z)', 
            content, re.DOTALL
        )
        if background_match:
            profile.background_facts = [
                s.strip() for s in background_match.group(1).split('.')
                if len(s.strip()) > 10
            ]
        
        # Extract speech patterns
        speaking_match = re.search(
            r'## Speaking Style\s*\n\n(.+?)(?=\n##|\Z)', 
            content, re.DOTALL
        )
        if speaking_match:
            profile.speech_patterns = [
                line.lstrip('- ').strip()
                for line in speaking_match.group(1).split('\n')
                if line.strip().startswith('-')
            ]
        
        # Extract boundaries
        boundaries_match = re.search(
            r'## Boundaries\s*\n\n(.+?)(?=\n##|\Z)', 
            content, re.DOTALL
        )
        if boundaries_match:
            profile.boundaries = [
                line.lstrip('- ').strip()
                for line in boundaries_match.group(1).split('\n')
                if line.strip().startswith('-')
            ]
        
        return profile


class CoherenceChecker:
    """Main coherence checker class."""
    
    def __init__(self, profile: CharacterProfile):
        self.profile = profile
        self.issues: List[CoherenceIssue] = []
        self.checks_performed: List[str] = []
    
    def check_all(self, content: str) -> CoherenceReport:
        """Run all coherence checks.
        
        Args:
            content: The SOUL.md content to check
            
        Returns:
            CoherenceReport with all issues found
        """
        self.issues = []
        self.checks_performed = []
        
        # Run all checks
        self._check_name_consistency(content)
        self._check_trait_contradictions(content)
        self._check_speech_pattern_consistency(content)
        self._check_boundary_violations(content)
        self._check_background_accuracy(content)
        self._check_tone_consistency(content)
        
        return CoherenceReport(
            character_name=self.profile.name,
            source_work=self.profile.source_work,
            issues=self.issues,
            checks_performed=self.checks_performed,
        )
    
    def _check_name_consistency(self, content: str):
        """Check for name inconsistencies."""
        self.checks_performed.append("name_consistency")
        
        # All valid names for this character
        valid_names = {self.profile.name.lower()}
        valid_names.update(a.lower() for a in self.profile.aliases)
        
        # Check for common name confusion patterns
        # e.g., if character is "Katou Megumi", check for "Kato Megumi"
        if 'ou' in self.profile.name.lower():
            alt_name = self.profile.name.lower().replace('ou', 'o')
            # This is a variant, not necessarily an error
        
        # Check for completely wrong names in identity section
        identity_match = re.search(
            r'## Identity\s*\n\n(.+?)(?=\n##|\Z)', 
            content, re.DOTALL
        )
        if identity_match:
            identity_text = identity_match.group(1).lower()
            
            # Check if main name appears in identity
            if self.profile.name.lower() not in identity_text:
                self.issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.NAME_INCONSISTENCY,
                    severity=Severity.CRITICAL,
                    description=f"Character name '{self.profile.name}' not found in Identity section",
                    location="Identity",
                    suggestion=f"Ensure Identity section mentions '{self.profile.name}'",
                ))
    
    def _check_trait_contradictions(self, content: str):
        """Check for contradictory personality traits."""
        self.checks_performed.append("trait_contradictions")
        
        # Common contradictory trait pairs
        contradictions = [
            ("shy", "outgoing"),
            ("confident", "insecure"),
            ("calm", "hot-headed"),
            ("honest", "deceptive"),
            ("cheerful", "gloomy"),
            ("serious", "playful"),
        ]
        
        personality_text = self._extract_section(content, "Personality").lower()
        
        for trait1, trait2 in contradictions:
            has_trait1 = trait1 in personality_text
            has_trait2 = trait2 in personality_text
            
            if has_trait1 and has_trait2:
                # Check if they're qualified (e.g., "seems shy but is outgoing")
                # If not qualified, flag as contradiction
                if not self._has_qualifying_context(personality_text, trait1, trait2):
                    self.issues.append(CoherenceIssue(
                        issue_type=CoherenceIssueType.CONTRADICTION,
                        severity=Severity.MAJOR,
                        description=f"Contradictory traits detected: '{trait1}' and '{trait2}'",
                        location="Personality",
                        suggestion=f"Clarify how these traits coexist or remove the contradiction",
                    ))
    
    def _check_speech_pattern_consistency(self, content: str):
        """Check for consistent speech patterns."""
        self.checks_performed.append("speech_pattern_consistency")
        
        speaking_style = self._extract_section(content, "Speaking Style").lower()
        
        # Check for generic/vague speech patterns
        vague_patterns = [
            "speaks normally",
            "talks like a regular person",
            "uses standard speech",
        ]
        
        for vague in vague_patterns:
            if vague in speaking_style:
                self.issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.INCONSISTENT_TONE,
                    severity=Severity.MINOR,
                    description=f"Vague speech pattern: '{vague}'",
                    location="Speaking Style",
                    suggestion="Replace with specific speech characteristics",
                ))
    
    def _check_boundary_violations(self, content: str):
        """Check for boundary definition issues."""
        self.checks_performed.append("boundary_violations")
        
        boundaries = self._extract_section(content, "Boundaries")
        
        # Check if boundaries mention the character name
        if self.profile.name and self.profile.name not in boundaries:
            self.issues.append(CoherenceIssue(
                issue_type=CoherenceIssueType.NAME_INCONSISTENCY,
                severity=Severity.MINOR,
                description="Boundaries section doesn't reference character name",
                location="Boundaries",
                suggestion=f"Add 'Stay in character as {self.profile.name}' to boundaries",
            ))
    
    def _check_background_accuracy(self, content: str):
        """Check background facts for plausibility."""
        self.checks_performed.append("background_accuracy")
        
        # This is a simplified check
        # In a real implementation, might cross-reference with external databases
        background = self._extract_section(content, "Background")
        
        # Check for placeholder text
        placeholders = ["todo", "fixme", "placeholder", "unknown"]
        for placeholder in placeholders:
            if placeholder in background.lower():
                self.issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.KNOWLEDGE_MISMATCH,
                    severity=Severity.MAJOR,
                    description=f"Placeholder text detected: '{placeholder}'",
                    location="Background",
                    suggestion="Replace placeholder with actual background information",
                ))
    
    def _check_tone_consistency(self, content: str):
        """Check overall tone consistency."""
        self.checks_performed.append("tone_consistency")
        
        # Check personality section length
        personality = self._extract_section(content, "Personality")
        trait_count = len([l for l in personality.split('\n') if l.strip().startswith('-')])
        
        if trait_count < 3:
            self.issues.append(CoherenceIssue(
                issue_type=CoherenceIssueType.TRAIT_VIOLATION,
                severity=Severity.MINOR,
                description=f"Only {trait_count} personality traits defined (recommend 3-5)",
                location="Personality",
                suggestion="Add more specific personality traits for richer character",
            ))
    
    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract content of a specific section."""
        pattern = rf'## {re.escape(section_name)}\s*\n\n(.+?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1) if match else ""
    
    def _has_qualifying_context(self, text: str, word1: str, word2: str) -> bool:
        """Check if contradictory words have qualifying context."""
        # Look for qualifying words between the contradictory terms
        qualifying = ["but", "however", "although", "yet", "actually", "secretly"]
        
        # Simple check: are they in the same sentence with a qualifier?
        sentences = re.split(r'[.!?]+', text)
        for sent in sentences:
            if word1 in sent and word2 in sent:
                if any(q in sent for q in qualifying):
                    return True
        return False


def check_coherence(content: str) -> CoherenceReport:
    """Convenience function to check coherence of SOUL.md content.
    
    Args:
        content: SOUL.md content
        
    Returns:
        CoherenceReport
    """
    profile = CharacterProfile.from_soul_content(content)
    checker = CoherenceChecker(profile)
    return checker.check_all(content)


def check_coherence_between(soul1: str, soul2: str) -> List[CoherenceIssue]:
    """Check coherence between two character profiles.
    
    Useful for multi-character SOUL files to ensure consistency.
    
    Args:
        soul1: First character SOUL content
        soul2: Second character SOUL content
        
    Returns:
        List of coherence issues between characters
    """
    profile1 = CharacterProfile.from_soul_content(soul1)
    profile2 = CharacterProfile.from_soul_content(soul2)
    
    issues = []
    
    # Check for name collision
    if profile1.name == profile2.name:
        issues.append(CoherenceIssue(
            issue_type=CoherenceIssueType.NAME_INCONSISTENCY,
            severity=Severity.CRITICAL,
            description=f"Duplicate character name: '{profile1.name}'",
            location="Multi-character file",
            suggestion="Ensure characters have unique names or merge profiles",
        ))
    
    # Check for source work consistency
    if profile1.source_work != profile2.source_work:
        issues.append(CoherenceIssue(
            issue_type=CoherenceIssueType.KNOWLEDGE_MISMATCH,
            severity=Severity.NOTICE,
            description=f"Characters from different works: '{profile1.source_work}' vs '{profile2.source_work}'",
            location="Source work",
            suggestion="Ensure cross-work interactions are intentional",
        ))
    
    return issues
