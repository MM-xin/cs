# CS 饰品管理工具 - 功能清单

栈：FastAPI + SQLite + Vue 3 + Element Plus + ECharts + APScheduler + SteamDT API。

---

## 第 0 步：基础框架（已完成）

- [x] FastAPI 后端 + Session 登录（默认 `user/123456`）
- [x] Vue 3 + Vite + Element Plus 前端（`frontend-vue`）
- [x] 前后端 CORS、axios 全局拦截、dev proxy
- [x] 用户会话过期自动跳登录
- [x] 一键启动脚本（`start_backend.bat`）
- [x] Docker 部署（`docker-compose.yml` + Nginx）

---

## 第 1 步：库存管理（已完成）

- [x] `items` 表 + 自动建表、迁移
- [x] 冷却规则：`buy_time -> 下一个 16:00 -> +7 天 = tradable_at`
- [x] 手续费固定 1%，首次写卖出价时自动填充 `sold_time`
- [x] 列表、搜索、状态/类型/时间（含月份）多维筛选，300ms 防抖
- [x] 行内编辑买入价/卖出价（带撤销）、磨损下拉
- [x] 新增 / 编辑 / 删除 / 复制
- [x] 级联删除（删饰品同时删 trades / audit_logs 关联记录）
- [x] 状态可视化：在库 / 冷却中 / 已售 / 撤回
- [x] 左侧菜单区分 “在库饰品 / 已售饰品”
- [x] 同名饰品合并显示（平均价、加权利润率、合并涨跌）
- [x] 批量新增（N 件同名一起入库）
- [x] 批量出售（多选统一卖出价/时间）
- [x] 空图片时按名称自动取占位

---

## 第 2 步：交易流水（已完成）

- [x] `trades` 表 + 索引
- [x] 创建 / 修改价格 / 撤回 / 手续费调整自动写流水
- [x] 历史数据首次访问自动生成基线流水
- [x] 点击 “出售时间” 弹出独立流水对话框（汇总买入/卖出/手续费/净额）

---

## 第 3 步：可观测性 & 可运维（已完成）

- [x] loguru 结构化日志（按天滚动，`logs/app_*.log` + `logs/error_*.log`）
- [x] 全局异常处理器（HTTPException / 参数校验 / 未捕获）
- [x] `audit_logs` 审计表 + `record_audit` 服务，覆盖全部写操作
- [x] APScheduler 定时任务：
  - 每日 04:00 数据库备份（保留 7 份）
  - 每日凌晨从 SteamDT `/base` 同步饰品目录
  - 每 15 分钟自动刷新在库饰品价格
- [x] `/api/audit-logs` 只读接口
- [x] pytest 单元测试（覆盖冷却、手续费、利润、行内编辑、仪表盘、CSV）

---

## 第 4 步：统计与仪表盘（已完成）

- [x] `/dashboard` 独立页面
- [x] 关键指标卡片：在库数量、在库成本、在库市值、浮动盈亏、已售利润、近 30 天
- [x] 近 12 个月利润 / 营收 / 出货数 柱线混合图（ECharts）
- [x] 利润 Top 5 / 亏损 Top 5
- [x] 一键 “重算利润”（基于现有价格重算全部手续费/利润）
- [x] CSV 导出（UTF-8 BOM，Excel 中文不乱码）

---

## 第 5 步：SteamDT 价格 & 目录同步（已完成）

- [x] `steamdt.yaml` 保存 API Key、默认价源、首选平台顺序
- [x] `item_catalog` 本地目录表（中英对照、磨损、平台），每日自动同步
- [x] 目录浏览器（左菜单），支持中英文搜索 + 分页（10/20/50/100/200）
- [x] 新增/编辑时名称自动补全（从本地目录查询，回填 `market_hash_name` / `wear`）
- [x] `current_price` / `previous_price` / `price_source` / `price_updated_at` 字段
- [x] 单个 / 批量刷新价格（默认悠悠有品 youpin）
- [x] 当前价单元格双行展示：上方红绿涨跌 +/-，下方小字当前价
- [x] 前端每 15 分钟轮询拉新，手动刷新按钮可立即触发

---

## 第 6 步：图片本地化（已完成）

- [x] ByMykel CSGO-API 的 `skins.json` 本地缓存（每日更新）
- [x] 新增饰品若无图片：先复用库内同名已下载的 icon，否则从 Steam CDN 拉取存入 `app/static/icons/`
- [x] `/static/` 由 Nginx 反代到后端（生产同源，开发 Vite 代理）

---

## 第 7 步：部署（已完成）

- [x] `Dockerfile`（后端，Python 3.12-slim）
- [x] `frontend-vue/Dockerfile`（多阶段：Node 构建 → Nginx 托管）
- [x] `frontend-vue/nginx.conf`（SPA 回退 + `/api` `/static` 反代）
- [x] `docker-compose.yml`（两服务 + 数据卷挂宿主机）
- [x] `DEPLOY.md`（部署文档）
- [x] `/api/health` 用于容器 healthcheck

---

## 后续可选增强（未开始）

- [ ] 已选饰品批量删除 / 批量撤回
- [ ] 每件不同卖价的批量出售（可编辑表格形态）
- [ ] CSV 导入（带模板和错误行报告）
- [ ] 一键还原备份到指定时间点
- [ ] 审计日志可视化页面
- [ ] 移动端自适应
- [ ] 多用户 / 多仓库（当前仅 `user` 单账号）
