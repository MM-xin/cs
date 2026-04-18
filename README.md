# CS 饰品管理工具（Python/FastAPI）

一个可直接运行的基础框架，已包含：

- 项目骨架（FastAPI + 模板页面）
- 配置文件用户登录（默认 `user/123456`）
- 会话登录/退出流程
- SQLite 数据库自动建表
- 饰品库存列表 / 新增 / 编辑 / 删除 / 快速复制
- 冷却结束时间与“当前是否可售”自动计算
- 数据库备份目录（支持手动触发备份）

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 启动项目

```bash
uvicorn app.main:app --reload
```

Windows 下也可直接运行根目录脚本（免输长命令）：

```bash
start_backend.bat
```

## 3. 访问地址

- 浏览器打开：`http://127.0.0.1:8000`
- 登录后默认进入：`/items`
- 默认账号：`user`
- 默认密码：`123456`

## 4. 用户配置位置

用户信息写在 `config/users.yaml`，后续你只需要改这个文件即可。

## 5. 数据文件位置

- SQLite 数据库：`data/items.db`
- 备份目录：`backups/`
