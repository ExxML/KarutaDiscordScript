"""run_instance (per-channel drop loop), drop fail limit handling, async_input_handler and reset_drop_fail_count."""
import asyncio
import subprocess
import sys
import threading
from unittest.mock import AsyncMock

import aiohttp
import pytest

import main
from conftest import REAL_SLEEP, settle

CHANNEL_TOKENS = ["tok1", "tok2", "tok3"]


@pytest.fixture
def dropper(bot, monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(bot, "drop_and_grab", mock)
    return mock


def per_drop_delay(num_accounts):
    """Delay after each drop with uniform() returning its lower bound: 30 min / accounts + 0.5 min."""
    return 30 * 60 / num_accounts + 0.5 * 60


async def run(bot, time_limit, channel_tokens = CHANNEL_TOKENS, start_delay = 0, channel_num = 1, channel_id = "100"):
    await bot.run_instance(channel_num, channel_id, start_delay, list(channel_tokens), time_limit)


# --------------------------------------------------------------------------- #
# Scheduling
# --------------------------------------------------------------------------- #

async def test_time_limit_zero_stops_before_any_drop(bot, discord, dropper, capsys):
    await run(bot, time_limit = 0)
    dropper.assert_not_called()
    [(token, channel, content)] = discord.sent()
    assert (token, channel) == ("tok1", "100")
    assert content in bot.TIME_LIMIT_EXCEEDED_MESSAGES
    assert "Channel #1 has reached the time limit of 0.0 hours" in capsys.readouterr().out


async def test_accounts_take_turns_until_time_limit(bot, discord, dropper, clock):
    delay = per_drop_delay(3)  # 630s
    await run(bot, time_limit = delay * 4 - 1)  # Room for exactly four drops
    assert [c.args for c in dropper.await_args_list] == [
        ("tok1", 1, "100", CHANNEL_TOKENS),
        ("tok2", 2, "100", CHANNEL_TOKENS),
        ("tok3", 3, "100", CHANNEL_TOKENS),
        ("tok1", 1, "100", CHANNEL_TOKENS),
    ]
    assert discord.sent()[0][0] == "tok2"  # The account whose turn it is announces the stop


async def test_channel_tokens_passed_as_copy(bot, dropper):
    tokens = list(CHANNEL_TOKENS)
    await bot.run_instance(1, "100", 0, tokens, 1)
    assert dropper.await_args.args[3] == tokens
    assert dropper.await_args.args[3] is not tokens


@pytest.mark.parametrize("num_accounts", [1, 2, 3])
async def test_each_account_drops_at_most_every_30_minutes(bot, dropper, clock, num_accounts):
    """Karuta's drop cooldown is 30 minutes; one full rotation must never be shorter."""
    drop_times = []
    dropper.side_effect = lambda token, *a: drop_times.append((token, clock.now))
    tokens = CHANNEL_TOKENS[:num_accounts]
    await run(bot, time_limit = 3 * 60 * 60, channel_tokens = tokens)
    for token in tokens:
        times = [t for tok, t in drop_times if tok == token]
        assert len(times) >= 2
        assert all(b - a >= 30 * 60 for a, b in zip(times, times[1:]))


async def test_delay_is_split_into_pause_checking_steps(bot, dropper, clock):
    await run(bot, time_limit = 1)
    steps = round(per_drop_delay(3) / 2)
    assert clock.sleeps.count(2) == steps  # uniform(2, 3) -> 2s steps
    assert clock.now == pytest.approx(steps * 2)


async def test_start_delay(bot, dropper, clock):
    times = []
    dropper.side_effect = lambda *a: times.append(clock.now)
    await run(bot, time_limit = 1, start_delay = 100)
    assert times == [100]  # 50 steps of 2s before the first drop
    assert clock.sleeps[:50] == [2] * 50


async def test_start_delay_respects_pause(bot, dropper, clock):
    bot.pause_event.clear()
    task = asyncio.create_task(run(bot, time_limit = 1, start_delay = 10))
    await settle()
    assert clock.now == 0
    dropper.assert_not_called()
    bot.pause_event.set()
    await task
    dropper.assert_awaited_once()


async def test_time_limit_counts_from_end_of_start_delay(bot, dropper):
    await run(bot, time_limit = 1, start_delay = 10000)
    dropper.assert_awaited_once()


async def test_drop_skip(bot, discord, dropper, rng, capsys):
    bot.DROP_SKIP_RATE = 0.5
    rng.randoms.extend([0.4, 0.6])  # Skip tok1, drop with tok2
    await run(bot, time_limit = per_drop_delay(3) * 2 - 1)
    assert [c.args[0] for c in dropper.await_args_list] == ["tok2"]
    assert "[Account #1] Skipped drop." in capsys.readouterr().out


async def test_random_commands_between_drops(bot, discord, dropper, rng):
    bot.RANDOM_COMMAND_RATE = 1.0
    rng.default_random = 0.5  # Below the random command rate, above the drop skip rate (0.0)
    await run(bot, time_limit = 1)
    sent = discord.sent()
    commands = [c for t, ch, c in sent if c in bot.RANDOM_COMMANDS]
    assert len(commands) == round(per_drop_delay(3) / 2)  # One per 2-3s step at 100%
    assert all(t == "tok1" and ch == "100" for t, ch, _ in sent[:-1])


async def test_no_random_commands_at_zero_rate(bot, discord, dropper, rng):
    rng.default_random = 0.0
    await run(bot, time_limit = 1)
    assert [c for _, _, c in discord.sent() if c in bot.RANDOM_COMMANDS] == []


@pytest.mark.parametrize("error", [aiohttp.ClientError("boom"), asyncio.TimeoutError()])
async def test_random_command_network_errors_are_ignored(bot, dropper, rng, monkeypatch, error):
    bot.RANDOM_COMMAND_RATE = 1.0
    rng.default_random = 0.5
    send = AsyncMock(side_effect = error)
    monkeypatch.setattr(bot, "send_message", send)
    await run(bot, time_limit = per_drop_delay(3) * 2 - 1)
    assert dropper.await_count == 2  # The channel kept going


async def test_unexpected_error_in_delay_stops_channel(bot, dropper, rng, monkeypatch, capsys):
    bot.RANDOM_COMMAND_RATE = 1.0
    rng.default_random = 0.5
    monkeypatch.setattr(bot, "send_message", AsyncMock(side_effect = ValueError("weird")))
    await run(bot, time_limit = 10 ** 9)
    assert dropper.await_count == 1
    assert "Error in Channel #1 Script Instance" in capsys.readouterr().out


async def test_drop_error_is_logged_and_channel_continues(bot, dropper, capsys):
    dropper.side_effect = [RuntimeError("connection reset"), None]
    await run(bot, time_limit = per_drop_delay(3) * 2 - 1)
    assert dropper.await_count == 2
    out = capsys.readouterr().out
    assert "Error in Channel #2 Drop" not in out
    assert "❌ Error in Channel #1 Drop ❌\nconnection reset" in out


async def test_system_exit_from_drop_is_not_swallowed(bot, dropper):
    dropper.side_effect = SystemExit()
    with pytest.raises(SystemExit):
        await run(bot, time_limit = 10 ** 9)


async def test_empty_channel_is_reported(bot, dropper, capsys):
    await run(bot, time_limit = 10, channel_tokens = [])
    assert "Error in Channel #1 Script Instance" in capsys.readouterr().out
    dropper.assert_not_called()


async def test_drop_waits_while_paused(bot, dropper):
    async def pause_during_drop(*args):
        bot.pause_event.clear()
    dropper.side_effect = pause_during_drop
    task = asyncio.create_task(run(bot, time_limit = 1))
    await settle()
    assert not task.done()
    bot.pause_event.set()
    await task


# --------------------------------------------------------------------------- #
# Drop fail limit
# --------------------------------------------------------------------------- #

def failing_dropper(bot, dropper, failures = 1):
    async def fail(*args):
        bot.drop_fail_count += failures
    dropper.side_effect = fail


async def test_below_limit_keeps_running(bot, discord, dropper):
    bot.drop_fail_count = 3
    failing_dropper(bot, dropper)  # 4/5
    await run(bot, time_limit = 1)
    assert bot.pause_event.is_set()
    assert [c for _, _, c in discord.sent() if "Drop fail limit" in c] == []


async def test_limit_disabled_never_pauses(bot, discord, dropper):
    bot.DROP_FAIL_LIMIT = -1
    failing_dropper(bot, dropper, failures = 100)
    await run(bot, time_limit = per_drop_delay(3) * 3 - 1)
    assert dropper.await_count == 3
    assert bot.pause_event.is_set()


async def test_limit_prompts_and_resumes(bot, discord, dropper, inputs, capsys):
    inputs.expect("oops", "")  # A wrong answer re-prompts
    bot.drop_fail_count = 4
    failing_dropper(bot, dropper)
    await run(bot, time_limit = per_drop_delay(3) * 2 - 1)
    assert discord.sent()[0] == ("tok1", "300", "⚠️ Drop fail limit reached")
    assert len(inputs.prompts) == 2
    assert "Drop Fail Limit Reached" in inputs.prompts[0]
    assert "failed to retrieve 5 total drops" in inputs.prompts[0]
    assert bot.drop_fail_count == 1  # Reset on resume, then the next drop failed again
    assert bot.pause_event.is_set()
    assert dropper.await_count == 2
    assert "Reset drop fail count. Resuming drops..." in capsys.readouterr().out


async def test_limit_without_command_channel_prompts(bot, discord, dropper, inputs):
    inputs.expect("")
    bot.COMMAND_CHANNEL_IDS = []
    bot.drop_fail_count = 5
    await run(bot, time_limit = 1)
    assert [c for _, _, c in discord.sent() if "Drop fail limit" in c] == []
    assert len(inputs.prompts) == 1
    assert bot.drop_fail_count == 0


async def test_limit_reached_once_pauses_every_channel(bot, discord, dropper, monkeypatch):
    """Only the channel that hits the limit should report it; the others must wait."""
    async def wait_for_enter(*args):
        await asyncio.Event().wait()  # Nobody presses Enter

    monkeypatch.setattr(bot, "async_input_handler", wait_for_enter)
    failing_dropper(bot, dropper, failures = 5)
    tasks = [asyncio.create_task(bot.run_instance(n, ch, delay, list(CHANNEL_TOKENS), 10 ** 9)) for n, ch, delay in ((1, "100", 0), (2, "101", 10))]
    await settle(200)
    assert [c for _, _, c in discord.sent()].count("⚠️ Drop fail limit reached") == 1
    assert dropper.await_count == 1
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions = True)


