from server_drop_checker import ServerDropChecker
from command_checker import CommandChecker
from token_extractor import TokenExtractor
from config import Config
from datetime import datetime, timedelta
from collections import defaultdict
import win32console
import win32api
import win32con
import win32gui
import contextlib
import subprocess
import random
import asyncio
import aiohttp
import base64
import ctypes
import signal
import math
import time
import uuid
import json
import sys
import re

class DropScript():
    def __init__(self):
        # Initialize config and map instance constants
        self.__dict__.update(vars(Config()))

        ### DO NOT MODIFY THESE CONSTANTS ###
        self.KARUTA_BOT_ID = "646937666251915264"
        self.KARUTA_DROP_MESSAGE = "is dropping 3 cards!"
        self.KARUTA_ANY_DROP_MESSAGE_REGEX = re.compile(r"is dropping \d+ cards!")  # Other users' drops may contain more than 3 cards
        self.KARUTA_SERVER_ACTIVITY_DROP_MESSAGE = "since this server is currently active!"
        self.KARUTA_EXPIRED_DROP_MESSAGE = "This drop has expired and the cards can no longer be grabbed."
        self.KARUTA_DROP_COOLDOWN_MESSAGE = ", you must wait"

        self.KARUTA_CARD_TRANSFER_TITLE = "Card Transfer"
        self.KARUTA_MULTITRADE_LOCK_MESSAGE = "Both sides must lock in before proceeding to the next step."
        self.KARUTA_MULTITRADE_CONFIRM_MESSAGE = "This trade has been locked."
        self.KARUTA_BURN_TITLE = "Burn Card"
        self.KARUTA_MULTIBURN_TITLE = "Burn Cards"
        self.KARUTA_ITEM_PURCHASE_TITLE = "Item Purchase"

        self.CARD_EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']  # Server drops and other users' drops may contain more than 3 cards
        self.EMOJIS = self.CARD_EMOJIS[:3]  # Script drops always contain 3 cards
        self.EMOJI_MAP = {emoji: f"[{num}]" for num, emoji in enumerate(self.CARD_EMOJIS, start = 1)}  # Use card number instead of emoji in terminal output for better readability

        self.CARD_COMPANION_BOT_ID = "1380936713639166082"
        self.CARD_COMPANION_POG_EMOJIS = [f":no_{num}:" for num in range(1, len(self.CARD_EMOJIS) + 1)]

        self.RANDOM_ADDON = ['', ' ', ' !', ' :D', ' w']
        self.DROP_COMMANDS = [f"{self.KARUTA_PREFIX}drop", f"{self.KARUTA_PREFIX}d"]
        self.BURN_COMMANDS = [f"{self.KARUTA_PREFIX}burn", f"{self.KARUTA_PREFIX}b"]
        self.BUY_EXTRA_GRAB_COMMAND = f"{self.KARUTA_PREFIX}buy extra grab"
        self.RANDOM_COMMANDS = [
            f"{self.KARUTA_PREFIX}reminders", f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}rm", 
            f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}rm", 
            f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}rm", 
            f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}rm", f"{self.KARUTA_PREFIX}lookup", 
            f"{self.KARUTA_PREFIX}lu", f"{self.KARUTA_PREFIX}vote", f"{self.KARUTA_PREFIX}view", 
            f"{self.KARUTA_PREFIX}v", f"{self.KARUTA_PREFIX}collection", f"{self.KARUTA_PREFIX}c", 
            f"{self.KARUTA_PREFIX}c o:wl", f"{self.KARUTA_PREFIX}c o:p", f"{self.KARUTA_PREFIX}c o:eff", 
            f"{self.KARUTA_PREFIX}cardinfo", f"{self.KARUTA_PREFIX}ci", f"{self.KARUTA_PREFIX}cd", 
            f"{self.KARUTA_PREFIX}cd", f"{self.KARUTA_PREFIX}cd", f"{self.KARUTA_PREFIX}cd", 
            f"{self.KARUTA_PREFIX}cooldowns", f"{self.KARUTA_PREFIX}daily", f"{self.KARUTA_PREFIX}monthly", 
            f"{self.KARUTA_PREFIX}help", f"{self.KARUTA_PREFIX}wishlist", f"{self.KARUTA_PREFIX}wl", 
            f"{self.KARUTA_PREFIX}jobboard", f"{self.KARUTA_PREFIX}jb", f"{self.KARUTA_PREFIX}shop", 
            f"{self.KARUTA_PREFIX}itemshop", f"{self.KARUTA_PREFIX}gemshop", f"{self.KARUTA_PREFIX}frameshop", 
            f"{self.KARUTA_PREFIX}inventory", f"{self.KARUTA_PREFIX}inv", f"{self.KARUTA_PREFIX}i", 
            f"{self.KARUTA_PREFIX}i", f"{self.KARUTA_PREFIX}i", f"{self.KARUTA_PREFIX}i", f"{self.KARUTA_PREFIX}i", 
            f"{self.KARUTA_PREFIX}schedule", f"{self.KARUTA_PREFIX}blackmarket", f"{self.KARUTA_PREFIX}bm", 
            f"{self.KARUTA_PREFIX}view", f"{self.KARUTA_PREFIX}afl", f"{self.KARUTA_PREFIX}backgroundshop", 
            f"{self.KARUTA_PREFIX}al"
        ]
        self.RANDOM_MESSAGES = [
            "bruhh", "ggzz", "dude lmao", "tf what", "omg nice", "dam welp", "crazy stuf", "look at dis", "wowza", 
            "wait huh", "umm what", "heyy", "hellooo", "yo", "hows it goin", "thats insane", "nice card", "pretty", 
            "nice drop lol", "clean grab", "dannggg what I wanted that", "can I give u one of my cards for that", 
            "yo i need that card", "gimme that", "how long have you had that??", "check my inv lol", 
            "dude accept the trade", "where should i kmt u?", "ayoo that's clean", "no way you dropped that", 
            "i was just about to grab", "hold up fr?", "yo what are the odds", "someone always steals my pull 😭", 
            "BRO just got my dream card", "real lucky today huh", "wait how rare is that", "gg bro", "wait lemme check wiki", 
            "nah that's a flex card fr", "i swear my luck is cursed", "yo who boosting drops rn", "bruh that was mine 😤", 
            "bet you won't trade that", "wait lemme drop too", "someone check its value lol", "bro always grabs fast af", 
            "here kmt me", "who tryna kmt", "u online for trade?", "can i see ur favs?", "i swear it's rigged", 
            "dawg i was afk nooOO", "nah fr that's wild", "yo queue with me real quick", "yo why so many rares today", 
            "i swear u always pull good stuff", "damn stop stealing my luck lol", "wait that's mint condition right?", 
            "hold up is that sketch art?", "bruh where my luck at", "yo let's duel after this", "tryna 1v1 for it?", 
            "how tf u keep dropping bangers", "wait i missed it BRUH", "i got scammed in trade lol",
            "yo i blinked and missed it", "how u pull sm heat", "who boosting rn lol", "lemme borrow ur luck", 
            "stoppp that's too clean", "yo fr stop hoggin", "wait that's signed right?", "please trade it to me", 
            "you farming rn?", "yo gimme that theme", "bruh stop stealing drops", "i swear that was mine", 
            "how's that even possible lol", "yo ggs on that pull", "can't believe u got that", "W pull fr", 
            "yo thats actually cracked", "nah you cheating fr", "how that even drop here", "yo can i see ur binder", 
            "is that a lp??", "yo whered u get that bg", "nahhh that card's nuts", "WISHING WORKED OMG", 
            "no shot you got that", "how do u drop so good", "yo that pull's fire", "stop flexin ur pulls 🥺", 
            "wait what event is this from", "yo i'm savin that pull", "yo i need to start wishing", "gimme that plsss", 
            "is that even tradable?", "i swear u got admin luck", "yo queue with me bruh", "that card go hard", 
            "lemme wishlist that real quick", "whyd u drop in this channel", "yo teach me your luck", 
            "i'll trade u 3 for it fr", "you pull like a whale", "yo check auction prices", "nah im done lmao", 
            "yo queue now or i'm stealing", "why so many good cards today", "i got baited smh", "yo that's a set piece?", 
            "wait was that a dupe?", "i need that in my favs", "nah u got god luck today", "yo stop sniping me", 
            "i was lagging bruh", "pleaseeee i'll overpay", "yo is that new art?", "AINT NO WAY", "WTF"
        ]
        self.TIME_LIMIT_EXCEEDED_MESSAGES = ["stawp", "stoop", "quittin", "q", "exeeting", "exité", "ceeze", "cloze", '🛑', '🚫', '❌', '⛔']

        self.RELAUNCH_FLAG = "--no-relaunch"
        self.DROP_FAIL_LIMIT_REACHED_FLAG = "Drop Fail Limit Reached"
        self.EXECUTION_COMPLETED_FLAG = "Execution Completed"

        self.BROWSER_VERSIONS = [
            "114.0.5735.198", "115.0.5790.170", "115.0.5790.114", "116.0.5845.111", 
            "116.0.5845.97", "117.0.5938.149", "117.0.5938.132", "117.0.5938.62", 
            "118.0.5993.117", "118.0.5993.90", "118.0.5993.88", "119.0.6045.160", 
            "119.0.6045.123", "119.0.6045.105", "120.0.6099.224", "120.0.6099.110", 
            "120.0.6099.72", "121.0.6167.184", "121.0.6167.139", "121.0.6167.85", 
            "122.0.6261.174", "122.0.6261.128", "122.0.6261.111", "122.0.6261.95", 
            "123.0.6312.122", "123.0.6312.106", "123.0.6312.87", "123.0.6312.86", 
            "124.0.6367.207", "124.0.6367.112", "124.0.6367.91", "125.0.6422.113", 
            "125.0.6422.112", "125.0.6422.76", "125.0.6422.60", "126.0.6478.127", 
            "126.0.6478.93", "126.0.6478.61", "126.0.6478.57", "127.0.6533.112", 
            "127.0.6533.77"
        ]

        # Set up variables
        self.drop_fail_count = 0
        self.drop_fail_count_lock = asyncio.Lock()
        self.token_headers = {}
        self.user_ids = {}
        self.tokens = []

        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.background_tasks = set()
        self.input_task = None
        self.loop = None
        self.shutting_down = False

    def check_config(self):
        try:
            if not all([
                all(id.isdigit() for id in self.COMMAND_USER_IDS),
                (self.COMMAND_CHANNEL_IDS == [] or all(id.isdigit() for id in self.COMMAND_CHANNEL_IDS)),
                all(id.isdigit() for id in self.DROP_CHANNEL_IDS),
                all(id.isdigit() for id in self.SERVER_ACTIVITY_DROP_CHANNEL_IDS)
            ]):
                input("⛔ Configuration Error ⛔\nPlease enter non-empty, numeric strings for the command user IDs (or leave empty), command channel IDs (or leave empty), and (server activity) drop channel IDs in config.py.")
                sys.exit()
        except (AttributeError, TypeError):
            input("⛔ Configuration Error ⛔\nPlease enter strings (not integers) for the command user IDs (or leave empty), command channel IDs (or leave empty), and (server activity) drop channel IDs in config.py.")
            sys.exit()
        if not all([
            # Script Settings
            isinstance(self.KARUTA_PREFIX, str),
            isinstance(self.SPECIAL_EVENT, bool),
            isinstance(self.SHUFFLE_ACCOUNTS, bool),
            isinstance(self.TIME_LIMIT_HOURS_MIN, (int, float)) and 0 <= self.TIME_LIMIT_HOURS_MIN < math.inf,
            isinstance(self.TIME_LIMIT_HOURS_MAX, (int, float)) and 0 <= self.TIME_LIMIT_HOURS_MAX < math.inf,
            isinstance(self.TERMINAL_VISIBILITY, int) and self.TERMINAL_VISIBILITY in (0, 1),
            isinstance(self.CHANNEL_SKIP_RATE, float) and (self.CHANNEL_SKIP_RATE >= 0.0 and self.CHANNEL_SKIP_RATE <= 1.0),
            isinstance(self.DROP_SKIP_RATE, float) and (self.DROP_SKIP_RATE >= 0.0 and self.DROP_SKIP_RATE <= 1.0),
            isinstance(self.RANDOM_COMMAND_RATE, float) and (self.RANDOM_COMMAND_RATE >= 0.0 and self.RANDOM_COMMAND_RATE <= 1.0),
            isinstance(self.RATE_LIMIT, int) and self.RATE_LIMIT >= 0,
            isinstance(self.DROP_FAIL_LIMIT, int) and (self.DROP_FAIL_LIMIT == -1 or self.DROP_FAIL_LIMIT >= 1),

            # CardCompanion Settings
            isinstance(self.ONLY_GRAB_POG_CARDS, bool),
            isinstance(self.SKIP_GRAB_NON_POG_CARD_RATE, float) and (self.SKIP_GRAB_NON_POG_CARD_RATE >= 0.0 and self.SKIP_GRAB_NON_POG_CARD_RATE <= 1.0),
            isinstance(self.GRAB_SERVER_POG_CARDS, bool),
            isinstance(self.ATTEMPT_EXTRA_POG_GRABS, bool),
            isinstance(self.ATTEMPT_BUY_EXTRA_GRABS, bool),
            isinstance(self.BURN_NON_POG_CARDS, bool),
            isinstance(self.FIGHT_FOR_POG_CARD, bool)
        ]):
            input("⛔ Configuration Error ⛔\nPlease enter valid values in config.py.")
            sys.exit()
        if self.TIME_LIMIT_HOURS_MIN > self.TIME_LIMIT_HOURS_MAX:
            input("⛔ Configuration Error ⛔\nPlease enter a maximum time limit greater than or equal to the minimum time limit in config.py.")
            sys.exit()

    def get_headers(self, token: str, channel_id: str):
        if token not in self.token_headers:
            fingerprint_random = random.Random(token)  # Seeded by token so each account keeps the same fingerprint across runs
            windows_version = "10.0"  # Windows 11 browsers also report Windows NT 10.0
            browser_version = fingerprint_random.choice(self.BROWSER_VERSIONS)
            build_number = fingerprint_random.choice([381653, 382032, 382201, 382355, 417521])  # Random Discord build version numbers
            super_properties = {
                "os": "Windows",
                "browser": "Chrome",
                "device": "",
                "system_locale": "en-US",
                "browser_user_agent": (
                    f"Mozilla/5.0 (Windows NT {windows_version}; Win64; x64) "
                    f"AppleWebKit/537.36 (KHTML, like Gecko) "
                    f"Chrome/{browser_version} Safari/537.36"  # Brave Browser - Windows 10/11 (Brave uses the same user agent as Chrome)
                ),
                "browser_version": browser_version,
                "os_version": windows_version.split(".")[0],  # Ex. 10.0 -> 10
                "referrer": "https://discord.com/channels/@me",
                "referring_domain": "discord.com",
                "referrer_current": "https://discord.com/channels/@me",
                "referring_domain_current": "discord.com",
                "release_channel": "stable",
                "client_build_number": build_number,
                "client_event_source": None
            }
            x_super_props = base64.b64encode(
                json.dumps(super_properties, separators = (',', ':')).encode()
            ).decode()

            self.token_headers[token] = {
                "Authorization": token,
                "Content-Type": "application/json",
                "User-Agent": super_properties["browser_user_agent"],
                "X-Super-Properties": x_super_props,
                "X-Discord-Locale": "en-US",
                "X-Debug-Options": "bugReporterEnabled",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://discord.com",
                "Referer": "https://discord.com/channels/@me"
            }
        return {
            **self.token_headers[token],
            "X-Context-Properties": base64.b64encode(json.dumps({
                "location": "Channel",
                "location_channel_id": channel_id,
                "location_channel_type": 0,  # Guild text channel
            }).encode()).decode()
        }

    async def get_user_id(self, token: str, channel_id: str):
        if token not in self.user_ids:
            headers = self.get_headers(token, channel_id)
            async with aiohttp.ClientSession() as session:
                async with session.get("https://discord.com/api/v10/users/@me", headers = headers) as resp:
                    if resp.status == 200:
                        self.user_ids[token] = (await resp.json()).get('id')
        return self.user_ids.get(token)

    async def get_retry_after(self, resp: aiohttp.ClientResponse):
        try:
            return min(float((await resp.json())['retry_after']), 10)  # Capped so a long rate limit cannot stall drops/grabs
        except (aiohttp.ContentTypeError, KeyError, TypeError, ValueError):
            return 1  # seconds

    async def count_drop_fail(self, account: int, action: str, reason: str, count: bool = True):
        print(f"❌ [Account #{account}] {action} failed" + (f" ({self.drop_fail_count + 1}/{self.DROP_FAIL_LIMIT})" if count and self.DROP_FAIL_LIMIT >= 1 else "") + f": {reason}")
        if count:
            async with self.drop_fail_count_lock:
                self.drop_fail_count += 1

    async def get_drop_message(self, token: str, account: int, channel_id: str, drop_command_id: str, secondary_special_event_check: bool):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=20"  # Room for chat/grab messages sent after the drop message
        headers = self.get_headers(token, channel_id)
        on_cooldown = False
        timeout = 30  # seconds
        start_time = time.monotonic()
        async with aiohttp.ClientSession() as session:
            while (time.monotonic() - start_time) < timeout:
                user_id = await self.get_user_id(token, channel_id)  # Retried each poll until the lookup succeeds
                async with session.get(url, headers = headers) as resp:
                    status = resp.status
                    if status == 200 and user_id:
                        messages = await resp.json()
                        for msg in messages:  # Newest to oldest
                            if int(msg.get('id')) <= int(drop_command_id):
                                break  # Older messages (e.g. stale cooldown messages) were sent before the drop command
                            reactions = msg.get('reactions', [])
                            if all([
                                msg.get('author', {}).get('id') == self.KARUTA_BOT_ID,
                                len(reactions) >= 3,
                                f"<@{user_id}> {self.KARUTA_DROP_MESSAGE}" in msg.get('content', ''),
                                self.KARUTA_EXPIRED_DROP_MESSAGE not in msg.get('content', '')
                            ]):
                                if secondary_special_event_check:
                                    print(f"✅ [Account #{account}] Retrieved drop message (watching special event).")
                                else:
                                    print(f"✅ [Account #{account}] Retrieved drop message.")
                                return msg
                            elif msg.get('author', {}).get('id') == self.KARUTA_BOT_ID and f"<@{user_id}>{self.KARUTA_DROP_COOLDOWN_MESSAGE}" in msg.get('content', ''):
                                on_cooldown = True
                        if on_cooldown:
                            print(f"ℹ️ [Account #{account}] Retrieve drop message failed: Drop is on cooldown.")
                            return None
                    elif status == 401:
                        await self.count_drop_fail(account, "Retrieve drop message", "Invalid token.", count = not secondary_special_event_check)
                        return None
                    elif status == 403:
                        await self.count_drop_fail(account, "Retrieve drop message", "Token banned or insufficient permissions.", count = not secondary_special_event_check)
                        return None
                await asyncio.sleep(random.uniform(0.5, 1))
            # The secondary check runs after a successful drop, so its failures do not count toward the drop fail limit
            await self.count_drop_fail(account, "Retrieve drop message", f"Timed out ({timeout}s).", count = not secondary_special_event_check)
            return None

    async def send_message(self, token: str, account: int, channel_id: str, content: str, rate_limited: int):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = self.get_headers(token, channel_id)
        payload = {
            "content": content,
            "tts": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers = headers, json = payload) as resp:
                status = resp.status
                if status == 200:
                    print(f"✅ [Account #{account}] Sent message '{content}'.")
                    return await resp.json()  # The sent message
                elif status == 401:
                    print(f"❌ [Account #{account}] Send message '{content}' failed: Invalid token.")
                elif status == 403:
                    print(f"❌ [Account #{account}] Send message '{content}' failed: Token banned or insufficient permissions.")
                elif status == 429 and rate_limited < self.RATE_LIMIT:
                    rate_limited += 1
                    retry_after = await self.get_retry_after(resp)
                    print(f"⚠️ [Account #{account}] Send message '{content}' failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    return await self.send_message(token, account, channel_id, content, rate_limited)
                else:
                    print(f"❌ [Account #{account}] Send message '{content}' failed: Error code {status}.")
                return None

    async def get_card_companion_pog_cards(self, token: str, account: int, channel_id: str, drop_message_id: str):
        if account == 0:
            account_string = "[Server Account]"
        else:
            account_string = f"[Account #{account}]"
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=20"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    card_companion_replied = False
                    for msg in reversed(messages):  # Oldest to newest
                        if int(msg.get('id')) <= int(drop_message_id):  # Ensure CardCompanion message was sent after the drop message
                            continue
                        content = msg.get('content', '')
                        author_id = msg.get('author', {}).get('id')
                        if author_id == self.KARUTA_BOT_ID and (self.KARUTA_ANY_DROP_MESSAGE_REGEX.search(content) or self.KARUTA_SERVER_ACTIVITY_DROP_MESSAGE in content):
                            break  # Any later CardCompanion messages belong to the next drop
                        if author_id != self.CARD_COMPANION_BOT_ID or (msg.get('message_reference') or {}).get('message_id', drop_message_id) != drop_message_id:
                            continue  # Not a CardCompanion message about this drop
                        card_companion_replied = True
                        if any(emoji_str in content for emoji_str in self.CARD_COMPANION_POG_EMOJIS):  # Check if message contains an emoji indicating a pog card
                            card_numbers = []
                            # Parse card numbers
                            for match in re.findall(r"<:(no_\d+):\d+>", content):
                                emoji_str = f":{match}:"
                                if emoji_str in self.CARD_COMPANION_POG_EMOJIS:
                                    card_numbers.append(int(match.split("_")[1]))
                            # Check if card numbers were successfully parsed
                            if card_numbers:
                                print(f"✅ {account_string} Identified CardCompanion pog card(s): {card_numbers}.")
                                return card_numbers
                            else:
                                print(f"❌ {account_string} Unable to parse pog card numbers from CardCompanion message.")
                                return None
                else:
                    print(f"❌ {account_string} Retrieve CardCompanion message failed: Error code {status}.")
                    return None
                # CardCompanion replies to every drop, so no reply means the pog cards are unknown (None) rather than none ([])
                if not card_companion_replied:
                    print(f"ℹ️ {account_string} CardCompanion message not found.")
                    return None
                return []

    async def add_reaction(self, token: str, account: int, channel_id: str, message_id: str, emoji: str, rate_limited: int):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers = headers) as resp:
                status = resp.status
                # Get channel name
                if channel_id in self.DROP_CHANNEL_IDS:
                    channel_name = f"Drop Channel #{self.DROP_CHANNEL_IDS.index(channel_id) + 1}"
                elif channel_id in self.SERVER_ACTIVITY_DROP_CHANNEL_IDS:
                    channel_name = f"Server Activity Drop Channel #{self.SERVER_ACTIVITY_DROP_CHANNEL_IDS.index(channel_id) + 1}"
                elif channel_id in self.COMMAND_CHANNEL_IDS:
                    channel_name = f"Command Channel #{self.COMMAND_CHANNEL_IDS.index(channel_id) + 1}"
                else:
                    channel_name = f"Channel {channel_id}"
                # Print result
                if emoji in self.CARD_EMOJIS:  # when grabbing cards
                    card_number = self.EMOJI_MAP.get(emoji)
                    # Get account string
                    if account == 0:  # Server token account
                        account_string = f"[Server Account]"
                    else:  # Either a ServerDropChecker grab or a regular DropScript grab
                        account_string = f"[Account #{account}]"
                    if status == 204:
                        print(f"✅ {account_string} Grabbed card {card_number} in {channel_name}.")
                    elif status == 401:
                        print(f"❌ {account_string} Grab card {card_number} in {channel_name} failed: Invalid token.")
                    elif status == 403:
                        print(f"❌ {account_string} Grab card {card_number} in {channel_name} failed: Token banned or insufficient permissions.")
                    elif status == 429 and rate_limited < self.RATE_LIMIT:
                        rate_limited += 1
                        retry_after = await self.get_retry_after(resp)
                        print(f"⚠️ {account_string} Grab card {card_number} in {channel_name} failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        await self.add_reaction(token, account, channel_id, message_id, emoji, rate_limited)
                    else:
                        print(f"❌ {account_string} Grab card {card_number} in {channel_name} failed: Error code {status}.")
                elif account == 0 and token in list(self.server_drop_checker.special_event_tokens_dict.values()):  # when reacting to server event emojis
                    if status == 204:
                        print(f"✅ [Special Event Account] Grabbed {emoji} in {channel_name}.")
                    elif status == 401:
                        print(f"❌ [Special Event Account] Grab {emoji} in {channel_name} failed: Invalid token.")
                    elif status == 403:
                        print(f"❌ [Special Event Account] Grab {emoji} in {channel_name} failed: Token banned or insufficient permissions.")
                    elif status == 429 and rate_limited < self.RATE_LIMIT:
                        rate_limited += 1
                        retry_after = await self.get_retry_after(resp)
                        print(f"⚠️ [Special Event Account] Grab {emoji} in {channel_name} failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        await self.add_reaction(token, account, channel_id, message_id, emoji, rate_limited)
                    else:
                        print(f"❌ [Special Event Account] Grab {emoji} in {channel_name} failed: Error code {status}.")
                elif channel_id in self.COMMAND_CHANNEL_IDS:  # when reacting using message commands
                    if status == 204:
                        print(f"✅ [Account #{account}] Reacted {emoji} in {channel_name}.")
                    elif status == 401:
                        print(f"❌ [Account #{account}] React {emoji} in {channel_name} failed: Invalid token.")
                    elif status == 403:
                        print(f"❌ [Account #{account}] React {emoji} in {channel_name} failed: Token banned or insufficient permissions.")
                    elif status == 429 and rate_limited < self.RATE_LIMIT:
                        rate_limited += 1
                        retry_after = await self.get_retry_after(resp)
                        print(f"⚠️ [Account #{account}] React {emoji} in {channel_name} failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        await self.add_reaction(token, account, channel_id, message_id, emoji, rate_limited)
                    else:
                        print(f"❌ [Account #{account}] React {emoji} in {channel_name} failed: Error code {status}.")

    async def get_karuta_message(self, token: str, account: int, channel_id: str, search_content: str, rate_limited: int, command_id: str | None = None):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
        headers = self.get_headers(token, channel_id)
        user_id = await self.get_user_id(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    for msg in messages:
                        referenced_message = msg.get('referenced_message') or {}  # null if the replied-to message was deleted
                        if all([
                            msg.get('author', {}).get('id') == self.KARUTA_BOT_ID,
                            user_id and user_id == referenced_message.get('author', {}).get('id'),  # Reply to this account
                            command_id is None or command_id == referenced_message.get('id')  # Reply to this exact command, if given
                        ]):
                            if search_content == self.KARUTA_CARD_TRANSFER_TITLE and msg.get('embeds') and self.KARUTA_CARD_TRANSFER_TITLE == msg['embeds'][0].get('title'):
                                print(f"✅ [Account #{account}] Retrieved card transfer message.")
                                return msg
                            elif search_content == self.KARUTA_MULTITRADE_LOCK_MESSAGE and self.KARUTA_MULTITRADE_LOCK_MESSAGE in msg.get('content', ''):
                                print(f"✅ [Account #{account}] Retrieved multitrade lock message.")
                                return msg
                            elif search_content == self.KARUTA_MULTITRADE_CONFIRM_MESSAGE and self.KARUTA_MULTITRADE_CONFIRM_MESSAGE in msg.get('content', ''):
                                print(f"✅ [Account #{account}] Retrieved multitrade confirm message.")
                                return msg
                            elif search_content == self.KARUTA_BURN_TITLE and msg.get('embeds') and self.KARUTA_BURN_TITLE == msg['embeds'][0].get('title'):
                                print(f"✅ [Account #{account}] Retrieved burn message.")
                                return msg
                            elif search_content == self.KARUTA_MULTIBURN_TITLE and msg.get('embeds') and self.KARUTA_MULTIBURN_TITLE == msg['embeds'][0].get('title'):
                                print(f"✅ [Account #{account}] Retrieved multiburn message.")
                                return msg
                            elif search_content == self.KARUTA_ITEM_PURCHASE_TITLE and msg.get('embeds') and self.KARUTA_ITEM_PURCHASE_TITLE == msg['embeds'][0].get('title'):
                                print(f"✅ [Account #{account}] Retrieved item purchase message.")
                                return msg
                elif status == 429 and rate_limited < self.RATE_LIMIT:
                    rate_limited += 1
                    retry_after = await self.get_retry_after(resp)
                    print(f"⚠️ [Account #{account}] Retrieve message failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    return await self.get_karuta_message(token, account, channel_id, search_content, rate_limited, command_id)
                else:
                    print(f"❌ [Account #{account}] Retrieve message failed: Error code {status}.")
                    return None
                print(f"❌ [Account #{account}] Retrieve message failed: Message '{search_content}' not found in recent messages.")
                return None

    async def get_server_id(self, token: str, account: int, channel_id: str):
        url = f"https://discord.com/api/v10/channels/{channel_id}"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status != 200:
                    print(f"❌ [Account #{account}] Retrieve Guild ID failed: Error code {status}.")
                    return None
                data = await resp.json()
                return data.get("guild_id")

    async def get_payload(self, token: str, account: int, channel_id: str, button_string: str, message: dict):
        button_bot_id = message.get('author', {}).get('id')
        components = message.get('components', [])
        for action_row in components:
            for button in action_row.get('components', []):
                button_emoji = button.get('emoji', {}).get('name') or ''
                button_label = button.get('label', '')
                if button_string in button_emoji + button_label:
                    custom_id = button.get('custom_id', '')
                    command_server_id = await self.get_server_id(token, account, channel_id)
                    # Simulate button click via interaction callback
                    payload = {
                        "type": 3,  # Component interaction
                        "nonce": str(uuid.uuid4().int >> 64),  # Unique interaction ID
                        "guild_id": command_server_id,
                        "channel_id": channel_id,
                        "message_flags": 0,
                        "message_id": message.get('id', ''),
                        "application_id": button_bot_id,
                        "session_id": str(uuid.uuid4()),
                        "data": {
                            "component_type": 2,
                            "custom_id": custom_id
                        }
                    }
                    print(f"✅ [Account #{account}] Found {button_string} button successfully.")
                    return payload
        return None

    async def get_grabbed_card_code(self, token: str, account: int, channel_id: str, drop_message_id: str):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
        headers = self.get_headers(token, channel_id)
        user_id = await self.get_user_id(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status != 200:
                    print(f"❌ [Account #{account}] Retrieve grab message failed: Error code {status}.")
                    return None
                for msg in reversed(await resp.json()):  # Oldest to newest, so a grab from a later drop is never picked
                    if msg.get('author', {}).get('id') == self.KARUTA_BOT_ID and int(msg.get('id')) > int(drop_message_id):
                        # Ex. "<@user> took the **X** card `code`!" or "<@user> fought off 7 others and took the **X** card `code`!"
                        match = re.match(rf"<@{user_id}> (?:fought off .+? and )?took the \*\*.+?\*\* card `(\w+)`", msg.get('content', ''))
                        if match:
                            return match.group(1)
                return None

    async def burn_non_pog_cards(self, tokens_to_burn: list[str], channel_id: str, drop_message_id: str):
        for token in tokens_to_burn:
            account = self.tokens.index(token) + 1
            await asyncio.sleep(random.uniform(5, 90))  # Random delay between accounts burning. Note that this function is ran asynchronously, so long delays should be fine
            await self.pause_event.wait()  # Check if need to pause
            card_code = await self.get_grabbed_card_code(token, account, channel_id, drop_message_id)
            if not card_code:  # Never burn without a code, or else the account's latest card (possibly a pog card) would be burned
                print(f"ℹ️ [Account #{account}] Grab not confirmed; skipping burn.")
                continue
            burn_command = await self.send_message(token, account, channel_id, f"{random.choice(self.BURN_COMMANDS)} {card_code}", 0)
            if not burn_command:  # Never confirm a burn prompt for a different card
                continue
            await asyncio.sleep(random.uniform(5, 8))  # Wait for Karuta burn message
            await self.pause_event.wait()  # Check if need to pause
            burn_message = await self.get_karuta_message(token, account, channel_id, self.KARUTA_BURN_TITLE, 0, burn_command['id'])
            if burn_message:
                payload = await self.get_payload(token, account, channel_id, '🔥', burn_message)
                if payload is not None:
                    async with aiohttp.ClientSession() as session:
                        headers = self.get_headers(token, channel_id)
                        async with session.post("https://discord.com/api/v10/interactions", headers = headers, json = payload) as resp:
                            status = resp.status
                            if status == 204:
                                print(f"✅ [Account #{account}] Card burned successfully.")
                            else:
                                print(f"❌ [Account #{account}] Card burn failed: Error code {status}.")
                else:
                    print(f"❌ [Account #{account}] Card burn failed: 🔥 button not found.")

    async def attempt_buy_extra_grabs(self, token: str, account: int, channel_id: str, num_pog_cards: int):
        num_extra_grabs_purchased = num_pog_cards - 1
        buy_command = await self.send_message(token, account, channel_id, self.BUY_EXTRA_GRAB_COMMAND + f" {num_extra_grabs_purchased}", 0)  # Note that num_pog_cards > 1, so -1 is safe
        if not buy_command:  # Never confirm a purchase prompt for a different item
            return
        await asyncio.sleep(random.uniform(5, 8))  # Wait for Karuta item purchase message
        await self.pause_event.wait()  # Check if need to pause
        extra_grab_purchase_message = await self.get_karuta_message(token, account, channel_id, self.KARUTA_ITEM_PURCHASE_TITLE, 0, buy_command['id'])
        if extra_grab_purchase_message:
            payload = await self.get_payload(token, account, channel_id, '✅', extra_grab_purchase_message)
            if payload is not None:
                async with aiohttp.ClientSession() as session:
                    headers = self.get_headers(token, channel_id)
                    async with session.post("https://discord.com/api/v10/interactions", headers = headers, json = payload) as resp:
                        status = resp.status
                        if status == 204:
                            print(f"✅ [Account #{account}] Purchased {num_extra_grabs_purchased} extra grabs successfully.")
                        else:
                            print(f"❌ [Account #{account}] Extra grab purchase failed: Error code {status}.")
            else:
                print(f"❌ [Account #{account}] Extra grab purchase failed: ✅ button not found.")

    async def drop_and_grab(self, token: str, account: int, channel_id: str, channel_tokens: list[str]):
        num_channel_tokens = len(channel_tokens)
        drop_message = random.choice(self.DROP_COMMANDS) + random.choice(self.RANDOM_ADDON)
        drop_command = await self.send_message(token, account, channel_id, drop_message, 0)
        if drop_command:
            drop_message = await self.get_drop_message(token, account, channel_id, drop_command['id'], secondary_special_event_check = False)
            if drop_message:
                drop_message_id = drop_message.get('id')
                # Note that there is no need to wait for the CardCompanion message because get_drop_message() only returns after all Karuta emojis have been added, by which time CardCompanion should have already identified the drop
                pog_cards = await self.get_card_companion_pog_cards(token, account, channel_id, drop_message_id) # Get all pog card numbers as a list (containing 1, 2, and/or 3, or empty), or None if unknown
                if pog_cards and max(pog_cards) > len(self.EMOJIS):
                    pog_cards = None  # Script drops only have 3 cards, so this CardCompanion message belongs to another drop
                pog_cards_known = pog_cards is not None
                pog_cards = pog_cards or []
                if pog_cards:
                    if self.FIGHT_FOR_POG_CARD and len(pog_cards) == 1:
                        # If fighting for a pog card,
                        # self.ATTEMPT_EXTRA_POG_GRABS is not a factor because fights only happen with one pog card
                        # self.ONLY_GRAB_POG_CARDS is also not a factor because fighting has a higher priority than grabbing non-pog cards
                        num_fighters = random.choice((1, 2))  # 50% chance for 1 or 2 other accounts in the channel to fight
                        pog_card_index = pog_cards[0] - 1
                        pog_card_emoji = self.EMOJIS[pog_card_index]
                        other_channel_tokens = channel_tokens.copy()
                        other_channel_tokens.remove(token)
                        random.shuffle(other_channel_tokens)

                        async def fight(grab_token: str):
                            grab_account = self.tokens.index(grab_token) + 1
                            await asyncio.sleep(random.uniform(0.2, 0.6))  # Assume 0 second grace period (total 1 second to grab, including request latency)
                            await self.add_reaction(grab_token, grab_account, channel_id, drop_message_id, pog_card_emoji, 0)

                        await self.add_reaction(token, account, channel_id, drop_message_id, pog_card_emoji, 0)
                        await asyncio.gather(*(fight(grab_token) for grab_token in other_channel_tokens[:num_fighters]))  # Fighters grab concurrently so request latencies do not stack
                        await asyncio.sleep(random.uniform(0.5, 3.5))

                    else:
                        # If not fighting for a pog card
                        if self.ATTEMPT_EXTRA_POG_GRABS:
                            # If self.ATTEMPT_EXTRA_POG_GRABS = True, the dropper should attempt to grab all the pog card(s)
                            for pog_card in pog_cards:
                                pog_card_index = pog_card - 1
                                pog_card_emoji = self.EMOJIS[pog_card_index]
                                await self.add_reaction(token, account, channel_id, drop_message_id, pog_card_emoji, 0)
                                await asyncio.sleep(random.uniform(0.5, 2))
                        else:
                            # If self.ATTEMPT_EXTRA_POG_GRABS = False, the dropper should only grab the first pog card
                            first_pog_card_index = pog_cards[0] - 1
                            first_pog_card_emoji = self.EMOJIS[first_pog_card_index]
                            await self.add_reaction(token, account, channel_id, drop_message_id, first_pog_card_emoji, 0)
                            await asyncio.sleep(random.uniform(0.5, 3.5))

                        if self.ONLY_GRAB_POG_CARDS:
                            # If self.ONLY_GRAB_POG_CARDS = True, the non-droppers will grab the pog cards excluding the first one (if any)
                            # This way, pog cards will always be grabbed, even if the dropper did not have enough extra grabs
                            other_pog_cards = pog_cards.copy()
                            other_pog_cards.pop(0)
                            random.shuffle(other_pog_cards)
                            other_channel_tokens = channel_tokens.copy()
                            other_channel_tokens.remove(token)
                            random.shuffle(other_channel_tokens)
                            for pog_card, grab_token in zip(other_pog_cards, other_channel_tokens):
                                emoji = self.EMOJIS[pog_card - 1]
                                grab_account = self.tokens.index(grab_token) + 1
                                await self.add_reaction(grab_token, grab_account, channel_id, drop_message_id, emoji, 0)
                                await asyncio.sleep(random.uniform(0.5, 3.5))
                        else:
                            # If self.ONLY_GRAB_POG_CARDS = False, the non-droppers will grab the other (2) cards in the drop
                            first_pog_card_index = pog_cards[0] - 1
                            first_pog_card_emoji = self.EMOJIS[first_pog_card_index]
                            other_channel_tokens = channel_tokens.copy()
                            other_channel_tokens.remove(token)
                            random.shuffle(other_channel_tokens)
                            other_emojis = self.EMOJIS.copy()
                            other_emojis.remove(first_pog_card_emoji)
                            other_emojis = sorted(other_emojis, key = lambda emoji: self.EMOJIS.index(emoji) + 1 not in pog_cards)[:len(other_channel_tokens)]  # Prioritize pog cards if there are fewer accounts than cards
                            random.shuffle(other_emojis)
                            tokens_to_burn = []
                            num_other_channel_tokens = len(other_channel_tokens)
                            for i in range(num_other_channel_tokens):
                                emoji = other_emojis[i]
                                grab_token = other_channel_tokens[i]
                                grab_account = self.tokens.index(grab_token) + 1
                                card_number = self.EMOJIS.index(emoji) + 1
                                if random.random() < self.SKIP_GRAB_NON_POG_CARD_RATE and card_number not in pog_cards:
                                    card_string = self.EMOJI_MAP.get(emoji)
                                    print(f"ℹ️ [Account #{grab_account}] Skipped grab for card {card_string}.")
                                    continue  # Skip grab
                                if self.BURN_NON_POG_CARDS and card_number not in pog_cards:
                                    tokens_to_burn.append(grab_token)
                                await self.add_reaction(grab_token, grab_account, channel_id, drop_message_id, emoji, 0)
                                await asyncio.sleep(random.uniform(0.5, 3.5))
                            if self.BURN_NON_POG_CARDS and tokens_to_burn:
                                self.create_background_task(self.burn_non_pog_cards(tokens_to_burn, channel_id, drop_message_id))

                else:
                    # If there are no pog cards and grabbing all cards, 
                    # All three accounts will grab one card each, as per usual
                    # Note that self.ATTEMPT_EXTRA_POG_GRABS is not a factor here because there are no pog cards in the drop
                    if not self.ONLY_GRAB_POG_CARDS:
                        shuffled_emojis = self.EMOJIS.copy()
                        random.shuffle(shuffled_emojis)
                        shuffled_channel_tokens = channel_tokens.copy()
                        random.shuffle(shuffled_channel_tokens)
                        tokens_to_burn = []
                        for i in range(num_channel_tokens):
                            emoji = shuffled_emojis[i]
                            grab_token = shuffled_channel_tokens[i]
                            grab_account = self.tokens.index(grab_token) + 1
                            card_number = self.EMOJIS.index(emoji) + 1
                            if random.random() < self.SKIP_GRAB_NON_POG_CARD_RATE and card_number not in pog_cards:
                                card_string = self.EMOJI_MAP.get(emoji)
                                print(f"ℹ️ [Account #{grab_account}] Skipped grab for card {card_string}.")
                                continue  # Skip grab
                            if self.BURN_NON_POG_CARDS and card_number not in pog_cards:
                                tokens_to_burn.append(grab_token)
                            await self.add_reaction(grab_token, grab_account, channel_id, drop_message_id, emoji, 0)
                            await asyncio.sleep(random.uniform(0.5, 3.5))
                        if self.BURN_NON_POG_CARDS and tokens_to_burn and pog_cards_known:  # Unknown pog cards may have been grabbed
                            self.create_background_task(self.burn_non_pog_cards(tokens_to_burn, channel_id, drop_message_id))

                await self.pause_event.wait()  # Check if need to pause

                # Grab special event emoji on special event account
                if self.SPECIAL_EVENT:
                    if self.ONLY_GRAB_POG_CARDS:  # Extra delay is only necessary if no cards were grabbed (if self.ONLY_GRAB_POG_CARDS = True)
                        await asyncio.sleep(4)  # Extra delay to wait for special event emojis
                    drop_message = await self.get_drop_message(token, account, channel_id, drop_command['id'], secondary_special_event_check = True)
                    if drop_message and len(drop_message.get('reactions', [])) > 3:  # 3 cards + special event emoji(s)
                        await self.server_drop_checker.add_special_event_reactions(channel_id, drop_message)

                # If only grabbing pog cards, then only the dropper will ever be active
                # Hence, non-droppers should never send random messages in the channel; only the dropper will
                if self.ONLY_GRAB_POG_CARDS:
                    if random.choice([True, True, True, False]):  # 75% chance of sending random commands/messages
                        for _ in range(random.randint(1, 3)):
                            random_msg_list = random.choice([self.RANDOM_COMMANDS, self.RANDOM_MESSAGES])
                            random_msg = random.choice(random_msg_list)
                            await self.send_message(token, account, channel_id, random_msg, self.RATE_LIMIT)
                            await asyncio.sleep(random.uniform(1, 4))
                else:
                    # If grabbing all cards, then all accounts in the channel are active, so all accounts should send random messages
                    shuffled_channel_tokens = channel_tokens.copy()
                    random.shuffle(shuffled_channel_tokens)
                    for i in range(num_channel_tokens):
                        if random.choice([True, False]):  # 50% chance of sending random commands/messages
                            msg_token = shuffled_channel_tokens[i]
                            msg_account = self.tokens.index(msg_token) + 1
                            for _ in range(random.randint(1, 3)):
                                random_msg_list = random.choice([self.RANDOM_COMMANDS, self.RANDOM_MESSAGES])
                                random_msg = random.choice(random_msg_list)
                                await self.send_message(msg_token, msg_account, channel_id, random_msg, self.RATE_LIMIT)
                                await asyncio.sleep(random.uniform(1, 4))

                await self.pause_event.wait()  # Check if need to pause

                # Dropper may attempt to buy extra grabs after using extra grabs
                num_pog_cards = len(pog_cards)
                if self.ATTEMPT_BUY_EXTRA_GRABS and self.ATTEMPT_EXTRA_POG_GRABS and num_pog_cards > 1:
                    await self.attempt_buy_extra_grabs(token, account, channel_id, num_pog_cards)

        else:
            await self.count_drop_fail(account, "Drop", "Drop command could not be sent.")

    async def reset_drop_fail_count(self):
        if self.DROP_FAIL_LIMIT >= 1 and self.drop_fail_count >= self.DROP_FAIL_LIMIT:
            async with self.drop_fail_count_lock:
                self.drop_fail_count = 0
            print("ℹ️ Reset drop fail count. Resuming drops...")

    async def async_input_handler(self, prompt: str, target_command: str, flag: str):
        while True:
            if self.pause_event.is_set():
                self.pause_event.clear()  # Pause drops, but not commands
            if self.input_task is None or self.input_task.done():
                self.input_task = asyncio.create_task(asyncio.to_thread(input, prompt))
            else:
                print(prompt, end = "")  # Reuse the input() still waiting from an earlier prompt (it cannot be cancelled)
            if flag == self.DROP_FAIL_LIMIT_REACHED_FLAG:
                resume_task = asyncio.create_task(self.pause_event.wait())
                await asyncio.wait([self.input_task, resume_task], return_when = asyncio.FIRST_COMPLETED)
                resume_task.cancel()
                if not self.input_task.done():
                    break  # Resumed by `cmd /resume`
            command = await self.input_task
            if command == target_command:  # Resume if target command is inputted
                if flag == self.DROP_FAIL_LIMIT_REACHED_FLAG:
                    await self.reset_drop_fail_count()
                elif flag == self.EXECUTION_COMPLETED_FLAG:
                    ctypes.windll.shell32.ShellExecuteW(
                        None, None, sys.executable, subprocess.list2cmdline(sys.argv + [self.RELAUNCH_FLAG]), None, self.TERMINAL_VISIBILITY
                    )
                    sys.exit()
                self.pause_event.set()
                break  # Continue the script

    async def run_instance(self, channel_num: int, channel_id: str, start_delay: int, channel_tokens: list[str], time_limit_seconds: int):
        try:
            num_accounts = len(channel_tokens)
            delay = 30 * 60 / num_accounts  # 10 min delay per account (if 3 accounts per channel)
            # Breaking up start delay into multiple steps to check if need to pause
            random_start_delay_per_step = random.uniform(2, 3)
            num_start_delay_steps = round(start_delay / random_start_delay_per_step)
            for _ in range(num_start_delay_steps):
                await self.pause_event.wait()  # Check if need to pause
                await asyncio.sleep(random_start_delay_per_step)
            start_time = time.monotonic()
            while True:
                for token in channel_tokens:
                    await self.pause_event.wait()  # Check if need to pause
                    print(f"\nChannel #{channel_num} - {datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")
                    if time.monotonic() - start_time >= time_limit_seconds:  # Time limit for automatic shutoff
                        print(f"ℹ️ Channel #{channel_num} has reached the time limit of {(time_limit_seconds / 60 / 60):.1f} hours. Stopping drops in channel...")
                        await self.send_message(token, self.tokens.index(token) + 1, channel_id, random.choice(self.TIME_LIMIT_EXCEEDED_MESSAGES), 0)
                        return
                    try:
                        if random.random() < self.DROP_SKIP_RATE:
                            print(f"ℹ️ [Account #{self.tokens.index(token) + 1}] Skipped drop.")
                        else:
                            await self.drop_and_grab(token, self.tokens.index(token) + 1, channel_id, channel_tokens.copy())
                        await self.pause_event.wait()  # Check if need to pause
                        if self.DROP_FAIL_LIMIT >= 1 and self.drop_fail_count >= self.DROP_FAIL_LIMIT:  # If FAIL_LIMIT == -1 (or any neg num), never pause
                            self.pause_event.clear()  # Pause all channels before awaiting, so only this channel handles the limit
                            if self.COMMAND_CHANNEL_IDS:
                                await self.send_message(token, self.tokens.index(token) + 1, self.COMMAND_CHANNEL_IDS[0], "⚠️ Drop fail limit reached", 0)
                            if self.TERMINAL_VISIBILITY:
                                await self.async_input_handler(f"\n⚠️ Drop Fail Limit Reached ⚠️\nThe script has failed to retrieve {self.DROP_FAIL_LIMIT} total drops. Automatically pausing drops...\nPress `Enter` if you wish to resume.\n",
                                                                                "", self.DROP_FAIL_LIMIT_REACHED_FLAG)
                            elif not self.COMMAND_CHANNEL_IDS:  # Drops could never be resumed
                                print(f"\n⛔ Drop Fail Limit Reached ⛔\nThe script has failed to retrieve {self.DROP_FAIL_LIMIT} total drops. Stopping script...")
                                sys.exit()
                    except Exception as e:  # Keep the channel running after errors such as dropped connections
                        print(f"\n❌ Error in Channel #{channel_num} Drop ❌\n{e}")
                    # Breaking up delay into multiple steps to check if need to pause
                    random_delay = delay + random.uniform(0.5 * 60, 10 * 60)  # Wait an additional 0.5-10 minutes per drop
                    random_delay_per_step = random.uniform(2, 3)
                    num_delay_steps = round(random_delay / random_delay_per_step)
                    for _ in range(num_delay_steps):
                        await self.pause_event.wait()  # Check if need to pause
                        await asyncio.sleep(random_delay_per_step)
                        if random.random() < self.RANDOM_COMMAND_RATE:
                            with contextlib.suppress(aiohttp.ClientError, asyncio.TimeoutError):  # Random commands are optional
                                await self.send_message(token, self.tokens.index(token) + 1, channel_id, random.choice(self.RANDOM_COMMANDS), 0)
        except Exception as e:
            print(f"\n❌ Error in Channel #{channel_num} Script Instance ❌\n{e}")

    def create_background_task(self, coro):
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)  # Keep a reference so the task is not garbage collected mid-execution
        task.add_done_callback(self.on_background_task_done)
        return task

    def on_background_task_done(self, task: asyncio.Task):
        self.background_tasks.discard(task)
        if not task.cancelled() and task.exception():
            print(f"\n❌ Background Task Error ❌\n{task.exception()}")

    async def run_command_checkers(self):
        if self.COMMAND_CHANNEL_IDS:
            for channel_id in self.COMMAND_CHANNEL_IDS:
                command_checker = CommandChecker(
                    main = self,
                    tokens = self.tokens,
                    command_user_ids = self.COMMAND_USER_IDS,
                    command_channel_id = channel_id,
                    karuta_prefix = self.KARUTA_PREFIX,
                    karuta_bot_id = self.KARUTA_BOT_ID,
                    rate_limit = self.RATE_LIMIT
                )
                self.create_background_task(command_checker.run_command_checker())
            print(f"\n🤖 Message commands are enabled in {len(self.COMMAND_CHANNEL_IDS)} channel(s).")
        else:
            print("\n🤖 Message commands are disabled.")

    async def set_token_dictionaries(self):
        self.token_channel_dict = {}
        tokens = self.shuffled_tokens if self.shuffled_tokens else self.tokens
        for index, token in enumerate(tokens):
            self.token_channel_dict[token] = self.DROP_CHANNEL_IDS[math.floor(index / 3)]  # Max 3 accounts per channel
        self.channel_token_dict = defaultdict(list)
        for k, v in self.token_channel_dict.items():
            self.channel_token_dict[v].append(k)

    async def run_script(self):
        self.loop = asyncio.get_running_loop()  # Used by console_ctrl_handler, which runs on another thread
        if self.SHUFFLE_ACCOUNTS:
            self.shuffled_tokens = random.sample(self.tokens, len(self.tokens))
        else:
            self.shuffled_tokens = None

        await self.run_command_checkers()  # if any
        await self.set_token_dictionaries()

        if self.SPECIAL_EVENT or self.GRAB_SERVER_POG_CARDS:
            self.server_drop_checker = ServerDropChecker(main = self)

        if self.ONLY_GRAB_POG_CARDS:
            print("\n❗ Only pog cards (as defined by CardCompanion) will be grabbed.")
        else:
            print("\nℹ️ All dropped cards will be grabbed, regardless of whether it is a pog card (as defined by CardCompanion).")

        task_instances = []
        num_channels = len(self.DROP_CHANNEL_IDS)
        start_delay_multipliers = random.sample(range(num_channels), num_channels)
        for index, channel_id in enumerate(self.DROP_CHANNEL_IDS):
            channel_num = index + 1
            if random.random() < self.CHANNEL_SKIP_RATE:
                print(f"\nℹ️ Channel #{channel_num} will be skipped.")
            else:
                channel_tokens = self.channel_token_dict[channel_id]
                start_delay_seconds = start_delay_multipliers[0] * 210 + random.uniform(5, 60)  # Randomly stagger start times
                start_delay_multipliers.pop(0)
                channel_time_limit_seconds = round(random.uniform(self.TIME_LIMIT_HOURS_MIN * 60 * 60, self.TIME_LIMIT_HOURS_MAX * 60 * 60))  # Random time limit in seconds
                target_time = datetime.now() + timedelta(seconds = start_delay_seconds) + timedelta(seconds = channel_time_limit_seconds)
                start_time = datetime.now() + timedelta(seconds = start_delay_seconds)
                print(f"\nℹ️ Channel #{channel_num} will run for {(channel_time_limit_seconds / 60 / 60):.1f} hrs (until {target_time.strftime('%I:%M %p').lstrip('0')}) " +
                        f"starting in {round(start_delay_seconds)}s ({start_time.strftime('%I:%M:%S %p').lstrip('0')}):")
                for token in channel_tokens:
                    print(f"  - Account #{self.tokens.index(token) + 1}")
                task_instances.append(asyncio.create_task(self.run_instance(channel_num, channel_id, start_delay_seconds, channel_tokens.copy(), channel_time_limit_seconds)))
        await asyncio.sleep(3)  # Short delay to show user the account/channel information
        if not self.TERMINAL_VISIBILITY:
            win32gui.ShowWindow(win32console.GetConsoleWindow(), win32con.SW_HIDE)  # Hidden only after startup, so any startup prompts are visible
        if self.COMMAND_CHANNEL_IDS:
            random_token = random.choice(self.tokens)
            print(f"\n{datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")
            await self.send_message(random_token, self.tokens.index(random_token) + 1, self.COMMAND_CHANNEL_IDS[0], "Execution started", 0)
        await asyncio.gather(*task_instances)
        await asyncio.sleep(1)
        if self.COMMAND_CHANNEL_IDS:
            random_token = random.choice(self.tokens)
            await self.send_message(random_token, self.tokens.index(random_token) + 1, self.COMMAND_CHANNEL_IDS[0], "Execution completed", 0)
        if self.TERMINAL_VISIBILITY:
            print(f"\n{datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")
            await self.async_input_handler(f"✅ Script Execution Completed ✅\nClose the terminal to exit, or press `Enter` to restart the script.\n", "", self.EXECUTION_COMPLETED_FLAG)

    async def cleanup(self):
        random_token = random.choice(self.tokens)
        await self.send_message(random_token, self.tokens.index(random_token) + 1, self.COMMAND_CHANNEL_IDS[0], "Shutting down...", 0)

    def console_ctrl_handler(self, ctrl_type: int):
        # Closing the terminal window sends CTRL_CLOSE_EVENT instead of a signal, and Windows ends the process ~5 seconds later
        if ctrl_type != win32con.CTRL_CLOSE_EVENT:
            return False  # Let Ctrl+C reach signal_handler
        print("\n✅ Terminal window closed. Running cleanup...")
        cleanup = asyncio.wait_for(self.cleanup(), timeout = 4)
        try:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(cleanup, self.loop).result()
            else:
                asyncio.run(cleanup)
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
        return True

    def signal_handler(self, signum, frame):
        if self.shutting_down:
            sys.exit()  # Repeated signal: exit without waiting for cleanup
        self.shutting_down = True
        print("\n✅ Exit signal received. Running cleanup...")
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self.cleanup())
            task.add_done_callback(lambda _: sys.exit())
        except RuntimeError:
            # No running loop, so create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.cleanup())
            loop.close()
            sys.exit()

if __name__ == "__main__":
    bot = DropScript()
    if bot.RELAUNCH_FLAG not in sys.argv:
        ctypes.windll.shell32.ShellExecuteW(
            None, None, sys.executable, subprocess.list2cmdline(sys.argv + [bot.RELAUNCH_FLAG]), None, 1  # Always visible at startup; run_script() hides it if TERMINAL_VISIBILITY = 0
        )
        sys.exit()
    bot.check_config()
    bot.tokens = TokenExtractor().main(standalone = False, num_channels = len(bot.DROP_CHANNEL_IDS))
    if len(set(bot.tokens)) != len(bot.tokens):
        input("⛔ Configuration Error ⛔\nThe same account was entered more than once. Please remove the duplicate token(s)/account(s).")
        sys.exit()
    
    # Set up handlers to send a message on exit or terminal window closure
    if bot.COMMAND_CHANNEL_IDS:
        signal.signal(signal.SIGTERM, bot.signal_handler)
        signal.signal(signal.SIGINT, bot.signal_handler)
        win32api.SetConsoleCtrlHandler(bot.console_ctrl_handler, True)
    
    asyncio.run(bot.run_script())