# Enterprise AI Agent Platform console

React + Vite + Tailwind 控制台。开发时通过 Vite 把 `/api` 代理到 `http://localhost:8000`。

```bash
cd frontend
npm ci
npm run dev
```

生产镜像用完整 `npm ci`（含 Vite）构建静态资源，再由 Nginx 提供并反代 `/api`。

Demo 登录：`admin` / `admin123`（先跑 `scripts/demo_start.ps1` 或 `demo_start.sh`）。