async def test_remote_resume_unblocks_channel_waiting_for_terminal(bot, discord, dropper, inputs, monkeypatch):
    inputs.expect()
    release = threading.Event()

    def blocking_input(prompt = ""):
        inputs.prompts.append(prompt)
        release.wait(5)
        return "not enter"

    monkeypatch.setattr("builtins.input", blocking_input)
    bot.drop_fail_count = 5
    task = asyncio.create_task(run(bot, time_limit = per_drop_delay(3) * 2 - 1))
    try:
        for _ in range(100):
            await REAL_SLEEP(0.01)
            if inputs.prompts:
                break
        await bot.reset_drop_fail_count()  # cmd /resume
        bot.pause_event.set()
        for _ in range(50):
            await REAL_SLEEP(0.01)
        assert dropper.await_count == 2
    finally:
        task.cancel()
        release.set()
        await asyncio.gather(task, bot.input_task, return_exceptions = True)


async def test_input_handler_reuses_pending_input_after_remote_resume(bot, inputs, monkeypatch, capsys):
    """input() cannot be cancelled, so a later prompt must reuse it instead of starting a second stdin reader."""
    inputs.expect()
    release = threading.Event()

    def blocking_input(prompt = ""):
        inputs.prompts.append(prompt)
        release.wait(5)
        return ""

    monkeypatch.setattr("builtins.input", blocking_input)
    first = asyncio.create_task(bot.async_input_handler("first> ", "", bot.DROP_FAIL_LIMIT_REACHED_FLAG))
    await REAL_SLEEP(0.05)
    bot.pause_event.set()  # cmd /resume
    await asyncio.wait_for(first, 1)
    pending = bot.input_task
    assert not pending.done()
    second = asyncio.create_task(bot.async_input_handler("second> ", "", bot.DROP_FAIL_LIMIT_REACHED_FLAG))
    await REAL_SLEEP(0.05)
    assert bot.input_task is pending
    assert inputs.prompts == ["first> "]
    assert "second> " in capsys.readouterr().out
    release.set()  # Enter
    await asyncio.wait_for(second, 1)
    assert bot.pause_event.is_set()


