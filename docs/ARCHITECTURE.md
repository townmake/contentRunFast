# 架构说明（MVP）

## 1. 逻辑架构

```
┌─────────────────────────────────────────────────────────────┐
│ 商品优化工作台 (Workbench UI)                                │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST
┌───────────────────────────▼─────────────────────────────────┐
│ backend (Django + DRF)                                      │
│  workbench · catalog · creative · publish · platforms       │
└───────┬─────────────────────────────┬───────────────────────┘
        │                             │
        │ MCP / HTTP                  │ PlatformAdapter
        ▼                             ▼
┌───────────────────┐       ┌───────────────────────────────┐
│ 选品系统           │       │ 美客多 Global Selling API     │
│ MCP + Listing只读  │       │ (Shopee/TikTok 二期 Adapter)  │
└───────────────────┘       └───────────────────────────────┘
```

## 2. 应用包职责

| App | 职责 |
|-----|------|
| `catalog` | `product_master`、`platform_listing`、选品导入与上下文缓存 |
| `creative` | `creative_asset`、`creative_version`、`ai_generation_task` |
| `publish` | `publication_history`、发布编排、回滚 |
| `platforms` | `platform_account`、`PlatformAdapter` 接口与 MLB 实现 |
| `workbench` | 聚合 API，供前端一页完成操作 |
| `config` | Django 工程配置 |

## 3. PlatformAdapter（统一能力）

```text
PlatformAdapter
  get_product(item_ref) -> ProductDTO
  upload_asset(file) -> remote_id
  update_listing_images(item_ref, image_ids_ordered) -> result
  get_publication_status(item_ref) -> status
  get_ad_metrics(...) -> optional   # MVP 可 NotImplemented
  get_sales_metrics(...) -> optional
  create_campaign / update_ad_budget / get_creative_metrics  # 二期+
  capabilities() -> {read_product, write_images, read_ads, ...}
```

每个适配器返回能力枚举：`supported` | `needs_permission` | `unavailable`。

## 4. 发布编排（防误删）

```text
1. lock platform_listing
2. get_product → snapshot_before (完整 pictures[])
3. upload 新图 → 得到 picture_ids
4. 组装完整 pictures 数组（替换主图位 / 按版本策略）
5. update_listing_images
6. get_product 校验 → snapshot_after
7. write publication_history(succeeded)
失败：标记 failed，保留 snapshot_before，不覆盖 current_version
```

## 5. 选品上下文缓存

导入后可在本地存 `xuanpin_context_json`（简报摘要、卖点、实拍 URL），并记录 `xuanpin_fetched_at`。  
「刷新」按钮重新拉取 MCP + Listing 只读，不自动覆盖已审核素材版本。

## 6. 技术选型（骨架）

| 层 | 选型 |
|----|------|
| 后端 | Django 4.2 + DRF |
| 任务 | 先同步/线程；量大后上 Celery（与选品一致） |
| DB | PostgreSQL（生产）；本地可先 SQLite |
| 前端 | MVP 可用 Django 模板或后续独立 React；`frontend/` 占位 |
| 鉴权 | 本系统用户体系独立；调选品用 MCP API Key |

## 7. 配置

见仓库根目录 `.env.example`：

- `XUANPIN_MCP_BASE_URL` / `XUANPIN_MCP_API_KEY`
- `MELI_APP_ID` / `MELI_ACCESS_TOKEN` / `MELI_SITE_ID=MLB`
- `AI_IMAGE_PROVIDER` / keys
