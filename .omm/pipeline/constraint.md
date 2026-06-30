Find 代理上限 2000 轮；Grade 上限 50 轮；Recon 上限 100 轮；Report 上限 200 轮；Patch 每次迭代上限 200 轮，最多迭代 5 次。Judge 串行执行（互斥锁），防止两个并行 find 完成时对同一漏洞同时声明 NEW。Patch 阶段要求 config.yaml 中配置 build_command 以通过 T0 层。
