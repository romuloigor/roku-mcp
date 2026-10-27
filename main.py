"""Ponto de entrada principal para execução do Roku MCP Server."""

import sys
from pathlib import Path

# Adiciona diretório src ao path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from roku_mcp.server import main

if __name__ == "__main__":
    main()
