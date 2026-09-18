# A 当前阶段准备交付记录

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> 历史快照说明：以下 A-PREP-0.1 记录对应上一轮准备及当时哈希。随后“修正”授权形成 [A-FIX-0.1](a-defect-closure-20260907.md)，当前已是本地 rc.5/MA-0.3/CS-0.2 等修订；以下“原图/契约未改”、旧计数及哈希不得当作当前字节或本轮结果。


> `A-PREP-0.1`，2026-09-07；本轮授权来源：“按照你的顺序完成任务”。这是一次交付/证据记录，不是另建实时状态看板。新成果保存在本地，未提交或上传；已有 PR #11 的发布与 CI 单独记录。

## 1. 按约定顺序完成了哪些准备

| 顺序 / 原 WBS | 已交付的可核验成果 | 正式完成仍缺什么 |
|---|---|---|
| 1 / F.01、M-A.01 | [AD-0.1 设计决定包](../14-member-a-design-decisions.md)：尝试 ID/计数、查询阶段、跨批准边界、并发、source receipt、审计及附件；12 个待实施反例 | A 本人解释和选择、对应 B/C review。计数方案未改 rc.4；MA-Q02/.03 没有冒充运行证明 |
| 2 / M-S.01 候选 | [PD-0.1](../15-package-deployment-models.md)：Package/Deployment 两对可编辑 PUML/SVG，12 包映射、12 场景、真实环境与计划业务区分 | F.01 及三人规格前置接受、A/C/B 对应模型评审；B 的最终模型索引仍由 B 整合 |
| 3 / F.02 | [独立复现包](f02-independent-reproduction.md)与[环境证据](../10-f02-environment-readiness.md)：精确已发布 head/CI、隔离复现步骤及填写模板 | C 实际干净复现与非作者确认，F.01 接受、实际 F.02 Jira key；本轮没有把 A/AI 复跑冒充 C 的结果 |
| 4 / M-A.06 准备、R.04 的 A 贡献 | [个人 Stage 1 草稿](../reports/member-a-stage1-draft.md)及[课程清单](../11-stage1-readiness.md)：三个讲解场景、模型/取舍/真实贡献及视频材料；核验 Canvas 入口 | A 改写并掌握，B/C 自己的材料，C 的证据审核；实际提交/录制未发生，原 S/F 仍适用 |
| 5 / F.03 准备 | [身份与权限设计](../16-demo-identity-authorization.md)：15 操作角色/资源矩阵、会话来源、history/cursor/附件边界、12 个负向情境 | F.01 接受后开始集成，F.02 是完成依赖；算法/会话参数及内部实现需正常评审，不新增公开登录端点 |
| 6 / A3.01 预调查 | [A3-PRE-0.1](../17-logistics-sandbox-feasibility.md)：官方资格/恢复能力清单、8 个预备情境及未发送 tutor 问题；组长确认无合同/测试账号 | 当前 Australia Post / StarTrack 接入条件不满足；替代方向未采纳、未注册；原 selected optional 与验收保留 |

四位 AI 协作完成起草/检查的事实不等于四名项目成员；项目仍只有 A/B/C 三人，原九功能、45/27/28 计划比例及 89 项 Owner/Reviewer/S/F 不变。B/C 的个人成果与人审不可代签。

## 2. 本轮实际查询到的外部状态

### GitHub

