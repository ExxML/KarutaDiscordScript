"""
Shared fixtures for the drop script (drop_script/main.py) test suite.

Nothing in these tests talks to Discord, launches processes or touches the real
token files. Every external effect main.py can have is replaced with a fake:

- aiohttp.ClientSession -> FakeDiscord, a small in-memory simulation of the Discord
  REST endpoints main.py uses, plus enough of Karuta/CardCompanion to answer drops,
  burns and purchases. Requests to any endpoint the fake does not know about are
  recorded and fail the test, so unexpected API traffic is caught.
- asyncio.sleep / time.monotonic -> FakeClock, so multi-hour schedules run instantly
  and every delay can be asserted on.
- random -> FakeRandom, so card/account assignment is deterministic.
- input(), ShellExecuteW, win32 window calls -> recorders. A test that triggers
  input() without declaring it (inputs.expect()) fails.
"""
import asyncio
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drop_script"))

import main  # noqa: E402

REAL_SLEEP = asyncio.sleep

KARUTA_ID = "646937666251915264"
CARD_COMPANION_ID = "1380936713639166082"
CARD_EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
API = "https://discord.com/api/v10"

TOKENS = ["tok1", "tok2", "tok3", "tok4", "tok5", "tok6"]
USER_IDS = {token: str(500 + i) for i, token in enumerate(TOKENS, start = 1)}  # tok1 -> "501", ...
DROP_CHANNELS = ["100", "101"]
SERVER_CHANNELS = ["200"]
COMMAND_CHANNELS = ["300"]


# --------------------------------------------------------------------------- #
# Fake HTTP layer
# --------------------------------------------------------------------------- #

@dataclass
class Request:
    method: str
    url: str
    path: str
    params: dict
    headers: dict
    json: object

    @property
    def token(self):
        return (self.headers or {}).get("Authorization")


class FakeResponse:
    def __init__(self, status: int = 200, data = None):
        self.status = status
        self._data = data

    async def json(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, discord: "FakeDiscord"):
        self.discord = discord

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get(self, url, headers = None, **kwargs):
        return self.discord.handle("GET", url, headers, kwargs.get("json"))

    def post(self, url, headers = None, json = None, **kwargs):
        return self.discord.handle("POST", url, headers, json)

    def put(self, url, headers = None, json = None, **kwargs):
        return self.discord.handle("PUT", url, headers, json)


def karuta_drop(msg_id: str, user_id: str, num_cards: int = 3, extra_emojis = (), expired = False, reactions = None):
    content = f"<@{user_id}> is dropping {num_cards} cards!"
    if expired:
        content += "\nThis drop has expired and the cards can no longer be grabbed."
    if reactions is None:
        reactions = num_cards
    emojis = CARD_EMOJIS[:reactions] + list(extra_emojis)
    return {
        "id": msg_id,
        "content": content,
        "author": {"id": KARUTA_ID},
        "reactions": [{"emoji": {"id": None, "name": emoji}, "count": 1} for emoji in emojis],
    }


def server_drop(msg_id: str, num_cards: int = 3, extra_emojis = ()):
    msg = karuta_drop(msg_id, "0", num_cards, extra_emojis)
    msg["content"] = f"I'm dropping {num_cards} cards since this server is currently active!"
    return msg


def card_companion_msg(msg_id: str, pog_cards, extra: str = "", reply_to: str | None = None):
    content = (" ".join(f"<:no_{n}:13840000000000000{n}>" for n in pog_cards) or "No pog cards.") + extra
    msg = {"id": msg_id, "content": content, "author": {"id": CARD_COMPANION_ID}}
    if reply_to:
        msg["message_reference"] = {"message_id": reply_to}
    return msg


def karuta_reply(msg_id: str, replying_to: dict | None, content: str = "", title: str | None = None, buttons = ()):
    msg = {
        "id": msg_id,
        "content": content,
        "author": {"id": KARUTA_ID},
        "referenced_message": replying_to,
        "embeds": [{"title": title}] if title else [],
        "components": [],
    }
    if buttons:
        msg["components"] = [{
            "type": 1,
            "components": [{"type": 2, "custom_id": custom_id, "emoji": {"name": emoji}} for emoji, custom_id in buttons],
        }]
    return msg


