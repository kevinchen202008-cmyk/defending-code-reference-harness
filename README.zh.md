# Defending Code Reference Harness（防御性代码参考工具）

基于 Claude 的自主漏洞发现与修复参考实现，源自我们自 Claude Mythos Preview 发布以来[与多家安全团队合作](https://www.anthropic.com/glasswing)所积累的经验。相关经验总结与最佳实践请见[配套博客文章](https://claude.com/blog/using-llms-to-secure-source-code)（本地副本：[`docs/blog-post.md`](docs/blog-post.md)）。如需仅使用 SDK 的轻量级版本，演示同样的 侦察→发现→分类→报告→修复 循环，请参阅[配套 Cookbook](https://platform.claude.com/cookbook/claude-agent-sdk-06-the-vulnerability-detection-agent)。

本仓库不再维护，不接受贡献。

> 🔒 **需要托管方案？** Anthropic 提供 [Claude Security](https://claude.com/product/claude-security)，这是一款可跨多项目在您的源代码中查找和修复漏洞的托管产品。Claude Security 会扫描您的仓库以发现漏洞，应用多阶段验证流水线减少误报，并让您通过生命周期管理 findings：分类、修复验证和快速修复生成。
>
> 本仓库是基于通用最佳实践的开源参考实现，适用于使用 Claude 查找漏洞。您可以用它构建自己的漏洞发现流水线、自定义逻辑，并可配合任何 Claude API 访问方式使用（包括 Bedrock、Vertex 或 Azure）。

## 目录结构

- **Claude Code 技能**：`/quickstart`、`/threat-model`、`/vuln-scan`、`/triage`、`/patch`、`/customize`——交互式范围界定、扫描、分类和修复。在 Claude Code 中打开本仓库并运行 `/quickstart` 快速上手。
- **`harness/`**：自主参考流水线（侦察→发现→验证→报告→修复），配置用于通过 Docker 和 ASAN 发现 C/C++ 内存漏洞。该工具**是参考实现，不是成品**。整体架构、提示词和沙箱机制可复用，但不保证开箱即用于所有代码库。运行 `/customize` 可将其移植到您的语言、检测器或漏洞类别。

> ⚠️ **安全性说明：** `/quickstart`、`/threat-model`、`/vuln-scan` 和 `/triage` 仅读写文件。对静态 findings（`TRIAGE.json` 或 `VULN-FINDINGS.json`）运行 `/patch` 同样只读写文件。`/customize` 会编辑工具代码并运行验证命令。只要您在 Claude Code 中交互式审批每个工具调用，上述技能均可在无沙箱环境下安全运行。
> 自主参考流水线（包括对流水线结果运行 `/patch`）**会执行目标代码**，因此除非明确覆盖，否则拒绝在 gVisor 沙箱之外运行。初始化请运行一次 `scripts/setup_sandbox.sh`，然后通过 `bin/vp-sandboxed` 调用流水线。详见 [docs/security.md](docs/security.md) 和 [docs/agent-sandbox.md](docs/agent-sandbox.md)。

## 快速开始

```bash
git clone https://github.com/anthropics/defending-code-reference-harness
cd defending-code-reference-harness
claude

# 30 秒简介 + 在 canary 目标上的引导式首次运行
> /quickstart

> /quickstart how do I port the pipeline to Java?
> /quickstart how do I triage all these bugs?
```

## 延伸阅读

- [**博客文章**](docs/blog-post.md) · 配套博客，含经验总结与最佳实践
- [**流水线**](docs/pipeline.md) · 工作原理：流程图、阶段、CLI 参数
- [**安全**](docs/security.md) · 沙箱机制，哪些目录不应挂载
- [**Agent 沙箱**](docs/agent-sandbox.md) · 每个 agent 的 gVisor 隔离 + 出口白名单
- [**定制**](docs/customizing.md) · 移植到我的技术栈；哪些文件需要改以及原因
- [**修复**](docs/patching.md) · 为已验证的崩溃生成并验证修复方案
- [**故障排查**](docs/troubleshooting.md) · 重复 findings、速率限制、子 agent 模型固定
- [**安全护栏**](https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude) · 针对危险网络安全操作的拦截机制

---

## 上手路径

我们合作过的最成功的安全团队，都是上手速度最快的那些。尽管花数月时间设计完美流水线很诱人，我们建议第 1 天从小处入手，随着经验积累逐步扩展。以下步骤遵循这一模式，并基于我们的观察设定了一个有挑战性但合理的节奏。

|                                                             |              |                              |
|-------------------------------------------------------------|--------------|------------------------------|
| [步骤 1](#步骤-1第-1-天构建威胁模型并运行首次静态扫描和分类) | **第 1 天**  | 构建威胁模型并运行首次静态扫描和分类 |
| [步骤 2](#步骤-2第-2-天在-cc-库上运行参考流水线)            | **第 2 天**  | 在 C/C++ 库上运行参考流水线        |
| [步骤 3](#步骤-3第-3-5-天为您的目标定制流水线)              | **第 3-5 天**| 为您的目标定制流水线               |
| [步骤 4](#步骤-4第-2-周启动自主扫描分类和修复)              | **第 2 周**  | 启动自主扫描、分类和修复           |

### 步骤 1（第 1 天）：构建威胁模型并运行首次静态扫描和分类

第 1 天专注于端到端地走完整个流程。仅使用交互式技能，您将构建威胁模型、运行以其为范围的静态扫描、对返回结果进行分类，并起草候选修复方案。当天结束时，您将获得一份威胁模型、一份排序的静态 findings 列表和候选补丁。

相关技能**仅读写您仓库中的文件**。只要您以交互方式运行 Claude Code 并审批每个工具调用，无需沙箱。

```bash
# 将每个子 agent 固定到您想使用的模型
export CLAUDE_CODE_SUBAGENT_MODEL=<model-id>
claude

# 0. 简介 + 引导式首次运行
> /quickstart

# 1. 构建威胁模型（先瞄准再开枪）
> /threat-model bootstrap targets/canary

# 2. 运行以该威胁模型为范围的静态扫描
> /vuln-scan targets/canary

# 3. 验证、去重并排序返回结果
> /triage targets/canary/VULN-FINDINGS.json

# 4. 为已验证的 findings 生成候选修复
> /patch ./TRIAGE.json --repo targets/canary
```

此流程生成 `THREAT_MODEL.md`、`VULN-FINDINGS.{json,md}`、`TRIAGE.{json,md}` 和 `PATCHES/`。

步骤 1 生成的漏洞候选项来自 Claude 对源码的静态审查（不编译也不运行），因此对非 canary 目标预期会有更多误报。步骤 2 将生成**经执行验证**的 findings。

> **注意：** 在 canary 目标上，`/triage` 可能将扫描结果判定为误报。`entry.c` 本身声明是故意设置漏洞的演示代码，`/triage` 会正确排除测试/固件代码中的 bug。若要查看完整的确认/去重/误报流程，请对精选的固件运行（`/triage .claude/skills/triage/fixtures/canary-findings.json --repo targets/canary`），或将步骤 1 的技能指向您自己的代码。

### 步骤 2（第 2 天）：在 C/C++ 库上运行参考流水线

第 2 天，您将从交互式技能转向使用参考流水线进行首次自主运行。您将在自己的环境中对一个已知存在漏洞的开源库运行完整的 侦察→发现→验证→报告 循环，然后为发现的漏洞生成候选补丁。当天结束时，您将获得一组可复现的崩溃、可利用性报告和候选补丁，并对流水线工作方式有切身体会。

运行流水线非常简单：

```bash
# 一次性初始化
python3 -m venv .venv && .venv/bin/pip install -e .
./scripts/setup_sandbox.sh   # 安装 gVisor，构建 agent 镜像并验证隔离；注意：需要 Docker
export ANTHROPIC_API_KEY=sk-ant-...   # 或 CLAUDE_CODE_OAUTH_TOKEN；流水线需要其中之一

# 运行 侦察→发现→验证→报告 循环
bin/vp-sandboxed run drlibs --model <model-id> --runs 3 --parallel --stream --auto-focus
# 为每个 finding 生成候选补丁
bin/vp-sandboxed patch results/drlibs/<timestamp>/ --model <model-id>

# 或者，让 Claude Code 启动流水线并为您监控运行过程
claude
> run the pipeline on drlibs and explain findings as they come
```

循环结果存放在 `results/drlibs/<timestamp>/` 目录中。使用 `--stream` 参数时，第一份报告将在数分钟内出现在 `reports/bug_NN/` 下。

> ⚠️ **`run` 会生成自主 agent。** 流水线在 gVisor 容器内运行每个 agent，出口流量限制仅允许访问 Claude API。除非明确覆盖，否则生成 agent 的子命令拒绝在沙箱外启动。详见 [docs/security.md](docs/security.md) 和 [docs/agent-sandbox.md](docs/agent-sandbox.md)。

流水线底层包含七个阶段：

1. **构建**：将目标编译进带有 ASAN（C/C++ 内存错误检测器）的 Docker 镜像。流水线在首次运行时使用目标的 `Dockerfile` 自动构建此镜像。
2. **侦察**：一个轻量级 agent 在网络隔离的容器内读取源码，并提出分区方案，即"以下 N 个独立的输入解析子系统值得分别攻击"，使并行的 find agent 探索不同区域，而不是聚集到同一个 bug 上。不使用 `--auto-focus` 参数时，流水线使用目标 `config.yaml` 中的 `focus_areas` 列表。
3. **发现**：N 个 agent 并行运行，各自在独立的隔离容器中。每个 agent 读取源码、构造畸形输入，并持续运行 ASAN 二进制，直到某个输入连续 3 次触发崩溃。
4. **验证**：一个独立的评分 agent 在全新容器中重放每个崩溃，该容器从未被 find agent 接触过。从 find agent 传递给评分 agent 的唯一内容，是 find agent 生成的概念验证（PoC）。
5. **去重**：一个裁判 agent 将已验证的崩溃与已报告的 bug 进行比对，判断每个崩溃是新 bug、已知 bug 的更佳示例，还是应跳过的重复项。
6. **报告**：一个报告 agent 为每个唯一 bug 撰写结构化的可利用性分析，包括原语类别、可达性、攀升路径和严重级别等详细信息。
7. **修复**（上述独立的 patch 命令）：一个补丁 agent 编写建议修复方案，评分 agent 确认新代码能够编译、原始 PoC 输入不再触发崩溃、目标测试套件仍能通过，以及全新的 find agent 找不到绕过该修复的方法。

更多详情见 [docs/pipeline.md](docs/pipeline.md)。

### 步骤 3（第 3-5 天）：为您的目标定制流水线

第 3-5 天，您将为自己的目标定制工具。首先将步骤 1 的技能指向您的代码，然后使用 `/customize` 将流水线移植到您的技术栈。到本周结束时，您将拥有一个 `targets/<your-service>/` 目录，流水线可以针对它运行，通过流水线的单次冒烟测试验证，并在步骤 4 中准备好扩展。

参考流水线专为发现 C/C++ 代码中的内存漏洞而设计，但其整体架构是通用的。将其移植到新的漏洞类别或语言，只需回答以下问题：

| 问题                       | C/C++ 参考                       | 您的目标（示例）                      |
|----------------------------|----------------------------------|--------------------------------------|
| 什么是 finding 的信号？     | ASAN 崩溃签名                    | 异常 / 金丝雀文件 / DNS 回调          |
| PoC 是什么样的？            | 触发崩溃的输入文件                | HTTP 请求序列 / 交易列表 / 测试工具   |
| 目标如何构建和运行？         | `Dockerfile`（使用 clang + ASAN）| 您的语言在容器中的构建方式            |

定制之前，先将步骤 1 的技能指向您自己的代码。提醒：它们只读写文件，无需沙箱即可运行。

```bash
claude

> /quickstart how do I customize this for ~/code/my-service?

> /threat-model bootstrap-then-interview ~/code/my-service
> /vuln-scan ~/code/my-service
> /triage ~/code/my-service/VULN-FINDINGS.json --repo ~/code/my-service
```

然后，在 `/customize` 技能中使用这些技能生成的产物，该技能会针对您的代码库修改工具。

```bash
> /customize use ~/code/my-service/{THREAT_MODEL.md,VULN-FINDINGS.json} and ./TRIAGE.md
```

`/customize` 完成后，您将获得一个 `targets/my-service/` 目录。在扩展之前，通过流水线的冒烟测试验证它。

```bash
bin/vp-sandboxed run my-service --model <model-id> --runs 1
```

更多详情见 [docs/customizing.md](docs/customizing.md)。

### 步骤 4（第 2 周）：启动自主扫描、分类和修复

第 2 周，您将对步骤 3 定制的流水线应用于自己的目标，在内层流水线循环之外添加一个**外层**循环——运行多次流水线扫描，对多次运行的 findings 进行分类，按优先级修复，然后重复。

```bash
# 扫描——对目标运行一批并行扫描
bin/vp-sandboxed run my-service --model <model-id> --runs 5 --parallel --stream --auto-focus

# 分类——使用您的威胁模型对所有波次的每个 finding 去重并排序
> /triage results/my-service/ --repo ~/code/my-service --auto --votes 5

# 修复——生成并验证修复方案，从分类排名最高的开始
> /patch results/my-service/<timestamp>/ --model <model-id>
```

> ⚠️ 遵循与[步骤 2](#步骤-2第-2-天在-cc-库上运行参考流水线) 相同的沙箱指南。

单次流水线运行已对自身的 findings 进行验证和去重。`/triage` 可跨多次流水线运行工作。当指向 `results/` 目录时，它会折叠所有运行中的重复项（以及来自 `/vuln-scan` 的静态 findings，如果存在的话），根据您的威胁模型重新校准严重级别，并尝试将每个 finding 路由到对应的组件负责人。

尽可能快速地修复 findings，有助于让外层循环保持尽量高效。当 findings 被修复后，模型无法重新发现它们，转而会挖掘全新的、通常更深层的问题。随着流水线波次的增加，findings 的数量可能会减少，但复杂度可能也会上升。如果快速修复不可行，哪怕只是将之前的 findings 记录到目标的 `known_bugs` 中，也有助于引导未来的运行发现更新的 bug。

自主分类和修复仍是开放性问题，本参考工具尚未完全解决。`/patch` 中的验证策略有助于提高标准，但严重级别和优先级归根结底是关于您的环境的判断，已验证的补丁也并不总能提交到上游。许多合作伙伴反映这些步骤是当前的瓶颈，您应为此预留真实的工程时间。

更多详情见 [docs/triage.md](docs/triage.md) 和 [docs/patching.md](docs/patching.md)。

## 展望未来

初始上手之后，我们合作过的团队通常会在以下几个方向投入：

1. 审查所有内部仓库和关键开源依赖，按照暴露程度、CVE 历史、业务关键性等因素排序，确定最重要的扫描优先级，然后按优先级逐一扫描。
2. 搭建专用的扫描基础设施，将扫描任务从笔记本电脑或临时虚拟机上迁移出去。最成功的团队会抵制"先构建完美扫描平台再扩展"的冲动。
3. 将扫描纳入软件开发生命周期（SDLC）。部分团队已设置定期扫描（如每天、每周），或将扫描加入 CI 流水线。
4. 测试和实验不同模型，找到最适合自身需求的方案。