async def test_execution_completed_prompt_ignores_remote_resume(bot, inputs, monkeypatch):
    inputs.expect()
    release = threading.Event()
    monkeypatch.setattr("builtins.input", lambda prompt = "": release.wait(5) and "x")
    handler = asyncio.create_task(bot.async_input_handler("", "", bot.EXECUTION_COMPLETED_FLAG))
    await REAL_SLEEP(0.05)
    bot.pause_event.set()
    await REAL_SLEEP(0.05)
    assert not handler.done()  # Only Enter restarts (or the window is closed)
    handler.cancel()
    release.set()
    await asyncio.gather(handler, bot.input_task, return_exceptions = True)


async def test_no_drop_while_paused_before_turn(bot, dropper):
    bot.pause_event.clear()
    task = asyncio.create_task(run(bot, time_limit = 1))
    await settle()
    dropper.assert_not_called()
    bot.pause_event.set()
    await task
    dropper.assert_awaited_once()


# --------------------------------------------------------------------------- #
# reset_drop_fail_count / async_input_handler
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("limit, count, expected", [
    (5, 5, 0),
    (5, 7, 0),
    (5, 4, 4),  # Not at the limit: keep the count
    (-1, 9, 9),  # Limit disabled
    (1, 1, 0),
])
async def test_reset_drop_fail_count(bot, capsys, limit, count, expected):
    bot.DROP_FAIL_LIMIT = limit
    bot.drop_fail_count = count
    await bot.reset_drop_fail_count()
    assert bot.drop_fail_count == expected
    assert ("Reset drop fail count" in capsys.readouterr().out) is (expected == 0)


