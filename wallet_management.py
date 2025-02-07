import base58
import logging
from solana.keypair import Keypair
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot

from solana_integration import get_sol_balance
from database import get_user_wallets, add_root_wallet, delete_root_wallet, remove_user_wallet
from config import BANNER_URL

# ----------------------------------------------------------------
# Root Wallet Menu Functions
# ----------------------------------------------------------------

def root_wallet_menu() -> InlineKeyboardMarkup:
    """
    Build and return the inline keyboard markup for Root Wallet management.
    """
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔄 Generate New Root Wallet", callback_data="rw_gen"))
    kb.add(InlineKeyboardButton("🔑 Import Root Wallet", callback_data="rw_import"))
    kb.add(InlineKeyboardButton("🔐 Export Private Key", callback_data="rw_export"))
    kb.add(InlineKeyboardButton("❌ Delete Root Wallet", callback_data="rw_delete"))
    return kb


async def show_root_wallet_menu(user_id: str, bot: Bot):
    """
    Retrieve the root wallet information for the given user and send it to the user with the management menu.
    
    :param user_id: Telegram user ID as a string.
    :param bot: Instance of the aiogram Bot.
    """
    wallets = await get_user_wallets(user_id)
    # Find the wallet marked as the root wallet.
    root = next((w for w in wallets if w.get("is_root")), None)
    if root:
        try:
            root_key = Keypair.from_secret_key(base58.b58decode(root["base58_key"]))
            balance = await get_sol_balance(root_key.public_key)
            text = (
                f"<b>💰 Root Wallet</b>\n"
                f"Address: <code>{root_key.public_key}</code>\n"
                f"Balance: {balance:.4f} SOL\n\n"
                "Please choose an option:"
            )
        except Exception as e:
            logging.error(f"[show_root_wallet_menu] Error decoding wallet: {e}")
            text = "❌ Error retrieving wallet information."
    else:
        text = "⚠️ No Root Wallet found. Please generate or import one."
    
    # You might choose to send a banner with the message.
    # For example, if you have a helper function send_with_banner, you can use it instead.
    await bot.send_message(user_id, text, reply_markup=root_wallet_menu())


# ----------------------------------------------------------------
# Root Wallet Action Handler
# ----------------------------------------------------------------

async def handle_root_wallet_action(user_id: str, action: str, bot: Bot):
    """
    Handle actions related to root wallet management based on the provided action string.
    
    :param user_id: Telegram user ID as a string.
    :param action: A string indicating the action (e.g., "gen", "import", "export", "delete").
    :param bot: Instance of the aiogram Bot.
    """
    if action == "gen":
        # Generate a new root wallet by first deleting any existing one.
        await delete_root_wallet(user_id)
        root_kp = Keypair()
        root_b58 = base58.b58encode(root_kp.secret_key).decode("utf-8")
        await add_root_wallet(user_id, root_b58)
        await bot.send_message(user_id, "✅ New Root Wallet generated successfully!")
        await show_root_wallet_menu(user_id, bot)

    elif action == "import":
        # Set a flag or prompt the user to send their private key.
        # (In a full implementation, you might store a pending import state.)
        await bot.send_message(user_id, "📌 Please send your Private Key to import your Root Wallet.")

    elif action == "export":
        wallets = await get_user_wallets(user_id)
        root = next((w for w in wallets if w.get("is_root")), None)
        if not root:
            await bot.send_message(user_id, "❌ No Root Wallet found.")
            return
        private_key = root["base58_key"]
        text = (
            f"🔐 <b>Your Private Key:</b>\n"
            f"<tg-spoiler>{private_key}</tg-spoiler>\n\n"
            "⚠️ Please keep it safe!\nClick below once saved."
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("✅ Saved", callback_data="mm_overview"))
        await bot.send_message(user_id, text, reply_markup=kb)

    elif action == "delete":
        wallets = await get_user_wallets(user_id)
        for w in wallets:
            if w.get("is_root"):
                await remove_user_wallet(user_id, w["wallet_index"])
        await bot.send_message(user_id, "❌ Root Wallet deleted.")
        await show_root_wallet_menu(user_id, bot)
