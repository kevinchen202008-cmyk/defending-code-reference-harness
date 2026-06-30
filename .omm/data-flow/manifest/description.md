reports/manifest.jsonl——Judge 代理的权威漏洞注册表。每行将 bug_id（bug_00、bug_01……）映射到其 asan_excerpt 和来源 run。由 judge.py 在互斥锁下原子性地写入/更新。Report 代理读取 manifest 条目以避免生成重复报告；Judge 代理读取它来决定 NEW vs DUP。
