# MVP PRD：AI 商品优化（第一期）

**目标**：运营在本系统完成一次「选品上下文 → 生成候选 → 审核 → 美客多更新主图 → 留痕/回滚 → 手工记结果」闭环。

**非目标**：多平台全自动广告、严格随机 A/B、AI 无人值守改高销量链接、Shopee/TikTok 完整对接。

---

## 1. 角色与场景

| 角色 | 诉求 |
|------|------|
| 运营 | 同一工作台选商品、出图、审图、发美客多、看历史 |
| 管理员 | 配置平台授权、API Key、模型额度 |

**主场景（Happy Path）**

1. 从选品同步/搜索一件待优化商品（有 `product_listing_id` 或平台 Item ID）
2. 拉取简报 listing/作图包、实拍图、竞品对标（只读）
3. 选择创意方向与生成数量 → 创建 AI 任务 → 得到候选图
4. 审核通过 A/B 两个版本，写入素材版本库
5. 发布 A 到美客多已有链接 → 校验生效 → 记 `publication_history`
6. （人工）跑一段时间广告/自然流量后，在工作台录入 CTR/花费/订单摘要
7. 判定后发布 B 或回滚到发布前快照

---

## 2. 页面清单（MVP）

### 2.1 商品优化工作台（核心页）

路径建议：`/workbench` 或 `/workbench/:productId`

| 区块 | 功能 |
|------|------|
| 商品头 | 内部名、SKU、`product_listing_id`、平台 Item、链接状态 |
| Tab：生成 | 素材类型（图/文案）、创意方向、生成版本数、实拍约束图、触发生成 |
| Tab：素材库 | 候选版本列表、预览、审核通过/驳回、设为「待发布」 |
| Tab：发布 | 选择平台链接、发布前检查、确认整表图片数组、执行发布、查看结果 |
| Tab：历史 | `publication_history` 时间线、一键回滚 |
| Tab：分析（轻量） | 手工录入指标、简单对比表（不接广告写 API） |

按钮级操作：

- 「从选品刷新上下文」
- 「生成候选」
- 「通过审核 / 驳回」
- 「发布到美客多」
- 「回滚到此快照」
- 「录入测试结果」

### 2.2 商品列表

路径：`/products`

- 筛选：有/无平台映射、最近发布、待审核素材数
- 入口：进入工作台

### 2.3 平台账号（最小）

路径：`/settings/platforms`

- 美客多巴西：App / Token / 店铺 / 能力探测结果（商品读、图片写、广告读：支持/需权限/不可用）

### 2.4 AI / 任务（最小）

路径：`/settings/ai`（可二期再做独立页，MVP 可先环境变量）

- 图像模型供应商、额度提示（日志级即可）

---

## 3. 数据表清单（MVP 10 张内）

> 命名可用 Django 默认 `app_model`；下列为逻辑表名。

| 表 | 作用 | 关键字段 |
|----|------|----------|
| `product_master` | 内部商品主档（可薄，大量字段引用选品） | `id`, `name`, `internal_sku`, `xuanpin_listing_id`, `xuanpin_dev_project_id`, `cover_image_url`, `status` |
| `platform_listing` | SKU↔平台商品映射 | `product_id`, `platform`=`mercadolibre`, `ml_site`, `item_id`, `user_product_id?`, `shop_account_id`, `permalink`, `sync_status` |
| `creative_asset` | 单素材文件/文案 | `id`, `product_id`, `asset_type`=`image\|copy\|video`, `uri`, `sha256`, `source`=`ai\|upload\|xuanpin` |
| `creative_version` | 素材组合版本 | `id`, `product_id`, `version_code`, `role`=`candidate\|current\|winner\|archived`, `assets[]`/`payload`, `prompt`, `model`, `review_status` |
| `ai_generation_task` | 生成任务 | `id`, `product_id`, `params_json`, `status`, `cost_cents`, `error`, `result_version_ids` |
| `publication_history` | 发布与回滚快照 | `id`, `platform_listing_id`, `version_id`, `snapshot_before_json`, `snapshot_after_json`, `status`, `error`, `published_at`, `operator_id` |
| `platform_account` | 平台授权 | `platform`, `ml_site`, `label`, `token_ref`, `scopes_json`, `capability_json` |
| `manual_performance_log` | MVP 手工效果 | `platform_listing_id`, `version_id`, `date_from`, `date_to`, `impressions`, `clicks`, `ad_spend`, `orders`, `notes` |
| `optimization_decision` | （可延期）建议留表结构 | `product_id`, `recommendation`, `confirmed_by`, `result` |

