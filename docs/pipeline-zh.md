# 参考管道：深度解析

参考管道是一个自主多智能体管道，用于发现 C/C++ 代码库中的内存漏洞。本文介绍管道各阶段的工作原理、如何观察一次运行，以及相关的 CLI 参数。

> ⚠️ **管道会启动自主代理并执行目标代码。**
> 管道在网络出口限制为 Claude API 的 gVisor 容器内运行每个代理。涉及代理启动的子命令在沙箱环境外拒绝启动，除非显式覆盖。详见 [docs/security.md](docs/security.md) 和 [docs/agent-sandbox.md](docs/agent-sandbox.md)。

> 本文介绍参考管道的工作原理。关于其所实现的通用最佳实践，请参阅[博文](blog-post.md)。

## 安装与首次运行

```bash
# 一次性初始化
python3 -m venv .venv && .venv/bin/pip install -e .
./scripts/setup_sandbox.sh   # 安装 gVisor、构建代理镜像、验证隔离效果；注意：需要 Docker
export ANTHROPIC_API_KEY=sk-ant-...   # 或 CLAUDE_CODE_OAUTH_TOKEN；管道运行需要其中之一

# 运行 recon → find → verify → report 循环
bin/vp-sandboxed run drlibs --model <model-id> --runs 3 --parallel --stream --auto-focus
# 为每个发现生成候选补丁
bin/vp-sandboxed patch results/drlibs/<timestamp>/ --model <model-id>
```

先用这样一个小规模的批次来感受管道的工作方式和 token 消耗量，再考虑扩大规模。结果会落在 `results/<target>/<timestamp>/` 目录下。使用 `--stream` 时，首份报告通常在几分钟内出现在 `reports/bug_NN/` 中，无需等待整个批次完成。

你可以通过 Claude Code 来驱动管道。仓库的 `CLAUDE.md` 教会 Claude 如何运行管道的各个阶段以及需要观察什么。从 Claude Code 会话启动运行，便于实时跟踪转录本、询问运行状态，以及在不丢失任何结果的情况下提前停止。

## 各阶段说明

![管道阶段概览图](../static/harness-diagram.png)

**构建（Build）。** 首次对目标执行扫描时，目标的 `Dockerfile` 会被构建成一个启用了 ASAN 的镜像。同一镜像会被 find、grade 和 re-attack 复用，因此每个代理看到的是相同环境中的相同代码。

**侦察（Recon，可选）。** 代理读取源代码树，提出攻击面的划分方案（例如"这里有 8 个值得单独攻击的独立解析器"）。这让并行运行从不同起点出发，避免全部收敛到同一个漏洞。`--auto-focus` 标志会将此步骤作为完整管道的一部分自动执行。如果你已在目标的 `config.yaml` 中手动编写了 `focus_areas:`，可以跳过 recon。

**查找（Find）。** 循环的核心部分。每次运行为每个代理分配一个独立的网络隔离容器。代理读取源码、构造畸形输入，并反复运行 ASAN 二进制程序，直到某个输入在 3/3 次运行中均导致崩溃。输出的是崩溃输入文件，而非书面报告。并行 find 代理共享一个 `found_bugs.jsonl` 日志，在添加新条目前必须说明为何不是重复项。

**评分（Grade）。** 第二个代理在全新容器中重新运行 PoC，验证崩溃是否真实（即可重现、位于项目代码中、不只是内存耗尽）。从 find 容器传递到评分器的只有 PoC 字节，因此评分器不受 find 代理推理的影响。不稳定但真实的崩溃（竞态条件、依赖堆布局的崩溃）可以通过此步骤，但会获得较低评分。评分器代理完成后，每次运行的裁定结果立即写入 `run_NNN/result.json`。

**裁决（Judge）。** 当发现通过评分器时，一个无工具的短暂代理将崩溃与 `reports/manifest.jsonl` 中已有的漏洞进行比较，决定该发现是新漏洞（接受）、已知漏洞的更好示例（替换旧版本），还是重复项（跳过）。Judge 代理串行运行，防止两个同时到达的重复发现被误判为新漏洞。Judge 阶段仅在使用 `--stream` 修饰符时运行。

**报告（Report）。** 对每个新漏洞，报告代理仅使用 PoC 和源代码撰写结构化的可利用性分析。报告包括：损坏的内存允许攻击者做什么、从真实输入可达性如何、升级路径的概述，以及严重程度评级。随后，独立的评分代理对报告进行评分，检查其声明是否有证据支撑（如行号、重现结果），而非仅凭合理的文字描述。报告保存在 `reports/bug_NN/report.json` 中，并包含评分器的分数，便于判断哪些报告最可信。`--novelty` 修饰符（默认关闭）让编排器检查上游 git 历史，使报告能说明漏洞是否已在上游修复。

