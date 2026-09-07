# F.02：C 独立复现与证据填写包

> **rc.5 发布定位（2026-09-07）：**本版交付至 [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)，由包含本说明的实际提交定位。PR 中记录准确 source SHA、CI run 与评审状态；C 复现使用该准确 SHA，不能使用旧 `57d86fe` 或浮动分支。下文“未发布/本地准备”、旧测试和旧哈希是发布前历史；当前提交以 Git 文件内容及 `docs/reviews/rc5-publication-artifacts-20260907.json` 为准。发布不等于 F.01/F.02 接受、B/C 本人审阅/复现或课程提交，Jira 未由此同步。

> 2026-09-07；**本地准备稿，尚未由 C 执行或签署**。WBS F.02：Owner A、Reviewer C，S 无、F 依赖 F.01；不改变完成依赖。本文不授予访问权限，也不要求读取 Gold 标签。
>
> 已发布候选 `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577` 仅作为下列历史证据。本包的 Docker endpoint 核验与 healthcheck 代理修复随本次 rc.5 交付；旧 SHA 不包含这些修复。C 正式复现使用本次 PR 发布记录中的**包含修复、可从仓库获取的准确 40 位提交 SHA**，记录该版本后再执行，不能默用旧 SHA、main 或“最新”。

## 1. 已有证据与本次独立检查的边界

