# CloudTech demo pack

最短路径：

```bash
git clone <repo>
cd enterprise-ai-agent-platform
cp .env.example .env
docker compose up -d
./scripts/demo_start.sh          # Linux / macOS — 等待健康检查并灌入 Demo
.\scripts\demo_start.ps1         # Windows
```

打开 http://localhost ，账号 `admin` / `admin123`。


Tenant: **CloudTech**
User: **admin** / `admin123`
Agent: **Enterprise Assistant**
Workflow: **Incident Analysis**

Documents:

- Kubernetes 运维规范
- DevOps 开发流程
- API 文档
- 事件 SOP
- 安全策略

```bash
python scripts/demo_seed.py
# or
./scripts/demo_start.sh
```
