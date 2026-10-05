# ELEC5620：课程要求与全员交付对照

> **Stage2 本地原件补充（2026-10-05）：**已核实新增的两页 `practical/ELEC5620 Project Stage 2 Marking Criteria.pdf`（SHA256 `21b40026f135debeac05c411440bdb2710ba00616198f6106d0aaf748e8083ea`）。评分为设计实现7、AI能力4、Agile4、先进技术5，共20分；明确要求 Jira 协作、2026-11-01 23:59 源码提交、Week13 从 Canvas 下载源码并现场部署、四项评分维度的真实贡献表。PDF 未注明时区；当前 Canvas 上传细则及后续通知尚未核验。详见[Stage2 提交检查与未填写贡献表](28-stage2-submission-checklist.md)。下方9月14日来源表保留为当时的证据记录，不把其旧截止核验状态当作本次最新结论；九功能、89项分工及原依赖不变。

> **COURSE-20260914-0.1**，核对日期 2026-09-14；按 C 的请求进行 AI 辅助整理，供 A/全组评阅。这是官方来源与证据要求对照，不是 tutor 批准、个人贡献签字、实时看板或课程验收。产品范围仍以 [docs/00](00-project-definition-v1.md)为准，九项功能以 [docs/07](07-frozen-work-allocation.md)为准，89 项 ID/Owner/Reviewer/S/F 以 [docs/08](08-delivery-work-packages.md)为准；[docs/11](11-stage1-readiness.md)继续作为 R.04 提交核验入口。

## 1. 所有人先看

当前 Stage 1 rubric 是 **报告 15 + 视频 5 + interview 10 = 30 分**。每人有自己的 AH/UC/Activity/Interaction/State 链，参与**所有共享任务**并记录实际贡献。文件存在、AI 辅助评审、CI 通过都不等于本人已掌握、模型已验收或作业已提交。

A 保持报告/视频整合与实际提交责任；B 整合共享模型索引；C 提供分类、grounding/risk 材料并核验 R.04 证据。三人本人完成并解释各自个人任务。本次只澄清课程覆盖，不重新分配 A/B/C 的功能，不把课程 PDF 复制进 Git。

## 2. 官方来源与版本

