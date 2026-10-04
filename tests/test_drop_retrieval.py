"""get_drop_message (finding the account's own drop) and get_card_companion_pog_cards (reading CardCompanion's verdict)."""
import pytest

from conftest import (CARD_COMPANION_ID, USER_IDS, FakeResponse, card_companion_msg, karuta_drop,
                      karuta_reply, server_drop, user_msg)

UID = USER_IDS["tok1"]


def command(discord, channel = "100", msg_id = "1000", uid = UID):
    return discord.add(channel, user_msg(msg_id, uid, "kd"))


# --------------------------------------------------------------------------- #
# get_drop_message
# --------------------------------------------------------------------------- #

async def test_finds_drop_message(bot, discord, capsys):
    command(discord)
    discord.add("100", karuta_drop("1001", UID))
    msg = await bot.get_drop_message("tok1", 1, "100", "1000", secondary_special_event_check = False)
    assert msg["id"] == "1001"
    assert "✅ [Account #1] Retrieved drop message." in capsys.readouterr().out
    assert discord.calls("GET", r"messages\?limit=20$")
    assert bot.drop_fail_count == 0


async def test_finds_drop_message_in_busy_channel(bot, discord, capsys):
    command(discord)
    discord.add("100", karuta_drop("1001", UID))
    for i in range(10):  # Grab/chat messages sent after the drop
        discord.add("100", user_msg(str(1002 + i), "999", "nice"))
    msg = await bot.get_drop_message("tok1", 1, "100", "1000", secondary_special_event_check = True)
    assert msg["id"] == "1001"
    assert discord.calls("GET", r"messages\?limit=20$")
    assert "Retrieved drop message (watching special event)." in capsys.readouterr().out


async def test_polls_until_all_three_reactions_are_added(bot, discord, clock):
    command(discord)
    discord.add("100", karuta_drop("1001", UID))  # Third reaction arrives by the third poll
    partial = [karuta_drop("1001", UID, reactions = 2), user_msg("1000", UID, "kd")]
    discord.respond("GET", r"limit=20$", FakeResponse(200, partial), FakeResponse(200, partial))
    msg = await bot.get_drop_message("tok1", 1, "100", "1000", False)
    assert msg["id"] == "1001"
    assert len(discord.calls("GET", r"limit=20$")) == 3
    assert clock.sleeps == [0.5, 0.5]  # uniform(0.5, 1) between polls


@pytest.mark.parametrize("drop", [
    karuta_drop("1001", USER_IDS["tok2"]),  # Someone else's drop
    karuta_drop("1001", UID, expired = True),  # Expired
    {**karuta_drop("1001", UID), "author": {"id": "1"}},  # Not Karuta
    karuta_drop("1001", UID, reactions = 0),
])
async def test_ignores_non_matching_drops_until_timeout(bot, discord, clock, capsys, drop):
    command(discord)
    discord.add("100", drop)
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 1
    assert clock.now >= 30
    assert "Retrieve drop message failed (1/5): Timed out (30s)." in capsys.readouterr().out


async def test_keeps_polling_when_command_is_outside_window(bot, discord):
    """Busy channel: the drop command scrolled out of the 20-message window, so nothing marks where to stop."""
    command(discord)
    for i in range(20):
        discord.add("100", user_msg(str(1001 + i), "999", "spam"))
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 1


async def test_ignores_stale_drop_sent_before_command(bot, discord):
    discord.add("100", karuta_drop("990", UID))  # An earlier drop by the same account
    command(discord)
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 1


async def test_cooldown_message_returns_none_without_counting_failure(bot, discord, capsys):
    cmd = command(discord)
    discord.add("100", karuta_reply("1001", cmd, f"<@{UID}>, you must wait `5 minutes` before dropping more cards."))
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 0
    assert len(discord.calls("GET", r"limit=20$")) == 1
    assert "Retrieve drop message failed: Drop is on cooldown." in capsys.readouterr().out


async def test_stale_cooldown_message_is_ignored(bot, discord):
    discord.add("100", karuta_reply("990", None, f"<@{UID}>, you must wait `5 minutes` before dropping more cards."))
    command(discord)
    discord.add("100", karuta_drop("1001", UID))
    assert (await bot.get_drop_message("tok1", 1, "100", "1000", False))["id"] == "1001"


async def test_other_users_cooldown_is_ignored(bot, discord):
    command(discord)
    discord.add("100", karuta_reply("1001", None, f"<@{USER_IDS['tok2']}>, you must wait `5 minutes` before dropping more cards."))
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 1  # Timed out instead


@pytest.mark.parametrize("status, text", [(401, "Invalid token."), (403, "Token banned or insufficient permissions.")])
async def test_auth_errors_fail_immediately(bot, discord, capsys, status, text):
    command(discord)
    discord.respond("GET", r"limit=20$", status)
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 1
    assert len(discord.calls("GET", r"limit=20$")) == 1
    assert f"Retrieve drop message failed (1/5): {text}" in capsys.readouterr().out


@pytest.mark.parametrize("status, text", [(401, "Invalid token."), (403, "Token banned or insufficient permissions."), (None, "Timed out (30s).")])
async def test_secondary_check_failures_do_not_count(bot, discord, capsys, status, text):
    """The secondary (special event) check runs after the drop already succeeded."""
    command(discord)
    if status:
        discord.respond("GET", r"limit=20$", status)
    assert await bot.get_drop_message("tok1", 1, "100", "1000", secondary_special_event_check = True) is None
    assert bot.drop_fail_count == 0
    assert f"❌ [Account #1] Retrieve drop message failed: {text}" in capsys.readouterr().out


