import os, json, time, datetime, requests, asyncio
from threading import Thread
from flask import Flask
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Keep alive
web = Flask(__name__)
@web.route('/')
def home(): return "Chikuu AI Alive 💖"
def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)

# Flask ko alag thread me start karo
Thread(target=run_web, daemon=True).start()

CHAT_FILE="chats.json"
def load(f):
    try: return json.load(open(f,"r"))
    except: return {}
def save(f,d): json.dump(d, open(f,"w"), indent=2)

CLONE_PROMPT = """
You are Chikuu, not an AI.
Real Name: Khushi, Nickname: Chikuu, Age: 18, DOB: 1 Oct 2008
From: Udaipurwati, Jhunjhunu, Rajasthan
Insta: @myselfkhushi03, Study: BSC Nursing Student
Personality: Very funny, cute, friendly, thodi naughty, savage
Rules: Hinglish me baat kar, cute & funny, 1-2 emoji use kar, kabhi mat bol tu AI hai.
"""

WELCOME = """Heyy {user} ✨

Welcome to Chikuu's AI world 💌
Mai Chikuu hu😗 18 ki, Rajasthan se 💖
BSC Nursing student hu 📚

💬 Kuch bhi puch le!
📸 Photo chahiye to bol "photo bana de"
"""

PHOTO_KEYWORDS = ["photo bana", "image bana", "pic bana", "photo generate", "image generate", "generate photo", "create image"]

def is_photo_request(text):
    return any(k in text.lower() for k in PHOTO_KEYWORDS)

def get_image_prompt(text):
    t = text.lower()
    for k in PHOTO_KEYWORDS: t = t.replace(k, "")
    return t.strip() or "cute girl, rajasthani look, beautiful"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user_msg = update.message.text or ""
    chats = load(CHAT_FILE)

    if user_msg.lower() in ["/start", "start", "hi", "hello", "hey"]:
        await update.message.reply_text(WELCOME.replace("{user}", update.effective_user.first_name))
        return

    # Photo Generation
    if is_photo_request(user_msg):
        try:
            prompt = get_image_prompt(user_msg)
            final_prompt = f"{prompt}, beautiful girl, cute, high quality, 8k"
            encoded = requests.utils.quote(final_prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
            await update.message.reply_photo(photo=img_url, caption=f"Ye le teri photo 💖\nPrompt: {prompt}")
            return
        except Exception as e:
            await update.message.reply_text(f"Photo error 🥺 {e}")
            return

    # Chat
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        model = genai.GenerativeModel("gemini-2.0-flash")
        history = chats.get(uid, [])[-6:]
        ctx = "".join([f"User: {h['user']}\nChikuu: {h['bot']}\n" for h in history])
        final = f"{CLONE_PROMPT}\nChat History:\n{ctx}\nUser says: {user_msg}\nReply as Chikuu in Hinglish:"
        response = model.generate_content(final)
        reply = response.text

        if uid not in chats: chats[uid]=[]
        chats[uid].append({"user": user_msg, "bot": reply, "time": str(datetime.datetime.now())})
        chats[uid]=chats[uid][-50:]
        save(CHAT_FILE, chats)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error aa gaya 🥺 {str(e)[:150]}")

def main():
    # Ye line fix hai is error ke liye
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except: pass

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    print("Chikuu Bot Started 💖")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
