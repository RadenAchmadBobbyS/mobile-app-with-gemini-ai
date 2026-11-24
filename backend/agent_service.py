import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List

# Cek ketersediaan SDK Antigravity & GenAI
USE_ANTIGRAVITY = False
try:
    from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
    USE_ANTIGRAVITY = True
except ImportError:
    pass

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from file_service import get_workspace_root

async def stream_via_9router(
    prompt: str,
    history: List[Dict[str, Any]] = None,
    model: str = "gemini-2.5-flash",
    thinking_effort: str = "medium"
) -> AsyncGenerator[str, None]:
    """Mengalirkan respon LLM melalui 9router (OpenAI-compatible gateway)."""
    base_url = os.getenv("NINEROUTER_BASE_URL", "https://api.9router.com/v1")
    api_key = os.getenv("NINEROUTER_API_KEY")

    if not api_key:
        yield json.dumps({
            "type": "error",
            "content": "NINEROUTER_API_KEY belum diisi di backend/.env!"
        }) + "\n"
        return

    if not AsyncOpenAI:
        yield json.dumps({
            "type": "error",
            "content": "Package 'openai' belum terpasang. Jalankan: py -m pip install openai"
        }) + "\n"
        return

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    # Format model name (sesuaikan jika di 9router menggunakan awalan google/)
    target_model = model
    if "flash" in model.lower():
        target_model = "gemini-2.5-flash"
    elif "pro" in model.lower():
        target_model = "gemini-2.5-pro"

    # Thinking info
    if thinking_effort != "none":
        yield json.dumps({
            "type": "thought",
            "content": f"[9router Hub] Mengarahkan ke model {target_model} (Effort: {thinking_effort})...\n"
        }) + "\n"

    # Susun percakapan
    workspace = get_workspace_root()
    system_prompt = (
        f"Anda adalah Antigravity Mobile Assistant yang terhubung ke PC pengguna melalui 9router.\n"
        f"Folder workspace PC: {workspace}\n"
        f"Gaya bahasa: Ramah, terstruktur, gunakan markdown yang rapi."
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history[-6:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})

    messages.append({"role": "user", "content": prompt})

    try:
        response_stream = await client.chat.completions.create(
            model=target_model,
            messages=messages,
            stream=True,
            temperature=0.7
        )

        full_text = ""
        full_thoughts = ""

        async for chunk in response_stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Tangkap reasoning/thinking jika 9router mendukung reasoning_content
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                full_thoughts += reasoning
                yield json.dumps({"type": "thought", "content": reasoning}) + "\n"

            # Tangkap token teks reguler
            content = delta.content
            if content:
                full_text += content
                yield json.dumps({"type": "token", "content": content}) + "\n"

        yield json.dumps({
            "type": "done",
            "full_text": full_text,
            "thoughts": full_thoughts
        }) + "\n"

    except Exception as e:
        yield json.dumps({"type": "error", "content": f"Gagal dari 9router: {str(e)}"}) + "\n"

async def stream_agent_chat(
    prompt: str,
    history: List[Dict[str, Any]] = None,
    model: str = "gemini-2.5-flash",
    thinking_effort: str = "medium"
) -> AsyncGenerator[str, None]:
    """
    Router utama: Otomatis memilih 9router jika diaktifkan,
    atau menggunakan Direct Google AI Studio jika USE_9ROUTER=false.
    """
    use_9router = os.getenv("USE_9ROUTER", "false").lower() == "true"
    ninerouter_key = os.getenv("NINEROUTER_API_KEY")

    # 1. Prioritaskan 9router jika USE_9ROUTER=true atau jika NINEROUTER_API_KEY diisi
    if use_9router or (ninerouter_key and len(ninerouter_key) > 5):
        async for chunk in stream_via_9router(prompt, history, model, thinking_effort):
            yield chunk
        return

    # 2. Direct Gemini / Antigravity Mode
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield json.dumps({
            "type": "error",
            "content": "Kredensial belum diset. Isi NINEROUTER_API_KEY atau GEMINI_API_KEY di backend/.env"
        }) + "\n"
        return

    target_model = "gemini-2.5-flash" if "flash" in model.lower() else "gemini-2.5-pro"

    # Jika Antigravity SDK terpasang (Python >= 3.10)
    if USE_ANTIGRAVITY:
        try:
            config = LocalAgentConfig(
                model=target_model,
                system_instructions="Anda adalah asisten cerdas Antigravity yang terhubung ke aplikasi mobile.",
                capabilities=CapabilitiesConfig()
            )
            async with Agent(config) as agent:
                response = await agent.chat(prompt)
                if hasattr(response, 'thoughts'):
                    async for thought in response.thoughts:
                        yield json.dumps({"type": "thought", "content": thought}) + "\n"
                full_text = ""
                async for token in response:
                    full_text += token
                    yield json.dumps({"type": "token", "content": token}) + "\n"
                yield json.dumps({"type": "done", "full_text": full_text}) + "\n"
                return
        except Exception as e:
            yield json.dumps({"type": "thought", "content": f"[SDK fallback: {str(e)}]"}) + "\n"

    # Fallback ke google-genai
    client = genai.Client(api_key=api_key)
    workspace = get_workspace_root()
    sys_instruction = f"Anda adalah Antigravity Mobile Assistant. Workspace lokal PC: {workspace}."

    thinking_budget = 4096 if thinking_effort != "none" else 0

    try:
        contents = []
        if history:
            for msg in history[-6:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.get("content", ""))]))
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))

        config = types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.7)
        if thinking_budget > 0:
            try:
                config.thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)
            except Exception:
                pass

        full_text = ""
        full_thoughts = ""

        response_stream = client.models.generate_content_stream(model=target_model, contents=contents, config=config)

        for chunk in response_stream:
            if hasattr(chunk, 'candidates') and chunk.candidates:
                candidate = chunk.candidates[0]
                if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if getattr(part, 'thought', False):
                            full_thoughts += part.text or ""
                            yield json.dumps({"type": "thought", "content": part.text or ""}) + "\n"
                        elif part.text:
                            full_text += part.text
                            yield json.dumps({"type": "token", "content": part.text}) + "\n"
            elif chunk.text:
                full_text += chunk.text
                yield json.dumps({"type": "token", "content": chunk.text}) + "\n"
            await asyncio.sleep(0.01)

        yield json.dumps({"type": "done", "full_text": full_text, "thoughts": full_thoughts}) + "\n"
    except Exception as e:
        yield json.dumps({"type": "error", "content": f"Gagal menghasilkan respon: {str(e)}"}) + "\n"
