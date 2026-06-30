两套命令接口：(1) vuln-pipeline CLI，含 5 个子命令，通过 bin/vp-sandboxed 强制沙箱后执行；(2) 六个 Claude Code 斜杠技能，用于交互式静态分析工作流。CLI 为 Python 程序（pyproject.toml 入口点）；技能为 Claude Code 读取的 Markdown 指令文件。
