"""Message commands that confirm Karuta prompts (command_checker.py)."""
import asyncio

import pytest

from command_checker import CommandChecker
from conftest import USER_IDS, karuta_reply, settle, user_msg

COMMAND_CHANNEL = "300"


@pytest.fixture
def checker(bot):
    return CommandChecker(bot, bot.tokens, bot.COMMAND_USER_IDS, COMMAND_CHANNEL, bot.KARUTA_PREFIX, bot.KARUTA_BOT_ID, bot.RATE_LIMIT)


def stale_transfer(discord):
    """An unconfirmed Card Transfer prompt for an earlier command from Account #1."""
    earlier_command = discord.add(COMMAND_CHANNEL, user_msg("10", USER_IDS["tok1"], "kgive @x old11"))
    discord.add(COMMAND_CHANNEL, karuta_reply("11", earlier_command, title = "Card Transfer", buttons = [("✅", "stale_confirm")]))


def confirmed(discord):
    return [r.json["data"]["custom_id"] for r in discord.interactions()]


async def run_command(checker, discord, content):
    """Post a message command and let the checker loop handle it once."""
    discord.add(COMMAND_CHANNEL, user_msg(discord.new_id(), "900", content))
    loop_task = asyncio.create_task(checker.run_command_checker())
    await settle(300)
    loop_task.cancel()
    await asyncio.gather(loop_task, return_exceptions = True)


async def test_card_transfer_confirms_prompt_for_sent_command(checker, discord):
    stale_transfer(discord)
    await run_command(checker, discord, "cmd 1 kgive @x new22")
    assert confirmed(discord) == ["give_confirm"]


async def test_card_transfer_never_confirms_stale_prompt(checker, discord):
    stale_transfer(discord)
    await run_command(checker, discord, "cmd 1 kgems")  # Matches the "kg" prefix, but Karuta sends no Card Transfer prompt
    assert confirmed(discord) == []


async def test_card_transfer_skipped_when_command_not_sent(checker, discord):
    stale_transfer(discord)
    discord.respond("POST", r"/channels/300/messages$", 403)
    await run_command(checker, discord, "cmd 1 kgive @x new22")
    assert confirmed(discord) == []


async def test_multiburn_never_confirms_stale_prompt(checker, discord):
    earlier_command = discord.add(COMMAND_CHANNEL, user_msg("10", USER_IDS["tok1"], "kmb"))
    discord.add(COMMAND_CHANNEL, karuta_reply("11", earlier_command, title = "Burn Cards", buttons = [("☑️", "stale_check")]))
    await run_command(checker, discord, "cmd 1 kmb")
    assert confirmed(discord) == []
