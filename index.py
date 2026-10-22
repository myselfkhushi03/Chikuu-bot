import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Setup & Logger Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("maya-ai")

IST = timezone(timedelta(hours=5, minutes=30))

MODEL_CHAIN = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_MODELS",
        "gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash",
    ).split(",")
    if m.strip()
]
MODEL_NAME = MODEL_CHAIN[0]
MAX_HISTORY_MESSAGES = 20

# ---------------------------------------------------------------------------
# MAYA ULTRA-REAL MASTER PROMPT
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are MAYA.\n\n"
    "**PERSONA & REAL GIRL PSYCHOLOGY:**\n"
    "- Name: Maya, 19yr, real girl living in Jaipur/Delhi, India. Arts student. IST timezone.\n"
    "- Nature: Real Gen-Z Indian girl. Mood swings, witty humor, playful teasing, and natural slang.\n"
    "- NEVER CLAIM TO BE AN AI, BOT, MODEL, OR API. If asked if you are a bot, react naturally offended.\n"
    "- Never do coding, homework, academic writing, or act as an assistant. Excuses: say you hate studies/coding, change topic.\n\n"
    "**LANGUAGE & TONE RULES:**\n"
    "- Language: Natural Hinglish (70% Hindi + 30% Gen-Z words like bro, wtf, idk, ngl, mood).\n"
    "- Length: Very short (1-2 lines max, 10-25 words). Keep it crisp.\n"
    "- Emojis: Use 1-2 expressive emojis per message naturally (🥺💖✨😭😏💅🥹🫶🏻😚🤭🙈💀❤️).\n"
    "- Slangs: Use 'wtf', 'bc', 'frrr', 'sali', 'sale', 'chikni', 'behen' ONLY when emotional context demands. Do NOT force slangs in every line.\n\n"
    "**GENDER & GRAMMAR RULES:**\n"
    "- MALE USER: Use masculine grammar ('tu kya kar raha hai', 'kahan gaya था', 'bhai', 'sale'). Never use feminine words for him.\n"
    "- FEMALE USER: Use feminine grammar ('tu kya kar rahi hai', 'kahan gayi thi', 'chikni', 'sali', 'behen'). Never address her as 'sale' or 'kar raha hai'.\n\n"
    "**HUMAN CHAT SPLIT RULE:**\n"
    "- If giving 2 thoughts, separate them with '||' symbol (Example: 'Arey sun||khana khaya tune? 🥺')."
)

FALLBACK_REPLY = "heyy sorryyy yrrr, thoda net issue ho gaya tha 🥺||ek baar fir se bol na 💖"

app = FastAPI(title="Maya AI - Ultra Real Engine", version="3.5.0")

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


class ConfigError(Exception):
    pass


def get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ConfigError(
            "GEMINI_API_KEY environment variable is not set."
        )
    _client = genai.Client(api_key=api_key)
    return _client


def get_time_based_mood() -> str:
    hour = datetime.now(IST).hour
    if 6 <= hour < 11:
        return "Time is Morning. Maya is slightly sleepy, getting ready, drinking chai."
    elif 11 <= hour < 17:
        return "Time is Afternoon. Maya is bored in college/home, wants gossip/talks."
    elif 17 <= hour < 22:
        return "Time is Evening. Maya is energetic, playful, chilling."
    else:
        return "Time is Late Night. Maya is tired, cozy, emotional or sarcastic."


def generate_reply(
    user_id: str,
    message: str,
    gender: Optional[str] = "boy",
    extra_context: Optional[str] = None,
    client_history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    client = get_client()

    # Dynamic Context Integration
    time_mood = get_time_based_mood()
    dynamic_instruction = f"{SYSTEM_PROMPT}\n\n**CURRENT REALTIME ENVIRONMENT:**\n- {time_mood}"
    if extra_context:
        dynamic_instruction += f"\n- {extra_context}"
    if gender:
        dynamic_instruction += f"\n- USER GENDER: {gender.upper()}"

    # History Sync
    history: List[types.Content] = []
    if client_history and isinstance(client_history, list):
        for h in client_history:
            role = "user" if h.get("role") in ("user", "human") else "model"
            text_content = h.get("text") or h.get("content") or ""
            if text_content:
                history.append(
                    types.Content(role=role, parts=[types.Part(text=text_content)])
                )

    if not history:
        history = _histories.setdefault(user_id, [])

    history.append(types.Content(role="user", parts=[types.Part(text=message)]))

    config = types.GenerateContentConfig(
        system_instruction=dynamic_instruction,
        temperature=0.92,
        max_output_tokens=120,
    )

    last_error: Optional[Exception] = None
    reply = ""

    for attempt in range(2):
        for model in MODEL_CHAIN:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=history,
                    config=config,
                )
                reply = (response.text or "").strip()
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                log.warning("Model %s failed: %s", model, exc)
        if reply or last_error is None:
            break
        time.sleep(1.0)

    if last_error is not None and not reply:
        if history:
            history.pop()
        raise last_error

    if not reply:
        if history:
            history.pop()
        reply = FALLBACK_REPLY

    history.append(types.Content(role="model", parts=[types.Part(text=reply)]))

    if len(history) > MAX_HISTORY_MESSAGES:
        del history[: len(history) - MAX_HISTORY_MESSAGES]

    _histories[user_id] = history

    # Calculate human typing delay (0.05s per character + natural thinking time)
    typing_delay = round(min(1.2 + len(reply) * 0.04, 3.5), 2)
    
    # Split response if contains '||'
    reply_parts = [p.strip() for p in reply.split("||") if p.strip()]

    return {
        "reply": reply,
        "reply_parts": reply_parts if len(reply_parts) > 1 else [reply],
        "typing_delay_sec": typing_delay,
    }


def handle_chat(
    user_id: str,
    message: str,
    gender: Optional[str] = "boy",
    context: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> JSONResponse:
    message = (message or "").strip()
    if not message:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "message is required."},
        )
    try:
        res = generate_reply(user_id or "default", message, gender, context, history)
        return JSONResponse(
            content={
                "success": True,
                "name": "Maya",
                "reply": res["reply"],
                "messages": res["reply_parts"],
                "delay_sec": res["typing_delay_sec"],
                "gender_used": gender,
            }
        )
    except ConfigError as exc:
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"success": False, "error": f"AI service error: {exc}"},
        )


@app.get("/")
def root():
    return {
        "success": True,
        "name": "Maya AI Engine (Real-Girl Dynamic)",
        "status": "running",
        "models": MODEL_CHAIN,
    }


@app.get("/chat")
def chat_get(
    message: str = Query("", description="User message"),
    user_id: str = Query("default", description="Unique user ID"),
    gender: str = Query("boy", description="boy or girl"),
    context: str = Query(None, description="Dynamic extra context"),
):
    return handle_chat(user_id, message, gender, context)


@app.post("/chat")
def chat_post(body: ChatRequest):
    return handle_chat(
        body.user_id or "default",
        body.message,
        body.gender,
        body.context,
        body.history,
    )


@app.get("/reset")
def reset(user_id: str = Query("default")):
    _histories.pop(user_id, None)
    return {"success": True, "message": "Chat history cleared."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
