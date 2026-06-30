主 CLI 入口点，在 pyproject.toml 中注册为 `vuln-pipeline` → harness.cli:main。解析子命令、从 config.yaml 加载 TargetConfig、认证（ANTHROPIC_API_KEY 或 CLAUDE_CODE_OAUTH_TOKEN）、构建 Docker 镜像，然后分派到对应的阶段编排函数。
