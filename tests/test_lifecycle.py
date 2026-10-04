"""Script startup/shutdown: background tasks, command checkers, account-to-channel assignment, run_script,
exit handlers and the __main__ entry point."""
import asyncio
import runpy
import signal
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import main
from conftest import REAL_SLEEP, TOKENS, settle

MAIN_PATH = Path(__file__).resolve().parents[1] / "drop_script" / "main.py"


# --------------------------------------------------------------------------- #
# Background tasks
# --------------------------------------------------------------------------- #

async def test_background_task_is_tracked_until_done(bot):
    gate = asyncio.Event()

    async def job():
        await gate.wait()
        return "ok"

    task = bot.create_background_task(job())
    assert task in bot.background_tasks
    gate.set()
    assert await task == "ok"
    await REAL_SLEEP(0)  # Done callbacks run on the next loop iteration
    assert bot.background_tasks == set()


async def test_background_task_error_is_reported(bot, capsys):
    async def job():
        raise ValueError("burn exploded")

    task = bot.create_background_task(job())
    await asyncio.gather(task, return_exceptions = True)
    await REAL_SLEEP(0)
    assert bot.background_tasks == set()
    assert "❌ Background Task Error ❌\nburn exploded" in capsys.readouterr().out


async def test_cancelled_background_task_is_silent(bot, capsys):
    task = bot.create_background_task(asyncio.Event().wait())
    await REAL_SLEEP(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions = True)
    await REAL_SLEEP(0)
    assert bot.background_tasks == set()
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# Command checkers
# --------------------------------------------------------------------------- #

@pytest.fixture
def checker_cls(monkeypatch):
    instances = []

    class FakeChecker:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.run_command_checker = AsyncMock()
            instances.append(self)

    monkeypatch.setattr(main, "CommandChecker", FakeChecker)
    return instances


async def test_command_checker_per_command_channel(bot, checker_cls, capsys):
    bot.COMMAND_CHANNEL_IDS = ["300", "301"]
    await bot.run_command_checkers()
    assert [c.kwargs["command_channel_id"] for c in checker_cls] == ["300", "301"]
    for checker in checker_cls:
        assert checker.kwargs["main"] is bot
        assert checker.kwargs["tokens"] is bot.tokens
        assert checker.kwargs["command_user_ids"] == bot.COMMAND_USER_IDS
        assert checker.kwargs["karuta_prefix"] == "k"
        assert checker.kwargs["karuta_bot_id"] == bot.KARUTA_BOT_ID
        assert checker.kwargs["rate_limit"] == bot.RATE_LIMIT
    assert len(bot.background_tasks) == 2
    await asyncio.gather(*list(bot.background_tasks))
    assert all(c.run_command_checker.await_count == 1 for c in checker_cls)
    assert "Message commands are enabled in 2 channel(s)." in capsys.readouterr().out


async def test_command_checkers_disabled(bot, checker_cls, capsys):
    bot.COMMAND_CHANNEL_IDS = []
    await bot.run_command_checkers()
    assert checker_cls == []
    assert bot.background_tasks == set()
    assert "Message commands are disabled." in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# set_token_dictionaries
# --------------------------------------------------------------------------- #

async def test_three_accounts_per_channel_in_order(bot):
    bot.shuffled_tokens = None
    await bot.set_token_dictionaries()
    assert dict(bot.channel_token_dict) == {"100": ["tok1", "tok2", "tok3"], "101": ["tok4", "tok5", "tok6"]}
    assert bot.token_channel_dict["tok5"] == "101"


async def test_shuffled_tokens_are_used(bot):
    bot.shuffled_tokens = list(reversed(TOKENS))
    await bot.set_token_dictionaries()
    assert dict(bot.channel_token_dict) == {"100": ["tok6", "tok5", "tok4"], "101": ["tok3", "tok2", "tok1"]}


async def test_partial_last_channel(bot):
    bot.tokens = TOKENS[:4]
    bot.shuffled_tokens = None
    await bot.set_token_dictionaries()
    assert dict(bot.channel_token_dict) == {"100": ["tok1", "tok2", "tok3"], "101": ["tok4"]}


async def test_every_account_assigned_exactly_once(bot):
    bot.shuffled_tokens = None
    await bot.set_token_dictionaries()
    assigned = [t for tokens in bot.channel_token_dict.values() for t in tokens]
    assert sorted(assigned) == sorted(bot.tokens)
    assert all(len(tokens) <= 3 for tokens in bot.channel_token_dict.values())


