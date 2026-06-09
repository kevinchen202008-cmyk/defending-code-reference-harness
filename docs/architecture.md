# Defending Code Reference Harness — 架构文档

## 1. 项目概述

**Defending Code Reference Harness** 是一个参考实现，用于通过 Claude 进行自主漏洞发现与修复。项目实现了一个多阶段、多智能体的 CI/CD 风格管道，用于在 C/C++ 代码库中自主发现并验证内存安全漏洞。

**核心特性：**
- 自主执行-验证的漏洞发现管道（Find → Grade → Judge → Report → Patch）
- 多阶段架构，每个阶段独立容器隔离
- gVisor 沙箱 + API 出站白名单代理，防止代理逃逸
- 模块化设计，支持扩展到其他语言和漏洞类型
- 包含交互式 Claude Code 技能（/vuln-scan、/triage、/patch 等）

---

## 2. 顶层目录结构

```
defending-code-reference-harness/
├── harness/              # 核心管道实现（Python）
│   ├── cli.py            # CLI 入口点，5 个子命令
│   ├── agent.py          # Claude Code 代理包装器（stream-json）
│   ├── config.py         # 目标配置加载器（TargetConfig）
│   ├── artifacts.py      # 数据契约（CrashArtifact、GraderVerdict 等）
│   ├── find.py           # Find 阶段：搜索漏洞
│   ├── grade.py          # Grade 阶段：验证漏洞可重现性
│   ├── recon.py          # Recon 阶段：自动发现焦点区域
│   ├── report.py         # Report 阶段：可利用性分析
│   ├── patch.py          # Patch 阶段：生成和验证补丁
│   ├── patch_grade.py    # 补丁验证梯队（T0-T3）
│   ├── judge.py          # Judge 和 Compare 代理（无工具）
│   ├── dedup.py          # 后处理：按签名聚类崩溃
│   ├── docker_ops.py     # Docker CLI 包装器
│   ├── sandbox.py        # gVisor 沙箱配置
│   ├── agent_image.py    # 构建代理镜像
│   ├── asan.py           # ASAN 输出解析
│   ├── novelty.py        # 上游 git 日志查询（可选）
│   └── prompts/          # 代理提示模板
│       ├── system_prompt.py
│       ├── find_prompt.py
│       ├── grade_prompt.py
│       ├── recon_prompt.py
│       ├── report_prompt.py
│       ├── report_grader_prompt.py
│       ├── patch_prompt.py
│       └── judge_prompt.py
│
├── targets/              # 测试目标（Dockerfile + config.yaml）
│   ├── canary/           # 快速冒烟测试（含 3 个故意漏洞）
│   ├── drlibs/           # 真实 CVE 目标（libdr_wav）
│   ├── alsa/             # 真实 CVE 目标（ALSA）
│   └── htslib/           # 真实 CVE 目标（CRAM 格式，10 个 CVE）
│
├── tests/                # 单元测试（pytest，15+ 文件）
├── scripts/              # 辅助脚本
│   ├── setup_sandbox.sh  # gVisor + 代理容器初始化
│   └── egress_proxy.py   # 出站白名单代理（Python）
├── bin/
│   └── vp-sandboxed      # Bash 包装器，验证沙箱后 exec 管道
├── docs/                 # 深度文档
├── .claude/skills/       # Claude Code 技能（/vuln-scan、/patch 等）
├── static/               # 图表资源
├── pyproject.toml        # 项目元数据和入口点
├── CLAUDE.md             # CC 操作员指南
└── README.md             # 启动指南
```

---

## 3. 管道架构

### 3.1 总体数据流

