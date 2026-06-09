# 分类：如何处理这数百个发现？

你的管道（或其他扫描器）刚刚产生了一堆原始发现。`/triage` 技能将这堆发现转化为一份简短的、按优先级排序的、已分配责任人的列表，供工程团队直接采取行动。

## 它做什么

该技能在单次传递中完成四件事：

1. **验证（Verify）。** 对源代码进行对抗性检查（只读，不执行代码），丢弃不真实的发现。
2. **去重（Deduplicate）。** 合并跨并行运行或多个扫描器重复报告的同一根本原因。
3. **重新排序（Re-rank）。** 根据前提条件和你声明的信任边界推导严重性。例如，需要一两个前提条件且通过已认证访问触发的"高危"会降级为中危。
4. **路由（Route）。** 为每个留存的发现标记组件负责人，以便适当路由。

它输出 `TRIAGE.md`（人类可读的按优先级排序的发现列表）和 `TRIAGE.json`（机器可读的发现列表，用于你的跟踪系统或其他下游使用）。

## 它应用的规则

- **重复项。** 如果修复一个发现同时修复了另一个，则两者为重复项。该技能通过两次传递尝试识别这些情况。首先是一次廉价的确定性传递，检查两个发现是否位于同一文件、具有相同类别，且行号在十行以内。其次是一次 LLM 传递，要求模型使用语义推理识别重复项。
- **严重性。** 基于攻击者实际需要做什么才能利用该发现。验证器首先列出前提条件，然后将数量映射为分数——零个，且具有未认证远程访问 = 高危；一两个，或经过认证的路径 = 中危；三个或更多，或仅限本地 = 低危。在技能运行开始时，你可以换入自己的评分标准。

要了解这两者背后的完整推理，请阅读[博文的分类章节](blog-post.md#5-triage-deduplicate-by-root-cause-rank-by-preconditions-and-impact)。

## 运行方式

```bash
# 对管道输出进行分类
> /triage results/<target>/<timestamp>/ --repo ./path/to/source

# 对 /vuln-scan 输出进行分类
> /triage ./VULN-FINDINGS.json --repo ./path/to/source

# 非交互式，每个发现使用更多验证器投票（默认为 3）
> /triage ./findings/ --auto --votes 5 --repo ./path/to/source

# 使用组织特定的假阳性规则（见 customizing.md）
> /triage ./VULN-FINDINGS.json --repo ./src --fp-rules .claude/fp-rules.txt
```

默认情况下，该技能会**先与你访谈**，了解你的信任边界、威胁模型、评分标准（高/中/低 vs. CVSS vs. 你的组织漏洞标准），以及在分票时偏向精准率还是召回率。这些答案会影响验证和排序。传递 `--auto` 可跳过访谈并使用偏向精准率的默认值。

## 何时使用 triage

管道自身的 grade、judge 和 dedup 阶段已应用了其中部分原则。`/triage` 是其之上跨运行、跨扫描器的层次，并且可以处理*任何*发现文件，不仅限于管道输出。如果你现在面前有一堆发现（一个新的 `/vuln-scan` 输出、多次管道运行的重叠结果，或来自早期工具的旧积压），并希望对其进行验证、合并和排序，请使用它。

如果管道运行持续产生大量噪音，最好先考虑改进管道本身。确保使用 `--stream` 以便 judge 代理对报告内容进行门控（见 [pipeline.md](pipeline.md)），并在目标的 `known_bugs` 中设置种子，以防止代理反复收敛到相同崩溃（见 [troubleshooting.md 中的重复发现](troubleshooting.md#duplicate-findings)）。

## 分类后：打补丁

对于管道产生的崩溃（含 PoC 和 ASAN 跟踪），`bin/vp-sandboxed patch` 可为每个崩溃生成并验证修复方案。详见 [patching.md](patching.md)。对于没有可运行 PoC 的发现，请参阅 [patching.md 的静态模式](patching.md#运动式补丁生成patch-技能静态模式)。
