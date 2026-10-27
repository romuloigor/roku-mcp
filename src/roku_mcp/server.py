"""Servidor MCP para controle da Smart TV Roku."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict
from dotenv import load_dotenv

# Carrega variáveis de ambiente se existirem
load_dotenv()

import pathlib
from mcp.server.mcpserver import MCPServer
# Garante que o diretório src e o diretório raiz estejam no sys.path
_current_dir = pathlib.Path(__file__).resolve().parent
_src_dir = _current_dir.parent
_root_dir = _src_dir.parent
for p in (_current_dir, _src_dir, _root_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from roku_mcp.roku_client import RokuClient
except (ModuleNotFoundError, ImportError):
    try:
        from src.roku_mcp.roku_client import RokuClient
    except (ModuleNotFoundError, ImportError):
        from roku_client import RokuClient

roku = RokuClient(
    host=os.getenv("ROKU_HOST", "192.168.1.100"),
    port=int(os.getenv("ROKU_PORT", "8060")),
)

server = MCPServer(
    name="roku_control",
    title="Roku TV Controller",
    description="Servidor MCP de alta performance para controle e automação da Smart TV Roku por voz e texto.",
    version="1.0.0",
)

from starlette.responses import Response

class AlreadyHandledResponse(Response):
    """Resposta vazia para evitar que o Starlette envie cabeçalhos duplos após o término do stream SSE."""
    async def __call__(self, scope, receive, send):
        pass



@server.tool()
async def roku_get_status() -> Dict[str, Any]:
    """Retorna o status atual da TV Roku: estado de energia (ligada/desligada), aplicativo ativo na tela e informações do dispositivo."""
    try:
        active = await roku.get_active_app()
        device = await roku.get_device_info()
        return {
            "power_mode": device.get("power-mode", "Desconhecido"),
            "friendly_name": device.get("friendly-device-name", device.get("user-device-name", "Roku TV")),
            "active_app": active,
            "model": f"{device.get('vendor-name', 'Philco')} {device.get('model-name', 'Roku TV')}",
            "network": {
                "type": device.get("network-type"),
                "network_name": device.get("network-name"),
                "wifi_mac": device.get("wifi-mac"),
            },
            "software_version": device.get("software-version"),
            "uptime_seconds": device.get("uptime"),
        }
    except Exception as e:
        return {"error": f"Falha ao consultar TV Roku: {str(e)}"}


@server.tool()
async def roku_power(action: str = "toggle") -> Dict[str, Any]:
    """Liga ou desliga a Smart TV Roku.
    
    Args:
        action: Ação desejada ('on' para ligar, 'off' para desligar, 'toggle' para alternar o estado atual).
    """
    return await roku.power(action=action)


@server.tool()
async def roku_launch_app(app_name: str) -> Dict[str, Any]:
    """Abre um aplicativo ou canal na TV Roku pelo nome ou ID.
    
    Exemplos suportados: 'youtube', 'netflix', 'prime video', 'globoplay', 'disney+', 'max', 'spotify', 'apple tv', 'pluto tv', 'twitch', etc.
    
    Args:
        app_name: Nome do aplicativo (ex: 'youtube', 'netflix', 'globoplay') ou ID numérico do canal.
    """
    return await roku.launch_app(app_name)


@server.tool()
async def roku_remote_key(key: str) -> Dict[str, Any]:
    """Envia uma tecla do controle remoto para a TV Roku.
    
    Teclas comuns:
    - Navegação: 'home', 'back', 'voltar', 'ok', 'select', 'up', 'down', 'left', 'right'
    - Mídia: 'play', 'pause', 'playpause', 'stop', 'rev', 'fwd'
    - Volume: 'volumeup', 'volumedown', 'mute', 'mudo'
    - TV & Entradas: 'hdmi1', 'hdmi2', 'hdmi3', 'antena', 'tuner', 'info', '*'
    
    Args:
        key: Nome da tecla a ser pressionada.
    """
    return await roku.press_key(key)


@server.tool()
async def roku_adjust_volume(action: str = "up", steps: int = 1) -> Dict[str, Any]:
    """Ajusta o volume da TV Roku ou silencia o som.
    
    Args:
        action: 'up' (aumentar), 'down' (abaixar) ou 'mute' (mutar/desmutar).
        steps: Quantidade de níveis para aumentar ou diminuir (padrão 1, máximo 20).
    """
    return await roku.adjust_volume(action=action, steps=steps)


@server.tool()
async def roku_type_text(text: str) -> Dict[str, Any]:
    """Digita um texto na TV Roku caractere por caractere (ideal para preenchimento de campos de busca).
    
    Args:
        text: Texto a ser digitado na tela da TV.
    """
    return await roku.type_text(text)


@server.tool()
async def roku_search(query: str) -> Dict[str, Any]:
    """Abre a busca universal da Roku TV para procurar filmes, séries, atores ou canais.
    
    Args:
        query: Termo de pesquisa (ex: 'Stranger Things', 'Rock', 'Coldplay').
    """
    return await roku.search(query)


@server.tool()
async def roku_list_apps() -> Dict[str, Any]:
    """Lista os aplicativos disponíveis, catálogo de canais conhecidos e informa o modo de controle da TV."""
    return await roku.list_apps()


def main():
    parser = argparse.ArgumentParser(description="Roku MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transporte do protocolo MCP (padrão: stdio, use sse para acesso remoto/web)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "0.0.0.0"),
        help="Host para servidor SSE/HTTP (padrão: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Porta para servidor SSE/HTTP (padrão: 8000)",
    )

    args = parser.parse_args()

    if args.transport == "sse":
        import json
        import sys
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.middleware.cors import CORSMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(scope, receive, send):
            async with sse.connect_sse(scope, receive, send) as streams:
                await server._lowlevel_server.run(
                    streams[0], streams[1], server._lowlevel_server.create_initialization_options()
                )

        async def dispatch_jsonrpc(req_data: dict) -> dict | None:
            """Despacha requisições JSON-RPC padrão do protocolo MCP."""
            method = req_data.get("method")
            req_id = req_data.get("id")

            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "prompts": {"listChanged": False},
                            "resources": {"listChanged": False},
                        },
                        "serverInfo": {
                            "name": "roku_control",
                            "title": "Roku TV Controller",
                            "version": "1.0.0",
                            "description": "Servidor MCP de alta performance para controle e automação da Smart TV Roku por voz e texto.",
                        },
                    },
                }
            elif method in ("notifications/initialized", "initialized"):
                return None
            elif method == "tools/list":
                tools = await server.list_tools()
                tools_list = [t.model_dump(by_alias=True, exclude_unset=True) for t in tools]
                return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}
            elif method == "tools/call":
                params = req_data.get("params", {})
                name = params.get("name")
                args_map = params.get("arguments", {})
                call_res = await server.call_tool(name, args_map)
                contents = []
                for c in call_res.content:
                    contents.append({"type": c.type, "text": c.text})
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": contents,
                        "isError": getattr(call_res, "is_error", False),
                    },
                }
            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method {method} not found"},
                }

        async def universal_endpoint(request: Request):
            # 1. Trata preflight OPTIONS
            if request.method == "OPTIONS":
                return Response(status_code=200)

            # 2. Se for POST com corpo JSON-RPC (Streamable HTTP / MCP direto)
            if request.method == "POST":
                # Se tiver session_id na URL e for para /messages/, delega para sse.handle_post_message
                if "session_id" in request.query_params:
                    return await sse.handle_post_message(request.scope, request.receive, request._send)

                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        body_json = json.loads(body_bytes)
                        if isinstance(body_json, dict) and "method" in body_json:
                            rpc_res = await dispatch_jsonrpc(body_json)
                            if rpc_res is None:
                                return Response(status_code=204)
                            return JSONResponse(rpc_res)
                except Exception as e:
                    print(f"[JSON-RPC Error] {e}", file=sys.stderr)

            # 3. Se for GET com Accept: text/event-stream ou rota /sse pura
            accept = request.headers.get("accept", "")
            if "text/event-stream" in accept or request.url.path == "/sse":
                await handle_sse(request.scope, request.receive, request._send)
                return AlreadyHandledResponse()

            # 4. Resposta informativa GET padrão para descoberta
            return JSONResponse({
                "status": "online",
                "server": "roku_control",
                "version": "1.0.0",
                "protocol": "mcp-sse-and-http",
                "sse_endpoint": "/sse",
                "messages_endpoint": "/messages/",
            })

        routes = [
            Route("/", endpoint=universal_endpoint, methods=["GET", "HEAD", "OPTIONS", "POST"]),
            Route("/sse", endpoint=universal_endpoint, methods=["GET", "HEAD", "OPTIONS", "POST"]),
            Route("/mcp", endpoint=universal_endpoint, methods=["GET", "HEAD", "OPTIONS", "POST"]),
            Mount("/messages/", app=sse.handle_post_message),
        ]

        # CORS Security: Permitir Google Gemini, AI Studio e origens locais seguras
        cors_env = os.getenv("CORS_ALLOWED_ORIGINS")
        if cors_env:
            allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
        else:
            allowed_origins = [
                "https://gemini.google.com",
                "https://aistudio.google.com",
                "http://localhost",
                "http://localhost:8000",
                "http://127.0.0.1",
                "http://127.0.0.1:8000",
            ]

        app = Starlette(routes=routes)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
            allow_headers=["*"],
            expose_headers=["*"],
        )

        print(f"[Roku MCP] Servidor Universal SSE/HTTP com CORS ativo em http://{args.host}:{args.port}/sse", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        print(f"[Roku MCP] Iniciando transporte Streamable HTTP em http://{args.host}:{args.port}", file=sys.stderr)
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()

