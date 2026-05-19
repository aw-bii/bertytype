import pytest
from unittest.mock import patch, MagicMock
from bertytype.llm import prompts, client


def test_get_prompt_clean_up_contains_text():
    result = prompts.get_prompt("clean_up", "um hello world")
    assert "hello world" in result


def test_get_prompt_rewrite_contains_text():
    result = prompts.get_prompt("rewrite", "gonna do stuff")
    assert "gonna do stuff" in result


def test_get_prompt_unknown_mode_raises():
    with pytest.raises(ValueError, match="Unknown mode"):
        prompts.get_prompt("blah", "text")


def test_refine_posts_to_ollama():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "  cleaned text  "}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = client.refine("um hello", "clean_up", "gemma4")

    assert result == "cleaned text"
    call_kwargs = mock_post.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
    assert payload["model"] == "gemma4"


def test_refine_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500")

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(Exception, match="500"):
            client.refine("text", "clean_up", "gemma4")


def test_refine_strips_whitespace():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "\n  result \n"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        result = client.refine("text", "rewrite", "gemma4")

    assert result == "result"


def test_sanitize_removes_control_characters():
    dirty = "hello\x00\x1b\x07world"
    result = prompts._sanitize(dirty)
    assert result == "helloworld"


def test_sanitize_removes_null_bytes():
    result = prompts._sanitize("test\x00string")
    assert result == "teststring"


def test_sanitize_preserves_normal_text():
    text = "Hello, world! 123 😀"
    result = prompts._sanitize(text)
    assert result == text


def test_sanitize_preserves_newlines_and_tabs():
    text = "line1\nline2\twith tab"
    result = prompts._sanitize(text)
    assert result == text


def test_get_prompt_sanitizes_input():
    dirty = "safe\x00\x07text"
    result = prompts.get_prompt("clean_up", dirty)
    assert "safe\x00" not in result
    assert "safe\x07" not in result
    assert "safetext" in result


def test_refine_raises_runtime_on_connection_error(mocker):
    mocker.patch("requests.post", side_effect=__import__("requests").ConnectionError)
    with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
        client.refine("hello", "clean_up", "gemma4:e2b")


def test_refine_raises_runtime_on_timeout(mocker):
    mocker.patch("requests.post", side_effect=__import__("requests").Timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        client.refine("hello", "clean_up", "gemma4:e2b", timeout=5)


def test_refine_raises_runtime_on_bad_response_format(mocker):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"unexpected": "key"}
    mocker.patch("requests.post", return_value=mock_resp)
    with pytest.raises(RuntimeError, match="Unexpected Ollama response"):
        client.refine("hello", "clean_up", "gemma4:e2b")
