from datetime import datetime
import random
import asyncio
import aiohttp
import base64
import ctypes
import uuid
import time
import json
import sys
import os
import re
# Import config
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from drop_script.config import Config

class AutoWorker():
    def __init__(self):
        ### Feel free to customize these settings ###
        self.RAND_DELAY_MIN = 10  # (int) Minimum amount of minutes to wait between works
        self.RAND_DELAY_MAX = 20  # (int) Maximum amount of minutes to wait between works
        self.SHUFFLE_ACCOUNTS = True  # (bool) Whether to randomize the order of accounts when working. I recommend keeping this setting `True`
        
        try:
            with open("tokens/tokens.json", "r") as tokens_file:
                self.TOKENS = json.load(tokens_file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.TOKENS = []
        if not isinstance(self.TOKENS, list) or not all(isinstance(token, str) for token in self.TOKENS):
            input('⛔ Token Format Error ⛔\nExpected a list of strings. Example: ["exampleToken1", "exampleToken2", "exampleToken3"]')
            sys.exit()
        elif self.TOKENS == ["exampleToken1", "exampleToken2", "exampleToken3", "..."]:
            input('⛔ Token Format Error ⛔\nPlease replace the example tokens in tokens.json with your real tokens.')
            sys.exit()

        if self.TOKENS:
            if self.SHUFFLE_ACCOUNTS:
                self.tokens = random.sample(self.TOKENS, len(self.TOKENS))
                print("ℹ️ Accounts will work in a randomized order.\n")
            else:
                self.tokens = self.TOKENS
                print("ℹ️ Accounts will work in order.\n")
        else:
            input("⛔ Token Error ⛔\nNo tokens found. Please enter at least 1 token for working in tokens.json.")
            sys.exit()

        self.config = Config()
        self.WORK_CHANNEL_IDS = self.config.DROP_CHANNEL_IDS
        if not self.WORK_CHANNEL_IDS or not all(id.isdigit() for id in self.WORK_CHANNEL_IDS):
            input("⛔ Configuration Error ⛔\nPlease enter non-empty, numeric strings for the drop channel ID(s) in config.py." +
                    "\nThese channels are where the accounts will send work commands.")
            sys.exit()
        
        self.KARUTA_BOT_ID = "646937666251915264"
        self.KARUTA_PREFIX = self.config.KARUTA_PREFIX
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
        self.RATE_LIMIT = 3

        self.KARUTA_NODES_OVERVIEW_TITLE = "Nodes Overview"
        self.KARUTA_WORK_TITLE = "Work"
        self.KARUTA_WORK_FINISHED_MESSAGE = "Your workers have finished their tasks."
        self.KARUTA_WORK_INJURED_MESSAGE = "The following workers have been injured:"
        self.KARUTA_NO_PERMIT_MESSAGE = ", you do not have a permit to work. You can purchase one with the `k!buy work permit` command, then activate it with `k!use work permit`."
        self.KARUTA_WORK_CD_MESSAGE = "before working again."

    def get_headers(self, token: str, channel_id: str):
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
        
        token_header = {
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
        return token_header

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

    async def get_payload(self, token: str, account: int, channel_id: str, button_string: str, msg: dict):
        button_bot_id = msg.get('author', {}).get('id')
        components = msg.get('components', [])
        for action_row in components:
            for button in action_row.get('components', []):
                button_emoji = button.get('emoji', {}).get('name') or ''
                button_label = button.get('label', '')
                if button_string in button_emoji + button_label:
                    custom_id = button.get('custom_id')
                    server_id = await self.get_server_id(token, account, channel_id)
                    # Simulate button click via interaction callback
                    payload = {
                        "type": 3,  # Component interaction
                        "nonce": str(uuid.uuid4().int >> 64),  # Unique interaction ID
                        "guild_id": server_id,
                        "channel_id": channel_id,
                        "message_flags": 0,
                        "message_id": msg.get('id'),
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

    async def click_button(self, token: str, account: int, channel_id: str, button_string: str):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    for msg in messages:
                        if msg.get('author', {}).get('id') in self.KARUTA_BOT_ID:
                            payload = await self.get_payload(token, account, channel_id, button_string, msg)
                            if payload is not None:
                                async with aiohttp.ClientSession() as session:
                                    headers = self.get_headers(token, channel_id)
                                    async with session.post("https://discord.com/api/v10/interactions", headers = headers, json = payload) as resp:
                                        status = resp.status
                                        if status == 204:
                                            print(f"✅ [Account #{account}] Clicked {button_string} button.")
                                        else:
                                            print(f"❌ [Account #{account}] Click {button_string} button failed: Error code {status}.")
                                        return
                    print(f"❌ [Account #{account}] Click {button_string} button failed: Button not found.")
                else:
                    print(f"❌ [Account #{account}] Retrieve message failed: Error code {status}.")

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

    async def get_user_id(self, token: str, channel_id: str):
        headers = self.get_headers(token, channel_id)
        user_id = None
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/v10/users/@me", headers = headers) as resp:
                if resp.status == 200:
                    user_id = (await resp.json()).get('id')
        return user_id

    async def get_karuta_message(self, token: str, account: int, channel_id: str, search_content: str, rate_limited: int):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    try:
                        for msg in messages:
                            referenced_author_id = msg.get('referenced_message', {}).get('author', {}).get('id')  # Get the user ID of the user being replied to
                            if msg.get('author', {}).get('id') == self.KARUTA_BOT_ID and referenced_author_id == await self.get_user_id(token, channel_id):
                                if search_content == self.KARUTA_NODES_OVERVIEW_TITLE and msg.get('embeds') and self.KARUTA_NODES_OVERVIEW_TITLE == msg['embeds'][0].get('title'):
                                    print(f"✅ [Account #{account}] Retrieved Nodes Overview message.")
                                    return msg
                                elif search_content == self.KARUTA_WORK_TITLE and msg.get('embeds') and self.KARUTA_WORK_TITLE == msg['embeds'][0].get('title'):
                                    print(f"✅ [Account #{account}] Retrieved Work message.")
                                    return msg
                                elif search_content == self.KARUTA_NO_PERMIT_MESSAGE and self.KARUTA_NO_PERMIT_MESSAGE in msg.get('content', ''):
                                    print(f"❌ [Account #{account}] Account is missing work permit and unable to work.")
                                    return msg
                                elif search_content == self.KARUTA_WORK_CD_MESSAGE and self.KARUTA_WORK_CD_MESSAGE in msg.get('content', ''):
                                    print(f"ℹ️ [Account #{account}] Account is on work cooldown.")
                                    return msg
                    except (KeyError, IndexError):
                        pass
                elif status == 429 and rate_limited < self.RATE_LIMIT:
                    rate_limited += 1
                    retry_after = 1  # seconds
                    print(f"⚠️ [Account #{account}] Retrieve message failed ({rate_limited}/{self.RATE_LIMIT}): Rate limited, retrying after {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    return await self.get_karuta_message(token, account, channel_id, search_content, rate_limited)
                else:
                    print(f"❌ [Account #{account}] Retrieve message failed: Error code {status}.")
                    return None
                if search_content != self.KARUTA_NO_PERMIT_MESSAGE and search_content != self.KARUTA_WORK_CD_MESSAGE:
                    print(f"❌ [Account #{account}] Retrieve message failed: Message '{search_content}' not found in recent messages.")
                return None

    def parse_min_tax_node(self, msg: dict):
        description = msg['embeds'][0].get('description')

        # \n2\. Gets the second node from the top (the node with the lowest tax)
        # [^a-zA-Z]* Skips non-letter characters (like spaces or backticks)
        # ([a-zA-Z]+) Captures the actual letters of the node
        match = re.search(r'\n2\.[^a-zA-Z]*([a-zA-Z]+)', description)

        min_tax_node = match.group(1)
        return min_tax_node

    def confirm_work_complete(self, account: int, work_msg: str):
        description = work_msg.get('embeds', [{}])[0].get('description', '')
        if self.KARUTA_WORK_FINISHED_MESSAGE in description:
            print(f"✅ [Account #{account}] Work completed.")
            if self.KARUTA_WORK_INJURED_MESSAGE in description:
                print(f"ℹ️ [Account #{account}] Worker(s) have been injured.")
        else:
            print(f"❌ [Account #{account}] Work failed.")

    async def auto_work(self, token: str, account: int):
        account_num = self.TOKENS.index(token) + 1
        random_work_channel_id = random.choice(self.WORK_CHANNEL_IDS)
        print(f"Auto-working on Account #{account_num} ({account}/{len(self.tokens)}) in Channel #{self.WORK_CHANNEL_IDS.index(random_work_channel_id) + 1}...")

        sent = await self.send_message(token, account_num, random_work_channel_id, f"{self.KARUTA_PREFIX}n", 0)
        if sent:
            await asyncio.sleep(random.uniform(3, 7))  # Wait for Nodes Overview message from Karuta
            nodes_overview_msg = await self.get_karuta_message(token, account_num, random_work_channel_id, self.KARUTA_NODES_OVERVIEW_TITLE, 0)
            if nodes_overview_msg:
                min_tax_node = self.parse_min_tax_node(nodes_overview_msg)
                sent = await self.send_message(token, account_num, random_work_channel_id, f"{self.KARUTA_PREFIX}jn {min_tax_node} abcde", 0)
                if sent:
                    await asyncio.sleep(random.uniform(1, 5))  # Random delay
                    sent = await self.send_message(token, account_num, random_work_channel_id, f"{self.KARUTA_PREFIX}w", 0)
                    if sent:
                        await asyncio.sleep(random.uniform(3, 7))  # Wait for Work message from Karuta
                        no_permit_msg = await self.get_karuta_message(token, account_num, random_work_channel_id, self.KARUTA_NO_PERMIT_MESSAGE, 0)
                        cd_msg = await self.get_karuta_message(token, account_num, random_work_channel_id, self.KARUTA_WORK_CD_MESSAGE, 0)
                        if not no_permit_msg and not cd_msg:
                            await self.click_button(token, account_num, random_work_channel_id, '✅')
                            await asyncio.sleep(random.uniform(3, 5))  # Wait for Work message to update
                            work_msg = await self.get_karuta_message(token, account_num, random_work_channel_id, self.KARUTA_WORK_TITLE, 0)
                            user_id = await self.get_user_id(token, random_work_channel_id)
                            self.confirm_work_complete(account_num, user_id, work_msg)
        return

    def main(self):
        # Executes with tokens
        for account_idx in range(len(self.tokens)):
            print(f"{datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")
            token = self.tokens[account_idx]
            asyncio.run(self.auto_work(token, account_idx + 1))
            delay = random.uniform(self.RAND_DELAY_MIN, self.RAND_DELAY_MAX) * 60  # Random delay between works
            print(f"Waiting {round(delay / 60)} minutes before working on another account...\n")
            time.sleep(delay)

        input("✅ All accounts have worked. Press `Enter` to exit.")
        sys.exit()

if __name__ == "__main__":
    RELAUNCH_FLAG = "--no-relaunch"
    if RELAUNCH_FLAG not in sys.argv:
        ctypes.windll.shell32.ShellExecuteW(
            None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, 1  # 0 = hidden, 1 = visible (recommended)
        )
        sys.exit()
    AutoWorker().main()