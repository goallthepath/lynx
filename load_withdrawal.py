import asyncio
import logging
import base58
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.publickey import PublicKey

from database import get_user_wallets, get_user_settings
from solana_integration import solana_client, get_sol_balance

async def load_all_agents(user_id: str, amount: float) -> str:
    """
    Transfer a specified amount of SOL from the root wallet to all agent wallets.
    
    :param user_id: Telegram user ID as a string.
    :param amount: Amount of SOL to send to each agent.
    :return: A summary string indicating the result for each agent.
    """
    wallets = await get_user_wallets(user_id)
    root = next((w for w in wallets if w.get("is_root")), None)
    agents = [w for w in wallets if w.get("is_agent")]
    if not root or not agents:
        logging.info("[Load] Missing root wallet or agent wallets.")
        return "Missing root wallet or agent wallets."
    root_key = Keypair.from_secret_key(base58.b58decode(root["base58_key"]))
    responses = []
    for agent in agents:
        agent_key = Keypair.from_secret_key(base58.b58decode(agent["base58_key"]))
        lamports = int(amount * 1_000_000_000)
        txn = Transaction()
        txn.add(transfer(TransferParams(
            from_pubkey=root_key.public_key,
            to_pubkey=agent_key.public_key,
            lamports=lamports
        )))
        try:
            resp = await solana_client.send_transaction(txn, root_key)
            logging.info(f"[Load] {amount:.4f} SOL sent from Root to Agent {agent_key.public_key}: {resp}")
            responses.append(f"Agent {agent['agent_name']}: Success")
        except Exception as e:
            logging.error(f"[Load] Error sending funds to agent {agent['agent_name']}: {e}")
            responses.append(f"Agent {agent['agent_name']}: Failed")
    return "\n".join(responses)

async def load_to_agent(user_id: str, agent_wallet: dict, amount: float) -> str:
    """
    Transfer a specified amount of SOL from the root wallet to a specific agent wallet.
    
    :param user_id: Telegram user ID as a string.
    :param agent_wallet: The agent wallet record (a dictionary) from the database.
    :param amount: Amount of SOL to send.
    :return: A result message indicating success or failure.
    """
    wallets = await get_user_wallets(user_id)
    root = next((w for w in wallets if w.get("is_root")), None)
    if not root:
        logging.info("[Load] No root wallet found.")
        return "No root wallet found."
    root_key = Keypair.from_secret_key(base58.b58decode(root["base58_key"]))
    agent_key = Keypair.from_secret_key(base58.b58decode(agent_wallet["base58_key"]))
    lamports = int(amount * 1_000_000_000)
    txn = Transaction()
    txn.add(transfer(TransferParams(
        from_pubkey=root_key.public_key,
        to_pubkey=agent_key.public_key,
        lamports=lamports
    )))
    try:
        resp = await solana_client.send_transaction(txn, root_key)
        logging.info(f"[Load] {amount:.4f} SOL sent from Root to Agent {agent_key.public_key}: {resp}")
        return f"{amount:.4f} SOL sent to Agent {agent_wallet['agent_name']}."
    except Exception as e:
        logging.error(f"[Load] Error sending funds to agent {agent_wallet['agent_name']}: {e}")
        return "Transfer failed. Check logs."

async def collect_agents_to_root(user_id: str) -> str:
    """
    Collect excess funds from each agent wallet and transfer them back to the root wallet.
    
    A minimum balance (set by MIN_BALANCE) is retained in each agent wallet.
    
    :param user_id: Telegram user ID as a string.
    :return: A summary string indicating the amount collected from each agent.
    """
    wallets = await get_user_wallets(user_id)
    root = next((w for w in wallets if w.get("is_root")), None)
    agents = [w for w in wallets if w.get("is_agent")]
    if not root:
        logging.info("[Collect] No Root Wallet found.")
        return "No Root Wallet found."
    if not agents:
        logging.info("[Collect] No Agent Wallets found.")
        return "No Agent Wallets found."
    try:
        root_key = Keypair.from_secret_key(base58.b58decode(root["base58_key"]))
    except Exception as e:
        logging.error(f"[Collect] Error decoding Root Wallet key: {e}")
        return "Error decoding Root Wallet key."
    
    results = []
    MIN_BALANCE = 0.001  # Keep a minimum balance in agents to cover fees
    for agent in agents:
        try:
            agent_key = Keypair.from_secret_key(base58.b58decode(agent["base58_key"]))
        except Exception as e:
            logging.error(f"[Collect] Error decoding key for agent '{agent.get('agent_name')}': {e}")
            results.append(f"Agent {agent.get('agent_name', 'Unknown')}: Key decode error")
            continue

        balance = await get_sol_balance(agent_key.public_key)
        if balance <= MIN_BALANCE:
            logging.info(f"[Collect] Agent {agent.get('agent_name')} has insufficient SOL: {balance:.6f} SOL")
            results.append(f"Agent {agent.get('agent_name')}: Insufficient balance")
            continue

        lamports = int((balance - MIN_BALANCE) * 1_000_000_000)
        txn = Transaction()
        txn.add(transfer(TransferParams(
            from_pubkey=agent_key.public_key,
            to_pubkey=root_key.public_key,
            lamports=lamports
        )))
        try:
            resp = await solana_client.send_transaction(txn, agent_key)
            logging.info(f"[Collect] Collected {lamports/1_000_000_000:.6f} SOL from Agent {agent_key.public_key} to Root: {resp}")
            results.append(f"Agent {agent.get('agent_name')}: {lamports/1_000_000_000:.6f} SOL")
        except Exception as e:
            logging.error(f"[Collect] Error transferring from Agent {agent.get('agent_name')}: {e}")
            results.append(f"Agent {agent.get('agent_name')}: Transfer failed")
    return "\n".join(results)

async def withdraw_from_root(user_id: str, amount: float) -> str:
    """
    Withdraw a specified amount of SOL from the root wallet to an external address.
    
    The external withdraw address is retrieved from the user's settings.
    
    :param user_id: Telegram user ID as a string.
    :param amount: Amount of SOL to withdraw.
    :return: A message indicating the success or failure of the withdrawal.
    """
    settings = await get_user_settings(user_id)
    withdraw_addr = settings.get("withdraw_address")
    if not withdraw_addr:
        logging.info("[Withdraw] Withdraw address not set.")
        return "Withdraw address not set."
    wallets = await get_user_wallets(user_id)
    root = next((w for w in wallets if w.get("is_root")), None)
    if not root:
        logging.info("[Withdraw] No root wallet found.")
        return "No root wallet found."
    root_key = Keypair.from_secret_key(base58.b58decode(root["base58_key"]))
    try:
        dest_pub = PublicKey(withdraw_addr)
    except Exception as e:
        logging.error(f"[Withdraw] Invalid withdraw address: {e}")
        return "Invalid withdraw address."
    lamports = int(amount * 1_000_000_000)
    txn = Transaction()
    txn.add(transfer(TransferParams(
        from_pubkey=root_key.public_key,
        to_pubkey=dest_pub,
        lamports=lamports
    )))
    try:
        resp = await solana_client.send_transaction(txn, root_key)
        return f"Withdrawal from Root successful! Tx: {resp}"
    except Exception as e:
        logging.error(f"[Withdraw] Error: {e}")
        return "Withdrawal failed. Check logs."
