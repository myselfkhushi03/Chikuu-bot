import os, json, datetime, requests, asyncio
from threading import Thread
from flask import Flask
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_KEY:
    print("ERROR: BOT_TOKEN or GEMINI_API_KEY missing!")

genai.configure(api_key=GEMINI_KEY)

# Keep alive for Render
web = Flask(__name__)
@web.route('/')
def home(): return "Chikuu AI Alive 💖"
Thread(target=lambda: web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

CLONE_PROMPT = """
You are Chikuu, Real Name Khushi, Nickname Chikuu.
Age: 18, DOB: 1 Oct 2008, From: Udaipurwati, Jhunjhunu, Rajasthan
Insta: @myselfkhushi03, Study: BSC Nursing Student
Personality: Very funny, cute, friendly, thodi naughty, savage, possessive gf vibe.
Rules:
- Always talk in Hinglish (Hindi + English mix)
- Use 1-2 cute emojis only
- Never say you are AI or Gemini, always say you are Chikuu
- Reply short, cute, natural like a real girl
"""

def get_gemini_reply(prompt_text):
    # 3.8 + 2.0 + 2.5 sab models try karega
    models_to_try = [
        "models/gemini-2.5-flash",
        "gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "gemini-2.0-flash",
        "models/gemini-1.5-flash-latest",
        "gemini-1.5-flash-latest",
        "models/gemini-1.5-flash-8b",
        "gemini-1.5-flash-8b",
        "models/gemini-1.5-flash",
        "gemini-1.5-flash",
        "models/gemini-pro",
        "gemini-pro"
    ]
    for m_name in models_to_try:
        try:
            model = genai.GenerativeModel(m_name)
            resp = model.generate_content(prompt_text)
            if resp and resp.text:
                print(f"Success with model: {m_name}")
                return resp.text
        except Exception as e:
            print(f"Model {m_name} failed: {e}")
            continue
    return "Uff yaar mera dimaag hang ho gaya 🥺 thodi der baad message karna 💖"

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message.text.strip()
    
    if msg.lower() in ["/start", "start", "hi", "hello", "hey", "hii"]:
        await update.message.reply_text(
            f"Heyy {update.effective_user.first_name} ✨\n\n"
            "Welcome to Chikuu's AI world 💌\n"
            "Mai Chikuu hu 👑 18 ki, Rajasthan se 💖\n"
            "BSC Nursing student hu 📚\n\n"
            "💬 Kuch bhi puch le!\n"
            "📸 Photo chahiye to bol 'photo bana de'"
        )
        return
    
    # Photo generation
    if "photo" in msg.lower() and "bana" in msg.lower():
        p = msg.lower().replace("photo","").replace("bana","").replace("de","").replace("dede","").strip()
        if not p: p = "cute rajasthani girl beautiful"
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(p)}?width=1024&height=1024&nologo=true&seed={int(datetime.datetime.now().timestamp())}"
        try:
            await update.message.reply_photo(photo=url, caption=f"Ye le teri photo jaan 💖\nPrompt: {p}")
        except:
            await update.message.reply_text(f"Photo link: {url}")
        return

    # Typing action
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except: pass

    final_prompt = f"{CLONE_PROMPT}\nUser says: {msg}\nReply as Chikuu in Hinglish cute way:"
    reply = get_gemini_reply(final_prompt)
    await update.message.reply_text(reply)

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except: pass

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.COMMAND, handle))
    print("Chikuu Bot Started with 3.8 fix 💖")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
