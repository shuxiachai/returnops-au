# A 的接口与模型设计决定包

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> `AD-0.2`，2026-09-07；AI 辅助准备的**具体方案修正候选，等待 A 本人解释及 B/C 对应评审**。用户授权修正缺陷，不等于认可下面每个技术选择。
> 主项 F.01 / [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)，个人规格 M-A.01 / [KAN-13](https://lucastaooo.atlassian.net/browse/KAN-13)；Owner A，Reviewer C，影响 UI/公共消费语义由 B 确认。两项原 S/F 均无；其他工作包依赖不变。
> `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577` 的 rc.4、MA-0.2、CS-0.1 是历史发布依据；当前本地 rc.5 / MA-0.3 / CS-0.2 修正标签成功观察及制品恢复的语义，wire shape 保持不变。1-based 序号等推荐仍未采纳；无业务实现或人审接受。

## 1. 读完后需要作出的决定

本包将 [MA 未决项](12-member-a-model-chain.md#7-明确提出的设计选择与待确认点)和 [CS 未决项](13-shared-composite-structure.md#5-设计选择未决项与具体贡献)变成可比较的方案、反例与验收任务。既有 [产品边界](00-project-definition-v1.md)、[分工](07-frozen-work-allocation.md)、[依赖](08-delivery-work-packages.md)及 [rc.5 契约](09-interface-contract-v1.md)继续有效。

| 项目 | 本包推荐候选 | 处置状态 |
|---|---|---|
| MA-D01 / MA-Q01 | 每次尝试一个不可复用的 ID；`attempt_count` 采用同一 command 内从 1 开始、创建后不变的尝试序号 | 方案已写明；公共计数语义仍待 A/B/C 评审及版本处置 |
| MA-D02 | 查询只改变原尝试阶段；独立查询次数和 claim 不混入公开尝试序号 | 与现图一致的细化候选；阈值、预算及运行证明后续处理 |
| MA-Q02 | 当前版本不自动跨批准续派；旧成功/未知效果保留，旧批准过期仍可授权查询 | 保留现有禁止边界；跨批准恢复能力没有被宣布完成或取消 |
| MA-Q03 | 以案件级串行化、持久化意图、稳定效果身份及 provider 防重共同约束派发 | 运行设计候选；最终调用时点与故障竞争证明仍是 A2 的未决验收项 |
| CS-D01 | 确定性包装保留原始来源 receipt，经 Domain 接受再进入独立 Risk | A/C 待审；无新增公共 DTO |
| CS-D02 | Domain 使用同一工作单元提交业务事实、必要审计与待办 | A/C 待审；不引入第二状态库或新增消息中间件 |
| CS-D03 / CS-Q01 | 每一逻辑工作固定一套 provider 配置；结构化分组映射现有模块职责 | 映射见 [Package/Deployment](15-package-deployment-models.md)，不按 part 数量强制分进程 |
| CS-Q02 | 图片只读与标签写入采用不同的内部受控上下文 | A/C 待审，B 确认附件消费；公开附件契约不变 |

“方案已写明”只表示评审问题已具体化。F.01 接受、M-A.01 的本人贡献、C review、运行安全证明分别记录，不能合成一个勾选。

## 2. 尝试身份与计数：MA-D01 / MA-Q01

### 推荐映射

| 概念 | rc.5 wire 字段（shape 沿用 rc.4） | AD-0.2 候选语义 |
|---|---|---|
| 共享类 `attempt_id` | `operation_id` | 同一对象的概念名与 wire 名；不生成两套 ID |
| 共享类 `attempt_number` | `attempt_count` | 同一 `command_id` 下按创建顺序分配的 1-based 序号；该对象状态改变后序号不变 |
| 一次业务命令 | `command_id` | 同一原批准内重试继续引用同一 command；不用于身份授权 |
| 外部效果防重身份 | 持久化 `idempotency_key`，并绑定 provider/config | 新尝试 ID 不产生新效果 key；禁止为绕过 UNKNOWN 而换 key |
| 具体授权参数绑定 | `operation_fingerprint` | rc.5 沿用 rc.4 对 `{approval_id, scope_fingerprint, command}` 的 hash；同原批准/原命令不变 |

创建 PENDING 就消耗一个序号；之后若确定未调用而 BLOCKED，序号仍保留。因此它**不是实际网络调用次数**。恢复查询不消耗新尝试序号。调用次数、查询次数、拒绝次数需要通过不同的内部事件统计；不能将 `attempt_count - 1` 自动报告为实际重试次数。`NotificationRecord.attempt_count` 属于另一个 DTO，本包不改变其送达计数语义。

候选的事务约束：在案件/command 的权威写入上下文内分配序号，唯一约束保护 `(command_id, attempt_number)`；同一 logical effect 不能存在另一个活跃或未知尝试。序号不得回收，失败事务不被报告为已创建尝试。FAILED/BLOCKED 对原对象终结，允许重试时另建新 `operation_id`；查询无结论仍留在原对象。

示例仅作设计走查，不是正式 Gold 或已运行 API：

| 事件 | ID / 序号 | 保持的身份与效果 |
|---|---|---|
| command-return-001 创建第一次意图 | operation-return-001 / 1 | 原 approval、command、provider key、fingerprint |
| 调用结果不明，随后查询三次 | 仍 operation-return-001 / 1 | UNKNOWN ↔ RECONCILING；不产生新效果身份 |
| provider 有权威证据证明未执行，且原批准仍有效 | 旧尝试 FAILED；新 operation-return-002 / 2 | 同 command、原 provider key、原 fingerprint，再走完整守卫 |
| 第一次已成功，只是 label 失败 | return 的旧成功保留 | label 是另一 command 的尝试序列；不重做 return |

**兼容性处置：**rc.5 延续 rc.4 的 Schema，仍接受 `attempt_count=0`，并未规定上述序号解释。现有 `operation-unknown/reconciling/success` 样例都为 1，不能据此声称 1-based 是已冻结规则。若 A/B/C 接受本候选，须在同一次 F.01 修订中更新说明、共享类映射、Schema 最小值/样例与边界检查，按版本规则发布下一 rc；拒绝 0 属于验证语义收紧。本轮不收紧该计数 shape，也不把仅通过 Schema 的 0 当作运行合法证明。

未选方案：复用一个 OperationAttempt 并递增“重试次数”会丢失独立尝试终态，和当前一 command 多 attempt 的类关系/状态机不一致；将序号混作 provider 调用计数会让 PENDING/BLOCKED 和查询统计产生歧义。若团队选择它，需明确模型与契约迁移，不能同时保留两种解释。

## 3. UNKNOWN 与查询：MA-D02

执行 claim 和查询 claim 是内部持久化协调信息，不是新公开字段。它们至少绑定原 operation、可信工作身份、当前版本、有效期及 fencing/代次；具体列名和时间参数在 A1.02/A2.04–.05 实现前落实。

1. 先读可信的效果确认 receipt：存在原标签确认事实时，按第 6 节保持 EXECUTING 并恢复制品，不因 worker 失联或 lease 到期改为 UNKNOWN。没有确认事实的旧 EXECUTING 意图才在原 claim 不再活跃时，以版本条件保存 UNKNOWN；写入失败只报告最后持久化状态。
2. 对 UNKNOWN 获取独立查询 claim 并保存 RECONCILING 后，才用原 provider ID / 原 fingerprint 查询。只有一个查询 worker 获得该资格。
3. 查询权威成功：同一原尝试保存确认事实及审计；完整 CREATE_RETURN 结果可以 SUCCEEDED，标签缺制品则先保存 receipt、artifact-only 工作与 EXECUTING，不能发布缺 label_evidence_id 的结果。查询明确证明没有效果且没有仍可能完成的旧调用：记录 FAILED；新尝试另经 G-RETRY/G-DISPATCH。
4. 暂不可见、普通 NOT_FOUND、查询失败或不能排除仍在执行：回 UNKNOWN。不能把“本轮查不到”转换成“可以再创建”。
5. 查询 claim 失联按同样版本规则恢复；迟到 worker 不能覆盖新事实。停止自动查询或升级案件后，UNKNOWN 历史保留，可由授权 Founder 请求后续核实。

查旧事实与批准新效果分开。旧批准过期不阻止有独立权限的历史查询；也不因 `reconcile` 请求被 202 受理就获得新的执行授权。已接受 MANUAL_HANDLED/REJECTED outcome 时，查询只补旧事实和审计，通知与案件结果保持原义。

## 4. 新批准遇到旧效果：MA-Q02

本版本的推荐保守路径是**禁止自动跨批准续派**。这不是删除恢复需求；先完成同原批准的可证明安全恢复，跨批准的自动映射继续保留明确待决项。

| 原逻辑效果事实 | 新批准/重新生成提案时的处理候选 |
|---|---|
| 旧效果成功 | 保留事实；不能以新 approval_id、新 command_id 或换 provider 再做同一效果；label 不能私自重绑别的 return |
| EXECUTING、UNKNOWN、RECONCILING 或本地提交结果未知 | 阻止同一 parcel 上有重叠效果的全部新派发，先核实；单查新 fingerprint 是否重复不足以保护 |
| 已权威证明旧效果不存在 | 原批准仍有效可走同批准重试；原批准已过期，继续阻止自动续派，按当前合法目标走人工处理或等待明确迁移设计 |
| 已接受人工/拒绝 outcome | 保留原结果和通知；历史查询不能重开或生成 RETURN_CREATED 通知 |

后续 A2 必须建立不依赖 `approval_id` 的内部效果关联约束，例如在同一 case/order/parcel 与 command kind 下检查已知及未决历史；这是防止换批准绕过防重的内部候选，不是另一个公开效果 key。范围或 provider 改变也要检查冲突，而非只比较完全相等的旧指纹。若确需自动恢复，A/C 需另行给出旧效果关联、独立 provider 能力和 B 展示方案，不能把该能力写作当前已实现。

## 5. 最后检查与调用竞争：MA-Q03

目标来源为 AH-10、FR-009/010、NFR-002/004。候选选择一个可说明的课程实现路径：同案件影响授权的动作与效果派发串行化；调用前先保存恢复意图，外部效果仍不属于数据库事务。没有用“多检查一次”代替并发设计。

| 步骤 | 拟议责任与失败语义 |
|---|---|
| 取得排他资格 | Domain 为案件/重叠效果取得跨 worker 的协调锁和持久化 claim；仅进程内 mutex 不足以约束多 worker。影响授权有效性的 Domain 写入以及 F.03 的身份停用/角色撤销均须参与一致的授权代次/协调协议；案件锁本身不能约束独立身份登记。 |
| 保存意图 | 同一事务写 command/approval 绑定、provider 配置和稳定 key、当前 attempt、必要审计；提交未确认就不调用，以原身份恢复。 |
| 最后授权检查 | 持有排他资格时重新加载权威 state/input/proposal/review/approval、可信 actor 权限、期限、scope、provider 权限和历史效果。不能对缓存值检查。 |
| 进入 adapter | 在实际本地 adapter 调用边界核对服务端时间、claim 和当前授权代次；不得先通过检查，再排队到一个稍后无检查的网络调用。身份登记与派发之间的协调实现、检查到调用的时点定义需 A/C 审查和调度暂停测试。 |
| 接受结果 | Domain 将观测按尝试/版本提交；保存失败保留预先写入的意图供查询。并发 loser 不得修改赢家状态。 |
| 锁丢失/超时/进程崩溃 | 先读可信效果 receipt；已确认标签只恢复制品，没有确认事实的旧调用才按未知处理。不能等 lease 到期就重发。迟到 worker 的过期写入须拒绝；provider 不支持有效防重时，客户端锁不能补出保证。 |

课程核心 mock 必须提供可观测、稳定 key 下至多一次效果的 ledger，用真实并发/故障注入测试核验。A3 则须独立验证 provider 的等价能力；若官方 API 只提供查询而没有足够防重/最终无效果证明，应保持 UNKNOWN/人工路径，不承诺自动恢复。

**仍未证明的边界：**本地锁不能与外部 provider 原子提交，也不能阻止 provider 在请求发出后、批准期限已过时才处理请求。批准应约束哪个精确调用时点，必须与现有“最终调用边界仍有效”的要求一致；不能把到期语义静默改成任务入队时间或提前生成许可的时间。本包给出实现与反例计划，MA-Q03 继续保持待运行验证。

## 6. 来源、审计及附件内部交接

### CS-D01：确定性来源包装

保留现有 Composite 的 required callback 契约；首选同步确定性 wrapper 捕获原 order/retrieval/citation receipt，再原样回调 Orchestrator，由 Domain 接受。receipt 至少在内部关联 invocation、case/input、source/corpus/config 版本与内容 hash。不是生成器返回一份“我看过这些来源”的自述。

同 invocation/同 hash 的重放只复用一次接受记录；同 invocation 不同内容应报冲突并阻止混用。迟到、跨案、过期输入或缺 receipt 时，Domain 不接受为当前 Risk 输入；技术失败不得伪造 C2 PASS。Risk 使用完整原材料/冲突和独立调用；不读生成器隐藏推理。

### CS-D02：一个工作单元

Domain 建立可信业务 AuditEvent，再通过 CaseRepository 与 AuditPort 共用一个 PostgreSQL 事务上下文，提交事实、必要审计和适用待办。任一写入失败均不能独立宣布业务成功；提交应答未知需按原请求/工作身份查证。适配器、LLM、UI 的观测不允许自己签署 actor 或写权威案件状态。诊断日志可独立存在，但不代替业务审计。

### CS-Q02：两种附件能力

| 内部交接 | 输入/权限候选 | 结果与禁止行为 |
|---|---|---|
| C3 图片读取 | Domain/编排提供当前 case/input 和获准 evidence ID 集；A 的附件服务校验 BOUND、归属、真实类型、大小与版本 | 返回受限内容和来源 hash；无 token、任意 URL/path。C3 的观察仍是不可信建议，不能写原图或决定责任。 |
| Operations 保存 label | 原 GENERATE_LABEL 的原始 provider 成功观测、原 command/attempt/parcel 绑定，确定性 provider adapter 的限定输出；原始观察不是 OperationResult | Domain 先保存可信 receipt/审计/制品待办；Operations 在当前 G-ARTIFACT 权限下校验 PDF/尺寸/hash/归属并受控存储，Domain 接受完整附件绑定后才形成含 label_evidence_id 的公开 OperationResult / SUCCEEDED。失败保留 EXECUTING 及原确认事实，不借 CUSTOMER STAGED 上传或新创建恢复。 |

**无新增 wire 状态/字段的映射：**EXECUTING 包含内部“效果已确认、制品待完成”子阶段。receipt 至少持久化原 operation/command/parcel/provider 配置、provider operation ID、确认依据/hash 及关联工作身份；内容 bytes/凭据留受控存储，不能写入普通审计。公开记录不带 result，可提供既有 provider_operation_id 和实际存储 ErrorEnvelope。receipt 和 artifact-only 待办共用 Domain 事务，存在确认事实就阻断任何新 invoke，而不是只检查公开 status==SUCCEEDED。

恢复先重读 receipt 再处理 claim。已有确认事实的 worker 崩溃或文件失败保持 EXECUTING，只允许查询/取回/保存原标签；它不是效果 UNKNOWN，也不是确认无效果的 FAILED。当前恢复身份、只读 provider 权限、原绑定/claim 及保留资格必须有效；创建批准过期不重新授予或阻止这种独立获权的读取/存储。若 receipt 提交未确认，先查原持久化记录，无法确认事实才查原 provider 身份，不新建 attempt/key。文件已写好但结果事务失败时复核原内容/引用；禁止重建已按政策删除的内容。预算耗尽可保留事实并升级人工处理，已有人工/拒绝 outcome 则保持；恢复成功也不能改变该 outcome/通知。

上述是端口语义候选，尚未命名/冻结新的内部方法或错误类型。公开失败沿现有 ErrorEnvelope 与 A 的规范化边界；不存在凭内部失败绕过案件访问检查的捷径。类/模块 multiplicity 见 [docs15](15-package-deployment-models.md)，附件访问矩阵见 [docs16](16-demo-identity-authorization.md)。

## 7. 可复核的反例清单

下面是**待实施的测试规格**，不是新增通过的运行测试或 Gold 标签。

| ID | 输入/故障注入 | 必须观察到的结果 | 后续验收归属 |
|---|---|---|---|
| AD-T01 | 同 command 两个 worker 同时申请下一尝试 | 一个新对象/序号；另一个读取既有记录，无第二效果 | A1.02 / A2.04 |
| AD-T02 | 同 UNKNOWN 连续三次授权查询 | 同 operation ID / 同尝试序号；查询次数另记 | A2.05 |
| AD-T03 | 原效果成功但 response 或本地保存丢失 | 不新造 key；先查可信 receipt，有标签确认则恢复制品，无确认才从原意图查询；仅一个效果 | A2.04/.05 |
| AD-T04 | provider 暂未找到但原请求仍可能完成 | 继续 UNKNOWN，不创建新尝试 | A2.05 |
| AD-T05 | 换 approval、command 或 provider 后重提同 parcel 效果 | 旧成功/未知关联仍阻止重复 | A2.02/.04 |
| AD-T06 | 最后检查之后暂停 worker，再让批准过期/输入失效 | 实際调用边界拒绝失效授权；无额外效果；不能只验最后一次检查的返回值 | A2.02/.07 / E.10 |
| AD-T07 | claim 回收后旧 worker 恢复，且 provider 结果迟到 | 过期写拒绝，未决旧效果先核实；不因 lease 到期发第二次 | A2.04/.05 |
| AD-T08 | return 成功、label 未知、随后人工收口再查到 label 成功 | 旧结果补审计，人工 outcome/通知不被覆盖；不新建执行通知 | A2.05/.06 |
| AD-T09 | 来源 receipt 缺失、跨 input、同 invocation 不同 hash | 当前提案/Risk 输入不接受混合来源，记录真实失败 | A1.08 / C1.05 / C2.05 |
| AD-T10 | 业务写成功但 AuditPort 写失败，或事务提交应答丢失 | 不分别提交成“成功无审计”；同身份查证未知提交 | F.05 / A1.03 |
| AD-T11 | C3 请求任意路径/他案 evidence；label 存储绑定错 parcel | 受控服务拒绝，无内容泄漏/无错误绑定 | F.04/.07 / A2.03 |
| AD-T12 | HTTP 决定重放、查询重试、通知重试混合 | 三者各用自身身份；不把任一种重试当新 return/label 授权 | A2.07 |
| AD-T13 | provider 已创建 label，存储失败或 PDF 尚不可取 | 持久化确认 receipt/EXECUTING，不发布残缺 result；仅取回/存原标签；完整绑定后才 SUCCEEDED，创建效果计数不增加 | F.04 / A2.03/.05 |
| AD-T14 | receipt 已存后崩溃，随后批准过期；或结果提交丢失 | 先重读 receipt，当前恢复权限允许时只恢复原制品；无权限不读取；没有可信确认事实才查询原效果，绝不先重新创建 | A2.04/.05；MA-T21 |

其中 AD-T06/.07 的排程和 provider 调用计数必须在运行系统中验证；结构图、schema 或静态文本匹配都不足以通过。

## 8. 最小联合评审与个人解释

沿用现有 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11) 作为评审上下文；本文是否发布由实际 commit 决定，当前新增候选不冒称已在 PR 中。当前文件 hash 与检查证据见本轮 [缺陷修正记录](reviews/a-defect-closure-20260907.md)；[A-PREP 准备交付记录](reviews/a-preimplementation-readiness-20260907.md)只保留修正前的历史快照。

| 由谁回答 | 最小问题 | 记录要求 |
|---|---|---|
| A 本人 | 用正常 return→label→通知、label 超时且保存失败、无提案订单阻断人工处理三个例子解释“谁能写、谁能调用、何时不能重试” | 本人修订/解释记录；不能由 AI 将本次授权填成个人理解完成 |
| A/C，B 确认消费 | 是否采用 1-based 不变尝试序号；若采用，如何发布下一契约修订 | 指定 AD/rc/MA 版本，明确接受或具体异议；没有回复不算接受 |
| A/C | UNKNOWN 查询、原始来源 receipt、业务/审计事务是否一致；MA-Q02/.03 是否按上文保持未决 | 对反例逐项有处置，运行证明分配到原 WBS |
| B | 尝试与查询/通知计数分开显示；202/UNKNOWN/人工结果和旧历史是否可消费 | 具体 DTO/页面映射与例子，不要求 B 重做 A 的后端 |

接受后的下一步才是同步选定方案到契约/类图并复验，推进 A1.01、F.03 及其依赖。R.02 之前不把 LLM 接入执行链；A 的本人说明、C 的人审与 tutor 反馈仍由真实参与者提供。
