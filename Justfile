# Justfile para automação do Roku MCP Server

set shell := ["bash", "-c"]

# Ajuda e lista de comandos disponíveis
default:
    @just --list

# Executa os testes funcionais contra a TV Roku
test:
    uv run python tests/test_roku.py

# Inicia o servidor MCP localmente em modo Stdio (para Antigravity IDE / Desktop)
dev:
    uv run python src/roku_mcp/server.py --transport stdio

# Inicia o servidor MCP em modo SSE na porta 8000 (para Web / iPhone)
serve:
    uv run python src/roku_mcp/server.py --transport sse --host 0.0.0.0 --port 8000

# Exponha a porta 8000 via Tailscale Funnel na internet (gera HTTPS oficial)
funnel:
    tailscale funnel 8000

# Instala o serviço em segundo plano no macOS (LaunchAgent dinâmico)
install-service:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p ~/Library/LaunchAgents
    UV_PATH="$(command -v uv || echo '/opt/homebrew/bin/uv')"
    CUR_DIR="$(pwd)"
    ROKU_IP="$(grep -E '^ROKU_HOST=' .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || true)"
    if [ -z "$ROKU_IP" ]; then
        ROKU_IP="192.168.1.100"
    fi
    sed -e "s|__WORKING_DIR__|$CUR_DIR|g" \
        -e "s|__UV_PATH__|$UV_PATH|g" \
        -e "s|__ROKU_HOST__|$ROKU_IP|g" \
        scripts/com.user.roku-mcp.plist.template > ~/Library/LaunchAgents/com.user.roku-mcp.plist
    launchctl unload ~/Library/LaunchAgents/com.user.roku-mcp.plist 2>/dev/null || true
    launchctl unload ~/Library/LaunchAgents/com.romuloigor.roku-mcp.plist 2>/dev/null || true
    rm -f ~/Library/LaunchAgents/com.romuloigor.roku-mcp.plist 2>/dev/null || true
    launchctl load ~/Library/LaunchAgents/com.user.roku-mcp.plist
    echo "Serviço com.user.roku-mcp instalado e iniciado com sucesso!"
    echo "Logs disponíveis em /tmp/roku-mcp.stdout.log e /tmp/roku-mcp.stderr.log"

# Desinstala o serviço em segundo plano
uninstall-service:
    #!/usr/bin/env bash
    launchctl unload ~/Library/LaunchAgents/com.user.roku-mcp.plist 2>/dev/null || true
    launchctl unload ~/Library/LaunchAgents/com.romuloigor.roku-mcp.plist 2>/dev/null || true
    rm -f ~/Library/LaunchAgents/com.user.roku-mcp.plist ~/Library/LaunchAgents/com.romuloigor.roku-mcp.plist
    echo "Serviço com.user.roku-mcp removido com sucesso."

# Verifica status do servidor e da TV
status:
    #!/usr/bin/env bash
    ROKU_IP="$(grep -E '^ROKU_HOST=' .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || true)"
    if [ -z "$ROKU_IP" ]; then
        ROKU_IP="192.168.1.100"
    fi
    echo "=== Status da TV Roku ($ROKU_IP) ==="
    curl -s -m 2 "http://$ROKU_IP:8060/query/active-app" | grep -o "<app.*</app>" || echo "TV inacessível ($ROKU_IP)"
    echo ""
    echo "=== Status do Servidor MCP SSE Local ==="
    curl -s -I -m 2 http://127.0.0.1:8000/sse | head -n 1 || echo "Servidor SSE não está rodando"
