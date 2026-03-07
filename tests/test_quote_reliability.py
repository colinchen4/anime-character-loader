"""Tests for quote reliability grading system."""

import pytest

from anime_character_loader.validator.quote_reliability import (
    GradingFactors,
    GradingResult,
    ReliabilityGrade,
    SourceType,
    calculate_grade_score,
    convert_wikiquote_source,
    grade_quote,
    grade_quotes_batch,
    score_to_grade,
)


class TestReliabilityGrades:
    """Test reliability grade calculations."""
    
    def test_score_to_grade_s(self):
        assert score_to_grade(0.95) == ReliabilityGrade.S
        assert score_to_grade(0.90) == ReliabilityGrade.S
    
    def test_score_to_grade_a(self):
        assert score_to_grade(0.89) == ReliabilityGrade.A
        assert score_to_grade(0.80) == ReliabilityGrade.A
    
    def test_score_to_grade_b(self):
        assert score_to_grade(0.79) == ReliabilityGrade.B
        assert score_to_grade(0.65) == ReliabilityGrade.B
    
    def test_score_to_grade_f(self):
        assert score_to_grade(0.34) == ReliabilityGrade.F
        assert score_to_grade(0.0) == ReliabilityGrade.F


class TestGradingFactors:
    """Test grading factor calculations."""
    
    def test_official_script_base_grade(self):
        factors = GradingFactors(source_type=SourceType.OFFICIAL_SCRIPT)
        score, reason = calculate_grade_score(factors)
        assert score >= 0.90  # S grade base
        assert ReliabilityGrade.S == score_to_grade(score)
    
    def test_yurippe_base_grade(self):
        factors = GradingFactors(source_type=SourceType.YURIPPE_API)
        score, reason = calculate_grade_score(factors)
        assert 0.65 <= score <= 0.75  # B grade base
        assert score_to_grade(score) == ReliabilityGrade.B
    
    def test_verification_bonus(self):
        base_factors = GradingFactors(source_type=SourceType.WIKI_API)
        verified_factors = GradingFactors(
            source_type=SourceType.WIKI_API,
            speaker_verified=True,
            context_verified=True
        )
        
        base_score, _ = calculate_grade_score(base_factors)
        verified_score, _ = calculate_grade_score(verified_factors)
        
        assert verified_score > base_score
    
    def test_translation_penalty(self):
        official = GradingFactors(
            source_type=SourceType.YURIPPE_API,
            translation_quality=None
        )
        machine = GradingFactors(
            source_type=SourceType.YURIPPE_API,
            translation_quality="machine"
        )
        
        official_score, _ = calculate_grade_score(official)
        machine_score, _ = calculate_grade_score(machine)
        
        assert machine_score < official_score


class TestGradedQuote:
    """Test quote grading."""
    
    def test_grade_quote_basic(self):
        factors = GradingFactors(source_type=SourceType.YURIPPE_API)
        graded = grade_quote(
            text="Test quote",
            speaker="Test Character",
            factors=factors
        )
        
        assert graded.text == "Test quote"
        assert graded.speaker == "Test Character"
        assert graded.grade == ReliabilityGrade.B
        assert 0 <= graded.score <= 1
    
    def test_grade_quote_with_verification(self):
        factors = GradingFactors(
            source_type=SourceType.YURIPPE_API,
            speaker_verified=True,
            context_verified=True,
            has_multiple_attestations=True,
        )
        graded = grade_quote(
            text="Verified quote",
            speaker="Character",
            factors=factors
        )
        
        assert graded.score > 0.70  # Should be boosted above base B
        assert "verified" in graded.grade_reason.lower()


class TestGradingResult:
    """Test grading result aggregation."""
    
    def test_empty_result(self):
        result = GradingResult(
            character="Test",
            work="Test Work",
            graded_quotes=[]
        )
        assert result.average_score == 0.0
        assert result.overall_grade is None
    
    def test_result_summary_calculation(self):
        quotes_data = [
            {
                "text": f"Quote {i}",
                "speaker": "Character",
                "source_type": "yurippe",
            }
            for i in range(5)
        ]
        
        result = grade_quotes_batch("Character", "Work", quotes_data)
        
        assert result.total_quotes == 5
        assert result.summary[ReliabilityGrade.B] == 5
        assert result.average_score > 0
        assert result.overall_grade is not None
    
    def test_get_quotes_by_grade(self):
        quotes_data = [
            {"text": "High quality", "source_type": "official_script"},
            {"text": "Medium quality", "source_type": "yurippe"},
            {"text": "Low quality", "source_type": "smart_excerpt"},
        ]
        
        result = grade_quotes_batch("Char", "Work", quotes_data)
        
        s_quotes = result.get_quotes_by_grade(ReliabilityGrade.S)
        b_quotes = result.get_quotes_by_grade(ReliabilityGrade.B)
        
        assert len(s_quotes) >= 1  # At least official_script
        assert len(b_quotes) >= 2  # S, A, and B grades


class TestSourceConversion:
    """Test source type conversion."""
    
    def test_convert_yurippe(self):
        assert convert_wikiquote_source("yurippe") == SourceType.YURIPPE_API
    
    def test_convert_wiki(self):
        assert convert_wikiquote_source("wiki") == SourceType.WIKI_BROWSER
    
    def test_convert_excerpt(self):
        assert convert_wikiquote_source("excerpt") == SourceType.SMART_EXCERPT
    
    def test_convert_unknown(self):
        assert convert_wikiquote_source("unknown") == SourceType.UNKNOWN


class TestRecommendations:
    """Test recommendation generation."""
    
    def test_high_quality_recommendation(self):
        quotes_data = [
            {"text": f"Quote {i}", "source_type": "official_script"}
            for i in range(10)
        ]
        
        result = grade_quotes_batch("Char", "Work", quotes_data)
        
        assert any("fine-tuning" in r.lower() for r in result.recommendations)
    
    def test_low_quality_warning(self):
        quotes_data = [
            {"text": f"Quote {i}", "source_type": "smart_excerpt"}
            for i in range(3)
        ]
        
        result = grade_quotes_batch("Char", "Work", quotes_data)
        
        assert any("low reliability" in r.lower() for r in result.recommendations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