@pytest.mark.parametrize("status", [429, 500, 502])
async def test_transient_errors_keep_polling(bot, discord, status):
    command(discord)
    discord.add("100", karuta_drop("1001", UID))
    discord.respond("GET", r"limit=20$", status, status)
    assert (await bot.get_drop_message("tok1", 1, "100", "1000", False))["id"] == "1001"
    assert bot.drop_fail_count == 0


async def test_failure_message_omits_counter_when_limit_disabled(bot, discord, capsys):
    bot.DROP_FAIL_LIMIT = -1
    discord.respond("GET", r"limit=20$", 401)
    await bot.get_drop_message("tok1", 1, "100", "1000", False)
    out = capsys.readouterr().out
    assert "Retrieve drop message failed: Invalid token." in out
    assert bot.drop_fail_count == 1


async def test_tolerates_messages_without_optional_fields(bot, discord):
    command(discord)
    discord.add("100", {"id": "1001"})  # No author/content/reactions
    discord.add("100", karuta_drop("1002", UID))
    assert (await bot.get_drop_message("tok1", 1, "100", "1000", False))["id"] == "1002"


async def test_script_drops_must_have_three_cards(bot, discord):
    """README: script accounts must only drop 3 cards."""
    command(discord)
    discord.add("100", karuta_drop("1001", UID, num_cards = 4))
    assert await bot.get_drop_message("tok1", 1, "100", "1000", False) is None
    assert bot.drop_fail_count == 1


async def test_user_lookup_failure_does_not_fail_the_drop(bot, discord):
    command(discord)
    discord.add("100", karuta_drop("1001", UID))
    discord.respond("GET", "/users/@me", 429)
    assert (await bot.get_drop_message("tok1", 1, "100", "1000", False))["id"] == "1001"
    assert len(discord.calls("GET", "/users/@me")) == 2  # Retried on the next poll
    assert bot.drop_fail_count == 0


async def test_user_id_is_cached(bot, discord):
    for _ in range(3):
        assert await bot.get_user_id("tok1", "100") == UID
    assert len(discord.calls("GET", "/users/@me")) == 1


# --------------------------------------------------------------------------- #
# get_card_companion_pog_cards
# --------------------------------------------------------------------------- #

def drop_with(discord, *after, channel = "100"):
    discord.add(channel, karuta_drop("1001", UID))
    for msg in after:
        discord.add(channel, msg)


@pytest.mark.parametrize("cards", [[1], [2], [3], [1, 3], [1, 2, 3]])
async def test_identifies_pog_cards(bot, discord, capsys, cards):
    drop_with(discord, card_companion_msg("1002", cards))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") == cards
    assert f"✅ [Account #1] Identified CardCompanion pog card(s): {cards}." in capsys.readouterr().out
    assert discord.calls("GET", r"messages\?limit=20$")


async def test_server_account_label(bot, discord, capsys):
    drop_with(discord, card_companion_msg("1002", [7]), channel = "200")
    assert await bot.get_card_companion_pog_cards("srvTok", 0, "200", "1001") == [7]  # Server drops can have up to 9 cards
    assert "✅ [Server Account] Identified CardCompanion pog card(s): [7]." in capsys.readouterr().out


async def test_no_pog_cards(bot, discord, capsys):
    drop_with(discord, card_companion_msg("1002", []))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") == []
    assert capsys.readouterr().out == ""


async def test_no_card_companion_message_is_unknown(bot, discord, capsys):
    """CardCompanion replies to every drop, so a missing reply means the pog cards are unknown."""
    drop_with(discord, user_msg("1002", "999", "gg"))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") is None
    assert "ℹ️ [Account #1] CardCompanion message not found." in capsys.readouterr().out


async def test_ignores_card_companion_message_before_drop(bot, discord):
    discord.add("100", card_companion_msg("999", [2]))
    drop_with(discord)
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") is None


async def test_ignores_card_companion_reply_to_another_drop(bot, discord):
    drop_with(discord, card_companion_msg("1002", [3], reply_to = "990"), card_companion_msg("1003", [1], reply_to = "1001"))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") == [1]


@pytest.mark.parametrize("next_drop", [
    karuta_drop("1002", USER_IDS["tok2"], num_cards = 4),
    server_drop("1002"),
])
async def test_stops_at_next_drop(bot, discord, next_drop):
    drop_with(discord, next_drop, card_companion_msg("1003", [1]))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") is None


async def test_ignores_non_card_companion_authors(bot, discord):
    impostor = card_companion_msg("1002", [1])
    impostor["author"] = {"id": "999"}
    drop_with(discord, impostor)
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") is None


async def test_skips_card_companion_messages_without_pog_emoji(bot, discord):
    drop_with(discord, {"id": "1002", "content": "Drop analysed: nothing special", "author": {"id": CARD_COMPANION_ID}},
              card_companion_msg("1003", [3]))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") == [3]


async def test_returns_first_card_companion_pog_message(bot, discord):
    drop_with(discord, card_companion_msg("1002", [2]), card_companion_msg("1003", [3]))
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") == [2]


async def test_unparseable_pog_message(bot, discord, capsys):
    drop_with(discord, {"id": "1002", "content": "pog :no_1: card", "author": {"id": CARD_COMPANION_ID}})
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") is None
    assert "Unable to parse pog card numbers from CardCompanion message." in capsys.readouterr().out


async def test_ignores_unknown_no_emojis(bot, discord):
    drop_with(discord, {"id": "1002", "content": "<:no_10:1> <:no_2:2>", "author": {"id": CARD_COMPANION_ID}})
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") == [2]


@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_http_error_is_unknown(bot, discord, capsys, status):
    discord.respond("GET", r"limit=20$", status)
    assert await bot.get_card_companion_pog_cards("tok1", 1, "100", "1001") is None
    assert f"Retrieve CardCompanion message failed: Error code {status}." in capsys.readouterr().out
