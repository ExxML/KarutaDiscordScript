"""Server drops and other users' drops with more than 3 cards (Server Drop Grabber and Special Event Grabber)."""
import asyncio

import pytest

from conftest import CARD_EMOJIS, USER_IDS, card_companion_msg, karuta_drop, server_drop, settle
from server_drop_checker import ServerDropChecker

SERVER_CHANNEL = "200"


@pytest.fixture
def checker(bot, discord):
    """A ServerDropChecker without __init__ (which reads the token files and starts the loop)."""
    instance = ServerDropChecker.__new__(ServerDropChecker)
    instance.main = bot
    instance.server_token = "srvTok"
    instance.special_event_tokens_dict = {"any": "eventTok"}
    discord.users.update({"srvTok": "598", "eventTok": "599"})
    bot.server_drop_checker = instance
    return instance


def reactions_on(discord, msg_id):
    return [(token, emoji) for token, _, mid, emoji in discord.reactions() if mid == msg_id]


async def run_checker_once(bot, checker):
    """Run the checker loop until it goes idle, then stop it and any grabs it started."""
    loop_task = asyncio.create_task(checker.run_server_drop_checker())
    await settle(300)
    loop_task.cancel()
    for task in [loop_task, *bot.background_tasks]:
        task.cancel()
    await asyncio.gather(loop_task, *bot.background_tasks, return_exceptions = True)


# --------------------------------------------------------------------------- #
# Server Drop Grabber
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("num_cards", range(4, 10))
async def test_server_drop_pog_in_last_position_is_grabbed(bot, discord, checker, capsys, num_cards):
    discord.add(SERVER_CHANNEL, server_drop("1001", num_cards))
    discord.add(SERVER_CHANNEL, card_companion_msg("1002", [num_cards], reply_to = "1001"))
    await checker.grab_server_drop(SERVER_CHANNEL, "1001")
    assert reactions_on(discord, "1001") == [("srvTok", CARD_EMOJIS[num_cards - 1])]
    assert f"✅ [Server Account] Grabbed card [{num_cards}] in Server Activity Drop Channel #1." in capsys.readouterr().out


async def test_server_drop_multiple_pogs_beyond_third_card(bot, discord, checker):
    discord.add(SERVER_CHANNEL, server_drop("1001", 7))
    discord.add(SERVER_CHANNEL, card_companion_msg("1002", [6, 2], reply_to = "1001"))
    await checker.grab_server_drop(SERVER_CHANNEL, "1001")
    # Server account takes the first pog card; a script account takes the rest
    assert reactions_on(discord, "1001") == [("srvTok", CARD_EMOJIS[5]), ("tok1", CARD_EMOJIS[1])]


async def test_server_drop_without_pogs_is_not_grabbed(bot, discord, checker):
    discord.add(SERVER_CHANNEL, server_drop("1001", 4))
    discord.add(SERVER_CHANNEL, card_companion_msg("1002", [], reply_to = "1001"))
    await checker.grab_server_drop(SERVER_CHANNEL, "1001")
    assert reactions_on(discord, "1001") == []


async def test_checker_loop_grabs_pog_on_large_server_drop(bot, discord, checker):
    bot.GRAB_SERVER_POG_CARDS = True
    discord.add(SERVER_CHANNEL, server_drop("1001", 5))
    discord.add(SERVER_CHANNEL, card_companion_msg("1002", [5], reply_to = "1001"))
    await run_checker_once(bot, checker)
    assert reactions_on(discord, "1001") == [("srvTok", CARD_EMOJIS[4])]


async def test_checker_loop_ignores_other_users_drops_for_pog_grabs(bot, discord, checker):
    """README: only server activity drops are tracked by the Server Drop Grabber."""
    bot.GRAB_SERVER_POG_CARDS = True
    discord.add(SERVER_CHANNEL, karuta_drop("1001", "777", num_cards = 4))
    discord.add(SERVER_CHANNEL, card_companion_msg("1002", [4], reply_to = "1001"))
    await run_checker_once(bot, checker)
    assert reactions_on(discord, "1001") == []


# --------------------------------------------------------------------------- #
# Special Event Grabber
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("drop", [
    karuta_drop("1001", "777", num_cards = 4, extra_emojis = ["🎃"]),  # Another user's 4-card drop
    server_drop("1001", num_cards = 9, extra_emojis = ["🎃"]),  # 9-card server drop
], ids = ["user-4-cards", "server-9-cards"])
async def test_special_event_on_large_drops_grabs_only_event_emoji(bot, discord, checker, drop):
    bot.SPECIAL_EVENT = True
    discord.add(SERVER_CHANNEL, drop)
    await run_checker_once(bot, checker)
    assert reactions_on(discord, "1001") == [("eventTok", "🎃")]  # Never a card emoji such as 4️⃣ or 9️⃣


@pytest.mark.parametrize("num_cards", [4, 9])
async def test_special_event_ignores_large_drops_without_event_emoji(bot, discord, checker, num_cards):
    bot.SPECIAL_EVENT = True
    discord.add(SERVER_CHANNEL, karuta_drop("1001", "777", num_cards = num_cards))
    await run_checker_once(bot, checker)
    assert reactions_on(discord, "1001") == []


# --------------------------------------------------------------------------- #
# CardCompanion lookup and logging
# --------------------------------------------------------------------------- #

async def test_card_companion_lookup_reports_pogs_up_to_nine(bot, discord):
    discord.add(SERVER_CHANNEL, server_drop("1001", 9))
    discord.add(SERVER_CHANNEL, card_companion_msg("1002", [9, 4, 1], reply_to = "1001"))
    assert await bot.get_card_companion_pog_cards("srvTok", 0, SERVER_CHANNEL, "1001") == [9, 4, 1]


async def test_card_companion_lookup_stops_at_following_large_drop(bot, discord):
    discord.add(SERVER_CHANNEL, server_drop("1001", 3))
    discord.add(SERVER_CHANNEL, karuta_drop("1002", USER_IDS["tok2"], num_cards = 4))
    discord.add(SERVER_CHANNEL, card_companion_msg("1003", [4]))  # Belongs to the 4-card drop
    assert not await bot.get_card_companion_pog_cards("srvTok", 0, SERVER_CHANNEL, "1001")


@pytest.mark.parametrize("card", range(4, 10))
async def test_grabs_of_cards_beyond_third_are_logged(bot, discord, capsys, card):
    await bot.add_reaction("tok1", 1, SERVER_CHANNEL, "1001", CARD_EMOJIS[card - 1], 0)
    assert f"✅ [Account #1] Grabbed card [{card}] in Server Activity Drop Channel #1." in capsys.readouterr().out
