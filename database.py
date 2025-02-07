import asyncpg
import logging
from typing import List, Dict, Optional
from config import DATABASE_URL

# Global variable for the database pool
db_pool: asyncpg.Pool = None

async def init_db():
    """
    Initialize the database by creating necessary tables and adding
    additional columns if they do not exist.
    """
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with db_pool.acquire() as conn:
        # Create the wallets table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                user_id TEXT,
                wallet_index INT,
                base58_key TEXT,
                is_root BOOLEAN DEFAULT FALSE,
                is_agent BOOLEAN DEFAULT FALSE,
                agent_name TEXT DEFAULT NULL,
                PRIMARY KEY (user_id, wallet_index)
            )
        """)
        # Attempt to add extra columns (ignore error if they already exist)
        for cmd in [
            "ALTER TABLE wallets ADD COLUMN is_agent BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE wallets ADD COLUMN agent_name TEXT DEFAULT NULL;"
        ]:
            try:
                await conn.execute(cmd)
            except asyncpg.exceptions.DuplicateColumnError:
                pass

        # Create the settings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id TEXT PRIMARY KEY,
                token_address TEXT DEFAULT ''
            )
        """)
        # Add extra columns to settings if needed
        for col_def in [
            "fixed_buy FLOAT DEFAULT 0.0",
            "fixed_sell_delay INT DEFAULT 0",
            "take_profit FLOAT DEFAULT 0.0",
            "use_take_profit BOOLEAN DEFAULT FALSE",
            "randomizer BOOLEAN DEFAULT TRUE",
            "fee FLOAT DEFAULT 0.0",
            "tip FLOAT DEFAULT 0.0",
            "buy_slippage FLOAT DEFAULT 0.0",
            "sell_slippage FLOAT DEFAULT 0.0",
            "withdraw_address TEXT DEFAULT ''",
            "referrer_id TEXT DEFAULT ''",
            "referral_earnings FLOAT DEFAULT 0.0"
        ]:
            try:
                await conn.execute(f"ALTER TABLE settings ADD COLUMN {col_def};")
            except asyncpg.exceptions.DuplicateColumnError:
                pass

        # Create the agent_settings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_settings (
                user_id TEXT,
                agent_name TEXT,
                fixed_buy FLOAT DEFAULT 0.0,
                fixed_sell_delay INT DEFAULT 0,
                buy_slippage FLOAT DEFAULT 0.0,
                sell_slippage FLOAT DEFAULT 0.0,
                tip FLOAT DEFAULT 0.0,
                PRIMARY KEY (user_id, agent_name)
            )
        """)
        # Add extra columns to agent_settings if needed
        for col_def in [
            "fixed_rest_delay INT DEFAULT 0",
            "sell_enabled BOOLEAN DEFAULT TRUE"
        ]:
            try:
                await conn.execute(f"ALTER TABLE agent_settings ADD COLUMN {col_def};")
            except asyncpg.exceptions.DuplicateColumnError:
                pass

async def get_user_wallets(user_id: str) -> List[Dict]:
    """
    Retrieve all wallet records for a given user.
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT wallet_index, base58_key, is_root, is_agent, agent_name
            FROM wallets WHERE user_id = $1 ORDER BY wallet_index
        """, user_id)
    return [dict(r) for r in rows]

async def add_user_wallet(user_id: str, base58_key: str, is_root: bool = False,
                          is_agent: bool = False, agent_name: Optional[str] = None):
    """
    Insert a new wallet record into the database for the given user.
    """
    wallets = await get_user_wallets(user_id)
    next_index = len(wallets)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wallets (user_id, wallet_index, base58_key, is_root, is_agent, agent_name)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, user_id, next_index, base58_key, is_root, is_agent, agent_name)

async def remove_user_wallet(user_id: str, index: int):
    """
    Remove a wallet identified by its user and wallet index.
    """
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM wallets WHERE user_id = $1 AND wallet_index = $2
        """, user_id, index)

async def get_root_wallet(user_id: str) -> Optional[Dict]:
    """
    Retrieve the root wallet for a given user.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT wallet_index, base58_key FROM wallets
            WHERE user_id = $1 AND is_root = TRUE
        """, user_id)
    return dict(row) if row else None

async def add_root_wallet(user_id: str, base58_key: str):
    """
    Create a new root wallet for the user, replacing any existing one.
    """
    await delete_root_wallet(user_id)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wallets (user_id, wallet_index, base58_key, is_root)
            VALUES ($1, (SELECT COALESCE(MAX(wallet_index), 0) + 1 FROM wallets WHERE user_id = $1), $2, TRUE)
        """, user_id, base58_key)

async def delete_root_wallet(user_id: str):
    """
    Delete the root wallet for the given user.
    """
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM wallets WHERE user_id = $1 AND is_root = TRUE
        """, user_id)

