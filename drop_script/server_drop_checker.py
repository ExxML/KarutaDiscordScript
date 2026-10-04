from textwrap import dedent
import random
import asyncio
import aiohttp
import json
import sys

class ServerDropChecker():
    def __init__(self, main):
        self.main = main
        if self.main.SPECIAL_EVENT:
            self.init_special_event_tokens_dict()
        if self.main.GRAB_SERVER_POG_CARDS:
            self.init_server_token()

        self.main.create_background_task(self.run_server_drop_checker())

    def init_special_event_tokens_dict(self):
        try:
            with open("tokens/special_event_tokens.json", "r", encoding = "utf-8") as special_event_tokens_file:
                self.special_event_tokens_dict = json.load(special_event_tokens_file)
                example_special_event_tokens_dict = {
                    "any": "specialEventToken1",
                    "🌼": "specialEventToken2",
                }
                printed_example_special_event_tokens_dict = dedent(
                    """
                    Example:
                    {
                        "any": "specialEventToken1", <- This token will grab the special event emojis that the other accounts do not grab
                        "🌼": "specialEventToken2"   <- This token will exclusively grab the 🌼 emoji
                    }
                    """
                )
                if not (
                    isinstance(self.special_event_tokens_dict, dict)
                    and all(isinstance(k, str) and isinstance(v, str) for k, v in self.special_event_tokens_dict.items())
                ):
                    input(
                        "\n⛔ Special Event Token Format Error ⛔\nExpected a dictionary in special_event_tokens.json with string keys and values.\n" +
                        printed_example_special_event_tokens_dict
                    )
                    sys.exit()
                elif self.special_event_tokens_dict == {}:
                    input(
                        "\n⛔ Special Event Token Error ⛔\nNo valid values entered in special_event_tokens.json.\n" +
                        printed_example_special_event_tokens_dict +
                        "\nIf you wish to disable the Special Event Grabber, set self.SPECIAL_EVENT to False in config.py."
                    )
                    sys.exit()
                elif self.special_event_tokens_dict == example_special_event_tokens_dict:
                    input("\n⛔ Special Event Token Error ⛔\nPlease replace the example values in special_event_tokens.json with real tokens.\n" +
                                "If you wish to disable the Special Event Grabber, set self.SPECIAL_EVENT to False in config.py."
                    )
                    sys.exit()
                else:
                    print(f"\n👀 Watching for special event reactions in {len(self.main.DROP_CHANNEL_IDS)} script drop channel(s) " +
                            f"and {len(self.main.SERVER_ACTIVITY_DROP_CHANNEL_IDS)} server activity drop channel(s).")
        except FileNotFoundError:
            input("\n⛔ Special Event Token Error ⛔\nNo special_event_tokens.json file found.\n" +
                        "If you wish to disable the Special Event Grabber, set self.SPECIAL_EVENT to False in config.py."
            )
            sys.exit()
        except json.JSONDecodeError:
            input(
                "\n⛔ Special Event Token Format Error ⛔\nExpected a dictionary in special_event_tokens.json with string keys and values.\n" +
                printed_example_special_event_tokens_dict
            )
            sys.exit()

    def init_server_token(self):
        try:
            with open("tokens/server_token.json", "r", encoding = "utf-8") as server_token_file:
                self.server_token = json.load(server_token_file)
                example_server_token = "exampleServerToken"
                if not isinstance(self.server_token, str):
                    input(f'\n⛔ Server Token Format Error ⛔\nExpected a string in server_token.json. Example: "{example_server_token}"')
                    sys.exit()
                elif self.server_token == "":
                    input(f'\n⛔ Server Token Error ⛔\nNo valid values entered in server_token.json. Example: "{example_server_token}"\n' +
                                "If you wish to disable the Server Drop Grabber, set self.GRAB_SERVER_POG_CARDS to False in config.py."
                    )
                    sys.exit()
                elif self.server_token == example_server_token:
                    input("\n⛔ Server Token Error ⛔\nPlease replace the example value in server_token.json with a real token.\n" +
                                "If you wish to disable the Server Drop Grabber, set self.GRAB_SERVER_POG_CARDS to False in config.py."
                    )
                    sys.exit()
                elif len(self.main.SERVER_ACTIVITY_DROP_CHANNEL_IDS) == 0:
                    input("\n⛔ Server Activity Drop Channel Error ⛔\nPlease enter at least one channel ID in self.SERVER_ACTIVITY_DROP_CHANNEL_IDS in config.py.\n" +
                                "If you wish to disable the Server Drop Grabber, set self.GRAB_SERVER_POG_CARDS to False in config.py."
                    )
                    sys.exit()
                else:
                    print(f"\n👀 Watching for pog cards in {len(self.main.SERVER_ACTIVITY_DROP_CHANNEL_IDS)} server activity drop channel(s).")
        except FileNotFoundError:
            input("\n⛔ Server Token Error ⛔\nNo server_token.json file found.\n" +
                        "If you wish to disable the Server Drop Grabber, set self.GRAB_SERVER_POG_CARDS to False in config.py."
            )
            sys.exit()
        except json.JSONDecodeError:
            input(f'\n⛔ Server Token Format Error ⛔\nExpected a string in server_token.json. Example: "{example_server_token}"')
            sys.exit()

    def get_special_event_emojis(self, message: dict):
        emoji_names = [reaction.get('emoji', {}).get('name') for reaction in message.get('reactions', [])]
        return [emoji for emoji in emoji_names if emoji not in self.main.CARD_EMOJIS]

    async def karuta_reacted(self, token: str, channel_id: str, msg_id: str, emoji: str):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{msg_id}/reactions/{emoji}?limit=100"
        headers = self.main.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                return resp.status == 200 and any(user.get('id') == self.main.KARUTA_BOT_ID for user in await resp.json())

    async def add_special_event_reactions(self, channel_id: str, message: dict):
        try:
            msg_id = message.get('id')
            for special_event_emoji in reversed(self.get_special_event_emojis(message)):  # Last emoji first
                if special_event_emoji in self.special_event_tokens_dict:
                    token = self.special_event_tokens_dict.get(special_event_emoji)
                else:
                    token = self.special_event_tokens_dict.get("any", "")
                    if not token:  # If there is no token found for "any", skip this emoji
                        continue
                if not await self.karuta_reacted(token, channel_id, msg_id, special_event_emoji):
                    continue  # Reaction was added by a player, not by Karuta
                await self.main.add_reaction(token, 0, channel_id, msg_id, special_event_emoji, 0)  # 0 as account stub
        except KeyError:
            print(f"❌ [Special Event Account] Retrieve message failed: KeyError.")
            pass
        except IndexError:
            print(f"❌ [Special Event Account] Retrieve message failed: IndexError.")
            pass

    async def grab_server_drop(self, channel_id: str, drop_message_id: str):
        await asyncio.sleep(random.uniform(10, 20))  # Long delay before grabbing to avoid looking suspicious
        pog_cards = await self.main.get_card_companion_pog_cards(self.server_token, 0, channel_id, drop_message_id)
        if pog_cards:
            await self.grab_pog_cards(self.server_token, channel_id, pog_cards, drop_message_id)

    async def grab_pog_cards(self, token: str, channel_id: str, pog_cards: list[str], drop_message_id: str):
        first_pog_card_index = pog_cards[0] - 1
        first_pog_card_emoji = self.main.CARD_EMOJIS[first_pog_card_index]
        await self.main.add_reaction(token, 0, channel_id, drop_message_id, first_pog_card_emoji, 0)
        await asyncio.sleep(random.uniform(0.5, 3.5))
        # Use random accounts to grab the other pog cards, if any
        other_pog_cards = pog_cards.copy()
        other_pog_cards.pop(0)
        random.shuffle(other_pog_cards)
        for pog_card in other_pog_cards:
            emoji = self.main.CARD_EMOJIS[pog_card - 1]
            grab_token = random.choice(self.main.tokens)
            grab_account = self.main.tokens.index(grab_token) + 1
            await self.main.add_reaction(grab_token, grab_account, channel_id, drop_message_id, emoji, 0)
            await asyncio.sleep(random.uniform(0.5, 3.5))

    async def run_server_drop_checker(self):
        server_drop_tokens = []
        if self.main.SPECIAL_EVENT:
            # special_event_msg_history contains the messages that have been previously reacted to (key = message ID, value = number of emojis reacted)
            # Note that if the number of distinct emojis has changed, the message will be considered unseen! This way, if there are multiple special event emojis, all of them will be guaranteed to be grabbed.
            special_event_msg_history: dict[str, int] = {}
            server_drop_tokens += list(self.special_event_tokens_dict.values())
        if self.main.GRAB_SERVER_POG_CARDS:
            # server_pog_drop_msg_history contains the message IDs that have been previously checked for pog cards
            server_pog_drop_msg_history: set[str] = set()
            server_drop_tokens.append(self.server_token)
        while True:
            try:
                for channel_id in self.main.SERVER_ACTIVITY_DROP_CHANNEL_IDS:
                    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=20"
                    headers = self.main.get_headers(random.choice(server_drop_tokens), channel_id)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers = headers) as resp:
                            status = resp.status
                            if status == 200:
                                messages = await resp.json()
                                for msg in messages:
                                    msg_id = msg.get('id')

                                    # Special Event Grabber
                                    num_reactions = len(msg.get('reactions', []))
                                    if self.main.SPECIAL_EVENT and all([
                                        self.get_special_event_emojis(msg),
                                        msg.get('author', {}).get('id') == self.main.KARUTA_BOT_ID,
                                        (msg_id not in special_event_msg_history or special_event_msg_history.get(msg_id) != num_reactions),
                                        (self.main.KARUTA_ANY_DROP_MESSAGE_REGEX.search(msg.get('content', '')) or self.main.KARUTA_SERVER_ACTIVITY_DROP_MESSAGE in msg.get('content', '')),
                                        self.main.KARUTA_EXPIRED_DROP_MESSAGE not in msg.get('content', '')
                                    ]):
                                        await self.add_special_event_reactions(channel_id, msg)
                                        special_event_msg_history[msg_id] = num_reactions
                                    
                                    # Server Drop Grabber
                                    if self.main.GRAB_SERVER_POG_CARDS and all([
                                        num_reactions >= 3,  # At least 3 cards
                                        msg.get('author', {}).get('id') == self.main.KARUTA_BOT_ID,
                                        (msg_id not in server_pog_drop_msg_history),
                                        self.main.KARUTA_SERVER_ACTIVITY_DROP_MESSAGE in msg.get('content', ''),
                                        self.main.KARUTA_EXPIRED_DROP_MESSAGE not in msg.get('content', '')
                                    ]):
                                        server_pog_drop_msg_history.add(msg_id)
                                        self.main.create_background_task(self.grab_server_drop(channel_id, msg_id))  # Run asynchronously so multiple drops can be grabbed concurrently
                            else:
                                print(f"❌ [Special Event Account] Retrieve message failed: Error code {status}.")
                                if status == 429:
                                    await asyncio.sleep(await self.main.get_retry_after(resp))
                                elif status < 500:
                                    return None  # Only rate limits and server errors are temporary
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:  # Dropped connections are temporary, so keep checking
                print(f"\n❌ Special Event Checker Connection Error ❌\n{e}")
            except Exception as e:
                print(f"\n❌ Special Event Checker Failed ❌\n{e}")
                return
            await asyncio.sleep(random.uniform(0.5, 1.5))  # Short delay between checking channels to avoid rate-limiting
