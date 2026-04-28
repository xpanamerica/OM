# =============================================================================
# 将下列逻辑并入 ~/.bashrc（建议放在文件最前，或至少放在 PhaseAGI 相关行之前）
# 目的：Cursor Agent / 沙箱子进程会设置 CURSOR_AGENT / CURSOR_SANDBOX 等变量；
#       此时跳过 PhaseAGI 的交互密码，避免「Agent 跑命令永远卡住」。
# 官方参考：Cursor Docs → Agent tools → Terminal → Troubleshooting（CURSOR_AGENT）
# =============================================================================
#
# 示例结构（请把「你的 PhaseAGI 初始化」整段挪到 else 里，不要留在顶层）：
#
#   if [[ -n "${CURSOR_AGENT:-}" ]] || [[ -n "${CURSOR_SANDBOX:-}" ]]; then
#     # Cursor Agent / 沙箱：不加载 PhaseAGI
#     :
#   else
#     # 仅普通真人终端：执行 PhaseAGI
#     # … 原先 PhaseAGI 的代码 …
#   fi
#
# 若你在 Cursor 集成终端里仍需要 conda（且未用工作区 media_app profile），可在 then 分支里按需 source：
#   # [[ -f "$HOME/software/anaconda3/etc/profile.d/conda.sh" ]] && source "$HOME/software/anaconda3/etc/profile.d/conda.sh"
#
# =============================================================================