```
目标目录 (Dockerfile + config.yaml)
        │
        ▼
  docker build ──────────────────────────► 共享镜像
        │
        ▼
  [可选] Recon 阶段 (100 turns)
   发现 focus_areas → focus_areas.json
        │
        ├─── Run 0 ──┐
        ├─── Run 1 ──┤  asyncio.gather() 并行
        └─── Run N ──┘
                │
                ▼ 每个 Run 内部
        ┌───────────────┐
        │  Find Agent   │  (最多 2000 turns)
        │ 搜索内存漏洞  │
        └──────┬────────┘
               │ CrashArtifact (poc_bytes + crash_output)
               ▼
        ┌───────────────┐
        │ Grade Agent   │  (50 turns，独立容器)
        │ 验证可重现性  │
        └──────┬────────┘
               │ GraderVerdict (passed + score)
               ▼
          result.json (立即写入)
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼ (--stream 模式)
     汇总       ┌───────────────┐
               │  Judge Agent  │ (无工具，决策)
               │ NEW/DUP/SKIP  │
               └──────┬────────┘
                      │ NEW 或 DUP_BETTER
                      ▼
               ┌───────────────┐
               │ Report Agent  │ (200 turns)
               │ 可利用性分析  │
               └──────┬────────┘
                      │ ReportVerdict
                      ▼
               reports/bug_NN/report.json
                      │
                      ▼ (vuln-pipeline patch)
               ┌───────────────┐
               │  Patch Agent  │ (≤5 次迭代)
               │ 生成候选补丁  │
               └──────┬────────┘
                      │ diff bytes
                      ▼
               T0 构建 → T1 PoC → T2 测试 → Re-attack
               reports/bug_NN/patch.diff
```

### 3.2 管道各阶段说明

| 阶段 | 模块 | 最大轮次 | 角色 | 输出 |
|------|------|----------|------|------|
| Recon | recon.py | 100 | 工具代理 | focus_areas.json |
| Find | find.py | 2000 | 工具代理 | CrashArtifact |
| Grade | grade.py | 50 | 工具代理 | GraderVerdict |
| Judge | judge.py | 20 | 无工具代理 | JudgeVerdict (NEW/DUP/SKIP) |
| Report | report.py | 200+10 | 工具代理 + 评分代理 | ReportVerdict |
| Patch | patch.py | 200×5 | 工具代理 | diff bytes |
| Patch Grade | patch_grade.py | T0-T3 oracle | 可执行验证 | PatchVerdict |

---

## 4. 核心模块详解

### 4.1 CLI 层（harness/cli.py）

**入口点：** `vuln-pipeline`（pyproject.toml: `harness.cli:main`）

**5 个子命令：**

| 命令 | 功能 | 关键参数 |
|------|------|----------|
| `run` | find + grade 循环，可选 judge→report | `--parallel`、`--stream`、`--auto-focus`、`--resume` |
| `recon` | 自动发现焦点区域 | `--model` |
| `report` | 批处理漏洞报告 | `--novelty`、`--parallel` |
| `patch` | 批处理补丁生成和验证 | `--max-iterations`（≤5） |
| `dedup` | 后处理：按签名聚类结果 | 只读，仅摘要 |

**`_cmd_run` 核心流程：**
1. 解析目标目录 → 加载 `config.yaml`（TargetConfig）
2. 解析认证（`ANTHROPIC_API_KEY` 或 `CLAUDE_CODE_OAUTH_TOKEN`）
3. 构建目标镜像（一次性，所有 run 共享）
4. 可选 Recon：发现焦点区域或从 config.yaml 加载
5. 循环分派 N 个 run（`--parallel` 时使用 `asyncio.gather()`）
6. 每个 run：Find → Grade → [Judge → Report]
7. 生成 `results/<target>/<ts>/` 目录树
8. 打印汇总报告

信号处理：`_on_signal` 捕获 SIGTERM/SIGINT，终止子进程并清理容器。

---

### 4.2 数据契约（harness/artifacts.py）

管道各阶段通过以下不可变数据类传递信号：

| 类 | 目的 | 关键字段 |
|----|------|----------|
| `CrashArtifact` | Find 产出 / Grade 输入 | `poc_bytes`、`crash_output`、`crash_type`、`dup_check` |
| `GraderVerdict` | Grade 产出 | `passed`、`score`（0-1）、`criteria`（5 项） |
| `RunResult` | 单次 run 完整结果 | `target`、`status`、`crash`、`verdict`、转录本 |
| `ReportVerdict` | 可利用性分析结果 | `rubric_score`、`severity_rating`、`novelty_status` |
| `PatchVerdict` | T0-T3 梯队结果 | `t0_builds`、`t1_poc_stops`、`t2_tests_pass`、`re_attack_clean` |
| `JudgeVerdict` | Judge 裁定 | `judgment`（NEW/DUP_BETTER/DUP_SKIP）、`bug_id` |

