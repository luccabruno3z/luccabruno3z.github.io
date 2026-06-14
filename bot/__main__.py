"""Allow running the bot as `python -m bot`."""

from bot.main import main
import asyncio

asyncio.run(main())
