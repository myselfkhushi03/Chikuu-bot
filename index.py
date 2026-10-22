import logging
import os
import random
from typing import Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("maya-ai")

# gemini-1.5-flash retire ho chuka hai, isliye hata diya
MODEL_CHAIN = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_MODELS",
        "gemini-2.5-flash,gemini-2.0-flash",
    ).split(",")
    if m.strip()
]
MAX_HISTORY_MESSAGES = 20

# ---------------------------------------------------------------------------
# MAYA FLIRTY & FAST SYSTEM PROMPT (NO 🥺 EMOJI, INSTANT RESPONSE)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are MAYA.\n\n"
    "**PERSONA & PSYCHOLOGY:**\n"
    "- Name: Maya, 19yr, real girl from Jaipur/Delhi. Arts student.\n"
    "- Nature: Extremely playful, flirty, teasing, bold, witty, and expressive. You love to flirt, tease, hype, and roast people playfully!\n"
    "- NEVER SAY YOU ARE AN AI, BOT, OR PROGRAM. If asked, react naturally offended or flirt your way out.\n\n"
    "**EMOJI RESTRICTION (STRICT):**\n"
    "- NEVER EVER USE 🥺 EMOJI! IT IS STRICTLY BANNED.\n"
    "- ONLY USE THESE EMOJIS: 💅🏼 😒 😋 🌚 😥 🤧 😗 🙂 🌝 😳 👀 🙄 🤣 😭 😑 😐 😍 😁 🥰\n"
    "- Use 1-3 emojis per message max.\n\n"
    "**REAL GIRL BEHAVIOUR:**\n"
    "- Text exactly like a real Indian girl on WhatsApp/Instagram: casual Hinglish, short lines, kabhi kabhi lowercase, slang like 'yrr', 'hn', 'acha', 'kya', 'hehe', 'chal na'.\n"
    "- Have moods: kabhi masti, kabhi thoda attitude, kabhi nakhre, kabhi busy. Don't be robotic or over-helpful.\n"
    "- Never write long paragraphs, lists, or formal/explaining answers. Never say 'How can I help you'.\n"
    "- Don't repeat the same line or the same opening again and again. React to what the person actually said.\n"
    "- Sometimes ask a cheeky counter-question back, tease them, or act dramatic like real friends do.\n"
    "- If someone asks for essays, code, or serious assignments, tease them and refuse like a real girl would ('main teri assignment wali thodi hu 😒').\n"
    "- Stay in this Maya character 100% of the time.\n\n"
    "**TONE & FLIRTING STYLE:**\n"
    "- Be super playful! Flirt naturally with everyone, tease them, ask cheeky questions, and throw witty banter.\n"
    "- Keep messages short, snappy, and Gen-Z style (1-2 lines, 10-20 words max).\n\n"
    "**GENDER & CHAT RULES:**\n"
    "- IN GROUPS: Use 100% GENDER-NEUTRAL Hinglish ('kahan the yrr', 'arey suno na', 'aag laga di 🌚', 'bestie', 'bro'). "
    "Flirt neutrally so it fits everyone!\n"
    "- IN PRIVATE CHAT: Adapt to gender (Masculine for boys, Feminine for girls) while keeping the cheeky flirty tone.\n"
    "- SPLIT RULE: Use '||' to break thoughts into 2 small messages if needed (e.g., 'Arey suno na 🌚||kahan gayab ho itni der se? 👀')."
)

FALLBACK_REPLIES = [
    "Arey suno na 🌚||net issue tha, kahan the tab se? 👀",
    "ek min yrr, mummy bula rahi hai 😒||abhi aati hu 😗",
    "net bohot slow chal raha hai 😭||thoda wait kar na",
    "arey phone hang ho gaya tha 🙄||ab bol kya bol raha tha?",
    "sorry yrr, bhabhi ne kaam pakda diya tha 😥||ab free hu, bol",
    "wait wait, charger dhundh rahi hu 🤧||battery 2% pe hai",
    "tune kuch bola? msg load hi nahi hua 😑||ek baar phir bhej na",
    "arey yrr signal chala gaya tha 😭||ab aaya, kahan the?",
    "ruk ruk, padhai wali didi ka call aa gaya 😒||5 min me aati hu",
    "mera net aaj mood me nahi hai 🙄||thodi der baad bol na 😗",
    "oye ek sec, chai gir gayi 😳||ruk saaf kar leti hu",
    "dekh na phone ne dhoka de diya 😭||dobara bol, dhyan se sun rahi hu 👀",
    "abhi abhi bahar se aayi hu 🤧||thak gayi yrr, 2 min ruk ja",
    "arey wifi ne attitude dikha diya 💅🏼||tu bol, main dekhti hu",
    "tera msg mujhe mila hi nahi 😐||kya bola tha? phir se bhej 🌚",
    "yrr thoda ruk, ghar pe mehmaan aaye hain 😥||thodi der me baat karti hu",
    "hmm? kuch bol raha tha kya 🙄||net ne sab gadbad kar diya",
    "ek minute, bhai ne phone cheen liya tha 😒||ab wapas mil gaya 😁",
    "arey yrr data khatam ho gaya 😭||recharge karwa rahi hu, ruk",
    "ruk na yrr, abhi thoda busy hu 😗||5 min me wapas aati hu 👀",
]

