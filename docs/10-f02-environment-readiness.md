# F.02：环境、依赖与最小 CI

> 2026-09-07；**环境评审候选，F.02 未验收**。Owner A、Reviewer C；S 无、F 依赖 F.01。F.02 实际 Jira key 尚未核验，不复用 KAN-32，也不虚构新卡。评审入口为 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，提交及真实 CI 以该 PR 的具体 revision/run 为证。
>
> 组长已要求环境准备和候选发布。健康 API、PostgreSQL/Compose、空业务迁移、完整依赖锁和 CI 文件是本次环境产物；本地验证及后续 CI 都不代表 F.01 接受或 A1.02 实现。

## 1. 本轮产出与范围

沿用[产品定义 §11](00-project-definition-v1.md#11-engineering-strategy)的 FastAPI/Pydantic、SQLAlchemy/Alembic、PostgreSQL 和 Docker Compose。

| 产出 | 文件 / 运行行为 | 验收边界 |
|---|---|---|
| 应用包 | [pyproject.toml](../pyproject.toml)、[API](../apps/api/returnops_api/main.py) | 只有 /health/live 和 /health/ready；十五个 /v1 契约操作、身份/案件/审批仍未实现 |
| 就绪检查 | [database.py](../apps/api/returnops_api/database.py) | SELECT 1 和版本查询成功且恰好一个预期 revision 才 200；其他为 503；不隐式迁移/stamp |
| 配置 | [settings.py](../apps/api/returnops_api/settings.py)、[.env.example](../.env.example) | 缺失/错误配置明确失败，错误不回显 DSN，凭据通过环境注入 |
| 空业务迁移 | [alembic.ini](../alembic.ini)、[env.py](../alembic/env.py)、[0001_environment](../alembic/versions/0001_environment.py) | 只有版本表和 revision，无案件/提案/审批/审计实体 |
| 安装锁 | [运行锁](../requirements.lock)、[开发/测试锁](../requirements-dev.lock) | Python 3.12 传递依赖、版本与 hashes；开发锁约束到运行锁 |
| 容器 | [Dockerfile](../Dockerfile)、[Compose](../compose.yaml)、[.dockerignore](../.dockerignore) | PG healthy → migration 成功 → API；应用非 root，构建上下文仅运行文件 |
| 验证 | [环境测试](../tests/environment/test_environment.py)、[统一入口](../tools/checks/README.md)、[原生独立簇复现](../tools/environment/native_check.py)、[CI](../.github/workflows/ci.yml) | 本地失败退出可核验；未发布时不存在真实 GitHub run |

追踪：NFR-001/003/006/007/008/009，支持后续 FR-001/009/011/012 的基础设施。模型依据为[系统设计的模块化单体、API/PostgreSQL 边界](02-system-design.md)与共享类/接口；**尚无已验收的 Package/Deployment 图**，Compose 或 Composite 不能替代课程 UML。健康检查直读基础设施，不表示已实现 Domain/CaseRepository。

## 2. 首次安装与配置

在唯一项目仓库根目录使用 CPython 3.12。下面不安装全局 Python 包；.venv、.env、缓存均被 Git 忽略。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B tools/environment/local.py init
npm ci --prefix tools/model-checks --ignore-scripts --no-audit --no-fund
```

macOS/Linux 将解释器替换为 .venv/bin/python。首次安装需访问 PyPI/npm；安装后契约/模型检查本身不联网。Docker 只装运行锁，通过 /app/apps/api 加载源包，不包含开发依赖或个人全局包。

[local.py](../tools/environment/local.py) 只在 .env 不存在时生成随机本地密码，不覆盖现有配置，不显示密码。不要复用账户密码；手工配置 Compose 的密码应使用 URL-safe 字符，原生 DATABASE_URL 的特殊字符须编码。local.py 可向子进程注入编码后的 URL，避免密码进入命令历史。不要打印完整 docker compose config 或 .env；校验用 `docker compose config --quiet`。

示例配置默认仅发布到本机：API 127.0.0.1:8000、PG 127.0.0.1:5433。**本机 Docker 恢复后，原有 academic_agent 容器自动启动占用 8000，因此本机被忽略的 .env 已只将 API_PORT 改为 8001**；本项目当前 API 为 127.0.0.1:8001。容器内 API 监听 0.0.0.0:8000 是映射所需，不等于对外发布。本机 5432 已由原有 PostgreSQL 18 使用，本项目不停止/复用它。端口冲突时调整自己的 .env，不关闭其他服务。

## 3. 启动、迁移与检查

先启动 Docker daemon，再检查已有项目/卷。默认项目名 returnops-au-f02，卷按项目隔离；如果已有同名且不属于本项目的资源，应选新的 `-p` 名，不覆盖或清空。

```powershell
docker version
docker compose ls
docker volume ls
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose ps -a
$apiPort = 8001 # 本机 .env 当前值；其他机器以自己的 API_PORT 为准
Invoke-RestMethod "http://127.0.0.1:$apiPort/health/live"
Invoke-RestMethod "http://127.0.0.1:$apiPort/health/ready"
```

Windows 若 context 不对，在命令中显式加 `--context desktop-linux`，不必改变全局设置。up 失败时查看本项目 `docker compose logs migrate api`；失败不能略过。连接、池等待、查询均有短超时。停止本项目用 `docker compose stop` 保留数据；不默认删卷/prune/reset/全局 WSL shutdown。

数据库已启动后，使用 .env 的 loopback PG 配置执行验证：

```powershell
.\.venv\Scripts\python.exe -B tools/environment/local.py run python tools/checks/run.py environment
.\.venv\Scripts\python.exe -B tools/checks/run.py offline --baseline-ref main
```

environment 依次执行 Alembic upgrade/current 和完整 pytest。直接 Alembic 入口也保护专用库：只允许 returnops_f02 或小写字母/数字/下划线后缀，名字至多 63 字符；拒绝 URL query/fragment，防止 ?dbname=... 覆盖实际连接目标。这是 F.02 测试防误用边界，不代替数据库权限。健康 API 不执行迁移；后续增业务迁移须同步预期 revision 与相应测试，不能对新旧 schema 一概报 ready。

没有 DB 时只可明确运行非数据库子集：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/environment -m "not database" -q
```

这不等于完整环境通过。完整命令缺配置/数据库时会失败而非 skip。真实 PG 检查包含连接、HTTP 就绪、重复升级不变、TEMP 表事务回滚；不改公共版本表制造失败，不删业务表。缺版本/旧版本/多头/连接失败等逻辑另用隔离 doubles 验证。

若 Docker 暂不可用，但已有 PostgreSQL 二进制，可运行独立原生复现。`--bin` 必须指向本人机器上现有的 PostgreSQL bin；下例是本轮实际路径，不要求其他成员安装到同处：

```powershell
.\.venv\Scripts\python.exe -B tools/environment/native_check.py --bin 'D:/Program Files/PostgreSQL/18/bin' --db-port 5434 --api-port 8002
```

脚本先检查端口与二进制，每次在仓库 tmp 下新建簇及随机测试密码，不读取 .env、不连接原有库。依次运行完整 environment 检查、真实 Uvicorn TCP 就绪/存活检查及数据库停止后的 503/200 检查；最后只停止自己创建的进程。默认端口 5433/8000，可用 `--db-port` / `--api-port` 指定其他空闲端口；上例避开已运行的两个 Docker 项目。保留该次数据与日志、删除初始化密码文件；不会安装软件、注册服务或修改 Docker。原生结果不能代替指定 PostgreSQL 17 / Compose 平台验收。

## 4. 依赖与 CI

本轮用 uv 0.11.24 解析 PyPI 并生成 hashes；安装和运行不依赖 uv。依赖更新由 A 单独修订并审查两个锁，不在每次启动时重解析：

```powershell
uv pip compile pyproject.toml --python-version 3.12 --universal --generate-hashes --output-file requirements.lock
uv pip compile pyproject.toml --extra dev --constraint requirements.lock --python-version 3.12 --universal --generate-hashes --output-file requirements-dev.lock
```

运行锁用于 Docker；开发锁含 pytest/httpx、构建工具及契约验证器。原 [contracts/requirements.txt](../contracts/requirements.txt) 仍是独立契约入口，不是应用完整锁。Node 模型工具另有锁。Python/PostgreSQL 镜像采用 2026-09-07 实查的官方多架构 digest；CI 的 PG 与 Compose 相同。更新需重验。

CI 有离线契约/模型、临时 PG 迁移/环境两个 job。官方 actions 固定已核验 SHA，token 仅 contents:read，不使用 pull_request_target 或 continue-on-error。PR 比较 base SHA 的 WBS；普通 push 明确跳过独立基线比较。固定引用和完整说明见 [tools/checks](../tools/checks/README.md)。本地有文件不等于 Actions 已运行或 required checks 已配置。

F.01 未接受时可以保存或发布环境候选供评审；**commit/PR 不等于采纳或验收**，B/C 未审阅不是禁止提交的技术理由。

## 5. 本轮证据与待完成项

以下记录发布前本机实测；旧 Docker Server=null、仅全局环境的快照不作为当前结论。发布后的 CI 和真人评审证据另在 PR #11 记录，不能由这些本地结果推定。

- 新 .venv：CPython 3.12.9，include-system-site-packages=false；哈希锁与 editable 包安装成功，pip check 无冲突。
- 新环境统一离线入口通过：53 契约、6 组模型/文档、7 模型工具测试、5 统一入口测试、15 Mermaid 块；仍是静态/工具验证。
- Windows 原生 PostgreSQL **18.2** 的全新独立测试簇：迁移到 `0001_environment`，完整 **30 项环境测试通过**（26 项配置/隔离逻辑，4 项实际数据库测试）。可复现 native_check.py 再运行成功；实际 TCP `/health/live` 与 `/health/ready` 均为 200，停止自己的数据库后分别为 200 / 503。测试进程已停止，原有主机 PG18 / 5432 服务保留；这不是 Docker PostgreSQL 17 的证据。
- 原生复现日志与数据保存在被 Git 忽略的 `tmp/f02-native-qnf359mz/`；早期单步验证保存在 `tmp/f02-native-tr8s88sy/`。它们是发布前工作树的本机结果，不是远端运行证据。测试输出有 Starlette/httpx 与 AnyIO 的弃用提示，未影响通过；没有因此改用未验证的测试依赖。
- Compose 配置静态检查通过，Python/PG 官方多架构镜像 digest 已实查。早期 Docker Desktop 4.85.0 因旧 `dockerInference` AF_UNIX 节点退出，逐节点安全读取/改名报 Win32 1920。**2026-09-07 用户授权修复后，Desktop 4.85.0 / Engine 29.6.2 已恢复**；原有 3 个容器、2 个卷可读取。首次重启又发现 Secrets Engine 旧 socket；普通停止等待 20 秒未完成，确认当时引擎均已停止且无 VM 后，官方 `docker desktop stop --force` 成功，再备份对应目录并重启恢复。
- 本机可逆恢复只对已盘点为仅含零字节 socket 的普通目录改名，保留三个备份：`C:/Users/shuxia/AppData/Local/Docker/run.repair-backup-20260907`（原始 run）、`C:/Users/shuxia/AppData/Local/docker-secrets-engine.repair-backup-20260907`（Secrets Engine）和 `C:/Users/shuxia/AppData/Local/Docker/run.repair-attempt1-20260907`（第一次失败重启残留）。配置 `EnableDockerAI=true` 保持不变；未 reset、修改 ACL、删除 VHDX、执行全局 WSL shutdown 或停止原有主机 PG18。备份保留原故障状态，不应覆盖/合并进运行中的新目录；如需回滚，应先停止 Docker，并把新目录另行保留。此为本机实测恢复，不承诺系统重启或异常断电后永不复发；[Docker 同类问题记录](https://github.com/docker/desktop-feedback/issues/531)提供调查线索。
- **项目容器已实际验证**：固定镜像构建成功；独立 Compose 项目 `returnops-au-f02` 新建网络和 `returnops-au-f02_postgres-data` 卷，PostgreSQL **17.11** healthy → migration **Exited (0)** → API healthy。容器 Python **3.12.14**、API UID **10001**；API / DB 仅映射本机 **8001 / 5433**。迁移版本 `0001_environment`，Windows .venv 连接该 PG17 容器的完整 **30 项环境测试通过**；这不是 Linux pytest/远端 CI 结果。
- 实际容器 API TCP 检查为 live=200、ready=200；只停止本项目 db 时 ready=503、live=200，重新启动同一 db 后 ready 恢复 200，卷保留。本项目 api/db 最终保持运行；原有 academic_agent / 8000 和主机 PG18 / 5432 保留。日志在被忽略的 `tmp/f02-docker-environment-20260907.log` 与 `tmp/f02-docker-http-20260907.log`。发布前这些结果不包含 GitHub Actions；后续真实 CI 按 PR #11 的具体 run 记录，环境恢复不等于 F.02 联合验收。
- F.01 rc.4 仍待接受；F.02 Jira key、C 干净环境复现、required checks、正式模型/契约认可仍待完成。实际 PR CI 按具体 run 单独记录，成功运行也不替代这些事项。

申请 F.02 Done 前需同时具备：F.01 接受版本、干净 checkout/新测试库启动与迁移证据、真实成功/失败 PR 检查日志、C 非作者复现、具体提交/review/Jira 关联。环境骨架不计为 Gate 1、A1.02 业务持久化或生产就绪。

实现参考：[FastAPI 官方容器部署](https://fastapi.tiangolo.com/deployment/docker/)、[Compose 启动依赖](https://docs.docker.com/compose/how-tos/startup-order/)、[Alembic 迁移环境](https://alembic.sqlalchemy.org/en/latest/tutorial.html)。权限、分工和完成条件来自 docs/00、07、08。
