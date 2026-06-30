主 CLI 入口点（harness/cli.py），定义 5 个子命令：run、recon、report、patch、dedup。负责阶段编排、通过 asyncio.gather() 实现异步并行、信号处理（SIGTERM/SIGINT）以及结果目录布局。在 pyproject.toml 中注册为 `vuln-pipeline` 入口点。
