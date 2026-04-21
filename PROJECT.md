# 项目交接文档 (PROJECT.md)

> 给"下一个会话里的 AI"看的项目全景手册。用户在新对话里扔这份文档给我，我就能立刻理解这个项目。
>
> 阅读顺序：1. 项目定位 → 2. 架构全景 → 3. 目录结构 → 4. 数据模型 → 5. 业务规则 → 6. API → 7. 前端 → 8. 外部集成 → 9. 定时任务 → 10. 配置 → 11. 开发/部署 → 12. 约定与坑

---

## 1. 项目定位

个人用的 **CS2 饰品库存与交易管理系统**。单用户（`user / 123456`），本地部署或 Docker 部署，不做 SaaS。

核心诉求：

- 记录每件饰品的买入、冷却期、卖出、利润。
- 自动接入 SteamDT 拉当前价，浮动盈亏一目了然。
- 统计仪表盘：月度利润趋势、Top 盈亏。
- 全部数据本地 SQLite，每日自动备份。

---

## 2. 架构全景

```
                              浏览器
                                │
            ┌───────────────────┴───────────────────┐
            │                                         │
   http://localhost:9000 (dev)              http://localhost:8080 (prod/Docker)
   Vite dev server                           Nginx 容器
      │                                       │
      │ /api proxy                            │ /api & /static reverse-proxy
      ▼                                       ▼
   http://127.0.0.1:8000                 backend:8000 (内部网络)
   FastAPI + uvicorn                     FastAPI + uvicorn
      │                                       │
      ├── SQLite: data/items.db (WAL)
      ├── Icons: app/static/icons/
      ├── Backups: backups/
      ├── Logs:   logs/
      └── 外部：SteamDT API + ByMykel CSGO-API
```

- **后端**：FastAPI + 会话登录（SessionMiddleware），所有业务接口挂 `/api/*`。
- **前端**：Vue 3 + Vite + Element Plus + ECharts。
- **存储**：SQLite（单文件，`data/items.db`），WAL 模式。
- **后台**：APScheduler（备份、目录同步、刷价）。
- **部署**：`docker-compose` 两个服务（`backend` + `frontend`），数据卷挂宿主机。

> 历史遗留：项目最早用 Jinja2 模板直出（访问 `http://IP:8000/items`）。**已在 2026-04 清理干净**，后端只保留 REST API，唯一的前端是 Vue SPA。

---

## 3. 目录结构

