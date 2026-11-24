import os
import json
import uuid
from typing import Optional, List
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import database
from agent_service import stream_agent_chat
from file_service import list_directory, read_file_content, save_file_content, execute_terminal_command, get_workspace_root
from scheduler_service import automation_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inisialisasi DB dan Scheduler
    await database.init_db()
    automation_manager.start()
    await automation_manager.reload_all_jobs()
    print("[Server] Antigravity Mobile Backend siap melayani di port 8000.")
    yield
    # Shutdown
    if automation_manager.scheduler.running:
        automation_manager.scheduler.shutdown()

app = FastAPI(title="Antigravity Mobile API", version="2.0.0", lifespan=lifespan)

# CORS Policy - Izinkan akses dari mobile app di manapun
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class NewSessionRequest(BaseModel):
    title: Optional[str] = "Obrolan Baru"
    model: Optional[str] = "gemini-2.5-flash"
    thinking_effort: Optional[str] = "medium"

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    thinking_effort: Optional[str] = None

class ChatStreamRequest(BaseModel):
    session_id: str
    prompt: str
    model: Optional[str] = "gemini-2.5-flash"
    thinking_effort: Optional[str] = "medium"

class FileSaveRequest(BaseModel):
    path: str
    content: str

class TerminalCommandRequest(BaseModel):
    command: str

class AutomationCreateRequest(BaseModel):
    title: str
    prompt: str
    schedule_type: str = "interval"  # 'interval' (menit) atau 'cron'
    schedule_value: str = "60"

# --- HEALTH & INFO ---
@app.get("/api/health")
def health_check():
    use_9router = os.getenv("USE_9ROUTER", "false").lower() == "true"
    has_9router_key = bool(os.getenv("NINEROUTER_API_KEY"))
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY"))

    provider = "9router" if (use_9router or has_9router_key) else "google_direct"

    return {
        "status": "online",
        "provider": provider,
        "workspace": get_workspace_root(),
        "is_configured": has_9router_key or has_gemini_key
    }

# --- SESSIONS (CHAT HISTORY) ---
@app.get("/api/sessions")
async def list_sessions():
    return await database.get_all_sessions()

@app.post("/api/sessions")
async def create_new_session(req: NewSessionRequest):
    sess_id = str(uuid.uuid4())
    await database.create_session(sess_id, req.title, req.model, req.thinking_effort)
    return {"id": sess_id, "title": req.title, "model": req.model, "thinking_effort": req.thinking_effort}

@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, req: UpdateSessionRequest):
    await database.update_session(session_id, req.title, req.model, req.thinking_effort)
    return {"status": "updated"}

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    await database.delete_session(session_id)
    return {"status": "deleted"}

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    return await database.get_messages(session_id)

# --- CHAT STREAMING ---
@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatStreamRequest):
    # Simpan pesan user ke database
    user_msg_id = str(uuid.uuid4())
    await database.save_message(user_msg_id, req.session_id, "user", req.prompt)

    # Ambil history obrolan sebelumnya untuk konteks
    history = await database.get_messages(req.session_id)

    async def event_generator():
        full_text = ""
        full_thoughts = ""
        try:
            async for chunk in stream_agent_chat(
                prompt=req.prompt,
                history=history,
                model=req.model,
                thinking_effort=req.thinking_effort
            ):
                event = json.loads(chunk)
                if event.get("type") == "token":
                    full_text += event.get("content", "")
                elif event.get("type") == "thought":
                    full_thoughts += event.get("content", "")
                
                # Kirim ke client mobile (format chunk JSON baris per baris)
                yield chunk

            # Simpan pesan AI ke database setelah stream selesai
            ai_msg_id = str(uuid.uuid4())
            await database.save_message(ai_msg_id, req.session_id, "assistant", full_text, full_thoughts)
            
            # Update judul sesi jika masih "Obrolan Baru"
            if len(history) <= 2:
                title = req.prompt[:30] + ("..." if len(req.prompt) > 30 else "")
                await database.update_session(req.session_id, title=title)

        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# --- FILE EXPLORER & EDITING PC ---
@app.get("/api/files/tree")
def get_files_tree(path: str = Query("", description="Sub-path relatif dari root workspace")):
    try:
        return list_directory(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/files/read")
def read_file(path: str = Query(..., description="Path file relatif")):
    try:
        return read_file_content(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/files/save")
def save_file(req: FileSaveRequest):
    try:
        return save_file_content(req.path, req.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/terminal/run")
def run_terminal(req: TerminalCommandRequest):
    return execute_terminal_command(req.command)

# --- AUTOMATIONS & NOTIFICATIONS ---
@app.get("/api/automations")
async def list_automations():
    return await database.get_all_automations()

@app.post("/api/automations")
async def create_automation(req: AutomationCreateRequest):
    auto_id = str(uuid.uuid4())
    await database.save_automation(auto_id, req.title, req.prompt, req.schedule_type, req.schedule_value)
    await automation_manager.reload_all_jobs()
    return {"id": auto_id, "status": "created"}

@app.patch("/api/automations/{auto_id}/toggle")
async def toggle_auto(auto_id: str, is_active: int = Query(...)):
    await database.toggle_automation(auto_id, is_active)
    await automation_manager.reload_all_jobs()
    return {"status": "toggled"}

@app.delete("/api/automations/{auto_id}")
async def delete_auto(auto_id: str):
    await database.delete_automation(auto_id)
    await automation_manager.reload_all_jobs()
    return {"status": "deleted"}

@app.post("/api/automations/{auto_id}/trigger")
async def trigger_now(auto_id: str):
    automations = await database.get_all_automations()
    target = next((a for a in automations if a["id"] == auto_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Automasi tidak ditemukan")
    
    # Jalankan di background
    import asyncio
    asyncio.create_task(
        automation_manager.execute_automation_task(auto_id, target["title"], target["prompt"])
    )
    return {"status": "triggered"}

@app.get("/api/notifications")
async def list_notifications():
    return await database.get_notifications()

# --- WEBSOCKET REALTIME HUB ---
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await automation_manager.register_client(websocket)
    try:
        while True:
            # Tetap jaga koneksi aktif dan terima ping/pesan dari mobile
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        automation_manager.unregister_client(websocket)
    except Exception:
        automation_manager.unregister_client(websocket)

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)
