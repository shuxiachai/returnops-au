# F.03 独立身份与权限组件候选

> **最新发布定位覆盖 · F03-C0.1 · 2026-09-15。** 本组件通过 [PR #15](https://github.com/shuxiachai/returnops-au/pull/15) 交付；F.03 主卡为 [KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34)，状态 **In Review**。准确的当前源码 SHA 和对应 CI 结果以 PR 正文及其 [GitHub Actions 记录](https://github.com/shuxiachai/returnops-au/actions)为准；本段覆盖旧的“本地／尚未发布／Jira key 未核实”快照。旧准备收据及首次发布的 CI 记录仍只证明各自对应版本，不随后续文档提交改写或自动延伸。
>
> 准确 F.01 基线仍为 A `3dd1ff637693a826990eee5712cfb239a3c3da7b`，分支为 `feat/f03-security-component`。A 实现，C 为指定 Reviewer，B 后续验证浏览器消费。S=F.01、F=F.02 保持不变；没有接入业务 HTTP 路由、数据库或完整工作流。发布及 In Review 不代表 C 本人复核或 F.01/F.02/F.03 已接受。

## 1. 已实现的边界

代码位于 [security 包](../apps/api/returnops_api/security/)，沿用 [F03-D0.2 设计](16-demo-identity-authorization.md) 和 rc.5 契约：

- `Authenticator.authenticate` 验证显式 Bearer JWT 的签名、固定算法、issuer/audience、必需声明和时间窗口；每次从 `IdentityStore` 读取主体与会话的当前一致快照。
- `PrincipalRecord`、`SessionRecord` 与 `IdentitySnapshot` 是内部可信登记，不能由请求正文构造。必须验证 sub、jti、主体启用状态、会话撤销状态及完全一致的 iat/nbf/exp；token 自报的 role/store/owner 不授予权限。登记查询期间过期的会话也被拒绝。
- `VerifiedPrincipal.session_view()` 只投影现有 `Principal {principal_id, role}`。它不是 `/v1/session` HTTP 路由，不签发 token，不提供登录或角色切换。
- `AuthorizationService.authorize` 每次先重新认证，再检查十五个 operationId 的角色矩阵，最后解析可信资源关系。客户只能读自己案件；Founder 只在登记的商店范围内访问 Founder 操作，也不能调用客户专属接口。
- operation/notification 必须反查其权威 case 关系；STAGED 附件只归上传者，BOUND 附件由案件关系授权，GENERATED 制品不伪造客户上传者。不可用、到期、跨店或断裂关系均拒绝。
- `AccessGrant` 明确携带本次检查的商店、案件和资源范围；列表/统计也不能丢失 store scope。所有返回记录不可变，且不含 bearer token。

这些接口没有业务写方法、审批生成或 provider 调用。测试使用一个合成 Founder、两个合成客户及资源 doubles；没有创建真实登记、读取 `.env`、签发可使用的演示凭证或启动服务。

## 2. 本轮明确的内部候选选择

| 选择 | 实际实现及限制 |
|---|---|
| 库和算法 | `PyJWT==2.13.0`，固定 `HS256`，不根据 token 选择算法或密钥，不读取远程 JWKS。新增依赖已写入 runtime/dev 哈希锁，其余锁定版本不变。 |
| 私有密钥 | 构造时注入 32–128 bytes；未来受控配置必须使用高熵随机值。长度检查不等于熵证明。密钥不进入 repr 或普通诊断；本轮仅在测试内存生成随机 key。 |
| 时间 | 默认且至多 900 秒，时钟容差默认且至多 5 秒；要求整数 iat/nbf/exp、iat≤nbf<exp、exp−iat≤最大期限。exp 等于当前时间减容差时拒绝。登记时间与 token 精确绑定，不允许 token 延长或替换登记会话。 |
| 声明与 JOSE header | 必须有 iss/aud/sub/jti/iat/nbf/exp；sub/jti 遵守现有 Id 格式。aud 必须是精确单字符串；header 仅接受 alg/typ 且 typ=JWT。kid/jku/jwk/crit 等元数据不进入此单密钥候选。 |
| 轮换与重启 | 替换 verifier 私有 key 后旧签名立即失效；本轮没有实现密钥轮换后台。空登记不产生默认身份。主体停用或会话撤销立即生效，时间容差不延迟撤权。 |
| 身份及资源端口 | 只定义协议，没有正式存储适配器。IdentityStore 必须提供当前一致快照；ReadOnlyResources 提供当前可信关联。端口故障以 SecurityStoreUnavailable 表达，转换为无私密详情的安全依赖错误；不回退缓存或默认身份。 |
| 错误 | 内部异常固定为 401/UNAUTHENTICATED、403/FORBIDDEN、404/NOT_FOUND、503/INTERNAL_ERROR；都是现有错误枚举。未来 API 负责既有 ErrorEnvelope、X-Correlation-ID、WWW-Authenticate 和合法的传输响应。当前不是 HTTP 状态实测。 |

库行为核对依据：[PyJWT 2.13.0 API](https://pyjwt.readthedocs.io/en/2.13.0/api.html)、[PyPI 2.13.0](https://pypi.org/project/PyJWT/2.13.0/)，于 2026-09-09 查看。库负责密码学、签名及标准声明验证，组件额外限定本项目会话约定。

HS256 的签发者与验证者共享秘密，适用于此本机受控演示候选。没有开放签发入口；公开注册、刷新/退出接口、多签发方、多密钥过渡和正式部署密钥管理仍需后续设计及验证。上述均为 A 提供的内部候选选择，不能写成 A/B/C 已共同接受。

## 3. 需求、模型和测试追踪

| 组件/场景 | 需求与模型 | 本轮证据 |
|---|---|---|
| JWT、登记及会话重验 | FR-009/012，NFR-002/003/009；[CS-D01](13-shared-composite-structure.md)、[MA G-REQUEST](12-member-a-model-chain.md)；AUTH-01/02/07/12 的身份部分 | [认证测试](../tests/security/test_authentication.py)：缺失/畸形 token、错误算法/签名/issuer/audience、声明类型、时间边界、过期与撤销、登记不匹配、角色变化、故障和秘密显示边界。 |
| 十五操作的角色及资源范围 | FR-001/009/011/012，NFR-002/003/009；共享 API/Domain 交互、AUTH-02/03/04/05/12 的授权部分 | [权限测试](../tests/security/test_authorization.py)：独立期望矩阵与 OpenAPI operation 集合对照；错误角色零资源查询；跨客户/商店、关联错误、附件范围与到期、列表 store scope。 |
| 两组件组合 | 同上；CS-D01、AUTH-07/12 的重复授权部分 | 使用真实 JWT verifier 与真实授权策略，合成注册/案件端口；第一次成功后撤销/停用/改 owner/改店，第二次拒绝且不会再次调用测试下游 spy。 |
| 既有环境与锁文件 | F.02，NFR-006/007/008 | 本隔离包复用既有依赖环境执行 pip check 与非数据库环境测试，未重新安装依赖；下方命令供新环境复现。真实业务 HTTP、数据库竞态及 provider 安全仍未验收。 |

`AUTH-*` 是场景追踪，不表示整行对应的原验收已完成：本轮没有实现 422 DTO 处理、附件原子绑定、实际幂等回执、history 投影/cursor、删除后正文重放或 CORS/浏览器流程。拒绝的下游零调用是组件 spy 证据，不能冒充真实业务/provider 效果。

## 4. 复现与结果

使用专用 Python 3.12 环境，在仓库根目录执行：

```powershell
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -B -m pytest tests/security -q -p no:cacheprovider
python -B -m pytest tests/environment -m 'not database' -q -p no:cacheprovider
python -B tools/checks/run.py offline --baseline-ref 9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf
```

以上安全测试不需要网络、真实密钥、数据库或运行中的 API。首次安装需要包源访问；完整 offline 检查还需要按 [检查入口](../tools/checks/README.md)安装锁定 Mermaid 工具。不要把安装命令中的 `python` 指向全局环境。

隔离准备阶段的实际计数、命令、文件范围和 SHA-256 清单保留在 [F03-C0.1 独立评审包核验记录](reviews/f03-component-review-20260914.json)，这是准备时的历史收据，其内容和哈希不随发布状态文字更新。组件现已通过 PR #15 交付；首次发布版本 `5ed71127b4e8add0fa6a8f3e1f553cc146dd35d5` 的 CI 记录只适用于其对应源码，后续准确源码和检查结果仍查 PR 正文及 Actions，本文不预先声明新提交的 CI 通过。C 本人接受仍待完成。2026-09-09 的原始本地记录保留在原工作区，未收入这个包。

2026-09-09 的完整原工作区检查曾修正 report 分段源链接解析；这是独立的历史报告工具工作。该检查器修复、其新增回归及报告文件均排除在本 F.03 包外，本包保留 `3dd1ff6` 的模型检查器。不能把含报告修复的原工作区测试计数当作本包结果；本轮不修改原工作区报告或 Google Doc。

## 5. 后续边界与评审

历史观察（2026-09-09，当时状态，不代表当前评审）：只读实查 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)：OPEN，source head `64582a3007fea0fa3d1b1c3c212168b96af6b607`，reviews 为空，B/C 请求保留。当时组件是其后本地改动；当前隔离包基线已更新为上述 `3dd1ff6`。本包不代替当前 PR11 审查，也不改变 B 已有的五项消费边界批准或 C 待审状态。F.03 现由 [KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34) 跟踪，状态 In Review，并关联 PR #15；此前“key 未核实”仅为旧准备快照，KAN-32 仍是 F.01，不作为 F.03 主卡。

接下来由 C 对 PR #15 的准确具体版本复核，A 处理评审反馈；B 在正式联调时确认使用方式。F.01 接受后才按原开始依赖接真实路由；F.03 最终验收还需 F.02 和原验收条件。后续按 A1.01 → A1.02/03 → A1.05 推进无 LLM 案件链，不把当前授权组件当作案件业务已完成。

**并发边界：** 当前授权结果只是该次读取的观察。生产/集成的 Domain 必须在写入或派发事务中重新核验当前身份权限、资源关系和版本；只读端口或 frozen dataclass 无法消除检查后撤权竞态。任何 Founder grant 都不等于 ApprovalRecord，不能跳过精确提案、命令、有效期和 provider 守卫。

本轮不改变九功能、89 WBS 或责任归属，不填造 C 的人审、F.01/F.02/F.03 接受、个人建模贡献、业务安全验收或课程提交。
