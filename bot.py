import os
import json
import time
import logging
import asyncio
import requests
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging setup for clean tracking
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("BOT_TOKEN")
# Render automatically provides PORT, fallback to 8080 locally
PORT = int(os.environ.get("PORT", 8080))
# Render app URL environment variable (e.g., https://your-app-name.onrender.com)
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

# Flask App for Webhook / Server hosting
app = Flask(__name__)

# Global tracking for monthly active users
monthly_users = set()

# Professional Main Menu Keyboard with cute vibe
def get_main_menu():
    keyboard = [
        [KeyboardButton("📊 Status"), KeyboardButton("🆘 Help")],
        [KeyboardButton("❌ Cancel")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Smart File & Content Type Detector (Handles JSON, Code, UID:Pass credentials safely)
def smart_detect_and_parse(text):
    cleaned_text = text.strip()
    
    # 1. Check if it's valid JSON or credentials dictionary structure
    try:
        parsed_json = json.loads(cleaned_text)
        formatted_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
        return formatted_json, "accounts_data.json", "JSON / Credentials Data"
    except json.JSONDecodeError:
        pass  

    # 2. Check for HTML code
    text_lower = cleaned_text.lower()
    if "<html" in text_lower or "<body" in text_lower or "<!doctype html>" in text_lower or ("<" in text_lower and ">" in text_lower and "/>" in text_lower):
        return cleaned_text, "index.html", "HTML Code"

    # 3. Check for Python code
    elif any(keyword in cleaned_text for keyword in ["def ", "import ", "print(", "class ", "if __name__"]):
        return cleaned_text, "script.py", "Python Code"

    # 4. Check for JavaScript code
    elif any(keyword in cleaned_text for keyword in ["console.log", "function ", "const ", "let ", "document.getElementById"]):
        return cleaned_text, "script.js", "JavaScript Code"

    # 5. Check for CSS code
    elif "{" in cleaned_text and ("margin:" in cleaned_text or "padding:" in cleaned_text or "color:" in cleaned_text or "background:" in cleaned_text):
        return cleaned_text, "style.css", "CSS Stylesheet"

    # 6. Fallback for raw text, unstructured uid:pass logs, etc.
    else:
        return cleaned_text, "data_output.txt", "Text / Credentials Log"

# /start Command Handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    monthly_users.add(user.id)
    
    current_time = datetime.now().strftime("%I:%M %p")
    user_count = len(monthly_users)
    
    welcome_text = (
        f"👥 **Monthly Active Users:** `{user_count}`\n\n"
        f"🧸 **Welcome to Pixie File Bot ✨**\n"
        f"Send any text, code, JSON, or `uid:pass` credentials. I will automatically detect the format and generate a clean downloadable file for you!\n\n"
        f"💡 *Tip:* Use `/make filename.ext` to specify a custom name.\n\n"
        f"⏱️ *Interaction Time:* `{current_time}`"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

# Help Command Handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now().strftime("%I:%M %p")
    help_text = (
        f"🆘 **Pixie Help & Guide 🧸**\n\n"
        f"1. **Auto-Detection:** Paste anything directly (JSON, Code, Credentials). Bot reads and converts it instantly.\n"
        f"2. **Manual Naming:** Use `/make custom_name.json` followed by your data.\n"
        f"3. **Zero Errors:** Built-in exception handling ensures safe processing without silent failures.\n\n"
        f"⏱️ `{current_time}`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_main_menu())

# Cancel Command Handler
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now().strftime("%I:%M %p")
    await update.message.reply_text(
        f"No active operation to cancel. Returning to main menu.\n⏱️ `{current_time}`",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

# Manual Command: /make filename.ext
async def make_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now().strftime("%I:%M %p")
    if not context.args:
        await update.message.reply_text(
            f"❌ Please provide a filename.\nExample: `/make credentials.json`\n⏱️ `{current_time}`",
            parse_mode="Markdown"
        )
        return
    
    filename = context.args[0]
    full_text = update.message.text
    parts = full_text.split(maxsplit=1)
    
    if len(parts) < 2:
        await update.message.reply_text(
            f"❌ Please provide the content along with the command.\n⏱️ `{current_time}`",
            parse_mode="Markdown"
        )
        return
    
    content = parts[1].replace(filename, "", 1).strip()
    await process_and_send(update, filename, content, detected_type="Manual Custom File")

# Main Message Handler for Auto-Detection & Processing
async def handle_incoming_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now().strftime("%I:%M %p")
    text = update.message.text
    
    if not text:
        return

    # Handle Menu Buttons
    if text == "📊 Status":
        await update.message.reply_text(
            f"🟢 **Bot Status:** Online & Fully Operational\n"
            f"👥 **Monthly Active Users:** `{len(monthly_users)}`\n"
            f"⏱️ `{current_time}`",
            parse_mode="Markdown"
        )
        return
    elif text == "🆘 Help":
        await help_command(update, context)
        return
    elif text == "❌ Cancel":
        await cancel_command(update, context)
        return

    # Error handling guard to prevent silent crashes
    try:
        processed_content, filename, detected_type = smart_detect_and_parse(text)
        await process_and_send(update, filename, processed_content, detected_type=detected_type)
        
    except Exception as e:
        logger.error(f"Error processing text content: {e}")
        await update.message.reply_text(
            f"⚠️ **Processing Error Occurred**\n"
            f"Reason: `{str(e)}`\n"
            f"Please check your formatting and try again.\n⏱️ `{current_time}`",
            parse_mode="Markdown"
        )

# Core File Builder and Sender Function
async def process_and_send(update: Update, filename: str, content: str, detected_type: str):
    current_time = datetime.now().strftime("%I:%M %p")
    
    status_msg = await update.message.reply_text(
        f"⚙️ Analyzing content type and building file...\n⏱️ `{current_time}`",
        parse_mode="Markdown"
    )

    start_time = time.time()
    
    file_path = f"temp_{filename}"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as file_write_error:
        await status_msg.edit_text(
            f"❌ **File Generation Failed**\nReason: `{str(file_write_error)}`\n⏱️ `{current_time}`",
            parse_mode="Markdown"
        )
        return

    file_size_bytes = os.path.getsize(file_path)
    file_size_str = f"{file_size_bytes} B"
    if file_size_bytes > 1024:
        file_size_str = f"{round(file_size_bytes / 1024, 2)} KB"

    end_time = time.time()
    total_time_taken = round(end_time - start_time, 2)

    caption = (
        f"🏁 **File Generation Complete!**\n\n"
        f"📂 **Filename:** `{filename}`\n"
        f"🔍 **Detected Type:** `{detected_type}`\n"
        f"📏 **File Size:** `{file_size_str}`\n"
        f"⏱️ **Time Taken:** `{total_time_taken}s`\n"
        f"🕒 `{current_time}`\n\n"
        f"📥 Sending result file..."
    )

    await status_msg.edit_text(caption, parse_mode="Markdown")

    try:
        with open(file_path, "rb") as doc_file:
            await update.message.reply_document(
                document=doc_file,
                caption=f"File: {filename} ({detected_type})"
            )
    except Exception as send_error:
        await update.message.reply_text(f"❌ Failed to send document: {str(send_error)}")

    if os.path.exists(file_path):
        os.remove(file_path)

# Telegram Application & Webhook Setup
application = Application.builder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("make", make_file_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_content))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Pixie File Bot is active and running smoothly! ✨", 200

# Automatic Webhook Setter function for Render
def setup_telegram_webhook():
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/{TOKEN}"
        api_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
        try:
            resp = requests.get(api_url)
            logger.info(f"Auto Webhook Setup Response: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to auto-set webhook: {e}")

if __name__ == "__main__":
    application.initialize()
    setup_telegram_webhook()
    app.run(host="0.0.0.0", port=PORT)
