from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import httpx, os
import json, uuid, requests
from bs4 import BeautifulSoup

OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

print(" ")
print(f"OLLAMA_URL = {OLLAMA_URL}")
print(f"OLLAMA_MODEL = {OLLAMA_MODEL}")
print(" ")

app = FastAPI()

# Fetch the page content in Python
url = "https://www.dm.unipi.it/cluster-di-calcolo-scientifico/"
html = requests.get(url).text
soup = BeautifulSoup(html, "html.parser")
text_content = soup.get_text()

# Example: define system instructions at the start
SYSTEM_PROMPT = {
    "role": "system",
    "content": ""
}

with open("system-prompt.txt", "r") as h:
    SYSTEM_PROMPT["content"] = h.read()

sessions = {}

def get_history(session_id: str):
    if session_id not in sessions:
        sessions[session_id] = [SYSTEM_PROMPT.copy()]  # Start with system prompt
    return sessions[session_id]

with open("index.html") as h:
    html_template = h.read()

@app.get("/", response_class=HTMLResponse)
async def home():
    return html_template

@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    body = await request.json()

    session_id = body.get("session_id")
    message = body.get("message", "")

    if not session_id:
        # generate a new session if not provided
        session_id = str(uuid.uuid4())

    chat_history = get_history(session_id)
    
    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            assistant_message = ""

            async with client.stream("POST", OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "messages": chat_history, 
                "repeat_penalty": 1.15, 
                "prompt": message}) as resp:
                partial = ""
                async for chunk in resp.aiter_bytes():
                    text_chunk = chunk.decode()
                    partial += text_chunk
                    lines = partial.split("\n")
                    partial = lines.pop()  # keep last incomplete line
                    
                    for line in lines:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                msg = data.get("message")
                                if msg.get("role") == "assistant" and msg.get("content"):
                                    # Append incrementally to chat history
                                    assistant_message += msg["content"]
                                    # chat_history.append({"role": "assistant", "content": msg["content"]})
                                    yield line.encode() + b"\n"
                            except Exception:
                                yield b""  # skip malformed lines

            chat_history.append({"role": "assistant", "content": assistant_message})

    chat_history.append({"role": "user", "content": message})

    return StreamingResponse(event_stream(), media_type='application/octet-stream')

@app.post("/api/reset")
async def api_reset(request: Request):
    session_id = request.get("session_id")

    if session_id:
         del sessions[session_id]

    return JSONResponse({"status": "reset"})
