import aiohttp
from aiohttp import ClientConnectorError, ClientConnectorDNSError
from datetime import datetime
import asyncio
import random
import uuid

class CommandChecker():
    def __init__(self, main, tokens: list[str], command_user_ids: list[str], command_server_id: str, command_channel_id: str, karuta_prefix: str, karuta_bot_id: str, karuta_drop_message: str, 
                      karuta_expired_drop_message: str, karuta_card_transfer_title: str, karuta_multitrade_lock_message: str, karuta_multitrade_confirm_message: str, karuta_multiburn_title: str, 
                      rate_limit: int):
        self.main = main
        self.tokens = tokens
        self.COMMAND_USER_IDS = command_user_ids
        self.COMMAND_SERVER_ID = command_server_id
        self.COMMAND_CHANNEL_ID = command_channel_id
        self.KARUTA_PREFIX = karuta_prefix
        self.KARUTA_BOT_ID = karuta_bot_id
        self.INTERACTION_BOT_IDS = [self.KARUTA_BOT_ID, "408785106942164992"]  # List of bot IDs to look for when pressing buttons or sending reactions (i.e. OwO)
        self.KARUTA_DROP_MESSAGE = karuta_drop_message
        self.KARUTA_EXPIRED_DROP_MESSAGE = karuta_expired_drop_message
        self.KARUTA_CARD_TRANSFER_TITLE = karuta_card_transfer_title
        self.KARUTA_MULTITRADE_LOCK_MESSAGE = karuta_multitrade_lock_message
        self.KARUTA_MULTITRADE_CONFIRM_MESSAGE = karuta_multitrade_confirm_message
        self.KARUTA_MULTIBURN_TITLE = karuta_multiburn_title
        self.RATE_LIMIT = rate_limit

        self.MESSAGE_COMMAND_PREFIX = "cmd"
        self.ALL_ACCOUNT_FLAG = "all"
        self.INTERACTION_URL = "https://discord.com/api/v10/interactions"
        self.KARUTA_LOCK_COMMAND = "/lock"
        self.KARUTA_MULTIBURN_COMMAND = "/burn"
        self.KARUTA_CLICK_BUTTON_COMMAND = "/b "
        self.KARUTA_SEND_REACTION_COMMAND = "/r "
        self.KARUTA_PAUSE_COMMAND = "/pause"
        self.KARUTA_RESUME_COMMAND = "/resume"

        self.discord_down_consec_count = 0  # Consecutive times HTTP error 502/503 is returned
        self.DISCORD_DOWN_CONSEC_LIMIT = 5  # When HTTP error 502/503 is returned self.discord_service_down_limit times in a row, start displaying warnings
        self.exception_count = 0  # Consecutive times an exception is thrown
        self.EXCEPTION_LIMIT = 5  # Max consecutive times an exception is thrown before stopping command checker
        self.executed_commands = []
        self.card_transfer_messages = []
        self.multitrade_messages = []
        self.multiburn_initial_messages = []
        self.multiburn_fire_messages = []

    async def get_karuta_message(self, token: str, account: int, channel_id: str, search_content: str, rate_limited: int):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50"
        headers = self.main.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    try:
                        for msg in messages:
                            if msg.get('author', {}).get('id') == self.KARUTA_BOT_ID:
                                if search_content == self.KARUTA_CARD_TRANSFER_TITLE and msg.get('embeds') and self.KARUTA_CARD_TRANSFER_TITLE == msg['embeds'][0].get('title'):
                                    print(f"✅ [Account #{account}] Retrieved card transfer message.")
                                    return msg
                                elif search_content == self.KARUTA_MULTITRADE_LOCK_MESSAGE and self.KARUTA_MULTITRADE_LOCK_MESSAGE in msg.get('content', ''):
                                    print(f"✅ [Account #{account}] Retrieved multitrade lock message.")
                                    return msg
                                elif search_content == self.KARUTA_MULTITRADE_CONFIRM_MESSAGE and self.KARUTA_MULTITRADE_CONFIRM_MESSAGE in msg.get('content', ''):
                                    print(f"✅ [Account #{account}] Retrieved multitrade confirm message.")
                                    return msg
                                elif search_content == self.KARUTA_MULTIBURN_TITLE and msg.get('embeds') and self.KARUTA_MULTIBURN_TITLE == msg['embeds'][0].get('title'):
                                    print(f"✅ [Account #{account}] Retrieved multiburn message.")
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
                print(f"❌ [Account #{account}] Retrieve message failed: Message '{search_content}' not found in recent messages.")
                return None

    async def check_command(self, token: str):
        url = f"https://discord.com/api/v10/channels/{self.COMMAND_CHANNEL_ID}/messages?limit=3"
        headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    self.discord_down_consec_count = 0
                    messages = await resp.json()
                    for msg in messages:
                        try:
                            raw_content = msg.get('content', '')
                            if ((not self.COMMAND_USER_IDS or (self.COMMAND_USER_IDS and msg.get('author', {}).get('id') in self.COMMAND_USER_IDS))
                                and raw_content.startswith(self.MESSAGE_COMMAND_PREFIX)
                                and msg not in self.executed_commands
                            ):
                                self.executed_commands.append(msg)
                                content = raw_content.removeprefix(self.MESSAGE_COMMAND_PREFIX).strip()
                                account_str, command = (content.split(" ", 1) + [""])[:2]

                                # Parsing account number
                                if account_str.isdigit():
                                    account_num = int(account_str)
                                    if account_num < 1 or account_num > len(self.tokens):
                                        print(f"\n❌ Error parsing command: Account number is not between 1 and {len(self.tokens)}.")
                                        return None, None, None
                                    account_range = (account_num, account_num)
                                elif account_str.lower() == self.ALL_ACCOUNT_FLAG:
                                    account_range = (1, len(self.tokens))
                                elif account_str.lower() == self.KARUTA_PAUSE_COMMAND:
                                    if self.main.pause_event.is_set():
                                        self.main.pause_event.clear()  # Pause drops
                                        print("\n🤖 Pausing all drops...")
                                        await self.main.send_message(token, self.tokens.index(token) + 1, self.COMMAND_CHANNEL_ID, "Pausing all drops...", 0)
                                    else:
                                        print("\n🤖 Drops are already paused.")
                                        await self.main.send_message(token, self.tokens.index(token) + 1, self.COMMAND_CHANNEL_ID, "Drops are already paused.", 0)
                                    return None, None, None
                                elif account_str.lower() == self.KARUTA_RESUME_COMMAND:
                                    if not self.main.pause_event.is_set():
                                        self.main.pause_event.set()  # Resume drops
                                        print("\n🤖 Resuming all drops...")
                                        await self.main.send_message(token, self.tokens.index(token) + 1, self.COMMAND_CHANNEL_ID, "Resuming all drops...", 0)
                                    else:
                                        print("\n🤖 Drops have already resumed.")
                                        await self.main.send_message(token, self.tokens.index(token) + 1, self.COMMAND_CHANNEL_ID, "Drops have already resumed.", 0)
                                    return None, None, None
                                elif '-' in account_str:
                                    account_strs = account_str.split('-')
                                    lower_str = account_strs[0]
                                    upper_str = account_strs[1]
                                    if (lower_str.isdigit() and upper_str.isdigit()):
                                        lower = int(lower_str)
                                        upper = int(upper_str)
                                        if (1 <= lower and lower <= upper and upper <= len(self.tokens)):
                                            account_range = (lower, upper)
                                        else:
                                            print(f"\n❌ Error parsing command: Account number range is either not between 1 and {len(self.tokens)} or the lower account number is greater than the upper account number.")
                                            return None, None, None
                                    else:
                                        print("\n❌ Error parsing command: Account number range does not contain two integers.")
                                        return None, None, None
                                else:
                                    print("\n❌ Error parsing command: Account number is not a number, a range of numbers, or 'all'.")
                                    return None, None, None

                                # Parsing commands
                                is_single_account = (account_range[0] == account_range[1])
                                if (is_single_account):
                                    # If sending from single account
                                    if command.startswith(f"{self.KARUTA_PREFIX}give") or command.startswith(f"{self.KARUTA_PREFIX}g"):
                                        print(f"\n🤖 Sending card transfer from Account #{account_range[0]}...")
                                        send = True
                                    elif command == self.KARUTA_LOCK_COMMAND:
                                        print(f"\n🤖 Locking and confirming trade from Account #{account_range[0]}...")
                                        send = False
                                    elif command.startswith(f"{self.KARUTA_PREFIX}multiburn") or command.startswith(f"{self.KARUTA_PREFIX}mb"):
                                        print(f"\n🤖 Multiburning on Account #{account_range[0]}...")
                                        send = True
                                    elif command == self.KARUTA_MULTIBURN_COMMAND:
                                        print(f"\n🤖 Confirming multiburn on Account #{account_range[0]}...")
                                        send = False
                                    elif command.startswith(self.KARUTA_CLICK_BUTTON_COMMAND) and command.split(" ", 1)[-1] != self.KARUTA_CLICK_BUTTON_COMMAND:
                                        print(f"\n🤖 Clicking {command.split(" ", 1)[-1]} button on Account #{account_range[0]}...")
                                        send = False
                                    elif command.startswith(self.KARUTA_SEND_REACTION_COMMAND) and command.split(" ", 1)[-1] != self.KARUTA_SEND_REACTION_COMMAND:
                                        print(f"\n🤖 Sending {command.split(" ", 1)[-1]} reaction on Account #{account_range[0]}...")
                                        send = False
                                    else:
                                        # If single account and not sending special command
                                        print(f"\n🤖 Sending '{command}' from Account #{account_range[0]}...")
                                        send = True
                                else:
                                    # If range of accounts and not sending special commands
                                    print(f"\n🤖 Sending '{command}' from Accounts #{account_range[0]}-{account_range[1]}...")
                                    send = True
                                return send, account_range, command
                        
                        except Exception as e:
                            print(f"\n❌ Error parsing command: {e}")
                            return None, None, None
                elif status == 502 or status == 503:  # Discord servers under heavy load, not client-side error
                    self.discord_down_consec_count += 1
                    if self.discord_down_consec_count >= self.DISCORD_DOWN_CONSEC_LIMIT:
                        print(f"\n❌ Command check failed ({datetime.now().strftime('%I:%M:%S %p').lstrip('0')}): Discord servers down / under heavy load.")
                else:
                    print(f"\n❌ Command check failed on Account #{self.tokens.index(token) + 1} ({datetime.now().strftime('%I:%M:%S %p').lstrip('0')}): Error code {status}.")
                    return None, None, None
                # If status = 200 but no MESSAGE_COMMAND_PREFIX found |OR| If status = 502/503 but not reached limit yet
                return None, None, None

    async def get_payload(self, account: int, button_string: str, message: dict):
        button_bot_id = message.get('author', {}).get('id')
        components = message.get('components', [])
        for action_row in components:
            for button in action_row.get('components', []):
                button_emoji = button.get('emoji', {}).get('name') or ''
                button_label = button.get('label', '')
                if button_string in button_emoji + button_label:
                    custom_id = button.get('custom_id')
                    # Simulate button click via interaction callback
                    payload = {
                        "type": 3,  # Component interaction
                        "nonce": str(uuid.uuid4().int >> 64),  # Unique interaction ID
                        "guild_id": self.COMMAND_SERVER_ID,
                        "channel_id": self.COMMAND_CHANNEL_ID,
                        "message_flags": 0,
                        "message_id": message.get('id'),
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

    async def check_card_transfer(self, token: str, account: int, command: str):
        if command.startswith(f"{self.KARUTA_PREFIX}give") or command.startswith(f"{self.KARUTA_PREFIX}g"):
            await asyncio.sleep(random.uniform(3, 5))  # Wait for Karuta card transfer message
            card_transfer_message = await self.get_karuta_message(token, account, self.COMMAND_CHANNEL_ID, self.KARUTA_CARD_TRANSFER_TITLE, self.RATE_LIMIT)
            if card_transfer_message and card_transfer_message not in self.card_transfer_messages:
                self.card_transfer_messages.append(card_transfer_message)
                # Find ✅ button
                payload = await self.get_payload(account, '✅', card_transfer_message)
                if payload is not None:
                    async with aiohttp.ClientSession() as session:
                        headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
                        async with session.post(self.INTERACTION_URL, headers = headers, json = payload) as resp:
                            status = resp.status
                            if status == 204:
                                print(f"✅ [Account #{account}] Confirmed card transfer.")
                            else:
                                print(f"❌ [Account #{account}] Confirm card transfer failed: Error code {status}.")
                else:
                    print(f"❌ [Account #{account}] Confirm card transfer failed: ✅ button not found.")

    async def check_multitrade(self, token: str, account: int, command: str):
        if command == self.KARUTA_LOCK_COMMAND:
            multitrade_lock_message = await self.get_karuta_message(token, account, self.COMMAND_CHANNEL_ID, self.KARUTA_MULTITRADE_LOCK_MESSAGE, self.RATE_LIMIT)
            if multitrade_lock_message and multitrade_lock_message not in self.multitrade_messages:
                self.multitrade_messages.append(multitrade_lock_message)
                # Find 🔒 button
                lock_payload = await self.get_payload(account, '🔒', multitrade_lock_message)
                if lock_payload is not None:
                    async with aiohttp.ClientSession() as session:
                        headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
                        async with session.post(self.INTERACTION_URL, headers = headers, json = lock_payload) as lock_resp:
                            status = lock_resp.status
                            if status == 204:
                                print(f"✅ [Account #{account}] Locked multitrade.")
                                await asyncio.sleep(random.uniform(3, 5))  # Wait for Karuta multitrade message to update
                                multitrade_confirm_message = await self.get_karuta_message(token, account, self.COMMAND_CHANNEL_ID, self.KARUTA_MULTITRADE_CONFIRM_MESSAGE, self.RATE_LIMIT)
                                # Find ✅ button
                                check_payload = await self.get_payload(account, '✅', multitrade_confirm_message)
                                if check_payload is not None:
                                    async with session.post(self.INTERACTION_URL, headers = headers, json = check_payload) as check_resp:
                                        status = check_resp.status
                                        if status == 204:
                                            print(f"✅ [Account #{account}] Confirmed multitrade.")
                                        else:
                                            print(f"❌ [Account #{account}] Confirm multitrade failed: Error code {status}.")
                                else:
                                    print(f"❌ [Account #{account}] Confirm multitrade failed: ✅ button not found.")
                            else:
                                print(f"❌ [Account #{account}] Lock multitrade failed: Error code {status}.")
                else:
                    print(f"❌ [Account #{account}] Lock multitrade failed: 🔒 button not found.")

    async def check_multiburn(self, token: str, account: int, command: str):
        if command.startswith(f"{self.KARUTA_PREFIX}multiburn") or command.startswith(f"{self.KARUTA_PREFIX}mb"):
            await asyncio.sleep(random.uniform(3, 5))  # Wait for Karuta multiburn message
            multiburn_initial_message = await self.get_karuta_message(token, account, self.COMMAND_CHANNEL_ID, self.KARUTA_MULTIBURN_TITLE, self.RATE_LIMIT)
            if multiburn_initial_message and multiburn_initial_message not in self.multiburn_initial_messages:
                await asyncio.sleep(3)  # Longer delay to wait for check button to enable
                self.multiburn_initial_messages.append(multiburn_initial_message)
                # Find ☑️ button
                payload = await self.get_payload(account, '☑️', multiburn_initial_message)
                if payload is not None:
                    async with aiohttp.ClientSession() as session:
                        headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
                        async with session.post(self.INTERACTION_URL, headers = headers, json = payload) as resp:
                            status = resp.status
                            if status == 204:
                                print(f"✅ [Account #{account}] Confirmed initial (0/2) multiburn.")
                            else:
                                print(f"❌ [Account #{account}] Confirm initial (0/2) multiburn failed: Error code {status}.")
                else:
                    print(f"❌ [Account #{account}] Confirm initial (0/2) multiburn failed: ☑️ button not found.")

    async def confirm_multiburn(self, token: str, account: int, command: str):
        if command == self.KARUTA_MULTIBURN_COMMAND:
            multiburn_fire_message = await self.get_karuta_message(token, account, self.COMMAND_CHANNEL_ID, self.KARUTA_MULTIBURN_TITLE, self.RATE_LIMIT)
            if multiburn_fire_message and multiburn_fire_message not in self.multiburn_fire_messages:
                self.multiburn_fire_messages.append(multiburn_fire_message)
                # Find 🔥 button
                fire_payload = await self.get_payload(account, '🔥', multiburn_fire_message)
                if fire_payload is not None:
                    async with aiohttp.ClientSession() as session:
                        headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
                        async with session.post(self.INTERACTION_URL, headers = headers, json = fire_payload) as fire_resp:
                            status = fire_resp.status
                            if status == 204:
                                print(f"✅ [Account #{account}] Confirmed initial (1/2) multiburn.")
                                await asyncio.sleep(random.uniform(3, 5))  # Wait for Karuta multiburn message to update
                                multiburn_confirm_message = await self.get_karuta_message(token, account, self.COMMAND_CHANNEL_ID, self.KARUTA_MULTIBURN_TITLE, self.RATE_LIMIT)
                                # Find ✅ button
                                check_payload = await self.get_payload(account, '✅', multiburn_confirm_message)
                                if check_payload is not None:
                                    async with session.post(self.INTERACTION_URL, headers = headers, json = check_payload) as check_resp:
                                        status = check_resp.status
                                        if status == 204:
                                            print(f"✅ [Account #{account}] Confirmed final (2/2) multiburn.")
                                        else:
                                            print(f"❌ [Account #{account}] Confirm final (2/2) multiburn failed: Error code {status}.")
                                else:
                                    print(f"❌ [Account #{account}] Confirm final (2/2) multiburn failed: ✅ button not found.")
                            else:
                                print(f"❌ [Account #{account}] Confirm initial (1/2) multiburn failed: Error code {status}.")
                else:
                    print(f"❌ [Account #{account}] Confirm initial (1/2) multiburn failed: 🔥 button not found.")

    async def check_click_button(self, token: str, account: int, command: str):
        if command.startswith(self.KARUTA_CLICK_BUTTON_COMMAND) and command.split(" ", 1)[-1] != self.KARUTA_CLICK_BUTTON_COMMAND:
            button_string = command.split(" ", 1)[-1]
            url = f"https://discord.com/api/v10/channels/{self.COMMAND_CHANNEL_ID}/messages?limit=50"
            headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers = headers) as resp:
                    status = resp.status
                    if status == 200:
                        messages = await resp.json()
                        for msg in messages:
                            if msg.get('author', {}).get('id') in self.INTERACTION_BOT_IDS:
                                payload = await self.get_payload(account, button_string, msg)
                                if payload is not None:
                                    async with aiohttp.ClientSession() as session:
                                        headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
                                        async with session.post(self.INTERACTION_URL, headers = headers, json = payload) as resp:
                                            status = resp.status
                                            if status == 204:
                                                print(f"✅ [Account #{account}] Clicked {button_string} button.")
                                            else:
                                                print(f"❌ [Account #{account}] Click {button_string} button failed: Error code {status}.")
                                            return
                        print(f"❌ [Account #{account}] Click {button_string} button failed: Button not found.")
                    else:
                        print(f"❌ [Account #{account}] Retrieve message failed: Error code {status}.")

    async def check_send_reaction(self, token: str, account: int, command: str):
        if command.startswith(self.KARUTA_SEND_REACTION_COMMAND) and command.split(" ", 1)[-1] != self.KARUTA_SEND_REACTION_COMMAND:
            reaction_string = command.split(" ", 1)[-1]
            url = f"https://discord.com/api/v10/channels/{self.COMMAND_CHANNEL_ID}/messages?limit=50"
            headers = self.main.get_headers(token, self.COMMAND_CHANNEL_ID)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers = headers) as resp:
                    status = resp.status
                    if status == 200:
                        messages = await resp.json()
                        for msg in messages:
                            if msg.get('author', {}).get('id') in self.INTERACTION_BOT_IDS:
                                # Check if the target reaction exists on the message
                                reaction_found = any(r.get('emoji', {}).get('name') == reaction_string for r in msg.get('reactions', []))
                                if reaction_found:
                                    await self.main.add_reaction(token, account, self.COMMAND_CHANNEL_ID, msg.get('id'), reaction_string, self.RATE_LIMIT)
                                    return
                        print(f"❌ [Account #{account}] React {reaction_string} failed: Reaction not found.")
                    else:
                        print(f"❌ [Account #{account}] React {reaction_string} failed: Error code {status}.")

    async def run(self):
        while True:
            try:
                send, account_range, command = await self.check_command(random.choice(self.tokens))  # Use a random account to check for message commands
                if account_range and command:
                    lower_account, upper_account = account_range
                    if (lower_account == upper_account):
                        # If single account
                        token = self.tokens[lower_account - 1]
                        if send:
                            await self.main.send_message(token, lower_account, self.COMMAND_CHANNEL_ID, command, self.RATE_LIMIT)
                        await self.check_card_transfer(token, lower_account, command)
                        await self.check_multitrade(token, lower_account, command)
                        await self.check_multiburn(token, lower_account, command)
                        await self.confirm_multiburn(token, lower_account, command)
                        await self.check_click_button(token, lower_account, command)
                        await self.check_send_reaction(token, lower_account, command)
                    else:
                        # If range of accounts
                        for i in range(lower_account - 1, upper_account):
                            token = self.tokens[i]
                            account_num = i + 1
                            await self.main.send_message(token, account_num, self.COMMAND_CHANNEL_ID, f"{account_num}", self.RATE_LIMIT)  # Show account number
                            await asyncio.sleep(random.uniform(0.1, 0.3))
                            await self.main.send_message(token, account_num, self.COMMAND_CHANNEL_ID, command, self.RATE_LIMIT)  # Won't retry even if rate-limited (so it doesn't interfere with drops/grabs)
                            await asyncio.sleep(random.uniform(2.5, 3.5))
                    print("🤖 Message command executed.")
                self.exception_count = 0
                await asyncio.sleep(random.uniform(1, 2))  # Short delay to avoid getting rate-limited
            except ClientConnectorDNSError:
                print("\n❌ Command checker DNS error.")
                await asyncio.sleep(3)  # Short delay before retrying
            except ClientConnectorError:
                print("\n❌ Command checker connection error.")
                await asyncio.sleep(3)
            except aiohttp.ClientError:
                print("\n❌ Command checker client error.")
                await asyncio.sleep(3)
            except Exception as e:
                self.exception_count += 1
                print(f"\n❌ Command checker unexpected error ({self.exception_count}/{self.EXCEPTION_LIMIT}):\n{e}")
                if self.exception_count >= self.EXCEPTION_LIMIT:
                    print("❌ Terminating command checker due to too many exceptions.")
                    break
                await asyncio.sleep(5)