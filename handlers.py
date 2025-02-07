import asyncio
import logging
import base58
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# Import configuration and initialize the bot
from config import BOT_TOKEN
from database import init_db
from wallet_management import show_root_wallet_menu, handle_root_wallet_action
from agent_management import show_agents_menu, show_agent_settings, create_new_agent, delete_agent_action, update_agent_name_action
from load_withdrawal import load_all_agents, load_to_agent, collect_agents_to_root, withdraw_from_root
from trading import run_user_trading

# Create bot and dispatcher instances
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# -------------------------------
# COMMAND HANDLERS
# -------------------------------

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    """
    Handler for the /start command.
    - Initializes the database.
    - Welcomes the user.
    - Displays the main menus (e.g. Root Wallet and Agent Management).
    """
    user_id = str(message.from_user.id)
    await init_db()
    await message.reply("Welcome! Use the menu below to manage your wallets and agents.")
    
    # Display the Root Wallet menu and the Agent Management menu (separately or combined as needed)
    await show_root_wallet_menu(user_id, bot)
    await show_agents_menu(user_id, bot)

@dp.message_handler(commands=["trading_on"])
async def cmd_trading_on(message: types.Message):
    """
    Command to start trading for all agent wallets.
    """
    user_id = str(message.from_user.id)
    await message.reply("Starting trading on all your agents...")
    asyncio.create_task(run_user_trading(user_id))

@dp.message_handler(commands=["trading_off"])
async def cmd_trading_off(message: types.Message):
    """
    Command to stop trading.
    (Note: Your trading loop should periodically check a shared flag to stop.)
    """
    # You might set an active trading flag here (see config.py: active_trading)
    user_id = str(message.from_user.id)
    # For example, if you maintain a dictionary `active_trading` in config.py:
    # from config import active_trading
    # active_trading[user_id] = False
    await message.reply("Trading has been stopped.")

# -------------------------------
# CALLBACK QUERY HANDLERS
# -------------------------------

@dp.callback_query_handler(lambda cq: cq.data.startswith("rw_"))
async def callback_root_wallet(cq: types.CallbackQuery):
    """
    Handles callback queries for root wallet actions.
    Expected callback data examples: "rw_gen", "rw_import", "rw_export", "rw_delete"
    """
    user_id = str(cq.from_user.id)
    action = cq.data.split("_", 1)[1]
    await handle_root_wallet_action(user_id, action, bot)
    await cq.answer()

@dp.callback_query_handler(lambda cq: cq.data == "new_agent")
async def callback_new_agent(cq: types.CallbackQuery):
    """
    Handles the creation of a new agent.
    This example simply asks the user to provide the agent name.
    A more complete implementation would store pending state to process the reply.
    """
    user_id = str(cq.from_user.id)
    await bot.send_message(user_id, "Please send the name for the new agent.")
    # (Store pending state if needed to capture the next message.)
    await cq.answer()

@dp.callback_query_handler(lambda cq: cq.data.startswith("delete_agent"))
async def callback_delete_agent(cq: types.CallbackQuery):
    """
    Handles deletion of an agent.
    Expected callback data: "delete_agent:<agent_name>"
    """
    user_id = str(cq.from_user.id)
    parts = cq.data.split(":", 1)
    if len(parts) > 1:
        agent_name = parts[1]
        await delete_agent_action(user_id, agent_name, bot)
    else:
        await bot.send_message(user_id, "No agent specified for deletion.")
    await cq.answer()

@dp.callback_query_handler(lambda cq: cq.data.startswith("agent_settings"))
async def callback_agent_settings(cq: types.CallbackQuery):
    """
    Handles the agent settings request.
    Expected callback data: "agent_settings:<agent_name>"
    """
    user_id = str(cq.from_user.id)
    parts = cq.data.split(":", 1)
    if len(parts) > 1:
        agent_name = parts[1]
        await show_agent_settings(user_id, agent_name, bot)
    else:
        await bot.send_message(user_id, "No agent specified.")
    await cq.answer()

@dp.callback_query_handler(lambda cq: cq.data.startswith("load_all"))
async def callback_load_all(cq: types.CallbackQuery):
    """
    Handles a callback to load funds to all agent wallets.
    For demonstration, the amount is hardcoded. In practice, you might prompt the user.
    """
    user_id = str(cq.from_user.id)
    amount = 0.1  # Example: 0.1 SOL per agent
    result = await load_all_agents(user_id, amount)
    await bot.send_message(user_id, f"Load Results:\n{result}")
    await cq.answer()

@dp.callback_query_handler(lambda cq: cq.data.startswith("collect_agents"))
async def callback_collect_agents(cq: types.CallbackQuery):
    """
    Handles the collection of funds from all agent wallets back to the root wallet.
    """
    user_id = str(cq.from_user.id)
    result = await collect_agents_to_root(user_id)
    await bot.send_message(user_id, f"Collection Results:\n{result}")
    await cq.answer()

@dp.callback_query_handler(lambda cq: cq.data.startswith("withdraw_from_root"))
async def callback_withdraw(cq: types.CallbackQuery):
    """
    Initiates the withdrawal process from the Root Wallet.
    For this demo, we simply prompt the user to send the withdrawal amount.
    """
    user_id = str(cq.from_user.id)
    await bot.send_message(user_id, "Please enter the SOL amount to withdraw from the Root Wallet.")
    await cq.answer()

# -------------------------------
# GENERAL MESSAGE HANDLER
# -------------------------------

@dp.message_handler()
async def handle_text(message: types.Message):
    """
    This handler catches all text messages that do not match a command.
    You can use this to capture input for pending actions (like new agent name,
    withdrawal amount, or wallet import keys) based on your stored state.
    
    For this example, we simply echo the user's message.
    """
    user_id = str(message.from_user.id)
    text = message.text.strip()
    
    # In a full implementation, you would check a pending state dictionary
    # (e.g., pending_new_agents, pending_wallet_import, etc.) and process accordingly.
    await message.reply(f"You said: {text}")

# -------------------------------
# MAIN EXECUTION
# -------------------------------

if __name__ == '__main__':
    # Start polling and skip any pending updates (if needed)
    executor.start_polling(dp, skip_updates=True)