```
cs/
├─ app/                              # 后端（Python）
│  ├─ main.py                        # FastAPI 入口，中间件、异常处理、生命周期
│  ├─ core/
│  │   ├─ config.py                  # 路径常量、费率、配置读取 (users.yaml / steamdt.yaml)
│  │   ├─ constants.py               # CATEGORY_OPTIONS（下拉）
│  │   ├─ database.py                # SQLite schema + migrations + get_connection
│  │   ├─ item_logic.py              # 纯函数：冷却/手续费/利润/时间
│  │   └─ logger.py                  # loguru 初始化
│  ├─ routers/
│  │   └─ api.py                     # 全部 REST 端点，唯一的 router
│  ├─ services/
│  │   ├─ auth_service.py            # verify_user（对照 users.yaml）
│  │   ├─ backup_service.py          # 备份 & 目录预创建
│  │   ├─ item_service.py            # 饰品 CRUD + 流水 + 仪表盘 + CSV + 重算 + 批量
│  │   ├─ audit_service.py           # record_audit / list_audit_logs
│  │   ├─ scheduler.py               # APScheduler 三项定时任务
│  │   ├─ steamdt_service.py         # SteamDT HTTP client
│  │   ├─ catalog_service.py         # item_catalog 本地目录 CRUD + 同步 + 分页搜索
│  │   ├─ price_service.py           # 刷价：单件 / 批量 / 配置
│  │   └─ image_service.py           # ByMykel 索引 + 本地图标缓存
│  └─ static/
│      └─ icons/                     # 饰品图标本地缓存（运行时产生）
├─ frontend-vue/                     # 前端（Vue 3）
│  ├─ src/
│  │   ├─ main.js                    # createApp + ElementPlus + router
│  │   ├─ App.vue                    # 仅 <router-view />
│  │   ├─ style.css                  # 全局样式（含 scrollbar-gutter / stats-grid / profit-pct 等）
│  │   ├─ router/index.js            # /login /dashboard /items，beforeEach 校验 getMe
│  │   ├─ views/
│  │   │   ├─ LoginView.vue          # 登录页
│  │   │   ├─ DashboardView.vue      # 仪表盘 + ECharts 月度趋势 + Top 排行
│  │   │   └─ ItemsView.vue          # 饰品主页：左侧菜单 / 筛选 / 表格 / 行内编辑 / 所有弹窗入口
│  │   ├─ components/
│  │   │   ├─ StatsCards.vue         # 顶部六张指标卡（随 activeItems 动态计算）
│  │   │   ├─ ItemFilters.vue        # 筛选区（两行布局 + 防抖）
│  │   │   ├─ ItemFormDialog.vue     # 新增/编辑弹窗（带名称 el-autocomplete）
│  │   │   ├─ TradeHistoryDialog.vue # 交易流水弹窗（点出售时间触发）
│  │   │   ├─ CatalogBrowser.vue     # 饰品目录浏览（中英搜索 + 分页）
│  │   │   ├─ BulkCreateDialog.vue   # 批量新增 N 件同名
│  │   │   └─ BulkSellDialog.vue     # 批量出售（多选统一卖价/时间）
│  │   └─ services/
│  │       ├─ http.js                # axios 实例 + 拦截器（401 跳 /login, 422/5xx toast）
│  │       ├─ auth.js                # /api/login /api/logout /api/me
│  │       ├─ items.js               # 全部饰品/价格/仪表盘/批量/导出接口 SDK
│  │       └─ catalog.js             # 目录搜索/统计/同步
│  ├─ public/favicon.svg
│  ├─ index.html
│  ├─ vite.config.js                 # 端口 9000，/api /static 代理到 127.0.0.1:8000
│  ├─ Dockerfile                     # 多阶段：Node 构建 → Nginx
│  ├─ nginx.conf                     # SPA 回退 + /api /static 反代
│  └─ package.json
├─ config/
│  ├─ users.yaml                     # 登录账号
│  ├─ steamdt.yaml                   # API Key / 首选平台 / 刷价间隔
│  └─ steamdt.example.yaml
├─ data/items.db                     # SQLite 主库
├─ backups/                          # 每日备份
├─ logs/                             # loguru 输出
├─ tests/                            # pytest（26 例）
├─ Dockerfile                        # 后端镜像
├─ docker-compose.yml
├─ DEPLOY.md                         # Docker 部署文档
├─ FEATURES.md                       # 功能清单 / roadmap
├─ PROJECT.md                        # ← 本文档
├─ README.md
├─ requirements.txt
├─ pytest.ini
└─ start_backend.bat                 # Windows 本地 uvicorn 启动
```

---

## 4. 数据模型

全部定义在 `app/core/database.py`，SQLite。

### 4.1 `items`（饰品主表）

