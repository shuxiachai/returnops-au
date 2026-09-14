# A3：物流测试环境资格与恢复能力预调查

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> `A3-PRE-0.1`，2026-09-07；**公开资料调查及验收准备，不是已获测试权限或适配器实现**。Owner A，Reviewer C；既有 [KAN-16](https://lucastaooo.atlassian.net/browse/KAN-16) 是 A3 交付上下文，本轮只读 board 可见其 Backlog/Flagged，未更改状态。
> A3.01 原 S=F.01；A3.02 原 S=A3.01、R.02，F=A2.05；A3.03 原 S=A3.02，保持 [工作包](08-delivery-work-packages.md)不变。当前只是允许提前开展的资格调查，不能跳过 S 依赖完成正式验收。

## 1. 当前结论与资料边界

Australia Post 仍是待核实的候选。官方 FAQ 说明 Shipping & Tracking 的申请资格涉及已有 eParcel 或 StarTrack parcels contract；通过资格核验后才取得 testbed 账号和凭据。testbed 是 stub 服务，返回合成数据和通用样例标签，不创建生产发货或账单；测试凭据与生产凭据的可用环境不同。[官方 FAQ：General / Developer Test Bed](https://developers.auspost.com.au/content/apis/shipping-and-tracking/info/api-resources/faq.html)

**组长在本轮明确回复“没有”合同及测试账号。**因此当前团队不具备已确认的 Australia Post / StarTrack 合同和测试访问条件，不能开始该 provider 的接入调用；将来是否能申请到合规访问仍未确定。普通开发者注册或学校邮箱不能替代资格。本轮没有注册、提交申请、读取凭据、调用 provider API 或创建任何外部 shipment/label。

| 2026-09-07 访问的官方页面 | 本轮可取得的内容 | 可以支持什么 |
|---|---|---|
| [FAQ](https://developers.auspost.com.au/content/apis/shipping-and-tracking/info/api-resources/faq.html) | 可读 General / Developer Test Bed 等正文 | 上述资格、测试环境性质与限制 |
| [Shipping & Tracking 入口](https://developers.auspost.com.au/apis/shipping-and-tracking/) | 访问成功但工具未取得正文 | 不能单凭空白提取验证申请流程细节 |
| [Get Accounts](https://developers.auspost.com.au/apis/shipping-and-tracking/reference/get-accounts) | 工具未取得正文 | 账号/产品参数须在有权限后按当前参考核验 |
| [Create Labels](https://developers.auspost.com.au/apis/shipping-and-tracking/reference/create-labels) | 工具未取得正文 | 不能据名称推断幂等、返回形状或费用保证 |
| [Get Shipments](https://developers.auspost.com.au/apis/shipping-and-tracking/reference/get-shipments) | 工具未取得正文 | 不能据存在 GET 就声称可由原稳定 key 恢复未知创建 |

本稿独立记录 A3 的运行提供方可行性，不扩写冻结的需求研究附录。不把 `Get Shipments`、tracking、泛化的标签样例与本项目的逻辑 CREATE_RETURN / GENERATE_LABEL 自动等同；适配器需明确映射和失败语义。

## 2. 先拿证据，再决定是否接入

| 必要能力 | 需要的具体证据 | 当前状态 / 不满足时处理 |
|---|---|---|
| 合法访问 | 合同资格确认、服务商测试授权与本项目使用范围；仓库只记非敏感引用 | 组长确认目前没有合同/测试账号；接入条件不满足，不索取密码或合同敏感正文 |
| 无生产/收费效果 | 明确测试环境、测试专用凭据、无真实收费/配送，配置允许列表 | 公开 testbed 性质有资料；团队没有已确认的测试账号，不启用调用 |
| 独立于核心 mock | 外部获准 testbed 的请求/响应和独立适配器代码 | 未实现；本地 mock 不能重复算 A3 |
| 逻辑动作可映射 | 单 order/多 line item/单 parcel，return 与 PDF label 的含义、顺序、参数来源 | 未核验；不能新增 manifest/付费动作来凑逻辑命令 |
| 防重 | 明确稳定请求身份的作用域、保留期、同 key/异参数冲突、并发处理 | 未核验；原 operation_fingerprint 是项目字段，不能假设 provider 能按它查询 |
| 未知恢复 | 原请求应答丢失后可找回原效果的身份；一致性窗口、最终无效果证据和迟到请求边界 | 未核验；普通 NOT_FOUND 不得开启重派 |
| 可重复故障演示 | 可控超时/丢响应/查询失败与无新增效果的证据 | 待接入设计；可在边界注入本地通信故障，但必须区分注入与外部真实响应 |
| 输出与隐私 | 合成输入、受控 PDF 获取、内容校验/大小限制、日志脱敏 | 待 F.04/F.07 与 A2；禁止把凭据放进 UI、模型、Git 或评审日志 |

如果团队没有合同或无法获准，首先把“该 provider 暂不可用”作为依赖事实保留，并准备 tutor 问题；不擅自把 A3 后置为 portfolio 或替换成第二个本地 mock。其他 provider 只有在保留 selected optional 的独立性、恢复能力和课程要求，并获得相应变更确认后才能替换。

## 3. 预备验收情境

以下仅是 A3.02/.03 的测试设计；没有实际运行结果：

| ID | 将来测试 | 成功条件 |
|---|---|---|
| A3-P01 | 有效测试授权下按精确批准执行一次 | 独立 testbed 返回可核对的测试引用/标签，provider/config 与批准一致，零生产收费 |
| A3-P02 | 同一操作双击/并发，以及同 key 改参数 | 只接受原精确范围；不能出现第二逻辑效果；冲突可追踪 |
| A3-P03 | provider 接受后丢失响应 | 本地保留原意图，按原身份查询；不生成新效果 key |
| A3-P04 | 查询暂不可见/失败、旧请求仍可能完成 | 留 UNKNOWN 或人工处理；不得把不确定写成 FAILED |
| A3-P05 | return 已成功而 label 未知 | 复用原 return，恢复原 label；不重放 return，也不改成另一个 provider |
| A3-P06 | 批准过期、输入变更或已人工收口 | 不派新效果；授权历史查询可保留事实，原 outcome/通知不被覆盖 |
| A3-P07 | 标签已创建但文件下载或本地保存失败 | 只恢复受控获取/存储，验证原效果引用与 PDF，不重新创建 label |
| A3-P08 | 通知失败 | 仅通知重试；不能再进入物流创建路径 |

每次记录实际 commit、接口参考版本、非敏感测试账号代号、provider 环境、输入 hash、原效果身份、响应/查询观察、预期与实际、C review。敏感值留受支持的本地环境配置；报告只附脱敏证据。对应 FR-009/010/011/012、NFR-002/004/007/008、OF-004、UC-04 和 [A 的恢复模型](12-member-a-model-chain.md)。

## 4. 待发送的 tutor 问题草稿

### 可继续核验的具体方向

本轮另查 [Shippo 官方认证说明](https://docs.goshippo.com/guides/authentication)：提供免费账号注册流程以及独立 test/live token，test token 可创建不收费的测试标签。因此它是值得继续做资格验证的候选，**不是已选替代或团队已获账号**。澳大利亚所需测试 carrier、账号实际开通条件、稳定 key 的防重与未知创建恢复仍未验证；尤其不因存在 test token 就宣称符合 A3 全部验收。本轮未注册或调用 Shippo。

若采用该方向，先完成上表资格/动作映射/恢复能力证据，形成具体替代说明，交 A/C 并就课程适配向 tutor 确认；不先接入再追认，也不降低原安全条件。

> Our selected A3 feature is an independent logistics sandbox/test adapter with recovery, separate from the core mock. The Australia Post documentation indicates contract-based eligibility, and our team currently has no Australia Post / StarTrack contract or test account. Would another independently authorised, non-chargeable logistics test service satisfy this selected optional feature, provided we preserve exact approval, idempotency, unknown-outcome recovery and evidence requirements? We will document a concrete proposed replacement and seek confirmation before changing scope.

这是提问草稿，**没有发给 tutor，也没有获得答复**。现有 A3 归属和验收保持不变。资格预调查已经得到“目前无访问条件”的明确结论；正式 A3.01 接受仍需 F.01 和 C 的评审，A3.02 不能以本稿代替合法测试权限。
