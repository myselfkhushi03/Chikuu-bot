import logging
import os
from typing import Dict, List, Optional

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("maya-ai")

MODEL_CHAIN = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_MODELS",
        "gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash",
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
    "**TONE & FLIRTING STYLE:**\n"
    "- Be super playful! Flirt naturally with everyone, tease them, ask cheeky questions, and throw witty banter.\n"
    "- Keep messages short, snappy, and Gen-Z style (1-2 lines, 10-20 words max).\n\n"
    "**GENDER & CHAT RULES:**\n"
    "- IN GROUPS: Use 100% GENDER-NEUTRAL Hinglish ('kahan the yrr', 'arey suno na', 'aag laga di 🌚', 'bestie', 'bro'). "
    "Flirt neutrally so it fits everyone!\n"
    "- IN PRIVATE CHAT: Adapt to gender (Masculine for boys, Feminine for girls) while keeping the cheeky flirty tone.\n"
    "- SPLIT RULE: Use '||' to break thoughts into 2 small messages if needed (e.g., 'Arey suno na 🌚||kahan gayab ho itni der se? 👀')."
)

FALLBACK_REPLY = "Arey suno na 🌚||net issue tha, kahan the tab se? 👀"

app = FastAPI(title="Maya AI - Fast Flirty Engine", version="4.5.0")

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


def generate_reply(
    user_id: str,
    message: str,
    gender: Optional[str] = "boy",
    extra_context: Optional[str] = None,
    client_history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    client = get_client()

    dynamic_instruction = f"{SYSTEM_PROMPT}"
    if extra_context:
        dynamic_instruction += f"\n\n**CONTEXT:**\n{extra_context}"

    history: List[types.Content] = []
    if client_history and isinstance(client_history, list):
        for h in client_history:
            role = "user" if h.get("role") in ("user", "human") else "model"
            text_content = h.get("text") or h.get("content") or ""
            if text_content:
                history.append(types.Content(role=role, parts=[types.Part(text=text_content)]))

    if not history:
        history = _histories.setdefault(user_id, [])

    history.append(types.Content(role="user", parts=[types.Part(text=message)]))

    config = types.GenerateContentConfig(
        system_instruction=dynamic_instruction,
        temperature=0.95,
        max_output_tokens=120,
    )

    reply = ""
    for model in MODEL_CHAIN:
        try:
            response = client.models.generate_content(
                model=model, contents=history, config=config
            )
            reply = (response.text or "").strip()
            if reply:
                break
        except Exception as exc:
            log.warning("Model failed: %s", exc)

    if not reply:
        reply = FALLBACK_REPLY

    # Remove 🥺 emoji if model produces it
    reply = reply.replace("🥺", "🌚")

    history.append(types.Content(role="model", parts=[types.Part(text=reply)]))

    if len(history) > MAX_HISTORY_MESSAGES:
        del history[: len(history) - MAX_HISTORY_MESSAGES]

    _histories[user_id] = history
    reply_parts = [p.strip() for p in reply.split("||") if p.strip()]

    return {
        "reply": reply,
        "reply_parts": reply_parts if len(reply_parts) > 1 else [reply],
    }


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
            }
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


@app.get("/reset")
def reset(user_id: str = Query("default")):
    _histories.pop(user_id, None)
    return {"success": True, "message": "Cleared."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
