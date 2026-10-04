"""Low-level Discord API helpers: headers, user/server lookup, sending messages, reactions, Karuta message lookup, buttons."""
import base64
import json
import uuid

import pytest

from conftest import API, CARD_EMOJIS, KARUTA_ID, USER_IDS, FakeResponse, karuta_reply, user_msg


def decode(b64: str) -> dict:
    return json.loads(base64.b64decode(b64))


# --------------------------------------------------------------------------- #
# get_headers
# --------------------------------------------------------------------------- #

def test_headers_contain_token_and_browser_fingerprint(bot):
    headers = bot.get_headers("tok1", "100")
    assert headers["Authorization"] == "tok1"
    assert headers["Content-Type"] == "application/json"
    assert headers["Origin"] == "https://discord.com"
    props = decode(headers["X-Super-Properties"])
    assert props["os"] == "Windows"
    assert props["browser_user_agent"] == headers["User-Agent"]
    assert props["browser_version"] in bot.BROWSER_VERSIONS
    assert f"Chrome/{props['browser_version']}" in headers["User-Agent"]
    assert props["os_version"] == "10"
    assert "Windows NT 10.0" in headers["User-Agent"]  # Windows 11 browsers also report NT 10.0
    assert "Brave/" not in headers["User-Agent"]  # Real Brave sends Chrome's user agent
    assert props["client_build_number"] in (381653, 382032, 382201, 382355, 417521)


def test_headers_context_properties_track_channel(bot):
    assert decode(bot.get_headers("tok1", "100")["X-Context-Properties"]) == {"location": "Channel", "location_channel_id": "100", "location_channel_type": 0}
    assert decode(bot.get_headers("tok1", "300")["X-Context-Properties"])["location_channel_id"] == "300"


def test_headers_fingerprint_is_stable_per_token(bot, monkeypatch):
    import main
    first = bot.get_headers("tok1", "100")
    monkeypatch.setattr(main.random, "choice", lambda seq: list(seq)[-1])  # Different random picks must not change an existing token's fingerprint
    second = bot.get_headers("tok1", "101")
    for key in ("User-Agent", "X-Super-Properties", "Authorization"):
        assert first[key] == second[key]
    bot.get_headers("tok2", "100")
    assert set(bot.token_headers) == {"tok1", "tok2"}


def test_headers_fingerprint_is_stable_across_runs(bot):
    import main
    first = bot.get_headers("tok1", "100")
    second = main.DropScript().get_headers("tok1", "100")  # A fresh script instance, like a restart
    assert first["X-Super-Properties"] == second["X-Super-Properties"]
    agents = {main.DropScript().get_headers(f"token{i}", "100")["User-Agent"] for i in range(20)}
    assert len(agents) > 1  # Different accounts still get different fingerprints


def test_headers_cache_is_not_mutated_by_context_properties(bot):
    bot.get_headers("tok1", "100")
    assert "X-Context-Properties" not in bot.token_headers["tok1"]


# --------------------------------------------------------------------------- #
# get_user_id / get_server_id
# --------------------------------------------------------------------------- #

async def test_get_user_id_success(bot, discord):
    assert await bot.get_user_id("tok2", "100") == USER_IDS["tok2"]
    assert discord.calls("GET", "/users/@me")[0].token == "tok2"


@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_get_user_id_failure_returns_none(bot, discord, status):
    discord.respond("GET", "/users/@me", status)
    assert await bot.get_user_id("tok1", "100") is None


async def test_get_server_id_success(bot, discord):
    assert await bot.get_server_id("tok1", 1, "300") == discord.guild_id


async def test_get_server_id_failure(bot, discord, capsys):
    discord.respond("GET", r"/channels/300$", 403)
    assert await bot.get_server_id("tok1", 1, "300") is None
    assert "[Account #1] Retrieve Guild ID failed: Error code 403." in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# send_message
# --------------------------------------------------------------------------- #

async def test_send_message_success(bot, discord, capsys):
    sent = await bot.send_message("tok1", 1, "100", "hello", 0)
    assert sent["content"] == "hello"
    assert sent["author"]["id"] == USER_IDS["tok1"]
    request = discord.calls("POST")[0]
    assert request.json == {"content": "hello", "tts": False}
    assert request.url == f"{API}/channels/100/messages"
    assert "✅ [Account #1] Sent message 'hello'." in capsys.readouterr().out


