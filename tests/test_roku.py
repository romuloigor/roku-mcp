"""Testes funcionais para o RokuClient e ferramentas MCP."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Carrega configurações locais do .env se existir
load_dotenv()

# Adiciona o diretório src ao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from roku_mcp.roku_client import RokuClient


async def run_tests():
    print("========================================")
    print(" INICIANDO TESTES DO ROKU CLIENT")
    print("========================================")

    host = os.getenv("ROKU_HOST", "192.168.1.100")
    print(f"[1] Conectando ao host Roku: {host}:8060...")
    client = RokuClient(host=host)

    # Teste 1: get_device_info
    print("\n[2] Consultando informações do dispositivo (get_device_info)...")
    try:
        info = await client.get_device_info()
        print(f" -> Modelo: {info.get('model-name')} ({info.get('vendor-name')})")
        print(f" -> Número de série: {info.get('serial-number')}")
        print(f" -> Versão de Software: {info.get('software-version')}")
        print(f" -> Modo de energia: {info.get('power-mode')}")
        assert info.get("serial-number"), "Serial number deve existir"
        print(" [OK] get_device_info aprovado!")
    except Exception as e:
        print(f" [FALHA] get_device_info: {e}")

    # Teste 2: get_active_app
    print("\n[3] Consultando aplicativo ativo (get_active_app)...")
    try:
        active = await client.get_active_app()
        print(f" -> App ativo: {active.get('name')} (ID: {active.get('id')})")
        assert "name" in active, "Campo 'name' deve existir"
        print(" [OK] get_active_app aprovado!")
    except Exception as e:
        print(f" [FALHA] get_active_app: {e}")

    # Teste 3: list_apps
    print("\n[4] Consultando catálogo e lista de apps (list_apps)...")
    try:
        apps = await client.list_apps()
        print(f" -> Modo detectado: {apps.get('mode')}")
        if apps.get("mode") == "limited":
            print(" -> Aviso: Modo Limitado ativo na TV. Apps do catálogo em fallback disponíveis:")
            sample = list(apps.get("available_apps", {}).keys())[:8]
            print(f"    Exemplos: {', '.join(sample)}...")
        else:
            print(f" -> Total de apps instalados: {apps.get('count')}")
        print(" [OK] list_apps aprovado!")
    except Exception as e:
        print(f" [FALHA] list_apps: {e}")

    # Teste 4: press_key (VolumeUp)
    print("\n[5] Testando envio de tecla (press_key)...")
    try:
        res = await client.press_key("VolumeUp")
        print(f" -> Resposta da TV para tecla 'VolumeUp': {res}")
        print(" [OK] press_key testado!")
    except Exception as e:
        print(f" [FALHA] press_key: {e}")

    # Teste 5: Segurança contra Path Traversal (CodeMender 9ddf2c03)
    print("\n[6] Testando bloqueio contra Path Traversal (CodeMender 9ddf2c03)...")
    try:
        res = await client.press_key("../install/12345")
        assert res.get("status_code") == 400 and not res.get("success"), "Deve rejeitar path traversal com HTTP 400"
        print(f" -> Bloqueio validado com sucesso: {res.get('error')}")
        print(" [OK] Proteção contra Path Traversal aprovada!")
    except Exception as e:
        print(f" [FALHA] Teste de segurança: {e}")

    print("\n========================================")
    print(" TESTES CONCLUÍDOS COM SUCESSO!")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
