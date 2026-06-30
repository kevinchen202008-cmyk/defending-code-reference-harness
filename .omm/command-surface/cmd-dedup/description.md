`vuln-pipeline dedup <results_dir>` ——只读后处理命令。遍历所有 run_NNN/result.json，通过 asan.py 提取 (crash_type, top_frame) ASAN 签名并聚类，打印去重摘要报告。不写入任何工件。适合在启动报告生成前对批次发现结果进行快速人工概览。
