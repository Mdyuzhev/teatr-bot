"""
Утилита для вызова MCP-сервера homelab (streamable-http).
Использование: python scripts/mcp_call.py <tool_name> '<json_args>'
Например:
  python scripts/mcp_call.py run_shell_command '{"command": "echo hello"}'
  python scripts/mcp_call.py get_docker_ps '{}'
"""
import os
import sys
import json
import uuid
import requests


MCP_SERVER = os.getenv("MCP_SERVER_URL", "http://localhost:8765")
MCP_ENDPOINT = f"{MCP_SERVER}/mcp"


def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Вызвать инструмент MCP-сервера через streamable-http (JSON-RPC)."""

    # 1. Инициализация сессии
    init_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "teatr-bot", "version": "1.0.0"},
        },
    }

    resp = requests.post(
        MCP_ENDPOINT,
        json=init_payload,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        timeout=30,
    )
    resp.raise_for_status()

    # Извлечь session-id из заголовков
    session_id = resp.headers.get("mcp-session-id", "")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["mcp-session-id"] = session_id

    # 2. Отправить initialized notification
    notif = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    requests.post(MCP_ENDPOINT, json=notif, headers=headers, timeout=10)

    # 3. Вызов инструмента
    tool_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    resp = requests.post(MCP_ENDPOINT, json=tool_payload, headers=headers, timeout=120)
    resp.raise_for_status()

    # Ответ может быть JSON или SSE
    content_type = resp.headers.get("content-type", "")

    if "text/event-stream" in content_type:
        # Парсим SSE — ищем последний event с data
        result = None
        for line in resp.text.splitlines():
            if line.startswith("data: "):
                try:
                    result = json.loads(line[6:])
                except json.JSONDecodeError:
                    pass
        return result or {"error": "No data in SSE stream"}
    else:
        return resp.json()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python scripts/mcp_call.py <tool_name> '<json_args>'")
        sys.exit(1)

    tool = sys.argv[1]
    args = json.loads(sys.argv[2])

    result = call_mcp_tool(tool, args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
