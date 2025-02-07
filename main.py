import asyncio
from aiogram import executor
from database import init_db
import handlers  # This import registers all command and callback handlers with the Dispatcher

async def main():
    # Initialize the database (this creates tables, etc.)
    await init_db()
    
    # Optionally, you can perform any additional initialization here.
    
    # Start polling for updates.
    # The `handlers` module should already have created and configured the Dispatcher (dp).
    executor.start_polling(handlers.dp, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