[PR #11](https://github.com/shuxiachai/returnops-au/pull/11) 已发布候选包含健康 API、依赖锁、空业务 Alembic 迁移与 Compose。2026-09-07 只读核验：PR OPEN、非 draft，head 为 `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577`，尚无已提交 review，B/C 仍为 requested；main 为 `9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf`。这是当时状态，不代表后续修复已发布。

| 可直接核对的运行 | 实际版本与结果 |
|---|---|
| [PR run 34117330147](https://github.com/shuxiachai/returnops-au/actions/runs/34117330147) | source head `57d86fe…`；实际合成 checkout `5650601d24c8f109237dea91b3b45cab63bc0e3d`；两个 job 成功，包含对 PR base 的 89 项 WBS 比较 |
| [Push run 34117330053](https://github.com/shuxiachai/returnops-au/actions/runs/34117330053) | checkout `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577`；两个 job 成功，明确跳过独立 Git baseline 比较 |

每次 offline 结果：53 项契约、6 组模型/文档、7 项模型工具测试、5 项统一入口测试、15 个 Mermaid 块。每次环境结果：30 passed、2 warnings；Ubuntu 24.04 / CPython 3.12.14 / Node 24.20.0 / PostgreSQL 17.11。环境测试中 26 项是配置/隔离逻辑，4 项使用真实数据库。CI 使用 PG service，没有构建 Compose 镜像或测试容器的实际 TCP 断库恢复；这些有单独的[发布前本机证据](../10-f02-environment-readiness.md#51-发布前本地验证历史记录)。

本轮已只读核验 Jira：KAN-32 仍为 rc.2 / PR #9 的旧正文；KAN-14 是 A1.01–.03 / F.05 umbrella，提及 F.02 依赖不等于它是 F.02 主卡。**F.02 实际 Jira key 待取得直接证据**，记录表保留空缺，不使用推测 key。

C 的检查应从自己的干净目录、虚拟环境和新项目卷重复安装、迁移、完整测试及 HTTP 故障恢复。已有 CI、A 的机器运行和本包命令均不能代填 C 的执行结论。只实现两条 health API，十五个 `/v1` 业务操作、身份、案件、审批、Agent 和领域持久化未实现。

## 2. 干净 checkout 与工具

以下为 PowerShell 示例。需要已有 Git、CPython 3.12、Node 24/npm、可运行 Linux 容器的 Docker/Compose，以及自己的私有仓库读取权限。首次依赖/镜像安装需联网。不要复制 A 的 `.env`、数据库、Docker 配置或 token。

先在**已有主仓库之外、自己选择的复现父目录**打开一个未设置 `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`、`DB_PORT`、`API_PORT` 的终端。Compose 的 shell 变量会覆盖 env 文件，所以下面仅检查变量名是否存在，发现时停止；不显示其值，也不清除用户原配置。后面的 Docker 步骤还会单独拒绝 `DOCKER_HOST` / `DOCKER_CONTEXT` 覆盖，并核验和固定一个本地 endpoint。

```powershell
$ErrorActionPreference = 'Stop'
function Run-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited $LASTEXITCODE; stop this review step." }
}
$overrideNames = @('POSTGRES_USER','POSTGRES_PASSWORD','POSTGRES_DB','DB_PORT','API_PORT')
foreach ($name in $overrideNames) {
    if (Test-Path "Env:$name") { throw "Existing environment override: $name. Use a separate clean terminal." }
}
$reviewSha = (Read-Host 'Enter the exact 40-character commit SHA supplied by A containing the F.02 fixes').Trim()
if ($reviewSha -notmatch '^[0-9a-fA-F]{40}$' -or $reviewSha -eq '57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577') {
    throw 'Use a specific published fix commit; the historical head does not contain these fixes.'
}
$reviewRoot = Join-Path (Get-Location) ('returnops-f02-c-' + (Get-Date -Format 'yyyyMMddHHmmss'))
if (Test-Path -LiteralPath $reviewRoot) { throw 'Review checkout already exists; choose a new path.' }
Run-Checked git @('clone','--no-checkout','https://github.com/shuxiachai/returnops-au.git',$reviewRoot)
Set-Location -LiteralPath $reviewRoot
$baselineSha = '9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf'
Run-Checked git @('cat-file','-e',"${reviewSha}^{commit}")
Run-Checked git @('checkout','--detach',$reviewSha)
Run-Checked git @('rev-parse','HEAD')
Run-Checked git @('status','--short')
if (-not (Test-Path -LiteralPath 'tests/environment/test_compose_healthcheck.py')) {
    throw 'The checkout does not include the F.02 proxy regression check; verify the review commit.'
}
Run-Checked python @('-c','import sys; assert sys.version_info[:2] == (3,12); print(sys.version)')
Run-Checked python @('-m','venv','.venv')
$py = Join-Path (Get-Location) '.venv/Scripts/python.exe'
Run-Checked $py @('-m','pip','install','--require-hashes','-r','requirements-dev.lock')
Run-Checked $py @('-m','pip','install','--no-deps','--no-build-isolation','-e','.')
Run-Checked $py @('-m','pip','check')
Run-Checked $py @('-B','-m','pytest','tests/environment/test_compose_healthcheck.py','-q')
Run-Checked node @('--version')
Run-Checked npm @('ci','--prefix','tools/model-checks','--ignore-scripts','--no-audit','--no-fund')
Run-Checked $py @('-B','tools/checks/run.py','offline','--baseline-ref',$baselineSha)
```

macOS/Linux 的解释器路径为 `.venv/bin/python`；可以用对应 shell 执行同一程序和参数，仍须逐步检查非零退出。`git status --short` 在安装前应为空；若指定 SHA 不可获取、checkout/version/安装失败则先记录问题，不在失败步骤后继续验证，也不改用另一个 SHA 冒充。§1 的数量是旧版本历史记录；新版本记录实际收集/通过数量，不修改测试使其凑数。新增 healthcheck 回归使用自建临时 HTTP 服务，不需要 Docker 或数据库。

## 3. 独立端口、配置与卷

context 名称本身不能证明实际连接位置：[Docker 官方说明](https://docs.docker.com/engine/manage-resources/contexts/)规定 `DOCKER_HOST` / `DOCKER_CONTEXT` 可覆盖默认连接。下面拒绝这些终端覆盖，读取所选 context 的实际 endpoint，只接受本机 named pipe / Unix socket，并验证 Linux engine。TCP/SSH 或其他 endpoint 必须先另行核验，不让本机端口检查与其他主机的 Docker 混用。已有覆盖时换用没有这些覆盖的独立终端，不在脚本中清空或更改用户全局设置。

通过后固定 `--context`，每次操作前复核 endpoint 未变。盘点、启动、故障检查及收尾统一使用 `Run-ReviewDocker`；不能绕开该函数或另换 context，也不关闭别人的服务、清理旧卷。

```powershell
function Assert-NoDockerOverrides {
    foreach ($name in @('DOCKER_HOST','DOCKER_CONTEXT')) {
        if (Test-Path "Env:$name") { throw "Docker override present: $name. Use a separate clean terminal." }
    }
}
function Test-LocalDockerEndpoint {
    param([string]$Endpoint)
    return $Endpoint.StartsWith('unix:///', [StringComparison]::Ordinal) -or $Endpoint -match '^npipe:/+\./pipe/[^/\\]+$'
}
Assert-NoDockerOverrides
$reviewContext = (Run-Checked docker @('context','show') | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($reviewContext)) { throw 'Docker context is missing.' }
$dockerArgs = @('--context',$reviewContext)
$endpointArgs = @('context','inspect',$reviewContext,'--format','{{.Endpoints.docker.Host}}')
$reviewEndpoint = (Run-Checked docker ($dockerArgs + $endpointArgs) | Out-String).Trim()
if (-not (Test-LocalDockerEndpoint $reviewEndpoint)) { throw 'The selected Docker endpoint is not a verified local named pipe or Unix socket.' }
function Run-ReviewDocker {
    param([string[]]$Arguments)
    Assert-NoDockerOverrides
    $currentEndpoint = (Run-Checked docker ($dockerArgs + $endpointArgs) | Out-String).Trim()
    if ($currentEndpoint -cne $reviewEndpoint) { throw 'Docker endpoint changed; stop this reproduction.' }
    Run-Checked docker ($dockerArgs + $Arguments)
}
$serverOs = (Run-ReviewDocker @('info','--format','{{.OSType}}') | Out-String).Trim()
if ($serverOs -ne 'linux') { throw 'This Compose candidate requires a local Linux container engine.' }
Write-Output "Verified local Docker context: $reviewContext ($reviewEndpoint)"
Run-ReviewDocker @('version')
Run-ReviewDocker @('compose','ls')
Run-ReviewDocker @('volume','ls')
$reviewProject = 'returnops-au-f02-c-' + (Get-Date -Format 'yyyyMMddHHmmss')
$reviewEnv = '.env.f02-c-review'
$dbPort = 15433
$apiPort = 18001
if (Test-Path -LiteralPath $reviewEnv) { throw 'Review env file already exists; stop and verify ownership.' }
$portCheck = @'
import socket, sys
ports = [int(p) for p in sys.argv[1:]]
assert len(set(ports)) == len(ports)
listeners = []
try:
    for port in ports:
        s = socket.socket()
        listeners.append(s)
        s.bind(('127.0.0.1', port))
    print('Requested loopback ports are available at this check.')
finally:
    for s in listeners:
        s.close()
'@
Run-Checked $py @('-c',$portCheck,"$dbPort","$apiPort")
Run-Checked $py @('-B','tools/environment/local.py','--env-file',$reviewEnv,'init')
$setPorts = @'
from pathlib import Path
import sys
p = Path(sys.argv[1])
updates = {'DB_PORT': sys.argv[2], 'API_PORT': sys.argv[3]}
lines = p.read_text(encoding='utf-8').splitlines()
assert all(sum(line.startswith(key + '=') for line in lines) == 1 for key in updates)
p.write_text('\n'.join(key + '=' + updates[key] if (key := line.partition('=')[0]) in updates else line for line in lines) + '\n', encoding='utf-8')
print('Only review port settings updated; credentials not displayed.')
'@
Run-Checked $py @('-c',$setPorts,$reviewEnv,"$dbPort","$apiPort")
$composeArgs = @('compose','-f','compose.yaml','--env-file',$reviewEnv,'-p',$reviewProject)
Run-ReviewDocker ($composeArgs + @('config','--quiet'))
Run-ReviewDocker ($composeArgs + @('up','--build','-d','--wait','--wait-timeout','180'))
Run-ReviewDocker ($composeArgs + @('ps','-a'))
```

端口检查到启动之间仍可能出现竞争；如果 up 报端口占用，停止本次步骤，选择其他端口后记录重试，不关闭占用者。项目名必须不存在于盘点结果中；如碰撞换新名称。确认新建卷为 `${reviewProject}_postgres-data`，不是 A 的 `returnops-au-f02_postgres-data`，也没有挂载现有主机 PostgreSQL 数据。A 的 8000/8001/5432/5433 均不是 C 必须使用的端口。

成功标准：db healthy、migrate Exited (0)、api healthy；API/PG 端口只绑定 127.0.0.1。可用 `Run-ReviewDocker ($composeArgs + @('logs','migrate','api'))` 查看本项目错误，但不要打印 `.env`、`DATABASE_URL`、完整 `docker compose config` 或带凭据的 inspect/env；上面只读取 context 的 endpoint 字段。`.env.f02-c-review` 已被仓库规则忽略，不能作为提交附件。修复后的容器 healthcheck 显式绕过 HTTP 代理，不要求修改用户全局代理配置。

## 4. 完整测试、重复迁移与实际 HTTP

在上一步的同一终端和目录执行，保证本机测试与 Compose 使用同一个 env 文件：

```powershell
Run-Checked $py @('-B','tools/environment/local.py','--env-file',$reviewEnv,'run','python','tools/checks/run.py','environment')
Run-Checked $py @('-B','tools/environment/local.py','--env-file',$reviewEnv,'run','python','-m','alembic','upgrade','head')
Run-Checked $py @('-B','tools/environment/local.py','--env-file',$reviewEnv,'run','python','-m','alembic','current')
Run-ReviewDocker ($composeArgs + @('exec','-T','db','psql','-U','returnops_dev','-d','returnops_f02','-Atc','select version_num from alembic_version'))
```

成功标准：完整环境入口退出 0，记录该 SHA 的全部测试数量，真实 DB 的 4 项和新增 healthcheck 回归均没有 skip；两次升级后都只有 `0001_environment`。历史 SHA 的 30 项不包含本轮新增检查，不能作为新版本通过数量抄写。`-m "not database"` 的子集不能填作完整通过。迁移只创建版本表，没有案件/审批/审计业务表。保留 warnings 原文，报告新出现的错误，不为得到绿色结果临时放宽测试。

下面的 HTTP 检查直接连自己的容器 API，绕过系统代理。首次调用与恢复后要求 live=200、ready=200；只停止自己的 db 时要求 live=200、ready=503。脚本只输出健康路径/状态，不打印连接配置。

```powershell
$healthCheck = @'
import json, sys
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
port, expected_ready = int(sys.argv[1]), int(sys.argv[2])
opener = build_opener(ProxyHandler({}))
for path, expected, state in [('live', 200, 'alive'), ('ready', expected_ready, 'ready' if expected_ready == 200 else 'not_ready')]:
    try:
        response = opener.open(f'http://127.0.0.1:{port}/health/{path}', timeout=10)
    except HTTPError as error:
        response = error
    with response:
        status, body = response.code, json.load(response)
    assert status == expected and body.get('status') == state, f'{path}: unexpected health result'
    print(f'{path}: {status} / {state}')
'@
Run-Checked $py @('-c',$healthCheck,"$apiPort",'200')
Run-ReviewDocker ($composeArgs + @('stop','db'))
try {
    Run-Checked $py @('-c',$healthCheck,"$apiPort",'503')
} finally {
    Run-ReviewDocker ($composeArgs + @('start','db'))
}
Run-ReviewDocker ($composeArgs + @('up','-d','--wait','--wait-timeout','90'))
Run-Checked $py @('-c',$healthCheck,"$apiPort",'200')
Run-ReviewDocker ($composeArgs + @('ps','-a'))
```

如果检查失败，记录出错阶段；finally 只尝试恢复本次项目 db。`up --wait` 也必须成功后才能记作恢复通过。断库期间 liveness 持续为 200、readiness 为 503 表示基础设施故障被准确暴露，不是业务恢复或 OperationAttempt 状态机已实现。

## 5. 本地失败退出与收尾

缺少 DATABASE_URL 的环境入口必须在迁移前失败。下面只在子进程中移除变量，不连接 DB，不改当前终端配置：

```powershell
$missingConfigCheck = @'
import os, subprocess, sys
env = os.environ.copy()
env.pop('DATABASE_URL', None)
result = subprocess.run([sys.executable, '-B', 'tools/checks/run.py', 'environment'], env=env)
print(f'Missing-config child exit: {result.returncode}; expected 2 before migration.')
sys.exit(0 if result.returncode == 2 else 1)
'@
Run-Checked $py @('-c',$missingConfigCheck)
Run-Checked git @('status','--short')
# 复核完成后，仅停止本次 reviewer 项目；保留卷及日志供核查。
Run-ReviewDocker ($composeArgs + @('stop'))
```

负例成功是内部 child exit=2、外层检查退出 0；它不是失败的远端 Actions run。已有统一入口回归还验证首次失败后不再执行后续步骤、缺工具报错不吞掉失败；测试 doubles 不证明真实业务故障恢复。此包不制造红色 PR run，不配置 required checks。

本包没有 `down -v`、prune、Docker reset、全局 WSL shutdown 或对已有数据库的清空操作。若要保留 API 演示，可在记录用途后暂不执行最后的 stop；仍只管理本次项目。原生 PostgreSQL 替代路线见 [docs10 §3](../10-f02-environment-readiness.md#3-启动迁移与检查)，不等同于 PostgreSQL 17 / Compose 验收。

## 6. C 填写的证据与决定

所有“待填”均由实际执行者填写。日志只保存必要的安装/测试/状态输出，检查没有密码/token/DSN 后再提供；不要附 env 文件。可将本机日志放在被忽略的 `tmp/`，记录相对文件名、SHA-256 和供 Reviewer 访问的获准位置。`Get-FileHash -Algorithm SHA256 <日志路径>` 可记录文件完整性；日志是否可访问仍须真人检查。

| 字段 | C 的实际记录 |
|---|---|
| 执行者、日期/时区、机器与 OS | 待 C 填写；当前无签名 |
| WBS / F.02 实际 Jira key | F.02 / 待核验，不填 KAN-14 或 KAN-32 代替 |
| 实际 `git rev-parse HEAD` / baseline / 初始及最终 git status | 待填包含修复的准确 SHA、A 提供的评审入口及可获取证据；不是历史 57d86fe |
| Python / Node / npm / Docker / Compose / PG 实际版本 | 待填 |
| 本次目录、固定 context、核验的 local endpoint / Linux engine、项目名、网络、卷名 | 待填；确认没有 DOCKER_HOST/CONTEXT 覆盖，endpoint 未变，仅新建且属于本次检查 |
| env 文件名、API/DB loopback 端口 | 待填文件名和端口，绝不填密码或完整 URL |
| 安装与 pip check / offline 数量及退出码 | 待填，附必要日志与 hash |
| 迁移、新库及重复升级后的 revision | 待填 |
| 完整环境测试数量 / 真实 DB 四项 / warnings | 待填，附日志与 hash；不能用非 DB 子集代替 |
| 健康 → 断库 → 恢复的 live/ready 状态 | 待填三组 HTTP 结果及时间 |
| 缺配置 child exit / 未启动迁移 | 待填，期望 2，保留错误类型而非凭据 |
| 已核对的 GitHub source SHA / checkout SHA / run URL | 待填，区分 PR 合成 checkout 与源分支 head |
| 资源收尾与保留日志位置 | 待填，仅停止自己项目；说明留下的卷/进程 |
| 问题、严重度、可复现步骤与 A 的后续处置 | 待填；没有问题也由 C 明确记录 |
| C 的结论与范围 | 待本人填写：通过本次复现 / 需修订后复查 / 环境受阻；不是预填 F.02 Done |

当前状态为“复现包已准备、C 未执行”。即使 C 复现通过，F.02 的 F.01 接受依赖、实际 Jira 关联、PR/review、成功/失败检查日志和所需仓库规则证据仍按 [docs10 §5.3](../10-f02-environment-readiness.md#53-尚需独立闭环)与原 WBS 分别闭环；也不代表 Stage 1 提交或课程评分通过。
