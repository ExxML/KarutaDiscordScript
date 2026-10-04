"""DropScript.__init__ constants and DropScript.check_config validation."""
import asyncio

import pytest

import config
import main
from conftest import CARD_EMOJIS


@pytest.fixture
def script():
    s = main.DropScript()
    # A fully valid configuration; individual tests break one setting at a time
    s.COMMAND_USER_IDS = ["111"]
    s.COMMAND_CHANNEL_IDS = ["222"]
    s.DROP_CHANNEL_IDS = ["333", "444"]
    s.SERVER_ACTIVITY_DROP_CHANNEL_IDS = ["555"]
    return s


# --------------------------------------------------------------------------- #
# __init__
# --------------------------------------------------------------------------- #

def test_init_copies_every_config_setting():
    script = main.DropScript()
    for name, value in vars(config.Config()).items():
        assert getattr(script, name) == value


def test_init_constants():
    script = main.DropScript()
    assert script.KARUTA_BOT_ID == "646937666251915264"
    assert script.CARD_COMPANION_BOT_ID == "1380936713639166082"
    assert script.CARD_EMOJIS == CARD_EMOJIS
    assert script.EMOJIS == CARD_EMOJIS[:3]  # Script drops always contain 3 cards
    assert script.EMOJI_MAP == {emoji: f"[{i}]" for i, emoji in enumerate(CARD_EMOJIS, start = 1)}
    assert script.CARD_COMPANION_POG_EMOJIS == [f":no_{i}:" for i in range(1, 10)]
    assert script.KARUTA_ANY_DROP_MESSAGE_REGEX.search("<@1> is dropping 4 cards!")
    assert script.KARUTA_ANY_DROP_MESSAGE_REGEX.search("<@1> is dropping 3 cards!")
    assert not script.KARUTA_ANY_DROP_MESSAGE_REGEX.search("<@1> is dropping cards!")


def test_init_initial_state():
    script = main.DropScript()
    assert script.drop_fail_count == 0
    assert isinstance(script.drop_fail_count_lock, asyncio.Lock)
    assert script.pause_event.is_set()  # Script starts unpaused
    assert script.background_tasks == set()
    assert script.token_headers == {}
    assert script.tokens == []
    assert script.loop is None


def test_init_commands_use_configured_prefix(monkeypatch):
    original_init = config.Config.__init__

    def patched_init(self):
        original_init(self)
        self.KARUTA_PREFIX = "x"

    monkeypatch.setattr(config.Config, "__init__", patched_init)
    script = main.DropScript()
    assert script.DROP_COMMANDS == ["xdrop", "xd"]
    assert script.BURN_COMMANDS == ["xburn", "xb"]
    assert script.BUY_EXTRA_GRAB_COMMAND == "xbuy extra grab"
    assert all(command.startswith("x") for command in script.RANDOM_COMMANDS)


def test_random_commands_and_messages_are_harmless():
    """Random 'human' commands must never be drops, burns, gives, trades or purchases."""
    script = main.DropScript()
    dangerous = ("kd", "kdrop", "kb", "kburn", "kg", "kgive", "kmt", "kmultitrade", "kmb", "kmultiburn", "kbuy", "ktrade")
    for command in script.RANDOM_COMMANDS:
        assert command.split()[0] not in dangerous, command
    for message in script.RANDOM_MESSAGES + script.TIME_LIMIT_EXCEEDED_MESSAGES:
        assert message.split()[0] not in dangerous, message
        assert not message.startswith("cmd"), message  # Would be parsed as a message command


# --------------------------------------------------------------------------- #
# check_config
# --------------------------------------------------------------------------- #

def test_valid_config_passes(script):
    script.check_config()  # No input() prompt (enforced by the inputs fixture) and no SystemExit


@pytest.mark.parametrize("name, value", [
    ("COMMAND_USER_IDS", []),  # Empty = any user may send commands
    ("COMMAND_CHANNEL_IDS", []),  # Empty = commands disabled
    ("SERVER_ACTIVITY_DROP_CHANNEL_IDS", []),
])
def test_optional_id_lists_may_be_empty(script, name, value):
    setattr(script, name, value)
    script.check_config()


@pytest.mark.parametrize("name", ["COMMAND_USER_IDS", "COMMAND_CHANNEL_IDS", "DROP_CHANNEL_IDS", "SERVER_ACTIVITY_DROP_CHANNEL_IDS"])
@pytest.mark.parametrize("bad_id", ["", "abc", "12a", " 123", "-1", "1.0"])
def test_non_numeric_id_strings_rejected(script, inputs, name, bad_id):
    inputs.expect()
    setattr(script, name, ["123", bad_id])
    with pytest.raises(SystemExit):
        script.check_config()
    assert "non-empty, numeric strings" in inputs.prompts[0]


def test_default_config_placeholder_ids_rejected(inputs):
    """The shipped config.py has [""] placeholders, which must be rejected until the user fills them in."""
    inputs.expect()
    with pytest.raises(SystemExit):
        main.DropScript().check_config()
    assert len(inputs.prompts) == 1


@pytest.mark.parametrize("name", ["COMMAND_USER_IDS", "COMMAND_CHANNEL_IDS", "DROP_CHANNEL_IDS", "SERVER_ACTIVITY_DROP_CHANNEL_IDS"])
@pytest.mark.parametrize("bad_value", [[123], None])
def test_integer_or_missing_id_lists_rejected(script, inputs, name, bad_value):
    inputs.expect()
    setattr(script, name, bad_value)
    with pytest.raises(SystemExit):
        script.check_config()
    assert "strings (not integers)" in inputs.prompts[0]


