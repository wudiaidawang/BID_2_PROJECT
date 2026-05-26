"""YAML 配置加载器 — 单例模式，启动时加载一次，运行时通过 config_loader.get() 读取"""
import os
from typing import Any, Optional
import yaml


class ConfigLoader:
    """YAML 配置文件加载器（单例）"""

    _instance: Optional["ConfigLoader"] = None
    _data: dict = {}
    _loaded: bool = False

    def __new__(cls) -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, path: str = "config.yaml") -> None:
        """加载 YAML 配置文件（幂等，只加载一次）"""
        if self._loaded:
            return

        if not os.path.isabs(path):
            # 相对于项目根目录
            path = os.path.join(os.path.dirname(__file__), "..", "..", path)
            path = os.path.abspath(path)

        if not os.path.exists(path):
            print(f"[ConfigLoader] 配置文件不存在: {path}，使用默认值")
            self._loaded = True
            return

        with open(path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        self._loaded = True
        print(f"[ConfigLoader] 已加载配置: {path}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """按路径读取配置，如 'llm.temperature'、'retrieval.top_k'"""
        if not self._loaded:
            self.load()

        keys = key_path.split(".")
        current = self._data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def reload(self, path: str = "config.yaml") -> None:
        """强制重新加载"""
        self._loaded = False
        self._data = {}
        self.load(path)

    @property
    def data(self) -> dict:
        """获取完整配置数据"""
        if not self._loaded:
            self.load()
        return self._data


# 全局单例
config_loader = ConfigLoader()