**MVP 可暂缓**：`experiment` / `experiment_variant` / `ad_performance_daily`（二期；MVP 用 `manual_performance_log`）。

### 3.1 与选品字段对应（只读镜像，不双写）

| 本系统 | 选品来源 |
|--------|----------|
| `xuanpin_listing_id` | `ProductListing.id` |
| `xuanpin_dev_project_id` | `DevProject.id` |
| 初始文案/图 | Listing + ContentProduction + gallery |
| 简报候选 | `StakeholderBriefTask.listing_pack` / `image_brief_pack` |

---

## 4. 接口清单（MVP）

### 4.1 本系统对外（Workbench API）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/products` | 商品列表 |
| POST | `/api/products/import-from-xuanpin` | 用 `listing_id` 或 `dev_project_id` 导入 |
| GET | `/api/products/{id}` | 详情 + 平台映射 + 当前版本 |
| POST | `/api/products/{id}/refresh-xuanpin` | 刷新选品上下文缓存 |
| POST | `/api/products/{id}/generate` | 创建 AI 生成任务 |
| GET | `/api/ai-tasks/{id}` | 任务状态 |
| GET | `/api/products/{id}/versions` | 素材版本列表 |
| POST | `/api/versions/{id}/review` | `{action: approve\|reject}` |
| POST | `/api/publications` | `{platform_listing_id, version_id}` 发布 |
| POST | `/api/publications/{id}/rollback` | 回滚到 snapshot_before |
| GET | `/api/publications` | 历史 |
| POST | `/api/performance-logs` | 手工录入效果 |
| GET | `/api/platform-accounts` | 账号与能力 |

### 4.2 依赖选品（外部）

见 [API-CONTRACTS.md](API-CONTRACTS.md)：

- **已有 MCP**：简报、Listing 总结、痛点、探索、平台商品详情等
- **待建 Listing 只读**：`list/get_product_listings`、`get_content_production`、`list_listing_images`、`list_listing_faqs`

### 4.3 美客多（平台 Adapter）

| 能力 | 用途 | MVP |
|------|------|-----|
| 读 Item / User Product | 取完整图片数组与当前 Listing | 必须 |
| 上传图片 | `pictures` upload | 必须 |
| 更新商品图片数组 | PUT item / user-products | 必须 |
| 广告 metrics | 效果数据 | 可选（可手工） |

能力探测接口：`GET /api/platform-accounts/{id}/capabilities`

---

## 5. 状态机（MVP）

### 5.1 `creative_version.review_status`

`draft` → `pending_review` → `approved` | `rejected` →（approved 可）`published` → `archived`

### 5.2 `publication_history.status`

`queued` → `uploading` → `updating` → `verifying` → `succeeded` | `failed`  
回滚：`rollback_queued` → … → `rolled_back`

### 5.3 `ai_generation_task.status`

`queued` → `running` → `succeeded` | `failed`

---

## 6. 发布前检查（硬规则）

1. 版本 `review_status=approved`
2. 平台账号能力含「图片写」
3. 已成功 `getProduct` 并保存 `snapshot_before.pictures`
4. 新图片数组长度 ≥ 1，且主图位明确
5. 不修改价格/库存/物流字段（MVP 只动图片；文案更新单独立项）
6. 人工二次确认弹窗展示 before/after 缩略图

---

## 7. 验收标准（MVP Done）

- [ ] 能用选品 `product_listing_id` 导入工作台并看到标题/图/简报摘要
- [ ] 能生成 ≥2 个图片候选并审核通过其中 1 个
- [ ] 能对沙箱或真实测试 Item 更新主图，并在历史中看到 before/after
- [ ] 能回滚到发布前图片数组
- [ ] 能手工录入一阶段测试指标并在页面对比
- [ ] 选品侧 Listing 只读 4 接口可用（见任务拆分文档）

---

## 8. 里程碑建议

| 周 | 交付 |
|----|------|
| W1 | 选品 Listing 只读 API + 本系统 catalog 导入 |
| W2 | 素材版本 + AI 生成任务（可先接一个图像供应商） |
| W3 | 美客多 Adapter 读/传/更图片 + 发布历史 |
| W4 | 工作台页面打通 + 回滚 + 手工效果录入 + 验收 |
