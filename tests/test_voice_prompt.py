from anime_character_loader.generator.voice import build_voice_prompt, render_voice_prompt_markdown


def test_build_voice_prompt_contains_required_schema_fields():
    prompt = build_voice_prompt(
        character="Megumi Katou",
        source_work="Saenai Heroine no Sodatekata",
        description="A calm, quiet, intelligent girl with subtle warmth and composed delivery.",
    )

    data = prompt.to_dict()

    assert data["character"] == "Megumi Katou"
    assert data["source_work"] == "Saenai Heroine no Sodatekata"
    assert isinstance(data["tone"], list) and data["tone"]
    assert data["pace"]
    assert data["emotion_range"]
    assert data["pause_style"]
    assert isinstance(data["banned_traits"], list) and data["banned_traits"]
    assert isinstance(data["sample_lines"], list) and len(data["sample_lines"]) >= 4


def test_render_voice_prompt_markdown_includes_required_sections():
    prompt = build_voice_prompt(
        character="Utaha Kasumigaoka",
        source_work="Saekano",
        description="A confident, intelligent, sarcastic girl with a sharp tongue.",
    )

    rendered = render_voice_prompt_markdown(prompt)

    assert "## Voice Prompt" in rendered
    assert "- tone:" in rendered
    assert "- pace:" in rendered
    assert "- emotion_range:" in rendered
    assert "- pause_style:" in rendered
    assert "- banned_traits:" in rendered
    assert "### Voice Calibration Sample Lines" in rendered
    assert "[mild_irritation]" in rendered


def test_voice_prompt_markdown_is_api_agnostic():
    prompt = build_voice_prompt(
        character="Mai Sakurajima",
        source_work="Seishun Buta Yarou",
        description="A calm and serious actress with gentle restraint.",
    )

    rendered = render_voice_prompt_markdown(prompt)

    assert "ElevenLabs" not in rendered
    assert "OpenAI" not in rendered
    assert "API key" not in rendered
