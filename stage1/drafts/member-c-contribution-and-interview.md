# C：真实贡献、模型讲解与提交前核对

> **2026-09-17 交付事实与评审交接补录（MC-PER-0.2）。** C 负责并委托 AI 辅助完成的候选成果属于 C 的交付范围；下面补齐版本、交付内容、技术说明、AI 使用范围与已存在的整合回执，不把这些都留成空白。交付归属不等于未借助 AI 独立制作、本人已经讲解、评审通过或验收完成。补录日期不是虚构的个人阅读、会议或测试日期。新 commit 和检查结果以 [PR #12](https://github.com/shuxiachai/returnops-au/pull/12) 的本次发布记录为准；`15c136a` 是补录前的资料快照。

> **历史入口：2026-09-16（MC-PER-0.1.1）。** B 已对 C `c9f205d` 留下[消费者边界 approval](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5199940157)，不替代 A 的最终 review。C 的[六项报告反馈](../../docs/reviews/member-c-integration-followup-20260916.md)已由 A 在 B 的 PR #14 中作技术修订；[9 月 17 日处置回执](https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/reviews/b-shared-model-followup-20260917.md)和下方固定版本链接取代“尚无整合回执”的旧状态，但不证明最终 PDF、共享 Google Doc 或个人确认已完成。

> **MC-PER-0.1，2026-09-14；待本人填写的记录，不是已完成证明。**
> 本模板由 AI 辅助整理；所有标记“待 C 本人”的内容必须来自实际发生的理解、修改、讲解和确认。不得用本模板推断 C 已独立完成、A/B 已认可、interview 已进行或 Jira 可标 Done。

对象：C / Lucas Tao / `lulucas-tao`。个人交付 WBS M-C.01–.06，对应已识别的 [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22)；F.01 评审关联 [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)。这些是追踪入口，不声明当前实时状态。原 Owner、Reviewer、S/F 不变；不另外创建重复状态板。

## 1. 先固定要解释的版本

| 项目 | 已知资料 / 本人需完成的记录 |
|---|---|
| 个人模型文档 | [MC-0.1.3](../../docs/18-member-c-model-chain.md)；原三图 MC-ACT/SEQ/SM-0.1 保留 |
| C 报告稿 | [MC-RPT-0.4](member-c-stage1-draft.md)；含报告视图、Object 切片和新团队报告的 C 替换段落 |
| A 契约技术参考 | F.01 rc.5，`3dd1ff637693a826990eee5712cfb239a3c3da7b`；[PR #11](https://github.com/shuxiachai/returnops-au/pull/11) |
| 已发布 A 技术处置 | [COMMENT](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5196102404)，针对 C `32c704f6bf4b86139b0bcbe53419fe23530fdd97`；不是本轮新文档的评审 |
| 本人实际阅读/修改的最终 commit | **待 C 本人记录**：准确 SHA / 文件版本；不能只写浮动分支或旧评审 SHA |
| 阅读/解释的真实日期与场合 | **待 C 本人记录**；不倒填日期、虚构会议、工时或签字 |
| 本次讲解后仍不理解的问题 | **待 C 本人记录**；没有把握时写问题，不用 AI 输出冒充已掌握 |

课程依据见[要求登记固定快照](https://github.com/shuxiachai/returnops-au/blob/b3b3b5869d33704e9f1da5b777c8c9338de6b565/docs/19-course-assessment-requirements.md)。该共享文件在独立 review 分支上；链接存在不代表已合并。Rubric 要求个人模型源于本人 AH/UC，所有成员参与所有共享任务并说明实际贡献；官方 unit outline 允许 AI 但要求 acknowledgement。任务解锁后的具体声明/上传规则仍需核对。

### 1.1 C 负责的可核实交付台账

以下记录交付责任和仓库中真实存在的 AI 辅助成果，不据此推算本人手工工作量、独立完成程度或贡献百分比。旧团队讨论稿 Chapter 8 / Figures 21–23 及 A/B 作者记录保留。

| 交付 | C 负责提交的内容（AI 辅助） | 可核实版本 / 证据及限制 |
|---|---|---|
| 个人需求与模型链 | AH-08 → UC-02/UC-05；C1 来源/引用和 C2 独立审查边界；Activity、Sequence、State、12 个静态走查场景及分类表 | [MC-0.1.3 @15c136a](https://github.com/shuxiachai/returnops-au/blob/15c136a1f717ba074d4aa77a0572d159c28cda8c/docs/18-member-c-model-chain.md)；不是 12 个已运行的业务测试 |
| 图源和报告视图 | 3 个完整行为图、3 个清晰报告视图、1 个合成冲突 Object 切片，共 7 组 PUML/SVG | [图目录 @15c136a](https://github.com/shuxiachai/returnops-au/tree/15c136a1f717ba074d4aa77a0572d159c28cda8c/docs/diagrams/member-c)；MC-ACT/SEQ/SM-0.1、对应 RPT-0.1、MC-OBJ-0.1；不是 B 的 OBJ-1 作者证明 |
| 报告与整合反馈 | MC-RPT-0.4；团队报告 §§7.3/10/13.4/14/16/17 的替换文案；六项证据/语义问题及来源 | [报告 @15c136a](https://github.com/shuxiachai/returnops-au/blob/15c136a1f717ba074d4aa77a0572d159c28cda8c/docs/reports/member-c-stage1-draft.md)、[已发给 PR #14 的反馈](https://github.com/shuxiachai/returnops-au/pull/14#issuecomment-5696352699)；A 完成后续共享文件修订，不归作 C 直接修改 B 文件 |
| F.01 / F.02 证据 | 已发布契约审查、C-F01 复测和受限环境复现记录 | [9 月 14 日证据](../../docs/reviews/member-c-followup-20260914.md)：58 contracts + 15-case matrix，使用披露的重构源码；[9 月 12 日环境记录](../../docs/reviews/member-c-f02-reproduction-20260912.md)：native PG16.2。均不是新的 clean Git / PG17 Compose 复现 |
| F.03 审查准备 | 对 A 的独立认证/授权组件作限定范围静态审查，列出 7 项后续 Domain/集成验证 | [9 月 16 日 C 审查](../../docs/reviews/member-c-f03-review-20260916.md)、[PR #15 COMMENT](https://github.com/shuxiachai/returnops-au/pull/15#issuecomment-5696357090)；未在该次审查重跑 244 项测试，也不是 C 个人批准 |
| 课程对照与交接 | 整理 Canvas 要求/证据映射、README 阅读路径、待交付事项与版本限定 | [共享 PR #13](https://github.com/shuxiachai/returnops-au/pull/13) 与 [README](../../README.md)；没有上传课程原始 PDF，也没有提交课程作业或证明全组通过 rubric |

**最近验证的归属：** 补录前 C `15c136a` 的 [push 35090527092](https://github.com/shuxiachai/returnops-au/actions/runs/35090527092) 与 [PR 35090530526](https://github.com/shuxiachai/returnops-au/actions/runs/35090530526) 各两项 job 成功，共 4/4；这些是该 SHA 的 CI，不覆盖未来提交，也不证明个人理解、业务运行或本机 Compose。

**整合回执：** A 在 B 的 [PR #14 / `1b094289`](https://github.com/shuxiachai/returnops-au/commit/1b094289c219727d9e42e694ade6f13431c34c7b) 中使用 C `15c136a` 的文案，修订模型编号、五种结果/第二次真实 REVISE、版本/保留边界、Gold 限制和未经证实的贡献/运行表述。[团队报告固定快照](https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/reports/stage-1-team-report.md) §§7.3/10/13.4/14/16/17 是候选整合证据；不是已合并的最终报告，也不能覆盖 A 对 C 新版本的评审。

## 2. C 本人的设计决定与实际修订

一个决定可以是“保留某设计并解释理由”，不必为了显示贡献强行改对的模型。但必须记录本人实际核对的细节和证据，不能把 AI 辅助初稿自动算作本人完成。旧共享报告 Chapter 8 / Figures 21–23 的来源和既有作者记录继续保留。

| 记录 | C 交付中的技术说明（AI 辅助整理） | 来源 / 决定归属 | 本人核对记录 |
|---|---|---|---|
| AH-08 → UC-02/05 | 从证据可追踪的 Founder 决策需求导出非执行型提案准备与授权历史查看；模型责任 C、UI B、权威 API/状态 A | MC §1–3；是个人模型范围，不扩展功能分工 | 实际阅读/解释日期和本人修订待补 |
| C1 引用可解析性与 C2 主张支持的界限 | C1 校验精确来源版本/位置/hash；C2 独立判断主张支持、冲突、缺失材料与安全；可定位或 JSON 合法不等于建议正确 | MC §2 C02–C06、§3；C1/C2 候选设计 | 待本人复述和指出图中对应位置 |
| MC-D01：七工作阶段 / 五业务结果 | 工作进度与不可变审查结果分开；新上下文产生新工作，旧结果不改写，不增加公共 outcome | MC §6；A 的 9 月 14 日技术选择，不写成 C 原创决定 | 待本人解释为何不能共用一个 enum |
| MC-D02：原子 selected-work 事件守卫 | 启动/接受及失败、重试、耗尽、retirement 均核对 selected identity；Domain 原子提交状态、必要 audit 和适用 durable scheduling | MC §6；A 选择事务边界，运行并发实现未由模型证明 | 待本人用同版本替换 invocation 举例 |
| MC-D03：两次 reservation / 一次自动 revision | 每 logical call 最多两次持久 reservation；每 episode 最多一次自动提案修订；dispatch 失败仍耗已提交名额，重启不能重置 | MC §6；A 选择的原型默认值，不是实测最优值或 OperationAttempt 次数 | 待本人解释 unknown commit 与第二次 REVISE |
| UC-05 历史与删除/权限边界 | 每页重验权限；固定快照/筛选器/游标；精确关联历史版本；保留合法 tombstone，不从旧缓存恢复被删正文 | MC §2 UC-05；权限和存储仍属 A，展示属 B | 待本人核对一条历史读取路径 |
| 取舍分析 | 现有设计选择完整证据和显式失败而非静默截断、持久有界重试而非无限循环、人工精确批准而非 PASS 自动执行 | MC §2/§6 的设计理由；这里只是准备好的比较，不伪称 C 已召开讨论或独立选定 | 待本人选择一个确实理解的取舍并记录理由 |

## 3. 四场景：由 C 用自己的话回答

先独立讲解，再对照 [模型 §2/§6/§7](../../docs/18-member-c-model-chain.md)。下方补入 AI 辅助参考说明，供核对和准备，不记录“本人已答对”。本人实际复述/修改、日期和反馈仍须如实填写。例子只使用合成数据，不打开或生成正式 Gold labels；学习记录不是运行测试。

### MC-T01：通过不等于执行

- 指出输入、proposal/input/corpus 版本、selected work/round/invocation 及被接受的 source bundle。
- 从 C01 走到 C07，指出谁检查引用、谁判断支持性、谁写权威状态。
- 为什么 JSON 合法不够？PASS 后还缺哪些 Founder/Domain/Operations 条件？
- 若发现 citation 能定位但不支持主张，哪一步必须改变，为什么？

**交付中的参考说明（AI 辅助）：** C01–C04 由 Domain 装载授权当前上下文，并验证完整来源、引用覆盖和 case/input/proposal/corpus 绑定后接受完整 bundle。Orchestrator 再以独立调用把该材料交给 C2，C2 不能仅复述 Assessment 的推理。C1 的来源定位/hash 检查与 C2 的主张支持判断各有责任；可解析但不支持主张的引用不能被当作通过依据，需按真实问题修订、补信息或处理阻断冲突，而不是伪造 PASS。C06 接受结果还必须满足 selected invocation 与当前权限/版本守卫。当前有效 PASS/PASS_WITH_WARNING 且其他 Domain 守卫通过，才可进入 Founder 待审队列；WARNING finding 本身不放行。精确批准、Domain 状态/权限和 Operations 执行前检查仍不可省略。

**C 本人复述或修订：** 待实际讲解后记录。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

### MC-T02：阻断性来源冲突

- 原始两个来源和 conflict 如何一直保留到独立审查？
- 哪个具体事实使它是 BLOCK/ESCALATE，而不是非阻断 WARNING？
- 为什么不能凭信心选择来源优先级，或把它命名为 OrderLookupBlock？
- 对照 [Object 切片](../../docs/diagrams/member-c/member-c-object-conflict.svg)，指出具名对象、属性槽和关系；解释工作对象与结果对象、设计快照与运行证据的区别。
- 此刻 Founder 还没有做什么？哪些下一步合法，哪些不合法？

**交付中的参考说明（AI 辅助）：** 两个冲突来源和 conflict 必须作为完整 RetrievalResult 保留到独立审查，不能只传 Assessment 选出的摘要。若冲突影响关键判断且无法形成安全建议，应保留 BLOCK finding 与真实 ESCALATE；不能凭置信度虚构来源优先级，也不能把来源冲突写成提案前订单查询的 OrderLookupBlock。MC-OBJ-0.1 展示一个合成时刻的具名实例、属性和链接，是设计快照而非运行日志。此时没有 Founder 精确批准；对当前不安全提案可走合法 REQUEST_REVISION 或 MANUAL_HANDLING，不能直接 APPROVE。只有真正没有当前提案的 failure/block 目标才是 manual-only。

**C 本人复述或修订：** 待实际讲解后记录。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

### MC-T03：补信息与新版本

- 哪组 question ID / 当前问题集允许接收这次回答？旧问题回放为何不同？
- 哪个版本在何时变化？旧 proposal/review 与新输入如何处理？
- 为什么任意新上传不是合法的 post-review append 入口？
- NEEDS_INFORMATION 后如何离开 episode，什么真实新意图才允许新 episode？

**交付中的参考说明（AI 辅助）：** NEEDS_INFORMATION 退出当前机器循环，由 Coordinator 的 UC-01E 路径收集当前授权问题集的回答。Domain 校验 question IDs、权限和当前绑定后追加新的输入版本；保留旧记录但撤销其当前适用性，新提案需要新的独立审查，旧批准不能转移。旧问题/请求回放不代表新意图，任意附件上传也不构成 post-review append 的许可。合法的当前问题集回答或 Founder 对当前提案的有效修订请求才可按守卫进入新 episode；本设计没有任意三轮客户澄清上限。

**C 本人复述或修订：** 待实际讲解后记录。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

### MC-T09：过期事件与持久预算

- round 2 已选中后，round 1 的 reply、timeout、retry、exhaustion 各应怎样处理？
- G_START 与 G_EVENT 有什么区别？为什么 recovery 检查的是失败/retired invocation？
- 哪些 selected identity、状态、audit 和 scheduling 事实必须同事务提交？
- reservation 已提交但未成功 dispatch 时，还剩多少额度？unknown commit 时先查什么？
- 新 invocation ID、重启、SDK retry 为何不能重置预算？这与 OperationAttempt 计数有什么不同？
- 第二次真实 REVISE 到来时，如何保留结果/当前 proposal 并停止机器循环？
- 哪个行为只有实际并发/故障运行测试才能证明，图本身不能证明？

**交付中的参考说明（AI 辅助）：** round 2 被选中后，round 1 的成功、校验失败、timeout、retry 或 exhaustion 都不得修改 round 2 的当前业务状态、审计结果或资格。G_START 检查尚未分配 invocation 的 queued work/round；G_EVENT 检查所选 active invocation，恢复时核对所选 failed/retired invocation；retirement 只能退役准确的旧对象。Domain 在一个事务上下文中核对并提交所需状态/audit/durable scheduling。初始 reservation 若已提交，即使 dispatch 失败也已消耗两次上限中的一次；commit 结果未知时先恢复原记录，不能盲目再次调用或计数。重启、新 ID 和 SDK retry 不重置预算，也不改变 A2 的 OperationAttempt 规则。一次自动提案修订后再得 REVISE，应保留真实 REVISE/当前提案，停止自动循环并记录升级原因，不改写为 ESCALATE 或虚构技术失败。如果实际生成、完整材料组装等环节发生真实技术失败，且权威记录中没有当前提案，则按实际阶段使用对应 no-proposal failure 路径；这也可能发生在首次提案之前，单纯修订预算耗尽不能制造 failure。这些事务/竞争保障仍需运行测试，图本身不能证明。

**C 本人复述或修订：** 待实际讲解后记录。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

## 4. 每项共享任务的真实贡献

下表的 Owner 是既有整合责任，不是个人参与的豁免。C 必须记录自己实际提供的元素、关系、约束、修改或实质评审，并取得进入最终成果的链接。不得拿计划 28% 当实际贡献，不能填造 A/B 的完成记录；如使用比例，只填写实际可解释的比例与依据。没有发生的参与继续标待完成。

| 共享任务 / 整合主责 | C 可核对的材料入口 | C 负责交付的内容 / 本人记录 | 整合证据 / 尚缺工作 |
|---|---|---|---|
| Requirements classification / B 整合 | [MC §8 分类追踪](../../docs/18-member-c-model-chain.md#8-cs-requirements-classification--traceability-hand-off-to-b) | C 提供 FR/NFR/证据类别 → UC/模型/测试与 WBS 的 AI 辅助分类候选；本人复核记录待补 | B 旧 approval 已接受整合方向；§1.1 有团队报告候选回执，完整 M-S.03 索引与实际贡献确认仍待最终链接 |
| Feature diagram / B | [需求模型](../../docs/05-lab-3-requirement-modelling.md)；核对 C1/C2/C3 与共享边界 | 待 C 本人填写具体元素或实质评审 | 待最终图号、版本和整合确认 |
| Overall Use-case diagram / B | UC-02/05 规格与其他四个 UC 的角色/边界 | C 的 AI 辅助规格与报告反馈明确 UC-05 归属、独立审查及不安全提案的合法路径；不冒称绘制 B 的整体图 | A 已在 PR #14 `1b094289` 修订共享 UCD 边界；C 本人复核和最终图号待补 |
| Elementary Class / A | [共享类模型](../../docs/diagrams/01-domain-class-diagram.md)；来源、引用、work/result 关系 | 待 C 本人填写类/属性/方法/关系核对和修改 | 待 A 处置与最终图号/版本 |
| Complex Structure / A | [既有 Composite](../../docs/13-shared-composite-structure.md)及 [C Object 切片](../../docs/diagrams/member-c/member-c-object-conflict.svg) | C 提供 MC-OBJ-0.1 的具名冲突对象切片及解释；区分 work/result、类/实例和观察/批准，属 AI 辅助候选 | A 的最终类/实例一致性处置、B 完整索引及 C 本人复核未完成；C 切片不替代共享 Composite，也不是 B OBJ-1 作者证明 |
| 项目保留的 Architecture / Package / Deployment / A | [架构决定](../../docs/14-member-a-design-decisions.md)、[Package/Deployment](../../docs/15-package-deployment-models.md) | 待 C 记录真实参与/评审；不把 rubric Optional 误写为全部必选 | 待相应处置链接 |
| 最终完整需求与模型索引 / B；报告整合 / A | [C 报告稿](member-c-stage1-draft.md)与本表 | C 提交报告 §10 替换文案及六项问题反馈；A 作 B 候选修订；本人讲解/实际手工改动不从 commit 作者名推断 | §1.1 的 `1b094289` 报告/处置已提供候选回执；最终全模型索引、PDF、Google Doc 和提交回执仍分开核对 |

## 5. 非作者评审与未决边界

已存在的 A 技术 COMMENT 选择了 D01–03。它不是空白或待选择，但不等于个人讲解、联合接受，也不覆盖本轮新增报告视图/对象切片。请 reviewer 对最终准确版本记录以下内容，不替 reviewer 预填结论：

| 核对项 | 真实结果 |
|---|---|
| A 对最终 C commit 的技术/课程一致性 review 链接 | 待 A 实际评审 |
| C 对上述四场景与 D01–03 的本人解释/确认 | 待 C 本人完成 |
| A 对 Object 切片及共享类一致性的处置 | 待 A 实际记录 |
| B 对分类/个人链/Object 索引的整合链接 | §1.1 已补 A 修订的 B 报告候选/处置链接；完整 M-S.03 索引、最终交付和个人认可仍待确认 |
| F.01/F.02 联合接受、clean Git / PG17 Compose 复现 | 独立未决工作；不由本模板、图或旧测试自动完成 |
| 本轮文档/图检查与运行测试区分 | 记录发布任务实际执行的检查；不重写 Sep 12/14 历史日志或把静态结果当业务测试 |

## 6. AI acknowledgement：事实表，而非预签声明

已知辅助范围：读取和比较已提供材料、整理规格/模型/报告草稿、绘图源和一致性检查、评审问题整理与证据组织。C 确认委托完成的上述任务属于其负责的工作；这明确交付责任，不把 AI 执行写成 C 亲手操作或独立讲解。既有共享讨论稿和历次 C 候选来源保留。

**供最终报告核实采用的披露稿（不是预签个人声明）：** C 负责 grounding/risk 个人模型链、相关报告与交付证据，使用 OpenAI Codex/ChatGPT 辅助阅读课程及仓库材料、起草和修订说明/PlantUML 图源、整理静态检查与测试记录、准备评审反馈，并按 C 的指示发布到其分支。MC-0.1.3、MC-RPT-0.4、七组 C 图源/视图、课程对照和相关 review 文档包含此类辅助内容。D01–03 的技术选择应归于 A 的已发布处置；既有共享稿及 B 的图保留原作者记录。学生本人实际阅读、修改、讲解与最终接受的范围仍须另有真实记录。没有据此声明独立完成全部内容、通过课程验收或取得正式实验结果。最终声明位置/格式由解锁后的任务规则确定。

| 最终需声明的事实 | 由本人核实的内容 |
|---|---|
| 实际工具/模型及使用范围 | 本轮为 OpenAI Codex；连续协作包含 ChatGPT/AI 辅助。阅读、草稿、图源、校验/证据和网页发布范围如上；底层具体模型版本未可靠登记，不补造 |
| 被保留的 AI 草稿/图/检查内容 | §1.1 已列模型、7 组图源/视图、报告、课程对照与 review 文件；保留在候选分支不等于本人已逐项核实或被最终报告全部采用 |
| 本人真正做出的决定、修改、核验与解释 | 待 C 引用 §2–§4 的真实条目 |
| 参考来源和旧稿作者 | 保留共享 Team Review Draft 和仓库历史，再由 C 核实最终引用 |
| 课程要求的声明位置/格式 | 待任务解锁后核对，A 整合、C 核验 |

## 7. 提交前清单与 Stage 2 边界

- [ ] C 本人完成四场景解释和具体决定/修订记录，能说明至少一个真实取舍。
- [ ] C 在所有共享任务的实际贡献可定位；A 审对象切片，B 返回全模型索引链接。
- [ ] A 对最终准确版本 review；个人和共同接受边界如实标注。
- [ ] 最终报告包含完整需求、模型追踪、贡献和 AI acknowledgement；原完整模型与清晰报告视图的对应关系可访问。
- [ ] 在最终 PDF 正常阅读尺寸及视频正常播放尺寸检查图中文字/箭头；视频不超过 8 分钟；个人 interview 仍需准备。
- [ ] A 按最新 Canvas 规则整合提交，C 核验最终版本、可访问性及真实回执；不把旧 Tutorial 周次替代当前课程时间。

Stage 2 的 C1 检索/引用、C2 独立审查和 C3 图片观察及各自实现/测试仍按 [docs/07](../../docs/07-frozen-work-allocation.md)、[docs/08](../../docs/08-delivery-work-packages.md) 执行。30 Gold、20-case 子集、p95 <120s 是项目协议/目标，不是全班统一的 Stage 1 评分门槛。此记录不创建 Gold、不证明 label sealing 或测量结果，也不允许越过 Gate 1 把 LLM 接入执行链。按时提交诚实标明未完成项的 Stage 1 材料，不等待 Stage 2 全部完成。
