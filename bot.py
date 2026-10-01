import os
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Heyy! Mai Chiku hu 🐣\nTumhari pyaari dost!")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"Tumhara naam Chiku hai, cute funny dost ho. Sawal: {user_text}"
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        print(e)
        await update.message.reply_text("Oops! Chiku confuse ho gayi 🥺")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("Chiku Started...")
app.run_polling()
