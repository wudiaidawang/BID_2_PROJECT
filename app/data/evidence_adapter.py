"""EvidenceAdapter — 将各种检索结果转为标准 Evidence 格式"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.data.schema.evidence import Evidence, Citation


class EvidenceAdapter:
    """适配器：内部 chunk / SQL 结果 / 检索结果 → Evidence"""

    @staticmethod
    def from_rag_chunk(chunk: Dict) -> Evidence:
        """从 RAG 检索 chunk 转为 Evidence"""
        meta = chunk.get("metadata", chunk.get("data", {}))
        text = chunk.get("text", "")
        score = chunk.get("score", 0.0)
        chunk_id = chunk.get("id", "")

        # 判断来源类型
        law_name = meta.get("law_name", "")
        article_id = meta.get("article_id", "")
        collection = meta.get("collection", "")
        source_type = "rag"

        # 标题
        title = meta.get("source", meta.get("project_name", ""))
        if law_name and article_id:
            title = f"{law_name} 第{article_id}条"
        elif meta.get("project_name"):
            title = meta.get("project_name")

        # 权威等级
        authority = 2 if law_name else 1  # 法规来源权威更高

        # 新鲜度
        freshness = 1
        publish_date = meta.get("publish_date", meta.get("发布时间", ""))
        if publish_date:
            freshness = 2  # 有明确日期的更新鲜

        # 稳定 ID
        stable_id = EvidenceAdapter._stable_id(
            "rag", str(chunk_id), text[:200]
        )

        return Evidence(
            id=stable_id,
            content=text,
            title=str(title),
            source_type=source_type,
            authority_level=authority,
            freshness_level=freshness,
            score=float(score),
            citation=Citation(
                source_type=source_type,
                title=str(title),
                source_name=law_name,
                article_id=str(article_id),
                law_name=law_name,
            ),
            metadata=meta,
        )

    @staticmethod
    def from_sql_result(sql: str, rows: List[Dict],
                        question: str = "") -> Evidence:
        """从 SQL 查询结果转为 Evidence"""
        ts = datetime.now(timezone.utc).isoformat()

        # 序列化为可读格式
        if not rows:
            content = json.dumps({"query": question, "result": "无数据"}, ensure_ascii=False)
        else:
            content = json.dumps({
                "query": question,
                "sql": sql,
                "row_count": len(rows),
                "data": rows[:50],  # 最多 50 行
            }, ensure_ascii=False, default=str)

        stable_id = EvidenceAdapter._stable_id("sql", question, sql)
        title = f"SQL查询结果 ({len(rows)}行)"

        return Evidence(
            id=stable_id,
            content=content,
            title=title,
            source_type="sql",
            authority_level=3,     # 数据库结果权威最高
            freshness_level=3,
            score=1.0,
            citation=Citation(
                source_type="sql",
                title=title,
                source_name="bid_data",
            ),
            metadata={"sql": sql, "row_count": len(rows)},
            retrieval_timestamp=ts,
        )

    @staticmethod
    def _stable_id(namespace: str, primary: str, content: str) -> str:
        payload = f"{namespace}|{primary}|{content}"
        return hashlib.sha256(payload.encode()).hexdigest()[:24]