2026-09-07 11:55 UTC 只读复查：[PR #11](https://github.com/shuxiachai/returnops-au/pull/11) Open、非 Draft，head `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577`，B/C 仍为 requested reviewers，reviews 为空；main 仍 `9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf`。两次已有 CI run、四个 job 成功，见 [F.02 证据](../10-f02-environment-readiness.md)。本轮新增文件不是这些历史 CI 的测试对象；本地验证另列。

### Jira

通过当前 Chrome 登录会话只读查看 [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32)、项目 board/list 及 [KAN-14](https://lucastaooo.atlassian.net/browse/KAN-14)：

- KAN-32 仍为 In Review，标题/说明是 rc.2，GitHub Link 指 PR #9；与当前 GitHub rc.4 / PR #11 评审入口存在明确漂移。
- KAN-14 明确仅为 A1.01–.03、F.05 的实施 umbrella；F.02 在其中是依赖说明，不是 F.02 的执行主卡证据。
- board 可见 KAN-12/13/28/32 为 In Review，KAN-17 为 In Progress，KAN-22 为 Ready，KAN-14/15/16 等为 Backlog。只作为本次读取快照，不能推断各人已开始/完成全部工作包；现有估算/日期不当作当前课程期限或本人承诺。
- 未取得 F.02 实际执行 key 的直接证据。board 存在按列加载、list 显示折叠父项的范围限制，本次有限查看不能证明没有相应卡；不猜 key、不重复建卡。

下一次经授权维护时，KAN-32 应保留 PR #9 的 rc.2 历史，改当前 review 入口为 PR #11/rc.4 及实际接受清单；F.02 先检索核对执行主卡，再附真实 CI/复现证据。本轮没有编辑卡片、日期、权限或发评论。

### Canvas

组长提供 [ELEC5620 Assignments](https://canvas.sydney.edu.au/courses/74323/assignments)，本轮经登录 Chrome 查看列表及两个详情：

| 条目 | 详情页可见截止 | 开放/访问边界 | 显示分值 |
|---|---|---|---|
| [Stage One Report Submission](https://canvas.sydney.edu.au/courses/74323/assignments/695832) | Sun Oct 4, 2026 23:59 | locked until Sep 20 at 0:00 | 25 Possible Points |
| [Stage One Video Presentation Submission](https://canvas.sydney.edu.au/courses/74323/assignments/695833) | Sun Oct 4, 2026 23:59 | locked until Sep 20 at 0:00 | 5 Possible Points |

页面未显式显示时区；按页面显示记录，不擅自换算为 AEST/AEDT/UTC。正文与上传设置受作业锁定限制，文件格式/大小/组提交规则/评分细项仍待开放或 tutor 说明。列表显示尚无 submission，详情的 Attempt 1 不是提交回执。当前列表未提供 Stage 2 作业项，不据此推断免交。

Canvas 的 25/5 与本地 brief/rubric 的 15/15（report/presentation+interview）口径存在差异；须核对真实评分安排，不能自行取消 interview 或修改冻结分工。实际课程核验与提问入口集中在 docs11，避免用 Jira 旧计划日期代替。

## 3. 本轮检查与可复现定位

本轮唯一工具行为修订是：Composite 专用解析限制为 `*-composite.puml`，避免把新增 Package/Deployment 错算作 CS 视图；通用源图/SVG 同步检查仍覆盖所有 PUML。新增回归证明其他共享图不增加 CS 数量，也不能掩盖缺失的受保护 Composite 图。关联 FR-011、NFR-006/007，M-S.01/.02；不是业务安全实现。

2026-09-07 在基于 `57d86fe` 的本轮工作副本执行：

```powershell
.venv/Scripts/python.exe -B tools/checks/run.py offline --baseline-ref main
.venv/Scripts/python.exe -B tools/model-checks/check.py --baseline-ref main
git diff --check
```

完整 offline 的 5 个步骤通过：53 项契约、6/6 静态组、8 项模型工具回归、5 项 runner 回归、15 个 Mermaid 块。静态组覆盖 89 项 WBS 固定字段相对 main 不变、无依赖环、9 对 PUML/SVG 内嵌源对应、MA 19 场景/37 动作/七态、CS 3 图/29 连接/12 场景。只追加交付索引/记忆文字后另复查文档/模型与差异格式；未重复启动数据库或冒充新远端 CI。

新增 Package/Deployment 已实际本地渲染并逐图查看完整 PNG，源图/SVG 对应成功。独立检查还验证 C 复现文档的 5 个 PowerShell 块语法、4 段 Python 编译；这是命令片段静态验证，不是执行 C 的完整复现。交叉审查修正了 F.03 身份撤销参与授权协调、label 原始观测与完整 OperationResult 的区分。

[21 个交付文件的 SHA-256 清单](a-preparation-artifacts-20260907.json)定位本轮本地字节版本，排除本索引和清单自身以避免自引用；实际发布若规范化换行需重算。完整 offline 本地日志在忽略目录 `tmp/a-preparation-offline-20260907.log`，SHA-256 为 `88aa4880ac2984fe267d17cb13f750184af85171eb9ac0fd5e869643fd1dfd2c`；它不是远端可访问运行。

任何运行守卫、AUTH/AD/A3 情境都继续是待执行规格，不算为已通过产品测试。课程 PDF、临时 PNG/JAR、环境与密钥不纳入交付。既有 rc.4 Schema/OpenAPI/样例、MA/CS 原图及业务运行代码没有改动。

## 4. 交给真人的最小下一步

1. A 先读 AD-0.1 第 2–5 节并用三个场景讲解；对 1-based 尝试序号给明确选择。接受后才协调下一 rc，不改已发布 rc.4 的含义。
2. B/C 对精确版本完成消费/模型评审，C 按独立复现包补真实结果。现有 PR 已请求评审，本轮未重复催发或代签。
3. A/C 核实 F.02 主卡；课程开放后核验时区、上传规则及 25/5 与 15/15 的评分差异。A3 无账号的事实已明确，按具体候选资格与 tutor 反馈决定后续，不立即接入。

F.01 接受后按原依赖推进 A1.01 与 F.03；之后形成无 LLM 的固定提案→审批→受控模拟执行闭环，再做 R.02。没有因环境 CI 成功提前接 Agent 执行链。