`CrashArtifact.to_dict()` 将 `poc_bytes` 进行 base64 编码以保证 JSON 兼容。

---

### 4.3 代理包装器（harness/agent.py）

**`run_agent()` — 核心异步循环：**

```python
async def run_agent(
    prompt: str,
    container: str,         # 目标容器名称
    max_turns: int,
    model: str,
    max_resume_attempts: int = 20,
) -> AgentResult
```

**执行逻辑：**
1. 构造 `docker exec -i` 命令，内嵌 `claude -p --output-format stream-json`
2. 启动子进程，流式处理 JSONL 消息
3. **心跳：** 每 25 条助理消息打印一次进度
4. **转录本流：** 每条消息 fsync 到 JSONL 文件（防止进程崩溃丢失）
5. **失败恢复：** 进程中途崩溃等待 3 秒后使用 `--resume <session_id>` 重启，最多 20 次
6. 返回 `AgentResult(messages, session_id, error, resume_count)`

**`find_tagged_message(tag)`：** 向后扫描消息列表，找到包含指定 XML 标签的最后一条助理消息，避免解析自由文本。

---

### 4.4 Find 阶段（harness/find.py）

**质量层级（由提示定义）：**
- **HIGH（提交）：** 堆溢出（WRITE）、UAF、SEGV @ 非零地址
- **LOW（继续搜索）：** 断言失败、栈溢出（DoS）、SEGV @ 0x0

**范围外（不提交）：** OOM、超时、干净退出、测试代码中的崩溃

**输出解析标签：** `<poc_path>`、`<reproduction_command>`、`<crash_type>`、`<crash_output>`、`<exit_code>`、`<dup_check>`

PoC 字节通过 `docker cp` 从容器读取并 base64 编码后存入 `CrashArtifact`。

---

### 4.5 Grade 阶段（harness/grade.py）

**关键设计：两容器信任边界**

Find 容器（可能已被污染）输出的 PoC 字节，经过主机层传递到 Grade 容器（同镜像的全新实例），Find 代理无法直接访问 Grade 容器。

**5 项验证标准：**

| 序号 | 标准 |
|------|------|
| 1 | 崩溃 3/3 次可重现 |
| 2 | 输出是真实的 AddressSanitizer 消息（非假阳性） |
| 3 | 崩溃位于项目代码中（非库代码或拦截器） |
| 4 | 进程以非零退出码退出 |
| 5 | 非纯内存耗尽（OOM） |

全部通过 → `GraderVerdict.passed = True`，`score` 基于稳定性。

---

### 4.6 Judge 和 Compare（harness/judge.py）

Judge 是无工具代理（纯 LLM 推理），负责防止重复报告进入 manifest。

**裁决类型：**
- `NEW` — 全新漏洞，分配 `bug_NN` ID
- `DUP_BETTER` — 同一漏洞的更好示例，替换旧报告
- `DUP_SKIP` — 重复，丢弃

**串行化：** Judge 运行受锁保护，防止两个并发的 find 代理都声称同一漏洞为 NEW。

Compare 代理用于 `DUP_BETTER` 场景：比较两个 ASAN 摘录，选出更具诊断价值的版本。

---

### 4.7 Report 阶段（harness/report.py）

Report 代理（200 轮）完成可利用性分析，然后 Report Grader（10 轮，无工具）对 5 个部分评分。

**6 部分分析框架：**

| 部分 | 内容 |
|------|------|
| `primitive` | 违反的内存原语（堆溢出、UAF 等） |
| `reachability` | 从真实攻击表面是否可达 |
| `heap_layout` | 堆布局依赖，触发稳定性 |
| `escalation_path` | 从崩溃到 RCE/信息泄露的路径 |
| `constraints` | 触发的前提条件限制 |
| `severity_rating` | 综合严重程度评级 |

