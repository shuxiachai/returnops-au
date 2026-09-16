# C：真实贡献、模型讲解与提交前核对

> **2026-09-16 资料入口更新（MC-PER-0.1.1）。** B 已对 C `c9f205d` 留下[消费者边界 approval](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5199940157)；这不替代 A 的指定 review，也不替 C 填写本人回答。新的团队报告中未经确认的 C 贡献比例、模型编号和运行结果表述见 [9 月 16 日核对](../reviews/member-c-integration-followup-20260916.md)；在真实确认前不采用。以下所有个人答案、日期、决定和贡献栏仍保持待本人填写。

> **MC-PER-0.1，2026-09-14；待本人填写的记录，不是已完成证明。**
> 本模板由 AI 辅助整理；所有标记“待 C 本人”的内容必须来自实际发生的理解、修改、讲解和确认。不得用本模板推断 C 已独立完成、A/B 已认可、interview 已进行或 Jira 可标 Done。

对象：C / Lucas Tao / `lulucas-tao`。个人交付 WBS M-C.01–.06，对应已识别的 [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22)；F.01 评审关联 [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)。这些是追踪入口，不声明当前实时状态。原 Owner、Reviewer、S/F 不变；不另外创建重复状态板。

## 1. 先固定要解释的版本

| 项目 | 已知资料 / 本人需完成的记录 |
|---|---|
| 个人模型文档 | [MC-0.1.3](../18-member-c-model-chain.md)；原三图 MC-ACT/SEQ/SM-0.1 保留 |
| C 报告稿 | [MC-RPT-0.4](member-c-stage1-draft.md)；含报告视图、Object 切片和新团队报告的 C 替换段落 |
| A 契约技术参考 | F.01 rc.5，`3dd1ff637693a826990eee5712cfb239a3c3da7b`；[PR #11](https://github.com/shuxiachai/returnops-au/pull/11) |
| 已发布 A 技术处置 | [COMMENT](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5196102404)，针对 C `32c704f6bf4b86139b0bcbe53419fe23530fdd97`；不是本轮新文档的评审 |
| 本人实际阅读/修改的最终 commit | **待 C 本人记录**：准确 SHA / 文件版本；不能只写浮动分支或旧评审 SHA |
| 阅读/解释的真实日期与场合 | **待 C 本人记录**；不倒填日期、虚构会议、工时或签字 |
| 本次讲解后仍不理解的问题 | **待 C 本人记录**；没有把握时写问题，不用 AI 输出冒充已掌握 |

课程依据见[最新要求登记](https://github.com/shuxiachai/returnops-au/blob/docs/canvas-requirements-20260914/docs/19-course-assessment-requirements.md)。该共享文件在独立 review 分支上；链接存在不代表已合并。Rubric 要求个人模型源于本人 AH/UC，所有成员参与所有共享任务并说明实际贡献；官方 unit outline 允许 AI 但要求 acknowledgement。任务解锁后的具体声明/上传规则仍需核对。

## 2. C 本人的设计决定与实际修订

一个决定可以是“保留某设计并解释理由”，不必为了显示贡献强行改对的模型。但必须记录本人实际核对的细节和证据，不能把 AI 辅助初稿自动算作本人完成。旧共享报告 Chapter 8 / Figures 21–23 的来源和既有作者记录继续保留。

| 记录 | 本人决定、理由与具体位置 | 实际修订 / 核对证据 | 日期与尚未解决的问题 |
|---|---|---|---|
| AH-08 → UC-02/05 | 待 C 本人填写 | 待 C 本人填写文件、段落/图元素及版本 | 待 C 本人填写 |
| C1 引用可解析性与 C2 主张支持的界限 | 待 C 本人填写 | 待 C 本人填写 | 待 C 本人填写 |
| MC-D01：七工作阶段 / 五业务结果 | 待 C 本人说明如何理解 A 的已记录选择 | 待 C 本人填写 | 待 C 本人填写 |
| MC-D02：原子 selected-work 事件守卫 | 待 C 本人说明成功、失败和 retirement 的同一约束 | 待 C 本人填写 | 待 C 本人填写 |
| MC-D03：两次 reservation / 一次自动 revision | 待 C 本人解释计数单位及重启、dispatch 失败、旧请求回放 | 待 C 本人填写 | 待 C 本人填写 |
| UC-05 历史与删除/权限边界 | 待 C 本人填写 | 待 C 本人填写 | 待 C 本人填写 |
| 被放弃的设计与取舍 | 待 C 本人填写真实比较；不能编造已经讨论过的选项 | 待 C 本人填写 | 待 C 本人填写 |

## 3. 四场景：由 C 用自己的话回答

先独立讲解，再对照 [模型 §2/§6/§7](../18-member-c-model-chain.md)。以下只提供问题，不提供“本人已答对”的结论。例子必须使用合成数据，不打开或生成正式 Gold labels；也不拿学习记录冒充运行测试。

### MC-T01：通过不等于执行

- 指出输入、proposal/input/corpus 版本、selected work/round/invocation 及被接受的 source bundle。
- 从 C01 走到 C07，指出谁检查引用、谁判断支持性、谁写权威状态。
- 为什么 JSON 合法不够？PASS 后还缺哪些 Founder/Domain/Operations 条件？
- 若发现 citation 能定位但不支持主张，哪一步必须改变，为什么？

**C 的回答：** 待 C 本人填写。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

### MC-T02：阻断性来源冲突

- 原始两个来源和 conflict 如何一直保留到独立审查？
- 哪个具体事实使它是 BLOCK/ESCALATE，而不是非阻断 WARNING？
- 为什么不能凭信心选择来源优先级，或把它命名为 OrderLookupBlock？
- 对照 [Object 切片](../diagrams/member-c/member-c-object-conflict.svg)，指出具名对象、属性槽和关系；解释工作对象与结果对象、设计快照与运行证据的区别。
- 此刻 Founder 还没有做什么？哪些下一步合法，哪些不合法？

**C 的回答：** 待 C 本人填写。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

### MC-T03：补信息与新版本

- 哪组 question ID / 当前问题集允许接收这次回答？旧问题回放为何不同？
- 哪个版本在何时变化？旧 proposal/review 与新输入如何处理？
- 为什么任意新上传不是合法的 post-review append 入口？
- NEEDS_INFORMATION 后如何离开 episode，什么真实新意图才允许新 episode？

**C 的回答：** 待 C 本人填写。

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

**C 的回答：** 待 C 本人填写。

**本人指出或修改的图元素/文件版本：** 待 C 本人填写。

**讲解日期、真实反馈与待解决问题：** 待 C 本人填写。

## 4. 每项共享任务的真实贡献

下表的 Owner 是既有整合责任，不是个人参与的豁免。C 必须记录自己实际提供的元素、关系、约束、修改或实质评审，并取得进入最终成果的链接。不得拿计划 28% 当实际贡献，不能填造 A/B 的完成记录；如使用比例，只填写实际可解释的比例与依据。没有发生的参与继续标待完成。

| 共享任务 / 整合主责 | C 可核对的材料入口 | C 实际贡献与版本 | 进入最终成果的证据 / 尚缺工作 |
|---|---|---|---|
| Requirements classification / B 整合 | [MC §8 分类追踪](../18-member-c-model-chain.md#8-cs-requirements-classification--traceability-hand-off-to-b) | AI 辅助候选已提供；本人具体核对/修订待填写 | 待 B 返回 exact commit / section / index link |
| Feature diagram / B | [需求模型](../05-lab-3-requirement-modelling.md)；核对 C1/C2/C3 与共享边界 | 待 C 本人填写具体元素或实质评审 | 待最终图号、版本和整合确认 |
| Overall Use-case diagram / B | UC-02/05 规格与其他四个 UC 的角色/边界 | 待 C 本人填写具体关系或实质评审 | 待最终图号、版本和整合确认 |
| Elementary Class / A | [共享类模型](../diagrams/01-domain-class-diagram.md)；来源、引用、work/result 关系 | 待 C 本人填写类/属性/方法/关系核对和修改 | 待 A 处置与最终图号/版本 |
| Complex Structure / A | [既有 Composite](../13-shared-composite-structure.md)及 [C Object 切片](../diagrams/member-c/member-c-object-conflict.svg) | 新切片为 AI 辅助候选；本人类/实例一致性核对待填写 | 待 A 审查/整合、B 索引；不能声称已获全组认可 |
| 项目保留的 Architecture / Package / Deployment / A | [架构决定](../14-member-a-design-decisions.md)、[Package/Deployment](../15-package-deployment-models.md) | 待 C 记录真实参与/评审；不把 rubric Optional 误写为全部必选 | 待相应处置链接 |
| 最终完整需求与模型索引 / B；报告整合 / A | [C 报告稿](member-c-stage1-draft.md)与本表 | 待 C 本人核对模型编号、引用、限制和贡献 | 待最终版本；仅草稿存在不足以完成 R.04 |

## 5. 非作者评审与未决边界

已存在的 A 技术 COMMENT 选择了 D01–03。它不是空白或待选择，但不等于个人讲解、联合接受，也不覆盖本轮新增报告视图/对象切片。请 reviewer 对最终准确版本记录以下内容，不替 reviewer 预填结论：

| 核对项 | 真实结果 |
|---|---|
| A 对最终 C commit 的技术/课程一致性 review 链接 | 待 A 实际评审 |
| C 对上述四场景与 D01–03 的本人解释/确认 | 待 C 本人完成 |
| A 对 Object 切片及共享类一致性的处置 | 待 A 实际记录 |
| B 对分类/个人链/Object 索引的整合链接 | 待 B 实际整合 |
| F.01/F.02 联合接受、clean Git / PG17 Compose 复现 | 独立未决工作；不由本模板、图或旧测试自动完成 |
| 本轮文档/图检查与运行测试区分 | 记录发布任务实际执行的检查；不重写 Sep 12/14 历史日志或把静态结果当业务测试 |

## 6. AI acknowledgement：事实表，而非预签声明

已知辅助范围：读取和比较已提供材料、整理规格/模型/报告草稿、绘图源和一致性检查、评审问题整理与证据组织。既有共享讨论稿和历次 C 候选来源保留。最终声明由学生按实际使用情况及解锁后课程规则核实，不宣称所有文字/图由学生未借助工具独立完成。

| 最终需声明的事实 | 由本人核实的内容 |
|---|---|
| 实际工具/模型及使用范围 | 待 C 本人核实实际工具名、使用环节；不猜测不可见模型版本 |
| 被保留的 AI 草稿/图/检查内容 | 待 C 指明文件、图和范围 |
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

Stage 2 的 C1 检索/引用、C2 独立审查和 C3 图片观察及各自实现/测试仍按 [docs/07](../07-frozen-work-allocation.md)、[docs/08](../08-delivery-work-packages.md) 执行。30 Gold、20-case 子集、p95 <120s 是项目协议/目标，不是全班统一的 Stage 1 评分门槛。此记录不创建 Gold、不证明 label sealing 或测量结果，也不允许越过 Gate 1 把 LLM 接入执行链。按时提交诚实标明未完成项的 Stage 1 材料，不等待 Stage 2 全部完成。
