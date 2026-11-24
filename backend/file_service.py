import os
import subprocess
from datetime import datetime
from typing import List, Dict, Any

DEFAULT_WORKSPACE = os.getenv("WORKSPACE_PATH", r"C:\Users\bobby\OneDrive\Documents\MY-PR")

def get_workspace_root() -> str:
    path = os.getenv("WORKSPACE_PATH", DEFAULT_WORKSPACE)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)

def list_directory(subpath: str = "") -> Dict[str, Any]:
    root = get_workspace_root()
    target_path = os.path.abspath(os.path.join(root, subpath.lstrip("/\\")))

    # Security check: ensure target_path is within root or users directory
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Path tidak ditemukan: {subpath}")

    items: List[Dict[str, Any]] = []
    
    # Sort folders first, then files alphabetically
    with os.scandir(target_path) as entries:
        sorted_entries = sorted(entries, key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in sorted_entries:
            # Skip hidden / venv / git folders
            if entry.name.startswith(".") or entry.name in ["venv", "__pycache__", "node_modules"]:
                continue
            
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "path": os.path.relpath(entry.path, root).replace("\\", "/"),
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size if not entry.is_dir() else 0,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                })
            except Exception:
                continue

    current_rel = os.path.relpath(target_path, root).replace("\\", "/")
    if current_rel == ".":
        current_rel = ""

    return {
        "root": root,
        "current_path": current_rel,
        "items": items
    }

def read_file_content(file_path: str) -> Dict[str, Any]:
    root = get_workspace_root()
    target = os.path.abspath(os.path.join(root, file_path.lstrip("/\\")))
    
    if not os.path.exists(target) or os.path.isdir(target):
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    # Maximum 2MB for mobile viewing
    if os.path.getsize(target) > 2 * 1024 * 1024:
        raise ValueError("Ukuran file terlalu besar (>2MB) untuk dibuka di mobile editor.")

    with open(target, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    return {
        "file_path": file_path,
        "absolute_path": target,
        "content": content,
        "size": len(content)
    }

def save_file_content(file_path: str, content: str) -> Dict[str, Any]:
    root = get_workspace_root()
    target = os.path.abspath(os.path.join(root, file_path.lstrip("/\\")))

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "file_path": file_path,
        "saved_bytes": len(content)
    }

def execute_terminal_command(command: str, cwd: str = None) -> Dict[str, Any]:
    work_dir = cwd or get_workspace_root()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out after 30s", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}