| 字段 | 类型 | 说明 |
| - | - | - |
| id | INTEGER PK | 自增 |
| name | TEXT | 中文名（或自定义名） |
| category | TEXT | 步枪/刀/手套 等 |
| wear | TEXT | 磨损：崭新出厂/略有磨损/... |
| market_hash_name | TEXT | SteamDT/Steam 英文名，**价格查询 key** |
| steamdt_id | TEXT | 保留字段（目前未用） |
| image_url | TEXT | 本地 `/static/icons/xxx.jpg` 或外链 |
| buy_price | REAL | 买入价 |
| sell_price | REAL nullable | 卖出价（未售时 NULL） |
| current_price | REAL | 当前市价（由 price_service 刷入） |
| previous_price | REAL nullable | 上次价格（红绿涨跌用） |
| price_source | TEXT nullable | youpin / buff 等 |
| price_updated_at | TEXT nullable | 最近刷价时间 |
| fee_rate | REAL | 固定 0.01 |
| fee_amount | REAL | sell_price × fee_rate，sold 时自动算 |
| profit / profit_rate | REAL | 见 §5 |
| buy_platform | TEXT | buff / youpin / steam |
| buy_time | TEXT | `YYYY-MM-DD HH:MM:SS` |
| sold_time | TEXT nullable | 首次写 sell_price 时自动填 |
| tradable_at | TEXT | 冷却结束时间，见 §5 |
| is_tradable | INT | 0/1 冗余字段 |
| status | TEXT | `in_stock` / `sold` / `withdrawn` |
| note | TEXT | 备注 |
| created_at / updated_at | TEXT | 系统时间 |

### 4.2 `trades`（交易流水）

item_id + trade_type (`buy` / `sell` / `fee_adjust` / `withdraw` / ...) + amount/fee/net + trade_time + source + note。

- 新建饰品、首次写卖价、撤回等动作都自动落一条。
- 老数据首次访问时自动补 baseline（见 `item_service._ensure_baseline_trades`）。

### 4.3 `audit_logs`（审计日志）

action + username + item_id + detail(JSON) + success + created_at。所有写接口都调用 `audit_service.record_audit(...)`。

动作枚举见 `audit_service.AUDIT_ACTIONS`：`item.create` / `item.create.bulk` / `item.update` / `item.inline_update` / `item.delete` / `item.clone` / `item.sell.bulk` / `item.recalculate` / `backup.manual` / `backup.scheduled` / `catalog.sync.*` / `price.refresh.*`。

### 4.4 `item_catalog`（饰品目录缓存）

`market_hash_name`(PK) + `name_cn` + `base_name_cn` / `base_name_en` + `wear` + `platform_list`(JSON) + `updated_at`。

- 每日凌晨 05:00 从 SteamDT `/base` 同步。
- 供前端 `ItemFormDialog` / `BulkCreateDialog` 名称自动补全，和 `CatalogBrowser` 浏览。

### 4.5 `system_kv`（通用 KV）

`key`/`value`/`updated_at`。目前用于缓存 catalog 同步时间戳等元数据。

---

## 5. 核心业务规则（`app/core/item_logic.py`）

### 5.1 冷却期

```
tradable_at = buy_time → 跳到下一个 16:00 → 再 +7 天
```

规则写在 `calculate_tradable_at()`。SQL 里不存剩余时间，由前端用 `tradable_at` vs 当前时间算。

### 5.2 手续费

固定 1%（`fee_rate=0.01`），只在 `status='sold'` 时按 `sell_price * 0.01` 计算。

### 5.3 利润

```python
if status == 'sold':
    profit = sell_price - buy_price - fee
elif status == 'withdrawn':
    profit = sell_price - buy_price - fee  # 用户可自填 fee_amount
else:  # in_stock / cooling
    profit = current_price - buy_price     # 浮动盈亏
profit_rate = profit / buy_price
```

前端颜色约定：**亏绿 / 盈红**（与 CS 饰品圈习惯一致）。

### 5.4 合并同名

`ItemsView.vue` 的 `mergeSameName` 开关打开后，按 `market_hash_name || name` 分组：

- 价格类字段取简单平均（`averageNumber`）。
- 利润率取**按 buy_price 加权平均**（`weightedProfitRate`）。
- 涨跌 (`price_change`) 只用有 `previous_price` 的子项计算，避免拖平。
- 首项行展示合并数，点击展开查看全部子项。

### 5.5 状态枚举