@pytest.mark.parametrize("status, text", [
    (401, "Invalid token."),
    (403, "Token banned or insufficient permissions."),
    (400, "Error code 400."),
    (500, "Error code 500."),
])
async def test_send_message_failure(bot, discord, capsys, status, text):
    discord.respond("POST", "/messages$", status)
    assert await bot.send_message("tok1", 1, "100", "hi", 0) is None
    assert len(discord.calls("POST")) == 1  # No retry
    assert f"Send message 'hi' failed: {text}" in capsys.readouterr().out


async def test_send_message_retries_after_rate_limit(bot, discord, clock):
    discord.respond("POST", "/messages$", 429, 429)
    sent = await bot.send_message("tok1", 1, "100", "hi", 0)
    assert sent["content"] == "hi"
    assert len(discord.calls("POST")) == 3
    assert clock.sleeps == [1, 1]


async def test_rate_limit_waits_for_discords_retry_after(bot, discord, clock, capsys):
    discord.respond("POST", "/messages$", FakeResponse(429, {"message": "You are being rate limited.", "retry_after": 2.5, "global": False}))
    await bot.send_message("tok1", 1, "100", "hi", 0)
    assert clock.sleeps == [2.5]
    assert "Rate limited, retrying after 2.5s." in capsys.readouterr().out


async def test_rate_limit_retry_after_is_capped(bot, discord, clock):
    discord.respond("POST", "/messages$", FakeResponse(429, {"message": "You are being rate limited.", "retry_after": 600, "global": True}))
    await bot.send_message("tok1", 1, "100", "hi", 0)
    assert clock.sleeps == [10]


async def test_send_message_gives_up_after_rate_limit(bot, discord, capsys):
    discord.respond("POST", "/messages$", *[429] * 10)
    assert await bot.send_message("tok1", 1, "100", "hi", 0) is None
    assert len(discord.calls("POST")) == bot.RATE_LIMIT + 1
    out = capsys.readouterr().out
    assert "(3/3): Rate limited" in out
    assert "failed: Error code 429." in out


async def test_send_message_with_exhausted_rate_limit_never_retries(bot, discord):
    """Random chat messages are sent with rate_limited=RATE_LIMIT so they never retry."""
    discord.respond("POST", "/messages$", 429)
    assert await bot.send_message("tok1", 1, "100", "hi", bot.RATE_LIMIT) is None
    assert len(discord.calls("POST")) == 1


# --------------------------------------------------------------------------- #
# add_reaction
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("channel_id, name", [
    ("100", "Drop Channel #1"),
    ("101", "Drop Channel #2"),
    ("200", "Server Activity Drop Channel #1"),
    ("777", "Channel 777"),
])
async def test_add_reaction_grab_card(bot, discord, capsys, channel_id, name):
    await bot.add_reaction("tok1", 1, channel_id, "999", CARD_EMOJIS[1], 0)
    assert discord.reactions() == [("tok1", channel_id, "999", CARD_EMOJIS[1])]
    assert f"✅ [Account #1] Grabbed card [2] in {name}." in capsys.readouterr().out


async def test_add_reaction_server_account_label(bot, discord, capsys):
    await bot.add_reaction("tok1", 0, "200", "999", CARD_EMOJIS[8], 0)
    assert "✅ [Server Account] Grabbed card [9] in Server Activity Drop Channel #1." in capsys.readouterr().out


@pytest.mark.parametrize("status, text", [
    (401, "failed: Invalid token."),
    (403, "failed: Token banned or insufficient permissions."),
    (404, "failed: Error code 404."),
])
async def test_add_reaction_grab_failures(bot, discord, capsys, status, text):
    discord.respond("PUT", "/reactions/", status)
    await bot.add_reaction("tok1", 1, "100", "999", CARD_EMOJIS[0], 0)
    assert len(discord.reactions()) == 1
    assert f"Grab card [1] in Drop Channel #1 {text}" in capsys.readouterr().out


async def test_add_reaction_grab_rate_limit_retry_and_give_up(bot, discord, clock, capsys):
    discord.respond("PUT", "/reactions/", *[429] * 10)
    await bot.add_reaction("tok1", 1, "100", "999", CARD_EMOJIS[0], 0)
    assert len(discord.reactions()) == bot.RATE_LIMIT + 1
    assert clock.sleeps == [1] * bot.RATE_LIMIT
    out = capsys.readouterr().out
    assert "Grab card [1] in Drop Channel #1 failed (1/3): Rate limited" in out
    assert "Grab card [1] in Drop Channel #1 failed: Error code 429." in out


async def test_add_reaction_grab_rate_limit_then_success(bot, discord, capsys):
    discord.respond("PUT", "/reactions/", 429)
    await bot.add_reaction("tok1", 1, "100", "999", CARD_EMOJIS[0], 0)
    assert len(discord.reactions()) == 2
    assert "✅ [Account #1] Grabbed card [1]" in capsys.readouterr().out