# --------------------------------------------------------------------------- #
# run_script
# --------------------------------------------------------------------------- #

@pytest.fixture
def script(bot, monkeypatch, checker_cls):
    bot.run_instance = AsyncMock()
    bot.async_input_handler = AsyncMock()
    server_checker = MagicMock()
    monkeypatch.setattr(main, "ServerDropChecker", server_checker)
    bot.server_checker_cls = server_checker
    bot.TIME_LIMIT_HOURS_MIN = 6
    bot.TIME_LIMIT_HOURS_MAX = 10
    return bot


async def test_run_script_starts_every_channel(script, discord, capsys):
    await script.run_script()
    assert script.loop is asyncio.get_running_loop()
    calls = [c.args for c in script.run_instance.await_args_list]
    assert [(n, ch, toks) for n, ch, _, toks, _ in calls] == [
        (1, "100", ["tok1", "tok2", "tok3"]),
        (2, "101", ["tok4", "tok5", "tok6"]),
    ]
    # Start delays are staggered by 210s slots plus 5-60s; time limits are within the configured hours
    assert [delay for _, _, delay, _, _ in calls] == [0 * 210 + 5, 1 * 210 + 5]
    assert all(6 * 3600 <= limit <= 10 * 3600 for *_, limit in calls)
    assert calls[0][3] is not script.channel_token_dict["100"]  # Each instance gets its own copy
    out = capsys.readouterr().out
    assert "Channel #1 will run for 6.0 hrs" in out
    assert "  - Account #4" in out
    assert "All dropped cards will be grabbed" in out


async def test_run_script_announces_start_and_end(script, discord):
    await script.run_script()
    assert [(ch, c) for _, ch, c in discord.sent()] == [("300", "Execution started"), ("300", "Execution completed")]


async def test_run_script_without_command_channels_is_silent(script, discord):
    script.COMMAND_CHANNEL_IDS = []
    await script.run_script()
    assert discord.sent() == []


async def test_run_script_prompts_restart_with_visible_terminal(script, discord):
    await script.run_script()
    script.async_input_handler.assert_awaited_once()
    assert script.async_input_handler.await_args.args[1:] == ("", script.EXECUTION_COMPLETED_FLAG)


async def test_run_script_ends_with_hidden_terminal(script, discord, system):
    script.TERMINAL_VISIBILITY = 0
    await script.run_script()
    script.async_input_handler.assert_not_called()
    system.win32gui.ShowWindow.assert_called_once_with(system.win32console.GetConsoleWindow.return_value, main.win32con.SW_HIDE)


async def test_run_script_keeps_visible_terminal(script, discord, system):
    await script.run_script()
    system.win32gui.ShowWindow.assert_not_called()


async def test_run_script_shuffles_accounts(script, discord, rng):
    script.SHUFFLE_ACCOUNTS = True
    await script.run_script()
    assert script.shuffled_tokens == script.tokens  # FakeRandom.sample keeps the order
    assert script.shuffled_tokens is not script.tokens


async def test_run_script_without_shuffle(script, discord):
    await script.run_script()
    assert script.shuffled_tokens is None


async def test_run_script_skips_channels(script, discord, rng, capsys):
    script.CHANNEL_SKIP_RATE = 0.5
    rng.randoms.extend([0.1, 0.9])
    await script.run_script()
    assert [c.args[1] for c in script.run_instance.await_args_list] == ["101"]
    assert "Channel #1 will be skipped." in capsys.readouterr().out


async def test_run_script_all_channels_skipped(script, discord):
    script.CHANNEL_SKIP_RATE = 1.0
    await script.run_script()
    script.run_instance.assert_not_called()
    assert [c for _, _, c in discord.sent()] == ["Execution started", "Execution completed"]


@pytest.mark.parametrize("special, server, created", [(False, False, False), (True, False, True), (False, True, True), (True, True, True)])
async def test_run_script_server_drop_checker(script, discord, special, server, created):
    script.SPECIAL_EVENT = special
    script.GRAB_SERVER_POG_CARDS = server
    await script.run_script()
    if created:
        script.server_checker_cls.assert_called_once_with(main = script)
        assert script.server_drop_checker is script.server_checker_cls.return_value
    else:
        script.server_checker_cls.assert_not_called()


async def test_run_script_only_pog_notice(script, discord, capsys):
    script.ONLY_GRAB_POG_CARDS = True
    await script.run_script()
    assert "Only pog cards (as defined by CardCompanion) will be grabbed." in capsys.readouterr().out


