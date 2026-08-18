# GitHub 仓库创建说明

发布前在 GitHub 创建 **Public** 仓库，再把 URL 发回本对话，即可执行 `git remote add` 与 `git push`。

**本地已完成：** `git init`、分支 `main`、提交与附注标签 `v1.0.0`（见下方「等待你提供」）。  
**尚未执行：** `git remote add` / `git push`（需仓库 URL）。

```bash
git remote add origin <repository_url>
git branch -M main
git push -u origin main
git push origin v1.0.0
```

---

## 创建仓库

| 字段 | 值 |
|------|-----|
| Repository name | `enterprise-ai-agent-platform` |
| Description | Enterprise AI Agent Platform with RAG, Knowledge Graph, Workflow Automation, Multi-Tenant Security and Cloud Native Deployment. |
| Visibility | **Public** |
| Initialize | **不要**勾选 README / LICENSE / .gitignore（本地已有完整历史） |

### Topics

```
ai
agent
llm
rag
knowledge-graph
fastapi
python
kubernetes
docker
mcp
workflow
```

### 网页操作

1. 打开 https://github.com/new
2. Owner 选你的账号或组织
3. 填入上表 Name / Description
4. 选 Public，不要初始化文件
5. Create repository
6. 复制 HTTPS 或 SSH URL，例如 `https://github.com/<owner>/enterprise-ai-agent-platform.git`

### GitHub CLI（可选）

```bash
gh repo create enterprise-ai-agent-platform --public --source=. --remote=origin --description "Enterprise AI Agent Platform with RAG, Knowledge Graph, Workflow Automation, Multi-Tenant Security and Cloud Native Deployment."
```

若使用 `gh repo create --source=. --push`，仍需补推标签：`git push origin v1.0.0`。

创建后建议在仓库 Settings → General 勾选 Issues / Discussions（按需），About 里粘贴 Description 并添加 Topics。
