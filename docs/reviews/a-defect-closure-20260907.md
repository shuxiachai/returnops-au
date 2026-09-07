# 六项缺陷修订记录

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> `A-FIX-0.1`，2026-09-07；授权：“修正”。基于本地 HEAD `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577` 及此前未提交准备材料；本轮没有 commit、push、merge、Jira/权限修改或代签成员 review。

当前本地候选为 **F.01 rc.5 / MA-0.3 / CS-0.2 / AD-0.2 / PD-0.2 / F03-D0.2**。PR #11 的已发布 rc.4/MA-0.2/CS-0.1 及旧 CI 留作历史；新修正不由旧 run 覆盖。字段形状、15 个公共操作、七个 OperationAttempt 状态、1-based 计数未采纳状态、九功能和 89 项 WBS 固定分工/依赖不变。

## 1. 修正与验收边界

| 缺陷 / 原追踪 | 本地修正 | 对应验证 |
|---|---|---|
| 标签 provider 成功与本地制品成功混淆；F.01/A2，FR-010/011，NFR-002/004 | [AD](../14-member-a-design-decisions.md)、[MA](../12-member-a-model-chain.md)、[CS](../13-shared-composite-structure.md)及共享模型：原效果 receipt 持久化，制品待存保持 EXECUTING，恢复仅取回/存原 label；完整结果保存后才 SUCCEEDED | 图/文档/Schema 一致性与完整/缺附件结果的离线反例；业务恢复未实现 |
| 删除后原 POST 回执恢复正文；F.01/F.03/F.07/A1，FR-001/011/012，NFR-003/004 | [契约第 7 节](../09-interface-contract-v1.md#7-版本审批和幂等)、[身份设计](../16-demo-identity-authorization.md)及六个 POST：保留最小受理事实，回执正文不可用时 409 INVALID_STATE / retryable=false，无再次执行或自动换 key | [rc.5 测试](../../tests/contracts/test_contract_v1_rc5.py)检查已接受澄清→删除→重放情境和合法错误 DTO 内原文泄露；真实 retention/idempotency 仍待实现 |
| Composite 缩进连接被静默漏检；M-S/F.02，FR-009/010/011，NFR-002/006/007 | [检查器](../../tools/model-checks/check.py)解析缩进及紧邻分隔符；疑似不支持的连接显式失败，保留登记和权限邻接检查 | 空格/Tab、未登记边、已登记越界边、错误箭头反例 |
| Compose healthcheck 受代理影响；F.02，NFR-006/007/008 | [Compose](../../compose.yaml)本机 readiness 显式绕过代理 | [实际 probe 回归](../../tests/environment/test_compose_healthcheck.py)：临时 HTTP 的 200/503、合成代理；不启停项目容器 |
| C 复现未固定实际 Docker endpoint；F.02，NFR-006/007 | [复现包](f02-independent-reproduction.md)拒绝 endpoint 覆盖变量、核验本地 endpoint/Linux engine，并固定同一 context 贯穿操作 | PowerShell 假 Docker 校验拒绝覆盖/远端/endpoint 变更，启动和收尾固定 context；不是 C 的真实执行 |
| docs00 RUNNING 与 Schema EXECUTING 不同；F.01/M-A，FR-010/011，NFR-006/007 | [产品词汇表](../00-project-definition-v1.md)统一 EXECUTING；检查器同时比较词汇表/Schema/MA | 反向改回 RUNNING 的回归必须失败 |

上述修正解决本次明确的材料/工具缺陷，不代表 F.01/F.02、模型本人贡献或运行安全已验收。并发/外部调用事实、尝试计数方案及 F.03/F.07 内部实现仍按原工作包处理。

## 2. 本轮验证

在当前本地修订实际执行：

```powershell
.venv/Scripts/python.exe -B tools/checks/run.py offline --baseline-ref main
.venv/Scripts/python.exe -B -m pytest tests/environment -m 'not database' -q -p no:cacheprovider
git diff --check
```

- 完整 offline 5 个步骤全部通过：**56 项契约、6/6 静态组、12 项模型工具回归、5 项 runner 回归、15 个 Mermaid 块**。当时静态组读取 31 份 Markdown / 339 个现有本地目标；随后只补本记录/验证导航，再核对文档/模型与差异。
- 89 项 WBS ID/Owner/Reviewer/S/F 相对 main 不变且无环；9 对 PUML/SVG 嵌入源匹配；MA 21 情境/41 动作/七态同时符合 Schema 和产品词汇；CS 3 图/29 连接/13 情境，五条已命名权限邻接约束通过。
- 环境子集 **28 passed、4 database deselected、2 既有弃用 warnings**（Starlette TestClient/httpx、AnyIO BlockingPortal）；包含新 200/503 实际健康命令代理回归。未重建或启停现有容器、未迁移数据库，不能记为新 32 项全量数据库/Compose 通过。
- 9 幅 PlantUML 实际重渲并逐图查看 PNG；修正 Activity 一处分支泳道可视歧义。状态图自环较密但文字可读。根代理另查看完整状态图与恢复序列。预览保存在忽略目录 `tmp/model-rc5-qa/`；这些渲染结果不同于 Mermaid 的纯语法检查。
- 独立交叉审查纠正澄清回执为 UNDER_INVESTIGATION，并确认把应有的 409 改为 403 会被检查拒绝。Schema 校验结构和 OpenAPI 路径/角色/响应定义相对 HEAD 未改变，仅版本/语义说明及合成反例变化；样例现为 86 正例、46 负例、21 **未执行**运行情境。

完整 offline 日志为忽略目录 `tmp/a-defect-offline-20260907.log`，SHA-256 `175e9a5d58a56feb96862fa44d179f6c60cbab3432644542cdf88a85e9d8e666`。日志和临时 PNG 不作为远端 CI 或人审证据。新标签/删除后重放情境依然是运行验收规格；本轮验证的是材料一致性及实际工具/环境探针行为。

## 3. 发布与剩余依赖

发布必须使用包含修复的准确提交；C 复现包已拒绝把旧 `57d86fe` 当修复版本。C 本人复现、B/C 指定 review、A 对候选的理解和确认仍待完成。F.01 接受后按既有 S/F 推进集成；不新增全项目前置门槛。

上一轮只读实查的 Jira KAN-32 仍为 rc.2/PR #9，F.02 主卡仍待核实；本轮没有写 Jira。后续同步应以届时实际已发布版本为准。Canvas 的锁定正文/上传规则与评分口径差异、A3 合同/测试账号缺失继续保留，未因修订文件而解决。

[上一轮 A-PREP-0.1 准备记录](a-preimplementation-readiness-20260907.md)与其哈希是历史快照，不能再用于证明当前修改后的字节。[本轮 SHA-256 清单](a-defect-artifacts-20260907.json)记录当前未发布仓库改动的原始字节，包含保留的上一轮准备；排除本索引和清单本身以避免自引用。若未来发布规范化换行，需按最终提交重新记录；课程根交接记忆仍留本机。

## 4. 提交字节与发布记录

组长后续授权“推送”。发布内容保留全部修正及此前准备，未修改业务实现、固定分工、课程原件或成员署名。发布前将历史状态说明与当前提交分开；历史 A-FIX/A-PREP 哈希不再代表经换行规范化的 Git 字节。[本次 Git blob SHA-256 清单](rc5-publication-artifacts-20260907.json)按暂存对象生成，排除自身以避免自引用；可用 `git show <review-sha>:<path>` 的原始字节复核。PR #11 保存准确提交和实际 CI 结果。C 的干净复现与 B/C 的正式评审仍待本人完成；本记录不代签。
