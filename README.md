# CS 饰品管理工具

个人用的 CS2 饰品库存与交易管理系统。

**技术栈**：FastAPI + SQLite + Vue 3 + Element Plus + ECharts + APScheduler，接入 SteamDT 价格 API。

功能总览请看 [`FEATURES.md`](./FEATURES.md)，项目架构与开发交接请看 [`PROJECT.md`](./PROJECT.md)，Docker 部署请看 [`DEPLOY.md`](./DEPLOY.md)。

---

## 目录结构

```
cs/
├─ app/                  # FastAPI 后端
│  ├─ main.py            # 入口：中间件、异常、调度、静态文件
│  ├─ routers/api.py     # 全部 REST 接口（/api/*）
│  ├─ services/          # 业务服务层
│  ├─ core/              # 配置 / 数据库 / 纯逻辑 / 日志
│  └─ static/icons/      # 饰品图标本地缓存（自动下载）
├─ frontend-vue/         # Vue 3 前端
├─ config/               # users.yaml / steamdt.yaml
├─ data/                 # SQLite 数据库
├─ backups/              # 数据库每日备份
├─ logs/                 # 后端日志
├─ tests/                # pytest 单元测试
├─ Dockerfile            # 后端镜像
├─ docker-compose.yml    # 一键编排
└─ DEPLOY.md             # 部署文档
```

---

## 本地开发

### 1. 后端

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows 可直接运行 `start_backend.bat`（需修改里面的 Python 路径）。

后端监听 `http://127.0.0.1:8000`，所有接口挂在 `/api/*` 下，`/docs` 看自动生成的 Swagger。

### 2. 前端

```bash
cd frontend-vue
npm install
npm run dev
```

访问 `http://127.0.0.1:9000`（端口见 `frontend-vue/vite.config.js`）。

默认账号：`user / 123456`（在 `config/users.yaml`）。

---

## 生产部署（Docker）

```bash
docker compose up -d --build
```

访问 `http://localhost:8080`。细节、数据卷、常用命令见 [`DEPLOY.md`](./DEPLOY.md)。

---

## 配置文件

- `config/users.yaml` — 登录账号
- `config/steamdt.yaml` — SteamDT API Key、默认价源、刷新频率

后端不再有 Jinja 模板页面，唯一入口是 Vue SPA。

---

## 测试

```bash
pytest
```

覆盖冷却计算、手续费、利润、行内编辑、仪表盘、CSV 导出等核心逻辑。
