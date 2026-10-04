"""drop_and_grab: dropping, deciding who grabs what, special events, random chatter and extra grab purchases."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import main
from conftest import CARD_EMOJIS, settle

E1, E2, E3 = CARD_EMOJIS[:3]
CHANNEL_TOKENS = ["tok1", "tok2", "tok3"]


async def drop(bot, token = "tok1", channel = "100", channel_tokens = CHANNEL_TOKENS):
    await bot.drop_and_grab(token, bot.tokens.index(token) + 1, channel, list(channel_tokens))


def grabs(discord):
    """(token, emoji) for every card grab on the last drop, in order."""
    return [(token, emoji) for token, _, msg_id, emoji in discord.reactions() if msg_id == discord.last_drop["id"]]


@pytest.fixture
def burn(bot, monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(bot, "burn_non_pog_cards", mock)
    return mock


async def finish_background(bot):
    await asyncio.gather(*list(bot.background_tasks))


# --------------------------------------------------------------------------- #
# Dropping
# --------------------------------------------------------------------------- #

async def test_drop_command_is_sent_by_dropper(bot, discord):
    await drop(bot)
    token, channel, content = discord.sent()[0]
    assert (token, channel) == ("tok1", "100")
    assert content in [cmd + addon for cmd in bot.DROP_COMMANDS for addon in bot.RANDOM_ADDON]


async def test_every_drop_command_variant_is_recognised(bot):
    # Every combination the script may send must be a valid Karuta drop command (prefix + optional harmless suffix)
    for cmd in bot.DROP_COMMANDS:
        for addon in bot.RANDOM_ADDON:
            assert (cmd + addon).split()[0] in ("kdrop", "kd")


async def test_drop_on_cooldown_does_nothing_else(bot, discord, burn):
    discord.drop_mode = "cooldown"
    bot.BURN_NON_POG_CARDS = True
    await drop(bot)
    assert discord.reactions() == []
    assert len(discord.sent()) == 1  # Only the drop command
    assert len(discord.calls("GET", r"limit=20$")) == 1  # Only the drop lookup; CardCompanion not checked
    burn.assert_not_called()


async def test_drop_not_found_does_nothing_else(bot, discord):
    discord.drop_mode = "none"
    await drop(bot)
    assert discord.reactions() == []
    assert bot.drop_fail_count == 1


@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_failed_drop_command_counts_as_drop_failure(bot, discord, system, capsys, status):
    discord.respond("POST", "/messages$", *[status] * 4)
    await drop(bot, token = "tok2")
    assert bot.drop_fail_count == 1
    assert discord.reactions() == []
    assert not discord.calls("GET")  # Nothing else attempted
    system.shell_execute.assert_not_called()
    system.win32gui.ShowWindow.assert_not_called()
    assert "❌ [Account #2] Drop failed (1/5): Drop command could not be sent." in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# No pog cards
# --------------------------------------------------------------------------- #

async def test_no_pog_each_account_grabs_one_distinct_card(bot, discord):
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok2", E2), ("tok3", E3)]


async def test_no_pog_assignment_is_shuffled(bot, discord, rng):
    rng.reverse_shuffle = True
    await drop(bot)
    assert grabs(discord) == [("tok3", E3), ("tok2", E2), ("tok1", E1)]
    assert sorted(e for _, e in grabs(discord)) == sorted([E1, E2, E3])


@pytest.mark.parametrize("channel_tokens, expected", [
    (["tok4"], [("tok4", E1)]),
    (["tok4", "tok5"], [("tok4", E1), ("tok5", E2)]),
])
async def test_no_pog_partial_channel_grabs_one_card_per_account(bot, discord, channel_tokens, expected):
    await drop(bot, token = "tok4", channel = "101", channel_tokens = channel_tokens)
    assert grabs(discord) == expected


async def test_no_pog_only_grab_pog_cards_grabs_nothing(bot, discord, burn):
    bot.ONLY_GRAB_POG_CARDS = True
    bot.BURN_NON_POG_CARDS = True  # Documented to do nothing when ONLY_GRAB_POG_CARDS is on
    await drop(bot)
    assert grabs(discord) == []
    await finish_background(bot)
    burn.assert_not_called()


async def test_no_pog_skip_rate(bot, discord, rng, capsys):
    bot.SKIP_GRAB_NON_POG_CARD_RATE = 0.5
    rng.randoms.extend([0.1, 0.9, 0.49])
    await drop(bot)
    assert grabs(discord) == [("tok2", E2)]
    out = capsys.readouterr().out
    assert "[Account #1] Skipped grab for card [1]." in out
    assert "[Account #3] Skipped grab for card [3]." in out


async def test_no_pog_skip_rate_one_skips_everything(bot, discord, burn):
    bot.SKIP_GRAB_NON_POG_CARD_RATE = 1.0
    bot.BURN_NON_POG_CARDS = True
    await drop(bot)
    assert grabs(discord) == []
    await finish_background(bot)
    burn.assert_not_called()  # Nothing grabbed, nothing to burn


async def test_no_pog_burns_every_grabbed_card(bot, discord, burn, rng):
    bot.BURN_NON_POG_CARDS = True
    bot.SKIP_GRAB_NON_POG_CARD_RATE = 0.5
    rng.randoms.extend([0.9, 0.1, 0.9])  # tok2 skips
    await drop(bot)
    await finish_background(bot)
    burn.assert_awaited_once_with(["tok1", "tok3"], "100", discord.last_drop["id"])


async def test_no_pog_no_burn_when_disabled(bot, discord, burn):
    await drop(bot)
    await finish_background(bot)
    burn.assert_not_called()


# --------------------------------------------------------------------------- #
# Pog cards, no fighting
# --------------------------------------------------------------------------- #

async def test_pog_dropper_grabs_pog_first_and_others_grab_the_rest(bot, discord):
    discord.pog_cards = [2]
    await drop(bot)
    assert grabs(discord) == [("tok1", E2), ("tok2", E1), ("tok3", E3)]


async def test_multiple_pogs_without_extra_grabs(bot, discord):
    discord.pog_cards = [3, 1]
    await drop(bot)
    # Dropper takes the first pog card; the others take the remaining cards, pog cards first
    assert grabs(discord)[0] == ("tok1", E3)
    assert sorted(grabs(discord)[1:]) == [("tok2", E1), ("tok3", E2)]


async def test_others_prioritise_pog_cards_when_short_of_accounts(bot, discord):
    discord.pog_cards = [1, 3]
    await drop(bot, token = "tok4", channel = "101", channel_tokens = ["tok4", "tok5"])
    assert grabs(discord) == [("tok4", E1), ("tok5", E3)]  # Card 3 (pog) is preferred over card 2


async def test_single_account_channel_with_pog(bot, discord):
    discord.pog_cards = [2, 3]
    await drop(bot, token = "tok4", channel = "101", channel_tokens = ["tok4"])
    assert grabs(discord) == [("tok4", E2)]


async def test_extra_pog_grabs_dropper_reacts_to_every_pog(bot, discord):
    bot.ATTEMPT_EXTRA_POG_GRABS = True
    discord.pog_cards = [1, 3]
    await drop(bot)
    reactions = grabs(discord)
    assert reactions[:2] == [("tok1", E1), ("tok1", E3)]
    # README: the other accounts still try for the remaining pog cards after the first, then the leftover card
    assert reactions[2:] == [("tok2", E3), ("tok3", E2)]


async def test_pog_skip_rate_never_skips_pog_cards(bot, discord):
    bot.SKIP_GRAB_NON_POG_CARD_RATE = 1.0
    discord.pog_cards = [1, 3]
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok2", E3)]


async def test_pog_burns_only_non_pog_grabs(bot, discord, burn):
    bot.BURN_NON_POG_CARDS = True
    discord.pog_cards = [2]
    await drop(bot)
    await finish_background(bot)
    burn.assert_awaited_once_with(["tok2", "tok3"], "100", discord.last_drop["id"])


async def test_pog_burn_skipped_when_all_others_grab_pogs(bot, discord, burn):
    bot.BURN_NON_POG_CARDS = True
    discord.pog_cards = [1, 2]
    await drop(bot, token = "tok4", channel = "101", channel_tokens = ["tok4", "tok5"])
    await finish_background(bot)
    burn.assert_not_called()


async def test_only_pog_single_pog_only_dropper_grabs(bot, discord):
    bot.ONLY_GRAB_POG_CARDS = True
    discord.pog_cards = [3]
    await drop(bot)
    assert grabs(discord) == [("tok1", E3)]


async def test_only_pog_other_accounts_grab_remaining_pogs(bot, discord):
    bot.ONLY_GRAB_POG_CARDS = True
    discord.pog_cards = [1, 2, 3]
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok2", E2), ("tok3", E3)]


async def test_only_pog_with_extra_grabs(bot, discord):
    bot.ONLY_GRAB_POG_CARDS = True
    bot.ATTEMPT_EXTRA_POG_GRABS = True
    discord.pog_cards = [1, 3]
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok1", E3), ("tok2", E3)]


async def test_only_pog_never_burns(bot, discord, burn):
    bot.ONLY_GRAB_POG_CARDS = True
    bot.BURN_NON_POG_CARDS = True
    discord.pog_cards = [1]
    await drop(bot)
    await finish_background(bot)
    burn.assert_not_called()


# --------------------------------------------------------------------------- #
# Fighting for a pog card
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("fighters, expected", [
    (1, [("tok1", E2), ("tok2", E2)]),
    (2, [("tok1", E2), ("tok2", E2), ("tok3", E2)]),
])
async def test_fight_for_single_pog(bot, discord, rng, burn, clock, fighters, expected):
    bot.FIGHT_FOR_POG_CARD = True
    bot.BURN_NON_POG_CARDS = True
    rng.fighters = fighters
    discord.pog_cards = [2]
    await drop(bot)
    assert grabs(discord) == expected  # Dropper first, fighters on the same card, other cards left alone
    assert clock.sleeps.count(0.2) == fighters
    await finish_background(bot)
    burn.assert_not_called()


async def test_fighters_never_include_the_dropper(bot, discord, rng):
    bot.FIGHT_FOR_POG_CARD = True
    rng.fighters = 2
    rng.reverse_shuffle = True
    discord.pog_cards = [1]
    await drop(bot, token = "tok2")
    reactions = grabs(discord)
    assert reactions[0] == ("tok2", E1)
    assert sorted(reactions[1:]) == [("tok1", E1), ("tok3", E1)]


async def test_fight_in_single_account_channel(bot, discord, rng):
    bot.FIGHT_FOR_POG_CARD = True
    rng.fighters = 2
    discord.pog_cards = [3]
    await drop(bot, token = "tok4", channel = "101", channel_tokens = ["tok4"])
    assert grabs(discord) == [("tok4", E3)]


async def test_fight_takes_precedence_over_only_grab_pog(bot, discord):
    bot.FIGHT_FOR_POG_CARD = True
    bot.ONLY_GRAB_POG_CARDS = True
    discord.pog_cards = [1]
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok2", E1)]


async def test_fight_ignored_with_multiple_pogs(bot, discord):
    bot.FIGHT_FOR_POG_CARD = True
    discord.pog_cards = [1, 2]
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok2", E2), ("tok3", E3)]


# --------------------------------------------------------------------------- #
# Special event
# --------------------------------------------------------------------------- #

@pytest.fixture
def event_checker(bot):
    checker = SimpleNamespace(add_special_event_reactions = AsyncMock(), special_event_tokens_dict = {"any": "eventTok"})
    bot.server_drop_checker = checker
    bot.SPECIAL_EVENT = True
    return checker


async def test_special_event_emoji_is_grabbed(bot, discord, event_checker):
    discord.drop_extra_emojis = ["🎃"]
    await drop(bot)
    event_checker.add_special_event_reactions.assert_awaited_once()
    channel, message = event_checker.add_special_event_reactions.await_args.args
    assert channel == "100"
    assert message["id"] == discord.last_drop["id"]
    assert discord.calls("GET", r"messages\?limit=20$")


async def test_special_event_only_copies_reactions_added_by_karuta(bot, discord, capsys):
    from server_drop_checker import ServerDropChecker
    checker = ServerDropChecker.__new__(ServerDropChecker)  # Skip __init__ (token files, background checker)
    checker.main = bot
    checker.special_event_tokens_dict = {"any": "tok4"}
    bot.server_drop_checker = checker
    bot.SPECIAL_EVENT = True
    discord.drop_extra_emojis = ["🎃", "👀"]
    discord.player_emojis = {"👀"}  # A player reacted with 👀; Karuta added 🎃
    await drop(bot)
    assert [(t, e) for t, _, _, e in discord.reactions() if e not in CARD_EMOJIS] == [("tok4", "🎃")]
    assert "✅ [Special Event Account] Grabbed 🎃 in Drop Channel #1." in capsys.readouterr().out


async def test_special_event_without_event_emoji(bot, discord, event_checker):
    await drop(bot)
    event_checker.add_special_event_reactions.assert_not_called()


async def test_special_event_disabled_skips_secondary_check(bot, discord):
    bot.SPECIAL_EVENT = False
    discord.drop_extra_emojis = ["🎃"]
    await drop(bot)
    assert len(discord.calls("GET", r"limit=20$")) == 2  # Only the drop and CardCompanion lookups


@pytest.mark.parametrize("only_pog, waits", [(True, True), (False, False)])
async def test_special_event_extra_wait_only_when_no_cards_grabbed(bot, discord, event_checker, clock, only_pog, waits):
    bot.ONLY_GRAB_POG_CARDS = only_pog
    await drop(bot)
    assert (4 in clock.sleeps) is waits


async def test_special_event_secondary_lookup_failure(bot, discord, event_checker):
    discord.drop_extra_emojis = ["🎃"]
    discord.respond("GET", r"limit=20$", None, None, 403)  # Drop and CardCompanion lookups succeed, secondary drop lookup fails
    await drop(bot)
    event_checker.add_special_event_reactions.assert_not_called()


async def test_special_event_secondary_failure_does_not_count_as_drop_failure(bot, discord, event_checker):
    discord.respond("GET", r"limit=20$", None, None, 403)
    await drop(bot)
    assert bot.drop_fail_count == 0


# --------------------------------------------------------------------------- #
# Random messages after the drop
# --------------------------------------------------------------------------- #

def chatter(discord):
    return discord.sent()[1:]  # Everything after the drop command


@pytest.mark.parametrize("only_pog, chat, expected_senders", [
    (True, True, ["tok1"]),  # Only the dropper is active when only grabbing pogs
    (True, False, []),
    (False, True, ["tok1", "tok2", "tok3"]),
    (False, False, []),
])
async def test_random_messages(bot, discord, rng, only_pog, chat, expected_senders):
    bot.ONLY_GRAB_POG_CARDS = only_pog
    rng.chat = chat
    await drop(bot)
    messages = chatter(discord)
    assert [token for token, _, _ in messages] == expected_senders
    for _, channel, content in messages:
        assert channel == "100"
        assert content in bot.RANDOM_COMMANDS or content in bot.RANDOM_MESSAGES


async def test_random_messages_up_to_three_per_account(bot, discord, rng, monkeypatch):
    rng.chat = True
    monkeypatch.setattr(main.random, "randint", lambda a, b: b)
    await drop(bot)
    assert [token for token, _, _ in chatter(discord)] == ["tok1"] * 3 + ["tok2"] * 3 + ["tok3"] * 3


async def test_random_messages_are_not_retried_when_rate_limited(bot, discord, rng):
    bot.ONLY_GRAB_POG_CARDS = True
    rng.chat = True
    discord.respond("POST", "/messages$", None, 429)
    await drop(bot)
    assert len(discord.calls("POST", "/messages$")) == 2


# --------------------------------------------------------------------------- #
# Extra grab purchase
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("buy, extra, pogs, expected", [
    (True, True, [1, 2], True),
    (True, True, [1, 2, 3], True),
    (True, True, [1], False),  # No extra grab used
    (True, True, [], False),
    (True, False, [1, 2], False),  # Documented: does nothing without ATTEMPT_EXTRA_POG_GRABS
    (False, True, [1, 2], False),
])
async def test_buy_extra_grabs_conditions(bot, discord, monkeypatch, buy, extra, pogs, expected):
    bot.ATTEMPT_BUY_EXTRA_GRABS = buy
    bot.ATTEMPT_EXTRA_POG_GRABS = extra
    discord.pog_cards = pogs
    buy_mock = AsyncMock()
    monkeypatch.setattr(bot, "attempt_buy_extra_grabs", buy_mock)
    await drop(bot)
    if expected:
        buy_mock.assert_awaited_once_with("tok1", 1, "100", len(pogs))
    else:
        buy_mock.assert_not_called()


# --------------------------------------------------------------------------- #
# Pausing
# --------------------------------------------------------------------------- #

async def test_pause_holds_drop_after_grabs(bot, discord, rng):
    rng.chat = True
    bot.pause_event.clear()
    task = asyncio.create_task(drop(bot))
    await settle()
    assert len(grabs(discord)) == 3  # Grabs are time-critical and happen even while paused
    assert chatter(discord) == []
    assert not task.done()
    bot.pause_event.set()
    await task
    assert len(chatter(discord)) == 3


# --------------------------------------------------------------------------- #
# Unknown or out-of-range pog cards
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("pogs", [[4], [2, 5]])
async def test_out_of_range_pog_cards_are_unknown(bot, discord, burn, pogs):
    """Script drops have 3 cards, so a pog card above 3 means the CardCompanion message is about another drop."""
    bot.BURN_NON_POG_CARDS = True
    discord.pog_cards = pogs
    await drop(bot)
    assert grabs(discord) == [("tok1", E1), ("tok2", E2), ("tok3", E3)]  # Grabbed as if there were no pog cards
    await finish_background(bot)
    burn.assert_not_called()


@pytest.mark.parametrize("unknown", ["lookup fails", "no reply"])
async def test_unknown_pog_cards_grab_everything_but_never_burn(bot, discord, burn, unknown):
    bot.BURN_NON_POG_CARDS = True
    discord.pog_cards = [1]
    if unknown == "lookup fails":
        discord.respond("GET", r"limit=20$", None, 500)  # Drop lookup succeeds, CardCompanion lookup fails
    else:
        discord.card_companion = False
    await drop(bot)
    assert len(grabs(discord)) == 3
    await finish_background(bot)
    burn.assert_not_called()


async def test_unknown_pog_cards_grab_nothing_when_only_grabbing_pogs(bot, discord):
    bot.ONLY_GRAB_POG_CARDS = True
    discord.card_companion = False
    await drop(bot)
    assert grabs(discord) == []


# --------------------------------------------------------------------------- #
# Invariants across every combination of grab settings
# --------------------------------------------------------------------------- #

POG_SETS = [[], [1], [2], [3], [1, 2], [3, 1], [2, 3], [1, 2, 3]]
FLAG_SETS = [
    dict(ONLY_GRAB_POG_CARDS = only, ATTEMPT_EXTRA_POG_GRABS = extra, FIGHT_FOR_POG_CARD = fight,
         BURN_NON_POG_CARDS = burn_flag, ATTEMPT_BUY_EXTRA_GRABS = buy)
    for only in (False, True) for extra in (False, True) for fight in (False, True)
    for burn_flag in (False, True) for buy in (False, True)
]


@pytest.mark.parametrize("pogs", POG_SETS, ids = str)
@pytest.mark.parametrize("flags", FLAG_SETS, ids = lambda f: ",".join(k for k, v in f.items() if v) or "defaults")
@pytest.mark.parametrize("fighters", [1, 2])
async def test_grab_invariants(bot, discord, rng, burn, monkeypatch, flags, pogs, fighters):
    for name, value in flags.items():
        setattr(bot, name, value)
    rng.fighters = fighters
    rng.chat = True
    buy_mock = AsyncMock()
    monkeypatch.setattr(bot, "attempt_buy_extra_grabs", buy_mock)
    discord.pog_cards = pogs
    await drop(bot, token = "tok2")
    await finish_background(bot)

    drop_id = discord.last_drop["id"]
    pog_emojis = [CARD_EMOJIS[n - 1] for n in pogs]
    fight = flags["FIGHT_FOR_POG_CARD"] and len(pogs) == 1

    # Only channel accounts react, only with card emojis, only on this drop
    for token, channel, msg_id, emoji in discord.reactions():
        assert token in CHANNEL_TOKENS and channel == "100" and msg_id == drop_id and emoji in (E1, E2, E3)
    # Messages stay in the drop channel; the first is the drop command
    assert all(channel == "100" for _, channel, _ in discord.sent())
    assert discord.sent()[0][2].split()[0] in ("kdrop", "kd")

    reactions = grabs(discord)
    dropper = [e for t, e in reactions if t == "tok2"]
    others = [(t, e) for t, e in reactions if t != "tok2"]
    assert len({t for t, _ in others}) == len(others)  # Each other account grabs at most once

    if pogs:
        assert reactions[0] == ("tok2", pog_emojis[0])  # Dropper grabs the first pog card first
        assert set(dropper) <= set(pog_emojis)  # Dropper never spends a grab on a non-pog card
        if not flags["ATTEMPT_EXTRA_POG_GRABS"] or fight:
            assert dropper == [pog_emojis[0]]
        else:
            assert dropper == pog_emojis
        # Every pog card is attempted when there are enough accounts
        assert set(pog_emojis) <= {e for _, e in reactions}
    else:
        assert len(dropper) <= 1

    if fight:
        assert {e for _, e in reactions} == {pog_emojis[0]}
        assert len(others) == fighters
    if flags["ONLY_GRAB_POG_CARDS"] and not fight:
        assert {e for _, e in reactions} <= set(pog_emojis)
    if not flags["ONLY_GRAB_POG_CARDS"] and not fight:
        assert {e for _, e in reactions} == {E1, E2, E3}  # Three accounts, no skip rate: every card is taken

    # Burning: only enabled mode, never pog cards, never in fight/only-pog modes
    if burn.await_count:
        assert flags["BURN_NON_POG_CARDS"] and not flags["ONLY_GRAB_POG_CARDS"] and not fight
        tokens_to_burn, channel, msg_id = burn.await_args.args
        assert (channel, msg_id) == ("100", drop_id)
        for token in tokens_to_burn:
            assert {e for t, e in reactions if t == token} & set(pog_emojis) == set()
    elif flags["BURN_NON_POG_CARDS"] and not flags["ONLY_GRAB_POG_CARDS"] and not fight:
        assert all(e in pog_emojis for _, e in others) and (pogs or not others)

    # Extra grabs are only bought after the dropper used them
    assert buy_mock.await_count == int(flags["ATTEMPT_BUY_EXTRA_GRABS"] and flags["ATTEMPT_EXTRA_POG_GRABS"] and len(pogs) > 1)
