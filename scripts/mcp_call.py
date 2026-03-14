"""
Утилита для вызова MCP-сервера homelab.
Использование: python scripts/mcp_call.py <tool_name> '<json_args>'
Например:
  python scripts/mcp_call.py run_shell_command '{"command": "echo hello"}'
  python scripts/mcp_call.py get_docker_ps {}
"""
import sys
import json
import requests


MCP_SERVER = "http://192.168.1.74:8765"


def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Вызвать инструмент MCP-сервера и вернуть результат."""
    payload = {
        "tool": tool_name,
        "arguments": arguments
    }
    response = requests.post(
        f"{MCP_SERVER}/call",
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python scripts/mcp_call.py <tool_name> '<json_args>'")
        sys.exit(1)

    tool = sys.argv[1]
    args = json.loads(sys.argv[2])

    result = call_mcp_tool(tool, args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
