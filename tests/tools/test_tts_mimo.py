"""Tests for the Xiaomi MiMo TTS provider (tools/tts_tool._generate_mimo_tts).

These exercise request construction and response parsing in isolation by
mocking the `requests.post` call — no network traffic.
"""
import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from tools import tts_tool


def _fake_response(audio_bytes: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "audio": {
                        "data": base64.b64encode(audio_bytes).decode("ascii"),
                    }
                }
            }
        ]
    }
    return resp


def test_generate_mimo_tts_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    out = tmp_path / "out.wav"
    with pytest.raises(ValueError, match="MiMo API key not set"):
        tts_tool._generate_mimo_tts("hi", str(out), {})


def test_generate_mimo_tts_reads_api_key_from_config(tmp_path, monkeypatch):
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    out = tmp_path / "out.wav"

    with patch("requests.post", return_value=_fake_response(b"wavdata")) as mock_post:
        tts_tool._generate_mimo_tts(
            "hi",
            str(out),
            {"mimo": {"api_key": "config-key"}},
        )

    assert mock_post.call_args.kwargs["headers"]["api-key"] == "config-key"


def test_generate_mimo_tts_writes_wav_and_posts_expected_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    out = tmp_path / "out.wav"
    fake_audio = b"RIFF....WAVEdata"

    with patch("requests.post", return_value=_fake_response(fake_audio)) as mock_post:
        result_path = tts_tool._generate_mimo_tts(
            "<style>Happy</style>hello",
            str(out),
            {"mimo": {"voice": "default_zh"}},
        )

    assert result_path == str(out)
    assert out.read_bytes() == fake_audio

    args, kwargs = mock_post.call_args
    assert args[0] == tts_tool.DEFAULT_MIMO_BASE_URL
    assert kwargs["headers"]["api-key"] == "test-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"

    payload = kwargs["json"]
    assert payload["model"] == tts_tool.DEFAULT_MIMO_MODEL
    assert payload["audio"] == {"format": "wav", "voice": "default_zh"}
    # Target text must be delivered as a role=assistant message (MiMo requirement)
    assert payload["messages"] == [
        {"role": "assistant", "content": "<style>Happy</style>hello"}
    ]


def test_generate_mimo_tts_auto_prepends_style_from_config(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    out = tmp_path / "out.wav"

    with patch("requests.post", return_value=_fake_response(b"wavdata")) as mock_post:
        tts_tool._generate_mimo_tts(
            "明天周五啦",
            str(out),
            {"mimo": {"style": "Happy"}},
        )

    payload = mock_post.call_args.kwargs["json"]
    assert payload["messages"][0]["content"] == "<style>Happy</style>明天周五啦"


def test_generate_mimo_tts_preserves_explicit_style_tag(tmp_path, monkeypatch):
    """If the caller already set a <style> tag, the config default must not override it."""
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    out = tmp_path / "out.wav"

    with patch("requests.post", return_value=_fake_response(b"wavdata")) as mock_post:
        tts_tool._generate_mimo_tts(
            "<style>Whisper</style>shh",
            str(out),
            {"mimo": {"style": "Happy"}},
        )

    payload = mock_post.call_args.kwargs["json"]
    assert payload["messages"][0]["content"] == "<style>Whisper</style>shh"


def test_generate_mimo_tts_rejects_empty_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    out = tmp_path / "out.wav"

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"audio": {"data": ""}}}]}

    with patch("requests.post", return_value=resp):
        with pytest.raises(RuntimeError, match="empty audio"):
            tts_tool._generate_mimo_tts("hi", str(out), {})


def test_generate_mimo_tts_unexpected_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    out = tmp_path / "out.wav"

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": []}

    with patch("requests.post", return_value=resp):
        with pytest.raises(RuntimeError, match="unexpected response shape"):
            tts_tool._generate_mimo_tts("hi", str(out), {})


def test_check_tts_requirements_detects_mimo(monkeypatch):
    # Hide other providers to isolate the MIMO_API_KEY path
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("MIMO_API_KEY", "test-key")

    # Force edge_tts / elevenlabs / openai imports to fail so we fall through.
    def boom():
        raise ImportError("stub")

    monkeypatch.setattr(tts_tool, "_import_edge_tts", boom)
    monkeypatch.setattr(tts_tool, "_import_elevenlabs", boom)
    monkeypatch.setattr(tts_tool, "_import_openai_client", boom)
    monkeypatch.setattr(tts_tool, "_check_neutts_available", lambda: False)

    assert tts_tool.check_tts_requirements() is True
