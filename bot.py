import os
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ======================
# VARIÁVEIS SEGURAS
# ======================

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("PUSHIN_API_KEY")

PUSHIN_URL = "https://api.pushinpay.com.br/api/pix/cashIn"

# ======================
# BANCO
# ======================

conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, payment_id TEXT)")

def ja_recebeu(user_id):
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    return cursor.fetchone() is not None

def salvar_usuario(user_id):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))
    conn.commit()

def salvar_pagamento(user_id, payment_id):
    cursor.execute("INSERT INTO payments VALUES (?,?)", (user_id, payment_id))
    conn.commit()

# ======================
# PUSHIN PIX
# ======================

def criar_pix(user_id):
    url = "https://api.pushinpay.com.br/api/pix/cashIn"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "value": 1000,
        "external_id": str(user_id),
        "webhook_url": "https://seusite.com/webhook"
    }

    r = requests.post(url, json=payload, headers=headers)

    print("STATUS:", r.status_code)
    print("BODY:", r.text)

    if r.status_code != 200:
        return None

    return r.json()

def verificar_pagamento(payment_id):
    url = f"https://api.pushinpay.com.br/api/transactions/{payment_id}"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }

    r = requests.get(url, headers=headers)

    print(r.status_code, r.text)

    if r.status_code != 200:
        return None

    try:
        data = r.json()
    except:
        return None

    # tenta os dois formatos comuns
    return (
        data.get("status")
        or data.get("data", {}).get("status")
    )

# ======================
# BOT
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💰 Comprar", callback_data="comprar")]]

    await update.message.reply_text(
        "Clique abaixo:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    if query.data == "comprar":

        if ja_recebeu(user_id):
            await query.message.reply_text("Você já recebeu esse conteúdo.")
            return

        pix = criar_pix(user_id)

        qr = pix.get("qr_code")
        payment_id = pix.get("id")

        salvar_pagamento(user_id, payment_id)

        await query.message.reply_text(
            f"💳 Pix gerado:\n\n{qr}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Já paguei", callback_data=f"check_{payment_id}")]
            ])
        )

    elif query.data.startswith("check_"):

        payment_id = query.data.split("_")[1]
        status = verificar_pagamento(payment_id)

        if status == "paid":
            salvar_usuario(user_id)

            await query.message.reply_text(
                "Pagamento confirmado!\nLINK_DO_CONTEUDO"
            )
        else:
            await query.message.reply_text("Pagamento ainda não confirmado.")

# ======================
# EXECUTAR
# ======================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.run_polling(drop_pending_updates=True)