**上游新颖性（可选）：** 主机端执行 `git log <commit>..HEAD -- <file>` 查询上游是否已修复，结果注入到报告提示中。

---

### 4.8 Patch 阶段（harness/patch.py + patch_grade.py）

**Patch 验证梯队（T0-T3）：**

```
Patch Agent 生成 diff
      │
      ▼
T0 构建测试 ── 应用 diff，运行 build_command，验证编译成功
      │ 通过
      ▼
T1 PoC 测试 ── 重现 PoC，验证崩溃消失（exit 0 + 无 ASAN 输出）
      │ 通过
      ▼
T2 回归测试 ── 运行 test_command（如已配置），验证 exit 0
      │ 通过
      ▼
Re-attack ── 50 轮 find 代理攻击已打补丁的二进制，任何崩溃导致失败
      │ 通过
      ▼
[可选] T3 风格评审 ── LLM 评判 0-10 分（仅咨询，不影响通过/失败）
```

失败时将反馈注入到下一轮 Patch 代理提示，最多迭代 5 次。

---

### 4.9 Dedup（harness/dedup.py）

后处理工具（非实时管道阶段），遍历 `results_root` 中所有 `result.json`，使用 `asan.py` 提取 `(crash_type, top_frame)` 签名进行聚类，输出去重摘要报告。

---

## 5. Docker 和沙箱

### 5.1 容器命名规则

| 阶段 | 容器名格式 |
|------|-----------|
| Find | `find_<target>_<run_idx>` |
| Grade | `grader_<target>_<run_idx>` |
| Report | `report_<target>_<run_idx>` |
| Recon | `recon_<target>` |
| Judge | `judge_<target>_<run_idx>` |
| Patch | `patch_<target>_<idx>` |

### 5.2 Docker 操作（docker_ops.py）

```python
build(dockerfile_dir, tag)         # docker build
run(image_tag, name, ...)          # docker run -dit（分离模式）
read_file(container, path)         # docker cp <container>:path -
write_file(container, path, bytes) # docker cp - <container>:path
exec_sh(container, command)        # docker exec bash -c
rm(container)                      # docker rm
```

### 5.3 沙箱隔离（sandbox.py + scripts/setup_sandbox.sh）

**两层隔离：**

1. **进程隔离：** 不同阶段运行在不同容器中，仅通过主机中转数据（PoC 字节、diff 字节）
2. **内核隔离：** gVisor（runsc）运行时，在用户空间拦截并验证所有系统调用

**关键环境变量：**

| 变量 | 来源 | 用途 |
|------|------|------|
| `VULN_PIPELINE_AGENT_RUNTIME` | vp-sandboxed | "runsc"（gVisor） |
| `VULN_PIPELINE_EGRESS_PROXY` | vp-sandboxed | `http://proxy_ip:3128` |
| `VULN_PIPELINE_AGENT_NETWORK` | vp-sandboxed | "vp-internal"（内部网络） |

**网络模型：**
```
代理容器
    │ vp-internal（--internal，无外网访问）
    ▼
egress_proxy.py（白名单代理）
    │ 仅允许 api.anthropic.com:443
    ▼
  互联网
```

---

## 6. 配置系统

### 6.1 目标配置（target/config.yaml）

```yaml
image_tag: string              # Docker 镜像标签
github_url: string             # 上游仓库 URL
commit: string                 # 已固定的提交哈希
binary_path: string            # 容器内二进制路径（如 /work/entry）
source_root: string            # 容器内源码根路径（如 /work）
focus_areas:                   # 可选，攻击面分区列表
  - "Parser A — 描述"
  - "Parser B — 描述"
known_bugs:                    # 可选，已知漏洞的 ASAN 摘录
  - "SUMMARY: heap-buffer-overflow..."
attack_surface: |              # 可选，可达性描述
  Local binary, reads files...
build_command: string          # 可选，Patch T0 构建命令
test_command: string           # 可选，Patch T2 回归测试命令
build_timeout_s: int           # 默认 1800
memory_limit: string           # 默认 "4g"
shm_size: string               # 可选
reattack_harness: string       # 可选，Re-attack 脚本
```

