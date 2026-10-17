"""
Telegram bot: sends notifications to the user and handles their commands
(/today, /status, /pending, /approve, /skip, etc.).

Setup (free, ~2 minutes):
1. Open Telegram, message @BotFather
2. Send /newbot, follow the prompts, choose any name/username
3. BotFather gives you a token like "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
4. Put that in your .env file as TELEGRAM_BOT_TOKEN=...
5. Message your new bot once (anything) so it can find your chat_id
6. Run: python -m notifications.telegram_bot --get-chat-id
   to print your chat_id, then put it in .env as TELEGRAM_CHAT_ID=...

This module is a thin wrapper -- all the actual message text is built by
notifications/message_formatting.py, which is unit-tested separately.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root into os.environ

logger = logging.getLogger(__name__)

try:
    from telegram import Bot
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TelegramNotifier:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self._bot = None

        if not TELEGRAM_AVAILABLE:
            logger.warning(
                "python-telegram-bot not installed. Run: pip install python-telegram-bot"
            )
        elif not self.bot_token or not self.chat_id:
            logger.warning(
                "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env -- "
                "notifications will be logged but not sent."
            )

    @property
    def is_configured(self) -> bool:
        return TELEGRAM_AVAILABLE and bool(self.bot_token) and bool(self.chat_id)

    def _get_bot(self):
        if self._bot is None and TELEGRAM_AVAILABLE:
            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def send(self, text: str) -> bool:
        """Sends a message. Returns True on success, False if not configured
        or the send fails -- never raises, so one failed notification never
        crashes the agent."""
        if not self.is_configured:
            logger.info("Telegram not configured. Would have sent:\n%s", text)
            return False
        try:
            bot = self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id, text=text,
                parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
            )
            return True
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return False


async def _print_chat_id():
    """Helper to discover your chat_id: message the bot once first, then
    run this."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in your .env first.")
        return
    bot = Bot(token=token)
    updates = await bot.get_updates()
    if not updates:
        print("No messages found. Send any message to your bot on Telegram first, then rerun this.")
        return
    chat_id = updates[-1].message.chat.id
    print(f"Your chat_id is: {chat_id}")
    print("Add this to your .env as: TELEGRAM_CHAT_ID=" + str(chat_id))


if __name__ == "__main__":
    import sys
    import asyncio
    if "--get-chat-id" in sys.argv:
        asyncio.run(_print_chat_id())