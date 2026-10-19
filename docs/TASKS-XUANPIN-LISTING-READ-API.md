# 选品侧任务拆分：Listing 只读 API

**实施仓库**：`E:\ToBetterLiveBra`（推送远程 `braproduct`）  
**消费方**：`E:\0_0_run_fast`  
**原则**：只读；权限与站内 `ProductListing.can_view` 一致；可挂 MCP + HTTP。

---

## Epic

为 AI Listing 优化系统提供待上架/内容生产/图集/FAQ 的只读查询能力。

**选品侧进度（2026-10-18）**

- [x] Task1 序列化：`ToBetterLiveBra/product_development/listing_read_api.py`
- [x] Task2 HTTP：`listing_read_views.py` + `routes.py` → `/product-development/api/open/listings/...`
- [x] Task4 权限/站点：`can_view` + `resolve_request_site` / MCP 用户
- [x] Task3 MCP：`mcp_gateway/tools_listing.py`（已挂入 `tools.py`）
- [ ] Task5 与本仓库 `import-from-xuanpin` 真机联调（部署选品后关掉 fixtures）

---

## Task 1 — 序列化层（0.5d）

**文件建议**

- 新建 `product_development/listing_read_api.py`（或 `listing_export_service.py`）
- 复用 `listing_gallery_service.listing_gallery_urls`

**交付**

- `serialize_listing_summary(listing) -> dict`
- `serialize_listing_detail(listing) -> dict`
- `serialize_content_production(cp|None) -> dict`
- `serialize_listing_images(listing) -> list`
- `serialize_listing_faqs(listing) -> list`
- 绝对 URL：用 `request.build_absolute_uri` 或 settings `PUBLIC_BASE_URL`

**验收**：单元测试或 manage.py shell 导出一条真实 Listing JSON。

---

## Task 2 — HTTP 只读路由（0.5d）

**文件建议**

- `product_development/listing_read_views.py`
- `product_development/routes.py` 注册

**路由草案**

| Method | Path | 对应契约 |
|--------|------|----------|
| GET | `/product-development/api/open/listings/` | list |
| GET | `/product-development/api/open/listings/<id>/` | get |
| GET | `/product-development/api/open/listings/<id>/content-production/` | content |
| GET | `/product-development/api/open/listings/<id>/images/` | images |
| GET | `/product-development/api/open/listings/<id>/faqs/` | faqs |

**鉴权**：复用 MCP Client API Key（`Authorization: Bearer`）或现有 open API Token 模式（参考 `task_management/ml_listing_batch_open_api.py`）。  
**禁止**：Session Cookie 作为唯一方式（本系统服务端调用不便）。

**验收**：用 curl + Key 拉通 list/get。

---

## Task 3 — MCP 工具注册（0.5d）

**文件建议**

- `mcp_gateway/tools_listing.py`（新建）或并入 `tools_product_dev.py`
- `mcp_gateway/tools.py` / TOOLS 列表注册
- 更新 `mcp_gateway/TOOLS_API.md`、`CLIENT_SETUP.md` 一行说明

**工具名（与契约对齐）**

1. `list_product_listings`
2. `get_product_listing`
3. `get_content_production`
4. `list_listing_images`
5. `list_listing_faqs`

**参数**：含可选 `ml_site`；内部 `resolve_request_site` + `_require_mcp_user`。

**验收**：Cursor / 豆包 tools/list 可见；对真实 `listing_id` 调用成功。

---

## Task 4 — 权限与站点库（0.5d）

- `can_view`：非创建者且无开发项目查看权 → 403
- 超管可见全部（与列表页一致或按协作配置）
- 墨西哥库：`ml_site=MLM` 时走 mexico alias；Listing 在对应站库查询
- 用户镜像：若写操作未来需要再复用 `_ensure_mcp_user_on_current_site_db`；本期只读可只查

**验收**：绑定普通用户 Key 只能看到自己有权的 Listing。

---

## Task 5 — 文档与联调（0.5d）

- 在选品 `mcp_gateway/TOOLS_API.md` 增加「产品上架只读」小节
- 本仓库 `API-CONTRACTS.md` 状态改为「已实现」并注明线上版本/日期
- 与 `0_0_run_fast` 联调：`POST /api/products/import-from-xuanpin` 成功导入

### 消费侧已就绪（本仓库，无需再等骨架）

| 能力 | 位置 |
|------|------|
| Listing HTTP 客户端 | `backend/apps/catalog/services/xuanpin_http_client.py` |
| MCP 简报客户端 | `backend/apps/catalog/services/xuanpin_mcp_client.py` |
| 导入 / 刷新 | `backend/apps/catalog/services/import_service.py` |
| API | `POST /api/products/import-from-xuanpin/`、`POST /api/products/{id}/refresh-xuanpin/`、`GET /api/products/{id}/` |
| 本地假数据 | `XUANPIN_USE_FIXTURES=1`（fixture `listing_id=90001`） |

---

## 明确不做（本期）

- [ ] 创建/更新 ProductListing
- [ ] 回写优胜素材
- [ ] 改美客多官方 Listing
- [ ] 暴露 Todo 分组（非 MVP 必需）

---

## 预估合计

约 **2～2.5 人日**。建议排在本系统 W1，阻塞「导入工作台」。

## 推荐实现顺序

`Task1 → Task2 → Task4 → Task3 → Task5`
