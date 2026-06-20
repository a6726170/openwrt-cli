"""配置文件管理 — 支持 YAML 配置文件"""
import os
import json
import yaml
from pathlib import Path


class ConfigManager:
    DEFAULT_CONFIG_PATH = os.path.expanduser("~/.openwrt-cli.yaml")

    def __init__(self, config_path: str = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH

    def load(self) -> dict:
        """加载配置文件（不存在则返回空配置）"""
        if not os.path.exists(self.config_path):
            return self._default_config()

        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save(self, config: dict):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    def _default_config(self) -> dict:
        return {
            "host": None,
            "user": "root",
            "port": 22,
        }