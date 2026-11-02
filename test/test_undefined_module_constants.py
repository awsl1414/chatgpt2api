"""全仓静态检查：大写常量被引用但未 import、也未在本地定义（防 NameError 回归）。

事故背景
--------
8c95aff（魔术数字收敛）把 ``timeout=60`` 这类裸数字替换成 ``utils.limits``
的具名常量，但在 ``services/account/token_refresh.py`` 与
``services/account/password_login.py`` 漏写 import。``timeout=`` 参数在调用
时才求值，于是运行期抛 ``NameError``；``refresh_access_token`` 的
``except Exception`` 又把它当成刷新失败落池并进入退避，导致 **token 自动刷新
永远失败**。编译期与类型检查都不会发现这类错误，故用 AST 静态兜底。

检查规则
--------
扫描 ``services/``、``api/``、``utils/`` 下所有 ``.py``：对每个
``ast.Name``（读上下文）中匹配 ``^[A-Z][A-Z0-9_]*$`` 的标识符，若该名字在本
模块内既没有被 import、也没有任何绑定（赋值 / 函数参数 / 类名 / 函数名 /
``global`` / ``nonlocal`` / 模式匹配捕获 / PEP 695 类型参数），且不是内置名，
即判为违规。

作用域取「模块内任意位置有过绑定」，与 pyflakes F821 的精确作用域分析相比
更宽松——宁可漏掉跨作用域的误用，也不产生误报，保证这条护栏长期可留。

已知边界
--------
- 模块内出现 ``from x import *`` 时跳过该文件（无法静态判定导入了什么）；
  当前仓库无星号导入。
- 只覆盖目录内业务代码，不含 ``test/``、``scripts/`` 与 ``web/``。
"""

from __future__ import annotations

import ast
import builtins
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("services", "api", "utils")

# 大写常量命名约定：全大写 + 数字 + 下划线，至少两个字符（单个大写字母多为
# PEP 695 类型参数，仍按绑定处理，不会误报）
CONSTANT_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
BUILTIN_NAMES = frozenset(dir(builtins))


def _bound_names(tree: ast.AST) -> set[str]:
    """收集模块内所有绑定的名字（导入、赋值、定义、参数、模式捕获等）。"""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    bound.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            # PEP 695 泛型参数：def f[T](...) / class C[T]
            for type_param in getattr(node, "type_params", ()):
                bound.add(type_param.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.MatchAs) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
        elif isinstance(node, (ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple)):
            bound.add(node.name)
    return bound


def find_undefined_constants(tree: ast.AST) -> list[tuple[int, str]]:
    """返回 ``[(行号, 常量名), ...]``，即被读取但本模块未绑定的常量名。"""
    has_star_import = any(
        isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        for node in ast.walk(tree)
    )
    if has_star_import:
        return []
    bound = _bound_names(tree)
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        name = node.id
        if CONSTANT_NAME_RE.match(name) and name not in bound and name not in BUILTIN_NAMES:
            violations.append((node.lineno, name))
    return violations


def test_scan_dirs_exist() -> None:
    """护栏自身的前置校验：扫描目录存在且能收集到 .py 文件。"""
    for dirname in SCAN_DIRS:
        directory = REPO_ROOT / dirname
        assert directory.is_dir(), f"扫描目录不存在：{directory}"
        assert any(directory.rglob("*.py")), f"扫描目录下没有 .py 文件：{directory}"


def test_no_undefined_module_constants() -> None:
    """services/ api/ utils/ 下不存在「用了大写常量却未 import / 未定义」的模块。"""
    violations: list[str] = []
    for dirname in SCAN_DIRS:
        for path in sorted((REPO_ROOT / dirname).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for lineno, name in find_undefined_constants(tree):
                violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {name}")
    assert not violations, (
        "以下位置引用了未定义的大写常量（运行期会抛 NameError，"
        "通常是常量提取后漏写 import）：\n" + "\n".join(violations)
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # 事故原形：常量替换裸数字但漏 import
        ("import requests\n\ndef f():\n    return requests.get('u', timeout=DEFAULT_REQUEST_TIMEOUT_SECS)\n", [(4, "DEFAULT_REQUEST_TIMEOUT_SECS")]),
        # 已 import：不报
        ("from utils.limits import DEFAULT_REQUEST_TIMEOUT_SECS\n\ndef f():\n    return DEFAULT_REQUEST_TIMEOUT_SECS\n", []),
        # 本地定义：不报
        ("TIMEOUT_SECS = 60\n\ndef f():\n    return TIMEOUT_SECS\n", []),
        # 函数内局部定义：不报
        ("def f():\n    TIMEOUT_SECS = 60\n    return TIMEOUT_SECS\n", []),
        # 函数参数：不报
        ("def f(TIMEOUT_SECS=60):\n    return TIMEOUT_SECS\n", []),
        # import as 别名：不报
        ("from utils import limits as TIMEOUT_SECS\n\ndef f():\n    return TIMEOUT_SECS\n", []),
        # 属性访问不算模块级常量引用：不报
        ("def f(cfg):\n    return cfg.DEFAULT_REQUEST_TIMEOUT_SECS\n", []),
        # 内置名：不报
        ("def f():\n    return NotImplemented\n", []),
    ],
)
def test_find_undefined_constants_detects_violations(source: str, expected: list[tuple[int, str]]) -> None:
    """检测逻辑自身的用例：既能抓到漏 import，也不对合法写法误报。"""
    assert find_undefined_constants(ast.parse(source)) == expected
