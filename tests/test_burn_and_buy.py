"""burn_non_pog_cards and attempt_buy_extra_grabs: follow-up actions that confirm Karuta button prompts."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from conftest import KARUTA_ID, USER_IDS, karuta_drop, karuta_reply, settle, user_msg


def grab_message(msg_id, token, code):
    return {"id": msg_id, "content": f"<@{USER_IDS[token]}> took the **Card** card `{code}`!", "author": {"id": KARUTA_ID}}


@pytest.fixture
def grabbed(discord):
    """Drop 1001 in channel 100 where tok2 grabbed card `aaa11` and tok3 grabbed `bbb22`."""
    discord.add("100", karuta_drop("1001", USER_IDS["tok1"]))
    discord.add("100", grab_message("1002", "tok2", "aaa11"))
    discord.add("100", grab_message("1003", "tok3", "bbb22"))
    discord.next_id = 2000
    return "1001"


def confirmed_buttons(discord):
    return [(r.token, r.json["data"]["custom_id"], r.json["message_id"]) for r in discord.interactions()]


# --------------------------------------------------------------------------- #
# burn_non_pog_cards
# --------------------------------------------------------------------------- #

async def test_burns_each_grabbed_card(bot, discord, grabbed, capsys, clock):
    await bot.burn_non_pog_cards(["tok2", "tok3"], "100", grabbed)
    sent = discord.sent()
    assert [(t, c) for t, _, c in sent] == [("tok2", "kburn aaa11"), ("tok3", "kburn bbb22")]
    buttons = confirmed_buttons(discord)
    assert [(t, cid) for t, cid, _ in buttons] == [("tok2", "burn_confirm"), ("tok3", "burn_confirm")]
    # Each confirmation targets the burn prompt Karuta sent in reply to that account's burn command
    burn_prompts = [m["id"] for m in discord.history["100"] if m.get("embeds") and m["embeds"][0]["title"] == "Burn Card"]
    assert sorted(mid for _, _, mid in buttons) == sorted(burn_prompts)
    out = capsys.readouterr().out
    assert out.count("Card burned successfully.") == 2
    assert clock.sleeps.count(5) == 4  # 5-90s before each burn, 5-8s waiting for each prompt


async def test_burn_command_variants(bot):
    assert bot.BURN_COMMANDS == ["kburn", "kb"]


async def test_skips_burn_without_card_code(bot, discord, grabbed, capsys):
    await bot.burn_non_pog_cards(["tok1"], "100", grabbed)  # tok1 never grabbed
    assert discord.sent() == []
    assert discord.interactions() == []
    assert "[Account #1] Grab not confirmed; skipping burn." in capsys.readouterr().out


async def test_skips_only_accounts_without_code(bot, discord, grabbed):
    await bot.burn_non_pog_cards(["tok1", "tok3"], "100", grabbed)
    assert [(t, c) for t, _, c in discord.sent()] == [("tok3", "kburn bbb22")]


async def test_burn_prompt_not_found(bot, discord, grabbed, capsys):
    discord.reply_to_burn = False
    await bot.burn_non_pog_cards(["tok2"], "100", grabbed)
    assert discord.interactions() == []
    assert "Retrieve message failed: Message 'Burn Card' not found" in capsys.readouterr().out


async def test_burn_button_missing(bot, discord, grabbed, capsys, monkeypatch):
    monkeypatch.setattr(bot, "get_payload", AsyncMock(return_value = None))
    await bot.burn_non_pog_cards(["tok2"], "100", grabbed)
    assert discord.interactions() == []
    assert "[Account #2] Card burn failed: 🔥 button not found." in capsys.readouterr().out


async def test_burn_interaction_failure(bot, discord, grabbed, capsys):
    discord.respond("POST", "/interactions$", 400)
    await bot.burn_non_pog_cards(["tok2"], "100", grabbed)
    assert "[Account #2] Card burn failed: Error code 400." in capsys.readouterr().out


async def test_burn_waits_while_paused(bot, discord, grabbed):
    bot.pause_event.clear()
    task = asyncio.create_task(bot.burn_non_pog_cards(["tok2"], "100", grabbed))
    await settle()
    assert discord.sent() == []
    bot.pause_event.set()
    await task
    assert len(discord.interactions()) == 1


async def test_end_to_end_drop_then_burn(bot, discord):
    bot.BURN_NON_POG_CARDS = True
    discord.pog_cards = [2]
    await bot.drop_and_grab("tok1", 1, "100", ["tok1", "tok2", "tok3"])
    await asyncio.gather(*list(bot.background_tasks))
    drop_id = discord.last_drop["id"]
    burns = [(t, c) for t, _, c in discord.sent() if c.startswith("kburn")]
    assert burns == [("tok2", f"kburn c{drop_id}1"), ("tok3", f"kburn c{drop_id}3")]  # The pog card (2) is kept
    assert len(discord.interactions()) == 2
    assert bot.background_tasks == set()


async def test_burn_not_confirmed_when_burn_command_fails(bot, discord, grabbed):
    manual = discord.add("100", user_msg("1500", USER_IDS["tok2"], "kburn pog99"))  # User inspected a pog card earlier
    discord.add("100", karuta_reply("1501", manual, title = "Burn Card", buttons = [("🔥", "burn_pog99")]))
    discord.respond("POST", "/messages$", 500)
    await bot.burn_non_pog_cards(["tok2"], "100", grabbed)
    assert discord.interactions() == []


async def test_burn_does_not_confirm_stale_prompt(bot, discord, grabbed):
    manual = discord.add("100", user_msg("1500", USER_IDS["tok2"], "kburn pog99"))
    discord.add("100", karuta_reply("1501", manual, title = "Burn Card", buttons = [("🔥", "burn_pog99")]))
    discord.reply_to_burn = False  # Karuta has not answered the new burn command yet
    await bot.burn_non_pog_cards(["tok2"], "100", grabbed)
    assert discord.interactions() == []


# --------------------------------------------------------------------------- #
# attempt_buy_extra_grabs
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("num_pog_cards, purchased", [(2, 1), (3, 2)])
async def test_buys_one_extra_grab_per_extra_pog(bot, discord, capsys, num_pog_cards, purchased):
    await bot.attempt_buy_extra_grabs("tok1", 1, "100", num_pog_cards)
    assert discord.sent()[0] == ("tok1", "100", f"kbuy extra grab {purchased}")
    assert [(t, cid) for t, cid, _ in confirmed_buttons(discord)] == [("tok1", "buy_confirm")]
    assert f"✅ [Account #1] Purchased {purchased} extra grabs successfully." in capsys.readouterr().out


async def test_purchase_prompt_not_found(bot, discord):
    discord.reply_to_purchase = False
    await bot.attempt_buy_extra_grabs("tok1", 1, "100", 2)
    assert discord.interactions() == []


async def test_purchase_button_missing(bot, discord, capsys, monkeypatch):
    monkeypatch.setattr(bot, "get_payload", AsyncMock(return_value = None))
    await bot.attempt_buy_extra_grabs("tok1", 1, "100", 2)
    assert discord.interactions() == []
    assert "Extra grab purchase failed: ✅ button not found." in capsys.readouterr().out


async def test_purchase_interaction_failure(bot, discord, capsys):
    discord.respond("POST", "/interactions$", 500)
    await bot.attempt_buy_extra_grabs("tok1", 1, "100", 2)
    assert "[Account #1] Extra grab purchase failed: Error code 500." in capsys.readouterr().out


async def test_purchase_waits_while_paused(bot, discord):
    bot.pause_event.clear()
    task = asyncio.create_task(bot.attempt_buy_extra_grabs("tok1", 1, "100", 2))
    await settle()
    assert len(discord.sent()) == 1
    assert discord.interactions() == []
    bot.pause_event.set()
    await task
    assert len(discord.interactions()) == 1


async def test_purchase_not_confirmed_when_command_fails(bot, discord):
    manual = discord.add("100", user_msg("1500", USER_IDS["tok1"], "kbuy expensive frame"))
    discord.add("100", karuta_reply("1501", manual, title = "Item Purchase", buttons = [("✅", "buy_frame")]))
    discord.respond("POST", "/messages$", 500)
    await bot.attempt_buy_extra_grabs("tok1", 1, "100", 2)
    assert discord.interactions() == []