### 6.2 运行时环境变量

| 变量 | 用途 |
|------|------|
| `ANTHROPIC_API_KEY` | API 认证（优先） |
| `CLAUDE_CODE_OAUTH_TOKEN` | API 认证（备选） |
| `VULN_PIPELINE_MODEL` | 默认模型字符串 |

---

## 7. 输出目录结构

```
results/<target>/<timestamp>/
├── run_000/
│   ├── result.json              # 立即写入，包含完整 RunResult
│   ├── find_transcript.jsonl    # Find 代理完整转录本
│   ├── grade_transcript.jsonl   # Grade 代理完整转录本
│   └── grade_workspace/
├── run_001/
├── focus_areas.json             # --auto-focus 检查点
├── found_bugs.jsonl             # 共享，并行 run 去重上下文
└── reports/                     # --stream 模式
    ├── manifest.jsonl           # bug_id + asan_excerpt 索引
    ├── judge_run000.jsonl       # Judge 代理转录本
    ├── judge_log.jsonl          # 幂等性日志（防重复）
    └── bug_00/
        ├── report.json          # ReportVerdict + 完整报告文本
        ├── report_transcript_run000.jsonl
        ├── patch.diff           # 候选补丁（git diff 格式）
        ├── patch_result.json    # PatchVerdict（T0-T3 结果）
        └── workspace/
```

---

## 8. 模块依赖关系

```
cli.py
├── docker_ops, sandbox, agent_image
├── agent (run_agent, color, parse_xml_tag, find_tagged_message)
├── artifacts (所有数据类)
├── asan (asan_excerpt, crash_reason, top_frame)
├── config (TargetConfig)
├── dedup, find, grade, judge, recon, report, patch
└── prompts/system_prompt (build_system_prompt)

find.py        → agent, config, artifacts, prompts/find_prompt
grade.py       → agent, docker_ops, sandbox, artifacts, prompts/grade_prompt
report.py      → agent, docker_ops, sandbox, artifacts, asan, novelty, prompts/{report_prompt,report_grader_prompt}
patch.py       → agent, docker_ops, sandbox, artifacts, patch_grade, prompts/patch_prompt
patch_grade.py → docker_ops, sandbox, agent, artifacts, asan, find (re-attack)
judge.py       → agent, sandbox, artifacts, prompts/judge_prompt
dedup.py       → asan（独立工具，无代理依赖）
agent_image.py → docker_ops（构建镜像，无代理依赖）
```

---

## 9. 提示系统

### 9.1 系统提示（prompts/system_prompt.py）

双层结构：
```
PIPELINE_PREAMBLE（固定，所有代理通用）
        +
ENGAGEMENT_CONTEXT（用户可通过 --engagement-context <file> 覆盖）
```

默认 engagement context："authorized security research on open-source C/C++ target, responsible disclosure"。

### 9.2 各阶段提示特征

| 提示文件 | 关键内容 |
|----------|----------|
| find_prompt.py | 质量层级（HIGH/LOW）、范围外定义、XML 输出格式 |
| grade_prompt.py | 5 项标准清单、评分逻辑 |
| recon_prompt.py | 攻击面分区指导、`<focus_areas>` 标签格式 |
| report_prompt.py | 6 部分分析框架、可利用性评级量表 |
| report_grader_prompt.py | 5 部分评分（0-2 分制） |
| patch_prompt.py | T0-T3 反馈注入位置、git diff 格式要求 |
| judge_prompt.py | manifest 格式、NEW/DUP_BETTER/DUP_SKIP 判断逻辑 |

---

## 10. 去重策略

三层防重设计：

