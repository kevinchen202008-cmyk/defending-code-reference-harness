# 故障排查 / 常见问题

## 重复发现

独立代理会收敛到"最容易发现的漏洞"。管道通过共享的 `found_bugs.jsonl` 缓解这一问题——代理在发现期间向其填充数据，并在提交前与之进行去重比对——但这不能消除所有碰撞。在第二次运行时，将第一次运行的发现输入到 `config.yaml` 的 `known_bugs` 中，有助于代理避免再次收敛到相同路径。

对于交互式扫描，运行 `/triage ./VULN-FINDINGS.json` 以合并重复项并按推导的可利用性重新排序。

## 速率限制

作为粗略参考，每个代理预计约 10K 未缓存输入 token/分钟和约 2K 输出 token/分钟。你可以将并行度扩展到账户的 ITPM 限制（大约**每 10 万 ITPM 可运行 10 个代理**）。你可以在 [Claude 控制台](https://console.claude.com/settings/limits)中查看你的限制。

短暂超出限制并不是灾难性的。管道在 429 错误后会恢复，且不会丢失对话上下文（见 [pipeline.md#resume-on-error](pipeline.md#resume-on-error)）。你不需要将并发量控制到远低于已配置容量。

## 技能在大型代码库上运行中途崩溃

`/threat-model bootstrap` 和 `/triage` 分别将每阶段检查点写入 `./.threat-model-state/` 和 `./.triage-state/`，与输出文件并列。如果运行因上下文耗尽、速率限制或 Ctrl-C 而中止，**只需重新调用相同命令**。它会读取 `progress.json`，从每阶段的 JSON 文件恢复状态，并从下一阶段/步骤继续，而不会重新启动已完成的子代理。传递 `--fresh` 可丢弃检查点并重新开始。

检查点通过 `.claude/skills/_lib/checkpoint.py` 原子写入，最终输出（`THREAT_MODEL.md` / `TRIAGE.md`）每次追加一节。因此，中途停顿最多丢失一节，而不是整个文件。

## 管道运行在批次中途崩溃

```bash
bin/vp-sandboxed run <target> --runs N --resume results/<target>/<ts>/
bin/vp-sandboxed report results/<target>/<ts>/          # 跳过已报告的漏洞
bin/vp-sandboxed report results/<target>/<ts>/ --fresh  # 强制完整重新报告
```

`--resume` 跳过 `result.json` 已达到终态（`crash_found` / `crash_rejected` / `no_crash_found`）的任何运行，并重试失败的运行（`agent_failed` / `build_failed` / `error`）。`found_bugs.jsonl` 和 `focus_areas.json` 会延续，因此恢复的运行看到相同的去重上下文。

这个管道级别的恢复（可在编排器被终止后存活）不同于 [pipeline.md#resume-on-error](pipeline.md#resume-on-error) 中描述的单代理会话恢复——后者在 API 错误后恢复单个代理的对话。

## 假阳性

假阳性最常见的原因不是模型错误阅读代码，而是模型不了解你的信任边界。如果某一整类发现以相同方式出错，请将缺失的假设写入你的 `THREAT_MODEL.md`。博文的[威胁模型章节](blog-post.md#1-threat-model-define-what-counts-as-a-vulnerability)对此有详细描述，并解释了为什么这是正确的起点。

另外两个修复措施也可能有帮助：
- **添加怀疑论 judge。** 一个读取每个发现及其批评，然后做出决定的独立代理。当被直接询问时，模型会可靠地降低自身发现的评级。
- **寻找模型看不见的缓解措施。** 常见的假阳性模式是代码路径是真实的，但调用服务中的验证或共享的 sanitizer 使其不可达。询问模型想要什么上游上下文（调用服务、配置、中间件）并提供，或者提供显示缓解措施在运行时触发的跟踪/日志。

先调整精准率，再调整召回率——将假阳性率降低到你信任输出的程度，*然后*再扩大网络。按这个顺序工作的团队，在精准率稳固后大约将召回率提高了一倍。

## 覆盖率和边际收益递减

如果第一次扫描只覆盖了应用表面的一小部分（一个团队发现初始传递覆盖了约 3% 的 API 端点），修复方法通常是 recon，而不是增加更多 find 代理。提高焦点区域数量，或者给 recon 提供端点清单，使其对完整表面进行分区。在不重新分区的情况下增加 find 代理会迅速产生边际收益递减，因为它们很可能收敛到相同漏洞。

一个值得追踪的完整性信号是跨所有 find 转录本触及的代码行数。将缺失的代码路径作为未来 find 代理运行的焦点区域。

## 子代理使用错误的模型

Claude Code 可能会在低于你主会话级别的模型上启动子代理。固定它们：

```bash
export CLAUDE_CODE_SUBAGENT_MODEL=<model-id>
```

或者在你的子代理定义中设置 `model: inherit`。如果有任何请求按层级名称指定模型，你也可以使用 `ANTHROPIC_DEFAULT_HAIKU_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL` 和 `ANTHROPIC_DEFAULT_OPUS_MODEL` 固定每个层级的解析目标。
