"""Quote reliability grading system.

Assigns reliability grades to quotes based on source quality,
verification status, and contextual confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ReliabilityGrade(Enum):
    """Reliability grades for quotes."""
    S = "S"  # Verified original, canonical source
    A = "A"  # High confidence, official source
    B = "B"  # Good confidence, secondary source
    C = "C"  # Moderate confidence, fan transcription
    D = "D"  # Low confidence, unverified
    F = "F"  # Unreliable, likely incorrect


class SourceType(Enum):
    """Types of quote sources."""
    OFFICIAL_SCRIPT = "official_script"
    BLU_RAY_SUBTITLE = "blu_ray_subtitle"
    MANGA_SCAN = "manga_scan"
    NOVEL_TEXT = "novel_text"
    YURIPPE_API = "yurippe_api"
    WIKI_API = "wiki_api"
    WIKI_BROWSER = "wiki_browser"
    FAN_WIKI = "fan_wiki"
    SMART_EXCERPT = "smart_excerpt"
    LOCAL_DB = "local_db"
    USER_SUBMITTED = "user_submitted"
    UNKNOWN = "unknown"


# Source type base grades
SOURCE_BASE_GRADES: Dict[SourceType, ReliabilityGrade] = {
    SourceType.OFFICIAL_SCRIPT: ReliabilityGrade.S,
    SourceType.BLU_RAY_SUBTITLE: ReliabilityGrade.A,
    SourceType.MANGA_SCAN: ReliabilityGrade.A,
    SourceType.NOVEL_TEXT: ReliabilityGrade.A,
    SourceType.YURIPPE_API: ReliabilityGrade.B,
    SourceType.WIKI_API: ReliabilityGrade.B,
    SourceType.WIKI_BROWSER: ReliabilityGrade.C,
    SourceType.FAN_WIKI: ReliabilityGrade.C,
    SourceType.SMART_EXCERPT: ReliabilityGrade.D,
    SourceType.LOCAL_DB: ReliabilityGrade.C,
    SourceType.USER_SUBMITTED: ReliabilityGrade.D,
    SourceType.UNKNOWN: ReliabilityGrade.F,
}


@dataclass
class GradingFactors:
    """Factors that influence quote reliability grading."""
    source_type: SourceType
    speaker_verified: bool = False
    context_verified: bool = False
    has_multiple_attestations: bool = False
    is_original_language: bool = True
    translation_quality: Optional[str] = None  # "official", "fan", "machine", None
    extraction_method: str = "api"  # "api", "ocr", "manual", "excerpt"
    
    # Scoring weights
    VERIFICATION_BONUS: float = 0.15
    MULTI_ATTESTATION_BONUS: float = 0.10
    ORIGINAL_LANG_BONUS: float = 0.05
    TRANSLATION_PENALTY_OFFICIAL: float = 0.0
    TRANSLATION_PENALTY_FAN: float = 0.10
    TRANSLATION_PENALTY_MACHINE: float = 0.20
    EXTRACTION_PENALTY_OCR: float = 0.10
    EXTRACTION_PENALTY_MANUAL: float = 0.05


@dataclass  
class GradedQuote:
    """A quote with assigned reliability grade."""
    text: str
    speaker: str
    grade: ReliabilityGrade
    score: float  # 0.0 - 1.0
    source_type: SourceType
    factors: GradingFactors
    grade_reason: str
    confidence_breakdown: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "speaker": self.speaker,
            "grade": self.grade.value,
            "score": round(self.score, 3),
            "source_type": self.source_type.value,
            "grade_reason": self.grade_reason,
            "confidence_breakdown": self.confidence_breakdown,
        }


@dataclass
class GradingResult:
    """Result of grading a collection of quotes."""
    character: str
    work: str
    graded_quotes: List[GradedQuote]
    summary: Dict[ReliabilityGrade, int] = field(default_factory=dict)
    average_score: float = 0.0
    overall_grade: Optional[ReliabilityGrade] = None
    recommendations: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.graded_quotes:
            self._calculate_summary()
    
    def _calculate_summary(self):
        """Calculate summary statistics."""
        # Count by grade
        self.summary = {grade: 0 for grade in ReliabilityGrade}
        for quote in self.graded_quotes:
            self.summary[quote.grade] += 1
        
        # Calculate average score
        self.average_score = sum(q.score for q in self.graded_quotes) / len(self.graded_quotes)
        
        # Determine overall grade
        if self.summary[ReliabilityGrade.S] >= 3:
            self.overall_grade = ReliabilityGrade.S
        elif self.average_score >= 0.85:
            self.overall_grade = ReliabilityGrade.A
        elif self.average_score >= 0.70:
            self.overall_grade = ReliabilityGrade.B
        elif self.average_score >= 0.55:
            self.overall_grade = ReliabilityGrade.C
        elif self.average_score >= 0.40:
            self.overall_grade = ReliabilityGrade.D
        else:
            self.overall_grade = ReliabilityGrade.F
        
        # Generate recommendations
        self._generate_recommendations()
    
    def _generate_recommendations(self):
        """Generate usage recommendations based on grading."""
        s_a_count = self.summary[ReliabilityGrade.S] + self.summary[ReliabilityGrade.A]
        total = len(self.graded_quotes)
        
        if s_a_count >= 5:
            self.recommendations.append(
                "High-quality dataset suitable for fine-tuning and canonical reference."
            )
        elif s_a_count >= 3:
            self.recommendations.append(
                "Good quality dataset suitable for character voice training."
            )
        elif self.summary[ReliabilityGrade.B] >= 5:
            self.recommendations.append(
                "Acceptable for casual roleplay and chatbot training."
            )
        elif self.summary[ReliabilityGrade.C] >= 5:
            self.recommendations.append(
                "Use with caution. Best for inspiration rather than canonical reference."
            )
        else:
            self.recommendations.append(
                "Low reliability. Consider finding better sources before using."
            )
        
        # Source diversity check
        source_types = set(q.source_type for q in self.graded_quotes)
        if len(source_types) < 2 and total > 5:
            self.recommendations.append(
                "Limited source diversity. Cross-reference with additional sources recommended."
            )
        
        # Translation warning
        machine_translated = sum(
            1 for q in self.graded_quotes 
            if q.factors.translation_quality == "machine"
        )
        if machine_translated > total * 0.3:
            self.recommendations.append(
                f"High proportion ({machine_translated}/{total}) of machine-translated content. "
                "Verify accuracy before critical use."
            )
    
    def get_quotes_by_grade(self, min_grade: ReliabilityGrade) -> List[GradedQuote]:
        """Get quotes meeting minimum grade requirement."""
        grade_order = [ReliabilityGrade.S, ReliabilityGrade.A, ReliabilityGrade.B, 
                       ReliabilityGrade.C, ReliabilityGrade.D, ReliabilityGrade.F]
        min_index = grade_order.index(min_grade)
        allowed_grades = set(grade_order[:min_index + 1])
        return [q for q in self.graded_quotes if q.grade in allowed_grades]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character,
            "work": self.work,
            "total_quotes": len(self.graded_quotes),
            "grade_distribution": {g.value: count for g, count in self.summary.items()},
            "average_score": round(self.average_score, 3),
            "overall_grade": self.overall_grade.value if self.overall_grade else None,
            "recommendations": self.recommendations,
            "top_quotes": [q.to_dict() for q in self.graded_quotes[:5]],
        }


def calculate_grade_score(factors: GradingFactors) -> Tuple[float, str]:
    """Calculate numerical score and grade reason.
    
    Returns:
        Tuple of (score: 0.0-1.0, reason: str)
    """
    # Get base score from source type
    base_grade = SOURCE_BASE_GRADES.get(factors.source_type, ReliabilityGrade.F)
    base_scores = {
        ReliabilityGrade.S: 0.95,
        ReliabilityGrade.A: 0.85,
        ReliabilityGrade.B: 0.70,
        ReliabilityGrade.C: 0.55,
        ReliabilityGrade.D: 0.40,
        ReliabilityGrade.F: 0.20,
    }
    score = base_scores[base_grade]
    
    adjustments = []
    
    # Apply verification bonus
    if factors.speaker_verified:
        score += factors.VERIFICATION_BONUS
        adjustments.append("speaker verified")
    
    if factors.context_verified:
        score += factors.VERIFICATION_BONUS / 2
        adjustments.append("context verified")
    
    # Multi-attestation bonus
    if factors.has_multiple_attestations:
        score += factors.MULTI_ATTESTATION_BONUS
        adjustments.append("multiple attestations")
    
    # Original language bonus
    if factors.is_original_language:
        score += factors.ORIGINAL_LANG_BONUS
        adjustments.append("original language")
    
    # Translation penalties
    if factors.translation_quality == "fan":
        score -= factors.TRANSLATION_PENALTY_FAN
        adjustments.append("fan translation")
    elif factors.translation_quality == "machine":
        score -= factors.TRANSLATION_PENALTY_MACHINE
        adjustments.append("machine translation")
    
    # Extraction method penalties
    if factors.extraction_method == "ocr":
        score -= factors.EXTRACTION_PENALTY_OCR
        adjustments.append("OCR extraction")
    elif factors.extraction_method == "manual":
        score -= factors.EXTRACTION_PENALTY_MANUAL
        adjustments.append("manual extraction")
    
    # Clamp to valid range
    score = max(0.0, min(1.0, score))
    
    # Generate reason string
    if adjustments:
        reason = f"Base grade {base_grade.value}: " + ", ".join(adjustments)
    else:
        reason = f"Base grade {base_grade.value}: no adjustments"
    
    return score, reason


def score_to_grade(score: float) -> ReliabilityGrade:
    """Convert numerical score to letter grade."""
    if score >= 0.90:
        return ReliabilityGrade.S
    elif score >= 0.80:
        return ReliabilityGrade.A
    elif score >= 0.65:
        return ReliabilityGrade.B
    elif score >= 0.50:
        return ReliabilityGrade.C
    elif score >= 0.35:
        return ReliabilityGrade.D
    else:
        return ReliabilityGrade.F


def grade_quote(
    text: str,
    speaker: str,
    factors: GradingFactors,
) -> GradedQuote:
    """Grade a single quote.
    
    Args:
        text: The quote text
        speaker: The character speaking
        factors: Grading factors
        
    Returns:
        GradedQuote with assigned grade and score
    """
    score, reason = calculate_grade_score(factors)
    grade = score_to_grade(score)
    
    # Build confidence breakdown
    base_grade = SOURCE_BASE_GRADES.get(factors.source_type, ReliabilityGrade.F)
    breakdown = {
        "base_score": {ReliabilityGrade.S: 0.95, ReliabilityGrade.A: 0.85, 
                       ReliabilityGrade.B: 0.70, ReliabilityGrade.C: 0.55,
                       ReliabilityGrade.D: 0.40, ReliabilityGrade.F: 0.20}[base_grade],
        "verification_bonus": (factors.speaker_verified + factors.context_verified) * 0.075,
        "multi_attestation_bonus": factors.MULTI_ATTESTATION_BONUS if factors.has_multiple_attestations else 0.0,
        "language_bonus": factors.ORIGINAL_LANG_BONUS if factors.is_original_language else 0.0,
        "translation_penalty": 0.0 if not factors.translation_quality else 
                               (0.20 if factors.translation_quality == "machine" else 0.10),
        "final_score": score,
    }
    
    return GradedQuote(
        text=text,
        speaker=speaker,
        grade=grade,
        score=score,
        source_type=factors.source_type,
        factors=factors,
        grade_reason=reason,
        confidence_breakdown=breakdown,
    )


def grade_quotes_batch(
    character: str,
    work: str,
    quotes_data: List[Dict[str, Any]],
) -> GradingResult:
    """Grade a batch of quotes.
    
    Args:
        character: Character name
        work: Source work
        quotes_data: List of quote dicts with 'text', 'speaker', 'source_type', etc.
        
    Returns:
        GradingResult with all graded quotes and summary
    """
    graded = []
    
    for q_data in quotes_data:
        # Extract factors from data
        factors = GradingFactors(
            source_type=SourceType(q_data.get("source_type", "unknown")),
            speaker_verified=q_data.get("speaker_verified", False),
            context_verified=q_data.get("context_verified", False),
            has_multiple_attestations=q_data.get("has_multiple_attestations", False),
            is_original_language=q_data.get("is_original_language", True),
            translation_quality=q_data.get("translation_quality"),
            extraction_method=q_data.get("extraction_method", "api"),
        )
        
        graded_quote = grade_quote(
            text=q_data.get("text", ""),
            speaker=q_data.get("speaker", "unknown"),
            factors=factors,
        )
        graded.append(graded_quote)
    
    # Sort by score descending
    graded.sort(key=lambda x: x.score, reverse=True)
    
    return GradingResult(
        character=character,
        work=work,
        graded_quotes=graded,
    )


# Convenience mapping from wikiquote source_type to grading source_type
WIKIQUOTE_TO_GRADING_SOURCE = {
    "yurippe": SourceType.YURIPPE_API,
    "wiki": SourceType.WIKI_BROWSER,
    "wiki_fandom": SourceType.WIKI_BROWSER,
    "wiki_moegirl": SourceType.WIKI_BROWSER,
    "excerpt": SourceType.SMART_EXCERPT,
    "local": SourceType.LOCAL_DB,
}


def convert_wikiquote_source(wikiquote_source: str) -> SourceType:
    """Convert wikiquote source_type to grading SourceType."""
    return WIKIQUOTE_TO_GRADING_SOURCE.get(wikiquote_source, SourceType.UNKNOWN)
