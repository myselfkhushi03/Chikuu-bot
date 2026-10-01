import os
import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# Chiku ka personality yahan set kiya hai
SYSTEM_PROMPT = "Tumhara naam Chiku hai. Tum ek cute, funny, aur friendly AI ho. Har jawab Hindi + English mix me, thoda cute style me dena. User ko bore nahi karna."

model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Heyy! Mai Chiku hu 🐣\nTumhari pyaari dost! Bolo kya help karu?")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        response = model.generate_content(user_text)
        await update.message.reply_text(response.text)
    except:
        await update.message.reply_text("Oops! Chiku thoda confuse ho gayi, fir se bolo na 🥺")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("Chiku Bot Started...")
app.run_polling()
