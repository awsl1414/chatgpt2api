"""账号管理路由包（审计 B-中7：api/accounts.py 巨型 create_router 拆分）。

按业务域拆分子路由模块，每个模块暴露 ``build_router()`` 返回独立 APIRouter：

- ``user_keys``：用户密钥 CRUD（/api/auth/users）
- ``accounts``：账号池列表、新增与删除（/api/accounts）
- ``refresh``：批量刷新与密码重登（/api/accounts/refresh、/api/accounts/re-login）
- ``export``：账号导出（/api/accounts/export）
- ``update``：单账号属性更新（/api/accounts/update）
- ``oauth``：OAuth 登录导入（/api/accounts/oauth）
- ``cpa``：CPA 连接池（/api/cpa/pools）
- ``sub2api``：Sub2API 服务器连接（/api/sub2api/servers）
- ``common``：后台任务调度与入参归一化工具

``create_router()`` 只做组合（include_router），挂载顺序与拆分前的端点定义顺序
一致；path / method / 鉴权 / 响应结构保持不变。
"""
from __future__ import annotations

from fastapi import APIRouter

from api.accounts import accounts, cpa, export, oauth, refresh, sub2api, update, user_keys

# 组合顺序即拆分前 create_router 内的端点定义顺序
_SUB_ROUTERS = (
    user_keys,
    accounts,
    refresh,
    export,
    update,
    oauth,
    cpa,
    sub2api,
)


def create_router() -> APIRouter:
    """组合账号管理各域子路由，返回挂载到应用的单一 APIRouter。"""
    router = APIRouter()
    for module in _SUB_ROUTERS:
        router.include_router(module.build_router())
    return router
