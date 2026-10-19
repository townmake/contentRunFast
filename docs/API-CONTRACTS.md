# 跨系统 API 契约

本系统调用 **选品系统** 的约定。鉴权复用选品「MCP 客户端 API Key」（`Authorization: Bearer mcp_...`），并绑定有效用户。

---

## 1. 已有：选品 MCP（调研喂料）

Base：线上 `/mcp/` 或选品文档 `mcp_gateway/CLIENT_SETUP.md`。  
站点：巴西 `ml_site=MLB`，墨西哥 `MLM`。

| 工具 | MVP 用途 |
|------|----------|
| `get_platform_product_detail` / `get_product_by_sku` | 竞品/本店平台商品 Listing 原文与图 |
| `get_stakeholder_brief` | `listing_pack`、`image_brief_pack`、报告摘要 |
| `get_dev_project` / `get_dev_project_module_bundle` | 开发项目上下文 |
| `get_product_explore` | 探索六步卖点 |
| `get_review_analysis` / `get_qa_analysis` | 痛点 / FAQ 原料 |
| `get_product_pk` | 差异化卖点 |
| `list_stakeholder_briefs` | 按项目找简报 |

**本系统封装建议**：`catalog.services.xuanpin_mcp_client`，统一超时、重试、错误码。

---

## 2. Listing 只读（选品系统 · 已实现）

> 任务拆分见 [TASKS-XUANPIN-LISTING-READ-API.md](TASKS-XUANPIN-LISTING-READ-API.md)。  
> **选品侧（2026-10-18）**：HTTP + MCP 已落地。  
> - HTTP：`GET {XUANPIN_BASE}/product-development/api/open/listings/` …  
> - MCP：`list_product_listings` / `get_product_listing` / `get_content_production` / `list_listing_images` / `list_listing_faqs`  
> - 鉴权：`Authorization: Bearer <mcp_client_api_key>`（与 MCP 同一 Key）  
>
> **消费侧进度（本仓库）**：`catalog.services.xuanpin_http_client` + `import_from_xuanpin` /
> `refresh_xuanpin_context` 已按本节契约实现；选品未部署前可用 `XUANPIN_USE_FIXTURES=1` 联调。
> 联调入口：`POST /api/products/import-from-xuanpin/`、`POST /api/products/{id}/refresh-xuanpin/`。

### 2.1 `list_product_listings`

列出待上架/线上产品。

**入参**

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string? | `pending` / `online` / `offline` / `cancelled` |
| `dev_project_id` | int? | 过滤 |
| `q` | string? | 标题搜索 |
| `limit` | int | 默认 20，最大 100 |
| `offset` | int | |
| `ml_site` | string? | 业务库站点 |

**出参 item（摘要）**

```json
{
  "listing_id": 123,
  "title": "...",
  "listing_title": "...",
  "status": "pending",
  "dev_project_id": 45,
  "platform_product_id": 678,
  "platform_sku": "MLB...",
  "stakeholder_brief_id": 9,
  "primary_image_url": "https://...",
  "updated_at": "2026-10-16T12:00:00+08:00"
}
```

### 2.2 `get_product_listing`

详情。

**入参**：`listing_id`（必填）

**出参**

```json
{
  "listing_id": 123,
  "title": "...",
  "listing_title": "...",
  "status": "pending",
  "source_type": "dev_project",
  "dev_project_id": 45,
  "platform_product_id": 678,
  "platform_sku": "MLB...",
  "stakeholder_brief_id": 9,
  "ml_listing_summary_id": 3,
  "listing_bullets": ["..."],
  "listing_characteristics": {},
  "listing_description": "...",
  "listing_image_urls": ["..."],
  "gallery_urls": ["..."],
  "remark": "",
  "created_by": "linzz",
  "updated_at": "..."
}
```

权限：调用用户须对该 Listing `can_view`（创建者/协作/超管），与站内一致。

### 2.3 `get_content_production`

**入参**：`listing_id`

**出参**

```json
{
  "listing_id": 123,
  "status": "draft",
  "mlb_payload": {},
  "shopee_payload": {},
  "updated_at": "..."
}
```

无内容生产记录时：`success=true` 且 `content_production=null`，或 404 二选一（建议前者便于导入）。

### 2.4 `list_listing_images`

**入参**：`listing_id`

**出参**

```json
{
  "listing_id": 123,
  "images": [
    {"index": 0, "url": "https://...", "source": "upload|url"}
  ]
}
```

URL 须本系统可下载（公网或带时效签名）；本地 media 需选品侧生成绝对 URL。

### 2.5 `list_listing_faqs`（可选但建议一期带上）

**入参**：`listing_id`

**出参**：`[{id, question_pt, answer_pt, question_zh?, answer_zh?}]`

---

## 3. 本系统 → 选品（第二期，本期不做）

| 能力 | 说明 |
|------|------|
| 优胜文案回写 | 更新 `listing_pack` 或 ProductListing 文案 |
| 优胜图回写 | 追加 Listing 图集 |
| 仅状态通知 | 备注「已在优化系统发布版本 vX」 |

---

## 4. 错误约定

| HTTP / MCP | 含义 |
|------------|------|
| 401 | Key 无效 |
| 403 | 无查看权限 |
| 404 | Listing 不存在或跨站库找不到 |
| 400 | 参数错误 |

响应统一：`{ "success": true/false, "error": "...", ... }`（与选品 MCP 风格一致）。
