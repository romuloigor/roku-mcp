"""Cliente assíncrono para a API Roku ECP (External Control Protocol)."""

from __future__ import annotations

import asyncio
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx
import xmltodict


class RokuClient:
    """Interface assíncrona para controlar Smart TVs Roku via protocolo ECP."""

    # Catálogo pré-configurado com apps populares no Brasil e globais
    BUILTIN_APPS: Dict[str, str] = {
        "youtube": "837",
        "netflix": "12",
        "prime": "13",
        "prime video": "13",
        "amazon": "13",
        "spotify": "1997",
        "globoplay": "242485",
        "globo play": "242485",
        "globo": "242485",
        "disney": "291097",
        "disney+": "291097",
        "disney plus": "291097",
        "max": "61322",
        "hbo": "61322",
        "hbo max": "61322",
        "apple tv": "551012",
        "apple": "551012",
        "paramount": "41468",
        "paramount+": "41468",
        "paramount plus": "41468",
        "pluto": "39893",
        "pluto tv": "39893",
        "crunchyroll": "24183",
        "twitch": "13842",
        "star+": "633446",
        "clarotv+": "743306",
        "claro tv": "743306",
        "deezer": "20721",
    }

    # Mapeamento de teclas normatizadas
    KEY_MAP: Dict[str, str] = {
        "home": "Home",
        "inicio": "Home",
        "select": "Select",
        "enter": "Select",
        "ok": "Select",
        "back": "Back",
        "voltar": "Back",
        "up": "Up",
        "cima": "Up",
        "down": "Down",
        "baixo": "Down",
        "left": "Left",
        "esquerda": "Left",
        "right": "Right",
        "direita": "Right",
        "play": "Play",
        "pause": "Play",
        "playpause": "Play",
        "reproduzir": "Play",
        "pausar": "Play",
        "stop": "Stop",
        "parar": "Stop",
        "mute": "VolumeMute",
        "mudo": "VolumeMute",
        "volumemute": "VolumeMute",
        "volumeup": "VolumeUp",
        "aumentar": "VolumeUp",
        "aumentar volume": "VolumeUp",
        "volumedown": "VolumeDown",
        "abaixar": "VolumeDown",
        "abaixar volume": "VolumeDown",
        "diminuir volume": "VolumeDown",
        "power": "Power",
        "poweroff": "PowerOff",
        "desligar": "PowerOff",
        "poweron": "PowerOn",
        "ligar": "PowerOn",
        "info": "Info",
        "ajuda": "Info",
        "*": "Info",
        "asterisco": "Info",
        "rev": "Rev",
        "retroceder": "Rev",
        "fwd": "Fwd",
        "avancar": "Fwd",
        "replay": "InstantReplay",
        "canal_cima": "ChannelUp",
        "canal_baixo": "ChannelDown",
        "channelup": "ChannelUp",
        "channeldown": "ChannelDown",
        "hdmi1": "InputHDMI1",
        "hdmi2": "InputHDMI2",
        "hdmi3": "InputHDMI3",
        "tuner": "InputTuner",
        "antena": "InputTuner",
        "av": "InputAV1",
    }

    def __init__(self, host: Optional[str] = None, port: int = 8060, timeout: float = 5.0):
        self.host = host or os.getenv("ROKU_HOST", "192.168.1.100")
        self.port = int(os.getenv("ROKU_PORT", str(port)))
        self.base_url = f"http://{self.host}:{self.port}"
        self.timeout = timeout
        self._cached_apps: Dict[str, str] = dict(self.BUILTIN_APPS)

    async def get_device_info(self) -> Dict[str, Any]:
        """Obtém detalhes de hardware, rede, versão e estado de energia da TV."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/query/device-info")
            resp.raise_for_status()
            data = xmltodict.parse(resp.text)
            return data.get("device-info", {})

    async def get_active_app(self) -> Dict[str, Any]:
        """Obtém o aplicativo ou canal em execução na tela no momento."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/query/active-app")
            resp.raise_for_status()
            data = xmltodict.parse(resp.text)
            active = data.get("active-app", {})
            app_data = active.get("app")
            if isinstance(app_data, dict):
                return {
                    "id": app_data.get("@id"),
                    "name": app_data.get("#text", "Home / Sistema"),
                    "version": app_data.get("@version"),
                    "type": app_data.get("@type"),
                }
            elif isinstance(app_data, list) and app_data:
                first = app_data[0]
                return {
                    "id": first.get("@id"),
                    "name": first.get("#text", "Desconhecido"),
                    "version": first.get("@version"),
                    "type": first.get("@type"),
                }
            return {"name": "Tela Inicial (Home)", "id": None}

    async def list_apps(self) -> Dict[str, Any]:
        """Tenta consultar os apps instalados na TV; caso em modo Limitado, retorna o catálogo de apps conhecidos."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.base_url}/query/apps")
                if "ECP command not allowed in Limited mode" in resp.text:
                    return {
                        "mode": "limited",
                        "notice": "A TV está em 'Modo Limitado'. Para permitir listagem dinâmica completa de todos os canais instalados, configure na TV: Configurações > Sistema > Configurações avançadas do sistema > Controle por aplicativos móveis > Acesso à rede > Permissivo.",
                        "available_apps": self._cached_apps,
                    }

                resp.raise_for_status()
                data = xmltodict.parse(resp.text)
                apps_list = data.get("apps", {}).get("app", [])
                if isinstance(apps_list, dict):
                    apps_list = [apps_list]

                installed = {}
                for app in apps_list:
                    app_id = app.get("@id")
                    app_name = app.get("#text")
                    if app_name and app_id:
                        installed[app_name] = app_id
                        self._cached_apps[app_name.lower()] = app_id

                return {
                    "mode": "permissive",
                    "installed_apps": installed,
                    "count": len(installed),
                }
            except Exception as e:
                return {
                    "mode": "fallback",
                    "error": str(e),
                    "available_apps": self._cached_apps,
                }

    async def press_key(self, key_name: str) -> Dict[str, Any]:
        """Envia uma tecla do controle remoto e retorna o resultado detalhado."""
        raw_key = key_name.strip()
        normalized = raw_key.lower()

        # 1. Mapeamento via catálogo canônico de teclas
        if normalized in self.KEY_MAP:
            roku_key = self.KEY_MAP[normalized]
        else:
            # 2. Defesa rigorosa contra Path Traversal / Injection (CodeMender finding 9ddf2c03)
            # Permite estritamente identificadores Roku oficiais [a-zA-Z0-9_] sem '../', '/', '?' ou '#'
            if not re.match(r"^[A-Za-z0-9_]{1,32}$", raw_key):
                return {
                    "success": False,
                    "key": raw_key,
                    "status_code": 400,
                    "error": (
                        f"Tecla inválida ou não autorizada: {raw_key!r}. "
                        "Apenas teclas alfanuméricas seguras são permitidas (ex: 'home', 'back', 'play', 'volume_up')."
                    ),
                }
            roku_key = raw_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/keypress/{roku_key}")
            if resp.status_code == 200:
                return {"success": True, "key": roku_key, "status_code": 200}
            elif resp.status_code == 403:
                return {
                    "success": False,
                    "key": roku_key,
                    "status_code": 403,
                    "error": (
                        "Comando bloqueado pelo 'Modo Limitado' da TV Roku. "
                        "Para liberar controle total de teclas e energia, acerte na TV: "
                        "Configurações > Sistema > Configurações avançadas do sistema > "
                        "Controle por aplicativos móveis > Acesso à rede > Permissivo."
                    ),
                }
            return {
                "success": False,
                "key": roku_key,
                "status_code": resp.status_code,
                "error": f"Erro HTTP {resp.status_code} retornado pela TV Roku",
            }

    async def power(self, action: str = "toggle") -> Dict[str, Any]:
        """Controla a energia da TV ('on', 'off' ou 'toggle')."""
        action_clean = action.strip().lower()
        if action_clean in ("on", "ligar", "true"):
            key = "PowerOn"
        elif action_clean in ("off", "desligar", "false"):
            key = "PowerOff"
        else:
            key = "Power"

        res = await self.press_key(key)
        return {"action": action_clean, "key_sent": key, **res}

    async def adjust_volume(self, action: str = "up", steps: int = 1) -> Dict[str, Any]:
        """Aumenta, abaixa ou silencia o volume por N passos."""
        act = action.strip().lower()
        if act in ("mute", "mudo", "silenciar"):
            res = await self.press_key("VolumeMute")
            return {"action": "mute", "steps": 1, **res}

        key = "VolumeUp" if act in ("up", "aumentar", "+") else "VolumeDown"
        steps = max(1, min(steps, 20))  # limite de segurança 1 a 20

        last_res = {}
        for _ in range(steps):
            last_res = await self.press_key(key)
            if not last_res.get("success"):
                break
            await asyncio.sleep(0.08)

        return {"action": act, "steps": steps, **last_res}

    async def launch_app(self, app_name_or_id: str) -> Dict[str, Any]:
        """Abre um aplicativo/canal pelo nome (ex: 'youtube', 'netflix') ou ID numérico."""
        query = app_name_or_id.strip()

        # Se já for ID numérico
        if query.isdigit():
            target_id = query
            target_name = query
        else:
            query_lower = query.lower()
            # Busca exata no catálogo
            if query_lower in self._cached_apps:
                target_id = self._cached_apps[query_lower]
                target_name = query
            else:
                # Busca por substring
                match = None
                for name, app_id in self._cached_apps.items():
                    if query_lower in name or name in query_lower:
                        match = (name, app_id)
                        break
                if match:
                    target_name, target_id = match
                else:
                    return {
                        "success": False,
                        "error": f"Aplicativo '{app_name_or_id}' não encontrado no catálogo. Apps conhecidos: {list(self.BUILTIN_APPS.keys())}",
                    }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/launch/{target_id}")
            success = resp.status_code == 200
            return {
                "success": success,
                "app_name": target_name,
                "app_id": target_id,
                "status_code": resp.status_code,
            }

    async def type_text(self, text: str) -> Dict[str, Any]:
        """Digita uma sequência de caracteres na TV (útil para campos de busca)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            sent_count = 0
            for char in text:
                encoded = urllib.parse.quote(char)
                url = f"{self.base_url}/keypress/Lit_{encoded}"
                resp = await client.post(url)
                if resp.status_code == 200:
                    sent_count += 1
                await asyncio.sleep(0.05)
            return {"success": True, "text": text, "characters_sent": sent_count}

    async def search(self, query: str) -> Dict[str, Any]:
        """Abre a busca universal da Roku com o termo digitado."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            encoded = urllib.parse.quote(query)
            resp = await client.post(f"{self.base_url}/search/browse?keyword={encoded}")
            if "ECP command not allowed in Limited mode" in resp.text:
                return {
                    "success": False,
                    "mode": "limited",
                    "error": "Busca direta via ECP bloqueada pelo Modo Limitado da TV. Ative o modo Permissivo nas configurações da TV ou use a digitação de texto com 'roku_type_text'.",
                }
            return {"success": resp.status_code == 200, "query": query}