1. **运行时（Find 代理内）：** 提示强制代理输出 `<dup_check>` 标签，与 `found_bugs.jsonl` 比对，对已知签名的漏洞降低优先级
2. **Report 门（--stream 模式）：** Judge 代理对 manifest 中每个现有 bug 进行语义比较，序列化执行防竞态
3. **后处理（dedup 命令）：** 按 `(crash_type, top_frame)` 签名聚类，生成事后摘要

---

## 11. Claude Code 技能（.claude/skills/）

项目包含 6 个交互式技能，支持从 Claude Code 会话中直接使用管道功能：

| 技能 | 命令 | 功能 |
|------|------|------|
| quickstart | `/quickstart` | 30 秒入门指南 + Q&A |
| threat-model | `/threat-model` | 为目标编写威胁模型 |
| vuln-scan | `/vuln-scan` | 静态扫描，发现潜在漏洞区域 |
| triage | `/triage` | 验证、去重和排序已发现漏洞 |
| patch | `/patch` | 生成并应用补丁 |
| customize | `/customize` | 引导移植管道到其他语言/漏洞类型 |

技能共享 `.claude/skills/_lib/` 中的检查点序列化库。

---

## 12. 安全威胁模型

### 12.1 保护边界

| 保护目标 | 机制 |
|----------|------|
| 主机内核 | gVisor 在用户空间拦截并验证系统调用 |
| 网络出站 | vp-internal 网络 + 白名单代理（仅 api.anthropic.com:443） |
| 主机凭据 | 不挂载 `~/.aws`、`.env` 等敏感文件 |
| 构建产物 | 镜像在构建时冻结，代理运行期间无法修改 |
| Find/Grade 边界 | PoC 字节经主机中转，Find 无法直接访问 Grade 容器 |

### 12.2 残余风险

| 风险 | 说明 |
|------|------|
| PoC 内容注入 | 提示中使用 `<untrusted_data>` 块，人工审查补丁前不自动应用 |
| 代理 prompt injection | 目标源代码可能含有对抗性注释；运营商提示优先级高于用户内容 |
| gVisor 逃逸 | gVisor 本身仍有已知漏洞，参见 security.md |

---

## 13. 扩展指南

将管道移植到其他语言或漏洞类型时，需修改的部分：

| 组件 | 修改范围 |
|------|----------|
| Find 提示 | 质量层级、范围外定义、输出格式 |
| Grade 标准 | 5 项清单替换为领域特定验证（如 SQLi、authn bypass） |
| Report 框架 | 6 部分可能需要重构（如 Web 漏洞无需 heap_layout） |
| Patch 验证 | T0-T3 oracle 替换（如符号执行代替 ASAN） |
| asan.py | ASAN 解析替换为目标语言的崩溃格式解析 |

相对不变的部分：CLI 编排（cli.py）、代理包装器（agent.py）、Docker/沙箱基础设施、数据契约（artifacts.py）。

使用 `/customize` 技能可获得交互式移植引导。

---

## 14. 开发参考

### 测试

```bash
pytest tests/
```

覆盖范围：XML 标签解析、ASAN 签名提取、工件序列化、焦点区域渲染、Judge/Compare 决策、报告解析、T0-T3 补丁梯队、技能检查点文件。

### 命令行参考

```bash
# 完整运行（find + grade + judge + report）
vuln-pipeline run <target_dir> \
  --model claude-opus-4-5 \
  --runs 10 \
  --parallel \
  --stream \
  --auto-focus

# 单独运行 recon
vuln-pipeline recon <target_dir> --model claude-opus-4-5

# 对已有结果生成报告
vuln-pipeline report <target_dir> --results-dir results/<target>/<ts>

# 对已有报告生成补丁
vuln-pipeline patch <target_dir> --results-dir results/<target>/<ts> --max-iterations 3

# 去重汇总
vuln-pipeline dedup <target_dir> --results-dir results/<target>/<ts>

# 沙箱模式入口
vp-sandboxed run <target_dir> ...
```

### 提示微调

编辑 `harness/prompts/*.py` 中的模板字符串。各阶段通过对应模块中的 `build_*_prompt()` 函数调用提示。

---

*本文档基于项目源码分析生成，反映仓库当前状态。如有出入，以源码为准。*
