# 技术洞察分析（Vulnerability Discovery Platform）

本目录收录来自漏洞挖掘平台项目（`vulnerability-discovery`）的技术文档，作为 `defending-code-reference-harness` 的架构参考与技术洞察输入。

## 目录结构

```
insights/
├── architecture/          # 平台架构演进文档
│   ├── vuln_platform_architecture_v3.2.md   ← 最新版（当前基线）
│   ├── vuln_platform_architecture_v3.1.md
│   ├── vuln_platform_architecture_v3.md
│   ├── vuln_platform_architecture.md        ← 初始版本
│   └── notes.md                             ← 散记/草稿
├── diagrams/              # 架构图源文件与渲染图
│   ├── architecture.png   ← 整体架构图
│   ├── dataflow.{dot,png} ← 数据流图
│   ├── lifecycle.{dot,png}← 生命周期图
│   ├── ref_codex.{dot,png}← 参考实现：Codex
│   └── ref_mythos.{dot,png}← 参考实现：Mythos
└── user-journey/          # 用户旅程材料
    ├── vuln_platform_user_journey.html       ← 完整旅程（交互式）
    ├── vuln_platform_swimlane_journey.html   ← 泳道图版本
    ├── 用户旅程.html
    ├── 用户旅程 - 副本.html
    └── vuln_platform_user_journey_简版.pptx ← 简版幻灯片
```

## 与本项目的关联

| 本项目模块 | 洞察来源 |
|---|---|
| `harness/agent.py` 多 Agent 并发设计 | `architecture/vuln_platform_architecture_v3.2.md` §任务调度 |
| `docs/architecture-proposal-zh.md` 集中服务层分析 | `architecture/` 全系列演进对比 |
| Find→Grade→Report 流水线 | `diagrams/lifecycle.*` |
| 沙箱隔离边界 | `diagrams/dataflow.*` |
| 产品化路径规划 | `user-journey/` 全套材料 |

> **注意：** 此目录为只读参考资料，不直接参与 harness 的构建或测试流程。