VALID_BOUNDARIES = [
    ("KARUTA_PREFIX", "!"),
    ("TIME_LIMIT_HOURS_MIN", 0),
    ("TIME_LIMIT_HOURS_MIN", 0.5),
    ("TIME_LIMIT_HOURS_MAX", 10.5),
    ("TERMINAL_VISIBILITY", 0),
    ("TERMINAL_VISIBILITY", 1),
    ("CHANNEL_SKIP_RATE", 0.0),
    ("CHANNEL_SKIP_RATE", 1.0),
    ("DROP_SKIP_RATE", 0.0),
    ("DROP_SKIP_RATE", 1.0),
    ("RANDOM_COMMAND_RATE", 0.0),
    ("RANDOM_COMMAND_RATE", 1.0),
    ("RATE_LIMIT", 0),
    ("DROP_FAIL_LIMIT", -1),
    ("DROP_FAIL_LIMIT", 1),
    ("SKIP_GRAB_NON_POG_CARD_RATE", 0.0),
    ("SKIP_GRAB_NON_POG_CARD_RATE", 1.0),
] + [(flag, value) for flag in ("SPECIAL_EVENT", "SHUFFLE_ACCOUNTS", "ONLY_GRAB_POG_CARDS", "GRAB_SERVER_POG_CARDS",
                               "ATTEMPT_EXTRA_POG_GRABS", "ATTEMPT_BUY_EXTRA_GRABS", "BURN_NON_POG_CARDS", "FIGHT_FOR_POG_CARD")
     for value in (True, False)]


@pytest.mark.parametrize("name, value", VALID_BOUNDARIES)
def test_valid_setting_values_pass(script, name, value):
    setattr(script, name, value)
    script.check_config()


INVALID_SETTINGS = [
    ("KARUTA_PREFIX", 1),
    ("KARUTA_PREFIX", None),
    ("SPECIAL_EVENT", 1),
    ("SPECIAL_EVENT", "True"),
    ("SHUFFLE_ACCOUNTS", 0),
    ("TIME_LIMIT_HOURS_MIN", -1),
    ("TIME_LIMIT_HOURS_MIN", "6"),
    ("TIME_LIMIT_HOURS_MAX", -0.1),
    ("TIME_LIMIT_HOURS_MAX", None),
    ("TERMINAL_VISIBILITY", 2),
    ("TERMINAL_VISIBILITY", -1),
    ("TERMINAL_VISIBILITY", 1.0),
    ("CHANNEL_SKIP_RATE", 0),  # Must be a float
    ("CHANNEL_SKIP_RATE", -0.01),
    ("CHANNEL_SKIP_RATE", 1.01),
    ("CHANNEL_SKIP_RATE", float("nan")),
    ("DROP_SKIP_RATE", 1),
    ("DROP_SKIP_RATE", 1.5),
    ("DROP_SKIP_RATE", -0.5),
    ("RANDOM_COMMAND_RATE", 0),
    ("RANDOM_COMMAND_RATE", 2.0),
    ("RATE_LIMIT", -1),
    ("RATE_LIMIT", 3.0),
    ("DROP_FAIL_LIMIT", 0),
    ("DROP_FAIL_LIMIT", -2),
    ("DROP_FAIL_LIMIT", 5.0),
    ("ONLY_GRAB_POG_CARDS", "False"),
    ("SKIP_GRAB_NON_POG_CARD_RATE", 0),
    ("SKIP_GRAB_NON_POG_CARD_RATE", 1.2),
    ("SKIP_GRAB_NON_POG_CARD_RATE", -0.1),
    ("GRAB_SERVER_POG_CARDS", None),
    ("ATTEMPT_EXTRA_POG_GRABS", 1),
    ("ATTEMPT_BUY_EXTRA_GRABS", "yes"),
    ("BURN_NON_POG_CARDS", 0),
    ("FIGHT_FOR_POG_CARD", []),
]


@pytest.mark.parametrize("name, value", INVALID_SETTINGS)
def test_invalid_setting_values_rejected(script, inputs, name, value):
    inputs.expect()
    setattr(script, name, value)
    with pytest.raises(SystemExit):
        script.check_config()
    assert inputs.prompts == ["⛔ Configuration Error ⛔\nPlease enter valid values in config.py."]


def test_min_time_limit_greater_than_max_rejected(script, inputs):
    inputs.expect()
    script.TIME_LIMIT_HOURS_MIN = 8
    script.TIME_LIMIT_HOURS_MAX = 7.5
    with pytest.raises(SystemExit):
        script.check_config()
    assert "maximum time limit greater than or equal to the minimum" in inputs.prompts[0]


def test_equal_min_and_max_time_limits_pass(script):
    script.TIME_LIMIT_HOURS_MIN = script.TIME_LIMIT_HOURS_MAX = 7
    script.check_config()


@pytest.mark.parametrize("name", ["TIME_LIMIT_HOURS_MIN", "TIME_LIMIT_HOURS_MAX"])
def test_infinite_time_limit_rejected(script, inputs, name):
    inputs.expect()
    setattr(script, name, float("inf"))
    with pytest.raises(SystemExit):
        script.check_config()
