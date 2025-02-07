import os
import logging
from typing import Dict, List

# ----------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------

# Database and Bot Settings
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://your:DatabaseURL@localhost/dbname"
)
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "Your Bot Token"
)

# Solana and Jupiter API Endpoints
SOLANA_RPC = "https://api.mainnet-beta.solana.com"  # Mainnet RPC URL
JUPITER_QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
JUPITER_SWAP_URL = "https://api.jup.ag/swap/v1/swap"

# Swap and HTTP Settings
DEFAULT_SLIPPAGE = 20            # expressed in percentage points (e.g., 20 = 20%)
HTTP_TIMEOUT = 10                # in seconds

# Visuals and Referral
BANNER_URL = "Telegram Banner Image URL"
REFERRAL_BASE = "https://example.com/referral?user="

# Other Constants

# ----------------------------------------------------------------
# LOGGING SETUP
# ----------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ----------------------------------------------------------------
# GLOBAL STATE VARIABLES
# ----------------------------------------------------------------

# Used to track the last buy amounts for each agent (key format: "userID_agentName")
agent_last_buy: Dict[str, int] = {}

# Dictionaries for pending updates and state management
pending_agent_updates: Dict[str, Dict[str, str]] = {}
pending_token_update: Dict[str, bool] = {}
pending_settings_update: Dict[str, Dict[str, str]] = {}
pending_new_agents: Dict[str, Dict[str, str]] = {}
pending_load_commands: Dict[str, Dict[str, str]] = {}
pending_wallet_import: Dict[str, bool] = {}

# For managing asynchronous tasks and trading states
user_tasks: Dict[str, List] = {}       # Could be List[asyncio.Task] when imported
active_trading: Dict[str, bool] = {}
transaction_messages: Dict[str, Dict[str, int]] = {}
last_banner_message: Dict[str, int] = {}