@pytest.fixture
def special_event_bot(bot):
    from types import SimpleNamespace
    bot.server_drop_checker = SimpleNamespace(special_event_tokens_dict = {"any": "eventTok", "🌼": "flowerTok"})
    return bot


@pytest.mark.parametrize("status, text", [
    (204, "✅ [Special Event Account] Grabbed 🎃 in Server Activity Drop Channel #1."),
    (401, "❌ [Special Event Account] Grab 🎃 in Server Activity Drop Channel #1 failed: Invalid token."),
    (403, "❌ [Special Event Account] Grab 🎃 in Server Activity Drop Channel #1 failed: Token banned or insufficient permissions."),
    (500, "❌ [Special Event Account] Grab 🎃 in Server Activity Drop Channel #1 failed: Error code 500."),
])
async def test_add_reaction_special_event(special_event_bot, discord, capsys, status, text):
    discord.respond("PUT", "/reactions/", status)
    await special_event_bot.add_reaction("eventTok", 0, "200", "999", "🎃", 0)
    assert text in capsys.readouterr().out


async def test_add_reaction_special_event_rate_limit(special_event_bot, discord, capsys):
    discord.respond("PUT", "/reactions/", *[429] * 10)
    await special_event_bot.add_reaction("flowerTok", 0, "100", "999", "🌼", 0)
    assert len(discord.reactions()) == 4
    out = capsys.readouterr().out
    assert "Grab 🌼 in Drop Channel #1 failed (3/3): Rate limited" in out
    assert "Grab 🌼 in Drop Channel #1 failed: Error code 429." in out


@pytest.mark.parametrize("status, text", [
    (204, "✅ [Account #2] Reacted 💰 in Command Channel #1."),
    (401, "❌ [Account #2] React 💰 in Command Channel #1 failed: Invalid token."),
    (403, "❌ [Account #2] React 💰 in Command Channel #1 failed: Token banned or insufficient permissions."),
    (400, "❌ [Account #2] React 💰 in Command Channel #1 failed: Error code 400."),
])
async def test_add_reaction_command_channel(bot, discord, capsys, status, text):
    discord.respond("PUT", "/reactions/", status)
    await bot.add_reaction("tok2", 2, "300", "999", "💰", 0)
    assert text in capsys.readouterr().out


async def test_add_reaction_command_channel_rate_limit(bot, discord, capsys):
    discord.respond("PUT", "/reactions/", 429, 429)
    await bot.add_reaction("tok2", 2, "300", "999", "💰", 0)
    assert len(discord.reactions()) == 3
    out = capsys.readouterr().out
    assert "React 💰 in Command Channel #1 failed (2/3): Rate limited" in out
    assert "✅ [Account #2] Reacted 💰" in out


async def test_add_reaction_other_emoji_elsewhere_is_silent(bot, discord, capsys):
    await bot.add_reaction("tok1", 1, "100", "999", "👍", 0)
    assert len(discord.reactions()) == 1
    assert capsys.readouterr().out == ""


async def test_add_reaction_server_account_non_event_token_is_silent(special_event_bot, discord, capsys):
    await special_event_bot.add_reaction("someoneElse", 0, "100", "999", "👍", 0)
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# get_payload
# --------------------------------------------------------------------------- #

def button_message(*buttons, rows = 1):
    msg = karuta_reply("777", None, title = "Burn Card", buttons = buttons)
    if rows == 2:  # Put each button on its own action row
        msg["components"] = [{"type": 1, "components": [b]} for b in msg["components"][0]["components"]]
    return msg


async def test_get_payload_by_emoji(bot, discord, capsys):
    msg = button_message(("❌", "cancel"), ("🔥", "confirm"))
    payload = await bot.get_payload("tok1", 1, "100", "🔥", msg)
    assert payload["type"] == 3
    assert payload["guild_id"] == discord.guild_id
    assert payload["channel_id"] == "100"
    assert payload["message_id"] == "777"
    assert payload["application_id"] == KARUTA_ID
    assert payload["message_flags"] == 0
    assert payload["data"] == {"component_type": 2, "custom_id": "confirm"}
    assert payload["nonce"].isdigit()
    uuid.UUID(payload["session_id"])
    assert "✅ [Account #1] Found 🔥 button successfully." in capsys.readouterr().out


async def test_get_payload_by_label_and_second_row(bot, discord):
    msg = button_message(("❌", "cancel"), ("✅", "ok"), rows = 2)
    msg["components"][1]["components"][0] = {"type": 2, "custom_id": "agree", "label": "I understand"}
    payload = await bot.get_payload("tok1", 1, "300", "I understand", msg)
    assert payload["data"]["custom_id"] == "agree"


