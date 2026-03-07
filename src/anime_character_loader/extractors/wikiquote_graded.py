"""Graded wikiquote fetcher - wraps unified fetcher with reliability grading.

This module extends the wikiquote_unified fetcher with reliability grading,
providing quality scores for each quote based on source type and verification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from anime_character_loader.extractors.wikiquote_unified import (
    fetch_quotes as unified_fetch_quotes,
    QuoteResult,
    QuoteItem,
)
from anime_character_loader.validator.quote_reliability import (
    GradedQuote,
    GradingFactors,
    GradingResult,
    SourceType,
    convert_wikiquote_source,
    grade_quote,
    ReliabilityGrade,
)


def fetch_quotes_graded(
    character: str,
    work: str = "",
    include_excerpt: bool = True,
    min_grade: Optional[ReliabilityGrade] = None,
) -> GradingResult:
    """Fetch quotes with reliability grading.
    
    This wraps the unified fetcher and adds reliability grading to each quote.
    
    Args:
        character: Character name
        work: Source work name
        include_excerpt: Whether to include smart excerpt fallbacks
        min_grade: Minimum grade filter (optional)
        
    Returns:
        GradingResult with graded quotes
        
    Example:
        >>> result = fetch_quotes_graded("Eriri Spencer Sawamura", "Saekano")
        >>> print(f"Overall grade: {result.overall_grade.value}")
        >>> print(f"S-grade quotes: {result.summary[ReliabilityGrade.S]}")
        >>> for q in result.get_quotes_by_grade(ReliabilityGrade.A):
        ...     print(f"[{q.grade.value}] {q.text[:60]}...")
    """
    # Fetch from unified fetcher
    raw_result = unified_fetch_quotes(character, work, include_excerpt)
    
    # Convert to graded quotes
    graded_quotes: List[GradedQuote] = []
    
    for quote_item in raw_result.get("quotes", []):
        # Map source type
        source_type = convert_wikiquote_source(quote_item.get("source_type", "unknown"))
        
        # Determine verification and extraction factors
        is_excerpt = not quote_item.get("is_original_quote", True)
        is_api = quote_item.get("source_type") == "yurippe"
        
        factors = GradingFactors(
            source_type=source_type,
            speaker_verified=quote_item.get("speaker") not in ["unknown", ""],
            context_verified=bool(quote_item.get("context")),
            has_multiple_attestations=False,  # Would need cross-source comparison
            is_original_language=quote_item.get("source_type") != "excerpt",
            translation_quality=None if quote_item.get("source_type") != "excerpt" else "fan",
            extraction_method="api" if is_api else ("excerpt" if is_excerpt else "manual"),
        )
        
        graded = grade_quote(
            text=quote_item.get("text", ""),
            speaker=quote_item.get("speaker", "unknown"),
            factors=factors,
        )
        graded_quotes.append(graded)
    
    # Sort by score
    graded_quotes.sort(key=lambda x: x.score, reverse=True)
    
    # Build result
    result = GradingResult(
        character=character,
        work=work,
        graded_quotes=graded_quotes,
    )
    
    # Apply grade filter if specified
    if min_grade:
        result.graded_quotes = result.get_quotes_by_grade(min_grade)
        # Recalculate summary
        result._calculate_summary()
    
    return result


def fetch_quotes_graded_dict(
    character: str,
    work: str = "",
    include_excerpt: bool = True,
    min_grade: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function returning dict format.
    
    Args:
        character: Character name
        work: Source work name
        include_excerpt: Whether to include smart excerpt fallbacks
        min_grade: Minimum grade as string (S/A/B/C/D/F) or None
        
    Returns:
        Dict with grading results
    """
    grade_enum = ReliabilityGrade(min_grade) if min_grade else None
    result = fetch_quotes_graded(character, work, include_excerpt, grade_enum)
    return result.to_dict()


def get_best_quotes(
    character: str,
    work: str = "",
    count: int = 10,
    min_grade: ReliabilityGrade = ReliabilityGrade.B,
) -> List[GradedQuote]:
    """Get the best quotes for a character.
    
    Args:
        character: Character name
        work: Source work name
        count: Number of quotes to return
        min_grade: Minimum grade threshold
        
    Returns:
        List of top graded quotes meeting criteria
    """
    result = fetch_quotes_graded(character, work, min_grade=min_grade)
    return result.graded_quotes[:count]


# Legacy compatibility
fetch_quotes = fetch_quotes_graded