async def get_agents(user_id: str) -> List[Dict]:
    """
    Retrieve all agent wallets for the given user.
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT wallet_index, base58_key, agent_name FROM wallets
            WHERE user_id = $1 AND is_agent = TRUE ORDER BY wallet_index
        """, user_id)
    return [dict(r) for r in rows]

async def get_agent_settings(user_id: str, agent_name: str) -> dict:
    """
    Retrieve agent-specific settings. If none exist, a default record is inserted.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT fixed_buy, fixed_sell_delay,
                   buy_slippage, sell_slippage, tip,
                   fixed_rest_delay, sell_enabled
            FROM agent_settings WHERE user_id = $1 AND agent_name = $2
        """, user_id, agent_name)
        if not row:
            await conn.execute("""
                INSERT INTO agent_settings (user_id, agent_name) VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, user_id, agent_name)
            return {
                "fixed_buy": 0.0,
                "fixed_sell_delay": 0,
                "buy_slippage": 0.0,
                "sell_slippage": 0.0,
                "tip": 0.0,
                "fixed_rest_delay": 0,
                "sell_enabled": True
            }
        return dict(row)

async def update_agent_settings(user_id: str, agent_name: str, column: str, value):
    """
    Update a specific setting for an agent.
    """
    async with db_pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE agent_settings SET {column} = $1 WHERE user_id = $2 AND agent_name = $3
        """, value, user_id, agent_name)

async def add_agent(user_id: str, agent_name: str, copy_from: Optional[str] = None):
    """
    Add a new agent wallet. Optionally copy settings from an existing agent.
    Note: This function generates a new keypair for the agent.
    """
    import base58
    from solana.keypair import Keypair
    kp = Keypair()
    agent_b58 = base58.b58encode(kp.secret_key).decode("utf-8")
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wallets (user_id, wallet_index, base58_key, is_agent, agent_name)
            VALUES ($1, (SELECT COALESCE(MAX(wallet_index), 0) + 1 FROM wallets WHERE user_id = $1), $2, TRUE, $3)
        """, user_id, agent_b58, agent_name)
        await conn.execute("""
            INSERT INTO agent_settings (user_id, agent_name) VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, user_id, agent_name)
    if copy_from:
        source_settings = await get_agent_settings(user_id, copy_from)
        for col in ["fixed_buy", "fixed_sell_delay", "buy_slippage", "sell_slippage", "tip", "fixed_rest_delay", "sell_enabled"]:
            await update_agent_settings(user_id, agent_name, col, source_settings[col])

async def update_agent_name(user_id: str, old_agent_name: str, new_agent_name: str):
    """
    Update the name of an agent in both wallets and agent_settings tables.
    """
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE wallets SET agent_name = $1 WHERE user_id = $2 AND agent_name = $3
        """, new_agent_name, user_id, old_agent_name)
        await conn.execute("""
            UPDATE agent_settings SET agent_name = $1 WHERE user_id = $2 AND agent_name = $3
        """, new_agent_name, user_id, old_agent_name)

async def delete_agent(user_id: str, agent_name: str):
    """
    Remove an agent wallet and its settings.
    """
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM wallets WHERE user_id = $1 AND agent_name = $2
        """, user_id, agent_name)
        await conn.execute("""
            DELETE FROM agent_settings WHERE user_id = $1 AND agent_name = $2
        """, user_id, agent_name)

async def get_user_settings(user_id: str) -> dict:
    """
    Retrieve the global settings for a given user. If not set, default settings are inserted.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT token_address, fixed_buy, fixed_sell_delay,
                   buy_slippage, sell_slippage, tip, withdraw_address,
                   referrer_id, referral_earnings
            FROM settings WHERE user_id = $1
        """, user_id)
        if not row:
            await conn.execute("INSERT INTO settings (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
            return {
                "token_address": "",
                "fixed_buy": 0.0,
                "fixed_sell_delay": 0,
                "buy_slippage": 0.0,
                "sell_slippage": 0.0,
                "tip": 0.0,
                "withdraw_address": "",
                "referrer_id": "",
                "referral_earnings": 0.0
            }
        return dict(row)

async def update_user_settings(user_id: str, column: str, value):
    """
    Update a global setting for the user.
    """
    async with db_pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE settings SET {column} = $1 WHERE user_id = $2
        """, value, user_id)
