class Config():
    def __init__(self):
        ### CUSTOMIZE THESE SETTINGS ###
        # Enter a list of strings containing the user IDs that can use message commands. Leave the list empty to allow any account to use commands.
        self.COMMAND_USER_IDS = [
            "",
        ]
        # Enter your command channels (where commands are allowed to be sent) as a list of strings. Leave the list empty to disable message commands.
        self.COMMAND_CHANNEL_IDS = [
            "",
        ]
        # Enter your drop channels as a list of strings. You MUST have at least 1 drop channel for every 3 accounts used.
        self.DROP_CHANNEL_IDS = [
            "",
        ]
        # Enter your server activity drop channels as a list of strings (for reacting to drops with the special event emoji during Karuta events). 
        # Only used if self.SPECIAL_EVENT = True or self.GRAB_SERVER_POG_CARDS = True for their respective purposes.
        self.SERVER_ACTIVITY_DROP_CHANNEL_IDS = [
            "",
        ]
        self.TERMINAL_VISIBILITY = 1  # 0 = hidden, 1 = visible (recommended)
        self.KARUTA_PREFIX = "k"  # (str) Karuta's bot prefix.
        self.SHUFFLE_ACCOUNTS = True  # (bool) Improve randomness by shuffling accounts across channels every time the script runs.
        self.RATE_LIMIT = 3  # (int) Maximum number of rate limits before giving up.
        self.DROP_FAIL_LIMIT = 5  # (int) Maximum number of failed drops across all channels before pausing script. Set to -1 if you wish to disable this limit.
        self.TIME_LIMIT_HOURS_MIN = 6  # (int/float) MINIMUM time limit in hours before script automatically pauses (to avoid ban risk).
        self.TIME_LIMIT_HOURS_MAX = 10  # (int/float) MAXIMUM time limit in hours before script automatically pauses (to avoid ban risk).
        self.CHANNEL_SKIP_RATE = 8  # (int) Every time the script runs, there is a 1/self.CHANNEL_SKIP_RATE chance of skipping a channel. Set to -1 if you wish to disable skipping.
        self.DROP_SKIP_RATE = 12  # (int) For every drop, there is a 1/self.DROP_SKIP_RATE chance of skipping the drop. Set to -1 if you wish to disable it skipping.
        self.ONLY_GRAB_POG_CARDS = False  # (bool) Determines whether to ONLY grab pog cards (as defined by CardCompanion). IF CARDCOMPANION IS NOT SET UP, SET THIS TO FALSE, or else no cards will be grabbed.
        self.RANDOM_COMMAND_RATE = 480  # (int) Every 2-3 seconds, there is a 1/self.RANDOM_COMMAND_RATE chance of sending a random command.
        self.SPECIAL_EVENT = False  # (bool) Whether the script will use the tokens in special_event_tokens.json to auto-react with the event emoji during Karuta special events.