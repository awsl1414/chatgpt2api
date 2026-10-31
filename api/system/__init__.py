"""系统管理路由包（审计 B-中7：api/system.py 巨型 create_router 拆分）。

按业务域拆分子路由模块，每个模块暴露 ``build_router(...)`` 返回独立 APIRouter：

- ``auth``：登录身份校验与版本查询（/auth/login、/version）
- ``settings``：配置读写与第三方应用配置（/api/settings、/api/third-party-apps）
- ``images``：图片列表、原始文件/缩略图、删除与打包下载（/api/images、/images）
- ``logs``：日志查询与删除（/api/logs）
- ``proxy``：代理连通性/运行时配置、清障测试与上游模型目录（/api/proxy、/api/upstream-models）
- ``storage``：存储后端信息与图片存储同步（/api/storage、/api/image-storage）
- ``backup``：备份连接测试、列表、执行、下载与删除（/api/backups）
- ``image_tags``：图片标签与存储维护（/api/images/tags、/api/images/storage）
- ``health``：健康检查 JSON 与 HTML 仪表盘（/health）

``create_router(app_version)`` 只做组合（include_router），挂载顺序与拆分前的
端点定义顺序一致；path / method / 鉴权 / 响应结构保持不变。
"""
from __future__ import annotations

from fastapi import APIRouter

from api.system import (
    auth,
    backup,
    health,
    image_tags,
    images,
    logs,
    proxy,
    settings,
    storage,
)


def create_router(app_version: str) -> APIRouter:
    """组合系统管理各域子路由，返回挂载到应用的单一 APIRouter。

    ``app_version`` 仅由需要回显版本的子路由（auth / health）使用。
    """
    router = APIRouter()
    router.include_router(auth.build_router(app_version))
    router.include_router(settings.build_router())
    router.include_router(images.build_router())
    router.include_router(logs.build_router())
    router.include_router(proxy.build_router())
    # 拆分前端点定义顺序为 storage/info → backup/test → image-storage/*，
    # 三个子路由分段挂载以保持全局顺序完全一致
    router.include_router(storage.build_info_router())
    router.include_router(backup.build_test_router())
    router.include_router(storage.build_router())
    router.include_router(backup.build_router())
    router.include_router(image_tags.build_router())
    router.include_router(health.build_router(app_version))
    return router
