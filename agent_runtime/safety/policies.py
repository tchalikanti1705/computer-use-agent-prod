GLOBAL_BLOCKED_DOMAINS = {"darkweb.onion"}
BLOCKED_COMMANDS = {"rm -rf /", "mkfs", "dd if=", "shutdown", "reboot", ":(){ :|:& };:"}
RISKY_KEYWORDS = {"delete","remove","submit","purchase","buy","pay","transfer","send","confirm","share","upload","logout","sign out","password","credit card"}
SAFE_ACTIONS = {"screenshot", "wait", "move"}
MAX_ACTIONS_PER_STEP = 10
