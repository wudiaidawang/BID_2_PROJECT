"""配置管理"""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置"""
    
    # LLM配置

    llm_api_key: str = "sk-L1HSFGczPAXb6Z8RTRTK6GnZqRApDMALJshDgm16r3hOF31L"
    llm_api_url: str = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
    llm_model: str = "hunyuan-standard"

    # 数据路径
    data_path_bids: str = "./data/bid_data.xlsx"
    data_path_prices: str = "./data/price_data.xlsx"
    pdf_dir: str = "./data/pdfs"
    
    # Chroma配置
    chroma_persist_dir: str = "./chroma_db"
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # 检索配置
    top_k: int = 5
    vector_recall: int = 50
    embedding_model: str = "BAAI/bge-small-zh"
    use_reranker: bool = True
    
    # 会话配置
    session_ttl: int = 1800
    max_history: int = 10
    
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    db_path: str = "./data/bid_data.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()