async def test_input_handler_pauses_until_target_input(bot, inputs, monkeypatch):
    inputs.expect("x", "y", "go")
    seen = []
    original = asyncio.to_thread

    async def spy(func, *args):
        seen.append(bot.pause_event.is_set())
        return await original(func, *args)

    monkeypatch.setattr(main.asyncio, "to_thread", spy)
    await bot.async_input_handler("prompt> ", "go", "other flag")
    assert seen == [False, False, False]  # Paused while waiting for input
    assert inputs.prompts == ["prompt> "] * 3
    assert bot.pause_event.is_set()


async def test_input_handler_drop_fail_flag_resets_count(bot, inputs):
    inputs.expect("")
    bot.drop_fail_count = 5
    await bot.async_input_handler("", "", bot.DROP_FAIL_LIMIT_REACHED_FLAG)
    assert bot.drop_fail_count == 0
    assert bot.pause_event.is_set()


async def test_input_handler_execution_completed_relaunches(bot, inputs, system):
    inputs.expect("")
    with pytest.raises(SystemExit):
        await bot.async_input_handler("", "", bot.EXECUTION_COMPLETED_FLAG)
    system.shell_execute.assert_called_once_with(
        None, None, sys.executable, subprocess.list2cmdline(sys.argv + ["--no-relaunch"]), None, 1
    )


async def test_input_handler_other_flag_does_not_reset_or_relaunch(bot, inputs, system):
    inputs.expect("")
    bot.drop_fail_count = 5
    await bot.async_input_handler("", "", "something else")
    assert bot.drop_fail_count == 5
    system.shell_execute.assert_not_called()
