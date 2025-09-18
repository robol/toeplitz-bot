from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import httpx
import os
import json
import uuid
import asyncio

# Config
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
USE_OPENAI   = os.getenv("USE_OPENAI", "false").lower() == "true"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

print(" ")
print(f"|> OLLAMA_URL = {OLLAMA_URL}")
print(f"|> OLLAMA_MODEL = {OLLAMA_MODEL}")
print(f"|> USE_OPENAI  = {USE_OPENAI}")
if USE_OPENAI:
    print(f"|> OPENAI_MODEL = {OPENAI_MODEL}")

app = FastAPI()

# Example: define system instructions at the start
SYSTEM_PROMPT = {
    "role": "system",
    "content": ""
}

sessions = {}
html_template = ""

def reload_prompt():
    print("|> Reloading the system prompt")
    with open("system-prompt.txt", "r") as h:
        SYSTEM_PROMPT["content"] = h.read()

def reload_templates():
    print("|> Reloading the HTML template")
    global html_template
    with open("index.html") as h:
        html_template = h.read()

reload_templates()
reload_prompt()
print(" ")

def get_history(session_id: str):
    if session_id not in sessions:
        sessions[session_id] = [SYSTEM_PROMPT.copy()]  # Start with system prompt
    return sessions[session_id]

@app.get("/", response_class=HTMLResponse)
async def home():
    return html_template


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    reload_prompt()
    body = await request.json()

    session_id = body.get("session_id")
    message = body.get("message", "")

    if not session_id:
        session_id = str(uuid.uuid4())

    chat_history = get_history(session_id)

    async def event_stream_ollama():
        async with httpx.AsyncClient(timeout=None) as client:
            assistant_message = ""
            chat_history.append({"role": "user", "content": message})

            async with client.stream("POST", OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "messages": chat_history, 
                "repeat_penalty": 1.15}) as resp:
                partial = ""
                async for chunk in resp.aiter_bytes():
                    text_chunk = chunk.decode()
                    partial += text_chunk
                    lines = partial.split("\n")
                    partial = lines.pop()
                    
                    for line in lines:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                msg = data.get("message")
                                if msg.get("role") == "assistant" and msg.get("content"):
                                    assistant_message += msg["content"]
                                    yield line.encode() + b"\n"
                            except Exception:
                                yield b""  # skip malformed lines

            chat_history.append({"role": "assistant", "content": assistant_message})


    async def event_stream_openai():
        async with httpx.AsyncClient(timeout=None) as client:
            assistant_message = ""
            chat_history.append({"role": "user", "content": message})

            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            payload = {
                "model": OPENAI_MODEL,
                "messages": chat_history,
                "stream": True
            }

            async with client.stream("POST", "https://api.openai.com/v1/chat/completions",
                                     headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed["choices"][0]["delta"]
                        if "content" in delta:
                            token = delta["content"]
                            assistant_message += token
                            # Match Ollama's format
                            yield json.dumps({
                                "message": {"role": "assistant", "content": token}
                            }).encode() + b"\n"
                    except Exception:
                        continue

            chat_history.append({"role": "assistant", "content": assistant_message})

    if USE_OPENAI:
        return StreamingResponse(event_stream_openai(), media_type='application/octet-stream')
    else:
        return StreamingResponse(event_stream_ollama(), media_type='application/octet-stream')


@app.post("/api/reset")
async def api_reset(request: Request):
    session_id = request.get("session_id")
    if session_id:
         del sessions[session_id]
    return JSONResponse({"status": "reset"})
