from special_event_grabber import SpecialEventGrabber
from command_checker import CommandChecker
from token_extractor import TokenExtractor
from config import Config
from datetime import datetime, timedelta
from collections import defaultdict
import win32console
import win32con
import win32gui
import random
import asyncio
import aiohttp
import base64
import ctypes
import signal
import math
import time
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
        self.KARUTA_SERVER_ACTIVITY_DROP_MESSAGE = "I'm dropping 3 cards since this server is currently active!"
        self.KARUTA_EXPIRED_DROP_MESSAGE = "This drop has expired and the cards can no longer be grabbed."
        self.KARUTA_DROP_COOLDOWN_MESSAGE = ", you must wait"

        self.KARUTA_CARD_TRANSFER_TITLE = "Card Transfer"

        self.KARUTA_MULTITRADE_LOCK_MESSAGE = "Both sides must lock in before proceeding to the next step."
        self.KARUTA_MULTITRADE_CONFIRM_MESSAGE = "This trade has been locked."

        self.KARUTA_MULTIBURN_TITLE = "Burn Cards"

        self.CARD_COMPANION_BOT_ID = "1380936713639166082"
        self.CARD_COMPANION_POG_EMOJIS = [":no_1:", ":no_2:", ":no_3:"]

        self.EMOJIS = ['1️⃣', '2️⃣', '3️⃣']
        self.EMOJI_MAP = {
            '1️⃣': '[1]',
            '2️⃣': '[2]',
            '3️⃣': '[3]'
        } # Use card number instead of emoji in terminal output for better readability

        self.RANDOM_ADDON = ['', ' ', ' !', ' :D', ' w']
        self.DROP_MESSAGES = [f"{self.KARUTA_PREFIX}drop", f"{self.KARUTA_PREFIX}d"]
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
            "how tf u keep dropping bangers", "wait i missed it BRUH", "i got scammed in trade lol"
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

        self.DROP_FAIL_LIMIT_REACHED_FLAG = "Drop Fail Limit Reached"
        self.EXECUTION_COMPLETED_FLAG = "Execution Completed"

        self.WINDOWS_VERSIONS = ["10.0", "11.0"]
        self.BROWSER_VERSIONS = [
            "114.0.5735.198", "115.0.5790.170", "115.0.5790.114", "116.0.5845.111", 
            "116.0.5845.97", "117.0.5938.149", "117.0.5938.132", "117.0.5938.62", 
            "118.0.5993.117", "118.0.5993.90", "118.0.5993.88", "119.0.6045.160", 
            "119.0.6045.123", "119.0.6045.105", "120.0.6099.224", "120.0.6099.110", 
            "120.0.6099.72", "121.0.6167.184", "121.0.6167.139", "121.0.6167.85", 
            "122.0.6261.174", "122.0.6261.128", "122.0.6261.111", "122.0.6261.95", 
            "123.0.6312.122", "123.0.6312.106", "123.0.6312.87", "123.0.6312.86", 
            "124.0.6367.207", "124.0.6367.112", "124.0.6367.91", "124.0.6367.91", 
            "125.0.6422.113", "125.0.6422.112", "125.0.6422.76", "125.0.6422.60", 
            "126.0.6478.127", "126.0.6478.93", "126.0.6478.61", "126.0.6478.57", 
            "127.0.6533.112", "127.0.6533.77"
        ]

        # Set up variables
        self.drop_fail_count = 0
        self.drop_fail_count_lock = asyncio.Lock()
        self.token_headers = {}
        self.tokens = []
        self.executed_commands = []
        self.card_transfer_messages = []
        self.multitrade_messages = []
        self.multiburn_initial_messages = []
        self.multiburn_fire_messages = []

        self.pause_event = asyncio.Event()
        self.pause_event.set()

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
        except AttributeError:
            input("⛔ Configuration Error ⛔\nPlease enter strings (not integers) for the command user IDs (or leave empty), command channel IDs (or leave empty), and (server activity) drop channel IDs in config.py.")
            sys.exit()
        if not all([
            isinstance(self.TERMINAL_VISIBILITY, int),
            isinstance(self.KARUTA_PREFIX, str),
            isinstance(self.SHUFFLE_ACCOUNTS, bool),
            isinstance(self.RATE_LIMIT, int),
            isinstance(self.DROP_FAIL_LIMIT, int),
            isinstance(self.TIME_LIMIT_HOURS_MIN, (int, float)),
            isinstance(self.TIME_LIMIT_HOURS_MAX, (int, float)),
            isinstance(self.CHANNEL_SKIP_RATE, int),
            isinstance(self.DROP_SKIP_RATE, int),
            isinstance(self.ONLY_GRAB_POG_CARDS, bool),
            isinstance(self.RANDOM_COMMAND_RATE, int),
            isinstance(self.SPECIAL_EVENT, bool),
            self.TERMINAL_VISIBILITY in (0, 1),
            self.RATE_LIMIT >= 0,
            self.TIME_LIMIT_HOURS_MIN >= 0,
            self.TIME_LIMIT_HOURS_MAX >= 0,
            self.CHANNEL_SKIP_RATE != 0,
            self.DROP_SKIP_RATE != 0,
            self.RANDOM_COMMAND_RATE > 0
        ]):
            input("⛔ Configuration Error ⛔\nPlease enter valid values in config.py.")
            sys.exit()
        if self.TIME_LIMIT_HOURS_MIN > self.TIME_LIMIT_HOURS_MAX:
            input("⛔ Configuration Error ⛔\nPlease enter a maximum time limit greater than the minimum time limit in config.py.")
            sys.exit()

    def get_headers(self, token: str, channel_id: str):
        if token not in self.token_headers:
            windows_version = random.choice(self.WINDOWS_VERSIONS)
            browser_version = random.choice(self.BROWSER_VERSIONS)
            build_number = random.choice([381653, 382032, 382201, 382355, 417521])  # Random Discord build version numbers
            super_properties = {
                "os": "Windows",
                "browser": "Chrome",
                "device": "",
                "system_locale": "en-US",
                "browser_user_agent": (
                    f"Mozilla/5.0 (Windows NT {windows_version}; Win64; x64) "
                    f"AppleWebKit/537.36 (KHTML, like Gecko) "
                    f"Chrome/{browser_version} Safari/537.36 Brave/{browser_version}"  # Brave Browser - Windows 10/11 (Brave bypasses most Cloudflare detections)
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
                "Referer": "https://discord.com/channels/@me",
                "X-Context-Properties": base64.b64encode(json.dumps({
                    "location": "Channel",
                    "location_channel_id": channel_id,
                    "location_channel_type": 1,
                }).encode()).decode()
            }
        return self.token_headers[token]

    async def get_user_id(self, token: str, channel_id: str):
        headers = self.get_headers(token, channel_id)
        user_id = None
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/v10/users/@me", headers = headers) as resp:
                if resp.status == 200:
                    user_id = (await resp.json()).get('id')
        return user_id

    async def get_drop_message(self, token: str, account: int, channel_id: str, special_event: bool):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=5"
        headers = self.get_headers(token, channel_id)
        user_id = await self.get_user_id(token, channel_id)
        on_cooldown = False
        timeout = 30  # seconds
        start_time = time.monotonic()
        async with aiohttp.ClientSession() as session:
            while (time.monotonic() - start_time) < timeout:
                async with session.get(url, headers = headers) as resp:
                    status = resp.status
                    if status == 200:
                        messages = await resp.json()
                        try:
                            for msg in messages:
                                reactions = msg.get('reactions', [])
                                if all([
                                    msg.get('author', {}).get('id') == self.KARUTA_BOT_ID,
                                    len(reactions) >= 3,
                                    f"<@{user_id}> {self.KARUTA_DROP_MESSAGE}" in msg.get('content', ''),
                                    self.KARUTA_EXPIRED_DROP_MESSAGE not in msg.get('content', '')
                                ]):
                                    if special_event:
                                        print(f"✅ [Account #{account}] Retrieved drop message (watching special event).")
                                    else:
                                        print(f"✅ [Account #{account}] Retrieved drop message.")
                                    return msg
                                elif msg.get('author', {}).get('id') == self.KARUTA_BOT_ID and f"<@{user_id}>{self.KARUTA_DROP_COOLDOWN_MESSAGE}" in msg.get('content', ''):
                                    on_cooldown = True
                        except (KeyError, IndexError):
                            pass
                        if on_cooldown:
                            print(f"ℹ️ [Account #{account}] Retrieve drop message failed: Drop is on cooldown.")
                            return None
                    elif status == 401:
                        print(f"❌ [Account #{account}] Retrieve drop message failed ({self.drop_fail_count + 1}/{self.DROP_FAIL_LIMIT}): Invalid token.")
                        async with self.drop_fail_count_lock:
                            self.drop_fail_count += 1
                        return None
                    elif status == 403:
                        print(f"❌ [Account #{account}] Retrieve drop message failed ({self.drop_fail_count + 1}/{self.DROP_FAIL_LIMIT}): Token banned or insufficient permissions.")
                        async with self.drop_fail_count_lock:
                            self.drop_fail_count += 1
                        return None
                await asyncio.sleep(random.uniform(0.5, 1))
            print(f"❌ [Account #{account}] Retrieve drop message failed ({self.drop_fail_count + 1}/{self.DROP_FAIL_LIMIT}): Timed out ({timeout}s).")
            async with self.drop_fail_count_lock:
                self.drop_fail_count += 1
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
                elif status == 401:
                    print(f"❌ [Account #{account}] Send message '{content}' failed: Invalid token.")
                elif status == 403:
                    print(f"❌ [Account #{account}] Send message '{content}' failed: Token banned or insufficient permissions.")
                elif status == 429 and rate_limited < self.RATE_LIMIT:
                    rate_limited += 1
                    retry_after = 1  # seconds
                    print(f"⚠️ [Account #{account}] Send message '{content}' failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    await self.send_message(token, account, channel_id, content, rate_limited)
                else:
                    print(f"❌ [Account #{account}] Send message '{content}' failed: Error code {status}.")
                return status == 200

    async def get_card_companion_pog_cards(self, token: str, account: int, channel_id: str, drop_message_id: str):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    try:
                        for msg in messages:
                            if all([
                                msg.get('author', {}).get('id') == self.CARD_COMPANION_BOT_ID,
                                msg.get('id') > drop_message_id,  # Ensure CardCompanion message was sent after the drop message
                                any(emoji_str in msg.get('content', '') for emoji_str in self.CARD_COMPANION_POG_EMOJIS)  # Check if message contains an emoji indicating a pog card
                            ]):
                                content = msg.get('content', '')
                                card_numbers = []
                                # Parse card numbers
                                for match in re.findall(r"<:(no_\d+):\d+>", content):
                                    emoji_str = f":{match}:"
                                    if emoji_str in self.CARD_COMPANION_POG_EMOJIS:
                                        card_numbers.append(int(match.split("_")[1]))
                                # Check if card numbers were successfully parsed
                                if card_numbers:
                                    print(f"✅ [Account #{account}] Identified CardCompanion pog card(s): {card_numbers}.")
                                    return card_numbers
                                else:
                                    print(f"❌ [Account #{account}] Unable to parse pog card numbers from CardCompanion message.")
                                    return None
                    except (KeyError, IndexError):
                        pass
                else:
                    print(f"❌ [Account #{account}] Retrieve CardCompanion message failed: Error code {status}.")
                    return None
                # In the case CardCompanion does not return a message containing a pog card, return None
                return None

    async def add_reaction(self, token: str, account: int, channel_id: str, message_id: str, emoji: str, rate_limited: int):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers = headers) as resp:
                status = resp.status
                if emoji in self.EMOJIS:
                    card_number = self.EMOJI_MAP.get(emoji)
                    if status == 204:
                        print(f"✅ [Account #{account}] Grabbed card {card_number}.")
                    elif status == 401:
                        print(f"❌ [Account #{account}] Grab card {card_number} failed: Invalid token.")
                    elif status == 403:
                        print(f"❌ [Account #{account}] Grab card {card_number} failed: Token banned or insufficient permissions.")
                    elif status == 429 and rate_limited < self.RATE_LIMIT:
                        rate_limited += 1
                        retry_after = 1  # seconds
                        print(f"⚠️ [Account #{account}] Grab card {card_number} failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        await self.add_reaction(token, account, channel_id, message_id, emoji, rate_limited)
                    else:
                        print(f"❌ [Account #{account}] Grab card {card_number} failed: Error code {status}.")
                elif account == 0 and self.SPECIAL_EVENT:  # when reacting with special event emoji
                    if channel_id in self.DROP_CHANNEL_IDS:
                        channel_name = f"Drop Channel #{self.DROP_CHANNEL_IDS.index(channel_id) + 1}"
                    elif channel_id in self.SERVER_ACTIVITY_DROP_CHANNEL_IDS:
                        channel_name = f"Server Activity Drop Channel #{self.SERVER_ACTIVITY_DROP_CHANNEL_IDS.index(channel_id) + 1}"
                    else:
                        channel_name = "Unknown Channel"
                    if status == 204:
                        print(f"✅ [Special Event Account] Reacted {emoji} in {channel_name}.")
                    elif status == 401:
                        print(f"❌ [Special Event Account] React {emoji} in {channel_name} failed: Invalid token.")
                    elif status == 403:
                        print(f"❌ [Special Event Account] React {emoji} in {channel_name} failed: Token banned or insufficient permissions.")
                    elif status == 429 and rate_limited < self.RATE_LIMIT:
                        rate_limited += 1
                        retry_after = 1  # seconds
                        print(f"⚠️ [Special Event Account] React {emoji} in {channel_name} failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        await self.add_reaction(token, account, channel_id, message_id, emoji, rate_limited)
                    else:
                        print(f"❌ [Special Event Account] React {emoji} in {channel_name} failed: Error code {status}.")
                else:  # when manually reacting with message commands
                    if status == 204:
                        print(f"✅ [Account #{account}] Reacted {emoji}.")
                    elif status == 401:
                        print(f"❌ [Account #{account}] React {emoji} failed: Invalid token.")
                    elif status == 403:
                        print(f"❌ [Account #{account}] React {emoji} failed: Token banned or insufficient permissions.")
                    elif status == 429 and rate_limited < self.RATE_LIMIT:
                        rate_limited += 1
                        retry_after = 1  # seconds
                        print(f"⚠️ [Account #{account}] React {emoji} failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        await self.add_reaction(token, account, channel_id, message_id, emoji, rate_limited)
                    else:
                        print(f"❌ [Account #{account}] React {emoji} failed: Error code {status}.")

    async def run_command_checker(self):
        if self.COMMAND_CHANNEL_IDS:
            for channel_id in self.COMMAND_CHANNEL_IDS:
                command_checker = CommandChecker(
                    main = self,
                    tokens = self.tokens,
                    command_user_ids = self.COMMAND_USER_IDS,
                    command_channel_id = channel_id,
                    karuta_prefix = self.KARUTA_PREFIX,
                    karuta_bot_id = self.KARUTA_BOT_ID,
                    karuta_card_transfer_title = self.KARUTA_CARD_TRANSFER_TITLE,
                    karuta_multitrade_lock_message = self.KARUTA_MULTITRADE_LOCK_MESSAGE,
                    karuta_multitrade_confirm_message = self.KARUTA_MULTITRADE_CONFIRM_MESSAGE,
                    karuta_multiburn_title = self.KARUTA_MULTIBURN_TITLE,
                    rate_limit = self.RATE_LIMIT
                )
                asyncio.create_task(command_checker.run())
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

    async def drop_and_grab(self, token: str, account: int, channel_id: str, channel_tokens: list[str]):
        num_channel_tokens = len(channel_tokens)
        drop_message = random.choice(self.DROP_MESSAGES) + random.choice(self.RANDOM_ADDON)
        sent = await self.send_message(token, account, channel_id, drop_message, 0)
        if sent:
            drop_message = await self.get_drop_message(token, account, channel_id, special_event = False)
            if drop_message:
                drop_message_id = drop_message.get('id')
                # Note that there is no need to wait for the CardCompanion message because get_drop_message() only returns after all Karuta emojis have been added, by which time CardCompanion should have already identified the drop
                pog_cards = await self.get_card_companion_pog_cards(token, account, channel_id, drop_message_id) # Get pog card number(s) as a list (containing 1, 2, or 3) or None
                if pog_cards:
                    # If there is at least one pog card, always ensure the dropper is the grabber
                    if self.ATTEMPT_EXTRA_POG_GRABS:
                        # If there are pog card(s) and attempting extra grabs,
                        if self.ONLY_GRAB_POG_CARDS:
                            # If only grabbing pog cards,
                            # The dropper will attempt to grab all pog cards, and non-droppers will attempt to grab all the pog cards EXCEPT the first pog card (the card that the dropper is guaranteed to be able to grab)
                            # This way, pog cards will always be grabbed, even if the dropper did not have enough extra grabs
                        
                        else:
                            # If grabbing all cards,
                            # The dropper will attempt to grab all pog cards, and non-droppers will attempt to grab the other 2 cards, regardless of whether the dropper has already grabbed the pog card(s)
                            # This way, pog cards will always be grabbed, even if the dropper did not have enough extra grabs
                        
                    else:
                        # If there are pog card(s) but not attempting extra grabs,
                        if self.ONLY_GRAB_POG_CARDS:
                            # If only grabbing pog cards,
                            # The dropper will only grab the first pog card, and non-droppers will grab the remaining pog cards, if any


                        else:
                            # If grabbing all cards,
                            # The dropper will only grab the first pog card, and non-droppers will grab the other two cards (which may or may not also be pog cards)
                            first_pog_card_index = pog_cards[0] - 1
                            first_pog_card_emoji = self.EMOJIS[first_pog_card_index]
                            await self.add_reaction(token, account, channel_id, drop_message_id, first_pog_card_emoji, 0)
                            await asyncio.sleep(random.uniform(0.5, 3.5))

                            # Copy, remove, and shuffle other_emojis and other_channel_tokens
                            other_emojis = self.EMOJIS.copy()
                            other_emojis.remove(first_pog_card_emoji)
                            shuffled_other_emojis = random.sample(other_emojis, len(other_emojis))
                            other_channel_tokens = channel_tokens.copy()
                            other_channel_tokens.remove(token)
                            num_other_channel_tokens = len(other_channel_tokens)
                            random.shuffle(other_channel_tokens)

                            for i in range(num_other_channel_tokens):
                                emoji = shuffled_other_emojis[i]
                                grab_token = other_channel_tokens[i]
                                grab_account = self.tokens.index(grab_token) + 1
                                await self.add_reaction(grab_token, grab_account, channel_id, drop_message_id, emoji, 0)
                                await asyncio.sleep(random.uniform(0.5, 3.5))
                else:
                    # If there are no pog cards and grabbing all cards, 
                    # All three accounts will grab one card each, as per usual
                    # Note that self.ATTEMPT_EXTRA_POG_GRABS is not a factor here because there are no pog cards in the drop
                    if not self.ONLY_GRAB_POG_CARDS:
                        shuffled_emojis = random.sample(self.EMOJIS, len(self.EMOJIS))  # Shuffle emojis for random emoji order
                        random.shuffle(channel_tokens)  # Shuffle tokens for random emoji assignment
                        for i in range(num_channel_tokens):
                            emoji = shuffled_emojis[i]
                            grab_token = channel_tokens[i]
                            grab_account = self.tokens.index(grab_token) + 1
                            await self.add_reaction(grab_token, grab_account, channel_id, drop_message_id, emoji, 0)
                            await asyncio.sleep(random.uniform(0.5, 3.5))
                
                # Grab special event emoji on special event account
                if self.SPECIAL_EVENT:
                    if self.ONLY_GRAB_POG_CARDS:  # Extra delay is only necessary if no cards were grabbed (if self.ONLY_GRAB_POG_CARDS = True)
                        await asyncio.sleep(3)
                    drop_message = await self.get_drop_message(token, account, channel_id, special_event = True)
                    if len(drop_message.get('reactions', [])) > 3:  # 3 cards + special event emoji(s)
                        await self.special_event_grabber.add_special_event_reactions(channel_id, drop_message)

                # If only grabbing pog cards, then only the dropper will ever be active
                # Hence, non-droppers should never send random messages in the channel; only the dropper will
                if self.ONLY_GRAB_POG_CARDS:
                    if random.choice([True, True, False]):  # 66% chance of sending random commands/messages
                        for _ in range(random.randint(1, 3)):
                            random_msg_list = random.choice([self.RANDOM_COMMANDS, self.RANDOM_MESSAGES])
                            random_msg = random.choice(random_msg_list)
                            await self.send_message(token, account, channel_id, random_msg, self.RATE_LIMIT)
                            await asyncio.sleep(random.uniform(1, 4))
                else:
                    # If grabbing all cards, then all accounts in the channel are active, so all accounts should send random messages
                    random.shuffle(channel_tokens)  # Shuffle tokens again for random order messages
                    for i in range(num_channel_tokens):
                        if random.choice([True, False]):  # 50% chance of sending random commands/messages
                            msg_token = channel_tokens[i]
                            msg_account = self.tokens.index(msg_token) + 1
                            for _ in range(random.randint(1, 3)):
                                random_msg_list = random.choice([self.RANDOM_COMMANDS, self.RANDOM_MESSAGES])
                                random_msg = random.choice(random_msg_list)
                                await self.send_message(msg_token, msg_account, channel_id, random_msg, self.RATE_LIMIT)
                                await asyncio.sleep(random.uniform(1, 4))
        else:
            if self.TERMINAL_VISIBILITY:
                hwnd = win32console.GetConsoleWindow()
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
                input(f"⛔ Request Error ⛔\nMalformed request on Account #{account}. Possible reasons include:" +
                        f"\n 1. Invalid/expired token\n 2. Incorrectly inputted server/channel/bot ID\nPress `Enter` to restart the script.")
                ctypes.windll.shell32.ShellExecuteW(
                    None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, self.TERMINAL_VISIBILITY
                )
            sys.exit()

    async def async_input_handler(self, prompt: str, target_command: str, flag: str):
        while True:
            if self.pause_event.is_set():
                self.pause_event.clear()  # Pause drops, but not commands
            command = await asyncio.to_thread(input, prompt)
            if command == target_command:  # Resume if target command is inputted
                if flag == self.DROP_FAIL_LIMIT_REACHED_FLAG and self.DROP_FAIL_LIMIT >= 0 and self.drop_fail_count >= self.DROP_FAIL_LIMIT:
                    async with self.drop_fail_count_lock:
                        self.drop_fail_count = 0
                    print("ℹ️ Reset drop fail count. Resuming drops...")
                elif flag == self.EXECUTION_COMPLETED_FLAG:
                    ctypes.windll.shell32.ShellExecuteW(
                        None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, self.TERMINAL_VISIBILITY
                    )
                    sys.exit()
                self.pause_event.set()
                break  # Continue the script

    async def run_instance(self, channel_num: int, channel_id: str, start_delay: int, channel_tokens: list[str], time_limit_seconds: int):
        try:
            num_accounts = len(channel_tokens)
            delay = 30 * 60 / num_accounts  # Ideally 10 min delay per account (3 accounts)
            # Breaking up start delay into multiple steps to check if need to pause
            random_start_delay_per_step = random.uniform(2, 3)
            num_start_delay_steps = round(start_delay / random_start_delay_per_step)
            for _ in range(num_start_delay_steps):
                await self.pause_event.wait()  # Check if need to pause
                await asyncio.sleep(random_start_delay_per_step)
            start_time = time.monotonic()
            while True:
                for token in channel_tokens:
                    print(f"\nChannel #{channel_num} - {datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")
                    if time.monotonic() - start_time >= time_limit_seconds:  # Time limit for automatic shutoff
                        print(f"ℹ️ Channel #{channel_num} has reached the time limit of {(time_limit_seconds / 60 / 60):.1f} hours. Stopping drops in channel...")
                        await self.send_message(token, self.tokens.index(token) + 1, channel_id, random.choice(self.TIME_LIMIT_EXCEEDED_MESSAGES), 0)
                        return
                    if self.DROP_SKIP_RATE < 0 or random.randint(1, self.DROP_SKIP_RATE) != 1:  # If SKIP_RATE == -1 (or any neg num), never skip
                        await self.drop_and_grab(token, self.tokens.index(token) + 1, channel_id, channel_tokens.copy())
                    else:
                        print(f"✅ [Account #{self.tokens.index(token) + 1}] Skipped drop.")
                    await self.pause_event.wait()  # Check if need to pause
                    if self.DROP_FAIL_LIMIT >= 0 and self.drop_fail_count >= self.DROP_FAIL_LIMIT:  # If FAIL_LIMIT == -1 (or any neg num), never pause
                        if self.COMMAND_CHANNEL_IDS:
                            await self.send_message(token, self.tokens.index(token) + 1, self.COMMAND_CHANNEL_IDS[0], "⚠️ Drop fail limit reached", 0)
                        if self.TERMINAL_VISIBILITY:
                            await self.async_input_handler(f"\n⚠️ Drop Fail Limit Reached ⚠️\nThe script has failed to retrieve {self.DROP_FAIL_LIMIT} total drops. Automatically pausing drops...\nPress `Enter` if you wish to resume.\n",
                                                                            "", self.DROP_FAIL_LIMIT_REACHED_FLAG)
                    # Breaking up delay into multiple steps to check if need to pause
                    random_delay = delay + random.uniform(0.5 * 60, 5 * 60)  # Wait an additional 0.5-5 minutes per drop
                    random_delay_per_step = random.uniform(2, 3)
                    num_delay_steps = round(random_delay / random_delay_per_step)
                    for _ in range(num_delay_steps):
                        await self.pause_event.wait()  # Check if need to pause
                        await asyncio.sleep(random_delay_per_step)
                        if random.randint(1, self.RANDOM_COMMAND_RATE) == 1:
                            await self.send_message(token, self.tokens.index(token) + 1, channel_id, random.choice(self.RANDOM_COMMANDS), 0)
        except Exception as e:
            print(f"\n❌ Error in Channel #{channel_num} Script Instance ❌\n{e}")

    async def run_script(self):
        if self.SHUFFLE_ACCOUNTS:
            self.shuffled_tokens = random.sample(self.tokens, len(self.tokens))
        else:
            self.shuffled_tokens = None

        await self.run_command_checker()
        await self.set_token_dictionaries()
        
        if self.SPECIAL_EVENT:
            self.special_event_grabber = SpecialEventGrabber(main = self)

        if self.ONLY_GRAB_POG_CARDS:
            print("\n❗ Only pog cards (as defined by CardCompanion) will be grabbed.")
        else:
            print("\nℹ️ All dropped cards will be grabbed, regardless of whether it is a pog card (as defined by CardCompanion).")

        task_instances = []
        num_channels = len(self.DROP_CHANNEL_IDS)
        start_delay_multipliers = random.sample(range(num_channels), num_channels)
        for index, channel_id in enumerate(self.DROP_CHANNEL_IDS):
            channel_num = index + 1
            if self.CHANNEL_SKIP_RATE > 0 and random.randint(1, self.CHANNEL_SKIP_RATE) == 1:  # If SKIP_RATE == -1 (or any neg num), never skip
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

    def signal_handler(self, signum, frame):
        print("\n✅ Terminal window closed. Running cleanup...")
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
    RELAUNCH_FLAG = "--no-relaunch"
    if RELAUNCH_FLAG not in sys.argv:
        ctypes.windll.shell32.ShellExecuteW(
            None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, bot.TERMINAL_VISIBILITY
        )
        sys.exit()
    bot.check_config()
    bot.tokens = TokenExtractor().main(standalone = False, num_channels = len(bot.DROP_CHANNEL_IDS))
    
    # Set up signal handlers to send a message on terminal window closure
    if bot.COMMAND_CHANNEL_IDS:
        signal.signal(signal.SIGTERM, bot.signal_handler)
        signal.signal(signal.SIGINT, bot.signal_handler)
    
    asyncio.run(bot.run_script())