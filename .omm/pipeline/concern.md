两容器信任边界（Find → 宿主机中转 → Grade）是防范奖励黑客的核心防线。若绕过此中转或使用 --dangerously-no-sandbox，Find 代理可能在 Grade 容器中预置状态。Patch 验证中的 Re-attack 层仅为 50 轮 find 代理——通过并不代表修复完整，只说明该代理无法在有限轮次内绕过。
