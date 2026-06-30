二进制崩溃时捕获的原始 ASAN stderr 文本。由 harness/asan.py 解析，提取：crash_type（如 "heap-buffer-overflow"）、top_frame（第一个项目代码栈帧）、asan_excerpt（SUMMARY 行 + 顶部 N 帧）。摘录是存入 found_bugs.jsonl 和 manifest.jsonl 的去重单元。
