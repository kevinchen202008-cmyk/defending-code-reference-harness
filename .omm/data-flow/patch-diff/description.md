reports/bug_NN/patch.diff——Patch 代理生成的 git 格式 diff。由 T0 层在 patch grader 容器内应用（git apply 或 patch -p1），随后用 build_command 重新构建。若 T1/T2/re-attack 失败，diff 内容加上失败证据将反馈给 Patch 代理进行下一轮迭代。合并到上游前需人工审查。
