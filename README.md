# AI Listing Optimization System

跨境电商 **AI 商品链接优化系统**（内部代号：`0_0_run_fast`）。

核心闭环：

```
一个内部 SKU → 多套 AI 营销素材 → 同步电商平台 → 广告/分时测试
→ 回收表现 → AI 分析优选 → 更新商品 → 持续迭代
```

## 与选品系统的边界（已确认）

| 系统 | 路径 | 职责 |
|------|------|------|
| **选品 / 产品开发** | `E:\ToBetterLiveBra`（线上 `braproduct`） | 商品真实身份、调研真相源（简报/痛点/探索/PK/待上架成品） |
| **本系统** | `E:\0_0_run_fast` | 素材版本、平台发布、实验、效果闭环、多平台 Adapter |

- **读**：选品 MCP（调研喂料）+ 待建 Listing 只读 API（待上架/内容生产/图/FAQ）
- **写平台**：本系统第一期做美客多商品图片/文案更新（选品系统不做官方写回）
- **不搬**：供应商/报关/利润全链路/品类主数据；`DevProject` 只引用 ID，不整表复制

详见 [docs/00-BOUNDARY.md](docs/00-BOUNDARY.md)。

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/PRD-MVP.md](docs/PRD-MVP.md) | 第一期 MVP：页面、表、接口、状态机 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 模块划分与数据流 |
| [docs/API-CONTRACTS.md](docs/API-CONTRACTS.md) | 跨系统契约（选品 MCP + Listing 只读） |
| [docs/TASKS-XUANPIN-LISTING-READ-API.md](docs/TASKS-XUANPIN-LISTING-READ-API.md) | **选品侧** Listing 只读 API 任务拆分 |

## 仓库骨架

```
0_0_run_fast/
├── README.md
├── docs/                      # PRD / 架构 / 契约 / 任务
├── backend/                   # Django + DRF（MVP 后端）
│   ├── manage.py
│   ├── config/                # settings / urls / asgi
│   ├── apps/
│   │   ├── catalog/           # 商品主档 + 平台链接映射
│   │   ├── creative/          # 素材资产与版本
│   │   ├── publish/           # 发布任务与历史回滚
│   │   ├── platforms/         # 平台 Adapter（MLB 优先）
│   │   └── workbench/         # 优化工作台 API
│   └── requirements.txt
├── frontend/                  # 后续：工作台前端（暂占位）
└── scripts/                   # 本地开发辅助
```

## 第一期（MVP）范围

1. 从选品拉取可优化商品上下文（MCP + Listing 只读）
2. AI 生成多套图片/文案候选 → 素材版本库
3. 人工审核后，经美客多 API 更新已有 Listing 图片（整表图片数组，防误删）
4. 发布快照 + 一键回滚
5. 测试数据：手动录入或半自动导入（不强制广告写 API）

不做：Shopee/TikTok 完整对接、严格随机 A/B、AI 无人值守改高销量链接。

## 本地启动（骨架阶段）

```bash
cd E:\0_0_run_fast\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env   # 填写密钥
python manage.py migrate
python manage.py runserver 0.0.0.0:8100
```

默认端口 **8100**，避免与选品本地 `8000` 冲突。

选品连接（推荐）：登录 Admin → **选品连接配置**，填写 HTTP/MCP Base 与 `mcp_…` Key，勾选启用后可用「测试选品连接」。Admin 优先于 `.env`。

选品 Listing 只读未上线时，可在 Admin 勾选「使用本地假数据」，或 `.env` 设 `XUANPIN_USE_FIXTURES=1`：

```bash
python manage.py createsuperuser
# POST /api/products/import-from-xuanpin/  body: {"listing_id": 90001}  # fixtures
# 或真实联调 body: {"listing_id": 2}
```

## 开发约定

- 语言：中文产品文案；代码/提交信息可用中英，优先说清「为什么」
- 平台写回必须经 `publication_history` 留痕
- 生成素材必须绑定实拍约束图，发布前人工审核
