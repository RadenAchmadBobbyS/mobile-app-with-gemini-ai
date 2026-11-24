import os
import aiosqlite
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "antigravity_mobile.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT DEFAULT 'gemini-2.5-flash',
                thinking_effort TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                thoughts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS automations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                schedule_type TEXT DEFAULT 'interval', -- 'interval' or 'cron'
                schedule_value TEXT NOT NULL, -- minutes e.g. '60' or cron '0 8 * * *'
                is_active INTEGER DEFAULT 1,
                last_run TIMESTAMP,
                last_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# Session functions
async def get_all_sessions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def create_session(session_id: str, title: str, model: str = "gemini-2.5-flash", thinking_effort: str = "medium"):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (id, title, model, thinking_effort, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, title, model, thinking_effort, now, now)
        )
        await db.commit()

async def update_session(session_id: str, title: str = None, model: str = None, thinking_effort: str = None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        updates = ["updated_at = ?"]
        params = [now]
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if model is not None:
            updates.append("model = ?")
            params.append(model)
        if thinking_effort is not None:
            updates.append("thinking_effort = ?")
            params.append(thinking_effort)
        params.append(session_id)
        await db.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

async def delete_session(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()

# Message functions
async def get_messages(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def save_message(msg_id: str, session_id: str, role: str, content: str, thoughts: str = ""):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id, session_id, role, content, thoughts, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, thoughts, now)
        )
        await db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        await db.commit()

# Automation functions
async def get_all_automations():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM automations ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def save_automation(auto_id: str, title: str, prompt: str, schedule_type: str, schedule_value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO automations (id, title, prompt, schedule_type, schedule_value, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (auto_id, title, prompt, schedule_type, schedule_value)
        )
        await db.commit()

async def toggle_automation(auto_id: str, is_active: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE automations SET is_active = ? WHERE id = ?", (is_active, auto_id))
        await db.commit()

async def delete_automation(auto_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM automations WHERE id = ?", (auto_id,))
        await db.commit()

async def record_automation_run(auto_id: str, status: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE automations SET last_run = ?, last_status = ? WHERE id = ?", (now, status, auto_id))
        await db.commit()

# Notification functions
async def save_notification(notif_id: str, title: str, message: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO notifications (id, title, message) VALUES (?, ?, ?)", (notif_id, title, message))
        await db.commit()

async def get_notifications(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
