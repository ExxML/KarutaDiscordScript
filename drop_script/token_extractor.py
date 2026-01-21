from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import math
import json
import random

class TokenExtractor():
    def __init__(self):
        ### The number of accounts entered should be a multiple of 3 or else the script will not be able to auto-grab all dropped cards!
        # List your accounts (separated by commas) in the format: {"email": "example_email@gmail.com", "password": "example_password"}, ...
        # LEAVE THE LIST IN `tokens.json` EMPTY if you would like to use account logins (below) instead.
        self.ACCOUNTS = [
        ]

        self.SAVE_TOKENS = True  # (bool) Choose whether to save tokens to file (tokens.json)

        try:
            with open("tokens.json", "r") as tokens_file:
                self.TOKENS = json.load(tokens_file)
                if not isinstance(self.TOKENS, list) or not all(isinstance(token, str) for token in self.TOKENS):
                    input('⛔ Token Format Error ⛔\nExpected a list of strings. Example: ["token1", "token2", "token3"]')
                    sys.exit()
        except (FileNotFoundError, json.JSONDecodeError):
            self.TOKENS = []

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

    def main(self, num_channels: int, windows_versions: list[str], browser_versions: list[str]):
        self.WINDOWS_VERSIONS = windows_versions
        self.BROWSER_VERSIONS = browser_versions
        if self.TOKENS:
            print("ℹ️ Using tokens (from tokens.json) instead of account logins...")
            num_accounts = len(self.TOKENS)
        else:
            print("ℹ️ Using account logins instead of tokens...")
            num_accounts = len(self.ACCOUNTS)

        if num_accounts == 0:
            input("\n⛔ Account Error ⛔\nNo accounts found. Please enter at least 1 account in token_extractor.py or tokens.json.")
            sys.exit()
        
        if self.TOKENS:
            num_channels_need = math.ceil(len(self.TOKENS) / 3)  # Maximum 3 accounts per channel
        else:
            num_channels_need = math.ceil(len(self.ACCOUNTS) / 3)  # Maximum 3 accounts per channel
        if num_channels_need != num_channels:
            input(f"\n⛔ Configuration Error ⛔\nYou have entered {num_channels} drop channel(s). You should have {num_channels_need} channel(s).")
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
            with open("tokens.json", "w") as tokens_file:
                json.dump(tokens, tokens_file)
                print("\nℹ️ Tokens saved to tokens.json")

        return tokens