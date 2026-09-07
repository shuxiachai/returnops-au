# F.01：公共接口与数据契约 v1

> 版本：`1.0.0-rc.2`；2026-09-07。状态：**已上传 [PR #9](https://github.com/shuxiachai/returnops-au/pull/9) 供评审，尚未合并或获三人验收**。
> Owner：A；指定 Reviewer：C；B 必须确认前端消费边界。Jira key 尚未映射。
> 本文落实 [固定分工](07-frozen-work-allocation.md) 与 [F.01](08-delivery-work-packages.md)，不重开业务范围，不代替 tutor 确认。
> 这是“数据如何交接”的约定，不是已经运行的服务；没有实现鉴权、数据库、状态守卫、LLM 或 provider。本次补齐五项契约缺口，不等于相应运行行为已实现。

## 1. 三人各自看什么

| 使用者 | 重点 | 后续工作 |
|---|---|---|
| A | 案件/提案版本，审批范围，操作与通知记录，公共错误 | F.02 环境/CI；F.01 验收后按 A1.01 对齐领域模型，按依赖开展后续工作 |
| B | 客户请求/读模型、Founder 读模型、四种决定、错误和超时反馈 | 用样例做 B1/B2 mock；不自行生成状态、风险、审批或操作成功结论 |
| C | 检索/引用核验/独立风险输入输出、来源元数据、图片观察 | 按 C1/C2/C3 实现自己的模块；核对标签枚举；映射或复用 Jira 条目 |

交付入口：

- [机器可读 JSON Schema](../contracts/v1/schemas.json)：`$defs` 是命名数据结构注册表；必须选中具体定义验证，不能只验证根对象。
- [OpenAPI](../contracts/v1/openapi.json)：13 个计划公共操作，引用同一份 Schema；不是额外维护一套字段。
- [JSON 样例](../contracts/v1/examples.json)：`positive`、`negative` 和 `runtime_guards` 三组。
- [基础契约检查](../tests/contracts/test_contract_v1.py)、[rc.2 回归检查](../tests/contracts/test_contract_v1_rc2.py) 与 [运行说明](../contracts/README.md)。

## 2. 不改变的边界

- 一家澳大利亚实体商品网店、一位 Founder；英文合成/去标识化数据、AUD。
- A 的 Coordinator/Assessment、C 的独立 Risk Reviewer 共三个业务 AI 角色；Domain Service 和 Operations Service 是确定性服务。
- AI 只返回各角色的非执行性结构化结果（如 `CoordinatorResult`、`DecisionPacket`、`RiskReview`）。服务端另建只读 `ActionPreview`；它仍不是授权。
- 只有服务端验证的 Founder 能创建可信 `ApprovalRecord`。客户端不能提交可信角色、审批记录、任意命令或 provider 凭据。
- 一个案件关联一个订单的多个商品项；一次退运只有一个 parcel、一个 label。不支持拆包、多单合并、实际退款、收费物流或生产数据修改。
- A3 的 `SANDBOX` 只是已选扩展的类型边界，必须另获明确的无收费测试权限；字段存在不代表 provider 已接入。课程核心使用 `SIMULATED`。
- 本轮不改旧 `packages/domain/models.py` 或 B/C 的 PR，也不实现 F.02/F.03/A1/A2。旧正文与五张共享图的 v1 对齐稿已与 rc.2 一同发布到 PR #9；仍需联合确认契约与模型，不声称图已获验收。

## 3. 公共格式和缺省规则

| 项目 | 约定 |
|---|---|
| 路径与版本 | URL 主版本 `/v1`；契约文档版本 `1.0.0-rc.2`；与案件/提案计数版本不同 |
| ID | 3–80 位不透明 ASCII 标识符，首位为字母/数字，其余为字母/数字/`_`/`-`；拒绝尾随换行及控制字符，不能推导权限。客户端仅引用服务端返回的 ID |
| 时间 | RFC 3339 UTC，统一以 `Z` 结束；不得用客户端时间判断审批是否过期 |
| 金额 | 整数 AUD cents，例如 `2000` 表示 AUD 20.00；不能用浮点金额做审批指纹。当前执行额度恒为 `0` |
| 未知值 | 可选字段省略；`source_version: null` 明确表示来源没有发布版本，不能编造版本号 |
| 额外字段 | DTO 对象关闭额外字段；客户端角色/命令注入不能因“前端不用”而忽略 |
| 客户意图 | `original_message` 唯一必填；缺订单、期望或附件仍可提交并进入后续澄清。缺省 `requested_outcome` 归为 `UNSPECIFIED`，缺省 `evidence_ids` 归为 `[]` |
| 其他期望 | `OTHER` 保留“其他诉求”分类，原文仍是依据；不自动扩大可执行命令范围 |
| 字符串 | 原始陈述按接收内容独立保存，不被抽取覆盖。仅空白消息由服务端拒绝；展示必须转义，不能当 HTML/指令 |
| 分页 | cursor 不透明且受授权范围约束；无下一页时省略 `next_cursor`，不返回伪造空页 token |
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
| `RiskReview` | C2 的独立调用 | 精确绑定 case/input/proposal/corpus；五种 outcome、发现、修改要求或问题；无批准/派发能力 |
| `ActionPreview` | A 的确定性领域逻辑 | 当前可批准提案的精确免费模拟范围、命令、provider、parcel、到期时间、指纹；B 确认显示 |
| `FounderDecisionRecord` / `ApprovalRecord` | A2 根据可信 Founder 请求 | 提案目标保留四种决定；无提案技术失败目标只允许 MANUAL_HANDLING。两个目标互斥，只有提案目标 APPROVE 才有独立精确审批记录 |
| `OperationAttempt` | A2 | provider ID、命令/审批绑定、操作指纹、持久化幂等键、类型化结果/错误；UNKNOWN 不冒充失败或成功 |
| `NotificationRecord` | A2 | 操作结果通知与拒绝/人工处理通知；独立 PENDING/SENT/FAILED、下一步和重试次数 |
| `CaseView` | A 的 Founder 查询 | 上述当前对象和历史记录；`cited_passages` 提供当前引用原文/来源供 B 核对；ESCALATED 且无 current_proposal 时必须提供 processing_failure |
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
| POST `/v1/cases/{id}/clarifications` | 案件所有者客户 | `ClarificationRequest` → 202 `CustomerCaseView` |
| GET `/v1/founder/cases` | FOUNDER | cursor/limit → `CaseList` |
| GET `/v1/founder/cases/{id}` | FOUNDER | → `CaseView` |
| POST `/v1/founder/cases/{id}/decisions` | FOUNDER | `FounderDecisionRequest`（提案目标或仅人工处理的技术失败目标）→ 202 `DecisionReceipt` |
| POST `/v1/founder/operations/{id}/reconcile` | FOUNDER | `VersionPrecondition` → 202 `OperationAttempt` |
| POST `/v1/founder/notifications/{id}/retry` | FOUNDER | `VersionPrecondition` → 202 `NotificationRecord` |
| GET `/v1/founder/cases/{id}/audit` | FOUNDER | cursor/limit → `AuditPage` |
| GET `/v1/founder/analytics` | FOUNDER | 可选 created_from/created_before/status（AnalyticsQuery）→ `AnalyticsSnapshot` |

表中的 `{id}` 是简写；准确参数名以 OpenAPI 的 `case_id/evidence_id/operation_id/notification_id` 为准。201 只表示资源创建，202 只表示请求接受，不代表案件已完成。每个响应有 `X-Correlation-ID`；错误体中的 ID 必须相同。

没有公开的 AI/Risk 回写接口、通用 `execute`、任意工具调用接口或自选角色登录接口。批准后由服务端持久化调度待办，不需要客户端再发一次执行请求；调度实现不因此要求新增消息中间件。

### 附件交接

本 rc 采用 JPEG/PNG/PDF、每个文件最多 10 MiB、每次提交最多引用 10 个附件，作为待 B/C 确认的技术限制，不是新增课程硬要求。

1. 上传只创建对上传者私有的 STAGED 附件；`description` 保留客户图注，但仍是不可信文本。
2. 创建案件/补充信息时，A 原子核验归属、可用性并绑定引用为 BOUND；失败不得产生半个案件绑定。
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
- Founder 只提交当前 proposal、`preview_id`、`scope_fingerprint`、决定和理由。A2 从可信会话补 principal，读取原 preview，生成 ApprovalRecord；不相信客户端重建的 scope。
- `APPROVE` 才允许 preview/fingerprint；另外三种决定不带执行范围。通过风险只是必要条件，仍要检查事实齐备、可执行状态、额度、权限和所有守卫。

无提案技术失败的 `MANUAL_HANDLING` 不走 `ApprovalScope`；其互斥目标与无执行权规则见第 8.1 节。

指纹采用本项目受限格式：对 **scope 对象本身**递归按对象键排序，数组保留顺序，无多余空白，ASCII 字符串、整数、布尔值，SHA-256 输出小写十六进制。服务端先将商品项按 line_item_id 排序且去重；之后不在计算时偷偷排序数组。没有浮点金额、未定义值、Unicode 或日期自动转换。此定义不声称完整实现通用 JSON canonicalization 标准；B 显示并回传服务端指纹，不自行计算授权。

样例 scope hash：

`33d8bb75e79e1219c9e3b0b1682361e32e9f573d391ef7c3d60e829875245a17`

操作指纹使用同一编码规则，对 `{approval_id, scope_fingerprint, command}` 计算 SHA-256。它绑定单个 provider 命令，未知结果查询/安全重试使用相同指纹与持久化幂等键。指纹用于一致性校验，不是签名、秘密或授权凭证。

### 7.3 重复请求与冲突

每个 POST 都有 `Idempotency-Key`，8–128 位，允许 `A–Z a–z 0–9 . _ : -`。作用域是可信 principal + HTTP method/route + 目标资源 + key。

1. 先鉴权并验证请求格式，再找同作用域的已接受记录。
2. 同 key、同规范化请求返回原受理回执，不重复写入/调度；原回执不是“当前状态”，B 随后 GET 最新案件。
3. 同 key、不同内容返回 409 `IDEMPOTENCY_CONFLICT`。不得把旧请求改个 key 后盲目重试。
4. 新意图才检查当前版本、状态和适用目标：提案路径检查 proposal/review/preview 及审批范围；技术失败路径核验当前 case/input/failure 且只能人工处理。随后原子持久化决定及适用待办；失败目标只能产生通知待办，不能产生 return/label 待办。
5. 受理结果不确定时用原 key 和原请求恢复；若明确收到版本冲突，先重新加载并由用户确认新的意图。
6. 并发同 key 至多一个执行者；其他请求等待已有结果或返回可安全恢复的忙/未决错误，不能先做两遍再去重。

请求规范化保留原始消息字节语义，仅补约定缺省值并稳定对象键；数组不重排。上传指纹包含实际文件 bytes hash 及允许的 filename/media_type/description，不依赖 multipart boundary。这些规则是后续持久化/并发测试要求，本轮没有实现它们。

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

### 8.1 提案不存在时的技术失败人工路径

`ProcessingFailure` 包含服务端保存的 `failure_id`、`case_id`、`input_version`、`stage`、`error: ErrorEnvelope` 和 `occurred_at`。stage 仅为 `COORDINATOR/ORDER_LOOKUP/RETRIEVAL/ASSESSMENT/RISK_REVIEW`，不是第四个 AI 角色，也不是第六种 risk outcome。它记录实际技术错误；不能替代正常 `REVISE/NEEDS_INFORMATION/ESCALATE` 业务审查结论。

当技术处理失败且有界恢复耗尽，Domain Service 可按状态规则把案件升级为 `ESCALATED`。如果没有 `current_proposal`，`CaseView` 必须带对应 `processing_failure`；B 展示错误的安全摘要与人工结果入口，不能创建占位提案、preview 或“默认通过”的 review。

同一 decisions 接口的两种目标严格互斥：

| 目标 | 必须带的目标字段 | 允许决定 | 禁止字段/效果 |
|---|---|---|---|
| 当前提案 | `proposal_id` + `proposal_version` | 原有四种决定，分别遵守原守卫 | 不带 `processing_failure_id`；仅 APPROVE 可带 preview/fingerprint 并产生审批 |
| 当前无提案技术失败 | `processing_failure_id` | 仅 `MANUAL_HANDLING` | 不带 proposal ID/version、preview、scope fingerprint 或 approval；绝不派发 return/label |

两类请求都需要 `expected_case_version`、理由和已验证 Founder 身份。记录同样保留互斥目标；失败目标的记录不能出现 `approval_id`。服务端必须加载权威案件，检查 `ESCALATED`、确无当前提案、请求版本、失败 ID 的归属和当前 input/failure 一致；旧失败、另一案件失败或客户端任意拼出的 ID 不因 Schema 合法而可受理。

人工处理记录与通知遵守同一幂等、审计和独立通知规则：结果保存后发送客户消息，失败可仅重试通知，成功后才为 `MANUAL_HANDLED`。没有执行模拟退运，也不记为 `COMPLETED`。这是既有人工故障恢复分支的数据交接补齐，不增加业务角色、决定枚举、HTTP 路由或新功能；运行守卫仍属 A1/A2 后续实现。

### 8.2 操作与通知恢复

provider 明确失败与模糊超时不同：后者为 `UNKNOWN → RECONCILING`，先查询核实，不能直接重派。`reconcile` 只触发核实；确定未产生效果后若确需安全重试，仍走当前审批、provider 权限与幂等守卫。

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

p50/p95 只对成功测量子集计算，不把它当全系统成功率；`sample_count=0` 时省略两值，不填假 0。展示失败与未测量计数及分母。评测运行另保留 input/model/corpus/environment 版本、token、费用和失败分母，不能仅靠 Dashboard 汇总证明 NFR-005。

### 10.3 审计内容

审计事件包含相关 ID、case version、组件版本、对象引用及 hash，不放原始附件/token/完整个人内容。首事件省略 previous hash；完整链编码、持久化、脱敏后仍可核验等属于 F.05/F.07，而非本轮实现。

## 11. 验证证据与不能得出的结论

2026-09-07 对 rc.2 当前文件重新验证：独立验证环境的 **35 项契约 unittest 全部通过**；包含旧领域模型 4 项检查的完整本地 pytest 为 **39 passed**。本轮还用 JavaScript 引擎编译全部 8 个 Schema 正则，并对 7 类严格端锚执行 35 个尾随换行负例检查，均通过。发布状态同步后的文档检查覆盖 15 个文件、15 个 Mermaid 块和 94 个本地文件链接，均无错误；这只是语法与链接检查，不是 UML 语义或课程评分验收。

以上不沿用 rc.1 的历史通过数。没有 HTTP/E2E、数据库、真实 AI 或 provider 实现。文件已上传 PR #9，但上传本身不会产生 GitHub CI 通过结果或 Jira 验收记录。后续修改后须重新运行，不能把本次结果套用到未测版本。

`examples.json` 目前围绕少量合成素材提供 56 个合法 DTO、24 个非法结构和 8 个未执行的运行时守卫情境。它们不是业务测试案件总数，更不是 Gold 标签、真实用户或实验结果；没有扩写被冻结的研究库或 30 Gold 计划。

本轮自动检查：

- JSON Schema 定义、全部本地引用与 OpenAPI 3.1 结构；
- 合法 DTO 可校验，非法字段/金额/枚举/角色元数据/执行命令组合被拒绝；
- 公共操作的角色声明、幂等键、相关 ID、版本前置条件及请求/响应样例对应；
- 示例中的订单多商品、单 parcel、来源 hash、审批/操作指纹与版本引用一致；
- 日期 format 检查真实启用，而非只检查字符串类型；
- rc.2 的互斥决定目标、完整 retrieval_result、容量边界、统计 query/未测量分支，以及 ID 换行/控制字符负例。

`runtime_guards` 中旧版本、过期、改指纹、升级、错角色、同 key 改请求等请求 **本身都符合 JSON 格式**。测试只核对情境和错误响应的结构；即使补了当前失败 ID、引用交接和统计一致性的样例检查，也不能证明真实服务已加载正确案件/输入、执行过状态守卫、保留全部冲突或正确聚合数据库。没有发 HTTP、调用 provider、证明零副作用或完成 Gate 1。

旧四项领域模型测试通过也不代表旧代码已经匹配本契约。A1.01 后续需迁移 float money、单商品字段、旧 Agent/DecisionProposal 词汇、缺失 proposal version/精确 scope 的审批模型；这次保持原文件不动以免跨过第一步。

## 12. 需求 → 模型 → 下一项实现

| 契约部分 | Requirement / UC | 模型对齐入口（已发布 PR #9；rc.2 需联合确认） | 后续 Owner |
|---|---|---|---|
| statement、facts、case、clarification | FR-001～005 / UC-01、UC-01E、UC-02 | [共享类图](diagrams/01-domain-class-diagram.md)、[用例图](diagrams/05-use-case-diagram.md)；B intake 个人链 | A1、B1 |
| passage、citation、packet、risk | FR-006～008 / UC-02、UC-03 | 共享类图、[交互图](diagrams/03-sequence-diagram.md)；C review 个人链 | A1、C1/C2 |
| processing_failure、preview、decision、approval、command | FR-009～012 / UC-03、UC-04、UC-05 | 无提案技术失败人工分支需联合确认；Approval/Execution 活动与交互；A OperationAttempt 状态机 | A1/A2、B2 |
| operation、notification | FR-010～012 / UC-04、UC-05 | [状态图](diagrams/02-state-machine-diagram.md)、交互图的核实/通知分支 | A2、B2 |
| auth、attachment、audit、analytics | FR-001、009、011、012 / NFR-001～003、005～009 | 共享 Class/Package/Deployment、Audit Port；待共享建模验收 | A 的 F 系列；B/C 消费 |
| sandbox、image、analytics UI | OF-004、OF-001、OF-006 | 对应 docs/07 冻结的三个人 optional 增量 | A3、C3、B3 |

上轮已对齐旧正文与五张共享图，但这不等于本次新字段已获模型验收；三人需核对无提案人工路径、检索冲突交接与统计数据选择是否逐项对应。UML 仍是课程交付物；机器 Schema 不能替代类图、复合结构图或每人的活动/顺序/状态机图。每次实现 PR 应使用表中具体映射，而非只贴“FR 全部覆盖”。

## 13. rc.1 → rc.2：五项缺口修订与迁移

| 修订 | rc.2 的约定 | 消费方迁移 / 仍须验证 |
|---|---|---|
| 无提案技术失败无法记录人工结果 | ProcessingFailure、CaseView 故障分支与互斥 Founder decision target | B 不再伪造提案；A 加载当前 case/input/failure 并校验状态、审计和通知；不存在失败目标执行权限 |
| 检索冲突在 C2 输入中丢失 | 必填完整 retrieval_result，删除旧顶层 passages | A/C 一起替换调用与 mock；保留 conflicts，逐条验证来源和引用，C2 负责语义 |
| 20 条检索容量与 100 条引用不相容 | passage/citation/check/read-model 容量上限对齐 100 | 校验边界与引用覆盖；不要求取满，不改 Gold/技术栈 |
| 统计缺筛选和明确分母 | AnalyticsQuery、filters、unmeasured_count，同 cohort/as_of 及当前输入 episode | B 更新 query 和展示；A 实现时间顺序、去重及聚合；C 核对指标，不把成功子集当全部案件 |
| ID 允许尾随换行等非法值 | 更严格的完整 ASCII ID 边界 | 更新边界负例；运行接口仍须实际启用验证，ID 合法不等于有权限 |

这是尚未正式采纳的 rc 间迁移，不假装无缝兼容：旧 RiskReviewRequest、旧 AnalyticsSnapshot 必须更新，严格客户端也要认识新的 CaseView/decision 分支。URL `/v1`、13 个公共操作、五风险结果、四人工决定及固定九功能保持不变；旧提案目标的四种决定语义保留。统一更新 mock/消费代码后共同采纳 rc.2，不在一个进程里混用 rc.1 与 rc.2 形状。修好 Schema 的表达能力不代表修好了尚未实现的运行服务。

## 14. 三人确认后才验收 F.01

- [ ] A：确认唯一状态源、版本/幂等、scope 指纹、商品与 parcel 关联，以及当前 failure 绑定、引用全覆盖和统计对账的运行守卫责任。
- [ ] B：确认提交/澄清、引用原文、四种决定、无提案人工分支、202/409/未知结果、统计筛选/分母足以支撑页面；确认附件技术限制。
- [ ] C：确认来源无版本/合成来源、完整 retrieval_result 与 conflicts、引用核验容量、独立 Risk 输入、五种结果、计时口径和 C3 交接；完成指定 Reviewer 审查。
- [ ] 三人联合确认 PR #9 中的模型与 rc.2 字段/异常分支的对应，区分结构检查、运行验证和课程个人模型验收。
- [ ] 三人确认后记录契约采纳版本及 PR review 证据；C 核对实际 Jira key 并建立链接，不虚构同意、进度或日期。

下一步是 **B/C 确认这份交接约定**。期间 A 可继续无开始依赖的 F.02 准备；A1.01 的正式对齐应等 F.01 验收。不是重新讨论九功能分工，也不是立刻把 LLM 接进执行路径。

规范依据：[OpenAPI 3.1.0](https://spec.openapis.org/oas/v3.1.0.html)、[JSON Schema 对象与额外字段](https://json-schema.org/understanding-json-schema/reference/object)。项目的权限、审批、免费模拟和贡献边界来自 docs/00 与 docs/07，而非这些通用规范。
