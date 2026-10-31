"""跨模块共享的请求超时等数值上限常量（魔术数字收敛）。

只收编多个模块复用同一语义的数值；单文件专用的数值放在各自文件顶部具名常量。
所有常量仅做字面提取，取值与提取前的裸数字一致。
"""
from __future__ import annotations

# 辅助/管理链路单请求超时（sub2api、CPA 管理 API、WebDAV、备份对象、登录流程等）
SHORT_REQUEST_TIMEOUT_SECS = 30

# 主链路单请求默认超时（对话元数据、文件注册、令牌获取等）
DEFAULT_REQUEST_TIMEOUT_SECS = 60

# 长请求超时（SSE 长流式对话、大文件下载等）
LONG_REQUEST_TIMEOUT_SECS = 300
