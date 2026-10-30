"""账号域包（审计 B-高3：account_service 上帝类拆分）。

模块划分：
- ``models``：账号 Pydantic 模型、归一化与判定函数、包内协议。
- ``pool``：号池（CRUD、持久化、token 别名、图片槽位并发、统计）。
- ``token_refresh``：access_token 刷新与 refresh_token keepalive。
- ``password_login``：邮箱密码登录与自动/手动重新登录编排。
- ``progress``：泛型进度追踪器。

依赖方向：pool 为底层；token_refresh / password_login 通过
``models`` 中的协议依赖号池实例（组装层注入），不反向 import pool；
``services/account_service.py`` 仅为组装 facade，对外调用面保持不变。
"""