**去重（Dedup）。** 一个可以事后运行的独立命令，按 ASAN 签名对管道结果进行聚类。适合快速汇总"这 N 个崩溃可聚类为 M 个签名"。

**补丁（Patch）。** 一个独立命令，为每个唯一漏洞生成候选补丁。详见 [patching.md](patching.md)。

## 观察运行过程

转录本和结果在产生时立即写入磁盘，因此可以在不停止运行的情况下实时观察：

- 每个 find 和 grade 代理的转录本在代理工作时落在 `results/<target>/<ts>/run_NNN/` 下。转录本在运行失败或被终止时仍会保留。
- `found_bugs.jsonl` 列出迄今为止提交的每个崩溃。
- 每次运行的 `result.json` 在评分代理完成审核后立即写入，因此统计 `run_*/result.json` 文件数量即可知道有多少次运行已完成。
- 在转录本中过滤 `"type":"tool_use"` 可以看到代理运行的每条命令。这是在迭代提示词时了解代理实际行为的最快方式。
- 使用 `--stream` 时，`reports/` 目录也会在运行期间逐步填充。Judge 和 report 的转录本保存在那里，`ls reports/bug_*/report.json` 可以查看已写入的报告。

## CLI 参考

```bash
bin/vp-sandboxed recon  <target> --model <m>             # 提议 focus_areas（将 YAML 输出到 stdout）
bin/vp-sandboxed run    <target> --model <m>             # 运行单个 find 代理 + grade 代理
bin/vp-sandboxed run    <target> --runs N --parallel     # 同时运行 N 个 find 代理（按焦点区域分配）
bin/vp-sandboxed run    <target> --stream                # 每次崩溃通过评分后立即运行 judge + report（推荐）
bin/vp-sandboxed run    <target> --auto-focus            # 先运行 recon 并使用其划分结果
bin/vp-sandboxed run    <target> --find-only             # 跳过评分（适合迭代提示词）
bin/vp-sandboxed run    <target> --accept-dos            # 将 DoS 类崩溃计为有效发现
bin/vp-sandboxed run    <target> --novelty               # 报告检查上游 git 历史以确定修复状态
bin/vp-sandboxed run    <target> --max-turns N           # 每个代理的轮次预算
bin/vp-sandboxed run    <target> --engagement-context F  # 包含组织授权范围的文件，注入每个代理提示
bin/vp-sandboxed run    <target> --resume <results-dir>  # 继续被终止的批次，跳过已完成的运行
bin/vp-sandboxed report results/<target>/<ts>/           # 批量报告模式，用于不带 --stream 完成的运行
bin/vp-sandboxed report results/<target>/<ts>/ --fresh   # 重新生成报告，忽略已有的 report.json 检查点
bin/vp-sandboxed patch  results/<target>/<ts>/           # 为每个唯一漏洞提议并验证修复方案
bin/vp-sandboxed dedup  results/<target>/<ts>/           # 按签名分组崩溃
```

> 本参考仅列出最常用的标志。完整标志集请对任意子命令使用 `--help`。

## 设计原则

简而言之，一个有效的漏洞发现管道的核心步骤：

1. 构建目标。
2. 启动 N 个代理搜索漏洞。
3. 对发现结果进行评分。

我们发现，将其分解为模块化步骤最为有效——每个步骤持久化保存其进度——并随时间增加了去重、报告撰写等更多步骤。Docker 容器镜像是存储可复用构建产物的好方式，并提供了一个可以安全尝试漏洞利用的环境。漏洞发现代理应以可被评分器验证的标准格式存储结果。这些代理可以自行决定探索路径，或者通过 recon 步骤为其提供"焦点区域"作为种子。评分器应能根据人工反馈对任意发现多次运行。

除了模块化，一个关键组件是有效的评分器。评分器必须作为独立代理运行，并能访问干净的沙箱以运行任何 PoC。它应被定位为积极尝试推翻发现的对手——发现结果在被证明之前是"有罪的"。能产生见证的 PoC 利用最佳，但并非总是可行。评分器还应针对所检查的漏洞类型量身定制：某些漏洞通过 PoC 证明，其他的则通过逻辑论证。当多个类别在范围内时，使用技能或轻量级路由层分发到不同验证器可能是好方法。

## 错误恢复与断点续跑

遭遇速率限制或其他错误不会丢失工作。每个代理是一个长期运行的 `claude -p` 会话。429 或 5xx 错误首先在 Claude CLI 内部通过退避重试。如果这些重试耗尽，管道会运行自己的退避重试循环。这些重试使用 Claude CLI 的 `--resume <session_id>` 重新启动代理，这会恢复完整对话，使代理能从失败的轮次继续。最多重试 20 次，之后将该次运行标记为失败。即便如此，你仍可以使用 `bin/vp-sandboxed run <target> --resume <results-dir>` 重启运行。

如果你自己构建管道，建议加入类似的逻辑。
