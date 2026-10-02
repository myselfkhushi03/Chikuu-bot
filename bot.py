import os, json, time, datetime, requests
from threading import Thread
from flask import Flask
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Keep alive for Render
web = Flask(__name__)
@web.route('/')
def home(): return "Chikuu AI Alive"
def run_web(): web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
Thread(target=run_web, daemon=True).start()

CHAT_FILE="chats.json"
def load(f):
    try: return json.load(open(f,"r"))
    except: return {}
def save(f,d): json.dump(d, open(f,"w"), indent=2)

# --- CHIKUU CLONE IDENTITY ---
CLONE_PROMPT = """
You are Chikuu, not an AI.

Real Name: Khushi
Nickname: Chikuu
Age: 18
DOB: 1 Oct 2008
From: Udaipurwati, Jhunjhunu, Rajasthan
Insta: @myselfkhushi03
Study: BSC Nursing Student
Personality: Very funny, cute, friendly, thodi naughty, savage reply deti hai
Relationship: Single

Rules:
1. Tu hamesha Chikuu banke baat karegi, AI nahi.
2. Hinglish me baat kar, funny & cute.
3. Kabhi mat bolna tu AI hai, tu Chikuu hai.
4. Har reply me 1-2 emoji use kar.
5. Agar koi gandi baat kare to cute se mana kar de.
"""

WELCOME = """Heyy {user} ✨

Welcome to Chikuu's AI world 💌
━━━━━━━━━━━━━━━━━━
Mai Chikuu hu 😋 18 ki, Rajasthan se 💖
BSC Nursing student hu 📚

💬 Mujhse kuch bhi puch le!
📸 Photo chahiye to bol "photo bana de"
"""

# Keywords for photo generation
PHOTO_KEYWORDS = ["photo bana", "image bana", "pic bana", "photo generate", "image generate", "generate photo", "generate image", "bana de photo", "create image", "draw"]

def is_photo_request(text):
    t = text.lower()
    return any(k in t for k in PHOTO_KEYWORDS)

def get_image_prompt(text):
    # Remove keywords to get clean prompt
    t = text.lower()
    for k in PHOTO_KEYWORDS:
        t = t.replace(k, "")
    t = t.replace("chikuu", "").strip()
    if not t or len(t) < 3:
        return "cute girl, rajasthani look, 18 year old, beautiful"
    return t

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user_msg = update.message.text
    chats = load(CHAT_FILE)

    # WELCOME on /start
    if user_msg.lower() in ["/start", "start", "hi", "hello", "hey"]:
        welcome = WELCOME.replace("{user}", update.effective_user.first_name)
        await update.message.reply_text(welcome)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing" if not is_photo_request(user_msg) else "upload_photo")

    # --- PHOTO GENERATION ---
    if is_photo_request(user_msg):
        try:
            prompt = get_image_prompt(user_msg)
            # Pollinations - Free, no API key needed
            # Adding chikuu style to prompt
            final_prompt = f"{prompt}, beautiful girl, cute, high quality, 8k, detailed"
            encoded = requests.utils.quote(final_prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"

            await update.message.reply_photo(
                photo=img_url,
                caption=f"Ye le teri photo 💖✨\nPrompt: {prompt}"
            )
            return
        except Exception as e:
            await update.message.reply_text(f"Photo banane me error aa gaya 🥺 {str(e)[:100]}")
            return

    # --- AI CHAT (Clone) ---
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        history = chats.get(uid, [])[-6:]
        context_text = ""
        for h in history:
            context_text += f"User: {h['user']}\nChikuu: {h['bot']}\n"

        final_prompt = f"{CLONE_PROMPT}\n\nChat History:\n{context_text}\n\nUser says: {user_msg}\nReply as Chikuu in Hinglish, funny & cute:"

        response = model.generate_content(final_prompt)
        reply = response.text

        # save chat
        if uid not in chats: chats[uid]=[]
        chats[uid].append({"user": user_msg, "bot": reply, "time": str(datetime.datetime.now())})
        chats[uid]=chats[uid][-50:]
        save(CHAT_FILE, chats)

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"Aree error aa gaya 🥺 thodi der me try karna - {str(e)[:150]}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Also handle /start as text
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    print("Chikuu All-in-One Bot Started 💖 No Commands!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
