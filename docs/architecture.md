# 系统架构说明

## 院系级校内课程 RAG MVP

| 字段 | 内容 |
|------|------|
| 版本 | 0.1.0 |
| 部署形态 | 单机 Docker Compose |
| 运行时 | Python 3.12 / FastAPI |

> **限域声明**：架构通过四层网关（输入、主题、证据、输出）与保守拒答降低越界回答概率，**无法保证 100% 限域**。运维与产品策略需按「可审计、可拒答、可下架」设计，而非假设模型绝对可控。

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI 应用 (app)                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ Web 模板页    │ │ REST API     │ │ 认证 (魔法链接 / SSO 预留) │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ RAG 编排层：L1 输入 → L2 主题 → 检索 → L3 证据 → LLM → L4 输出 ││
│  └─────────────────────────────────────────────────────────────┘│
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
             ▼                               ▼
┌────────────────────────┐      ┌───────────────────────────────┐
│ PostgreSQL + pgvector   │      │ 外部模型 API (Chat/Embedding) │
│ 元数据 / 向量 / 审计     │      │ OpenAI 兼容或院系批准 endpoint  │
└────────────────────────┘      └───────────────────────────────┘
             │
             ▼
┌────────────────────────┐
│ 本地卷：上传文件 / 日志   │
└────────────────────────┘
```

---

## 2. 组件边界

| 组件 | 职责 | 边界外（不负责） |
|------|------|------------------|
| **Web/API 层** (`app/api`) | HTTP 路由、请求校验；后续承载模板页面与会话 | 不做模型训练；不做复杂前端 SPA |
| **认证模块** (`app/auth`) | 魔法链接签发与校验、角色注入；SSO 适配接口 | MVP 不实现完整 IdP |
| **课程服务** (`app/courses`) | 课程 CRUD、发布状态、权限 | 不做 LMS 选课同步 |
| **Ingest 流水线** (`app/ingestion`) | 文件解析、切片、Embedding 调用、向量写入 | MVP 不做网页爬虫 |
| **检索与生成服务** (`app/rag`) | pgvector 检索、上下文构造、模型调用与引用 | 不做跨库联邦检索 |
| **限域网关** (`app/guardrails`) | 目标为 L1–L4 策略与拒答编码；M0 已实现 L1/L2，L3 位于问答服务 | M0 尚未实现生成后的 L4 校验 |
| **审计模块** (`app/audit`) | 问答与拒答事件持久化 | 不做 SIEM 集成（可导出） |
| **PostgreSQL** | 关系数据、向量索引、事务 | 单实例，MVP 无读写分离 |
| **外部模型 API** | Embedding 与文本生成 | 可用性/隐私受供应商约束 |

### 2.1 认证与授权边界

- **MVP**：`@school.edu` 魔法链接 → 会话 Cookie → 角色 `{student, course_admin, sys_admin}`。
- **正式版**：在 `app/auth/providers.py` 的接口基础上增加 OIDC 实现，令牌映射到同一内部 `User` 模型。
- **课程可见性**：所有已认证 **学生** 可读 **全部已发布课程**；未发布课程仅管理员可见。

---

## 3. 数据流

### 3.1 文档入库（Upload-first）

```
管理员上传文件
    → API 校验 (类型/大小)
    → 存储至 uploads/{course_id}/
    → 解析 (pdf/md/txt)
    → 切片 (chunk_size, overlap 可配置)
    → 调用 Embedding API
    → 写入 document_chunks + pgvector 列
    → 更新课程 ingest 状态
    → (可选) 满足条件后允许发布
```

### 3.2 问答（四层限域）

```
学生提交问题 + 可选 course_id
    → [L1 输入] 规则/分类：注入、敏感、滥用？
         ├─ 否 → 继续
         └─ 是 → 拒答 (reason=L1_*)
    → [L2 主题] 课程范围 + 主题相关性
         ├─ 通过 → 继续
         └─ 否 → 拒答 (reason=L2_*)
    → 向量检索 Top-K (限定已发布课程集合)
    → [L3 证据] 分数阈值、覆盖率、最小片段数
         ├─ 通过 → 继续
         └─ 否 → 拒答或仅返回摘录 (reason=L3_*)
    → 组装 Prompt (仅含片段 + 引用 ID)
    → 调用外部 LLM API
    → [L4 输出] 校验：引用存在、无新增事实、禁语
         ├─ 通过 → 返回答案 + citations
         └─ 否 → 拒答 (reason=L4_*)
    → 写入 audit_events