| ID | 2026-09-14 核对的官方来源 | 主要用途 |
|---|---|---|
| CR-01 | [当前 Stage 1 rubric](https://canvas.sydney.edu.au/courses/74323/files/52560629)，PDF pp1–2 | 分值、个人/共享任务、视频、interview |
| CR-02 | [Project Description](https://canvas.sydney.edu.au/courses/74323/modules/items/3245780)，pp1–2 | One-Person AI Company、需求/设计、贡献、Stage 2 源码/演示 |
| CR-03 | [Lab 1](https://canvas.sydney.edu.au/courses/74323/modules/items/3245781)、[Lab 2](https://canvas.sydney.edu.au/courses/74323/modules/items/3133252) | 分组/范围；至少 3 个主要业务 AI 角色，每人 2 core + 1 optional |
| CR-04 | [Lab 3](https://canvas.sydney.edu.au/courses/74323/modules/items/3133253)、[Tutorial 3](https://canvas.sydney.edu.au/courses/74323/modules/items/3254036) | AH/Feature/UC、边界、正常/异常流程 |
| CR-05 | [Lab 4](https://canvas.sydney.edu.au/courses/74323/modules/items/3133254)、[Tutorial 4](https://canvas.sydney.edu.au/courses/74323/modules/items/3256736) | tutor checkpoint、viewpoints、控制/功能、设计取舍 |
| CR-06 | [Lab 5](https://canvas.sydney.edu.au/courses/74323/modules/items/3133255)、[Tutorial 5](https://canvas.sydney.edu.au/courses/74323/modules/items/3260045) | 模式/组件/交互及 FR/NFR 影响，类属性、方法、关联 |
| CR-07 | [Lab 6](https://canvas.sydney.edu.au/courses/74323/modules/items/3133256)、[Tutorial 6](https://canvas.sydney.edu.au/courses/74323/modules/items/3268054) | 对象实例图：具名实例、具体 slots、某时刻 links；区别于 structured-class parts |
| CR-08 | [Tutorial 1](https://canvas.sydney.edu.au/courses/74323/modules/items/3247782)、[Tutorial 2](https://canvas.sydney.edu.au/courses/74323/modules/items/3249287) | 展示/设计解释、Stage 2、真实 Jira timeline；设计/运行时模型 |
| CR-09 | [Requirement example](https://canvas.sydney.edu.au/courses/74323/modules/items/3249279) | 示例结构，不是 ReturnOps 的新增强制功能 |
| CR-10 | [报告 695832](https://canvas.sydney.edu.au/courses/74323/assignments/695832)、[视频 695833](https://canvas.sydney.edu.au/courses/74323/assignments/695833) | 当前可见时间；锁定正文仍需核对 |
| CR-11 | [2026 官方 Unit Outline](https://www.sydney.edu.au/units/ELEC5620/2026-S2C-ND-CC) | Stage 1 30%、Stage 2 20%；AI allowed 与 acknowledgement |

CR-01 原始 PDF 已保存并检查两页：121,372 bytes，SHA-256 `b331a715ee877532ff86e9ec5229a658c7c0dc2e56d72fe2ab184720329c4c18`。旧 Aug 31 本地版本为 143,649 bytes / `7a11f35fcccba4c956b20d2121d3c78f0e8d7c3e41bf2239826aca17ffabe871`，未覆盖。新版 Complex Structure 举例为 object diagram、collaboration；旧版还提 structured class。这不使现有 Composite 失效；CR-07 另明确要求 Object Diagram。

已读取当前 9 项 Lab & Project 与 Tutorials 1–6；除下载的 rubric 外，其余通过 Canvas 官方预览核对。部分原始 PDF/课程导出 ZIP 被浏览器拦截，不能声称全部二进制已下载。7 份 lectures 已盘点，未全部重新下载/全文阅读。尚未发布、锁定或后续更新的规则不在已核验范围。官方更新优先，出现真实冲突时记录日期/来源并核实，不自行猜测。

## 3. Stage 1 逐项覆盖

| 要求 | 分值 | 现有分工与提交证据 |
|---|---:|---|
| 每人 ≥1 个人 informal AH requirement | 0.5 | A AH-10、B AH-01、C AH-08；保留本人需求分析及真实贡献 |
| 全组综合 Feature diagram | 1 | B 整合，A/C 参与；整体功能/约束及每人具体部分 |
| 全组 overall Use-case diagram | 1 | B 整合，A/C 参与；整体角色、边界、use cases 与需求一致 |
| 每人 ≥1 UC specification；全组 5–10 个 | 2 | A UC-03/04，B UC-01/01E，C UC-02/05，共六个；前置/触发/结果/正常与异常流 |
| Elementary Structure / Class | 3 | A M-S.01 Owner，C Reviewer，B 参与；合适的类属性/方法、接口、关联与多重性 |
| Complex Structure / runtime structure | 3 | A M-S.02 Owner，C Reviewer/贡献者，B 参与/索引；协作/结构与 CR-07 对象实例快照，与类模型一致 |
| 每人 Activity | 1.5 | 各自 M-*.02，由本人 AH/UC 推导并解释 |
| 每人 Interaction | 1.5 | 各自 M-*.03，消息、顺序和主要异常路径清楚 |
| 每人 State Machine | 1.5 | 各自 M-*.04，明确对象/工作主体、状态/事件/守卫/动作 |

CR-01 p2 要求**完整项目需求文档随 Stage 1 提交**，后续设计与其一致；个人三种行为图必须基于本人的 AH/UC。brief 还要求需求分类、假设及设计/放弃方案的理由。最终须形成需求 → 模型 → 报告章节/图 → 贡献/版本的索引，不能只交一组孤立图片。

评分表将 Ad hoc diagram、Architecture Analysis and Design、Package、Deployment 标为 **Optional**。保留有用的现有模型和 Lab 4–5 设计说明，但不要说所有规划图都是 rubric 必选；可选评分行也不取消 CR-03 每人已选定的 optional **功能**。

### Object Diagram 放入既有共享结构任务

用既有类、一个明确逻辑时刻、具名对象、选定具体属性值和实例链接。可以是明确标注的**合成设计快照**，无需冒充已经运行。下划线 `objectName : Class` 与 slots/links 应区别于 Composite 的 `role : Type [multiplicity]`；普通对象链接不照搬类关联多重性。不能只改 Composite 标题来充数。

保留现有三个 Composite 视图。C 可提交 grounding/冲突实例切片供 A 整合；A/B 参与核对相关案件、界面、执行边界并保留贡献。选定 Founder 尚未决定的时刻，不应画出已经批准/执行的事实；区分内部 review 工作阶段与 RiskReview 结果。C 的片段不自动证明全组贡献或 M-S.02 验收。

## 4. 每个人不变的交付

| 成员 | Stage 1 个人链 | 共享参与与交接 | 后续功能实现 |
|---|---|---|---|
| A / shuxiachai | AH-10 → UC-03/04 → 执行 Activity/Interaction/OperationAttempt state → 本人讲解 | 主持类/复杂结构和设计整合；参与 Feature/overall UC；整合提交报告/视频 | A1 案件/Coordinator/Assessment/编排；A2 精确批准/受控模拟执行；A3 有实际接入前提的物流 test adapter/recovery |
| B / ChengsiLi | AH-01 → UC-01/01E → intake Activity/Interaction/IntakeSession state → 本人讲解 | 整合 Feature/overall UC/分类/全模型索引；参与 Class/Complex Structure | B1 intake/clarification；B2 Founder dashboard；B3 analytics |
| C / lulucas-tao | AH-08 → UC-02/05 → grounding/risk Activity/Interaction/ProposalReview work state → 本人讲解 | 分类/来源/风险一致性及对象实例贡献；评审 A/共享模型；R.04 核验；向 B 交分类表 | C1 版本化 retrieval/citation；C2 独立 Risk Reviewer；C3 稳定文本流程后的 image observations |

业务 AI 角色仍是 Coordinator、Returns Assessment、Risk Reviewer；确定性 Operations Service 不是额外 AI 角色。每人测试自己的功能，C 的评测/证据/Jira 工作不能替代 C1/C2。A3 接入条件由 A/tutor 如实处置，不能自动更换 optional 或重复认领核心 mock。

### 共享贡献表：记录实际，不填写计划比例冒充事实

CR-01 p2 要求每人参与所有 group tasks。对每个共享任务/图单独记录：

| 任务/图/版本 | A 实际部分及证据 | B 实际部分及证据 | C 实际部分及证据 | 整合核对/未解决项 |
|---|---|---|---|---|
| 每个 Feature、overall UC、Class、Complex Structure 等共享项分别填一行 | 待真实元素/修改/评审及 commit/PR | 待真实元素/修改/评审及 commit/PR | 待真实元素/修改/评审及 commit/PR | 准确整合版本，不代填签字 |

按 rubric 可标具体部分或真实贡献比例，保留原作者。45/27/28 是计划投入，不能代替实际贡献。实质评审按它真实做的事记录，不冒充他人图的作者。B 返回 C 分类表的精确整合链接；A 整合报告，三人分别确认自己的部分。

## 5. 视频、interview、AI 与提交

- 视频 **≤8 分钟 / 5 分**：项目、agent 角色、功能、UC、设计模型；brief/tutorial 补充解释选择/放弃理由与贡献。按当前作业规则上传；YouTube 链接是 rubric 的建议，不是必须，也不替代 Canvas 提交。
- Interview **10 分**：当前 rubric 指定 Week 11/12 practical，逐人提问；具体时段等待通知。A 录制视频不免除 B/C interview。倒序安排 submission 的描述不是已预约时段。
- 最终报告按实际阅读尺寸、视频按正常播放尺寸检查。保留可编辑/完整图，用清楚标号的概览/细节面板提升可读性；语法通过或存在 SVG 不足以证明成品清晰。
- Unit Outline 标注 Stage 1/2 **AI allowed**，必须 acknowledgement。如实说明辅助范围、来源、学生决定/修改及局限；仍按个人任务要求本人完成/理解/解释。不能生成虚假签字、工时、访谈或测试结果。
- 报告与视频 Canvas 页面均显示 **Sun Oct 4, 2026 23:59** 截止，**Sep 20 at 0:00** 解锁。页面未明确时区偏移；锁定正文、格式、group 设置尚未核验。解锁后由 A 核对、C 验证记录。
- Canvas 显示报告项 25 / 视频项 5 points，rubric 拆分 15/5/10；25 可能归组报告+interview，但目前不能确认。保留所有组成，必要时向 tutor 澄清，不取消 interview。
- 成品/访问核验与真实回执记录精确文件、版本及时间；A 提交，C 核对 R.04。发布、green CI、课程回执分别只能支持对应事实。

## 6. Stage 2 与 Jira 过程证据

CR-02/08 要求基于 Stage 1 模型的原型、合理的 LLM 增强及设计/实现说明，保留源码提交和 final-week demo。brief 写最终周周一之前交源码，不能从中编造当前未核实的 Stage 2 日历日期/详细 rubric。另核对后续 Canvas/tutor 要求。

Agile 过程包括真实 Jira timeline 与支持记录。沿用实际 delivery key、状态变化、问题/阻塞、review 和 GitHub commit/PR/test 链接，不倒填日期或因文档存在就标 Done。本文件不新建 Jira 卡、不改流程/权限；它不是第二份进度看板。

ReturnOps 的 **30 Gold**、**20-case timing subset**、独立 pilot、**B1 versus B4**、**p95 <120s** 是自己的冻结评测方案和目标，不是 Stage 1 全班统一配额或已测结果。遵守原有标签隔离/验证顺序，不在此扩大范围。Stage 1 不等 Stage 2 全系统/Gold 完成；按时如实提交，独立披露 F.01/F.02/模型内部未验收项。

## 7. 后续维护

Canvas/tutor 变化在此更新来源、日期、受影响条目，并同步 docs/11 对应 R.04 检查。保持 docs/00 产品、docs/07 分工、docs/08 工作包一致，不能为了关闭检查而改变冻结字段。Jira 保存真实过程，GitHub 保存技术交付。这份要求更新不代替任何成员本人确认。
