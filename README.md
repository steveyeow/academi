# ChatBook MVP

最小可运行版本：上传书籍/文档或创建主题 Agent，并通过对话方式检索学习。

## 功能
- 上传 `.txt` / `.pdf` 生成可对话 Agent
- 主题 Agent（默认抓取维基百科摘要）
- 基于向量检索 + LLM 回答

## 运行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`

## 配置
编辑 `.env` 设置 API Key：
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `KIMI_API_KEY`

默认会优先使用 `gemini`，其次 `openai`，最后 `kimi`。

## 提示
- 主题 Agent 目前只抓取维基百科摘要文本。
- 如果要更高质量检索，可以在后续接入更多来源（论文库、教材库、爬虫）。

