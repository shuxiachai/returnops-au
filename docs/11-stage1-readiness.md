# Stage 1：当前阶段收口与提交核验

> 2026-09-07；状态：**准备与核验清单，未完成 Stage 1 验收**。
>
> 沿用 [固定分工](07-frozen-work-allocation.md)与[89 项 WBS](08-delivery-work-packages.md)，不新增功能或重新分配个人贡献。
> 报告整合与提交行动由 A 主持；视频由 A 后续自行录制、整合与提交，B/C 提供并确认自己的章节、模型及贡献说明和所需素材。R.04 证据核验仍为 C Owner、A Reviewer。

F.01 `1.0.0-rc.4`、`MA-0.2` 与 `CS-0.1` 是当前评审候选；[KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)追踪契约，KAN-13 追踪 A 的个人/共享模型。[PR #11](https://github.com/shuxiachai/returnops-au/pull/11)为本次评审入口，具体提交及 CI/review 以该 PR 为准；[PR #9](https://github.com/shuxiachai/returnops-au/pull/9)仅记录 rc.2 历史发布。候选仍须联合评审，发布记录不能代替本人贡献、B/C 同意、tutor 接受或课程提交记录。

**按时课程提交与项目验收分别记录。** 以下 R.04 子检查可逐项用于 Stage 1 提交，不要求整张 R.04 Done、R.01 正式采纳或 F.01 接受后才允许提交。A 应按实际 Canvas 截止提交如实标注候选/未完成项的材料，C 核对文件、访问权限和回执，保留未解决事项。不得因项目内部验收尚未闭环而延误课程要求的提交。R.05/E.12 的 Stage 2 最终交付与正式评测不是 Stage 1 提交前置条件。

Stage 2 也须分别核对源码提交与演示：docs/08 的 R.05.a/.b 沿用同一工作包，课程原件规定最终周周一之前交源码、最终周演示，实际日期仍待 Canvas/tutor 核验。按时提交不以内部 R.05 Done 为前提，回执不替代功能验收。

## 1. 课程依据与待核验信息

课程原件保留在课程目录，不复制 PDF 进 Git。以下页码为 PDF 页码；准确日期、时区、提交入口、文件格式和修改规则仍以最新 Canvas/tutor 通知为准，本轮未访问 Canvas。

| 原件 | 本清单采用的要求 |
|---|---|
| `ELEC5620_Project_Stage_1_Marking_Criteria.pdf`，第 1 页 | 5–10 个用例；共享 Class 与 Complex Structure 各 3 分；视频不超过 8 分钟、5 分；个人 interview 10 分，在 Week 11/12 practical 逐人提问 |
| 同上，第 1–2 页 | 每人的 Ad-hoc requirement、Use Case、Activity、Interaction、State 模型形成同源链；每人参与共享任务并明确个人贡献 |
| `Project Description.pdf`，第 1–2 页 | 报告、presentation 和个人贡献；第 2 页要求说明采纳/放弃的设计、模型概览、变更/验收和个人贡献；Stage 2 源码须最终周周一之前交 Canvas，演示在最终周 |
| `ELEC5620-Lab-Note-5.pdf`，第 1 页 | 设计模式与优缺点对 FR/NFR 的影响，类属性/方法及关联多重性核对；不由此推断新的提交日期或全部图的硬性要求 |
| `lecture&tutorial/ELEC5620-TUT-01.pdf`，第 18 页 | Stage 2 的 Agile 过程包含 Jira software timeline evidence 与支持文档；需持续保留真实记录，不能以最后补一张看板代替过程 |

brief 的 presentation slides 内容要求与 rubric 的 ≤8 分钟视频要求一并核对；是否另交 slides、具体格式和入口仍待 Canvas/tutor 确认。Package/Deployment、Architecture Analysis 在 rubric 标为 Optional，但 Lab 4/5 的架构分析与设计练习仍需对应说明，不把可选评分项误写成无需设计。

## 2. 当前成果与未闭环项

- 已有需求、六个详细用例和共享 Class/State/Sequence/Feature/Use-case 草稿；rc.4 沿用三种决定目标并进行本轮契约缺陷修订，仍需人审，不能用机器 Schema 代替 UML。具体修订、兼容性与静态验证范围以 docs/09 和实际文件版本为准。
- A 的 [MA-0.2 个人链](12-member-a-model-chain.md)在规格核验、Activity、两个 Sequence 面板、OperationAttempt 七态图及静态走查上修订本轮发现的恢复/通知等路径问题；仍需 A 本人修订/解释、C 人审、设计未决项处置和 F.01 接受。修复候选不等于已运行系统或 C 的认可。
- 共享 [CS-0.1 复合结构](13-shared-composite-structure.md)现有三幅内部结构视图、29 条连接及契约表、十二个静态走查；Class/Package/Deployment 的完整核验、B/C 共享贡献确认、原依赖与人审仍待完成。已有文件不等于模型已验收。
- B 的 PR #8 和 C 的既有材料须保留来源，并由本人核对、修订及提交；尚未取得本人确认的材料不能计为其完成。
- B/C 个人链、共享模型的最终一致性、报告/视频成品、个人 interview 准备和真实提交回执均按下面清单补证据；本轮未完成 Stage 1 报告/视频成品或课程提交，不因已有文件名而勾选完成。
- A3 的无收费 sandbox/test 资格与可行性证据仍待核验；记录提供方、测试权限、费用边界、查询/恢复能力和已知限制。无法取得时由 A 记录依赖并申请 tutor 处置，不把核心 mock 当作选定 optional 已完成。

**A3 官方资格调查（调查日期：2026-09-07）：** Australia Post 的 [Shipping & Tracking Getting started](https://developers.auspost.com.au/apis/shipping-and-tracking/) 与 [FAQ](https://developers.auspost.com.au/content/apis/shipping-and-tracking/info/api-resources/faq.html)说明，申请需要现有 Australia Post/eParcel 或 StarTrack parcel contract；testbed 使用 stubbed services、虚构样例公司和通用/水印标签，不创建生产发货或计费。团队合同、申请授权和测试凭据均未核验，普通学生账号不等于已有 testbed 权限。本次未注册、登录或调用 API，仅完成资格调查，不是 A3 实现或验收；不能通过生产调用或重复认领核心 mock 满足 A3。若无法合法访问，须记录依赖并向 tutor 确认可接受的处理，不能自动替换 selected optional。

## 3. R.04 的 Stage 1 子检查

下面的 `R.04.a` 等只是既有 R.04 的可审查子检查，不是新增独立大包或要求逐项新建 Jira 卡。**C 核验他人的证据，不接收他人成果的作者署名；A 整合作品也不代替 B/C 的个人贡献。**各原 WBS Owner/Reviewer 保持不变。

| 子检查 | 制作/行动责任与原 WBS | 具体输出及验收证据 | 确认人 |
|---|---|---|---|
| R.04.a 提交要求 | A 核对 Canvas/tutor，B/C 核对个人安排 | 当前截止日期/时区、入口、文件规则、视频方式、interview 时段及来源记录；未知项明确保留，不从旧 Jira 日期推定 | A 记录，C 核验来源，B/C 确认个人时段 |
| R.04.b 契约与未决项 | A 制作 F.01；C 指定 review；B 确认消费边界 | rc.4 三目标、无提案只人工处理、订单阻断与来源冲突及本轮缺陷修订逐项有人审；版本、问题处置、测试与 KAN-32/后续实际 PR 可定位；未发布/未接受项在课程材料中明示 | A/B/C 分别确认核对范围；tutor 反馈单独记录 |
| R.04.c 三条个人链 | A/B/C 各自完成 M-A/M-B/M-C.01–.06 | 本人的 requirement→UC→Activity→Interaction→State→报告段落/答辩说明；正常及主要异常场景走通，具体提交、图版本和修正记录可查 | M-A：C；M-B/M-C：A；本人能独立解释 |
| R.04.d 共享模型 | A：M-S.01/.02；B：M-S.03；C 提供分类/风险追踪核对 | Class/Package/Deployment 的适用范围与状态清楚；Composite Structure 有 ports/connectors；Feature/Use-case/全模型索引一致；每人共享贡献可定位 | M-S.01/.02：C；M-S.03：A；三人确认本人的贡献 |
| R.04.e 报告 | A 整合；B 用户交互/个人章节；C 来源摘要/风险/评测；各自 M-*.06 | 可阅读的报告候选及逐条 rubric→章节/图/作者索引；来源/假设摘要约 1–2 页；目标、规划、实现和实测分开；未决项未隐藏 | 各作者确认自己章节，C 核对证据完整性，A 确认整合版本 |
| R.04.f 视频 | A 后续自行录制、整合、导出与提交；B/C 提供并确认本人模型、贡献说明和所需素材，本轮不要求录制 | 最终视频≤8分钟；画面/模型/文字可读，声音可懂；包含设计取舍、模型概览、变更/验收、个人贡献；记录成品名、时长、版本和提交回执/可访问性结果 | 三人看完整成片并确认个人段落；C 核验成品与提交证据，A 执行提交 |
| R.04.g 个人 interview | 各成员本人准备与参加，关联各自 M-*.06 | 每人可脱离他人代答解释个人链、共享贡献、异常守卫、设计取舍与未实现内容；完成一次互问记录，时间以实际通知为准 | 本人负责；A/B/C 互问，C 汇总准备证据 |
| R.04.h 提交后核验 | A 按实际课程规则提交；C 核验 | 从提交入口重新打开报告/视频或获准链接，核对正确版本、可播放/可下载、截止前回执；记录未决项和允许补交/修改规则 | A 确认提交内容；C 独立核验；各作者确认贡献记录 |

R.04 的整体 Done 仍受 docs/08 原有完成依赖约束；子检查的提交回执只证明相应文件已提交，不证明全项目采纳、实现或评分结果。

## 4. 报告与个人模型检查重点

- [ ] 需求分类、Ad-hoc/Feature/Use-case 视图与当前产品边界一致；六个详细 UC 覆盖课程要求的 5–10 个，正常/异常路径、前后置条件和验收清楚。
- [ ] 每人 .01 规格、.02 Activity、.03 Interaction/Sequence、.04 State、.05 一致性、.06 报告/答辩证据逐项可定位。不能用 ReturnCase 共享状态图冒充三人的对象生命周期。
- [ ] 共享类图有适用的属性/方法、关联、继承、组合/聚合、接口和多重性；Composite Structure 的对象/协作/结构化类与 ports/connectors 可解释，不能只换标题充数。
- [ ] A 的执行链、B 的 IntakeSession、C 的 ProposalReview 与 F.01 版本一致；人工决定、风险结果、未知效果核实和通知重试的边界互相吻合。
- [ ] 对设计模式和架构取舍说明“为何选、为何不选、影响哪些 FR/NFR”；不把 Package/Deployment 等项目选择一律写成 rubric 强制项。
- [ ] C 的来源摘要引用冻结研究证据；30 Gold、20例盲计时子集、独立 pilot 是计划或实际结果分别标注。C 读取任何计时答案前须按 E.02 密封初始标签/理由及版本/hash，不提前向 A/B 公开；之后按 E.05→A 复核→B 仲裁→最终冻结评分，修改保留依据，不能按被评分答案调整标签。Stage 1 不等正式评测已经运行。
- [ ] 各图与章节明确作者/贡献、版本、review和待办；AI辅助、组长整合、既有PR来源如实记录，不能替代本人理解、修订、提交与讲解。

## 5. 下一项主工作与容量预约

实际估时、每周可用时间、课程截止和评审时间尚未获成员/Canvas确认。以下空缺必须由当事人提供，不能按45/27/28倒推工时或编造日期。每人仍只领取一个主要 In Progress 项，其他准备保持小型可审查范围。

| 成员 | 下一项主工作 | 可并行的小准备 | 实际估时 | 每周可用时间 | 已预约 review 时间 | Canvas 截止/个人时段 |
|---|---|---|---|---|---|---|
| A | 审阅并亲自完善 MA-0.2 / CS-0.1，提交 C 走查；同步处置 F.01 rc.4 本地缺陷修订与评审 | F.02 原生 PG 与 Docker/PG17 构建、迁移、健康及断库恢复验证通过；C 复现和实际 CI 仍待。A3 资格调查、Package/Deployment 按原依赖推进 | 待 A 填写 | 待 A 提供 | 待与 C/B 预约 | 未核验 |
| B | M-B.01 与 PR #8 来源/剩余个人链的对应核对 | 完成 F.01 前端消费确认；准备本人报告/视频内容提纲 | 待 B 填写 | 待 B 提供 | 待与 A 预约 | 未核验 |
| C | F.01 指定评审并提供明确问题/确认 | M-C.01 自检、R.04证据索引；不提前公开Gold标签 | 待 C 填写 | 待 C 提供 | 待与 A/B 预约 | 未核验 |

建议先预约一次 A/B/C 契约走查，再为三条个人链安排原 Reviewer 的检查时间；这只是待接受的预约顺序，不是已承诺日期。课程提交临近时，优先完成可提交材料及真实未决项说明，不等待运行 API、Docker、LLM 或正式 Gold 结果。

交付时沿用 docs/07/08 的最小评审包：WBS/实际 Jira key、具体 commit 或文件版本/hash、相关 FR/NFR/UML、可复现证据及未决项。候选未提交时明示本地状态，不编造 PR/CI/本人确认；原 Owner/Reviewer、一个主要 In Progress 和既有变更触发保持不变。

## 6. 收口记录

每次实际核验在获授权的对应 Jira/PR 留下：WBS/子检查、文件或成品版本、实际作者、核验者、时间、问题及处置、运行/渲染/提交证据；本次候选的发布和技术检查以 PR #11 的具体提交及运行记录为证，未代填本人确认。R.04 由 C 维护证据核验结果，A 主持 Jira 操作维护；每人提供自己的真实进度。Stage 1 提交后继续保留未接受的 F.01、个人/共享模型问题和 tutor 反馈，按原依赖推进；不因回执自动宣称 R.05 或课程已验收。
