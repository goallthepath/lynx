import logging
from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey
from config import SOLANA_RPC

# Initialize the asynchronous Solana client using the RPC URL from the configuration.
solana_client = AsyncClient(SOLANA_RPC)

async def get_token_balance(owner: PublicKey, token_mint: str) -> float:
    """
    Retrieve the token balance (in UI units) for the specified owner and token mint.
    
    :param owner: PublicKey object representing the wallet owner.
    :param token_mint: The mint address (as a string) of the token.
    :return: The token balance in UI-friendly units (floating point value).
    """
    try:
        response = await solana_client.get_token_accounts_by_owner(
            owner,
            {"mint": token_mint},
            "jsonParsed"
        )
        token_accounts = response.get("result", {}).get("value", [])
        balance = 0.0
        for token_account in token_accounts:
            parsed_info = token_account["account"]["data"]["parsed"]
            # Get the UI amount (if available) and add it to the balance.
            amount = parsed_info["info"]["tokenAmount"].get("uiAmount", 0)
            balance += amount
        logging.debug(f"[get_token_balance] Balance for {owner} (mint {token_mint}): {balance}")
        return balance
    except Exception as e:
        logging.error(f"[get_token_balance] Error retrieving token balance: {e}")
        return 0.0

async def get_sol_balance(pubkey: PublicKey) -> float:
    """
    Retrieve the SOL balance for the provided public key.
    
    :param pubkey: PublicKey object for which to retrieve the SOL balance.
    :return: The balance in SOL (converted from lamports to SOL).
    """
    try:
        resp = await solana_client.get_balance(pubkey)
        # Convert lamports (1_000_000_000 lamports = 1 SOL) to SOL.
        balance = resp.value / 1_000_000_000
        logging.debug(f"[get_sol_balance] Balance for {pubkey}: {balance} SOL")
        return balance
    except Exception as e:
        logging.error(f"[get_sol_balance] Error retrieving SOL balance for {pubkey}: {e}")
        return 0.0
