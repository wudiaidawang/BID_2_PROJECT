"""配置管理 — YAML 文件 + 环境变量双驱动"""

import os
from pydantic_settings import BaseSettings
from app.core.config_loader import config_loader


# 启动时加载 YAML
config_loader.load("config.yaml")


def _yaml(path: str, default=None):
    """快捷读取 YAML 配置"""
    return config_loader.get(path, default)


class Settings(BaseSettings):
    """应用配置 — 优先 YAML，其次环境变量，最后硬编码默认值"""

    # =========================================================================
    # LLM 配置 — 多厂商切换
    # =========================================================================
    @property
    def llm_provider(self) -> str:
        return _yaml("llm.provider", "hunyuan")

    @property
    def llm_api_key(self) -> str:
        return os.getenv("LLM_API_KEY") or _yaml(f"llm.providers.{self.llm_provider}.api_key", "")

    @property
    def llm_api_url(self) -> str:
        return os.getenv("LLM_API_URL") or _yaml(f"llm.providers.{self.llm_provider}.api_url", "")

    @property
    def llm_model(self) -> str:
        return os.getenv("LLM_MODEL") or _yaml(f"llm.providers.{self.llm_provider}.model", "hunyuan-standard")

    @property
    def llm_temperature(self) -> float:
        return float(_yaml("llm.temperature", 0.3))

    @property
    def llm_max_tokens(self) -> int:
        return int(_yaml("llm.max_tokens", 2000))

    @property
    def llm_timeout(self) -> int:
        return int(_yaml("llm.request_timeout", 60))

    # =========================================================================
    # Embedding 模型配置 — 切换模型只需改 config.yaml 的 embedding.model_name
    # =========================================================================
    @property
    def embedding_model_name(self) -> str:
        """当前选用的 embedding 模型标识"""
        return _yaml("embedding.model_name", "bge-small")

    @property
    def embedding_model(self) -> str:
        """当前选用的 embedding 模型实际名称"""
        return _yaml(f"embedding.models.{self.embedding_model_name}.name", "BAAI/bge-small-zh")

    @property
    def embedding_dimension(self) -> int:
        return int(_yaml(f"embedding.models.{self.embedding_model_name}.dimension", 512))

    @property
    def embedding_device(self) -> str:
        return _yaml("embedding.device", "cpu")

    @property
    def embedding_batch_size(self) -> int:
        return int(_yaml("embedding.batch_size", 32))

    @property
    def hf_endpoint(self) -> str:
        return _yaml("embedding.hf_endpoint", "https://hf-mirror.com")

    # =========================================================================
    # Reranker 配置
    # =========================================================================
    @property
    def reranker_enabled(self) -> bool:
        return bool(_yaml("reranker.enabled", True))

    @property
    def reranker_model(self) -> str:
        return _yaml("reranker.model_name", "BAAI/bge-reranker-base")

    @property
    def reranker_max_input_length(self) -> int:
        return int(_yaml("reranker.max_input_length", 512))

    @property
    def reranker_candidate_pool(self) -> int:
        return int(_yaml("reranker.candidate_pool", 30))

    # =========================================================================
    # 检索配置
    # =========================================================================
    @property
    def top_k(self) -> int:
        return int(_yaml("retrieval.top_k", 5))

    @property
    def vector_recall(self) -> int:
        return int(_yaml("retrieval.vector_recall", 50))

    @property
    def bm25_recall(self) -> int:
        return int(_yaml("retrieval.bm25_recall", 50))

    @property
    def fusion_strategy(self) -> str:
        return _yaml("retrieval.fusion_strategy", "rrf")

    @property
    def rrf_k(self) -> int:
        return int(_yaml("retrieval.rrf_k", 60))

    @property
    def bm25_weight(self) -> float:
        return float(_yaml("retrieval.weighted.bm25_weight", 0.65))

    @property
    def dense_weight(self) -> float:
        return float(_yaml("retrieval.weighted.dense_weight", 0.35))

    @property
    def min_final_score(self) -> float:
        return float(_yaml("retrieval.min_final_score", 0.1))

    @property
    def low_score_threshold(self) -> float:
        return float(_yaml("retrieval.low_score_threshold", 0.25))

    @property
    def query_expansion_enabled(self) -> bool:
        return bool(_yaml("retrieval.query_expansion.enabled", True))

    # =========================================================================
    # 路由 / Planner 配置
    # =========================================================================
    @property
    def router_mode(self) -> str:
        """binary | intent | planner"""
        return _yaml("router.mode", "binary")

    @property
    def template_match_threshold(self) -> float:
        return float(_yaml("router.binary.template_match_threshold", 0.92))

    @property
    def binary_three_way_voting(self) -> bool:
        return bool(_yaml("router.binary.three_way_voting", True))

    @property
    def intent_quick_intercept(self) -> bool:
        return bool(_yaml("router.intent.quick_intercept", True))

    @property
    def planner_plan_then_execute(self) -> bool:
        return bool(_yaml("router.planner.plan_then_execute", False))

    @property
    def planner_max_steps(self) -> int:
        return int(_yaml("router.planner.max_steps", 5))

    @property
    def planner_allow_replan(self) -> bool:
        return bool(_yaml("router.planner.allow_replan", True))

    # =========================================================================
    # Agent 配置
    # =========================================================================
    @property
    def agent_enabled(self) -> bool:
        return bool(_yaml("agent.enabled", False))

    @property
    def agent_max_steps(self) -> int:
        return int(_yaml("agent.max_steps", 5))

    @property
    def agent_temperature(self) -> float:
        return float(_yaml("agent.temperature", 0.3))

    @property
    def checkpoint_enabled(self) -> bool:
        return bool(_yaml("agent.checkpoint.enabled", True))

    @property
    def checkpoint_dir(self) -> str:
        return _yaml("agent.checkpoint.dir", "./checkpoints")

    @property
    def agent_tools(self) -> list:
        """返回所有已启用的工具配置"""
        tools = _yaml("agent.tools", [])
        return [t for t in tools if t.get("enabled", False)]

    # =========================================================================
    # 会话配置
    # =========================================================================
    @property
    def session_backend(self) -> str:
        return _yaml("session.backend", "redis")

    @property
    def session_ttl(self) -> int:
        return int(_yaml("session.ttl", 1800))

    @property
    def max_history(self) -> int:
        return int(_yaml("session.max_history", 10))

    @property
    def redis_host(self) -> str:
        return _yaml("session.redis.host", "localhost")

    @property
    def redis_port(self) -> int:
        return int(_yaml("session.redis.port", 6379))

    @property
    def redis_db(self) -> int:
        return int(_yaml("session.redis.db", 0))

    # =========================================================================
    # 数据路径
    # =========================================================================
    @property
    def data_path_bids(self) -> str:
        return _yaml("data.bid_data_path", "./data/bid_data.xlsx")

    @property
    def db_path(self) -> str:
        return _yaml("data.db_path", "./data/bid_data.db")

    @property
    def pdf_dir(self) -> str:
        return _yaml("data.pdf_dir", "./data/pdfs")

    @property
    def chroma_persist_dir(self) -> str:
        return _yaml("data.chroma_persist_dir", "./chroma_db")

    @property
    def colloquial_map_path(self) -> str:
        return _yaml("data.colloquial_map", "./data/colloquial_map.json")

    @property
    def collections(self) -> list:
        """ChromaDB 集合定义"""
        return _yaml("data.collections", [
            {"name": "bids", "description": "招标项目数据"},
            {"name": "regulations", "description": "法律法规条文"},
        ])

    # =========================================================================
    # 问题改写
    # =========================================================================
    @property
    def qr_colloquial_to_formal(self) -> bool:
        return bool(_yaml("query_rewriter.colloquial_to_formal", True))

    @property
    def qr_redundancy_removal(self) -> bool:
        return bool(_yaml("query_rewriter.redundancy_removal", True))

    @property
    def qr_synonym_expansion(self) -> bool:
        return bool(_yaml("query_rewriter.synonym_expansion", True))

    @property
    def qr_llm_reference_resolution(self) -> bool:
        return bool(_yaml("query_rewriter.llm_reference_resolution", True))

    # =========================================================================
    # 服务 & 评估
    # =========================================================================
    @property
    def host(self) -> str:
        return _yaml("server.host", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(_yaml("server.port", 8000))

    @property
    def debug(self) -> bool:
        return bool(_yaml("server.debug", True))

    @property
    def use_reranker(self) -> bool:
        return self.reranker_enabled

    @property
    def eval_set_path(self) -> str:
        return _yaml("evaluation.eval_set_path", "./data/eval_questions/hybrid_test_cases.json")

    # =========================================================================
    # 法律结构化切块配置
    # =========================================================================
    @property
    def legal_parent_context_enabled(self) -> bool:
        return bool(_yaml("legal_chunking.parent_context_enabled", True))

    @property
    def legal_child_split_threshold(self) -> int:
        return int(_yaml("legal_chunking.child_split_threshold", 400))

    @property
    def legal_child_target_size(self) -> int:
        return int(_yaml("legal_chunking.child_target_size", 300))

    @property
    def legal_child_overlap(self) -> int:
        return int(_yaml("legal_chunking.child_overlap", 40))

    @property
    def legal_header_injection_enabled(self) -> bool:
        return bool(_yaml("legal_chunking.header_injection_enabled", True))

    # =========================================================================
    # Pipeline 可观测性 + 断路器配置
    # =========================================================================
    @property
    def pipeline_tracing_enabled(self) -> bool:
        return bool(_yaml("pipeline.tracing.enabled", True))

    @property
    def pipeline_tracing_show_counts(self) -> bool:
        return bool(_yaml("pipeline.tracing.show_counts", True))

    @property
    def pipeline_tracing_show_timing(self) -> bool:
        return bool(_yaml("pipeline.tracing.show_timing", True))

    def pipeline_stage_config(self, stage_name: str) -> dict:
        """获取某个阶段的配置 {enabled, circuit_breaker}"""
        return {
            "enabled": bool(_yaml(f"pipeline.stages.{stage_name}.enabled", True)),
            "circuit_breaker": _yaml(f"pipeline.stages.{stage_name}.circuit_breaker", "fail_open"),
        }

    # =========================================================================
    # 中文数字转换配置
    # =========================================================================
    @property
    def chinese_number_mapping(self) -> dict:
        return _yaml("chinese_number_mapping.mapping", {})

    @property
    def enable_dynamic_conversion(self) -> bool:
        return bool(_yaml("chinese_number_mapping.enable_dynamic_conversion", True))

    @property
    def enable_digits(self) -> bool:
        return bool(_yaml("chinese_number_mapping.enable_digits", True))

    @property
    def enable_units(self) -> bool:
        return bool(_yaml("chinese_number_mapping.enable_units", True))

    # =========================================================================
    # Pydantic 基础配置（兼容旧代码里的直接属性访问）
    # =========================================================================
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow",
    }


settings = Settings()
