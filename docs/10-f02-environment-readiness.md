# F.02：环境、依赖与最小 CI 准备

> 2026-09-07；状态：**准备稿，未完成 F.02 验收**。Owner：A；Reviewer：C。
>
> WBS：F.02；开始依赖 S：无；完成依赖 F：[F.01](09-interface-contract-v1.md)。
> F.02 的实际 Jira key 待核对映射；不能直接复用 F.01 的 KAN-32。

本稿按 [项目定义第 11 节](00-project-definition-v1.md)、[固定分工](07-frozen-work-allocation.md)和[工作包 F.02](08-delivery-work-packages.md)准备可复现环境与检查入口。F.01 接受前可以准备环境和 CI 草案；F.02 完成仍须等待 F.01 接受，并取得干净环境启动、迁移、测试和真实 PR 检查证据。本文件没有安装依赖、启动 Docker、实现 API 或部署工作流。

## 1. 已核验的环境与缺口

以下为 2026-09-07 14:36 AEST 前的本机/远端快照，不是持续监控结果。

| 项目 | 实测结果 | 限制 |
|---|---|---|
| Python | 本机 Python 3.12.9 可执行 | 后续干净环境需记录实际版本，不能依赖个人全局包 |
| `tmp/f01-clean-venv` | `include-system-site-packages=false`；jsonschema 4.23.0、referencing 0.35.1、openapi-spec-validator 0.7.2 | 可运行离线契约 unittest；没有 pytest、Pydantic 或 API/数据库依赖 |
| `tmp/f01-venv` | `include-system-site-packages=true`；pytest 8.3.5、Pydantic 2.12.5；jsonschema 4.26.0、referencing 0.37.0 | 继承全局环境，验证器版本与声明不同；只能作本地参考，不能作为干净复现证据 |
| 依赖声明 | [contracts/requirements.txt](../contracts/requirements.txt)固定三个顶层验证依赖版本 | 不是完整传递依赖锁，也不是应用依赖锁；尚无根目录应用依赖配置 |
| Docker | CLI 29.6.2、Compose 5.3.1 可执行 | `docker version` 返回 `Server=null`；默认 `docker_engine` pipe 不存在，并有用户 Docker config 读取权限警告。本轮无法连接 daemon，未验证 PostgreSQL |
| 仓库实现 | 已有旧领域模型、合成 fixtures 和离线契约测试 | 尚无 `apps/api`、Compose、SQLAlchemy/Alembic 迁移或已验证的 PostgreSQL 服务 |
| GitHub | main 为 `9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf`；Actions workflow 数量为 0 | 尚无真实 PR CI 证据；没有核验或设置 required checks / branch protection |

[.gitignore](../.gitignore)已排除 `.venv/`、`.venv-contracts/`、`tmp/`、Python 缓存、`.env` 与 `.env.*`，并允许 `.env.example`。后续示例只放非秘密占位值；临时环境与真实配置不入 Git。

## 2. 当前可以运行的离线检查

在仓库根目录运行以下 PowerShell 命令。第一组使用已核验的隔离环境，不需要 pytest、数据库、API、模型密钥或 provider；安装依赖之后，检查本身可离线运行。

```powershell
.\tmp\f01-clean-venv\Scripts\python.exe -B -m unittest discover -s tests/contracts -p "test_*.py" -v
```

旧领域测试另需 pytest 与 Pydantic，可在现有继承全局包的环境中作参考检查：

```powershell
.\tmp\f01-venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/unit -q
```

以上命令由环境/入口检查确认可用，本稿未执行新一轮测试。F.01 工作副本修订后，以实际运行结果为准，不沿用历史 35/39 通过数。契约 unittest 检查文档结构及样例；旧领域测试也不能证明已实现审批、状态、幂等或 provider 守卫。

后续复现契约检查的独立环境可按以下命令创建；这会创建本地环境并安装依赖，**尚未由本稿执行**：

