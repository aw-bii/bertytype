"""Snapshot tests for messages.py and llm/prompts.py string constants."""
import pytest
from bertytype import messages
from bertytype.llm import prompts


class TestMessages:
    def test_all_error_strings_non_empty(self):
        for name in dir(messages):
            if name.startswith("ERROR_") or name.startswith("INFO_"):
                val = getattr(messages, name)
                assert isinstance(val, str) and len(val) > 0, f"{name} is empty"

    def test_no_em_dashes(self):
        for name in dir(messages):
            if name.startswith(("ERROR_", "INFO_")):
                val = getattr(messages, name)
                assert "—" not in val, f"{name} contains an em dash"
                assert " -- " not in val, f"{name} contains --"

    def test_format_placeholders_valid(self):
        formatted = messages.INFO_TRANSCRIPTION_COMPLETE.format(name="test.txt")
        assert "test.txt" in formatted

    def test_key_messages_present(self):
        assert hasattr(messages, "ERROR_OLLAMA_UNAVAILABLE")
        assert hasattr(messages, "ERROR_INJECTION_FAILED")
        assert hasattr(messages, "ERROR_TRANSCRIPTION_FAILED")
        assert hasattr(messages, "INFO_TRANSCRIPTION_COMPLETE")


class TestPrompts:
    def test_known_modes_non_empty(self):
        for mode in ("clean_up", "rewrite"):
            result = prompts.get_prompt(mode, "hello world")
            assert isinstance(result, str) and len(result) > 0

    def test_text_injected_into_prompt(self):
        result = prompts.get_prompt("clean_up", "test transcript")
        assert "test transcript" in result

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown mode"):
            prompts.get_prompt("nonexistent_mode", "text")

    def test_sanitize_strips_non_printable(self):
        result = prompts.get_prompt("clean_up", "hello\x00world")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_no_em_dashes_in_templates(self):
        for mode in ("clean_up", "rewrite"):
            result = prompts.get_prompt(mode, "x")
            assert "—" not in result
