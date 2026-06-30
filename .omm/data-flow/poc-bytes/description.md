触发崩溃的原始输入字节——以 base64 形式存储在 CrashArtifact.poc_bytes 中。通过 `docker cp <容器>:<poc_path> -` 从 Find 容器提取，再通过 `docker cp - <容器>:<路径>` 写入 Grade 容器。这是跨越 Find→Grade 信任边界的唯一工件，在 Grade 提示中被视为完全不可信的输入。
