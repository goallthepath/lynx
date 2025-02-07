import asyncio
import aiohttp
import base64
import logging
from typing import Optional

from solana.transaction import Transaction
from solana.rpc.types import TxOpts
from solana.keypair import Keypair

# Import configuration constants from config.py
from config import JUPITER_QUOTE_URL, JUPITER_SWAP_URL, DEFAULT_SLIPPAGE, HTTP_TIMEOUT

# Import the Solana client from your Solana integration module.
# (Ensure that solana_integration.py exports 'solana_client'.)
from solana_integration import solana_client


async def jupiter_get_quote(input_mint: str, output_mint: str, amount: int, slippage: float, max_retries: int = 5) -> dict:
    """
    Retrieve a swap quote from the Jupiter API with exponential backoff on rate limiting.

    :param input_mint: Mint address of the token you are swapping from.
    :param output_mint: Mint address of the token you are swapping to.
    :param amount: The amount in base units to swap.
    :param slippage: Slippage in percentage points.
    :param max_retries: Maximum number of retry attempts.
    :return: A dictionary containing the quote data or an empty dict on failure.
    """
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": str(int(slippage * 100)),
        "restrictIntermediateTokens": "false"
    }
    attempt = 0
    while attempt < max_retries:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(JUPITER_QUOTE_URL, params=params, timeout=HTTP_TIMEOUT) as resp:
                    status = resp.status
                    data = await resp.json()
                    logging.debug(f"[jupiter_get_quote] HTTP status: {status}")
                    if status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        logging.warning(f"[jupiter_get_quote] Rate limit exceeded. Retrying after {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        attempt += 1
                        continue
                    elif status != 200:
                        logging.error(f"[jupiter_get_quote] Unexpected status code: {status} - {data}")
                        return {}
                    logging.debug(f"[jupiter_get_quote] Response data: {data}")
                    if not data or "routePlan" not in data:
                        logging.error(f"[jupiter_get_quote] Quote unsuccessful: {data}")
                        return {}
                    return data
        except Exception as e:
            logging.error(f"[jupiter_get_quote] Error on attempt {attempt+1}: {e}")
            await asyncio.sleep(2 ** attempt)
            attempt += 1

    logging.error("[jupiter_get_quote] Maximum retries reached. Returning empty quote.")
    return {}


async def jupiter_swap(user_keypair: Keypair, swap_response: dict, wallet: str,
                       wrapAndUnwrapSol: bool = True,
                       useSharedAccounts: bool = False,
                       asLegacyTransaction: bool = True,
                       **kwargs) -> Optional[str]:
    """
    Execute a swap using the Jupiter API.

    :param user_keypair: Keypair object representing the user's wallet.
    :param swap_response: The quote response obtained from Jupiter.
    :param wallet: The wallet address (string) for signing the transaction.
    :param wrapAndUnwrapSol: Whether to wrap/unwrap SOL if needed.
    :param useSharedAccounts: Whether to use shared accounts.
    :param asLegacyTransaction: Whether to send the transaction as legacy.
    :param kwargs: Additional parameters to pass in the payload.
    :return: The transaction signature if successful, otherwise None.
    """
    payload = {
        "userPublicKey": wallet,
        "wrapAndUnwrapSol": wrapAndUnwrapSol,
        "useSharedAccounts": useSharedAccounts,
        "asLegacyTransaction": asLegacyTransaction,
        "quoteResponse": swap_response
    }
    payload.update(kwargs)
    logging.debug(f"[jupiter_swap] Swap payload: {payload}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                JUPITER_SWAP_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=HTTP_TIMEOUT
            ) as resp:
                logging.debug(f"[jupiter_swap] HTTP status: {resp.status}")
                data = await resp.json()
        logging.debug(f"[jupiter_swap] Swap response data: {data}")
        tx_b64 = data.get("swapTransaction")
        if not tx_b64:
            logging.error(f"[jupiter_swap] No swapTransaction in response: {data}")
            return None
        # Decode and deserialize the transaction
        tx_bytes = base64.b64decode(tx_b64)
        tx = Transaction.deserialize(tx_bytes)
        # Ensure the transaction has a recent blockhash if missing
        if not tx.recent_blockhash:
            recent = await solana_client.get_recent_blockhash()
            if "result" in recent and "value" in recent["result"]:
                tx.recent_blockhash = recent["result"]["value"]["blockhash"]
        tx.sign(user_keypair)
        raw_tx = tx.serialize()
        tx_sig = await solana_client.send_raw_transaction(raw_tx, opts=TxOpts(skip_preflight=True))
        logging.debug(f"[jupiter_swap] Transaction signature: {tx_sig}")
        return tx_sig
    except Exception as e:
        logging.error(f"[jupiter_swap] Swap failed: {e}")
        return None


async def buy_token_jupiter(wallet_kp: Keypair, token_address: str, amount_sol: float) -> Optional[tuple]:
    """
    Buy tokens by swapping SOL for a target token using the Jupiter API.
    
    :param wallet_kp: Keypair object of the wallet performing the swap.
    :param token_address: The target token's mint address.
    :param amount_sol: The amount of SOL to spend.
    :return: A tuple (transaction_signature, output_amount) if successful, otherwise None.
    """
    lamports = int(amount_sol * 1_000_000_000)
    logging.debug(f"[buy_token_jupiter] Converting {amount_sol} SOL to {lamports} lamports")
    if lamports < 100_000:
        logging.info("[buy_token_jupiter] Amount too small")
        return None
    input_mint = "So11111111111111111111111111111111111111112"
    output_mint = token_address
    quote = await jupiter_get_quote(input_mint, output_mint, lamports, DEFAULT_SLIPPAGE)
    logging.debug(f"[buy_token_jupiter] Received quote: {quote}")
    if not quote:
        logging.error("[buy_token_jupiter] Empty quote")
        return None

    out_amount_str = quote.get("outAmount")
    try:
        out_amount = int(out_amount_str)
    except Exception as e:
        logging.error(f"[buy_token_jupiter] Error converting outAmount: {e}")
        out_amount = 0

    tx_sig = await jupiter_swap(wallet_kp, quote, str(wallet_kp.public_key),
                                wrapAndUnwrapSol=True,
                                useSharedAccounts=False,
                                asLegacyTransaction=True)
    if tx_sig:
        logging.info(f"[buy_token_jupiter] Jupiter Swap TX: {tx_sig}")
        return (tx_sig, out_amount)
    else:
        logging.error("[buy_token_jupiter] Jupiter Swap failed.")
        return None


async def sell_token_jupiter(wallet_kp: Keypair, token_mint: str, amount: int) -> Optional[str]:
    """
    Sell tokens by swapping the target token for SOL using the Jupiter API.

    :param wallet_kp: Keypair object of the wallet performing the swap.
    :param token_mint: The mint address of the token to sell.
    :param amount: The amount (in base units) of the token to sell.
    :return: The transaction signature if successful, otherwise None.
    """
    input_mint = token_mint
    output_mint = "So11111111111111111111111111111111111111112"
    quote = await jupiter_get_quote(input_mint, output_mint, amount, DEFAULT_SLIPPAGE)
    logging.debug(f"[sell_token_jupiter] Received quote: {quote}")
    if not quote:
        logging.error("[sell_token_jupiter] Empty quote")
        return None
    tx_sig = await jupiter_swap(wallet_kp, quote, str(wallet_kp.public_key),
                                wrapAndUnwrapSol=True,
                                useSharedAccounts=False,
                                asLegacyTransaction=True)
    if tx_sig:
        logging.info(f"[sell_token_jupiter] Jupiter Swap TX: {tx_sig}")
    else:
        logging.error("[sell_token_jupiter] Jupiter Swap failed.")
    return tx_sig
