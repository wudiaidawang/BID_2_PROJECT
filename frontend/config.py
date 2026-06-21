# coding: utf-8
"""前端配置"""

import os


class FrontendSettings:
    BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000/api/v1")

    @property
    def INTERNAL_TIMEOUT(self):
        return None if os.environ.get("DEBUG_MODE") == "true" else 10.0

    @property
    def STREAM_TIMEOUT(self):
        return None if os.environ.get("DEBUG_MODE") == "true" else 300.0


settings = FrontendSettings()
