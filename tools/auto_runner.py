from auto_worker import AutoWorker
from auto_voter import AutoVoter
from datetime import datetime
import random
import asyncio
import ctypes
import time
import json
import sys

### To use this script, you must have a list of token(s) in tokens.json ###
### If you are using the Auto Worker, you must also have a list of drop channel IDs in config.py ###
class AutoRunner():
    def __init__(self):
        ### Feel free to customize these settings ###
        self.AUTO_VOTE = True  # (bool) Whether to run the auto voter
        self.AUTO_WORK = True  # (bool) Whether to do run the auto worker. Note that work permits and job boards must be set up on all accounts
        self.RAND_DELAY_MIN = 10  # (int) Minimum amount of minutes to wait between accounts
        self.RAND_DELAY_MAX = 20  # (int) Maximum amount of minutes to wait between accounts
        self.SHUFFLE_ACCOUNTS = True  # (bool) Whether to randomize the order of accounts when voting/working. I recommend keeping this setting `True`

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
                print("ℹ️ Accounts will run in a randomized order.\n")
            else:
                self.tokens = self.TOKENS
                print("ℹ️ Accounts will run in order.\n")
        else:
            input("⛔ Token Error ⛔\nNo tokens found. Please enter at least 1 token to vote/work with in tokens.json.")
            sys.exit()

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

        if not self.AUTO_VOTE and not self.AUTO_WORK:
            input("⛔ Configuration Error ⛔\nBoth self.AUTO_VOTE and self.AUTO_WORK are disabled. Please enable one to run this script.")
            sys.exit()
        if self.AUTO_VOTE:
            self.auto_voter = AutoVoter(self.TOKENS, self.tokens, self.WINDOWS_VERSIONS, self.BROWSER_VERSIONS)
            print("ℹ️ Auto voting is enabled.\n")
        if self.AUTO_WORK:
            self.auto_worker = AutoWorker(self.TOKENS, self.tokens, self.WINDOWS_VERSIONS, self.BROWSER_VERSIONS)
            print("ℹ️ Auto working is enabled.\n")

    def main(self):
        for account_idx in range(len(self.tokens)):
            print(f"{datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")

            token = self.tokens[account_idx]
            if self.AUTO_VOTE and self.AUTO_WORK:
                if random.choice([True, False]):  # 50% chance of working before and after voting
                    asyncio.run(self.auto_worker.auto_work(token, account_idx + 1))
                    delay = random.uniform(10, 120)  # Random delay
                    print(f"\nWaiting {round(delay)} seconds before voting...\n")
                    time.sleep(delay)
                    self.auto_voter.vote_setup(token, account_idx + 1)
                else:
                    self.auto_voter.vote_setup(token, account_idx + 1)
                    delay = random.uniform(10, 120)  # Random delay
                    print(f"\nWaiting {round(delay)} seconds before working...\n")
                    time.sleep(delay)
                    asyncio.run(self.auto_worker.auto_work(token, account_idx + 1))
            elif self.AUTO_VOTE and not self.AUTO_WORK:
                self.auto_voter.vote_setup(token, account_idx + 1)
            elif not self.AUTO_VOTE and self.AUTO_WORK:
                self.auto_worker.auto_work(token, account_idx + 1)

            delay = random.uniform(self.RAND_DELAY_MIN, self.RAND_DELAY_MAX) * 60  # Random delay between votes
            print(f"\nWaiting {round(delay / 60)} minutes before running on another account...\n")
            time.sleep(delay)

        input("✅ All accounts have been executed. Press `Enter` to exit.")
        sys.exit()

if __name__ == "__main__":
    RELAUNCH_FLAG = "--no-relaunch"
    if RELAUNCH_FLAG not in sys.argv:
        ctypes.windll.shell32.ShellExecuteW(
            None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, 1  # 0 = hidden, 1 = visible (recommended)
        )
        sys.exit()
    AutoRunner().main()