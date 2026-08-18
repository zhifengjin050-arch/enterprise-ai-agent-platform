# Knowledge Intelligence Architecture

## 概述

Phase 5 将同步入库的 Document 升级为企业智能知识系统：**Knowledge Graph + Advanced RAG**。

```
Document (SyncEngine / Pipeline)
    │
 SmartChunker          ← Markdown 标题 / 代码块 / 表格保护
    │
 DocumentChunk         ← document_chunks 表
    │
 ChunkEmbedding        ← 复用 app.embedding
    │
 KnowledgeRetriever    ← Vector + BM25/FTS + Graph
    │
 Reranker              ← TopK → TopN
    │
 ContextBuilder        ← LLM 上下文组装
```

同时构建：

```
Entity Extraction → Knowledge Graph (Entity / Relation / GraphNode / GraphEdge)
```

---

## 包布局说明

`app/knowledge/` **原本已是文档资产层**（Document/Category/Tag）。Phase 5 在同一包内**新增** Intelligence 模块，不覆盖现有文件：

| 文件 | 职责 |
|------|------|
| `chunking.py` | SmartChunker |
| `chunk_models.py` | DocumentChunk ORM |
| `chunk_repository.py` | Chunk 持久化 |
| `embedding.py` | ChunkEmbeddingService（wrap `app.embedding`） |
| `hybrid_search.py` | IntelligenceHybridSearch（wrap `app.search.hybrid`） |
| `retrieval.py` | KnowledgeRetriever + RetrievalResult |
| `reranker.py` | Reranker |
| `graph.py` | KnowledgeGraph / GraphNode / GraphEdge（wrap `app.graph` / entity / relation） |
| `memory.py` | KnowledgeMemory |
| `context_builder.py` | IntelligenceContextBuilder |
| `intelligence.py` | `process_document_intelligence()` 编排入口 |

复用（不重写）：

- `app.embedding` — EmbeddingProvider
- `app.search.hybrid` — RRF HybridSearch
- `app.entity` / `app.relation` — 实体关系表与抽取器
- `app.graph` — GraphBuilder / GraphQueryService
- `app.query.builder` — ContextBuilder
- Phase 2 异常体系 / Phase 3 Connector / Phase 4 SyncEvent

---

## 1. Smart Chunking

```python
from app.knowledge import SmartChunker

chunker = SmartChunker(max_tokens=512, overlap_tokens=64)
chunks = chunker.chunk(markdown, document_id="doc-1", title="Guide")
```

能力：

- Markdown 标题（H1–H6）切分
- 代码块（\`\`\` / \`\`\`\`）原子保护
- 表格（pipe table）原子保护
- 超长段落语义/硬切分
- Token 预算与 overlap

---

## 2. Hybrid Retrieval

统一接口：

```python
from app.knowledge import KnowledgeRetriever, RetrievalResult

retriever = KnowledgeRetriever(recall_k=20, top_n=5)
results: list[RetrievalResult] = await retriever.retrieve(
    "kubernetes 部署失败",
    use_graph=True,
    use_rerank=True,
    session=session,
)
```

`RetrievalResult` 字段：

| 字段 | 说明 |
|------|------|
| document_id | 文档 ID |
| chunk_id | Chunk ID（文档级命中可为空） |
| score | 相关分（rerank 后） |
| source | hybrid / vector / bm25 / graph |
| metadata | 扩展元数据 |
| content / title | 便于组装上下文 |

融合通道：

1. **Vector** — SemanticSearch / ChromaDB  
2. **BM25/FTS** — FullTextSearch  
3. **Knowledge Graph** — 查询命中实体时对结果加分  

---

## 3. Reranker

```
TopK 召回 → Rerank（词法重叠 + 原分加权） → TopN
```

可注入外部 `score_fn`（未来接 Cross-Encoder）。

---

## 4. Entity & Graph

实体类型（含 Phase 5 扩展）：

`Person` / `Organization` / `Project` / `System` / `API` / `Technology`  
（以及既有 Service、Component、Tool、Team…）

表（已有 + 新增）：

| 表 | 状态 |
|----|------|
| `knowledge_entities` | 已有（0003） |
| `knowledge_relations` | 已有（0003） |
| `document_chunks` | **新增**（0007） |

```python
from app.knowledge import KnowledgeGraph

kg = KnowledgeGraph(session)
await kg.build_from_document(title, content, document_id=doc_id)
node = await kg.get_entity(entity_id)
subgraph = await kg.get_subgraph(entity_id, depth=1)
```

---

## 5. Pipeline 对接

`knowledge_pipeline.store_node` 在文档入库后 **best-effort** 调用：

```python
process_document_intelligence(session, document_id=..., title=..., content=...)
```

执行：分块持久化 + 图谱构建（embedding 默认跳过，因 embed_node 已处理文档级向量）。

也可由 SyncEvent / API 主动触发：

```http
POST /api/knowledge/documents/{id}/intelligence
```

---

## 6. API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/knowledge/search` | Intelligence 混合检索 |
| GET | `/api/knowledge/search` | 旧版 ILIKE 搜索（保留） |
| GET | `/api/knowledge/entities/{id}` | 实体详情 |
| GET | `/api/knowledge/graph/{id}` | 以实体为中心的子图 |
| POST | `/api/knowledge/documents/{id}/intelligence` | 触发分块/图谱处理 |

### POST /search 示例

```json
{
  "query": "kubernetes OOM",
  "top_n": 5,
  "recall_k": 20,
  "use_graph": true,
  "use_rerank": true
}
```

---

## 7. 迁移

```bash
alembic upgrade head
```

Revision: `0007_add_document_chunks`

---

## 8. 测试

```
tests/knowledge/
├── test_chunking.py
├── test_embedding.py
├── test_hybrid_search.py
├── test_reranker.py
├── test_graph.py
└── test_api.py
```

```bash
python -m pytest tests/knowledge/ tests/test_connector/ tests/sync_engine/ tests/core/ -q
```

---

## 9. 后续建议

1. Chunk 级 Chroma upsert（当前 embedding_id 占位）
2. Cross-Encoder Reranker 接入
3. SyncEvent → 自动触发 `process_document_intelligence`
4. Graph 多跳检索（depth>1 路径打分）
5. 长期记忆持久化（当前 LRU + ConversationMemory）