async def test_run_script_starts_command_checkers(script, discord, checker_cls):
    await script.run_script()
    assert [c.kwargs["command_channel_id"] for c in checker_cls] == ["300"]


async def test_run_script_time_limits_are_randomised_per_channel(script, discord, monkeypatch):
    picks = iter([5.0, 6 * 3600.0, 60.0, 9 * 3600.0])  # (start offset, time limit) per channel
    monkeypatch.setattr(main.random, "uniform", lambda a, b: next(picks))
    await script.run_script()
    assert [c.args[4] for c in script.run_instance.await_args_list] == [6 * 3600, 9 * 3600]


# --------------------------------------------------------------------------- #
# Exit handlers
# --------------------------------------------------------------------------- #

async def test_cleanup_announces_shutdown(bot, discord):
    await bot.cleanup()
    assert discord.sent() == [("tok1", "300", "Shutting down...")]


def test_console_handler_ignores_ctrl_c(bot, discord):
    assert bot.console_ctrl_handler(main.win32con.CTRL_C_EVENT) is False
    assert discord.sent() == []


def test_console_handler_close_without_loop(bot, discord, capsys):
    assert bot.console_ctrl_handler(main.win32con.CTRL_CLOSE_EVENT) is True
    assert discord.sent() == [("tok1", "300", "Shutting down...")]
    assert "Terminal window closed. Running cleanup..." in capsys.readouterr().out


