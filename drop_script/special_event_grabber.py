from textwrap import dedent
import random
import asyncio
import aiohttp
import json
import sys

class SpecialEventGrabber():
    def __init__(self, main):
        self.main = main

        # Set up special event tokens dictionary
        try:
            with open("tokens/special_event_tokens.json", "r", encoding = "utf-8") as special_event_tokens_file:
                self.special_event_tokens_dict = json.load(special_event_tokens_file)
                example_special_event_tokens_dict = {
                    "any": "specialEventToken1",
                    "🌼": "specialEventToken2",
                }
                if not (
                    isinstance(self.special_event_tokens_dict, dict)
                    and all(isinstance(k, str) and isinstance(v, str) for k, v in self.special_event_tokens_dict.items())
                ):
                    input(
                        "\n⛔ Special Event Token Error ⛔\nExpected a dictionary with string keys and values.\n" +
                        dedent(
                            """
                            Example:
                            {
                                "any": "specialEventToken1", <- This token will grab the emojis that the other accounts do not grab
                                "🌼": "specialEventToken2"   <- This token will exclusively grab the 🌼 emoji
                            }"""
                        )
                    )
                    sys.exit()
                elif self.special_event_tokens_dict == {}:
                    input("\n⛔ Special Event Token Error ⛔\nNo values entered in special_event_tokens.json).\n" +
                                "If you wish to disable the Special Event Grabber, set self.SPECIAL_EVENT to False in config.py."
                    )
                    sys.exit()
                elif self.special_event_tokens_dict == example_special_event_tokens_dict:
                    input("\n⛔ Special Event Token Error ⛔\nPlease replace the example values in special_event_tokens.json with real tokens.\n" +
                                "If you wish to disable the Special Event Grabber, set self.SPECIAL_EVENT to False in config.py."
                    )
                    sys.exit()
                else:
                    asyncio.create_task(self.run_special_event_grabber())
                    print(f"\n👀 Watching for special event reactions in {len(self.main.DROP_CHANNEL_IDS)} script drop channel(s) " +
                            f"and {len(self.main.SERVER_ACTIVITY_DROP_CHANNEL_IDS)} server activity drop channel(s).")
        except FileNotFoundError:
            input("\n⛔ Special Event Token Error ⛔\nNo special_event_tokens.json file found.\n" +
                        "If you wish to disable the Special Event Grabber, set self.SPECIAL_EVENT to False in config.py."
            )
            sys.exit()
        except json.JSONDecodeError:
            input(
                "\n⛔ Special Event Token Error ⛔\nExpected a dictionary with string keys and values.\n" +
                dedent(
                    """
                    Example:
                    {
                        "any": "specialEventToken1", <- This token will grab the emojis that the other accounts do not grab
                        "🌼": "specialEventToken2"   <- This token will exclusively grab the 🌼 emoji
                    }"""
                )
            )
            sys.exit()

    async def add_special_event_reactions(self, channel_id: str, message: dict):
        try:
            msg_id = message.get('id')
            num_special_event_emojis = len(message.get('reactions')) - len(self.main.EMOJIS)  # num_special_event_emojis will be >= 1
            for i in range(1, num_special_event_emojis + 1):
                special_event_emoji = message.get('reactions')[-i].get('emoji').get('name')  # Get the ith last emoji (the event emoji)
                if special_event_emoji in self.special_event_tokens_dict:
                    token = self.special_event_tokens_dict.get(special_event_emoji)
                else:
                    token = self.special_event_tokens_dict.get("any", "")
                    if not token:  # If there is no token found for "any", return
                        return
                await self.main.add_reaction(token, 0, channel_id, msg_id, special_event_emoji, 0)  # 0 as account stub
        except KeyError:
            print(f"❌ [Special Event Account] Retrieve message failed: KeyError.")
            pass
        except IndexError:
            print(f"❌ [Special Event Account] Retrieve message failed: IndexError.")
            pass

    async def run_special_event_grabber(self):
         # history contains the messages that have been previously reacted to (key = message ID, value = number of emojis reacted)
         # Note that if the number of distinct emojis has changed, the message will be considered unseen! This way, if there are multiple special event emojis, all of them will be guaranteed to be grabbed.
        history: dict[str, int] = {} 
        special_event_tokens = list(self.special_event_tokens_dict.values())
        while True:
            try:
                for channel_id in self.main.SERVER_ACTIVITY_DROP_CHANNEL_IDS:
                    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=20"
                    headers = self.main.get_headers(random.choice(special_event_tokens), channel_id)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers = headers) as resp:
                            status = resp.status
                            if status == 200:
                                messages = await resp.json()
                                for msg in messages:
                                    msg_id = msg.get('id')
                                    num_reactions = len(msg.get('reactions', []))
                                    if all([
                                        (msg_id not in history or history.get(msg_id) != num_reactions),
                                        msg.get('author', {}).get('id') == self.main.KARUTA_BOT_ID,
                                        num_reactions > 3,  # 3 cards + special event emoji(s)
                                        (self.main.KARUTA_DROP_MESSAGE in msg.get('content', '') or self.main.KARUTA_SERVER_ACTIVITY_DROP_MESSAGE in msg.get('content', '')),
                                        self.main.KARUTA_EXPIRED_DROP_MESSAGE not in msg.get('content', '')
                                    ]):
                                        await self.add_special_event_reactions(channel_id, msg)
                                        history[msg_id] = num_reactions
                            else:
                                print(f"❌ [Special Event Account] Retrieve message failed: Error code {status}.")
                                return None
            except Exception as e:
                print(f"\n❌ Special Event Checker Failed ❌\n{e}")
                return
            await asyncio.sleep(random.uniform(0.5, 1.5))  # Short delay between checking channels to avoid rate-limiting