```

### 3.3 魔法链接登录

```
POST /auth/magic-link { email }
    → 校验校域后缀
    → 生成 signed token (单次, TTL)
    → 发送邮件 (MVP 可日志输出链接)
GET /auth/verify?token=
    → 校验签名与过期
    → 创建/加载 User
    → Set-Cookie session
```

---

## 4. 目录结构（目标骨架）

当前仓库为 **可运行骨架**，以下结构为 MVP 目标布局，随迭代逐步落地：

```
UNMC_RAG/
├── app/
│   ├── main.py                 # FastAPI 入口与健康检查
│   ├── config.py               # 环境配置
│   ├── api/routes.py           # MVP HTTP 接口
│   ├── auth/                   # 邮箱策略与身份提供方接口
│   ├── guardrails/             # 输入、主题、证据和输出限域
│   ├── ingestion/              # 文件、LMS、网页统一采集接口
│   ├── models/                 # 后续 PostgreSQL 业务模型
│   └── rag/                    # 检索契约、问答服务与引用
├── tests/                      # 单元与 API 测试
├── docs/
│   ├── PRD.md
│   └── architecture.md
├── deploy/postgres/init.sql    # pgvector 扩展
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 5. 部署拓扑

### 5.1 MVP：单机 Docker Compose

```yaml
# 目标逻辑拓扑（数据库接入阶段示意，并非当前 compose.yaml 的逐字副本）
services:
  api:
    image: unmc-rag-api
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - LLM_API_BASE=...
      - LLM_API_KEY=...
      - UNMC_RAG_SCHOOL_EMAIL_DOMAIN=school.edu
    volumes:
      - uploads:/app/uploads
    depends_on:
      db: { condition: service_healthy }

  db:
    image: pgvector/pgvector:pg16
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./deploy/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck: ...
```

| 节点 | 规格建议（200–2000 学生） |
|------|---------------------------|
| CPU | 4 vCPU |
| 内存 | 4–8 GB（Embedding 由外部 API 执行） |
| 磁盘 | 100 GB+ SSD（文档 + DB） |
| 网络 | 出站访问外部模型 API |

前置：**Nginx/Caddy** 终止 TLS（生产）；院系防火墙允许 API 出站至模型服务。

### 5.2 网络与安全分区

```
Internet
   │
   ▼
[Reverse Proxy :443]
   │
   ▼
[API Container :8000] ──内网──▶ [PostgreSQL :5432]
   │
   └──出站 HTTPS──▶ [External Model API]
```

- DB 不对公网暴露。
- 密钥经 `.env` 或院系密钥管理注入，不入镜像层。

---

## 6. 扩展路径

| 阶段 | 触发条件 | 演进 |
|------|----------|------|
| **垂直扩展** | 延迟升高、CPU 饱和 | 增大单机资源；增加 uvicorn workers；连接池调优 |
| **读扩展** | 检索 QPS 高 | PostgreSQL 只读副本；检索结果短缓存（Redis，可选） |
| **写扩展** |  ingest  backlog | 异步任务队列（Celery/RQ + Redis）；独立 worker 容器 |
| **应用水平扩展** | 并发 > 50 | 多 API 实例 + 负载均衡；会话粘滞或 JWT；共享 uploads 卷/NFS |
| **高可用** | 正式版 SLA | DB 主从、备份、多 AZ；健康检查与自动重启 |
| **身份** | 院系 SSO 要求 | 基于 `auth/providers.py` 实现 OIDC，替换原型身份入口 |
| **知识源** | LMS 集成 | 在 `ingestion/` 新增 LMS 适配器，不改 RAG 核心 |
| **限域增强** | 误答抽检失败 | 收紧阈值、引入 reranker、人工审核队列 |