def user_msg(msg_id: str, user_id: str, content: str = ""):
    return {"id": msg_id, "content": content, "author": {"id": user_id}}


class FakeDiscord:
    """In-memory Discord/Karuta simulation. Histories are stored newest-first, like the real API."""

    def __init__(self):
        self.requests: list[Request] = []
        self.unexpected: list[Request] = []
        self.users = dict(USER_IDS)
        self.history = defaultdict(list)
        self.overrides = []  # [method, compiled regex, deque of responses]
        self.next_id = 1000
        self.guild_id = "4242"
        # Karuta simulation knobs
        self.drop_mode = "drop"  # "drop" | "cooldown" | "none"
        self.drop_card_count = 3
        self.drop_extra_emojis = []  # e.g. special event emojis added to the drop message
        self.pog_cards = []  # CardCompanion pog cards announced for the next drop
        self.card_companion = True  # CardCompanion replies to every drop
        self.player_emojis = set()  # Reactions added by players rather than Karuta
        self.grab_messages = True  # Karuta posts "<@user> took the ... card `code`!" after a grab
        self.reply_to_burn = True
        self.reply_to_purchase = True
        self.last_drop = None
        self.grabbed = {}  # (message id, emoji) -> user id of first grabber

    # ---- helpers for tests ----
    def new_id(self) -> str:
        self.next_id += 1
        return str(self.next_id)

    def add(self, channel_id: str, msg: dict) -> dict:
        self.history[channel_id].insert(0, msg)
        return msg

    def respond(self, method: str, pattern: str, *responses):
        """Queue one-shot responses (status int or FakeResponse) for matching requests, taking priority over the simulation.
        None lets that request through to the simulation."""
        queue = deque(r if r is None or isinstance(r, FakeResponse) else FakeResponse(r, None) for r in responses)
        self.overrides.append([method, re.compile(pattern), queue])

    def calls(self, method: str | None = None, pattern: str | None = None) -> list[Request]:
        return [r for r in self.requests if (method is None or r.method == method) and (pattern is None or re.search(pattern, r.url))]

    def reactions(self):
        """(token, channel id, message id, emoji) of every reaction request, in order."""
        out = []
        for r in self.calls("PUT", r"/reactions/"):
            m = re.match(rf"{re.escape(API)}/channels/(\d+)/messages/(\d+)/reactions/(.+)/@me$", r.url)
            out.append((r.token, m.group(1), m.group(2), m.group(3)))
        return out

    def sent(self):
        """(token, channel id, content) of every message send request, in order."""
        out = []
        for r in self.calls("POST", r"/channels/\d+/messages$"):
            out.append((r.token, r.path.split("/")[4], r.json["content"]))
        return out

    def interactions(self):
        return [r for r in self.calls("POST", r"/interactions$")]

    # ---- request handling ----
    def handle(self, method: str, url: str, headers, body) -> FakeResponse:
        parsed = urlparse(url)
        req = Request(method, url, parsed.path, {k: v[0] for k, v in parse_qs(parsed.query).items()}, dict(headers or {}), body)
        self.requests.append(req)
        for override in self.overrides:
            o_method, regex, queue = override
            if queue and o_method == method and regex.search(url):
                response = queue.popleft()
                if response is not None:
                    return response
                break
        return self.simulate(req)

    def simulate(self, req: Request) -> FakeResponse:
        url, method = req.url, req.method
        if method == "GET" and url == f"{API}/users/@me":
            uid = self.users.get(req.token)
            return FakeResponse(200, {"id": uid}) if uid else FakeResponse(401, {"message": "401: Unauthorized"})
        m = re.match(rf"{re.escape(API)}/channels/(\d+)/messages\?limit=(\d+)$", url)
        if method == "GET" and m:
            return FakeResponse(200, [dict(msg) for msg in self.history[m.group(1)][:int(m.group(2))]])
        m = re.match(rf"{re.escape(API)}/channels/(\d+)/messages$", url)
        if method == "POST" and m:
            return self.post_message(m.group(1), req)
        m = re.match(rf"{re.escape(API)}/channels/(\d+)/messages/(\d+)/reactions/(.+)/@me$", url)
        if method == "PUT" and m:
            self.on_reaction(m.group(1), m.group(2), m.group(3), req.token)
            return FakeResponse(204)
        m = re.match(rf"{re.escape(API)}/channels/(\d+)/messages/(\d+)/reactions/(.+)\?limit=100$", url)
        if method == "GET" and m:
            target = next((msg for msg in self.history[m.group(1)] if msg["id"] == m.group(2)), {})
            karuta_emojis = [r["emoji"]["name"] for r in target.get("reactions", [])]
            emoji = m.group(3)
            users = [{"id": "777"}] if emoji in self.player_emojis else [{"id": KARUTA_ID}] if emoji in karuta_emojis else []
            return FakeResponse(200, users)
        m = re.match(rf"{re.escape(API)}/channels/(\d+)$", url)
        if method == "GET" and m:
            return FakeResponse(200, {"id": m.group(1), "guild_id": self.guild_id})
        if method == "POST" and url == f"{API}/interactions":
            return FakeResponse(204)
        self.unexpected.append(req)
        return FakeResponse(599, None)

    def post_message(self, channel_id: str, req: Request) -> FakeResponse:
        uid = self.users.get(req.token)
        if uid is None:
            return FakeResponse(401, {"message": "401: Unauthorized"})
        content = req.json["content"]
        msg = self.add(channel_id, user_msg(self.new_id(), uid, content))
        words = content.split()
        command = words[0] if words else ""
        if command in ("kdrop", "kd"):
            if self.drop_mode == "drop":
                self.last_drop = self.add(channel_id, karuta_drop(self.new_id(), uid, self.drop_card_count, self.drop_extra_emojis))
                if self.card_companion:
                    self.add(channel_id, card_companion_msg(self.new_id(), self.pog_cards, reply_to = self.last_drop["id"]))
            elif self.drop_mode == "cooldown":
                self.add(channel_id, karuta_reply(self.new_id(), msg, f"<@{uid}>, you must wait `12 minutes` before dropping more cards."))
        elif command in ("kburn", "kb") and self.reply_to_burn:
            self.add(channel_id, karuta_reply(self.new_id(), msg, title = "Burn Card", buttons = [("❌", "burn_cancel"), ("🔥", "burn_confirm")]))
        elif command in ("kgive", "kg"):
            self.add(channel_id, karuta_reply(self.new_id(), msg, title = "Card Transfer", buttons = [("❌", "give_cancel"), ("✅", "give_confirm")]))
        elif content.startswith("kbuy extra grab") and self.reply_to_purchase:
            self.add(channel_id, karuta_reply(self.new_id(), msg, title = "Item Purchase", buttons = [("❌", "buy_cancel"), ("✅", "buy_confirm")]))
        return FakeResponse(200, dict(msg))

    def on_reaction(self, channel_id: str, message_id: str, emoji: str, token: str):
        if not self.grab_messages or emoji not in CARD_EMOJIS:
            return
        target = next((m for m in self.history[channel_id] if m["id"] == message_id), None)
        if not target or target["author"]["id"] != KARUTA_ID or (message_id, emoji) in self.grabbed:
            return
        uid = self.users.get(token)
        self.grabbed[(message_id, emoji)] = uid
        number = CARD_EMOJIS.index(emoji) + 1
        self.add(channel_id, {
            "id": self.new_id(),
            "content": f"<@{uid}> took the **Card {number}** card `c{message_id}{number}`!",
            "author": {"id": KARUTA_ID},
        })


