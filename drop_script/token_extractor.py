from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium import webdriver
import random
import ctypes
import math
import json
import sys

class TokenExtractor():
    def __init__(self):
        ### The number of accounts entered should be a multiple of 3 or else the script will not be able to auto-grab all dropped cards!
        # List your accounts (separated by commas) in the format: [{"email": "example_email@gmail.com", "password": "example_password"}, ... ]
        # LEAVE THE LIST IN `tokens.json` EMPTY if you would like to use account logins (below) instead.
        self.ACCOUNTS = [
        ]
        self.SAVE_TOKENS = True  # (bool) Choose whether to save tokens to file (tokens.json)

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

    def load_chrome(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')  # Comment for non-headless mode if needed
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        windows_version = random.choice(self.WINDOWS_VERSIONS)
        browser_version = random.choice(self.BROWSER_VERSIONS)
        user_agent = (
            f"Mozilla/5.0 (Windows NT {windows_version}; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{browser_version} Safari/537.36 Brave/{browser_version}"
        )
        options.add_argument(f'--user-agent={user_agent}')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service = service, options = options)
        
        # Webdriver spoofer
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })

        # Spoof canvas
        canvas_script = """
        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const ctx = originalGetContext.call(this, type, ...args);
            if (type === '2d') {
                const originalGetImageData = ctx.getImageData;
                ctx.getImageData = function(x, y, w, h) {
                    const imageData = originalGetImageData.call(this, x, y, w, h);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] ^ 1;
                    }
                    return imageData;
                }
            }
            return ctx;
        };
        """
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": canvas_script})

    def extract_discord_token(self, email: str, password: str):
        try:
            # Navigate to Discord login
            self.driver.get("https://discord.com/login")
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
            print("  Login page loaded")
            # Find login fields and submit
            email_field = self.driver.find_element(By.NAME, "email")
            password_field = self.driver.find_element(By.NAME, "password")
            email_field.send_keys(email)
            password_field.send_keys(password)
            print("  Filled in credentials")
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            print("  Clicked log in")
            WebDriverWait(self.driver, 15).until(lambda d: "/login" not in d.current_url)
            print("  Discord loaded")
            
            # Update page to extract token from app
            self.driver.get("https://discord.com/app")

            # Execute JS to grab token from local storage
            token = self.driver.execute_script("return window.localStorage.getItem('token');")
            if token:
                print("  Token extracted")
                return token[1:-1]  # Trim quotes
            else:
                print(f"  No token found for {email}")
                return None
        except Exception as e:
            print(f"Error with {email}: {str(e)}")
            return None

    def main(self, standalone: bool, num_channels: int):
        # If this script is executed standalone, do not perform checks
        if not standalone:
            if self.TOKENS:
                print("ℹ️ Using tokens (from tokens.json) instead of account logins...")
                num_accounts = len(self.TOKENS)
            else:
                print("ℹ️ Using account logins instead of tokens...")
                num_accounts = len(self.ACCOUNTS)
        else:
            print("ℹ️ Extracting tokens using account logins...")
            num_accounts = len(self.ACCOUNTS)

        if num_accounts == 0:
            input("\n⛔ Account Error ⛔\nNo accounts found. Please enter at least 1 account in token_extractor.py (if you want to extract tokens) or tokens.json.")
            sys.exit()

        # If this script is executed standalone, do not perform checks
        if not standalone:
            if self.TOKENS:
                num_channels_need = math.ceil(len(self.TOKENS) / 3)  # Maximum 3 accounts per channel
            else:
                num_channels_need = math.ceil(len(self.ACCOUNTS) / 3)  # Maximum 3 accounts per channel
            if num_channels_need != num_channels:
                input(f"\n⛔ Configuration Error ⛔\nYou have entered {num_channels} drop channel(s). You must have {num_channels_need} channel(s).")
                sys.exit()

            if num_accounts % 3 != 0:
                input(f"\n⚠️ Configuration Warning ⚠️\nThe number of accounts you entered is not a multiple of 3." +
                        f"\nThe script will only be able to auto-grab {(num_accounts * 3) - 2}/{num_accounts * 3} dropped cards. Press `Enter` if you wish to continue.")

            if self.TOKENS:
                return self.TOKENS

        # Executes if using account logins
        tokens = []
        for index, account in enumerate(self.ACCOUNTS):
            print("\nLoading new Chrome...")
            self.load_chrome()
            print(f"Processing {index + 1}/{len(self.ACCOUNTS)}: {account['email']}...")
            token = self.extract_discord_token(account["email"], account["password"])
            print("Closing Chrome...")
            self.driver.quit()
            if token:
                tokens.append(token)

        num_tokens = len(tokens)
        if num_tokens == 0:
            input("\n⛔ Token Error ⛔\nNo tokens found. Please check your account info.")
            sys.exit()
        elif num_tokens != len(self.ACCOUNTS):
            input(f"\n⚠️ Configuration Warning ⚠️\nYou entered {len(self.ACCOUNTS)} accounts, but only {num_tokens} tokens were found.\nPress `Enter` if you wish to continue.")
        
        if self.SAVE_TOKENS:
            with open("tokens/tokens.json", "w") as tokens_file:
                json.dump(tokens, tokens_file)
                print("\nℹ️ Tokens saved to tokens.json")

        return tokens

if __name__ == "__main__":
    RELAUNCH_FLAG = "--no-relaunch"
    if RELAUNCH_FLAG not in sys.argv:
        ctypes.windll.shell32.ShellExecuteW(
            None, None, sys.executable, " ".join(sys.argv + [RELAUNCH_FLAG]), None, 1  # 0 = hidden, 1 = visible (recommended)
        )
        sys.exit()
    token_extractor = TokenExtractor()
    token_extractor.main(standalone = True, num_channels = None)