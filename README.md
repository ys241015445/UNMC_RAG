# UNMC RAG — 院系级校内课程问答 MVP

低成本、校内可部署的课程材料 RAG（检索增强生成）原型，面向 **200–2000 名学生**、**10–50 峰值并发** 的院系场景。

## 当前状态说明

> **本仓库是可运行骨架，而非完整生产系统。**

当前已具备：

- FastAPI 应用、`/health` 与 `/api/v1/chat` 接口
- 学校邮箱域名校验接口边界
- 提示注入/明显无关问题拦截、证据不足拒答和引用数据结构
- PostgreSQL/pgvector Docker Compose 配置
- 21 个认证、限域、问答服务与 API 自动化测试
- 产品与技术文档：[docs/PRD.md](./docs/PRD.md)、[docs/architecture.md](./docs/architecture.md)

尚未完备或需自行补齐的部分包括但不限于：

- 完整的认证、ingest、四层限域与外部模型 API 集成
- 生产级 HTTPS、备份、监控、SSO 对接
- LMS / 网页抓取等扩展知识源

系统采用 **输入 → 主题 → 证据 → 输出** 四层限域与 **保守拒答** 策略，**无法保证 100% 限域**。试点与上线前请阅读 [PRD 拒答策略](./docs/PRD.md#6-拒答策略) 与 [架构限域声明](./docs/architecture.md)。

当前聊天接口使用 `X-School-Email` 请求头演示邮箱域名门禁。该请求头可被伪造，**仅适用于本机开发，不得作为真实认证或直接暴露到公网**；试点前必须完成魔法链接或学校 SSO。

---

## 文档

| 文档 | 说明 |
|------|------|
| [docs/PRD.md](./docs/PRD.md) | 产品需求：背景、目标、用户故事、功能、安全、验收与里程碑 |
| [docs/architecture.md](./docs/architecture.md) | 系统架构：组件边界、数据流、部署拓扑、扩展路径与 ADR |

---

## 技术栈（MVP）

| 层级 | 选型 |
|------|------|
| 语言 / 框架 | Python 3.12、FastAPI |
| 前端 | 服务端轻量模板页（Jinja2） |
| 数据库 | PostgreSQL + pgvector |
| 部署 | 单机 Docker Compose |
| 模型 | 外部 Embedding / Chat API |
| 知识来源 | **文件上传优先**；LMS / 网页后续 |

认证：**学校邮箱魔法链接**（MVP）；正式版可替换为校内 SSO，详见架构文档。

---

## 快速开始

### 环境要求

- Python **3.12+**
- Docker & Docker Compose v2
- （可选）院系批准的外部模型 API Key

### 本地开发

```bash
# 克隆并进入仓库
git clone <repo-url> UNMC_RAG && cd UNMC_RAG

# 创建虚拟环境并安装依赖
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"

# 环境变量（示例）
cp .env.example .env
# 编辑 .env：数据库密码、模型密钥和学校邮箱域名等

# 启动 PostgreSQL（pgvector）
docker compose up -d db

# 运行 API（开发模式，热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开问答页：<http://localhost:8000/>  
API 文档：<http://localhost:8000/docs>。

原型调用示例：

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-School-Email: student@unmc.edu' \
  -d '{"question":"高等数学中的导数是什么？"}'
```

尚未接入课程索引时，课程问题会安全返回 `insufficient_evidence`。

### Docker Compose 一键启动

先准备 `.env`（至少设置数据库密码）与抓取语料：

```bash
cp .env.example .env
# 编辑 .env：设置 POSTGRES_PASSWORD=...
# 若尚无语料：
pip install -e ".[scrape]"
python scripts/scrape_current_students.py

docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health
```

浏览器打开：<http://localhost:8000/>  
Compose 会把 `./data/scraped` 只读挂载进容器，并启用本地关键词检索。

### 测试

```bash
pytest
pytest --cov=app --cov-report=term-missing
ruff check app tests
```

### 抓取 Current Students 公开页（独立脚本）

不接入聊天 API。仅抓取 `www.nottingham.edu.my/CurrentStudents/` 前缀下的 HTML 正文；PDF 等附件只记链接。

```bash
pip install -e ".[scrape]"
python scripts/scrape_current_students.py \
  --out-dir data/scraped/current_students \
  --max-pages 200 \
  --delay 0.75
```

产物：`documents.jsonl`、`pages/*.md`、`index.json`、`attachments.jsonl`、`run_meta.json`（目录默认被 gitignore）。

### 将抓取语料接入问答原型

当前阶段使用**本地关键词检索**（尚无 embedding / pgvector）。配置 `.env`：

```bash
cp .env.example .env
# 确认：
# UNMC_RAG_CORPUS_PATH=data/scraped/current_students/documents.jsonl
# UNMC_RAG_MINIMUM_RETRIEVAL_SCORE=0.3
# UNMC_RAG_COURSE_TERMS=...含 graduation,shuttle 等主题词...

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

示例：

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-School-Email: student@unmc.edu' \
  -d '{"question":"When is the next graduation ceremony?"}'
```

未设置 `UNMC_RAG_CORPUS_PATH` 或文件不存在时，行为与原先一致（证据不足拒答）。

### 常用环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 下一阶段数据库接线预留；当前 M0 API 尚未读取 |
| `LLM_API_BASE` | 外部模型 API 基址（智谱默认 `https://open.bigmodel.cn/api/paas/v4/`） |
| `LLM_API_KEY` | API 密钥（写入本地 `.env`，勿提交 Git） |
| `LLM_MODEL` | 聊天模型名，例如 `glm-4.5-air` |
| `UNMC_RAG_SCHOOL_EMAIL_DOMAIN` | 允许的学校邮箱域 |
| `UNMC_RAG_COURSE_TERMS` | 原型主题门禁使用的课程关键词 |
| `UNMC_RAG_MINIMUM_RETRIEVAL_SCORE` | 最低证据分数 |
| `UNMC_RAG_CORPUS_PATH` | 本地 `documents.jsonl` 路径；启用关键词检索 |
| `UNMC_RAG_CHUNK_SIZE` / `CHUNK_OVERLAP` | 切片大小与重叠 |
| `UNMC_RAG_RETRIEVAL_TOP_K` | 返回的最大切片数 |

---

## 项目结构（目标）

```
app/api/          # HTTP API
app/auth/         # 邮箱策略与身份提供方接口
app/guardrails/   # 输入与主题限域
app/ingestion/    # 文件、LMS、网页采集接口
app/rag/          # 检索与问答编排
tests/            # pytest
docs/             # PRD、架构
deploy/postgres/  # pgvector 初始化
compose.yaml
```

完整说明见 [docs/architecture.md](./docs/architecture.md)。

---

## 许可与合规

部署前请确认：外部模型 API 的数据处理协议、校内个人信息保护要求，以及课程材料的版权与发布范围。本 MVP 文档不构成法律意见。

---

## 相关链接

- 产品需求：[docs/PRD.md](./docs/PRD.md)
- 架构设计：[docs/architecture.md](./docs/architecture.md)
