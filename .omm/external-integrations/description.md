三个外部集成：Claude API（所有代理的 LLM 后端）、Docker+gVisor（提供隔离的容器运行时）、GitHub（可选的新颖性检查，通过宿主机侧 git log 实现）。出站代理是核心控制点：所有容器的出站流量均经由其转发，且仅允许 api.anthropic.com:443 通过。
