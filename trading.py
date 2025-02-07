import asyncio
import logging
import base58

from solana.keypair import Keypair

# Import functions from other modules
from solana_integration import get_sol_balance
from jupiter_integration import buy_token_jupiter, sell_token_jupiter
from database import get_agent_settings, get_user_settings, get_user_wallets

# Import global state variables and (optionally) the bot instance.
# Note: In your project, you may choose to inject a notification function instead of importing a global bot.
from config import active_trading, agent_last_buy

# If you have a globally available bot instance, you might import it here.
# For example, if your bot instance is stored in config, uncomment the following line:
# from config import bot


async def run_wallet_cycle(user_id: str, wallet_kp: Keypair, token_address: str, agent_name: str):
    """
    Continuously perform a buy-then-sell cycle for an agent wallet.

    This function checks the agent's settings (such as fixed buy amount, delays, and sell enable flag),
    verifies sufficient SOL balance in the wallet, executes a buy transaction using Jupiter API, and
    later (if enabled) sells the tokens acquired.

    :param user_id: The Telegram user ID as a string.
    :param wallet_kp: The agent's Solana Keypair.
    :param token_address: The token's contract (mint) address.
    :param agent_name: The name assigned to this agent.
    """
    # Construct a key for storing the last buy amount for this agent.
    agent_key = f"{user_id}_{agent_name}"
    
    while active_trading.get(user_id, False):
        # Retrieve agent-specific settings (e.g., fixed buy amount, delays, slippage, etc.)
        agent_settings = await get_agent_settings(user_id, agent_name)
        fixed_buy = agent_settings.get("fixed_buy", 0)
        fixed_sell_delay = agent_settings.get("fixed_sell_delay", 0)
        fixed_rest_delay = agent_settings.get("fixed_rest_delay", 0)
        sell_enabled = agent_settings.get("sell_enabled", True)
        
        logging.debug(
            f"[Cycle] Agent {agent_name} settings: fixed_buy={fixed_buy} SOL, "
            f"fixed_sell_delay={fixed_sell_delay} sec, fixed_rest_delay={fixed_rest_delay} sec, "
            f"sell_enabled={sell_enabled}"
        )
        
        if fixed_buy <= 0:
            logging.error(f"[Cycle] Fixed buy amount not set for agent '{agent_name}' (user {user_id}).")
            await asyncio.sleep(5)
            continue

        sol_balance = await get_sol_balance(wallet_kp.public_key)
        logging.debug(f"[Cycle] Wallet {wallet_kp.public_key} SOL balance: {sol_balance:.4f} SOL")
        if sol_balance < fixed_buy:
            logging.info(
                f"[Cycle] Insufficient SOL in wallet {wallet_kp.public_key} (Balance: {sol_balance:.4f} SOL), waiting for funds."
            )
            await asyncio.sleep(5)
            continue

        # Execute the buy transaction via Jupiter API.
        buy_result = await buy_token_jupiter(wallet_kp, token_address, fixed_buy)
        if buy_result:
            tx_buy, out_amount = buy_result
            logging.info(f"[Cycle] Buy transaction executed for wallet {wallet_kp.public_key}: {tx_buy}")
            # (Optional) Notify the user—if you have a bot instance, for example:
            # await bot.send_message(user_id, f"🟢 <b>[BUY]</b> Agent <code>{agent_name}</code> bought tokens.\nTransaction: <code>{tx_buy}</code>")
            agent_last_buy[agent_key] = out_amount
        else:
            logging.error(f"[Cycle] Buy transaction failed for wallet {wallet_kp.public_key}.")
            # (Optional) Notify the user:
            # await bot.send_message(user_id, f"❌ <b>[BUY]</b> Agent <code>{agent_name}</code> failed to buy tokens.")
            await asyncio.sleep(1)
            continue

        if sell_enabled:
            # Wait for the specified sell delay before selling.
            await asyncio.sleep(fixed_sell_delay)
            stored_amount = agent_last_buy.get(agent_key, 0)
            if stored_amount > 0:
                tx_sell = await sell_token_jupiter(wallet_kp, token_address, stored_amount)
                if tx_sell:
                    logging.info(f"[Cycle] Sell transaction executed for wallet {wallet_kp.public_key}: {tx_sell}")
                    # (Optional) Notify the user:
                    # await bot.send_message(user_id, f"🔴 <b>[SELL]</b> Agent <code>{agent_name}</code> sold tokens (amount: {stored_amount}).\nTransaction: <code>{tx_sell}</code>")
                    agent_last_buy[agent_key] = 0
                else:
                    logging.error(f"[Cycle] Sell transaction failed for wallet {wallet_kp.public_key}.")
                    # (Optional) Notify the user:
                    # await bot.send_message(user_id, f"❌ <b>[SELL]</b> Agent <code>{agent_name}</code> failed to sell tokens.")
            else:
                logging.info(f"[Cycle] No stored buy amount for agent {agent_name}; skipping sell.")
                # (Optional) Notify the user:
                # await bot.send_message(user_id, f"❌ <b>[SELL]</b> Agent <code>{agent_name}</code> has no buy amount stored to sell.")
        else:
            logging.info(f"[Cycle] Sell function disabled for agent {agent_name}. Skipping sell transaction.")
            # (Optional) Notify the user:
            # await bot.send_message(user_id, f"ℹ️ <b>[SELL]</b> Agent <code>{agent_name}</code> sell function is disabled.")
        
        # Wait for the fixed rest delay before starting the next cycle.
        await asyncio.sleep(fixed_rest_delay if fixed_rest_delay > 0 else 1)


async def run_user_trading(user_id: str):
    """
    Start the trading cycle for all agent wallets associated with a user.

    This function retrieves the user's global settings to get the token (contract) address
    and then iterates over each agent wallet to start its trading cycle.
    
    :param user_id: The Telegram user ID as a string.
    """
    # Retrieve the token (contract) address from user settings.
    user_settings = await get_user_settings(user_id)
    token_address = user_settings.get("token_address")
    if not token_address:
        logging.info(f"[Trading] No token (contract) set for user {user_id}.")
        return

    # Retrieve all wallets for the user and filter for agent wallets.
    wallets = await get_user_wallets(user_id)
    for wallet in wallets:
        if wallet.get("is_agent"):
            try:
                wallet_kp = Keypair.from_secret_key(base58.b58decode(wallet["base58_key"]))
            except Exception as e:
                logging.error(f"[Trading] Error decoding agent wallet key: {e}")
                continue
            agent_name = wallet.get("agent_name")
            # Start the wallet cycle for the agent as an asynchronous task.
            asyncio.create_task(run_wallet_cycle(user_id, wallet_kp, token_address, agent_name))
            await asyncio.sleep(1)  # Stagger the start time for each agent
