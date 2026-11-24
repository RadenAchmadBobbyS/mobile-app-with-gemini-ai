import asyncio
import json
import uuid
from datetime import datetime
from typing import Set, Dict, Any
from fastapi import WebSocket
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

import database
from agent_service import stream_agent_chat

class AutomationManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.connected_websockets: Set[WebSocket] = set()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            print("[Scheduler] Background Automation Engine aktif.")

    async def register_client(self, websocket: WebSocket):
        await websocket.accept()
        self.connected_websockets.add(websocket)
        # Kirim pesan sambutan
        await websocket.send_json({
            "type": "connected",
            "message": "Terhubung ke Antigravity Realtime Notification Hub",
            "timestamp": datetime.now().isoformat()
        })

    def unregister_client(self, websocket: WebSocket):
        self.connected_websockets.discard(websocket)

    async def broadcast_notification(self, title: str, message: str, payload: Dict[str, Any] = None):
        notif_id = str(uuid.uuid4())
        await database.save_notification(notif_id, title, message)

        dead_connections = set()
        data = {
            "type": "notification",
            "id": notif_id,
            "title": title,
            "message": message,
            "payload": payload or {},
            "timestamp": datetime.now().isoformat()
        }

        for ws in self.connected_websockets:
            try:
                await ws.send_json(data)
            except Exception:
                dead_connections.add(ws)

        for ws in dead_connections:
            self.connected_websockets.discard(ws)

    async def execute_automation_task(self, auto_id: str, title: str, prompt: str):
        print(f"[Automation] Menjalankan tugas: {title} ({auto_id})")
        await self.broadcast_notification(
            title=f"Memulai Automasi: {title}",
            message=f"Antigravity sedang memproses instruksi otomatis...",
            payload={"automation_id": auto_id, "status": "running"}
        )

        full_output = ""
        try:
            async for chunk in stream_agent_chat(prompt=prompt, model="gemini-2.5-flash", thinking_effort="low"):
                event = json.loads(chunk)
                if event.get("type") == "token":
                    full_output += event.get("content", "")
                elif event.get("type") == "done":
                    full_output = event.get("full_text", full_output)

            await database.record_automation_run(auto_id, "success")
            
            # Potong ringkasan pesan jika terlalu panjang untuk toast
            summary = (full_output[:140] + "...") if len(full_output) > 140 else full_output
            await self.broadcast_notification(
                title=f"Automasi Selesai: {title}",
                message=summary,
                payload={"automation_id": auto_id, "full_result": full_output, "status": "completed"}
            )
        except Exception as e:
            await database.record_automation_run(auto_id, f"error: {str(e)}")
            await self.broadcast_notification(
                title=f"Automasi Gagal: {title}",
                message=str(e),
                payload={"automation_id": auto_id, "status": "failed"}
            )

    async def reload_all_jobs(self):
        """Memuat ulang semua automasi dari database ke scheduler"""
        self.scheduler.remove_all_jobs()
        automations = await database.get_all_automations()

        for auto in automations:
            if not auto.get("is_active"):
                continue

            auto_id = auto["id"]
            schedule_type = auto.get("schedule_type", "interval")
            val = auto.get("schedule_value", "60")

            try:
                if schedule_type == "interval":
                    minutes = max(1, int(val))
                    self.scheduler.add_job(
                        self.execute_automation_task,
                        trigger=IntervalTrigger(minutes=minutes),
                        id=f"job_{auto_id}",
                        name=auto["title"],
                        kwargs={"auto_id": auto_id, "title": auto["title"], "prompt": auto["prompt"]},
                        replace_existing=True
                    )
                elif schedule_type == "cron":
                    # Contoh: '0 8 * * *' (menit jam hari bulan hari_minggu)
                    parts = val.split()
                    if len(parts) == 5:
                        self.scheduler.add_job(
                            self.execute_automation_task,
                            trigger=CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]),
                            id=f"job_{auto_id}",
                            name=auto["title"],
                            kwargs={"auto_id": auto_id, "title": auto["title"], "prompt": auto["prompt"]},
                            replace_existing=True
                        )
            except Exception as err:
                print(f"[Scheduler] Error menambahkan jadwal {auto_id}: {err}")

# Instance tunggal
automation_manager = AutomationManager()
