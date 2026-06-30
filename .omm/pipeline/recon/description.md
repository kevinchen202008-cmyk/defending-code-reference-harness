harness/recon.py。轻量代理（100 轮），在网络隔离容器中读取目标源码，并提出 focus_areas 分区方案——N 个值得单独攻击的独立输入解析子系统。防止并行 Find 代理收敛到同一漏洞。输出：results 根目录下的 focus_areas.json。由 --auto-focus 触发；否则使用 config.yaml 中的 focus_areas。
