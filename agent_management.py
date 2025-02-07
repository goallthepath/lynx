import base58
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from solana.keypair import Keypair

from database import get_agents, get_agent_settings, add_agent, update_agent_name, delete_agent
from solana_integration import get_sol_balance
from config import BANNER_URL

# ----------------------------------------------------------------
# MENU BUILDERS
# ----------------------------------------------------------------

def agents_main_menu() -> InlineKeyboardMarkup:
    """
    Build and return the inline keyboard markup for Agent Management.
    """
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ New Agent", callback_data="new_agent"),
        InlineKeyboardButton("❌ Delete Agent", callback_data="delete_agent")
    )
    kb.add(
        InlineKeyboardButton("🪄 Start Lynx", callback_data="start_agents"),
        InlineKeyboardButton("💫 Exit Lynx", callback_data="stop_agents")
    )
    kb.add(
        InlineKeyboardButton("⚙️ Agent Settings", callback_data="agent_settings_select")
    )
    return kb

def agent_settings_menu(agent_name: str) -> InlineKeyboardMarkup:
    """
    Build and return the inline keyboard markup for configuring an agent's settings.
    """
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Fixed Buy Amount 💸", callback_data=f"set:fixed_buy:{agent_name}"),
        InlineKeyboardButton("Fixed Sell Delay ⏱️", callback_data=f"set:fixed_sell_delay:{agent_name}")
    )
    kb.add(
        InlineKeyboardButton("Buy Slippage (%) 📉", callback_data=f"set:buy_slippage:{agent_name}"),
        InlineKeyboardButton("Sell Slippage (%) 📈", callback_data=f"set:sell_slippage:{agent_name}")
    )
    kb.add(
        InlineKeyboardButton("Tip (SOL) 💵", callback_data=f"set:tip:{agent_name}")
    )
    kb.add(
        InlineKeyboardButton("Fixed Rest Delay ⏳", callback_data=f"set:fixed_rest_delay:{agent_name}"),
        InlineKeyboardButton("Toggle Sell Function 🚫", callback_data=f"toggle:sell_enabled:{agent_name}")
    )
    return kb

# ----------------------------------------------------------------
# DISPLAY FUNCTIONS
# ----------------------------------------------------------------

async def show_agents_menu(user_id: str, bot):
    """
    Retrieve all agent wallets for a user and send a message listing them with the management menu.

    :param user_id: Telegram user ID as a string.
    :param bot: Instance of the aiogram Bot.
    """
    agents = await get_agents(user_id)
    text = "<b>Agent Management</b>\n\n"
    if not agents:
        text += "No agents available. Click 'New Agent' to create one."
    else:
        for agent in agents:
            try:
                kp = Keypair.from_secret_key(base58.b58decode(agent["base58_key"]))
                balance = await get_sol_balance(kp.public_key)
                text += f"• <b>{agent['agent_name']}</b> - Balance: {balance:.4f} SOL\n"
            except Exception as e:
                logging.error(f"[show_agents_menu] Error retrieving data for agent {agent.get('agent_name')}: {e}")
                text += f"• <b>{agent['agent_name']}</b>: (Error retrieving data)\n"
    await bot.send_message(user_id, text, reply_markup=agents_main_menu())

async def show_agent_settings(user_id: str, agent_name: str, bot):
    """
    Retrieve and display settings for a specific agent, along with an inline keyboard to update those settings.

    :param user_id: Telegram user ID as a string.
    :param agent_name: The name of the agent whose settings are to be displayed.
    :param bot: Instance of the aiogram Bot.
    """
    settings = await get_agent_settings(user_id, agent_name)
    text = (
        f"<b>Agent Settings - {agent_name}</b>\n\n"
        f"Fixed Buy Amount: {settings['fixed_buy']} SOL\n"
        f"Fixed Sell Delay: {settings['fixed_sell_delay']} sec\n"
        f"Buy Slippage: {settings['buy_slippage']}%\n"
        f"Sell Slippage: {settings['sell_slippage']}%\n"
        f"Tip: {settings['tip']} SOL\n"
        f"Fixed Rest Delay: {settings.get('fixed_rest_delay', 0)} sec\n"
        f"Sell Function: {'ENABLED' if settings.get('sell_enabled', True) else 'DISABLED'}"
    )
    await bot.send_message(user_id, text, reply_markup=agent_settings_menu(agent_name))

# ----------------------------------------------------------------
# AGENT ACTIONS (Creation, Update, Deletion)
# ----------------------------------------------------------------

async def create_new_agent(user_id: str, agent_name: str, copy_from: str = None, bot=None):
    """
    Create a new agent wallet for the user. Optionally, copy settings from an existing agent.

    :param user_id: Telegram user ID as a string.
    :param agent_name: The new agent's name.
    :param copy_from: (Optional) Name of an existing agent to copy settings from.
    :param bot: (Optional) Bot instance to send notifications.
    """
    await add_agent(user_id, agent_name, copy_from)
    if bot:
        await bot.send_message(user_id, f"✅ New agent <b>{agent_name}</b> created successfully!")
    # Optionally, you can show the updated agents menu:
    # await show_agents_menu(user_id, bot)

async def update_agent_name_action(user_id: str, old_agent_name: str, new_agent_name: str, bot):
    """
    Update the name of an existing agent.
    
    :param user_id: Telegram user ID as a string.
    :param old_agent_name: The current agent name.
    :param new_agent_name: The new agent name to update to.
    :param bot: Instance of the aiogram Bot.
    """
    await update_agent_name(user_id, old_agent_name, new_agent_name)
    await bot.send_message(user_id, f"✅ Agent name changed from <b>{old_agent_name}</b> to <b>{new_agent_name}</b>.")
    await show_agent_settings(user_id, new_agent_name, bot)

async def delete_agent_action(user_id: str, agent_name: str, bot):
    """
    Delete the specified agent wallet and its settings.
    
    :param user_id: Telegram user ID as a string.
    :param agent_name: The name of the agent to delete.
    :param bot: Instance of the aiogram Bot.
    """
    await delete_agent(user_id, agent_name)
    await bot.send_message(user_id, f"❌ Agent <b>{agent_name}</b> deleted successfully.")
    await show_agents_menu(user_id, bot)
