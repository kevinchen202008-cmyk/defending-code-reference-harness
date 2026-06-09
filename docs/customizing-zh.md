# 自定义管道

开箱即用的参考管道针对 C/C++ 代码中的内存漏洞，使用 ASAN 作为崩溃检测器。但管道的整体架构更具通用性——适配其他语言或漏洞类型，只需更新 C/C++ 和 ASAN 专属的部分。

## 从这里开始

在仓库根目录下，于 Claude Code 中运行：

```
> /customize
```

该技能读取管道源码，询问你关于目标的信息（语言、如何检测发现、构建系统、关心哪些漏洞类别），并提出具体的迁移计划。如果无法使用 Claude Code，可将 `.claude/skills/customize/SKILL.md` 的内容粘贴到其他 AI 编码工具中。

## 移植通常涉及的工作

大多数情况下，移植此管道意味着为新的软件栈构建容器镜像。这可以手动完成，也可以使用你的标准流程，只要最终结果是管道代理能在可复现的容器中检查并运行目标代码即可。在跨多个代码库大规模进行漏洞挖掘时，我们发现将*这项*任务也委托给代理非常有价值：搭建镜像既繁琐，而配备前沿模型的沙箱代理擅长生成能完整工作的构建配置。

利用 Claude Code 审查历次运行的转录本、建议改进管道和提示词，是迭代和完善特定移植版本的好方法。

**运行多个管道是完全可以的。** 许多团队维护几个有各自侧重点的变体（一个针对最强大的模型调优，一个将问题分解为更小块以适配更便宜的模型，一个针对特定漏洞类别），并合并结果。某个管道会显式或隐式地编码一组假设，增加具有不同假设的变体可以发现不同的问题。

## C/C++ 专属内容的具体位置

1. **Find 和 Grade**（`harness/prompts/find_prompt.py` 和 `harness/prompts/grade_prompt.py`）：
   find 代理寻找什么，以及评分器接受什么作为真实崩溃。在 find 提示中，主要是"崩溃质量层级"和"范围外"部分，以及输出格式中的崩溃字段。在 grade 提示中，是五项标准的评分细则。

2. **Report 和 Report Grader**（`harness/prompts/report_prompt.py` 和 `harness/prompts/report_grader_prompt.py`）：
   可利用性报告的各节内容以及对这些节评分的细则，目前基于内存损坏场景（堆布局、升级路径）。

3. **Patch 和 Patch Grader**（`harness/prompts/patch_prompt.py` 和 `harness/patch_grade.py`）：
   如何请求修复，以及什么算作已修复。

4. **崩溃签名**（`harness/asan.py`）：
   如何将检测器输出转换为去重签名。

5. **目标本身**（`targets/<target>/Dockerfile`）：
   如何在启用检测器的情况下构建目标，以及构建和测试命令。

编排层（`harness/cli.py`、`harness/find.py`、`harness/grade.py`、`harness/report.py`）大多是通用的管道代码，移植时通常只需极少改动即可保留。

## 调整交互式技能

如果不需要完整的移植，只想让 `/vuln-scan` 和 `/triage` 理解你的技术栈，两者都支持纯文本指令文件：

```
> /vuln-scan ./src --extra .claude/scan-extras.txt
> /triage ./VULN-FINDINGS.json --fp-rules .claude/fp-rules.txt
```

`--extra` 向扫描简报追加组织特定的漏洞类别（例如 GraphQL 深度攻击、PCI 数据留存、自定义鉴权层）。

`--fp-rules` 向分类验证器追加组织特定的排除规则（例如"我们全面使用 Prisma，只关注原始查询 SQLi"，"k8s 资源限制已覆盖 DoS"）。

如果使用这些文件调整技能，建议将它们与代码一起纳入版本控制。
