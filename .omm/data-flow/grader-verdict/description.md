来自 harness/artifacts.py 的 GraderVerdict 数据类。字段：passed（布尔值）、score（0.0-1.0，基于崩溃稳定性）、criteria（5 项通过/失败检查的字典）。由 grade.py 在 Grade 代理完成 50 轮会话后产生，立即序列化为 RunResult 并写入 result.json——无缓冲。
