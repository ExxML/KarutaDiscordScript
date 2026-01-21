import aiohttp
import asyncio
import random
import base64
import json
import sys
import ctypes

class MessageGrabber():
    def __init__(self):
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
        try:
            with open("tokens/tokens.json", "r") as tokens_file:
                self.TOKENS = json.load(tokens_file)
                if not isinstance(self.TOKENS, list) or not all(isinstance(token, str) for token in self.TOKENS):
                    input('⛔ Token Format Error ⛔\nExpected a list of strings. Example: ["exampleToken1", "exampleToken2", "exampleToken3"]')
                    sys.exit()
                elif self.TOKENS == ["exampleToken1", "exampleToken2", "exampleToken3", "..."]:
                    input('⛔ Token Format Error ⛔\nPlease replace the example tokens in tokens.json with your real tokens.')
                    sys.exit()
        except (FileNotFoundError, json.JSONDecodeError):
            self.TOKENS = []

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
    
    async def get_message(self, token: str, msg_id: str, channel_id: str):
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100"
        headers = self.get_headers(token, channel_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = headers) as resp:
                status = resp.status
                if status == 200:
                    messages = await resp.json()
                    try:
                        for msg in messages:
                            # OBSERVE: The list of messages contains the n = 100 most recent messages in the channel
                            # OBSERVE: The list of messages is sorted by newest first (highest message ID first)
                            if msg.get('id') == msg_id:
                                print(f"✅ Message Found:\n{msg}\n")
                                return
                    except (KeyError, IndexError):
                        pass
                else:
                    print(f"❌ Retrieve message failed: Error code {status}.\n")
                    return
                print(f"❌ Retrieve message failed: Message '{msg_id}' was not found in 100 recent messages.\n")

if __name__ == "__main__":
    RELAUNCH_FLAG = "--no-relaunch"
    if RELAUNCH_FLAG not in sys.argv:
        ctypes.windll.shell32.ShellExecuteW(
            None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, 1  # 0 = hidden, 1 = visible (recommended)
        )
        sys.exit()
    
    message_grabber = MessageGrabber()

    while True:
        print("\n=== Message Grabber ===\n")
        msg_id = input("Enter the message ID:\n")
        channel_id = input("Enter the channel ID:\n")
        asyncio.run(message_grabber.get_message(random.choice(message_grabber.TOKENS), msg_id, channel_id))