async def test_get_payload_button_with_null_emoji_name(bot, discord):
    msg = button_message(("❌", "cancel"))
    msg["components"][0]["components"].insert(0, {"type": 2, "custom_id": "x", "emoji": {"name": None}, "label": "Go"})
    assert (await bot.get_payload("tok1", 1, "300", "Go", msg))["data"]["custom_id"] == "x"


async def test_get_payload_not_found(bot, discord):
    assert await bot.get_payload("tok1", 1, "100", "🔥", button_message(("❌", "cancel"))) is None
    assert await bot.get_payload("tok1", 1, "100", "🔥", {"id": "1", "author": {"id": KARUTA_ID}}) is None
    assert discord.requests == []  # The guild lookup only happens once a button is found


# --------------------------------------------------------------------------- #
# get_karuta_message
# --------------------------------------------------------------------------- #

SEARCHES = [
    ("Card Transfer", {"title": "Card Transfer"}, "card transfer"),
    ("Both sides must lock in before proceeding to the next step.", {"content": "... Both sides must lock in before proceeding to the next step."}, "multitrade lock"),
    ("This trade has been locked.", {"content": "This trade has been locked."}, "multitrade confirm"),
    ("Burn Card", {"title": "Burn Card"}, "burn"),
    ("Burn Cards", {"title": "Burn Cards"}, "multiburn"),
    ("Item Purchase", {"title": "Item Purchase"}, "item purchase"),
]


@pytest.mark.parametrize("search, spec, label", SEARCHES)
async def test_get_karuta_message_finds_each_type(bot, discord, capsys, search, spec, label):
    command = user_msg("10", USER_IDS["tok1"], "kcmd")
    target = karuta_reply("11", command, content = spec.get("content", ""), title = spec.get("title"))
    discord.add("300", command)
    discord.add("300", target)
    assert (await bot.get_karuta_message("tok1", 1, "300", search, 0))["id"] == "11"
    assert f"✅ [Account #1] Retrieved {label} message." in capsys.readouterr().out
    assert discord.calls("GET", r"messages\?limit=50")


@pytest.mark.parametrize("search, spec, label", SEARCHES)
async def test_get_karuta_message_ignores_other_users_and_non_karuta(bot, discord, capsys, search, spec, label):
    other = user_msg("10", USER_IDS["tok2"], "kcmd")
    mine = user_msg("11", USER_IDS["tok1"], "kcmd")
    discord.add("300", karuta_reply("12", other, content = spec.get("content", ""), title = spec.get("title")))  # Reply to someone else
    fake = karuta_reply("13", mine, content = spec.get("content", ""), title = spec.get("title"))
    fake["author"] = {"id": "123456"}  # Not Karuta
    discord.add("300", fake)
    discord.add("300", karuta_reply("14", None, content = spec.get("content", ""), title = spec.get("title")))  # Replied-to message deleted
    assert await bot.get_karuta_message("tok1", 1, "300", search, 0) is None
    assert f"Retrieve message failed: Message '{search}' not found in recent messages." in capsys.readouterr().out


async def test_get_karuta_message_requires_matching_search_type(bot, discord):
    mine = user_msg("10", USER_IDS["tok1"], "kmt")
    discord.add("300", karuta_reply("11", mine, content = "This trade has been locked."))
    discord.add("300", karuta_reply("12", mine, title = "Burn Cards"))
    discord.add("300", karuta_reply("13", mine, title = None))  # No embeds
    discord.history["300"][0]["embeds"] = []
    assert await bot.get_karuta_message("tok1", 1, "300", "Both sides must lock in before proceeding to the next step.", 0) is None
    assert await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0) is None  # "Burn Cards" is a different embed
    assert (await bot.get_karuta_message("tok1", 1, "300", "Burn Cards", 0))["id"] == "12"


async def test_get_karuta_message_matches_reply_to_given_command(bot, discord):
    old = user_msg("10", USER_IDS["tok1"], "kb old")
    new = user_msg("12", USER_IDS["tok1"], "kb new")
    discord.add("300", old)
    discord.add("300", karuta_reply("11", old, title = "Burn Card"))
    discord.add("300", new)
    assert await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0, "12") is None  # Karuta has not replied to the new command yet
    discord.add("300", karuta_reply("13", new, title = "Burn Card"))
    discord.add("300", karuta_reply("14", old, title = "Burn Card"))  # Newer reply to the old command
    assert (await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0, "12"))["id"] == "13"