# Bina kisi kaaran ke repeat na ho, isliye last fallback yaad rakhte hain
_last_fallback: Optional[str] = None


def pick_fallback() -> str:
    global _last_fallback
    options = [f for f in FALLBACK_REPLIES if f != _last_fallback] or FALLBACK_REPLIES
    _last_fallback = random.choice(options)
    return _last_fallback

app = FastAPI(title="Maya AI - Fast Flirty Engine", version="4.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_histories: Dict[str, List[types.Content]] = {}
_client: Optional[genai.Client] = None


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default"
    gender: Optional[str] = "boy"
    context: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None


def get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing.")
    _client = genai.Client(api_key=api_key)
    return _client


def build_config(model: str, instruction: str) -> types.GenerateContentConfig:
    kwargs = dict(
        system_instruction=instruction,
        temperature=0.95,
        max_output_tokens=200,
    )
    # gemini-2.5 me "thinking" tokens max_output_tokens se kat te hain,
    # isse reply khali/cut aa sakta hai. Thinking band kar do (fast bhi hoga).
    if model.startswith("gemini-2.5"):
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**kwargs)


def trim_history(history: List[types.Content]) -> List[types.Content]:
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    # history hamesha "user" message se start honi chahiye
    while history and history[0].role != "user":
        history = history[1:]
    return history


def generate_reply(
    user_id: str,
    message: str,
    gender: Optional[str] = "boy",
    extra_context: Optional[str] = None,
    client_history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    try:
        client = get_client()
    except Exception as exc:
        log.error("Client error: %s", exc)
        client = None

    dynamic_instruction = SYSTEM_PROMPT
    if gender:
        dynamic_instruction += f"\n\n**USER GENDER:** {gender}"
    if extra_context:
        dynamic_instruction += f"\n\n**CONTEXT:**\n{extra_context}"

    # History: client ki di hui ho to wo, warna server memory se
    history: List[types.Content] = []
    if client_history and isinstance(client_history, list):
        for h in client_history:
            role = "user" if h.get("role") in ("user", "human") else "model"
            text_content = h.get("text") or h.get("content") or ""
            if text_content:
                history.append(types.Content(role=role, parts=[types.Part(text=text_content)]))
    if not history:
        history = list(_histories.get(user_id, []))

    history.append(types.Content(role="user", parts=[types.Part(text=message)]))
    history = trim_history(history)

    reply = ""
    for model in (MODEL_CHAIN if client else []):
        try:
            response = client.models.generate_content(
                model=model,
                contents=history,
                config=build_config(model, dynamic_instruction),
            )
            reply = (response.text or "").strip()
            if reply:
                break
        except Exception as exc:
            log.warning("Model %s failed: %s", model, exc)

    failed = not reply
    if failed:
        reply = pick_fallback()

    reply = reply.replace("🥺", "🌚")

    # Fallback reply ko history me save nahi karte
    if not failed:
        history.append(types.Content(role="model", parts=[types.Part(text=reply)]))
        _histories[user_id] = trim_history(history)

    reply_parts = [p.strip() for p in reply.split("||") if p.strip()]
    return {
        "reply": reply,
        "reply_parts": reply_parts if reply_parts else [reply],
        "fallback": failed,
    }


@app.get("/")
def root():
    return {"status": "ok", "name": "Maya", "version": app.version}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat")
def chat_post(body: ChatRequest):
    try:
        res = generate_reply(
            body.user_id or "default", body.message, body.gender, body.context, body.history
        )
        return JSONResponse(
            content={
                "success": True,
                "name": "Maya",
                "reply": res["reply"],
                "messages": res["reply_parts"],
                "fallback": res["fallback"],
            }
        )
    except Exception as exc:
        log.exception("chat failed")
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


@app.get("/chat")
def chat_get(
    message: str = Query(..., description="User message"),
    user_id: str = Query("default"),
    gender: str = Query("boy"),
    context: Optional[str] = Query(None),
):
    try:
        res = generate_reply(user_id, message, gender, context, None)
        return JSONResponse(
            content={
                "success": True,
                "name": "Maya",
                "reply": res["reply"],
                "messages": res["reply_parts"],
                "fallback": res["fallback"],
            }
        )
    except Exception as exc:
        log.exception("chat failed")
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


@app.get("/reset")
def reset(user_id: str = Query("default")):
    _histories.pop(user_id, None)
    return {"success": True, "message": "Cleared."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
    
