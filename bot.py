import logging
import random
import string
import asyncio
import os
from datetime import datetime, time, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable not set")
    # Don't proceed without token
    exit(1)

PORT = int(os.environ.get("PORT", 8080))

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "running", "message": "Bot is running!"})

@app.route('/health')
def health():
    return "OK", 200

# Card data
CARD_BINS = {
    "USD": ["435880xx", "491277xx", "511332xx", "428313xx", "520356xx", "409758xx", "525362xx", "451129xx", "434340xx", "426370xx", "411810xx", "403446xx", "533621xx", "446317xx", "457824xx", "545660xx", "432465xx", "516612xx", "484718xx", "485246xx", "402372xx", "457851xx"],
    "CAD": ["533985xx", "461126xx"],
    "AUD": ["373778xx", "377935xx", "375163xx"]
}

CAD_BINS = ["533985xx", "461126xx"]
AUD_BINS = ["373778xx", "377935xx", "375163xx"]

DEPOSIT_ADDRESSES = [
    "UQCgPsBnvSib5rYln5vK0rNfYo__xjfk5OD-0mKU7-n1ACnT",
    "UQCCTTF03CCeyNKov1azQty5iNcNMnwH72J7pcb7MUaDKXsd",
    "UQAZjMCIT6MEMUgvKmweTySPrGqxnUrgvG5JQVUfnR-d_tke",
    "UQBwwD_2VekRaM-7_6wwltzkboxbTiYDqif40G9Tbnq76Td1",
    "UQAMBt7k1FZHvewkpB1IHMLiOMLZR63rO_NKv-fiQ0n5EGW_",
    "UQC9OvldFlHMbxKRq-6yRTm9uWv-YWFcsywHQAZz6p9dtonc"
]

user_deposit_data = {}

@dataclass
class Card:
    card_number: str
    currency: str
    amount: float
    sticker: str = ""
    is_registered: bool = True
    is_out_of_stock: bool = False

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    ton_balance: float = 0.0
    usd_balance: float = 0.0
    total_deposits_ton: float = 0.0
    total_deposits_usd: float = 0.0
    last_deposit: str = "Never"
    purchase_count: int = 0
    usd_spent: float = 0.0
    purchased_cards: List[str] = field(default_factory=list)
    referrals_count: int = 0
    referred_by: str = ""
    referral_link: str = ""
    pending_deposit: Optional[Dict] = None

class CardGenerator:
    def __init__(self):
        self.cards: List[Card] = []

    def generate_cards(self) -> List[Card]:
        cards = []
        for _ in range(150):
            card_num = ''.join(random.choices(string.digits, k=16))
            amount = round(random.uniform(10, 500), 2)
            cards.append(Card(card_num, "USD", amount, "", True, False))
        return cards

    async def update_cards(self):
        self.cards = self.generate_cards()
        print(f"Generated {len(self.cards)} cards")

    def get_cards_paginated(self, page: int, per_page: int = 10, filter_type: str = None) -> Tuple[List[Card], int]:
        if not self.cards:
            return [], 0
        filtered = self.cards
        total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
        start = (page - 1) * per_page
        end = start + per_page
        return filtered[start:end], total_pages

class UserManager:
    def __init__(self):
        self.users: Dict[int, UserData] = {}
        self.order_counter = 20990

    def get_or_create_user(self, update: Update, referrer_id: Optional[int] = None) -> UserData:
        user = update.effective_user
        if user.id not in self.users:
            referral_link = f"https://t.me/Vanilla_cards_bot?start=ref_{user.id}"
            self.users[user.id] = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name,
                referral_link=referral_link
            )
        return self.users[user.id]

    def get_next_order_number(self) -> int:
        self.order_counter += 1
        return self.order_counter

card_generator = CardGenerator()
user_manager = UserManager()

# Keyboard Builder
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("💳 Stock", callback_data="stock")],
        [InlineKeyboardButton("📞 Admin", url="https://t.me/Vanilagcm")],
        [InlineKeyboardButton("🆘 Refund", url="https://t.me/VANILAExchange")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_manager.get_or_create_user(update)
    await update.message.reply_text(f"Welcome {user.first_name}!", reply_markup=get_main_menu())

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not card_generator.cards:
        await card_generator.update_cards()
    cards, total = card_generator.get_cards_paginated(1)
    text = "📋 Card List:\n\n"
    for i, card in enumerate(cards[:10], 1):
        text += f"{i}. {card.card_number} - ${card.amount}\n"
    await update.message.reply_text(text)

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = random.choice(DEPOSIT_ADDRESSES)
    user_id = update.effective_user.id
    user_deposit_data[user_id] = {'address': addr, 'status': 'waiting'}
    msg = f"Send TON to:\n`{addr}`\nMin 15 TON"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "stock":
        await stock(update, context)

async def main():
    print("Starting bot...")
    await card_generator.update_cards()
    
    app_telegram = Application.builder().token(BOT_TOKEN).build()
    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(CommandHandler("stock", stock))
    app_telegram.add_handler(CommandHandler("deposit", deposit))
    app_telegram.add_handler(CallbackQueryHandler(handle_callback))
    
    await app_telegram.initialize()
    await app_telegram.start()
    await app_telegram.updater.start_polling()
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