async def test_get_karuta_message_returns_newest_match(bot, discord):
    mine = user_msg("10", USER_IDS["tok1"], "kb")
    discord.add("300", karuta_reply("11", mine, title = "Burn Card"))
    discord.add("300", karuta_reply("12", mine, title = "Burn Card"))
    assert (await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0))["id"] == "12"


async def test_get_karuta_message_rate_limit_retry(bot, discord, clock):
    mine = user_msg("10", USER_IDS["tok1"], "kb")
    discord.add("300", karuta_reply("11", mine, title = "Burn Card"))
    discord.respond("GET", r"limit=50", 429)
    assert (await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0))["id"] == "11"
    assert clock.sleeps == [1]


async def test_get_karuta_message_rate_limit_exhausted(bot, discord, capsys):
    discord.respond("GET", r"limit=50", *[429] * 10)
    assert await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0) is None
    assert len(discord.calls("GET", r"limit=50")) == 4
    assert "Retrieve message failed: Error code 429." in capsys.readouterr().out


async def test_get_karuta_message_http_error(bot, discord, capsys):
    discord.respond("GET", r"limit=50", 403)
    assert await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0) is None
    assert "Retrieve message failed: Error code 403." in capsys.readouterr().out


async def test_get_karuta_message_tolerates_empty_embed_list(bot, discord):
    mine = user_msg("10", USER_IDS["tok1"], "kb")
    broken = karuta_reply("11", mine, title = None)
    broken["embeds"] = []
    discord.add("300", broken)
    assert await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0) is None


async def test_get_karuta_message_does_not_match_when_user_lookup_fails(bot, discord):
    discord.respond("GET", "/users/@me", 429)
    discord.add("300", karuta_reply("11", None, title = "Burn Card", buttons = [("🔥", "burn")]))  # Someone else's burn, command deleted
    assert await bot.get_karuta_message("tok1", 1, "300", "Burn Card", 0) is None


# --------------------------------------------------------------------------- #
# get_grabbed_card_code
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("content", [
    "<@501> took the **Naruto Uzumaki** card `abc12`!",
    "<@501> fought off 2 others and took the **Mikasa** card `abc12`!",
    "<@501> took the **Card** card `abc12`! It's in **pristine** condition.",
])
async def test_get_grabbed_card_code_parses_grab_messages(bot, discord, content):
    discord.add("100", {"id": "50", "content": "<@501> is dropping 3 cards!", "author": {"id": KARUTA_ID}})
    discord.add("100", {"id": "51", "content": content, "author": {"id": KARUTA_ID}})
    assert await bot.get_grabbed_card_code("tok1", 1, "100", "50") == "abc12"


async def test_get_grabbed_card_code_filters(bot, discord):
    discord.add("100", {"id": "40", "content": "<@501> took the **Old** card `old11`!", "author": {"id": KARUTA_ID}})  # Before the drop
    discord.add("100", {"id": "50", "content": "drop", "author": {"id": KARUTA_ID}})
    discord.add("100", {"id": "51", "content": "<@502> took the **Other** card `oth22`!", "author": {"id": KARUTA_ID}})  # Other user
    discord.add("100", {"id": "52", "content": "<@501> took the **Fake** card `fak33`!", "author": {"id": "1"}})  # Not Karuta
    discord.add("100", {"id": "53", "content": "lol <@501> took the **X** card `mid44`!", "author": {"id": KARUTA_ID}})  # Not at start
    assert await bot.get_grabbed_card_code("tok1", 1, "100", "50") is None


async def test_get_grabbed_card_code_picks_grab_from_this_drop(bot, discord):
    discord.add("100", {"id": "50", "content": "<@501> is dropping 3 cards!", "author": {"id": KARUTA_ID}})
    discord.add("100", {"id": "51", "content": "<@501> took the **This** card `thi11`!", "author": {"id": KARUTA_ID}})
    discord.add("100", {"id": "60", "content": "<@502> is dropping 3 cards!", "author": {"id": KARUTA_ID}})
    discord.add("100", {"id": "61", "content": "<@501> took the **Later** card `lat22`!", "author": {"id": KARUTA_ID}})  # Grab from a later drop
    assert await bot.get_grabbed_card_code("tok1", 1, "100", "50") == "thi11"


async def test_get_grabbed_card_code_http_error(bot, discord, capsys):
    discord.respond("GET", r"limit=50", 500)
    assert await bot.get_grabbed_card_code("tok1", 1, "100", "50") is None
    assert "[Account #1] Retrieve grab message failed: Error code 500." in capsys.readouterr().out
