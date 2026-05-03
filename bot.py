import logging
import random
import os
from dataclasses import dataclass
from typing import Dict

from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

PORT = int(os.environ.get("PORT", 8080))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

app = Flask(__name__)

DEPOSIT_ADDRESSES = [
    "UQCgPsBnvSib5rYln5vK0rNfYo__xjfk5OD-0mKU7-n1ACnT",
    "UQCCTTF03CCeyNKov1azQty5iNcNMnwH72J7pcb7MUaDKXsd",
    "UQAZjMCIT6MEMUgvKmweTySPrGqxnUrgvG5JQVUfnR-d_tke",
]

user_deposit_data: Dict[int, Dict[str, str]] = {}

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    ton_balance: float = 0.0

class UserManager:
    def __init__(self):
        self.users: Dict[int, UserData] = {}

    def get_or_create_user(self, update: Update) -> UserData:
        user = update.effective_user
        if user.id not in self.users:
            self.users[user.id] = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "User"
            )
        return self.users[user.id]

user_manager = UserManager()

application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_manager.get_or_create_user(update)
    keyboard = [[InlineKeyboardButton("💰 Deposit", callback_data="deposit")]]
    await update.message.reply_text(
        f"Welcome {user.first_name}!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = random.choice(DEPOSIT_ADDRESSES)
    user_id = update.effective_user.id
    user_deposit_data[user_id] = {"address": addr, "status": "waiting"}

    msg = f"Send TON to:
<code>{addr}</code>
Min 15 TON"

    if update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="HTML")
    else:
        await update.message.reply_text(msg, parse_mode="HTML")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "deposit":
        await deposit_command(update, context)

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("deposit", deposit_command))
application.add_handler(CallbackQueryHandler(handle_callback))

@app.route("/")
def home():
    return jsonify({"status": "running", "message": "Bot is running!"})

@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.post(f"/{BOT_TOKEN}")
async def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return ("", 200)

if __name__ == "__main__":
    import asyncio

    async def startup():
        await application.initialize()
        if RENDER_EXTERNAL_URL:
            webhook_url = f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"
            await application.bot.set_webhook(webhook_url)
            logger.info("Webhook set to %s", webhook_url)
        await application.start()
        logger.info("Bot started")

    asyncio.run(startup())
    app.run(host="0.0.0.0", port=PORT)