- `in_stock` 在库未卖
  - 前端派生 `cooling`（`tradable_at > now`） vs 可售
- `sold` 已出售
- `withdrawn` 撤回（自定义损益，有 fee_amount）

左侧菜单 "在库饰品" = `status != 'sold'`，按 `buy_time` 倒序；"已售饰品" = `status == 'sold'`，按 `sold_time` 倒序。

---

## 6. API 清单（全挂 `/api/*`）

所有非 `/health`、`/login`、`/logout` 接口都需要登录态（session cookie）。

### 认证 & 元信息

| 方法 | 路径 | 说明 |
| - | - | - |
| GET | `/api/health` | 无需登录，Docker healthcheck |
| POST | `/api/login` | `{username, password}` |
| POST | `/api/logout` | 清 session |
| GET | `/api/me` | `{username}` |
| GET | `/api/meta` | `category_options` / `status_options` |

### 饰品

| 方法 | 路径 | 说明 |
| - | - | - |
| GET | `/api/items` | 支持 search / status / category / start_date / end_date / sold_start_date / sold_end_date |
| GET | `/api/items/export` | 同筛选参数，返回 CSV (UTF-8 BOM) |
| GET | `/api/items/{id}` | 单件详情 |
| POST | `/api/items` | 新增（空 image_url 自动拉图） |
| POST | `/api/items/bulk` | `{base, quantity}` 批量新增 N 件同名 |
| POST | `/api/items/bulk-sell` | `{item_ids, sell_price, sold_time}` 批量出售 |
| PUT | `/api/items/{id}` | 全量更新 |
| DELETE | `/api/items/{id}` | 级联删 trades 和 audit_logs 关联记录 |
| POST | `/api/items/{id}/clone` | 复制（created_at 刷当前） |
| PATCH | `/api/items/{id}/inline` | `{field, value}` 行内编辑，返回 `previous` 供撤销 |
| GET | `/api/items/{id}/trades` | 该件的流水 |
| POST | `/api/items/recalculate` | 基于现价重算全部手续费/利润 |

### 仪表盘 & 审计

| 方法 | 路径 | 说明 |
| - | - | - |
| GET | `/api/dashboard` | 指标卡 + 月度趋势 + Top 盈亏 |
| GET | `/api/audit-logs?limit=200` | 倒序审计日志 |

### SteamDT

| 方法 | 路径 | 说明 |
| - | - | - |
| GET | `/api/steamdt/ping` | 连通性测试 |
| GET | `/api/steamdt/price?name=...` | 按 market_hash_name 查价，`preferred` 按配置选 |

### 目录

| 方法 | 路径 | 说明 |
| - | - | - |
| GET | `/api/catalog/stats` | 总数 / 最近同步时间 |
| GET | `/api/catalog/search?q=&page=&size=` | 中英搜索 + 分页（传 `limit` 则退化为不分页） |
| GET | `/api/catalog/lookup?name=` | 根据中文名查 market_hash_name |
| POST | `/api/catalog/sync` | 手动拉 SteamDT `/base` 同步 |

### 价格

| 方法 | 路径 | 说明 |
| - | - | - |
| GET | `/api/prices/config` | 默认平台、首选顺序、刷新间隔 |
| POST | `/api/prices/refresh` | `{item_ids?}` 可选指定 id，不给则全量刷在库 |
| POST | `/api/items/{id}/refresh-price` | 单件刷价 |

### 运维

| 方法 | 路径 | 说明 |
| - | - | - |
| POST | `/api/backup` | 手动备份 |

---

## 7. 前端关键视图

### `ItemsView.vue`（主力战场，2.7k 行）

