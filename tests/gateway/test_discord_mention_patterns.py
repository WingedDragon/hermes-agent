"""Tests for Discord mention_patterns functionality."""

import json
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig


def _ensure_discord_mock():
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return

    discord_mod = MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    discord_mod.DMChannel = type("DMChannel", (), {})
    discord_mod.Thread = type("Thread", (), {})
    discord_mod.ForumChannel = type("ForumChannel", (), {})
    discord_mod.ui = SimpleNamespace(View=object, button=lambda *a, **k: (lambda fn: fn), Button=object)
    discord_mod.ButtonStyle = SimpleNamespace(success=1, primary=2, secondary=2, danger=3, green=1, grey=2, blurple=2, red=3)
    discord_mod.Color = SimpleNamespace(orange=lambda: 1, green=lambda: 2, blue=lambda: 3, red=lambda: 4, purple=lambda: 5)
    discord_mod.Interaction = object
    discord_mod.Embed = MagicMock
    discord_mod.app_commands = SimpleNamespace(
        describe=lambda **kwargs: (lambda fn: fn),
        choices=lambda **kwargs: (lambda fn: fn),
        Choice=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    ext_mod = MagicMock()
    commands_mod = MagicMock()
    commands_mod.Bot = MagicMock
    ext_mod.commands = commands_mod

    sys.modules.setdefault("discord", discord_mod)
    sys.modules.setdefault("discord.ext", ext_mod)
    sys.modules.setdefault("discord.ext.commands", commands_mod)


_ensure_discord_mock()

import gateway.platforms.discord as discord_platform  # noqa: E402
from gateway.platforms.discord import DiscordAdapter  # noqa: E402


class FakeTextChannel:
    def __init__(self, channel_id: int = 1, name: str = "general", guild_name: str = "Hermes Server"):
        self.id = channel_id
        self.name = name
        self.guild = SimpleNamespace(name=guild_name)
        self.topic = None


class FakeDMChannel:
    def __init__(self, channel_id: int = 1, name: str = "dm"):
        self.id = channel_id
        self.name = name


def make_message(*, channel, content: str, mentions=None):
    author = SimpleNamespace(id=42, display_name="Tester", name="Tester")
    return SimpleNamespace(
        id=123,
        content=content,
        mentions=list(mentions or []),
        attachments=[],
        reference=None,
        created_at=datetime.now(timezone.utc),
        channel=channel,
        author=author,
    )


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.delenv("DISCORD_MENTION_PATTERNS", raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    a = DiscordAdapter(config)
    a._client = SimpleNamespace(user=SimpleNamespace(id=999))
    a._text_batch_delay_seconds = 0
    a.handle_message = AsyncMock()
    return a


@pytest.mark.asyncio
async def test_mention_pattern_triggers_response(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_MENTION_PATTERNS", json.dumps([r"hey\s+bot"]))
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    a = DiscordAdapter(config)
    a._client = SimpleNamespace(user=SimpleNamespace(id=999))
    a._text_batch_delay_seconds = 0
    a.handle_message = AsyncMock()

    message = make_message(channel=FakeTextChannel(channel_id=100), content="hey bot do something")
    await a._handle_message(message)

    a.handle_message.assert_awaited_once()
    event = a.handle_message.await_args.args[0]
    assert event.text == "hey bot do something"


@pytest.mark.asyncio
async def test_mention_pattern_no_match_still_rejected(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_MENTION_PATTERNS", json.dumps([r"hey\s+bot"]))
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    a = DiscordAdapter(config)
    a._client = SimpleNamespace(user=SimpleNamespace(id=999))
    a._text_batch_delay_seconds = 0
    a.handle_message = AsyncMock()

    message = make_message(channel=FakeTextChannel(channel_id=100), content="hello everyone")
    await a._handle_message(message)

    a.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_mention_pattern_case_insensitive(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_MENTION_PATTERNS", json.dumps(["HEY BOT"]))
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    a = DiscordAdapter(config)
    a._client = SimpleNamespace(user=SimpleNamespace(id=999))
    a._text_batch_delay_seconds = 0
    a.handle_message = AsyncMock()

    message = make_message(channel=FakeTextChannel(channel_id=100), content="hey bot help me")
    await a._handle_message(message)

    a.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_mention_pattern_from_config_extra(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.delenv("DISCORD_MENTION_PATTERNS", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    config = PlatformConfig(enabled=True, token="fake-token", extra={"mention_patterns": [r"@hermes"]})
    a = DiscordAdapter(config)
    a._client = SimpleNamespace(user=SimpleNamespace(id=999))
    a._text_batch_delay_seconds = 0
    a.handle_message = AsyncMock()

    message = make_message(channel=FakeTextChannel(channel_id=100), content="@hermes what time is it?")
    await a._handle_message(message)

    a.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_mention_patterns_default_behavior(adapter, monkeypatch):
    """Without mention_patterns configured, default @mention behavior applies."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    message = make_message(channel=FakeTextChannel(channel_id=100), content="hello")
    await adapter._handle_message(message)

    adapter.handle_message.assert_not_awaited()


def test_compile_mention_patterns_invalid_regex(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.setenv("DISCORD_MENTION_PATTERNS", json.dumps(["valid", "[invalid"]))

    config = PlatformConfig(enabled=True, token="fake-token")
    a = DiscordAdapter(config)
    assert len(a._mention_patterns) == 1


def test_compile_mention_patterns_string_input(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", type("Thread", (), {}), raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", type("ForumChannel", (), {}), raising=False)
    monkeypatch.setenv("DISCORD_MENTION_PATTERNS", "hello")

    config = PlatformConfig(enabled=True, token="fake-token")
    a = DiscordAdapter(config)
    assert len(a._mention_patterns) == 1
