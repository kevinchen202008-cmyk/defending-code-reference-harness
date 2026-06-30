results/<ts>/found_bugs.jsonl——只追加的共享去重日志。每行为一个 JSON 对象，包含 asan_excerpt（SUMMARY + 顶部帧）。运行开始时以 config.yaml 的 known_bugs 初始化。Find 代理提交前读取此文件并生成 <dup_check> 标签。Grade 每次通过后追加新条目；多个并行 find 代理的追加串行化执行。
