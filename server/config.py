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
        "model": "deepseek-v4-flash",
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

# 各 Provider 默认配置
PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "default_model": "deepseek-v4-flash",
        "note": "申请地址：platform.deepseek.com → API Keys",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "note": "申请地址：platform.openai.com → API Keys",
    },
    "dashscope": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen3-vl-plus"],
        "default_model": "qwen-max",
        "note": "申请地址：bailian.console.aliyun.com → API Keys",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3", "qwen2.5", "mistral", "deepseek-r1:latest"],
        "default_model": "llama3",
        "note": "本地 Ollama 服务，确保已启动：ollama serve",
        "api_key": "ollama",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4", "google/gemini-2.0-flash"],
        "default_model": "openai/gpt-4o",
        "note": "申请地址：openrouter.ai → Keys",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4", "claude-haiku-3.5", "claude-opus-4"],
        "default_model": "claude-sonnet-4",
        "note": "申请地址：console.anthropic.com → API Keys",
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
