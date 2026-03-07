"""Tests for use-case mode presets."""

import pytest

from anime_character_loader.generator.modes import (
    UseCaseMode,
    apply_mode,
    get_mode_by_name,
    get_mode_config,
    list_modes,
    ModeApplicationResult,
)


class TestModeEnum:
    """Test use case mode enum."""
    
    def test_roleplay_mode(self):
        assert UseCaseMode.ROLEPLAY.value == "roleplay"
    
    def test_chatbot_mode(self):
        assert UseCaseMode.CHATBOT.value == "chatbot"
    
    def test_creative_mode(self):
        assert UseCaseMode.CREATIVE.value == "creative"


class TestGetModeByName:
    """Test mode name resolution."""
    
    def test_exact_match(self):
        assert get_mode_by_name("roleplay") == UseCaseMode.ROLEPLAY
        assert get_mode_by_name("chatbot") == UseCaseMode.CHATBOT
        assert get_mode_by_name("creative") == UseCaseMode.CREATIVE
    
    def test_case_insensitive(self):
        assert get_mode_by_name("ROLEPLAY") == UseCaseMode.ROLEPLAY
        assert get_mode_by_name("ChatBot") == UseCaseMode.CHATBOT
    
    def test_aliases(self):
        assert get_mode_by_name("rp") == UseCaseMode.ROLEPLAY
        assert get_mode_by_name("role play") == UseCaseMode.ROLEPLAY
        assert get_mode_by_name("bot") == UseCaseMode.CHATBOT
        assert get_mode_by_name("assistant") == UseCaseMode.CHATBOT
        assert get_mode_by_name("write") == UseCaseMode.CREATIVE
    
    def test_invalid_mode(self):
        assert get_mode_by_name("invalid") is None
        assert get_mode_by_name("") is None


class TestModeConfigs:
    """Test mode configuration presets."""
    
    def test_roleplay_config(self):
        config = get_mode_config(UseCaseMode.ROLEPLAY)
        
        assert config.include_voice_prompt is True
        assert config.include_relationship_graph is True
        assert config.include_quotes is True
        assert config.quote_count == 8
        assert config.min_quote_grade == "B"
        assert config.validation_min_score == 85.0
        assert config.enforce_in_character is True
        assert config.allow_oob_knowledge is False
    
    def test_chatbot_config(self):
        config = get_mode_config(UseCaseMode.CHATBOT)
        
        assert config.include_voice_prompt is True
        assert config.include_relationship_graph is False
        assert config.include_quotes is True
        assert config.quote_count == 3
        assert config.min_quote_grade == "C"
        assert config.validation_min_score == 75.0
        assert config.enforce_in_character is True
        assert config.allow_oob_knowledge is True  # Key difference
    
    def test_creative_config(self):
        config = get_mode_config(UseCaseMode.CREATIVE)
        
        assert config.include_voice_prompt is True
        assert config.include_quotes is True
        assert config.quote_count == 10
        assert config.min_quote_grade == "C"
        assert config.validation_min_score == 70.0
        assert config.enforce_in_character is False  # Key difference
        assert config.allow_oob_knowledge is True


class TestApplyMode:
    """Test mode application."""
    
    def test_apply_roleplay(self):
        result = apply_mode("roleplay")
        
        assert result.mode == UseCaseMode.ROLEPLAY
        assert "--voice-prompt" in result.cli_flags
        assert "--relationship-graph" in result.cli_flags
        assert result.config.quote_count == 8
    
    def test_apply_chatbot(self):
        result = apply_mode("chatbot")
        
        assert result.mode == UseCaseMode.CHATBOT
        assert "--voice-prompt" in result.cli_flags
        assert "--relationship-graph" not in result.cli_flags
    
    def test_apply_creative(self):
        result = apply_mode("creative")
        
        assert result.mode == UseCaseMode.CREATIVE
        assert result.config.response_length == "long"
    
    def test_apply_invalid_mode(self):
        with pytest.raises(ValueError) as exc_info:
            apply_mode("invalid_mode")
        
        assert "Invalid mode" in str(exc_info.value)
        assert "roleplay" in str(exc_info.value)


class TestListModes:
    """Test mode listing."""
    
    def test_list_modes_returns_all(self):
        modes = list_modes()
        
        assert len(modes) == 3
        mode_ids = [m["id"] for m in modes]
        assert "roleplay" in mode_ids
        assert "chatbot" in mode_ids
        assert "creative" in mode_ids
    
    def test_list_modes_structure(self):
        modes = list_modes()
        
        for mode in modes:
            assert "id" in mode
            assert "description" in mode
            assert "best_for" in mode
            assert "key_features" in mode
            assert "config" in mode


class TestModeGeneratorOptions:
    """Test generator options building."""
    
    def test_roleplay_options(self):
        result = apply_mode("roleplay")
        opts = result.generator_options
        
        assert opts["include_voice_prompt"] is True
        assert opts["include_relationship_graph"] is True
        assert opts["enforce_in_character"] is True
        assert opts["greeting_style"] == "in_character"
    
    def test_chatbot_options(self):
        result = apply_mode("chatbot")
        opts = result.generator_options
        
        assert opts["enforce_in_character"] is True
        assert opts["greeting_style"] == "neutral"
    
    def test_creative_options(self):
        result = apply_mode("creative")
        opts = result.generator_options
        
        assert opts["enforce_in_character"] is False
        assert opts["greeting_style"] == "none"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
