# CloudTech demo pack

三分钟跑通（不要把 `.env` 提交到 Git）。

## Quick start

```bash
git clone https://github.com/zhifengjin050-arch/enterprise-ai-agent-platform.git
cd enterprise-ai-agent-platform
cp .env.example .env
python scripts/demo_check.py
```

Windows:

```powershell
.\scripts\demo_start.ps1
```

Linux / macOS:

```bash
./scripts/demo_start.sh
```

打开 http://localhost ，账号 `admin` / `admin123`。

| 项 | 值 |
|----|----|
| Tenant | CloudTech |
| User | admin / `admin123` |
| Agent | Enterprise Assistant |
| Workflow | Incident Analysis |
| 试一句 | `生产环境 Pod 频繁 OOM，应该怎么排查？` |

## 会灌入的文档

- Kubernetes 运维规范
- DevOps 开发流程
- API 文档
- 事件 SOP
- 安全策略

重置：

```bash
./scripts/demo_reset.sh
# Windows: .\scripts\demo_reset.ps1
```

## 截图

README 图由 `python scripts/render_readme_images.py` 从 `docs/screenshots/html/` 导出，不含密钥与真实 IP。
