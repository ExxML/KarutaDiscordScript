# Karuta Discord Script
Karuta Discord Script is a headless Python script for Windows that mimics realistic user behaviour to automatically drop and grab cards in Karuta, a Discord bot game.

While this script was originally designed for Karuta scripting, it can be easily adapted for other Discord self-bot purposes.


## Terminal Preview
![Karuta Script Preview](preview_images/drop_script_preview.png)


## ⚠️ WARNING ⚠️
Discord's Terms of Service explicitly prohibits self-bots (as of August 2025, and for the foreseeable future). Unauthorized use of this script *could* result in account bans. Use at your own risk.

*In my experience, no accounts using this script have been banned by Discord, but I still recommend using throwaway accounts just to be safe.*

Note: This script extracts user tokens from Discord accounts using Selenium and Undetected-ChromeDriver. To keep your accounts safe, DO NOT share these tokens (tokens.json) with anyone else.


## Setup (Do this first!)
1. Clone the repository.
2. Install Python 3.13.
3. Initialize a virtual environment, then install the required dependencies by running:
```bash
pip install -r requirements.txt
```
4. Ensure the Karuta drop mode (`kdropmode`) is set to reactions, NOT buttons, in ALL the drop channels.
5. All accounts must ONLY drop 3 cards, not 4. If an accounts drops 4 cards, the fourth card will not be auto-grabbed.
6. Create/buy accounts for the script to use! I **highly recommend** purchasing FULLY VERIFIED alt accounts from a trusted shop. A fully verified account means that it has a verified email AND phone number- a phone number connected to the account is imperative because Discord frequently phone-locks suspicious accounts. (You don't need to have access to the phone, it just needs to be connected to your account.)
    - If you decide to buy accounts, I recommend purchasing from https://shop.xyliase.com/product/discord-accounts-%7C-fully-verified-tokens (I am not affiliated with this shop). As of July 2025, there is plenty of cheap stock and customer service is excellent.
7. Edit the `__init__` constants in `config.py`.
- `self.COMMAND_USER_IDS` restricts message commands to these accounts- leave this list empty if you want to allow *any* user to send commands. `self.COMMAND_CHANNEL_IDS` are the channels where you are allowed to send message commands- leave this list empty if you want to disable commands entirely.
  - Read more about how to use message commands in Command Checker under Usage Tips/Features below.
- `self.DROP_CHANNEL_IDS` is a list of channels where the script will drop cards. 
  - **You MUST have at least 1 drop channel for every 3 accounts used.**
- `self.SERVER_ACTIVITY_DROP_CHANNEL_IDS` is used for two purposes:
  1. During a Karuta special event, the special event account will track these channels and automatically react to the special event emoji, whatever it happens to be.
  2. If CardCompanion is in use, the server drop account will also track these channels and automatically grab pog cards, if the setting is enabled.
  - Read more about how these two features work in Usage Tips/Features below.
8. Enter your accounts into the script. You can accomplish this via two ways:
    1. Enter your emails and passwords in `self.ACCOUNTS` in `token_extractor.py` using the following format, and then run `token_extractor.py`.
        ```python
        [{"email": "example_email@gmail.com", "password": "example_password"}, ... ]
        ```
    2. **OR**, you can enter your tokens as a list of strings in `tokens.json`. Leave the list in `tokens.json` empty if you would like to use the token extractor for account logins instead. 

    - **I recommend using tokens instead of account credentials so you can save time and avoid potential rate limiting.** If you don't have your tokens on hand, you can automatically extract and save your tokens to `tokens.json` by filling in your account credentials in `token_extractor.py`, setting `self.SAVE_TOKENS = True`, then running `token_extractor.py`.
9. Run `main.py`.

> [!TIP]
> For the script to auto-grab all dropped cards, the number of accounts you input must be a **multiple of 3** (3 accounts will *work together* in each drop channel). Make sure no accounts have 2FA enabled, and all accounts should have message access in all of `self.COMMAND_CHANNEL_IDS` and `self.DROP_CHANNEL_IDS` in `config.py`.


## Warnings

#### ⚠️ **DO NOT** run the drop script (`main.py`) for more than 10 consecutive hours or Karuta may flag your accounts for suspicious activity. Set `self.TIME_LIMIT_HOURS_MIN` and `self.TIME_LIMIT_HOURS_MAX` in `config.py` to control the time limit.
#### ⚠️ **DO NOT** run the account login script (`token_extractor.py`) too many times in a row because you will get login rate-limited by Discord Web. The cooldown after being rate-limited is typically a few hours.


## Usage Tips/Features
1. **Command Checker**
    - This script has a built-in command system that allows users to send messages, reactions, and button presses from any of the accounts in `tokens.json`.
    - In `config.py`, `self.COMMAND_USER_IDS` restricts the users who will be allowed to use commands. You can also set `self.COMMAND_CHANNEL_IDS` to an empty list to disable message commands entirely.
    - To send a command from any account, manually send a message from a `self.COMMAND_USER_IDS` account in any `self.COMMAND_CHANNEL_IDS` channel using the following format (without angle brackets):
        ```bash
        cmd <account_number |OR| account_number_range |OR| 'all'> <message>
        ```
        - Ex 1. `cmd all kcollection o:wishlist` sends `kcollection o:wishlist` from ALL accounts.
        - Ex 2. `cmd 1 kgive @ExxML <card_code>` sends a card transfer from Account #1 (the first account listed in `self.ACCOUNTS`). A few seconds after the transfer is sent, the script will automatically confirm the transfer (from Account #1).
        - Ex 3. Suppose `cmd 3 kmultitrade @ExxML`. After the trade items have been entered, type `cmd 3 /lock` to lock and confirm the trade (from Account #3).
        - Ex 4. Suppose `cmd 1 kmultiburn <filters>`. When you are FULLY READY to complete the multiburn, type `cmd 1 /burn` to confirm the multiburn.
        - Ex 5. `cmd 1 /b <emoji / label>` clicks the button on the most recent bot message (in self.INTERACTION_BOT_IDS) with the specified emoji OR label. For example, `cmd 1 /b ✅` or `cmd 1 /b I understand`.
        - Ex 6. `cmd 1 /r <emoji>` reacts to the most recent bot message (in self.INTERACTION_BOT_IDS) with the specified emoji. For example, `cmd 1 /r 💰`.
        - Ex 7. `cmd /pause` / `cmd /resume` pauses and resumes the script.
        - Ex 8. `cmd 1-10 kinventory` sends `kinventory` from Accounts #1-10.
> [!NOTE]
> - ONLY single account arguments work with `give`, `/lock` (for kmt), `/burn` (for kmb), `/b`, and `/r` commands. Account number ranges and `all` will not work with those commands.
> - If you mistype the account number for the `/lock` or `/burn` command, you must restart the trade/burn process. Sorry!
> - Automatic confirmation for the `kburn` command will not be supported. Use the `/b 🔥` command to manually confirm the burn, or use `kmultiburn` instead.

2. **Special Event Grabber**
    - If there is a special event going on in Karuta, you can set up an account to automatically react to the event emoji in all the drop channels and server activity drop channels.
    - To set this feature up:
      1. Set `self.SPECIAL_EVENT = True` in `config.py`
      2. Enter a **single** token (a string) in `special_event_token.json` to automatically react to drops with the event emoji. The token must, of course, have access to all `self.DROP_CHANNEL_IDS` and `self.SERVER_ACTIVITY_DROP_CHANNEL_IDS`.
      3. Enter the list of channels you want to track in `self.SERVER_ACTIVITY_DROP_CHANNEL_IDS`. Ignore the name of the constant; all drops in these channels will be tracked, regardless of whether they were generated by a user or from server activity.
    - When there is no special event, you should set `self.SPECIAL_EVENT = False` to avoid accidentally reacting to drops.


## Compatibility
- This script can be used in conjunction with [CardCompanion](https://top.gg/bot/1380936713639166082), a Discord bot that can analyze and notify you of rare cards being dropped. If a "pog card" is dropped (a card that matches a certain stat (ex. >1000 wl)), CardCompanion will include an emoji in the message (see red circle below), indicating which card is the "pog card". The script will then ensure the grabber of the card is the same as the dropper, boosting the card stats and avoiding suspicion. If CardCompanion is not being used OR a "pog card" was not dropped, the grabber will be randomized by default.

    ![Card Companion Preview](preview_images/card_companion_preview.png)
    - If you have set up CardCompanion and you want to ONLY grab pog cards (perhaps to make your stats look less suspicious), you can set `self.ONLY_GRAB_POG_CARDS` to `True` in `config.py`.

- The `/b` command can also be used on any bot buttons, not just Karuta. The list of allowed bots is set in `self.INTERACTION_BOT_IDS` in `command_checker.py`, which includes OwO by default.


## Auto-Runner Tool
A separate script from the drop script above that automatically votes/works on all the accounts.
1. Follow the Setup steps above to obtain a list of tokens in `tokens.json`, or manually paste your tokens in a list.
2. Follow the Setup steps below for the Auto-Voter and Auto-Worker.
3. Run `auto_runner.py`.
- If you wish, edit `self.RAND_DELAY_MIN` and `self.RAND_DELAY_MAX` to change the (randomized) time between votes/works.
- You may also edit `self.SHUFFLE_ACCOUNTS` depending on whether you want to randomize the order of accounts for voting/working. Generally, I would recommend keeping this setting `True`.

### Top.gg Auto-Voter Setup
1. Ensure your Chrome browser is up-to-date.
2. **DO NOT** use a VPN while running this script. Cloudflare (the service Top.gg uses) flags VPNs.

### Auto-Worker Setup
1. Set up work permits and job boards on all the acccounts.
2. Ensure you have listed at least one drop channel in `config.py`. A channel in `self.DROP_CHANNEL_IDS` will be randomly selected to work in for every account.
