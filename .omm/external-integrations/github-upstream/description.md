GitHub（仅在 --novelty 标志启用时使用）。编排器宿主机对目标 github_url 执行浅克隆，然后运行 `git log <固定提交>..HEAD -- <崩溃文件>`。结果注入 Report 代理提示，使报告能够标注 FIXED/UNFIXED 状态。默认禁用——隔离或出站受限环境不应使用此标志。报告容器的出站流量无论如何都仅限于 API；只有编排器宿主机访问 GitHub。
