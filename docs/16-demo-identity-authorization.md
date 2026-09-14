# F.03：演示身份与资源授权设计候选

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> 版本：F03-D0.2，2026-09-07；**准备文档，未实现、未集成、未验收**。Owner A，Reviewer C；B 确认浏览器消费和错误反馈。沿用 [WBS](08-delivery-work-packages.md) 的 **S=F.01、F=F.02**；本稿不解除开始依赖，不新增 WBS 主项或猜测 Jira key。
>
> 依据：[产品定义](00-project-definition-v1.md)、[固定分工](07-frozen-work-allocation.md)、[F.01 rc.5](09-interface-contract-v1.md)、[OpenAPI](../contracts/v1/openapi.json) 和 [Schema](../contracts/v1/schemas.json)。下文区分已有契约与内部演示设计提议；没有修改十五个公共操作、DTO 或请求 header。

## 1. 版本与当前证据

2026-09-07 **11:55 UTC** 只读核验：[PR #11](https://github.com/shuxiachai/returnops-au/pull/11) 为 OPEN、非 Draft、CLEAN，head 为 `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577`；B/C 已被请求评审，提交的 reviews 仍为空。main 为 `9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf`。该已发布 head 收录 rc.4；本地 rc.5/F03-D0.2 尚未发布，旧 run 不覆盖本次删除后回执规则。后续以 PR 实际 head、reviews 和 run 为准。

[PR run](https://github.com/shuxiachai/returnops-au/actions/runs/34117330147) 与 [push run](https://github.com/shuxiachai/returnops-au/actions/runs/34117330053) 的四个 job 均成功；它们验证 F.02 环境和离线契约/模型，不验证 F.03。PR run 的合成 merge checkout 为 `5650601d24c8f109237dea91b3b45cab63bc0e3d`，与关联的 PR head 不同。当前健康 API 的两个路由不属于以下十五个 `/v1` 业务操作，也不能充作鉴权端点。

## 2. 已有约定与身份来源

- OpenAPI 全局 `bearerAuth` 为 HTTP Bearer、JWT 格式。`GET /v1/session` 只返回已验证的 `Principal {principal_id, role}`，不是登录、token 签发或角色切换接口。业务角色只有 `CUSTOMER`、`FOUNDER`；成员 A/B/C、MODEL、SERVICE 不是额外可登录角色。
- 请求正文不能提交可信 principal、owner、role、`ApprovalRecord` 或任意命令。已关闭额外属性的 DTO 应拒绝这些字段；客户原文、附件、来源文本或 LLM 输出中的角色声明永不参与授权。
- F.03 提供认证结果和可复用的角色/归属判断；Domain Service 仍是业务状态的唯一写入者。请求经过 API 的身份检查后进入 [CS D01](13-shared-composite-structure.md)，Domain 再核验当前资源关联、状态和版本。API 不新增一条直写 CaseRepository 的路径。

**内部演示方案提议，待 A/C 审阅、B 确认使用方式：**

1. 通过受控的本机管理流程建立一个演示 Founder 和至少两个合成客户。账户 ID 与角色来自服务器管理的身份登记；角色不能由 Web 请求、URL 参数或界面选择创建。bootstrap 不公开 HTTP 路由，不读真实身份目录；命令名称及私有配置格式待实现时确定。
2. 使用成熟 JWT 库验证签名，并在服务器固定允许算法、签发者和受众；不采用 token 自报算法选择、不接受 `none` 或其他系统的 token。签名验证后仍核对 subject 对应的当前登记、启用状态及角色。不存在或已停用的身份不得继续使用旧 token。密钥从私有部署配置注入，不硬编码、不放镜像或普通日志。该方向沿用 [RFC 8725 §3](https://www.rfc-editor.org/rfc/rfc8725.html#section-3) 的算法、签发者、受众及声明验证原则；具体库和版本需另行锁定。
3. 建议使用短期 JWT 和服务端会话登记：校验 `exp/nbf/iat`、有限时钟偏差及会话撤销状态；有效期、算法/密钥轮换、会话登记的持久化策略在实现评审中确定并形成边界测试。本稿不编造已冻结的 JWT claim 值或数据库表。服务器重启不得通过默认身份绕过失效的会话登记。
4. bootstrap 只向对应演示参与者安全交付其 token，不向浏览器打包全部用户凭据，不在公开角色选择器中提供 Founder token。浏览器候选方案将 token 保存在内存、显式发送现有 `Authorization: Bearer ...`；刷新后重新取得合法演示会话。持久浏览器存储、公开注册、刷新/退出端点均不是本稿增加的接口。
5. 会话过期阻断新的 HTTP 请求及后续翻页；它不删除历史批准或审计。后台工作不转存、重放原始 bearer token，而按 A2 规则读取已保存的批准及当前主体权限、审批 expiry、案件和 provider 守卫。会话 expiry 与 `ApprovalRecord` expiry 不是同一概念；停用主体后的新派发必须被当前权限检查阻断。

## 3. 十五个操作的权限矩阵

假设请求满足基础语法，且目标资源存在、可用；允许项仍须通过正文、状态、版本和幂等守卫。`客户甲` 是目标案件/附件的合法所有者，`客户乙` 是另一已验证客户。没有目标资源的 session/upload/create 操作分别按调用者自身作用域解释，不得替另一客户指定 owner。

`401`=`UNAUTHENTICATED`；`403`=`FORBIDDEN`（角色不符，先于资源查找）；`404`=`NOT_FOUND`（资源不存在或不允许该主体访问，使用同一安全响应）。Founder 的允许项仅覆盖本演示商店获授权的资源，绝非任意 ID 的通行证。

| operationId | 方法 / 精确路径 | 匿名或无效会话 | 客户甲：自己的资源 | 客户乙：他人的资源 | 已验证 Founder |
|---|---|---|---|---|---|
| getSession | GET `/v1/session` | 401 | 200，仅甲 Principal | 200，仅乙 Principal | 200，仅 Founder Principal |
| stageEvidence | POST `/v1/evidence` | 401 | 201，仅甲私有 STAGED | 201，仅乙新建私有 STAGED | 403 |
| getEvidenceContent | GET `/v1/evidence/{evidence_id}/content` | 401 | 200，自己的合格附件 | 404 | 200，仅获授权案件关联的附件；他人的未绑定 STAGED 为 404 |
| createCase | POST `/v1/cases` | 401 | 201，创建甲的案件 | 201，只能创建乙的案件；引用甲附件为 404 | 403 |
| getCustomerCase | GET `/v1/cases/{case_id}` | 401 | 200，CustomerCaseView | 404 | 403 |
| listCustomerCaseHistory | GET `/v1/cases/{case_id}/history` | 401 | 200，CustomerHistoryPage | 404 | 403 |
| submitClarification | POST `/v1/cases/{case_id}/clarifications` | 401 | 202，限当前澄清 | 404 | 403 |
| listFounderCases | GET `/v1/founder/cases` | 401 | 403 | 403 | 200，授权商店的 CaseList |
| getFounderCase | GET `/v1/founder/cases/{case_id}` | 401 | 403 | 403 | 200，授权案件的 CaseView |
| listFounderCaseHistory | GET `/v1/founder/cases/{case_id}/history` | 401 | 403 | 403 | 200，授权案件的 FounderHistoryPage |
| recordFounderDecision | POST `/v1/founder/cases/{case_id}/decisions` | 401 | 403 | 403 | 202，接受合法决定；不等于执行成功 |
| reconcileOperation | POST `/v1/founder/operations/{operation_id}/reconcile` | 401 | 403 | 403 | 202，解析 operation 的所属案件后授权；仅受控核实 |
| retryNotification | POST `/v1/founder/notifications/{notification_id}/retry` | 401 | 403 | 403 | 202，解析 notification 的所属案件后授权；仅通知重试 |
| listCaseAudit | GET `/v1/founder/cases/{case_id}/audit` | 401 | 403 | 403 | 200，授权案件的脱敏 AuditPage |
| getFounderAnalytics | GET `/v1/founder/analytics` | 401 | 403 | 403 | 200，同一授权商店、合法筛选的 AnalyticsSnapshot |

这不是“Founder 继承客户所有 API”的角色层级。Founder 查看案件使用 `/v1/founder/...`；客户专属 create/clarification/history 接口仍拒绝 Founder。没有公开执行、AI 回写、任意下载 URL、角色自选登录或第三种业务角色。

## 4. 资源归属、关联与副作用边界

**内部可信关系。** 服务端需要维护 principal 的角色/启用状态、case→customer、STAGED evidence→uploader、BOUND evidence→case，以及 operation/notification/decision/proposal→case。具体字段/存储布局是内部实现候选，不添加到现有请求 DTO；公开 EvidenceAttachment 没有 owner 字段不能被解释成“不需要保存 owner”。订单号、ID 前缀、文件名、客户端传来的 case_id 或已解码 JWT 内容不证明归属。

**附件。** F.04 上传成功只产生调用者私有的 STAGED 记录；客户可读取自己的合格 STAGED 或 BOUND 内容。create/clarification 由 Domain 与受控附件边界原子检查所有者、到期/删除状态及兼容绑定，失败时不能留下半绑定。Founder 只能通过获授权 case 读取 BOUND 附件，不能浏览客户尚未提交的 STAGED 内容。系统生成的 label 由其案件关系授权；其内部来源/归属表示需在 F.04 说明，不伪造客户上传。下载保留已有 `Cache-Control: no-store`，不暴露存储密钥；C3 通过 A 提供的限定 evidence ID 内部 port 消费数据，不接收用户 bearer token 或任意路径/URL。

**所有权不是业务许可。** 自己的案件只在 `AWAITING_INFORMATION`、当前 question_set、expected_case_version 等守卫满足时接受 clarification；STAGED 上传不新增审查后的任意追加/重开入口。Founder 决定保留 rc.5 的三种互斥目标；技术失败和 pre-proposal `OrderLookupBlock` 只能 MANUAL_HANDLING，不能通过认证成功创造批准或 return/label 工作。

**查找顺序。** 先确认身份和操作角色，再通过受限资源查询取得案件上下文；同角色的不存在/不可访问资源统一 404，不能先向越权者显示状态/版本差异。资源已授权后，正文引用不属于当前 case/input 的 proposal、failure、order block 等按已有守卫返回 409 `INVALID_STATE`（或适用的已定义 stale code），不返回另一个案件的信息。operations/notifications 路由没有 case 参数，必须从权威记录解析 case；不能让正文另选 case。新写入在事务中复核关联、版本和权限，避免先检查后使用过时记录。

**幂等与日志。** 所有 POST 仍使用现有 `Idempotency-Key`；按已验证 principal、operation、被寻址资源及规范请求指纹隔离。每次重放先重新认证/授权，再查原受理记录；同 key/同请求复用接受事实，即使状态已推进，也不能当新请求重复执行。仅当回执正文仍全部可读时返回原结果；若正文已按保留规则移除，按 rc.5 返回 409 `INVALID_STATE`、`retryable=false`，只说明此前已受理、回执不可用并引导 GET 当前案件/历史，不能回放原文、重调度或自动换 key。同 key/不同请求仍为 409 `IDEMPOTENCY_CONFLICT`。不同主体不得命中对方回执。最小受理记录保留作用域/指纹/受理事实/资源与工作 ID/可用性，不保留去重不需要的原文；正文清理与回执失效协调，不能删掉去重记录导致旧 key 重新执行。安全拒绝不产生业务状态/附件绑定/批准/provider 效果；只记录必要的脱敏安全诊断和 correlation ID。Domain 根据可信上下文写 `ActorProvenance`，不采用客户端 actor。

## 5. history、分页与内容保留

- 每页重新执行身份、角色及案件授权。客户只取得 `STATEMENT/EVIDENCE/OUTCOME_MESSAGE`；消息须已 SENT 且为安全客户投影。不得下发 FounderHistoryRecord、actor、proposal、Risk、ApprovalRecord 或完整 NotificationRecord 后靠 UI 隐藏。Founder 仍只读获授权案件的严格类型材料。
- history cursor 按已有 rc.5 约定绑定 principal、role、case、kind、object filters、limit、snapshot 和最后稳定键；签名或服务器登记必须验证。不能信任裸 base64。客户角色在自己路由请求 Founder 专属 kind 属于 422 `VALIDATION_ERROR`；直接请求 Founder 路由为 403。
- 已授权案件上的跨主体/角色/案件/类型游标、篡改、筛选/limit 改动和快照过期为 409 `INVALID_STATE`；无权案件仍先 404，错误角色仍先 403，过期会话仍先 401。首请求无 cursor；后续重复查询参数；`object_version` 缺少 `object_id` 为 422。不静默换快照。
- `collection_windows.start_cursor` 从该视图 snapshot 的完整 kind 开始、默认 limit=20；不能接在最多 100 条预览尾部。预览不完整不能证明没有 UNKNOWN 效果。新记录/状态更新不混入旧快照；授权变化和允许的内容删除仍即时生效。
- 被移除正文在既有快照中也只能呈现合规 tombstone；附件下载、旧 bundle、缓存和当前投影一致禁止恢复正文。精确 object 过滤只能查已授权 case 内的对象；不能根据外部 object ID 去全局搜索并泄露存在性。具体无匹配筛选返回空页的细节见下方待确认项。
- Founder 列表与 audit cursor 也绑定主体、操作及查询作用域；audit 再绑定 case。它们沿用各自响应 Schema，不被强制改成 HistoryPage；其稳定分页的内部实现可复用，但不新增公开 cursor 字段。统计只能聚合当前 Founder 获授权的同一商店数据。

## 6. 浏览器会话、CSRF 与 CORS

**候选部署方式：** 优先让 B 的 UI 通过同源应用入口调用 API；确需不同开发 origin 时逐项配置精确 allowlist，不反射任意 Origin，不使用通配 origin 或 `null`。允许现有 Authorization、Content-Type、Idempotency-Key 请求头；若 B 要读取相关 ID，暴露已有响应 `X-Correlation-ID`。这些是部署策略提议，不新增 F.01 自定义 header。预检 OPTIONS 可不带 bearer，但只返回允许的传输元数据，不能返回会话或资源；实际十五个操作仍独立认证。

当前候选只接受显式 Authorization bearer，不把 cookie、URL token 或浏览器自动携带的身份当作等价入口。这样跨站表单不能仅借浏览器自动附带 cookie 取得权限；CORS 仍不是身份认证，也不能阻止持有有效 token 的非浏览器客户端。XSS/泄露 token 仍需通过转义、依赖和数据流控制防御，不宣称“使用 JWT 即无 CSRF/XSS”。依据 [OWASP REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html#cors) 与 [CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)。

若以后选择 HttpOnly cookie、BFF 或持久浏览器会话，必须先由 A/B/C 明确 CSRF token、Origin/Referer 检查、SameSite/Secure、退出/轮换和跨站传输规则，必要时修订契约；本稿不预先规定一个不存在的 CSRF header 或 cookie 名。远程演示使用 HTTPS；当前 loopback HTTP 环境证据不等于公网身份服务验收。

## 7. 错误契约与可复用负向场景

沿用 `ErrorEnvelope` 和响应 `X-Correlation-ID`，两处 ID 一致；拒绝消息/details 不回显 token、用户目录、foreign case 状态、完整附件或堆栈。身份失败 401；角色失败 403；资源缺失/越权/到期删除 404；可解析但不符 DTO 为 422；已授权对象的状态/版本/游标/幂等冲突为对应 409。上传单独沿用 400/413/415；503 依赖故障不默认放行。F.03 角色拒绝优先用 `FORBIDDEN`，不把普通 RBAC 失败伪造成订单/provider 的业务 `AUTHORITY_DENIED`。

下列编号是本稿测试场景标签，不是新增 WBS。用动态生成的测试密钥/token、两个客户和单一 Founder、至少两案及分别绑定的资源参数化；不使用真实凭据。组件 doubles、未来真实 HTTP/数据库结果分别记录。

| 场景 | 输入/扰动 | 预期证据与主要追踪 |
|---|---|---|
| AUTH-01 | 对十五个操作逐一省略 token、使用坏签名/过期/错误 issuer/audience/未启用 subject/撤销会话 | 全部 401；无资源或业务效果；FR-009，NFR-002/009 |
| AUTH-02 | CUSTOMER 调每个 Founder 操作；Founder 调每个 CUSTOMER-only 操作；body/query/文本伪造 role/actor | 按矩阵 403；合法角色请求里的额外 DTO 属性 422；不生成可信 principal/approval；FR-009，NFR-002/006/009 |
| AUTH-03 | 客户乙替换客户甲 case/evidence ID，分别用真实 ID 和不存在 ID | 同一 404 结构；无甲的内容、状态、计数或绑定泄露；FR-001/005/012，NFR-003 |
| AUTH-04 | 将外人、已删除/过期、冲突绑定的 evidence 放入 create/clarification；Founder 读他人 STAGED | 资源不可访问 404；自己已获授权但绑定状态冲突 409；无半绑定/新案残留；FR-001/005，NFR-003/004 |
| AUTH-05 | operation/notification ID 改指另一案或不可访问资源；伪造正文 case/actor | 先按资源授权拒绝或拒绝额外字段；expected_case_version 只能约束解析出的所属案；无任意执行或改收件人；FR-009/010/011 |
| AUTH-06 | 已授权案件使用跨案/旧 proposal、failure、order-block；非提案目标尝试 APPROVE/REQUEST_REVISION | 格式错误 422 或合法结构下适用 409；零批准/操作；FR-009，NFR-002 |
| AUTH-07 | 不同 principal 复用 key；相同主体同 key 同/异正文；接受后会话/资源权限撤销再重放 | 回执隔离；同请求无重复效果；改请求 409；撤销后不绕过 401/403/404；FR-001/009/010，NFR-004 |
| AUTH-08 | 客户 history 中尝试 Founder kind、投影属性注入；直接读 Founder detail/audit/analytics | 422/403；成功 CustomerHistoryPage 无 Founder 内容/actor；FR-011/012，NFR-003/009 |
| AUTH-09 | cursor 跨 principal/role/case/kind、改 object/limit、篡改、过期、仅 object_version | 按身份→角色→资源→cursor 顺序拒绝；授权范围内无效 cursor 409、非法 query 422；FR-011/012，NFR-001/003 |
| AUTH-10 | 101+ 历史记录；翻页间追加、状态更新、撤权、删除；从 start_cursor 读取 | 无重复/漏项/换快照；每页再鉴权；移除后仅 tombstone，旧附件路径不恢复内容；FR-011/012，NFR-003/004 |
| AUTH-11 | 跨站表单/JS、未允许或 null Origin、带 cookie 不带 bearer、匿名预检后实际调用 | 预检不授予身份；实际资源不得凭环境 cookie 获权；B 显示安全失败；FR-009/012，NFR-003/009 |
| AUTH-12 | 认证通过后更改 owner/身份启用状态；业务提交/派发前再次核验；检查日志 | 新效果被当前守卫阻断；历史事实保留；日志无 token/原附件；FR-009/010/011，NFR-002/003/008 |

| AUTH-13 | 已接受的 clarification 回执包含原陈述；允许删除该陈述后，同主体同 key/正文重放，并并发读取旧缓存 | 409 INVALID_STATE、retryable=false；无已删正文、零新写入/调度；保留去重事实，B 读当前案件/历史且不自动换 key；FR-001/011/012，NFR-003/004 |

## 8. 交付与待确认

模型定位：[共享类图](diagrams/01-domain-class-diagram.md) 的可信上下文与领域写入边界、[共享交互图](diagrams/03-sequence-diagram.md) 的客户/Founder 请求、[MA-0.3 G-REQUEST/G-DISPATCH](12-member-a-model-chain.md)、[CS-0.2 D01/D02/D13](13-shared-composite-structure.md)。F.03 补的是进入这些边界前及每次资源使用时的身份/授权；不是新增 AI 角色或已完成的个人 UML。Package/Deployment 的验收仍单独记录。

| 待确认事项 | 负责人 / 需要的可审阅结果 |
|---|---|
| 当前契约认可与版本 | A/C、B：在 rc.5 未来实际提交上确认矩阵、删除后回执错误和权限边界；PR 成功不替代 F.01 接受 |
| JWT/会话与 bootstrap | A 提供算法、库/锁、有效期/时钟偏差、issuer/audience、轮换/撤销、失败启动和私有分发方案；C 审阅；B 实测浏览器消费。均为内部 demo 选择，不是公开角色选择入口 |
| 无匹配历史 object 筛选 | 候选为授权 case 内无匹配返回 200 空页，绝不查找/透露外案对象；现有 Schema 可表达，但确切语义需 A/B/C 与 F.01 一起确认，不自行增新错误码 |
| 资源映射与竞态 | A 为 F.03/F.04/A1/A2 定义窄内部权限查询和原子复核；保持 Domain 唯一业务写入，系统 label 的案件关联明确；C 审阅、B 消费 |
| 单元与后续集成证据 | F.01 接受后按原 S 开始集成实现；组件测试可用合成资源解析 doubles，不能称十五条业务 API 已接通。真实路由/数据库/浏览器接入由原工作包分别补证；F.02 完成依赖及原 F.03 验收仍须满足 |

本稿可供 A/C/B 评审和准备测试输入；没有签发真实会话、访问身份接口、读取 .env/token、实现认证/授权、改变 WBS 依赖或更新 Jira。下一次实现应引用具体 FR/NFR、上述 UML 入口与对应 AUTH 场景，而非笼统声明“鉴权已完成”。
