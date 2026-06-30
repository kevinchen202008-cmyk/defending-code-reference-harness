reports/bug_NN/patch_result.json——序列化为 JSON 的 PatchVerdict 数据类。布尔字段：t0_builds、t1_poc_stops、t2_tests_pass、re_attack_clean。还记录最终结果产生于第几次迭代（1-5）以及可选的 T3 风格分数（0-10）。由 patch_grade.py 在每层完成后立即写入。
