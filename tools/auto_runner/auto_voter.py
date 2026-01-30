from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc  # MUST use undetected_chromedriver to bypass Cloudflare bot detection
import subprocess
import traceback
import random
import signal
import atexit
import time
import sys
import re

class AutoVoter():
    def __init__(self, unshuffled_tokens: list[str], tokens: list[str], windows_versions: list[str], browser_versions: list[str]):
        self.driver = None
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        self.TOKENS = unshuffled_tokens
        self.tokens = tokens
        self.WINDOWS_VERSIONS = windows_versions
        self.BROWSER_VERSIONS = browser_versions

    def get_chrome_major_version(self):
        commands = []
        if sys.platform.startswith("win"):  # Windows
            commands = [
                r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version',
                r'reg query "HKEY_LOCAL_MACHINE\Software\Google\Chrome\BLBeacon" /v version',
            ]
        elif sys.platform == "darwin":  # MacOS
            commands = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --version"
            ]
        else:  # Linux
            commands = [
                "google-chrome --version",
                "google-chrome-stable --version",
                "chromium-browser --version",
                "chromium --version",
            ]
        
        for cmd in commands:
            try:
                output = subprocess.check_output(
                    cmd, shell = True, stderr = subprocess.DEVNULL
                ).decode()
                match = re.search(r"(\d+)\.", output)
                if match:
                    return int(match.group(1))
            except Exception:
                pass

        print("ℹ️ Chrome version could not be detected. Loading Chrome may cause a version mismatch error.")
        return None

    def load_chrome(self):
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')  # Comment for non-headless mode if needed
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        
        windows_version = random.choice(self.WINDOWS_VERSIONS)
        browser_version = random.choice(self.BROWSER_VERSIONS)
        user_agent = (
            f"Mozilla/5.0 (Windows NT {windows_version}; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{browser_version} Safari/537.36 Brave/{browser_version}"  # Brave Browser - Windows 10/11 (Brave bypasses most Cloudflare detections)
        )
        options.add_argument(f'--user-agent={user_agent}')
        
        curr_chrome_version = self.get_chrome_major_version()
        if curr_chrome_version:
            self.driver = uc.Chrome(options = options, version_main = curr_chrome_version)
        else:
            # Attempt to open Chrome even if the version number couldn't be detected
            self.driver = uc.Chrome(options = options)

        # Wait for the browser to actually create a window/webview
        timeout = 15  # seconds
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                print("Waiting for browser to get ready...")
                handles = self.driver.window_handles  # Will raise if not ready
                if handles:
                    self.driver.switch_to.window(handles[0])
                    return
            except WebDriverException:
                pass
            time.sleep(1)
        
        # If browser didn't create a window in time
        try:
            self.driver.quit()
        except Exception:
            pass
        raise RuntimeError("Chrome started but no window was ready (timed out).")

    def is_login_button_present(self):
        try:
            _ = self.driver.find_element(By.XPATH, "//button[contains(., 'Log')]")
            return True
        except:
            return False

    def auto_vote(self, token: str):
        try:
            max_attempts = 10
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        print(f"  Retrying initialization: Attempt #{attempt + 1}/{max_attempts}")
                        if self.driver:
                            self.driver.quit()
                            self.driver = None
                        self.load_chrome()
                    else:
                        print(f"  Initializing Chrome: Attempt #1/{max_attempts}")
                    time.sleep(1)
                    
                    # Navigate to Discord login
                    self.driver.get("https://discord.com/login")
                    break
                except Exception as e:
                    if attempt >= max_attempts - 1:
                        print(f"  ❌ Error with Acccount #{self.TOKENS.index(token) + 1}:\n{e}")
                        return
                    if self.driver:
                        self.driver.quit()
                        self.driver = None
                    time.sleep(1)
            
            WebDriverWait(self.driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
            print("  Opened Discord")

            inject_token_script = f"""
                let token = "{token}";
                function login(token) {{
                    setInterval(() => {{
                        document.body.appendChild(document.createElement('iframe')).contentWindow.localStorage.token = `"${{token}}"`;
                    }}, 50);
                    setTimeout(() => {{
                        location.reload();
                    }}, 2500);
                }}
                login(token);
            """
            self.driver.execute_script(inject_token_script)
            print("  Injected token")

            # Force page refresh to ensure Discord has no loading errors
            time.sleep(8)
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            self.driver.refresh()

            # Wait for Discord to fully load
            WebDriverWait(self.driver, 15).until(lambda d: d.current_url == "https://discord.com/channels/@me")
            print("  Logged into Discord")
            time.sleep(1)  # Short delay to ensure Discord fully loads
            
            # Open top.gg
            self.driver.get("https://top.gg/bot/646937666251915264/vote")
            print("  Opened Top.gg")

            # Force page refresh to ensure Top.gg has no loading errors
            time.sleep(5)
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            self.driver.refresh()

            # Check if login button exists and click it (for loop to repeat unresponsive button clicks)
            for i in range(20):
                if self.is_login_button_present():
                    login_button = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Log')]")))
                    login_button.click()
                    print(f"  Clicked login button: Attempt #{i + 1}/20")
                else:
                    break
                time.sleep(1)
            
            # Force page refresh to ensure Discord authorization has no loading errors
            time.sleep(5)
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            self.driver.refresh()

            # Redirect to authorisation page
            WebDriverWait(self.driver, 15).until(lambda d: "https://discord.com/oauth2/authorize" in d.current_url)
            print("  Redirected to authorisation page")
            
            # Authorise
            self.driver.get(self.driver.current_url)
            discord_authorize_button = WebDriverWait(self.driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Auth')]")))
            discord_authorize_button.click()
            print("  Authorised Discord account")

            # Wait 10s (watch ad to vote)
            WebDriverWait(self.driver, 10).until(lambda d: d.current_url == "https://top.gg/bot/646937666251915264/vote")
            self.driver.get(self.driver.current_url)
            print("  Redirected to vote page, waiting 10s to vote..")
            time.sleep(10)

            try:
                WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'You have already voted')]")))
                print("  ℹ️ Already voted")
                return
            except:
                pass

            # Vote
            vote_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Vote')]")))
            vote_button.click()
            print("  Clicked vote button")

            # Check if voted successfully (long timeout because potential captcha)
            try:
                WebDriverWait(self.driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Thanks for voting!')]")))
                print("  ✅ Voted successfully")
            except:
                print("  ❌ Unexpected result after clicking vote")

        except Exception as e:
            print(f"  ❌ Error with Acccount #{self.TOKENS.index(token) + 1}:\n{e}")
            traceback.print_exc()
    
    def vote_setup(self, token: str, account: int):
        print("Loading new Undetected Chrome instance...")
        try:
            self.load_chrome()
        except Exception as e:
            input(f"\n⛔ Chrome Error ⛔\nChrome failed to open. Please ensure your Google Chrome is up-to-date.\n{e}")
            sys.exit()
        print(f"Auto-voting on Account #{self.TOKENS.index(token) + 1} ({account}/{len(self.tokens)})...")
        self.auto_vote(token)
        print("Closing Chrome...")
        self.driver.quit()

    def cleanup(self, *args):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