---

## 7. 关键决策（ADR 摘要）

### ADR-001：单机 Docker Compose 作为 MVP 部署单元

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | 院系 IT 资源有限，需快速试点。 |
| **决策** | MVP 使用单 Compose 栈（API + PostgreSQL/pgvector）。 |
| **后果** | 无 HA；恢复依赖备份；扩展路径见第 6 节。 |

### ADR-002：外部模型 API，不自建推理

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | GPU 与 MLOps 成本高；院系已可能有教育 API 合约。 |
| **决策** | Embedding 与生成均调用外部 API；通过 `llm_client` 抽象供应商。 |
| **后果** | 延迟与成本受供应商影响；需出站网络与 DPA。 |

### ADR-003：文件上传优先，LMS/爬虫后续

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | LMS 集成周期长；教师可提供导出 PDF。 |
| **决策** | Ingest 首阶段仅支持上传；连接器插件化预留。 |
| **后果** | 材料更新依赖人工上传；后续加 connector 不改表核心。 |

### ADR-004：MVP 魔法链接，SSO 可替换

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | SSO 对接需院系 IdP 排期；试点需尽快开放。 |
| **决策** | 魔法链接为默认；`auth/providers` 预留 OIDC。 |
| **后果** | 链接转发风险；正式版应迁移 SSO 并缩短 token TTL。 |

### ADR-005：已发布课程对全体学生可见

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | MVP 简化授权；院系材料多为院内共享。 |
| **决策** | 不做选课 ACL；仅区分 draft/published 与角色。 |
| **后果** | 敏感课程需谨慎发布；正式版可按 enrollment 收紧。 |

### ADR-006：四层限域 + 保守拒答，不承诺 100%

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | LLM 存在幻觉与 jailbreak 残余风险。 |
| **决策** | 分阶段实施 L1–L4；M0 先交付 L1–L3，接入生成模型前完成 L4；证据不足一律拒答。 |
| **后果** | 部分可答问题被拒；需运营调阈值与抽检。 |

### ADR-007：PostgreSQL + pgvector 统一存储

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | 降低组件数；200–2000 规模向量可承受。 |
| **决策** | 元数据与向量同库；HNSW/IVFFlat 索引按数据量选型。 |
| **后果** | 超大规模需专用向量库或分片；MVP 足够。 |

### ADR-008：FastAPI + 服务端模板页

| 项 | 内容 |
|----|------|
| **状态** | 已接受 |
| **背景** | 院系需轻量 UI，避免前后端分离维护成本。 |
| **决策** | Jinja2 模板 + 少量静态资源；API 与页面同进程。 |
| **后果** | 复杂交互受限；必要时再引入 SPA 仅作前端。 |

---

## 8. 数据模型（核心表，示意）

| 表 | 用途 |
|----|------|
| `users` | 邮箱、角色、创建时间 |
| `courses` | 代码、名称、学期、status(draft/published) |
| `documents` | 所属课程、文件路径、解析状态 |
| `document_chunks` | 文本、embedding vector、metadata JSON |
| `chat_sessions` / `chat_messages` | 可选会话历史 |
| `audit_events` | 问题、层、reason_code、scores、citations |

---

## 9. 可观测与运维

| 项 | MVP |
|----|-----|
| 健康检查 | 当前 `GET /health` 检查进程存活；接入数据库后增加独立 readiness |
| 日志 | 结构化 JSON 至 stdout / 卷 |
| 指标 | 预留 Prometheus 端点（可选 P2） |
| 备份 | `pg_dump` 定时任务（文档说明，MVP 手动） |

---

## 10. 与 PRD 的对应关系

| PRD 章节 | 架构落点 |
|----------|----------|
| 四层限域 | `app/guardrails/*` |
| 魔法链接 / SSO | `app/auth/*` |
| 文件上传 ingest | `app/ingestion/*` |
| 全体学生可见已发布课程 | `courses.status` + 检索过滤器 |
| 非功能 10–50 并发 | 单机 Compose + 限流 + 扩展路径第 6 节 |

详细产品需求见 [PRD.md](./PRD.md)。
