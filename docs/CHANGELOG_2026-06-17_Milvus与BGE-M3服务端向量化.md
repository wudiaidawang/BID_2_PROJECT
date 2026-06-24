# 更新日志12：Milvus + BGE-M3 服务端向量化

**日期：** 2026-06-17

## 背景

将向量存储从本地 ChromaDB 迁移到服务器 Milvus，Embedding 模型从本地 M3E (768维) 切换为服务器 BGE-M3 (1024维)，所有向量化计算在服务端完成。

## 配置变更 (config.yaml)

| 配置项 | 旧值 | 新值 |
|--------|------|------|
| `vector_store.backend` | `chroma` | `milvus` |
| `vector_store.milvus.uri` | `localhost:19530` | `localhost:19531` |
| `vector_store.milvus.database` | `bid_qa` | `panxin_bid_rag_v1` |
| `embedding.model_name` | `m3e` | `bge-m3` |
| `embedding.models.bge-m3` | (无) | `BAAI/bge-m3` / 1024维 |
| `embedding.model_service_url` | (无，默认127.0.0.1:8210) | `localhost:8210` |

## 架构说明

通过 SSH 隧道访问服务器服务：

```
ssh -L 19531:localhost:19531 -L 8210:localhost:8210 admin@47.117.173.99 -N
```

数据流：本地读取 data → 服务器 BGE-M3 embedding → 服务器 Milvus 存储

## 代码修复

### 1. MilvusStore.add_documents 批处理 (milvus_store.py)

原实现一次性 upsert 全部数据（8789条），导致超时。改为每 200 条一批：

- 每批独立调用 embedding
- 每批独立 upsert
- 打印进度 `[Milvus] Batch N: X/total`

### 2. add_documents 自动建集合

原 `add_documents` 不检查集合是否存在，init_pdf.py 先删后增时会报 `collection not found`。加入 `_ensure_collection()` 调用。

### 3. VarChar 字节截断（关键 bug）

**问题：** Milvus VarChar 的 `max_length` 按 UTF-8 **字节**计算，而非字符数。中文文本 1 字符 ≈ 3 字节。35884 字符的中文文本编码后 97086 字节，超过 65535 限制。

**修复：** 新增 `_truncate_text()` 方法，按 UTF-8 字节截断至 65000 字节：

```python
def _truncate_text(self, text: str, max_bytes: int = 65000) -> str:
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode('utf-8', errors='ignore')
```

`_build_row` 和 `add_documents` 均调用此方法。

## 向量化结果

| 集合 | 条数 | 来源 |
|------|------|------|
| `bids` | 8,789 | `data/bid_data.xlsx` Excel 招标记录 |
| `regulations` | 7,319 | 2 本 PDF 法规（滑动窗口 1,969 + Parent-Child 结构化 5,350） |
| **总计** | **16,108** | |

## 验证

- 法规检索 "串通投标处罚" → 相关法条 得分 0.78-0.79
- 招标检索 "北京市政项目最高金额" → 返回匹配项目记录
