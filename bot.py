import logging
import random
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import threading

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable not set")
    exit(1)

PORT = int(os.environ.get("PORT", 8080))
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "running", "message": "Bot is running!"})

DEPOSIT_ADDRESSES = [
    "UQCgPsBnvSib5rYln5vK0rNfYo__xjfk5OD-0mKU7-n1ACnT",
    "UQCCTTF03CCeyNKov1azQty5iNcNMnwH72J7pcb7MUaDKXsd",
    "UQAZjMCIT6MEMUgvKmweTySPrGqxnUrgvG5JQVUfnR-d_tke",
]

user_deposit_data = {}

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
                first_name=user.first_name
            )
        return self.users[user.id]

user_manager = UserManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_manager.get_or_create_user(update)
    keyboard = [[InlineKeyboardButton("💰 Deposit", callback_data="deposit")]]
    await update.message.reply_text(f"Welcome {user.first_name}!", reply_markup=InlineKeyboardMarkup(keyboard))

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = random.choice(DEPOSIT_ADDRESSES)
    user_id = update.effective_user.id
    user_deposit_data[user_id] = {'address': addr, 'status': 'waiting'}
    msg = f"Send TON to:\n`{addr}`\nMin 15 TON"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "deposit":
        await deposit_command(update, context)

async def main():
    print("Starting bot...")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("Bot is polling...")
    while True:
        await asyncio.sleep(3600)

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