# --------------------------------------------------------------------------- #
# Fake clock / randomness / console
# --------------------------------------------------------------------------- #

class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay, result = None):
        self.sleeps.append(delay)
        self.now += max(delay, 0)
        await REAL_SLEEP(0)
        return result


class FakeRandom:
    """Deterministic stand-in for the random module functions main.py uses."""

    def __init__(self):
        self.randoms = deque()  # values returned by random.random(), in order
        self.default_random = 0.99  # returned once self.randoms is exhausted (never below any rate < 0.99)
        self.chat = False  # result of the 50%/75% "send random messages" coin flips
        self.fighters = 1  # result of random.choice((1, 2)) when fighting for a pog card
        self.reverse_shuffle = False

    def random(self):
        return self.randoms.popleft() if self.randoms else self.default_random

    def uniform(self, a, b):
        return a

    def randint(self, a, b):
        return a

    def choice(self, seq):
        items = list(seq)
        if items in ([True, False], [True, True, True, False]):
            return self.chat
        if items == [1, 2]:
            return self.fighters
        return items[0]

    def shuffle(self, x):
        if self.reverse_shuffle:
            x.reverse()

    def sample(self, population, k):
        return list(population)[:k]


class InputRecorder:
    def __init__(self):
        self.prompts: list[str] = []
        self.responses = deque()
        self.expected = False

    def expect(self, *responses):
        self.expected = True
        self.responses.extend(responses)
        return self

    def __call__(self, prompt = ""):
        self.prompts.append(prompt)
        return self.responses.popleft() if self.responses else ""


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def discord(monkeypatch):
    fake = FakeDiscord()
    monkeypatch.setattr(main.aiohttp, "ClientSession", lambda *a, **kw: FakeSession(fake))
    yield fake
    assert not fake.unexpected, f"Unexpected API requests: {[(r.method, r.url) for r in fake.unexpected]}"


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(asyncio, "sleep", fake.sleep)
    monkeypatch.setattr(main, "time", SimpleNamespace(monotonic = fake.monotonic))
    return fake