布局：

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部 StatsCards（6 张：在库数、冷却、已售、在库浮盈、已售利润、近30天）
├──────────────┬──────────────────────────────────────────────┤
│ 左侧菜单      │ 筛选区（ItemFilters 两行：日期 / 搜索+状态+类别） │
│ - 在库饰品    │ 工具栏（合并同名 Switch / 批量新增 / 批量出售 / ... │
│ - 已售饰品    │                        导出 / 重算 / 备份）  │
│ - 饰品目录    │ Element Plus Table：                         │
│   (catalog)  │   ┌─ type=selection（仅在库+未合并显示）        │
│              │   ├─ 图片（懒加载，失败占位）                   │
│              │   ├─ 名称（小字带 buy_time）                   │
│              │   ├─ 类别 / 磨损                              │
│              │   ├─ 买入价 / 卖出价 (inline el-input-number) │
│              │   ├─ 当前价（两行：涨跌 + 红绿 + 手动刷新按钮）  │
│              │   ├─ 利润 (利润率%)                          │
│              │   ├─ 冷却剩余时间                             │
│              │   ├─ 状态 tag                                │
│              │   ├─ 出售时间（点击弹 TradeHistoryDialog）    │
│              │   └─ 操作（编辑/克隆/删除）                   │
└──────────────┴──────────────────────────────────────────────┘
```

- 计算管线：`items`（后端拉）→ `activeItems`（按左菜单过滤）→ `displayItems`（按合并开关分组）。
- `StatsCards` 绑 `activeItems`，所以菜单切换时卡片自动变。
- 每 15 分钟轮询 `/api/prices/refresh`（后端同时有 APScheduler 兜底）。

### `DashboardView.vue`

- 六张指标卡；ECharts 月度柱线混合；利润/亏损 Top 5 表格；刷新按钮。

### 其它

- `LoginView.vue` 纯登录。
- `router/index.js` 未命中 `requiresAuth` 时调 `getMe()` 失败就跳 `/login`。

---

## 8. 外部集成

### 8.1 SteamDT (`steamdt_service.py`)

- 配置在 `config/steamdt.yaml`：
  ```yaml
  steamdt:
    api_key: "..."
    base_url: https://open.steamdt.com
    default_platform: youpin
    preferred_platforms: [youpin, buff, ...]
    price_refresh_minutes: 15
    price_batch_size: 100
  ```
- 主要函数：
  - `ping()` — 基础连通性。
  - `fetch_base_info()` — 拉全量中英对照目录（`/base`，每日限次，所以本地缓存）。
  - `query_price(market_hash_name)` — 返回各平台报价列表。
  - `query_price_batch(names)` — 批量。
  - `pick_preferred_price(records)` — 按 `preferred_platforms` 顺序挑第一个。

### 8.2 ByMykel CSGO-API (`image_service.py`)

- 每日下载 `https://bymykel.github.io/CSGO-API/.../skins.json`，缓存在 `data/skins_index.json`。
- `ensure_local_image(name, market_hash_name)` 策略：
  1. 先在 items 表找同名饰品的 `image_url`，有则复用；
  2. 没有则从 skins.json 索引找 URL，下载存 `app/static/icons/<md5>.jpg`；
  3. 返回 `/static/icons/xxx.jpg`。
- 触发点：**只在 `create_item()` 且用户没填 image_url** 时调用。

---

## 9. 定时任务（`app/services/scheduler.py`）

| 任务 | 触发 | 说明 |
| - | - | - |
| `daily_backup` | 每天 04:00 | 复制 `data/items.db` 到 `backups/`，保留 7 份 |
| `daily_catalog_sync` | 每天 05:00 | 拉 SteamDT `/base` 回写 `item_catalog` |
| `price_refresh` | 每 `price_refresh_minutes` 分钟（默认 15） | 刷新所有在库/冷却中饰品当前价 |

所有任务都会写 `audit_logs`，失败不阻塞。关闭应用时 `shutdown_scheduler()` 优雅退出。

---

## 10. 配置文件

### `config/users.yaml`

```yaml
users:
  - username: user
    password: "123456"
```

### `config/steamdt.yaml`

