# Current Students 白名单爬虫设计

**日期:** 2026-08-31  
**分支:** `feat/scrape-current-students`  
**状态:** 已批准

## 目标

独立脚本抓取 [UNM Current Students](https://www.nottingham.edu.my/CurrentStudents/) 门户及其同域 `/CurrentStudents/` 前缀下的公开 HTML 子页，输出可直接作为后续 RAG ingest / 文件上传输入的结构化材料。

## 非目标

- 不接入 FastAPI、pgvector 或聊天链路
- 不下载 PDF / Word 等附件（仅记录链接）
- 不跟随站外链接，不扩大到整站 `nottingham.edu.my`
- 不绕过登录墙或访问需认证内容

## 范围

| 项 | 值 |
|----|-----|
| 种子 URL | `https://www.nottingham.edu.my/CurrentStudents/` |
| 允许主机 | `www.nottingham.edu.my` |
| 允许路径前缀 | `/CurrentStudents/` |
| 内容 | HTML 正文（去导航噪声后） |
| 附件 | 记入 `attachments.jsonl`，不下载 |
| 默认页数上限 | 200（CLI 可覆盖） |

## 输出布局

```
data/scraped/current_students/
  pages/<slug>.md
  documents.jsonl
  index.json
  attachments.jsonl
  run_meta.json
```

`data/scraped/` 由 `.gitignore` 忽略，避免整站抓取结果进入版本库。

## 记录字段

每页文档：

- `id`：稳定短哈希（基于规范化 URL）
- `url`：规范化 URL
- `title`
- `section`：从面包屑或路径推导
- `text`：纯文本正文
- `outbound_links`：同前缀 HTML 链接
- `attachment_links`：本页发现的附件 URL
- `fetched_at`：ISO8601 UTC
- `content_hash`：正文 SHA-256 前缀

Markdown：YAML front matter（`url` / `title` / `fetched_at` / `id`）+ 正文。

## 抓取行为

- BFS 队列
- URL 规范化：去 fragment；查询串保留；尾斜杠统一（目录页保留 `/`）
- 请求间隔默认 0.75s；User-Agent 标明 UNMC_RAG 研究爬虫
- 非 HTML / 4xx–5xx 记入 `run_meta.errors`，不中断
- 附件扩展名：`.pdf` `.doc` `.docx` `.xls` `.xlsx` `.ppt` `.pptx` `.zip`

## 依赖

可选依赖组 `scrape`：`httpx`、`beautifulsoup4`、`lxml`。不进入主应用运行时依赖。

## 合规

仅用于校内课程助手试点材料准备；遵守站点服务条款与合理请求频率；版权归原站点所有。