@pytest.fixture
def rng(monkeypatch):
    fake = FakeRandom()
    for name in ("random", "uniform", "randint", "choice", "shuffle", "sample"):
        monkeypatch.setattr(main.random, name, getattr(fake, name))
    return fake


@pytest.fixture(autouse = True)
def inputs(monkeypatch):
    recorder = InputRecorder()
    monkeypatch.setattr("builtins.input", recorder)
    yield recorder
    assert recorder.expected or not recorder.prompts, f"Unexpected input() prompts: {recorder.prompts}"


@pytest.fixture(autouse = True)
def system(monkeypatch):
    """Replace every Windows/process side effect main.py can trigger."""
    shell = SimpleNamespace(ShellExecuteW = MagicMock(return_value = 42))
    monkeypatch.setattr(main, "ctypes", SimpleNamespace(windll = SimpleNamespace(shell32 = shell)))
    monkeypatch.setattr(main, "win32console", MagicMock())
    monkeypatch.setattr(main, "win32gui", MagicMock())
    monkeypatch.setattr(main.sys, "argv", ["main.py"])
    return SimpleNamespace(shell_execute = shell.ShellExecuteW, win32gui = main.win32gui, win32console = main.win32console)


@pytest.fixture
def bot(discord, clock, rng):
    b = main.DropScript()
    b.COMMAND_USER_IDS = ["900"]
    b.COMMAND_CHANNEL_IDS = list(COMMAND_CHANNELS)
    b.DROP_CHANNEL_IDS = list(DROP_CHANNELS)
    b.SERVER_ACTIVITY_DROP_CHANNEL_IDS = list(SERVER_CHANNELS)
    b.SPECIAL_EVENT = False
    b.SHUFFLE_ACCOUNTS = False
    b.TERMINAL_VISIBILITY = 1
    b.CHANNEL_SKIP_RATE = 0.0
    b.DROP_SKIP_RATE = 0.0
    b.RANDOM_COMMAND_RATE = 0.0
    b.RATE_LIMIT = 3
    b.DROP_FAIL_LIMIT = 5
    b.ONLY_GRAB_POG_CARDS = False
    b.SKIP_GRAB_NON_POG_CARD_RATE = 0.0
    b.GRAB_SERVER_POG_CARDS = False
    b.ATTEMPT_EXTRA_POG_GRABS = False
    b.ATTEMPT_BUY_EXTRA_GRABS = False
    b.BURN_NON_POG_CARDS = False
    b.FIGHT_FOR_POG_CARD = False
    b.tokens = list(TOKENS)
    return b


async def settle(rounds: int = 50):
    """Let other tasks run until they block (fake sleeps yield once per call)."""
    for _ in range(rounds):
        await REAL_SLEEP(0)
