"""FastAPI 路由层。

职责边界：只做参数校验、鉴权与错误映射，业务逻辑全部在 services/ 层。
"""
from api.app import create_app

