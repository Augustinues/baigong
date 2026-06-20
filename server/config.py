"""百工配置管理"""

import os
import yaml
from pathlib import Path

CONFIG_DIR = Path.home() / ".baigong"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DB_PATH = CONFIG_DIR / "baigong.db"

DEFAULT_CONFIG = {
    "version": "1.0",
    "llm": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
    },
    "agents": [],
    "tools": {
        "enabled": [
            "web_search",
            "web_extract",
            "file_read",
            "file_write",
            "code_exec",
        ]
    },
}


class BaigongConfig:
    def __init__(self):
        self._data = None

    @property
    def path(self) -> Path:
        return CONFIG_PATH

    @property
    def exists(self) -> bool:
        return CONFIG_PATH.exists()

    def load(self) -> dict:
        if self._data is not None:
            return self._data
        if not CONFIG_PATH.exists():
            self._data = dict(DEFAULT_CONFIG)
            return self._data
        with open(CONFIG_PATH) as f:
            self._data = yaml.safe_load(f) or dict(DEFAULT_CONFIG)
        return self._data

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)

    def get(self, key: str, default=None):
        """点号路径取值，例如 llm.api_key"""
        d = self.load()
        parts = key.split(".")
        for p in parts:
            if isinstance(d, dict):
                d = d.get(p)
            else:
                return default
        return d if d is not None else default

    def set(self, key: str, value):
        """点号路径设值"""
        d = self.load()
        parts = key.split(".")
        for p in parts[:-1]:
            if p not in d:
                d[p] = {}
            d = d[p]
        d[parts[-1]] = value
        self.save()

    def add_agent(self, agent_config: dict):
        config = self.load()
        if "agents" not in config:
            config["agents"] = []
        config["agents"].append(agent_config)
        self.save()

    def remove_agent(self, agent_id: str):
        config = self.load()
        config["agents"] = [a for a in config.get("agents", []) if a.get("id") != agent_id]
        self.save()

    def update_agent(self, agent_id: str, updates: dict):
        config = self.load()
        for a in config.get("agents", []):
            if a.get("id") == agent_id:
                a.update(updates)
                break
        self.save()

    def reset(self):
        self._data = dict(DEFAULT_CONFIG)
        self.save()


config = BaigongConfig()