def test_console_handler_close_with_running_loop(bot, discord):
    """The handler runs on a Windows thread; cleanup must be scheduled on the script's loop."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target = loop.run_forever, daemon = True)
    thread.start()
    try:
        bot.loop = loop
        assert bot.console_ctrl_handler(main.win32con.CTRL_CLOSE_EVENT) is True
        assert discord.sent() == [("tok1", "300", "Shutting down...")]
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
        loop.close()


def test_console_handler_reports_cleanup_failure(bot, monkeypatch, capsys):
    monkeypatch.setattr(bot, "cleanup", AsyncMock(side_effect = RuntimeError("offline")))
    assert bot.console_ctrl_handler(main.win32con.CTRL_CLOSE_EVENT) is True
    assert "Cleanup failed: offline" in capsys.readouterr().out


def test_console_handler_cleanup_times_out(bot, monkeypatch, capsys):
    real_wait_for = asyncio.wait_for

    async def hang():
        await asyncio.Event().wait()

    monkeypatch.setattr(bot, "cleanup", hang)
    timeouts = []

    def short_wait_for(coro, timeout):
        timeouts.append(timeout)
        return real_wait_for(coro, 0.01)

    monkeypatch.setattr(main.asyncio, "wait_for", short_wait_for)
    assert bot.console_ctrl_handler(main.win32con.CTRL_CLOSE_EVENT) is True
    assert timeouts == [4]  # Windows kills the process ~5s after CTRL_CLOSE_EVENT
    assert "Cleanup failed" in capsys.readouterr().out


@pytest.fixture
def fake_sys(monkeypatch):
    exit_mock = MagicMock()
    monkeypatch.setattr(main, "sys", SimpleNamespace(exit = exit_mock, argv = ["main.py"], executable = sys.executable))
    return exit_mock


def test_signal_handler_without_running_loop(bot, discord, fake_sys, capsys):
    bot.signal_handler(signal.SIGINT, None)
    assert discord.sent() == [("tok1", "300", "Shutting down...")]
    fake_sys.assert_called_once_with()
    assert "Exit signal received. Running cleanup..." in capsys.readouterr().out


async def test_signal_handler_with_running_loop(bot, discord, fake_sys):
    bot.signal_handler(signal.SIGTERM, None)
    fake_sys.assert_not_called()  # Exit only after cleanup finished
    await settle()
    assert discord.sent() == [("tok1", "300", "Shutting down...")]
    fake_sys.assert_called_once_with()


async def test_repeated_signal_exits_without_second_cleanup(bot, discord, fake_sys):
    fake_sys.side_effect = [SystemExit, None]  # The second signal's exit raises, like the real sys.exit
    bot.signal_handler(signal.SIGINT, None)
    with pytest.raises(SystemExit):
        bot.signal_handler(signal.SIGINT, None)  # Second Ctrl+C exits immediately
    await settle()
    assert discord.sent() == [("tok1", "300", "Shutting down...")]


async def test_signal_handler_exits_even_if_cleanup_fails(bot, fake_sys, monkeypatch):
    monkeypatch.setattr(bot, "cleanup", AsyncMock(side_effect = RuntimeError("offline")))
    bot.signal_handler(signal.SIGINT, None)
    await settle()
    fake_sys.assert_called_once_with()


# --------------------------------------------------------------------------- #
# __main__
# --------------------------------------------------------------------------- #

@pytest.fixture
def entry(monkeypatch):
    """Run drop_script/main.py as __main__ with every side effect replaced."""
    import ctypes
    import config
    import token_extractor
    import win32api

    shell = MagicMock(return_value = 42)
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(shell32 = SimpleNamespace(ShellExecuteW = shell)))

    original_init = config.Config.__init__
    overrides = {
        "COMMAND_USER_IDS": ["900"], "COMMAND_CHANNEL_IDS": ["300"],
        "DROP_CHANNEL_IDS": ["100", "101"], "SERVER_ACTIVITY_DROP_CHANNEL_IDS": ["200"],
    }

    def config_init(self):
        original_init(self)
        self.__dict__.update(overrides)

    monkeypatch.setattr(config.Config, "__init__", config_init)

    extractor = MagicMock()
    extractor.return_value.main.return_value = list(TOKENS)
    monkeypatch.setattr(token_extractor, "TokenExtractor", extractor)

    signals = MagicMock()
    monkeypatch.setattr(signal, "signal", signals)
    ctrl_handler = MagicMock()
    monkeypatch.setattr(win32api, "SetConsoleCtrlHandler", ctrl_handler)

    ran = []

    def fake_run(coro):
        ran.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(asyncio, "run", fake_run)

    def run(argv):
        monkeypatch.setattr(sys, "argv", argv)
        return runpy.run_path(str(MAIN_PATH), run_name = "__main__")

    return SimpleNamespace(run = run, shell = shell, overrides = overrides, extractor = extractor,
                           signals = signals, ctrl_handler = ctrl_handler, ran = ran)


def test_main_relaunches_in_new_console(entry):
    with pytest.raises(SystemExit):
        entry.run(["main.py"])
    entry.shell.assert_called_once_with(None, None, sys.executable, subprocess.list2cmdline([str(MAIN_PATH), "--no-relaunch"]), None, 1)  # runpy sets argv[0] to the script path
    entry.extractor.assert_not_called()
    assert entry.ran == []


def test_main_relaunch_is_visible_even_when_hidden_mode(entry, monkeypatch):
    """Startup prompts must be visible; run_script() hides the window afterwards."""
    entry.overrides["TERMINAL_VISIBILITY"] = 0
    with pytest.raises(SystemExit):
        entry.run(["main.py"])
    assert entry.shell.call_args.args[-1] == 1


def test_main_runs_script_after_relaunch(entry):
    namespace = entry.run(["main.py", "--no-relaunch"])
    entry.shell.assert_not_called()
    entry.extractor.return_value.main.assert_called_once_with(standalone = False, num_channels = 2)
    bot = namespace["bot"]
    assert bot.tokens == TOKENS
    assert entry.ran == ["run_script"]
    registered = {c.args[0]: c.args[1] for c in entry.signals.call_args_list}
    assert registered == {signal.SIGTERM: bot.signal_handler, signal.SIGINT: bot.signal_handler}
    entry.ctrl_handler.assert_called_once_with(bot.console_ctrl_handler, True)


def test_main_without_command_channels_registers_no_exit_handlers(entry):
    entry.overrides["COMMAND_CHANNEL_IDS"] = []
    entry.run(["main.py", "--no-relaunch"])
    entry.signals.assert_not_called()
    entry.ctrl_handler.assert_not_called()
    assert entry.ran == ["run_script"]


def test_main_rejects_duplicate_tokens(entry, inputs):
    inputs.expect()
    entry.extractor.return_value.main.return_value = ["tok1", "tok2", "tok1"]
    with pytest.raises(SystemExit):
        entry.run(["main.py", "--no-relaunch"])
    assert "The same account was entered more than once" in inputs.prompts[0]
    assert entry.ran == []


def test_main_invalid_config_stops_before_login(entry, inputs):
    inputs.expect()
    entry.overrides["DROP_CHANNEL_IDS"] = ["not a number"]
    with pytest.raises(SystemExit):
        entry.run(["main.py", "--no-relaunch"])
    entry.extractor.assert_not_called()
    assert entry.ran == []
