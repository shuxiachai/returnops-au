# F.01：公共接口与数据契约 v1

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> 版本：`1.0.0-rc.5`；2026-09-07。状态：**本地修正候选，未发布，尚待 A/B/C 联合验收**。[PR #9](https://github.com/shuxiachai/returnops-au/pull/9) 是已合并的 rc.2 历史发布，不表示本修订已获同意。
> Owner：A；指定 Reviewer：C；B 必须确认前端消费边界。交付条目：[KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)；链接已核验，不代表 Jira 状态已改变或 F.01 已验收。
> 已发布评审入口：[PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，已核验 head `57d86fe` 收录 rc.4；本地 rc.5 尚未收录，旧 CI 不覆盖本轮修订。rc.3 提交 `90931562f7e8d038b994d8d3ff3b2f289e462643` 保留为历史起点。
> 当前技术评审入口：[Issue #10 — F.01 contract and aligned models](https://github.com/shuxiachai/returnops-au/issues/10)。后续 PR 在该 Issue 留下关联；Issue #5 / KAN-12 保留基线采纳范围。
> 本文落实 [固定分工](07-frozen-work-allocation.md) 与 [F.01](08-delivery-work-packages.md)，不重开业务范围，不代替 tutor 确认。
> 这是“数据如何交接”的约定，不是已经运行的业务服务；没有实现业务鉴权、业务实体持久化、状态守卫、LLM 或 provider。F.02 的数据库连通与环境迁移另见 docs/10。rc.4 在 rc.3 上补历史读取、容量与通知恢复约束，不等于相应运行行为已实现。

## 1. 三人各自看什么

[AD-0.2 设计决定包](14-member-a-design-decisions.md)将恢复边界具体化；[F.03 身份设计](16-demo-identity-authorization.md)给出操作/资源权限矩阵。rc.5 修正幂等回执移除优先级，并与标签制品恢复模型同步；不新增字段、状态、错误码或公共操作。1-based 尝试序号仍待另行采纳，不混入本次修正。

| 使用者 | 重点 | 后续工作 |
|---|---|---|
| A | 案件/提案版本，审批范围，操作与通知记录，公共错误 | F.02 环境/CI；F.01 验收后按 A1.01 对齐领域模型，按依赖开展后续工作 |
| B | 客户请求/读模型、Founder 读模型、四种决定、错误和超时反馈 | 用样例做 B1/B2 mock；不自行生成状态、风险、审批或操作成功结论 |
| C | 检索/引用核验/独立风险输入输出、来源元数据、图片观察 | 按 C1/C2/C3 实现自己的模块；核对标签枚举；核验 A 维护的 Jira 映射与证据 |

交付入口：

- [机器可读 JSON Schema](../contracts/v1/schemas.json)：`$defs` 是命名数据结构注册表；必须选中具体定义验证，不能只验证根对象。
- [OpenAPI](../contracts/v1/openapi.json)：15 个计划公共操作（新增两个角色隔离的历史 GET），引用同一份 Schema；不是额外维护一套字段。
- [JSON 样例](../contracts/v1/examples.json)：`positive`、`negative` 和 `runtime_guards` 三组。
- [基础契约检查](../tests/contracts/test_contract_v1.py)、[rc.2 回归检查](../tests/contracts/test_contract_v1_rc2.py)、[rc.3 回归检查](../tests/contracts/test_contract_v1_rc3.py)、[rc.4 回归检查](../tests/contracts/test_contract_v1_rc4.py)、[rc.5 回归检查](../tests/contracts/test_contract_v1_rc5.py) 与 [运行说明](../contracts/README.md)。

## 2. 不改变的边界

- 一家澳大利亚实体商品网店、一位 Founder；英文合成/去标识化数据、AUD。
- A 的 Coordinator/Assessment、C 的独立 Risk Reviewer 共三个业务 AI 角色；Domain Service 和 Operations Service 是确定性服务。
- AI 只返回各角色的非执行性结构化结果（如 `CoordinatorResult`、`DecisionPacket`、`RiskReview`）。服务端另建只读 `ActionPreview`；它仍不是授权。
- 只有服务端验证的 Founder 能创建可信 `ApprovalRecord`。客户端不能提交可信角色、审批记录、任意命令或 provider 凭据。
- 一个案件关联一个订单的多个商品项；一次退运只有一个 parcel、一个 label。不支持拆包、多单合并、实际退款、收费物流或生产数据修改。
- A3 的 `SANDBOX` 只是已选扩展的类型边界，必须另获明确的无收费测试权限；字段存在不代表 provider 已接入。课程核心使用 `SIMULATED`。
- 契约修订不改旧 `packages/domain/models.py` 或 B/C 的 PR，不实现 F.03/A1/A2。F.02 环境准备单独记录。旧正文与共享图的 rc.2 对齐稿保留 PR #9 历史；本地 rc.5 仍需联合确认，不声称图已获验收。

## 3. 公共格式和缺省规则

| 项目 | 约定 |
|---|---|
| 路径与版本 | URL 主版本 `/v1`；契约文档版本 `1.0.0-rc.5`；与案件/提案计数版本不同 |
| ID | 3–80 位不透明 ASCII 标识符，首位为字母/数字，其余为字母/数字/`_`/`-`；拒绝尾随换行及控制字符，不能推导权限。客户端仅引用服务端返回的 ID |
| 时间 | RFC 3339 UTC，统一以 `Z` 结束；不得用客户端时间判断审批是否过期 |
| 金额 | 整数 AUD cents，例如 `2000` 表示 AUD 20.00；不能用浮点金额做审批指纹。当前执行额度恒为 `0` |
| 未知值 | 可选字段省略；`source_version: null` 明确表示来源没有发布版本，不能编造版本号 |
| 额外字段 | DTO 对象关闭额外字段；客户端角色/命令注入不能因“前端不用”而忽略 |
| 客户意图 | `original_message` 唯一必填；缺订单、期望或附件仍可提交并进入后续澄清。缺省 `requested_outcome` 归为 `UNSPECIFIED`，缺省 `evidence_ids` 归为 `[]` |
| 其他期望 | `OTHER` 保留“其他诉求”分类，原文仍是依据；不自动扩大可执行命令范围 |
| 字符串 | 原始陈述按接收内容独立保存，不被抽取覆盖。仅空白消息由服务端拒绝；展示必须转义，不能当 HTML/指令 |
| 分页 | 统一 `Cursor`：1–1024 位 base64url-safe 不透明 token；须验证服务端状态/签名与身份、案件、查询、快照绑定。无下一页时省略 `next_cursor`；历史分页完整规则见 §10.4 |
| 身份 | Bearer 传递演示身份；F.03 决定并实现可信验证。Schema 本身不产生用户、不发 token、不授予权限 |

严格客户端可能拒绝新字段或新枚举，所以即使是“增加可选字段”也需 A/B/C 协调发布，不能默认完全兼容。改变业务枚举、审批语义或功能归属仍按 docs/07 的变更规则处理。

## 4. 核心数据如何交接

| 对象 | 谁生产 | 关键内容及消费者 |
|---|---|---|
| `CustomerStatement` | A 保存客户输入 | 不可被归一化覆盖的原文、原始/补充类型、时间；B 展示，A/C 引用 |
| `CustomerCaseView` | A 的授权查询 | 客户自己的案件版本、状态、陈述、附件、澄清、结果消息；不含内部提案/风险/审批 |
| `ExtractedFacts` / `EvidenceCriterion` | A 的 Coordinator/Assessment | 独立四字段；逐项 PRESENT/MISSING/CONFLICTING/NOT_APPLICABLE，引用 statement/evidence ID |
| `OrderLookupResult` | A 的只读订单 port | 五种结果；仅 MATCHED 含 snapshot，商品 ID/数量来自该快照 |
| `PolicyPassage` / `Citation` | C1 | 区分政策与已审阅指导；来源/位置/快照版本/hash 可核对，不代表语义判断正确 |
| `DecisionPacket` | A 的 Assessment | 原始 statement 引用、提案/输入版本、事实/矩阵、条件建议、依据、备选、费用责任说明、引用、不确定性、模型版本；无命令 |
| `ProcessingFailure` | A 的 Domain Service 保存受校验的技术失败 | `failure_id/case_id/input_version/stage/error/occurred_at`；无提案故障升级时给 B 显示并引用，不伪造提案或业务风险结论 |
| `OrderLookupBlock` | A 的 Domain Service 保存已接受的订单阻断 | `block_id/case_id/input_version/status/message/occurred_at`；status 仅 CONFLICT/AUTHORITY_DENIED；无提案时供 B 显示并以 block ID 人工处理，不冒充技术错误或 RiskReview |
| `RiskReview` | C2 的独立调用 | 精确绑定 case/input/proposal/corpus；五种 outcome、发现、修改要求或问题；无批准/派发能力 |
| `ActionPreview` | A 的确定性领域逻辑 | 当前可批准提案的精确免费模拟范围、命令、provider、parcel、到期时间、指纹；B 确认显示 |
| `FounderDecisionRecord` / `ApprovalRecord` | A2 根据可信 Founder 请求 | 提案、技术失败、订单阻断三种目标互斥；两个无提案目标只允许 MANUAL_HANDLING；只有提案目标 APPROVE 才有独立精确审批记录 |
| `OperationAttempt` | A2 | provider ID、命令/审批绑定、操作指纹、持久化幂等键、类型化结果/错误；UNKNOWN 不冒充失败或成功 |
| `NotificationRecord` | A2 | 操作结果通知与拒绝/人工处理通知；独立 PENDING/SENT/FAILED、下一步和重试次数 |
| `CaseView` | A 的 Founder 查询 | `cited_passages` 提供当前引用原文/来源；processing_failure/order_lookup_block 至多一个，ESCALATED 且无 current_proposal 时恰好一个；订单阻断不能与当前提案/review/preview 并存，历史操作和审批仍保留 |
| `FounderHistoryPage` / `CustomerHistoryPage` | A 的授权查询 | 有限 kind 对应严格内容类型；旧 proposal 完整输入、独立 review、决定/审批/操作/通知及移除标记；客户仅自己的陈述、证据和已发送安全结果消息 |
| `AuditPage` / `AnalyticsSnapshot` | A 的只读 API | 非个人事件引用/hash、相关 ID；统计回显 AnalyticsQuery 筛选，统一 cohort/as_of，按案件去重并区分成功、失败、未测量 |

`IssueCategory` 与 `AssessmentStatus` **逐字沿用 docs/00 第 5 节**；不另建一套前端/后端分类映射。`PossibleBasis` 只是可能依据，不是最终法律裁定。

## 5. 公共接口清单

所有接口声明 Bearer 鉴权；C 的模块不是第三种可登录业务角色。C 消费内部 port，不能通过 HTTP 自选 `FOUNDER`。

| 方法/路径 | 权限 | 请求 → 成功响应 |
|---|---|---|
| GET `/v1/session` | 已验证 CUSTOMER/FOUNDER | → `Principal` |
| POST `/v1/evidence` | CUSTOMER | multipart file/description → 201 `EvidenceAttachment(STAGED)` |
| GET `/v1/evidence/{id}/content` | 所有者客户/获授权 Founder | → 原文件 bytes；不返回存储凭据 |
| POST `/v1/cases` | CUSTOMER | `CreateCaseRequest` → 201 `CustomerCaseView` |
| GET `/v1/cases/{id}` | 案件所有者客户 | → `CustomerCaseView` |
| GET `/v1/cases/{id}/history` | 案件所有者客户 | CustomerHistoryQuery → `CustomerHistoryPage`（仅 STATEMENT/EVIDENCE/OUTCOME_MESSAGE） |
| POST `/v1/cases/{id}/clarifications` | 案件所有者客户 | `ClarificationRequest` → 202 `CustomerCaseView` |
| GET `/v1/founder/cases` | FOUNDER | cursor/limit → `CaseList` |
| GET `/v1/founder/cases/{id}` | FOUNDER | → `CaseView` |
| GET `/v1/founder/cases/{id}/history` | FOUNDER | FounderHistoryQuery → `FounderHistoryPage` |
| POST `/v1/founder/cases/{id}/decisions` | FOUNDER | `FounderDecisionRequest`（提案目标，或仅人工处理的技术失败/订单阻断目标）→ 202 `DecisionReceipt` |
| POST `/v1/founder/operations/{id}/reconcile` | FOUNDER | `VersionPrecondition` → 202 `OperationAttempt` |
| POST `/v1/founder/notifications/{id}/retry` | FOUNDER | `VersionPrecondition` → 202 `NotificationRecord` |
| GET `/v1/founder/cases/{id}/audit` | FOUNDER | cursor/limit → `AuditPage` |
| GET `/v1/founder/analytics` | FOUNDER | 可选 created_from/created_before/status（AnalyticsQuery）→ `AnalyticsSnapshot` |

表中的 `{id}` 是简写；准确参数名以 OpenAPI 的 `case_id/evidence_id/operation_id/notification_id` 为准。201 只表示资源创建，202 只表示请求接受，不代表案件已完成。每个响应有 `X-Correlation-ID`；错误体中的 ID 必须相同。

没有公开的 AI/Risk 回写接口、通用 `execute`、任意工具调用接口或自选角色登录接口。批准后由服务端持久化调度待办，不需要客户端再发一次执行请求；调度实现不因此要求新增消息中间件。

### 附件交接

本 rc 采用 JPEG/PNG/PDF、每个文件最多 10 MiB、每次提交最多引用 10 个附件，作为待 B/C 确认的技术限制，不是新增课程硬要求。

1. 上传只创建对上传者私有的 STAGED 附件；`description` 保留客户图注，但仍是不可信文本。
2. 创建案件/补充信息时，A 原子核验归属、可用性并绑定引用为 BOUND；失败不得产生半个案件绑定。补充仅在 AWAITING_INFORMATION 且匹配当前 question_set、case owner 与 expected_case_version 时受理；上传 STAGED 本身不改变业务输入。审查/批准后的“新材料”只指既有受控内部订单/来源版本更新，须先通过状态与在途效果守卫；不新增客户任意追加或重开接口。
3. 客户只读自己的附件；Founder 通过获授权案件读取。C 的内部读取由 A 提供限定 evidence ID 的 port，不收到 bearer token、任意本地路径或任意 URL。
4. MIME 声明不是内容验证；魔数/真实格式、大小、文件名安全、授权、到期清理和日志脱敏分别在 F.04/F.07 实现。
5. 生成的模拟 PDF label 同样通过受案件权限约束的附件引用读取，不公开永久下载凭据。样例附件仅是合成元数据，不声称包含实际文件。

## 6. A ↔ C 内部 port

这些是 Python 模块间的类型边界，不是新增 HTTP 路由，也不赋予 AI 权限。

| Port | 输入 → 输出 | 必须保留的语义 |
|---|---|---|
| C1.retrieve | `RetrievalRequest → RetrievalResult` | 指定 input/corpus version；MATCHED 有 passages，NO_MATCH 无 passages；冲突保持可见 |
| C1.verify_citations | `CitationVerificationRequest → CitationVerificationResult` | 一条输入引用对应一条结果；核对 ID/version/hash/location，不代替 C2 判断主张是否被支持 |
| C2.review | `RiskReviewRequest → RiskReview` | A 提供原始陈述、只读订单 lookup、附件引用、完整 retrieval_result（含来源原文与 conflicts）、引用核验；图片观察可选。不能只让 C 重读生成器自己的结论 |
| C3.observe_images | `ImageObservationRequest → ImageObservationResult` | 仅获准图像引用，输出可见现象、限制和置信度；不判断法律权利/责任，不另设第四个业务角色 |

`RiskReviewRequest.evidence_matrix` 是待审核的生成器材料，不是可信事实；订单快照和客户/来源材料才是独立核对依据。A 提供快照且去掉无关个人信息；C2 不获得 Assessment 的隐藏推理。`ModelRun.role` 为 RISK_REVIEWER，只说明记录格式；真正独立调用/提示词仍由 C2 测试证明。

rc.2 用唯一的 `RiskReviewRequest.retrieval_result: RetrievalResult` 替换旧顶层 `passages`，不能同时发送两份来源结果。必须原样保留 C1 返回的 `status/passages/conflicts/corpus_version/retrieved_at` 和 case/input 绑定；没有已引用片段也不能省略已知冲突。`NO_MATCH` 不代表检索调用失败，也不代表自动通过风险审查。

`RetrievalResult.passages` 上限从 20 对齐为 100，与 packet 引用、引用核验结果及 Founder 的 `cited_passages` 容量相容。100 是单份交接材料的容量上限，不是每次必须取 100 条，更不是将 30 Gold 扩成 100 例；检索仍使用小型已审阅语料与关键词/BM25。

A/C 的确定性交接检查还必须验证：

1. packet、检索、订单、引用核验与原始陈述/附件均属于当前 case/input；存在 corpus 版本的对象必须一致，不能拼接另一轮材料。
2. packet 每条引用都能在同一检索结果中找到对应来源/版本/hash/location，核验结果逐条覆盖且不重复、不漏项；Founder 返回的引用原文也必须覆盖当前 packet。
3. 检索 conflict 信号不被删掉，失效或无法解析的引用不被当成有效支持。C1 负责可解析性，C2 另行判断主张支持性和冲突的业务影响。

新提案的完整材料与容量预检必须先于 current proposal 受理：Assessment 产出先作 candidate，Domain 构建并验证完整 HistoricalProposalBundle 后，才与新 proposal 原子保存。在接受新 input/revision 的边界，旧关联退出 current 有效引用但仍留不可变历史；容量失败不创建新的 current proposal，也不删除旧提案/审查/审批/操作。

生命周期历史不以 100 条为上限；但内部 DTO 的 100 条仍是一次交接容量。A 不能把页面 preview 直接当完整 Risk 输入，也不能为了通过 Schema 默默截断原文/附件。若完整必要材料超出任何内部 DTO 容量，停止该次调用，在实际处理阶段保存不可重试的 `REQUEST_TOO_LARGE` 技术失败，走既有无提案人工处理分支；已受理输入和历史仍保存。必要原文已按保留政策移除时也不能伪称已核对。

JSON Schema 只能检查这些材料各自的形状和容量；跨对象关联、引用全覆盖和语义正确性不能仅靠数组有 100 条上限证明，仍须 C1/C2/A1 的实现及合同/集成测试。

来源允许 HTTPS 或 `urn:returnops:...` 内部登记标识；`is_synthetic` 明确合成材料。URN 不是让后端随意联网抓取的地址。没有来源出版版本时填 null，但 `corpus_version`、位置及内容 hash 仍必填。内容 hash 为返回的 `content` 精确 UTF-8 bytes 的 SHA-256；预处理在入库时完成并版本化，不在核验时静默改换换行/空格。

所有内部结果都要在 A 接收时复核 case/input/proposal/corpus 对应关系；超时/模型无效 JSON/port 错误返回类型化 `ErrorEnvelope`，不能伪装成 PASS 或“无冲突”。`OrderLookupResult.PROVIDER_FAILURE` 是订单 port 自己的明确失败分支。

## 7. 版本、审批和幂等

### 7.1 三个计数器

- `case_version`：每次被接受的权威业务修改递增，用于浏览器并发检查；GET、审计查询或重复请求回放不递增。
- `input_version`：事实来源改变才递增，例如补充陈述、证据或新的订单快照；只保存风险/提案元数据不递增。
- `proposal_version`：同案每次重新生成提案递增。`proposal_id + proposal_version`、当前输入版本与当前有效 review 必须同时匹配。
- 客户端修改现有资源统一提交 `expected_case_version`，不同时使用另一套 If-Match 约定。
- 新输入/新提案使旧 review、preview 和尚待执行的旧授权不再有效。历史记录保留，但不得用“最近一条 APPROVED”判断现在能执行。
- 运维结果记录不改变提案的业务输入；provider 已产生但未知的历史效果仍可查询核实，不能因版本过期丢弃事实或另发一次请求。

### 7.2 精确范围

`ApprovalScope` 包含 case/input/proposal/review 绑定、parcel、按顺序排列的两个命令、currency/amount ceiling、expiry、allowlist version 和 SIMULATED/SANDBOX 环境。

- 命令 1：`CREATE_RETURN`，指定只读订单 ID、商品 ID/数量、parcel 和 provider。
- 命令 2：`GENERATE_LABEL`，指定同一 parcel，引用命令 1 的 `return_command_id`，固定 PDF 且 `chargeable=false`。
- 商品 ID 不可重复且数量不得超过快照；两命令必须使用相同 parcel。Schema 之外的这些关联由 A1/A2 守卫验证。
- label adapter 只能从已保存的命令 1 结果取得 provider return ID，不能接受客户端更换的 return ID。
- 批准时 Founder 只提交当前 proposal、`preview_id`、`scope_fingerprint`、决定和理由。A2 从可信会话补 principal，读取原 preview，生成 ApprovalRecord；不相信客户端重建的 scope。
- `APPROVE` 才允许 preview/fingerprint；另外三种决定不带执行范围。通过风险只是必要条件，仍要检查事实齐备、可执行状态、额度、权限和所有守卫。

无提案技术失败或订单阻断的 `MANUAL_HANDLING` 不走 `ApprovalScope`；其互斥目标与无执行权规则见第 8.1 节。

指纹采用本项目受限格式：对 **scope 对象本身**递归按对象键排序，数组保留顺序，无多余空白，ASCII 字符串、整数、布尔值，SHA-256 输出小写十六进制。服务端先将商品项按 line_item_id 排序且去重；之后不在计算时偷偷排序数组。没有浮点金额、未定义值、Unicode 或日期自动转换。此定义不声称完整实现通用 JSON canonicalization 标准；B 显示并回传服务端指纹，不自行计算授权。

样例 scope hash：

`33d8bb75e79e1219c9e3b0b1682361e32e9f573d391ef7c3d60e829875245a17`

操作指纹使用同一编码规则，对 `{approval_id, scope_fingerprint, command}` 计算 SHA-256。它绑定单个 provider 命令，未知结果查询/安全重试使用相同指纹与持久化幂等键。指纹用于一致性校验，不是签名、秘密或授权凭证。

### 7.3 重复请求与冲突

每个 POST 都有 `Idempotency-Key`，8–128 位，允许 `A–Z a–z 0–9 . _ : -`。OpenAPI header 引用共享 `IdempotencyKey` 定义，拒绝尾随换行/控制字符，不能保留另一份宽松正则。作用域是可信 principal + HTTP method/route + 目标资源 + key。

1. 先鉴权并验证请求格式，再找同作用域的已接受记录。
2. 同 key、同规范化请求复用原受理事实，不重复写入/调度。原回执内容仍全部可读时返回原回执；它不是“当前状态”，B 随后 GET 最新案件。若允许的保留/删除操作已使原回执任一正文不可返回，改为 **409 `INVALID_STATE`、`retryable=false`**，仅告知“此前已受理，原回执已不可用，请读取当前案件/历史”；不返回原文、不伪造不完整成功 DTO，也不以当前视图冒充原回执。B 不得因此自动换 key 或重新提交原意图。
3. 同 key、不同内容返回 409 `IDEMPOTENCY_CONFLICT`。不得把旧请求改个 key 后盲目重试。
4. 新意图才检查当前版本、状态和适用目标：提案路径检查 proposal/review/preview 及审批范围；无提案路径核验当前 case/input 及精确 failure/block ID，且只能人工处理。随后原子持久化决定及适用待办；两个无提案目标只能产生通知待办，不能产生 return/label 待办。
5. 受理结果不确定时用原 key 和原请求恢复；若明确收到版本冲突，先重新加载并由用户确认新的意图。
6. 并发同 key 至多一个执行者；其他请求等待已有结果或返回可安全恢复的忙/未决错误，不能先做两遍再去重。

请求规范化保留原始消息字节语义，仅补约定缺省值并稳定对象键；数组不重排。上传指纹包含实际文件 bytes hash 及允许的 filename/media_type/description，不依赖 multipart boundary。这些规则是后续持久化/并发测试要求，本轮没有实现它们。

删除优先级适用于全部 POST 回执，包括含完整 CustomerCaseView 的 create/clarification、附件元数据与决定/操作/通知回执。Domain 保留最小受理记录：可信作用域、key、规范请求指纹、原受理资源/工作 ID、受理事实及回执可用性；不为去重长期保留原请求或回执正文。清理正文须同步标记回执不可用，重放读取与清理按同一保留边界协调，不能从旧缓存越过删除。禁止删除去重记录后将原 key 当作新请求重新执行；安全生命周期由 F.07 明确，不在此假定保存期限。每次重放仍先鉴权，内容不同仍为 `IDEMPOTENCY_CONFLICT`，这些拒绝不得暴露原受理详情给无权主体。

## 8. 风险和结果如何路由

| 输出/决定 | 后续动作 | 可否派发模拟 return |
|---|---|---|
| PASS | 准备 Founder 审查；仍需其他守卫 | 尚不可，须准确审批 |
| PASS_WITH_WARNING | 展示警告后审查；不能夹带 BLOCK finding | 同上 |
| REVISE | 回 Assessment；返回具体 revision_requests | 不可 |
| NEEDS_INFORMATION | 回 intake；返回明确 questions | 不可 |
| ESCALATE | Founder 人工处理；若回自动路径须新提案、新风险通过 | 不可直接批准 |
| APPROVE | 生成可信精确审批，交确定性服务复核 | 所有守卫通过后才可以 |
| REJECT | 记录理由，发送结果通知 | 不可 |
| REQUEST_REVISION | 记录理由，返回 Assessment 生成新版本 | 不可 |
| MANUAL_HANDLING | 记录人工处理结果并通知 | 不可 |

### 8.1 提案不存在时的人工路径

`ProcessingFailure` 包含服务端保存的 `failure_id`、`case_id`、`input_version`、`stage`、`error: ErrorEnvelope` 和 `occurred_at`。stage 仅为 `COORDINATOR/ORDER_LOOKUP/RETRIEVAL/ASSESSMENT/RISK_REVIEW`，不是第四个 AI 角色，也不是第六种 risk outcome。它记录实际技术错误；不能替代正常 `REVISE/NEEDS_INFORMATION/ESCALATE` 业务审查结论。

当技术处理失败且有界恢复耗尽，Domain Service 可按状态规则把案件升级为 `ESCALATED`，保存实际 `ProcessingFailure`。

`OrderLookupBlock` 只表示提案产生前已接受的 `OrderLookupResult.CONFLICT` 或 `AUTHORITY_DENIED`。字段为 `block_id/case_id/input_version/status/message/occurred_at`；Domain Service 保存唯一 block ID，case/input/status/message 与已接受的 lookup 结果一致，安全摘要在 port 边界脱敏。它不是任意“业务风险”容器：`MATCHED`、可纠正的 `NOT_FOUND`、技术 `PROVIDER_FAILURE`、源政策冲突及模型判断不得伪装为该对象。来源冲突进入 conditional packet 与独立 Risk，不能借用订单阻断绕过 C2。API 调用者无权访问案件仍应拒绝请求，不伪造 provider 阻断。

`CaseView.processing_failure` 与 `order_lookup_block` 至多出现一个；当 `ESCALATED` 且无 `current_proposal` 时必须恰好一个。存在 `order_lookup_block` 时不得存在当前 proposal/review/preview；无 proposal 时也不得出现 review/preview。B 展示安全摘要与人工结果入口，不能创建占位提案或默认通过的审查。已处理目标可保留到通知和 `MANUAL_HANDLED` 读模型中供重读，但其存在不再授权新的人工决定；旧目标进入审计，当前目标不可混用。历史 approvals/operations、已完成效果及 UNKNOWN 不被清空。

同一 decisions 接口的三种目标严格互斥：

| 目标 | 必须带的目标字段 | 允许决定 | 禁止字段/效果 |
|---|---|---|---|
| 当前提案 | `proposal_id` + `proposal_version` | 原有四种决定，分别遵守原守卫 | 不带 failure/block ID；仅 APPROVE 可带 preview/fingerprint 并产生审批 |
| 当前无提案技术失败 | `processing_failure_id` | 仅 `MANUAL_HANDLING` | 不带 block ID、proposal ID/version、preview、scope fingerprint 或 approval；绝不派发 return/label |
| 当前无提案订单阻断 | `order_lookup_block_id` | 仅 `MANUAL_HANDLING` | 不带 failure ID、proposal ID/version、preview、scope fingerprint 或 approval；绝不派发 return/label |

三类请求都需要 `expected_case_version`、理由/实际人工结果和已验证 Founder 身份。记录同样保留互斥目标；两个无提案目标的记录不能出现 `approval_id`。服务端必须加载权威案件，检查 `ESCALATED`、确无当前提案、请求版本、目标 ID 的归属和当前 input/record 一致，并核对订单阻断来自上述已接受 lookup。旧、跨案或已替换目标不因 Schema 合法而可受理；`APPROVE/REJECT/REQUEST_REVISION` 在两个无提案目标上均不可用。共享状态图的 `ESCALATED → POLICY_ASSESSMENT` 仅指当前提案的 `REQUEST_REVISION`，不新增无提案 revision/restart 端点。

运行守卫情境沿用现有错误枚举：旧 `expected_case_version` 返回 409 `STALE_CASE_VERSION`；跨案、已替换或当前状态不再允许的目标返回 409 `INVALID_STATE`；无权决定的已认证角色返回 403 `FORBIDDEN`。这些是后续运行行为约定，样例合法性检查并未执行鉴权或状态服务。

人工处理记录与通知遵守同一幂等、审计和独立通知规则：原子保存结果、审计和通知待办后发送客户消息，失败可仅重试通知，成功后才为 `MANUAL_HANDLED`。本决定没有执行模拟退运，也不记为 `COMPLETED`；保留历史未知效果，不能把人工闭环解释为已确认未执行。相同已接受请求按第 7 节复用受理事实及可用回执，正文已移除时返回明确不可用错误，不能重复通知待办；更换 key 不使已处理目标再次有效。这是既有人工恢复分支的数据交接补齐，不增加业务角色、决定枚举、HTTP 路由或新功能；运行守卫仍属 A1/A2 后续实现。

### 8.2 操作与通知恢复

provider 明确失败与模糊超时不同：后者为 `UNKNOWN → RECONCILING`，先查询核实，不能直接重派。`reconcile` 只触发核实；确定未产生效果后若确需安全重试，仍走当前审批、provider 权限与幂等守卫。

若 provider 的标签效果已确认而本地文件/引用未保存，Domain 保留可信原效果 receipt 与制品恢复待办，公开 OperationAttempt 保持 `EXECUTING` 且没有 `result`；此时 `EXECUTING` 不代表可以再调用 provider 创建效果。内部待办只获准查询/取回/校验/保存原 label，保持原 attempt/command/parcel/provider 身份；不新增公开重派端点。只有完整 `label_evidence_id`/OperationResult 与所需审计保存后才 `SUCCEEDED`。存储失败不是 provider 无效果，不能写 FAILED/BLOCKED 或伪造 UNKNOWN；无可信成功记录的未知效果才继续原查询路径。持久化/并发/恢复授权的细节见 MA-0.3 与 AD-0.2，仍须运行验证。

先以**已持久化的决定/NotificationRecord.outcome**选择通知路径：MANUAL_HANDLED / REJECTED 必须保持原 outcome；旧 return/label 的迟到查询只更新效果事实和审计，不覆盖结果、不重开终态、不创建新的执行结果通知。人工通知仍 PENDING 或 FAILED 时也遵守此规则。只有当前有效执行分支、两效果确认成功且不存在矛盾未决效果，才允许 RETURN_CREATED。

模拟 return/label 都成功并保存后，通知失败只进入 `NOTIFICATION_PENDING/NOTIFICATION_FAILED`。通知重试不能重放两个操作。只有通知成功后才进入核心 `COMPLETED`；拒绝/人工处理通知成功后分别是 `REJECTED/MANUAL_HANDLED`，不计为模拟退运成功。

枚举 `CaseStatus` 是跨端可显示的词汇，不是可任意设置的状态机；完整转换表/守卫属于 A1.03 与个人建模工作。没有新增“撤销审批”业务动作。

## 9. 错误和前端处理

统一结构：

```json
{
  "error": {
    "code": "STALE_CASE_VERSION",
    "message": "Reload the latest case before making a new decision.",
    "correlation_id": "correlation-demo-001",
    "retryable": false,
    "details": []
  }
}
```

| HTTP | 常用 code | B 的处理 |
|---|---|---|
| 400/422 | VALIDATION_ERROR | 展示安全字段错误；不回显秘密、原始 provider/模型响应 |
| 401 | UNAUTHENTICATED | 提示重新取得合法演示会话 |
| 403 | FORBIDDEN / AUTHORITY_DENIED | 无权操作；不建议通过修改 role 绕过 |
| 404 | NOT_FOUND | ID 不存在、已删除或资源不可访问统一反馈，不泄露其他客户案件 |
| 409 | STALE_CASE_VERSION / STALE_PROPOSAL | 重新加载，再确认当前版本 |
| 409 | INVALID_APPROVAL_SCOPE / APPROVAL_EXPIRED / RISK_NOT_PASSED / INVALID_STATE | 展示阻断原因；不能把“重试”当越过守卫的方法 |
| 409 | IDEMPOTENCY_CONFLICT | 原 key 已对应不同请求；查明当前结果再建立新意图 |
| 413/415 | REQUEST_TOO_LARGE / UNSUPPORTED_MEDIA_TYPE | 更换合规附件，不重复提交原无效文件 |
| 503 | PROVIDER_UNAVAILABLE | 区分请求受理未知和业务效果未知；使用相应恢复路径 |

`retryable=true` 不代表“可以再发一次 return”。不可向客户端返回 stack trace、token、provider credential 或提示词秘密。生产级全局异常处理尚属后续实现，不因定义错误 DTO 就已具备。

## 10. 统计与审计最小约定

### 10.1 同一筛选范围与时点

既有 GET `/v1/founder/analytics` 增加三个可选 query 参数，不新增路由：

| AnalyticsQuery 字段 | 含义与缺省 |
|---|---|
| `created_from` | 案件 `created_at` 的包含下界；省略即无下界 |
| `created_before` | 案件 `created_at` 的不包含上界；省略即截至响应 `as_of` 快照 |
| `status` | `as_of` 时的单个当前 CaseStatus；省略即所有状态，不是状态历史筛选，也不是多值列表 |

两个时间均有值时必须 `created_from < created_before`，范围为 `[from, before)`。未知状态、不合法时间或反向/空区间返回 422；比较两个时间的顺序必须由应用实现，不能宣称 JSON Schema 已完成。所有数据按 `as_of` 一致快照读取，显式上界晚于 `as_of` 也不包含未来数据。

`AnalyticsSnapshot.filters` 必填，回显本次经过校验的筛选对象；未给参数时为 `{}`，省略项按上表与 `as_of` 解释，不伪造用户给过的时间。B 显示筛选和时点，不自己重新算一套窗口。

`case_count`、状态分布、风险分布和耗时计数全部使用这一组案件；每个 case 只计一次，不能用事件时间或 proposal 创建时间另选 latency 分母。状态取 `as_of` 当前状态；风险取当前提案、当前输入的最新有效 review。旧 proposal 的 PASS 不算当前 PASS；无有效 review 单列，不能计为通过。

### 10.2 成功、失败与未测量

`proposal-latency-v1` 起点为接受完整输入，终点为保存 review-ready proposal；包含期间机器修改/风险循环，排除人工和实物等待。每案只选择**当前 input 的最新 assessment episode**，一个 episode 内部的重试或多版本不能重复计数：

- `sample_count`：该 episode 产出可审阅提案并有有效完整测量；不表示风险通过或退运成功。
- `failed_count`：该 episode 因技术失败而结束，未产出有效可审阅结果。
- `unmeasured_count`：未开始、信息不完整、仍在处理中或没有有效测量记录的案件；不得填假耗时或偷偷剔除。

三类互斥且 `sample_count + failed_count + unmeasured_count = case_count`。新 input 不得继承旧 input 的成功耗时。状态计数之和，以及风险计数之和加 `cases_without_current_review`，也都必须等于 `case_count`；这些跨字段/跨记录关系需要 F.06 实现及对账测试。

有效提案的业务风险结论为 `ESCALATE` 时，若已有完整可审阅结果和测量，仍可计入 `sample_count`；不得仅因案件为 `ESCALATED` 就算作技术失败。技术失败且缺少耗时值仍计为已知 `failed_count`；真正无法判定该轮结果或缺测的其余情况才落入 `unmeasured_count`。

无提案订单阻断没有 review-ready proposal 测量时属于 `unmeasured_count`；它是已知业务阻断，不能伪记为技术 `failed_count`，也不能继承旧 input 的成功耗时。该说明沿用上述三分母口径，不新增指标或把阻断视为成功。

p50/p95 只对成功测量子集计算，不把它当全系统成功率；`sample_count=0` 时省略两值，不填假 0。展示失败与未测量计数及分母。评测运行另保留 input/model/corpus/environment 版本、token、费用和失败分母，不能仅靠 Dashboard 汇总证明 NFR-005。

### 10.3 审计内容

审计事件包含相关 ID、case version、组件版本、对象引用及 hash，不放原始附件/token/完整个人内容。rc.4 用可信 `actor: ActorProvenance` 替换粗粒度 actor_type：人类 principal、模型的完整受限 `model_run: ModelRun` 元数据、服务 component 三种互斥形状；Coordinator 也能直接读取 model/provider/prompt 版本，不依赖不存在的运行记录端点。`object_ids` 仅用于关联；必填 `history_refs` 指向可授权读取的精确 record_id/kind/object_id/object_version，涉及已接受业务对象时必须包含相应版本。actor 来源与引用完整性均由 Domain 验证，不能由客户端自报。首事件省略 previous hash；完整链编码、持久化、脱敏后仍可核验等属于 F.05/F.07，而非本轮实现。

### 10.4 历史读取、预览和保留政策

这是 FR-011/012 的读取补齐；仅增加两个只读 GET，不增加业务角色、执行能力或通用对象平台。Founder 可选择 `STATEMENT/EVIDENCE/PROPOSAL/REVIEW/DECISION/APPROVAL/OPERATION/NOTIFICATION/PROCESSING_FAILURE/ORDER_LOOKUP_BLOCK`；客户只可选择本案 `STATEMENT/EVIDENCE/OUTCOME_MESSAGE`，且后者仅含已 SENT 的安全消息，不能返回完整 NotificationRecord。两个角色使用独立 Schema，不能把 Founder 材料下发后靠 UI 隐藏。

`HistoryRecord` 为已接受对象的不可变修订：record ID、case/version、kind、object ID/version、稳定 sequence、时间、内容 hash 和 availability。PROPOSAL 的 object_version 等于 proposal_version；其他 kind 按对象从 1 编号，后续状态改变追加修订，不覆写旧 revision。AVAILABLE 必须有对应严格类型的 content；REDACTED/DELETED 必须只保留允许的完整性引用和固定移除原因，不得携带正文。未知属性、任意 JSON payload、外部正文 URL 均不允许。

- PROPOSAL 保存 `HistoricalProposalBundle`：使用完整 RiskReviewRequest 形状保存当时 packet、原始陈述、附件、订单 lookup、完整 retrieval/conflicts、citation verification 和可选图片观察；在独立 review 前保存，不能用当前语料重新拼接。REVIEW 保存 RiskReview 和对应 proposal_record_id。订单阻断同时保存原 lookup 与 block。
- 旧 citation 按 passage/document/source version/corpus/location/hash 精确解析到当时原文；没有出版版本也不能省略 corpus/hash。审核需校验同案、同 input、proposal/version、绑定的原 statement 和来源全覆盖。Schema 合法不证明这些关联真实。
- `CaseView/CustomerCaseView` 的生命周期数组改为必带 `collection_windows` 的有界预览；每类先选 snapshot 内每个 object 的最新修订，仅当该修订 AVAILABLE 才显示；绝不因最新修订被移除而回退旧内容/状态。保留原始陈述（若仍可读），其余按最新记录填满至 100。它不是连续历史首页。total_records 统计所有修订含 tombstone，preview_count 等于显示数，unavailable_count 统计 tombstone，truncated 当且仅当 total_records 大于显示数。全部窗口与 CaseView 使用同一 snapshot/case_version；从 start_cursor 开始读取该 kind 的完整历史（默认 limit=20），不能从预览尾部接页。执行守卫从权威存储读取，绝不能因为 preview 没显示 UNKNOWN 就认为没有未知效果。
- 每页固定 `snapshot_id/snapshot_case_version/as_of`、kind 和精确筛选；排序为 `(recorded_sequence, record_id)`。首请求省略 cursor；object_version 必须与 object_id 一起给。后续请求重复 kind、object filters、limit。服务端 cursor 必须绑定 principal、角色、case、query、snapshot、最后稳定键，并验证签名或服务端状态；每页重新鉴权，不能信任可编辑 base64 内容。
- 使用不可变 revisions 的 as-of 读取或物化快照；仅冻结时间上界而读取最新可变 OperationAttempt/Notification 行并不满足约定。翻页期间新插入/状态更新不能混入原快照。跨身份/案件/类型、改筛选、篡改 token 在鉴权后返回 409 INVALID_STATE；无权案件仍先按既有 403/404 规则拒绝。快照过期明确返回 409 并要求用户重新从首请求开始，不能静默换快照。最终页省略 next_cursor。
- 允许的内容移除优先于旧快照正文可读性，但不改变记录成员/排序，返回 tombstone。清理须覆盖旧 bundle、当前派生读模型、缓存及附件下载；禁止从旧 cursor 恢复已删正文。若 bundle 的必要个人材料已移除，整体 tombstone，不伪造空文本。视图的 statements 可在明确窗口/移除记录下为空；普通新建案件仍必须保存原始 statement。数据不完整时不得保留可执行的 preview/授权判断。具体保留期限与可删除时机由 F.07 约定，不在此编造期限。

后续运行验收必须覆盖：101+ 记录无重复/遗漏；翻页间追加和状态更新保持原修订；跨 case/kind/principal/role cursor、改 filter/limit、篡改/过期；旧来源版本还原；删除后翻页只见 tombstone；删除后重放已接受 POST 返回第 7 节的不可用错误、零新写入/调度，原始请求文本不得从回执或诊断恢复；客户无法取得内部正文。当前静态样例和测试 oracle 仅验证结构及构造轨迹一致性，未实现 cursor、历史存储、保留服务或身份守卫。

## 11. 验证证据与不能得出的结论

**rc.5 本地修订（2026-09-07）：**56 项契约检查通过；86 正例、46 负例、21 未执行运行情境。新增三项检查覆盖删除后已受理澄清回执、结构合法错误中的已删正文，以及标签制品未完成/完整成功的边界。完整离线、模型渲染、环境子集和精确字节证据见 [A-FIX-0.1](reviews/a-defect-closure-20260907.md)。本轮没有业务服务、远端 CI、C 本人复现或人审验收；下面 rc.4 数字保留为历史。

**rc.4 本地验证（2026-09-07）：** 基于 HEAD `90931562f7e8d038b994d8d3ff3b2f289e462643` 加当前未提交修订，隔离 Python 3.12 契约环境运行 **53 项 unittest，全部通过**；当前样例 **86 个合法 DTO、46 个非法结构、20 个未执行运行守卫情境**。新增检查覆盖严格 history/角色隔离/移除/actor/cursor 形状，旧 material 引用及 101 条构造分页轨迹；后两者是测试数据 oracle，不是服务实现。仓库内模型工具的 **6/6 检查组、7 项工具回归、15 个 Mermaid 语法块**通过：23 份文档/189 个本地目标，7 对 SVG 内嵌源码对应，19 个 MA 情境/37 个动作/七态，3 个 CS 视图/29 条连接/12 个情境；89 个 WBS 的 ID/Owner/Reviewer/S/F 与 HEAD 一致且无环。改动的 3 份个人 UML 已本地重渲染并检查图像。完整命令见 contracts/README 和 tools/model-checks/README。git diff --check 通过；这些证据不等于运行安全、CI、人审或课程验收。

本轮 2026-09-07 10:36 UTC 只读复查 GitHub：PR #11 仍 Open、非 Draft、head `9093156`、未合并；main 仍 `9eb7b0b`。rc.4/MA-0.2 未 commit/push，不在该 PR 中。本轮未重新读取 Jira，也未修改 Jira 或发成员消息。

**rc.2 历史记录（不能作为后续修订结果）：** 2026-09-07 的独立验证环境记录 35 项契约 unittest、包含旧领域模型 4 项检查的 39 项本地 pytest 通过；当时编译 8 个 Schema 正则，对 7 类严格端锚执行 35 个尾随换行负例，并检查 15 个文档、15 个 Mermaid 块和 94 个本地链接。OpenAPI header 的重复正则未纳入当时的边界验证；这些记录也不是 UML 语义或课程验收。

**rc.3 历史验证（2026-09-07）：** Python 3.12 隔离契约环境运行 **44 项契约 unittest，全部通过**；另一个环境运行 **4 项旧领域模型 pytest，全部通过**。两次检查使用不同环境。本轮发布前检查的 19 个文档中，15 个 Mermaid 块均通过语法解析，121 个本地文件链接有效；FR/NFR/BR 与六个用例编号完整。JavaScript 另验证共享 ID/幂等键/hash 正则的 3 个合法值及 72 个非法值。另对 main 中 rc.2 的 80 个正/负 DTO 样例做差分验证，接受/拒绝结果未变。没有 HTTP/E2E、数据库、真实 AI 或 provider 实现；本地测试不产生 GitHub CI 证据或 Jira 验收记录，PR #9 的合并也不覆盖 rc.3。

rc.3 当时使用 64 个合法 DTO、36 个非法结构、16 个未执行运行时守卫情境。当前 rc.4 计数以样例文件与本节新增验证记录为准。它们不是业务测试案件总数、Gold 标签、真实用户或实验结果；没有扩写被冻结的研究库或 30 Gold 计划。

候选的自动检查范围：

- JSON Schema 定义、全部本地引用与 OpenAPI 3.1 结构；
- 合法 DTO 可校验，非法字段/金额/枚举/角色元数据/执行命令组合被拒绝；
- 公共操作的角色声明、幂等键、相关 ID、版本前置条件及请求/响应样例对应；
- 示例中的订单多商品、单 parcel、来源 hash、审批/操作指纹与版本引用一致；
- 日期 format 检查真实启用，而非只检查字符串类型；
- rc.2 的互斥决定目标、完整 retrieval_result、容量边界、统计 query/未测量分支，以及 ID 换行/控制字符负例。
- rc.3 的两种订单阻断、三目标互斥、当前读模型排他、旧/跨案/已替换目标 fixture 一致性，以及 OpenAPI 公共幂等 header 与共享定义一致。

`runtime_guards` 中旧版本、过期、改指纹、升级、错角色、同 key 改请求等请求 **本身都符合 JSON 格式**。测试只核对情境和错误响应的结构；即使补了当前失败 ID、引用交接和统计一致性的样例检查，也不能证明真实服务已加载正确案件/输入、执行过状态守卫、保留全部冲突或正确聚合数据库。没有发 HTTP、调用 provider、证明零副作用或完成 Gate 1。

旧四项领域模型测试通过也不代表旧代码已经匹配本契约。A1.01 后续需迁移 float money、单商品字段、旧 Agent/DecisionProposal 词汇、缺失 proposal version/精确 scope 的审批模型；这次保持原文件不动以免跨过第一步。

## 12. 需求 → 模型 → 下一项实现

| 契约部分 | Requirement / UC | 模型对齐入口（rc.2 / PR #9、rc.3 / PR #11 为历史发布；本地 rc.4 待联合确认） | 后续 Owner |
|---|---|---|---|
| statement、facts、case、clarification | FR-001～005 / UC-01、UC-01E、UC-02 | [共享类图](diagrams/01-domain-class-diagram.md)、[用例图](diagrams/05-use-case-diagram.md)；B intake 个人链 | A1、B1 |
| passage、citation、packet、risk | FR-006～008 / UC-02、UC-03 | 共享类图、[交互图](diagrams/03-sequence-diagram.md)；C review 个人链 | A1、C1/C2 |
| processing_failure、order_lookup_block、preview、decision、approval、command | FR-003、009～012 / UC-02、UC-03、UC-04、UC-05 | 三种目标、无提案人工分支；Approval/Execution 活动与交互；A OperationAttempt 状态机 | A1/A2、B2；C review |
| operation、notification | FR-010～012 / UC-04、UC-05 | [状态图](diagrams/02-state-machine-diagram.md)、交互图的核实/通知分支 | A2、B2 |
| auth、attachment、audit、analytics | FR-001、009、011、012 / NFR-001～003、005～009 | 共享 Class/Package/Deployment、Audit Port；待共享建模验收 | A 的 F 系列；B/C 消费 |
| sandbox、image、analytics UI | OF-004、OF-001、OF-006 | 对应 docs/07 冻结的三个人 optional 增量 | A3、C3、B3 |

上轮已对齐旧正文与五张共享图，但这不等于本次新字段已获模型验收；三人需核对无提案人工路径、检索冲突交接与统计数据选择是否逐项对应。UML 仍是课程交付物；机器 Schema 不能替代类图、复合结构图或每人的活动/顺序/状态机图。每次实现 PR 应使用表中具体映射，而非只贴“FR 全部覆盖”。

## 13. 修订历史与候选迁移

### 13.1 rc.1 → rc.2 的历史修订

| 修订 | rc.2 的约定 | 消费方迁移 / 仍须验证 |
|---|---|---|
| 无提案技术失败无法记录人工结果 | ProcessingFailure、CaseView 故障分支与互斥 Founder decision target | B 不再伪造提案；A 加载当前 case/input/failure 并校验状态、审计和通知；不存在失败目标执行权限 |
| 检索冲突在 C2 输入中丢失 | 必填完整 retrieval_result，删除旧顶层 passages | A/C 一起替换调用与 mock；保留 conflicts，逐条验证来源和引用，C2 负责语义 |
| 20 条检索容量与 100 条引用不相容 | passage/citation/check/read-model 容量上限对齐 100 | 校验边界与引用覆盖；不要求取满，不改 Gold/技术栈 |
| 统计缺筛选和明确分母 | AnalyticsQuery、filters、unmeasured_count，同 cohort/as_of 及当前输入 episode | B 更新 query 和展示；A 实现时间顺序、去重及聚合；C 核对指标，不把成功子集当全部案件 |
| ID 允许尾随换行等非法值 | 更严格的完整 ASCII ID 边界 | 更新边界负例；运行接口仍须实际启用验证，ID 合法不等于有权限 |

### 13.2 rc.2 → rc.3 的最小迁移

保留现有 proposal 和 `processing_failure_id` 请求/记录形状，新增 `OrderLookupBlock`、`CaseView.order_lookup_block` 与 `order_lookup_block_id` 第三互斥目标；将“无提案升级必有技术失败”改为两类记录恰好一个。B 的无提案页面和 mock 需识别这两个目标，A 保存并验证当前 lookup/block 绑定；C 核对订单阻断与来源/风险冲突的区别。OpenAPI `Idempotency-Key` 直接引用共享定义，同步覆盖 header 边界；UC-02/UC-03 与共享 Class/State/Sequence 展示同一分支。

这是尚未正式采纳的 rc 间迁移，不假装无缝兼容。旧 RiskReviewRequest/AnalyticsSnapshot 仍须完成 rc.2 迁移，严格客户端还需认识 rc.3 新 CaseView/decision 分支。URL `/v1`、13 个公共操作、五风险结果、四人工决定及固定九功能保持不变。统一更新 mock/消费代码后再记录采纳版本，不在同一进程混用各 rc 形状。修好 Schema 表达能力不代表实现运行服务。

### 13.3 rc.3 → rc.4 本地候选迁移

新增两个角色隔离的历史 GET（共 15 个公共操作）；严格客户端必须消费 collection_windows、空但有移除标记的 statement preview、typed history/tombstone、ActorProvenance/history_refs 和统一 Cursor。旧 13 个操作保留路径与业务权限；通知 outcome 优先与合法新材料入口补入模型。内部输入容量超限不能静默截断，历史容量与模型上下文容量分开处理。Owner/Reviewer/89 项 WBS 的 S/F 不变。

PR #11 记录本候选的具体 head 和 review；rc.4 需要按精确版本审阅后才能采纳，不覆盖 rc.3 历史 review，也不代表 Jira 已同步或正式验收完成。

### 13.4 rc.4 → rc.5 本地语义修正

15 个公共操作、请求/响应形状、七个 OperationAttempt 状态与已有错误码保持不变。第 7 节明确允许的删除优先于原 POST 回执重放：原内容已不可读时保留受理/去重事实并返回既有 409 INVALID_STATE，不重新执行；B 需区分该错误和可重试的新意图。新反例仅是离线规格检查，运行实现仍属 F.03/F.07/A1/A2。

MA-0.3 / CS-0.2 / AD-0.2 将 provider 原始成功观测与公开 OperationResult 分开。标签已存在而制品待保存时，原 OperationAttempt 保持 EXECUTING，内部持久化成功 receipt 及仅取回/存储原标签的待办；不得因失败、重启或批准过期重新 invoke。完整标签引用和结果由 Domain 保存后才 SUCCEEDED；UNKNOWN 仍表示效果事实未知。该内部子阶段不新增 wire 状态，详细守卫和恢复见 docs12/13/14。产品词汇表同步使用 EXECUTING。

本修订尚未发布；PR #11 的 rc.4/57d86fe 及已有 CI 是历史评审证据。后续发表和人审须指明 rc.5 的准确提交，不能回填旧 review。尝试序号最小值与 MA-Q03 的运行并发证明仍未在本轮采纳或实现。

## 14. 三人确认后才验收 F.01

- [ ] A：确认唯一状态源、版本/幂等、scope 指纹、商品与 parcel 关联，以及当前 failure/block 与已接受 lookup 绑定、引用全覆盖和统计对账的运行守卫责任。
- [ ] B：确认提交/澄清、引用原文、四种决定、无提案人工分支、202/409/未知结果、统计筛选/分母，以及历史分页/预览/移除提示足以支撑页面；确认附件技术限制。
- [ ] C：确认来源无版本/合成来源、完整 retrieval_result 与 conflicts、引用核验容量、独立 Risk 输入、五种结果、计时口径和 C3 交接；完成指定 Reviewer 审查。
- [ ] 三人联合确认 rc.5 规格/模型与三目标、检索交接、公共 ID 边界、历史分页/保留、删除后回执重放、标签制品恢复、容量失败和通知 outcome 对应；PR #9 仅作 rc.2 历史，区分结构检查、运行验证和课程个人模型验收。
- [ ] 三人确认后记录契约采纳版本及当前 PR review 证据，并关联 [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)；链接存在不等于同意或进度，本轮不修改 Jira。

下一步是 **B/C 确认这份交接约定**。期间 A 可继续无开始依赖的 F.02 准备；A1.01 的正式对齐应等 F.01 验收。不是重新讨论九功能分工，也不是立刻把 LLM 接进执行路径。

规范依据：[OpenAPI 3.1.0](https://spec.openapis.org/oas/v3.1.0.html)、[JSON Schema 对象与额外字段](https://json-schema.org/understanding-json-schema/reference/object)。项目的权限、审批、免费模拟和贡献边界来自 docs/00 与 docs/07，而非这些通用规范。

## 15. 合同外的演示部署接口（2026-10-31）

`POST /v1/auth/register` 与 `POST /v1/auth/login` 只在 `demo.py serve --accounts` 时注册，不属于合同 v1，不写入 `contracts/v1/openapi.json`，也不改变已冻结的操作和 DTO。注册只创建该私有凭据文件所属商店的 CUSTOMER；店主账号仍只能由 `demo.py provision` 预置。请求体为 `{"username", "password"}`；成功返回 `access_token`、`token_type`（`Bearer`）、`expires_in`（899）、`principal_id`、`role`，令牌与预置会话一样由 `GET /v1/session` 和现有校验接受；错误沿用 `ErrorEnvelope`。实现见 `apps/api/returnops_api/accounts.py`，限制见 [docs/47](47-stage2-submission-runbook.md) 第 7 节第 18 项。

`POST /v1/auth/renew`（2026-11-01，组长认为 15 分钟太短）同样只在 `serve --accounts` 时注册，不属于合同 v1。它不改变 F.03 的会话上限：每个令牌仍至多 899 秒（docs/18；数据库约束不变）。请求只带 `Authorization: Bearer`，无请求体；令牌须先通过现有校验，且须是本进程中由密码登录、注册或其续期签发的令牌（`demo.py provision` 的访问密钥不续期，进程重启后需重新登录，均为 409 `INVALID_STATE`）；只在当前令牌最后 5 分钟内续期，新令牌最晚在登录后 1 小时到期，超过即 409；成功返回与登录相同的字段，`expires_in` 为新令牌剩余秒数。“太早”的拒绝标为可重试（`retryable: true`），新令牌不会比当前令牌更晚到期时视为一小时已满。网页从令牌到期前约 280 秒开始请求续期，失败后每 25 秒重试到令牌到期；被最终拒绝（访问密钥、一小时已满、令牌无效）时保留当前令牌到其自然到期；另一个标签页续期后，本页沿用新令牌，不重新加载。

`GET /v1/cases`（顾客本人的案件列表，2026-10-31）同样只在 `serve --accounts` 时注册，不属于合同 v1，不写入 `contracts/v1/openapi.json`。它返回已登录顾客本人在其商店、仍可用的案件，按提交时间从新到旧，最多 20 条，响应为 `{"items": [...], "limit": 20}`；每条含 `case_id`、`status`、`created_at`、`updated_at`、`awaiting_answer`（是否在等顾客回答），以及可选的 `requested_outcome` 和 `excerpt`（顾客原始陈述的开头，空白合并，超过 120 个字符时截断并加 `...`）。列表不含店主数据、模型事实或其他顾客的案件；每个列出的案件都按 `getCustomerCase` 的同一套归属检查重新授权。店主调用返回 403 `FORBIDDEN`，带查询参数返回 422 `VALIDATION_ERROR`；未开 `--accounts` 时该路径只有冻结的 `POST`，`GET` 得到 405，前端随之隐藏列表，按案件编号查询照旧。实现见 `packages/returnops_domain/customer_case_list.py`，前端为 `apps/web/src/components/MyCasesList.tsx`。

店主 AI 助手（2026-10-31）的三个路由 `POST /v1/founder/cases/{case_id}/assistant/reply`、`POST /v1/founder/assistant/triage`、`POST /v1/founder/assistant/summary` 只在 `serve --accounts` 且模型展示开启时注册，同样不属于合同 v1，不写入 `contracts/v1/openapi.json`。三者只接受店主会话（顾客 403、无会话 401，均不调用模型），不带请求体、不接受查询参数（422）；返回仅供参考的回复草稿（`customer_language`、`reply`、`reply_english`）、未结案案件的紧急程度与同类分组（`cases`、`groups`，以案件编号返回）或近七天的计数摘要（`summary`、`highlights`），每个回答都带 `model_id`、`prompt_version`、`generated_at`。模型失败、超出调用上限、回答不合格或两个调用位都在使用时返回 503 `INTERNAL_ERROR`。不写任何业务数据。2026-11-01 起同样条件下还有第四个路由 `POST /v1/founder/cases/{case_id}/assistant/risk-review`：C2 风险审查对单个案件给出仅供参考的审查（`outcome` 为 C 的五种结论之一，另有 `summary`、`findings`、`questions`、`revision_requests`，以及 `case_version`、`case_status`、`reviewed_proposal` 和 `recorded: false`），不记为案件的风险审查，也不改变案件状态。详见 [docs/44](44-coordinator-showcase.md) 的 Founder AI assistant 一节。