```powershell
python -m venv .venv-contracts
.\.venv-contracts\Scripts\python.exe -m pip install -r contracts/requirements.txt
.\.venv-contracts\Scripts\python.exe -m unittest discover -s tests/contracts -p "test_*.py" -v
```

Linux CI 可执行等价的 `python -m pip install -r contracts/requirements.txt` 与 `python -m unittest discover -s tests/contracts -p 'test_*.py' -v`。使用 Python 3.12 的全新 runner 即可，不必为最小契约检查加入 pytest。若后来纳入旧领域测试，应单独声明 pytest/Pydantic 依赖与测试步骤。

## 3. 本轮可准备的最小交付物

| 产出 | 可审查条件 |
|---|---|
| 环境与依赖说明 | 区分契约检查、旧领域测试及未来 API 依赖；说明 Python 版本、安装入口和失败排查，不把全局包当项目依赖 |
| 最小契约 CI 草案 | PR 上安装已声明验证器并运行 unittest；缺包、结构错误或测试失败均以非零退出码结束；不使用 `continue-on-error` 掩盖失败 |
| 应用环境设计草案 | 沿用 FastAPI/Pydantic、PostgreSQL/SQLAlchemy/Alembic、Docker Compose；说明配置注入、启动顺序、数据库就绪、迁移和测试入口 |
| 验收证据清单 | 关联 F.02 的真实 Jira key、具体需求/模型、提交、非作者评审与真实 CI URL；状态和时间按实际发生记录 |

最小 CI 目前只是上述步骤约定，尚未写入或部署 `.github/workflows`。它通过以后，只能证明离线契约检查通过，不能代替 F.02 的 API/PostgreSQL 验收或 required checks 配置核验。

准备工作不迁移 A1.01 的业务领域模型、不提前实现依赖 F.01 的授权/附件/状态/审批服务，也不接入 LLM 或可产生操作效果的 provider。API 健康检查和空库迁移入口的后续基础设施实现必须与 A1.02 的业务实体/版本持久化区分，避免重复认领。

## 4. F.02 后续验收顺序

以下均待完成，不是已经存在的运行命令或结果。

1. **确认契约与环境。** 记录 F.01 接受版本和 A/B/C 确认；确定 Python、应用/开发依赖与可复现安装策略，提交非秘密配置示例和启动说明。
2. **准备 API/PostgreSQL。** 提交最小 API 启动入口、Compose 服务及就绪检查。使用干净 checkout 和新的测试数据库按说明启动；记录 API 响应、数据库连通结果、实际版本和启动耗时。本机 Docker daemon 的可用性须重新实测。
3. **验证迁移入口。** 空测试库按已提交命令迁移到 head，再次执行不产生额外变更；记录迁移版本与结果。F.02 不以空库迁移冒充 A1.02 的业务持久化验收。
4. **统一测试入口。** 从声明的依赖安装后运行契约及适用的应用基础测试；数据库未就绪、缺配置或缺包须明确失败。后续业务测试分别追溯到其 Owner 与 WBS。
5. **取得真实 PR CI。** 在实际 PR 上自动运行相同入口，保留可访问的成功日志与一次可审查的失败退出证据；不要在 main 留下故意失败的测试。检查失败必须使对应 job/run 失败。合并是否受 required checks 强制限制需另行读取配置核验，不能由绿勾推断。
6. **非作者复现与记录。** C 从干净环境复现，确认密钥通过环境注入且不出现在日志/仓库。完成 F.01 依赖并附提交、review、运行和 CI 链接后，才申请 F.02 Done。

本准备稿对应 `NFR-006 Testability` 的测试入口、`NFR-007 Maintainability` 的依赖边界、`NFR-003 Privacy` 的秘密配置隔离和 `NFR-001 Traceability` 的证据关联，具体定义见 [docs/00 的需求表](00-project-definition-v1.md)；模型入口为共享 Package/Deployment 设计与 [系统设计](02-system-design.md)。准备稿不宣称尚未提交的部署图、运行环境或未来业务功能已验收。