关键字段见 §8.1。首次克隆从 `steamdt.example.yaml` 复制。

---

## 11. 开发 / 部署

### 本地开发

```bash
# 后端
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# 或：start_backend.bat (Windows，需调整 PYTHON_EXE)

# 前端
cd frontend-vue
npm install
npm run dev
# 访问 http://127.0.0.1:9000
```

### Docker 部署

```bash
docker compose up -d --build
# 访问 http://localhost:8080
```

详见 `DEPLOY.md`。国内网络拉不动 Docker Hub 时，三个 Dockerfile 的基础镜像目前都用了 `docker.m.daocloud.io/library/...` 前缀加速。

### 环境变量

- `SESSION_SECRET`（可选）：固化 session 密钥，容器重启登录态不丢。不设置则每次启动随机。

### 测试

```bash
pytest
```

单测集中在 `tests/`，26 例，覆盖冷却计算、手续费、利润、行内编辑、仪表盘、CSV。

---

## 12. 约定与坑

### 风格

- 中文优先（UI 全中文，错误提示、审计 label 都是中文）。
- 注释：不写"这里是什么"（显而易见的不写），写"为什么"。
- 组件职责拆干净，`ItemsView` 作为容器，子组件纯表现 + emit。

### 命名

- 后端 `snake_case`；前端 JS `camelCase`；Vue 组件 `PascalCase`。
- 时间字段统一 `YYYY-MM-DD HH:MM:SS` 字符串存 SQLite（不用 ISO）。

### 已知坑 / 注意点

1. **Windows 下 uvicorn `--reload` 有时不触发**：改代码后如果行为不符预期，手工重启后端。
2. **端口占用**：windows 下 `TIME_WAIT` 可能让 8000 /5173 /9000 拒绝重绑定，等一会或 `taskkill /F /PID`。
3. **SteamDT `/base` 每日有调用次数限制**：一定要走本地 `item_catalog` 缓存，不要在前端实时调 SteamDT。
4. **级联删除**：`delete_item` 会同时删 `trades` 和相关 `audit_logs`，dashboard 的 Top5 实时更新。
5. **合并同名的涨跌算法**：只用有 `previous_price` 的子项平均，避免没拉过价的新件把涨跌拖成 0。见 `ItemsView.vue displayItems`。
6. **Session secret 每次随机**：不配 `SESSION_SECRET` 的话，后端重启你会被踢出登录。
7. **`image_url` 字段存的可能是本地路径 `/static/icons/xxx.jpg`，也可能是外链**：前端渲染统一 `<img>`，404 则显示 CSS 占位。
8. **CSV 导出必须带 `\ufeff` BOM**，否则 Excel 打开中文乱码。
9. **前端所有接口走 `/api` 前缀**，dev 通过 vite proxy，prod 通过 nginx proxy；**永远不要硬编码 `http://127.0.0.1:8000`**。
10. **老 Jinja 代码已全部删除**（`app/templates/`、`app/routers/auth.py`、`app/routers/items.py`、`app/static/style.css`）——如果看到有引用，肯定是陈旧的缓存或文档。

---

## 13. 如何快速响应新需求（给 AI 的提示）

- **新增一个 API** → 在 `app/routers/api.py` 末尾加路由，业务写 `services/*`，写入要 `record_audit`，补单测。
- **新增一个字段** → `database.py` schema + `_apply_migrations` ALTER；`item_service.build_item_payload` 加字段；前端 `ItemFormDialog` 加控件；`ItemsView` 表格加列。
- **改前端页面** → 优先拆成新的子组件而非把 `ItemsView` 继续膨胀。
- **修业务规则** → 改 `app/core/item_logic.py` 纯函数 + 补单测 + 跑 `recalculate_all()` 回刷历史数据。
- **遇到数据异常** → 先看 `logs/error_*.log`，再看 `audit_logs` 表最近几条，基本能定位。
