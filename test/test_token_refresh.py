"""TokenRefreshService 刷新链路单测。

覆盖点：
- `refresh_access_token` 决策链：空 token / 账号缺失 / token 仍新鲜 /
  缺 refresh_token / 近期刷新失败退避 → 均不发起刷新；token 过期 → 调
  OAuth 换取新 token 并走 `apply_token_rotation` 落池
- 刷新失败：错误落池（record_token_refresh_error）；`app_session_terminated`
  且账号带邮箱密码时在后台线程触发密码重登回调
- keepalive：`list_refresh_token_keepalive_tokens` 按 3 天锚点挑出到期
  refresh_token（禁用 / 近期错误 / 未到期的排除，按到期时间排序截断批量）
- `refresh_accounts` 批量编排：成功计数、非 TLS 异常计入 errors、TLS 连接
  错误不计入、进度回调 start/update/finish 时序
- `keepalive_refresh_tokens`：强制刷新成功/失败的汇总差异

OAuth 上游（`_request_access_token_refresh`）全部 monkeypatch，不发真实请求。
"""

import base64
import json
import threading
import time
from typing import Any

import pytest

from services.account.token_refresh import TokenRefreshService
from services.config import config

DAY = 24 * 60 * 60


def make_jwt(payload: dict[str, Any]) -> str:
    def encode(value: dict[str, Any]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f'{encode({"alg": "none", "typ": "JWT"})}.{encode(payload)}.sig'


def expired_token(seconds_ago: int = 100) -> str:
    return make_jwt({"exp": int(time.time()) - seconds_ago, "iat": int(time.time()) - 2 * DAY})


def fresh_token() -> str:
    return make_jwt({"exp": int(time.time()) + 30 * DAY, "iat": int(time.time())})


class FakePool:
    """AccountPoolProtocol 最小假实现（无别名链，token 即键）。"""

    def __init__(self, accounts: list[dict[str, Any]]):
        self._accounts = {
            account["access_token"]: dict(account)
            for account in accounts
            if account.get("access_token")
        }
        self.rotation_calls: list[tuple[str, dict, str]] = []
        self.error_calls: list[tuple[str, str, str]] = []

    def get_account_snapshot(self, access_token: str) -> tuple[str, dict | None]:
        account = self._accounts.get(access_token)
        return access_token, dict(account) if account else None

    def record_token_refresh_error(self, access_token: str, event: str, error: str) -> None:
        self.error_calls.append((access_token, event, error))
        account = self._accounts.get(access_token)
        if account:
            account["last_token_refresh_error"] = error
            account["last_token_refresh_error_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    def apply_token_rotation(self, old_access_token: str, token_data: dict, event: str) -> str:
        self.rotation_calls.append((old_access_token, dict(token_data), event))
        new_token = str(token_data.get("access_token") or old_access_token).strip()
        account = self._accounts.pop(old_access_token, None)
        if account:
            account["access_token"] = new_token
            if token_data.get("refresh_token"):
                account["refresh_token"] = str(token_data["refresh_token"])
            if token_data.get("id_token"):
                account["id_token"] = str(token_data["id_token"])
            account["last_token_refresh_error"] = None
            account["last_token_refresh_error_at"] = None
            self._accounts[new_token] = account
        return new_token

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(account) for account in self._accounts.values()]

    def list_accounts(self) -> list[dict[str, Any]]:
        return self.snapshot()

    def get_account(self, access_token: str) -> dict | None:
        account = self._accounts.get(access_token)
        return dict(account) if account else None

    def resolve_access_token(self, access_token: str) -> str:
        return access_token


@pytest.fixture(autouse=True)
def _no_auto_relogin(monkeypatch):
    monkeypatch.setattr(config, "data", {**config.data, "auto_relogin_after_refresh": False})


def make_service(accounts: list[dict[str, Any]]) -> tuple[TokenRefreshService, FakePool]:
    pool = FakePool(accounts)
    return TokenRefreshService(pool), pool


# ---- refresh_access_token 决策链 ----


def test_empty_token_returns_empty():
    service, _ = make_service([])
    assert service.refresh_access_token("") == ""


def test_unknown_account_returns_token_unchanged():
    service, pool = make_service([])
    assert service.refresh_access_token("ghost") == "ghost"
    assert pool.rotation_calls == []


def test_fresh_token_skips_refresh():
    token = fresh_token()
    service, pool = make_service([{"access_token": token, "refresh_token": "rt"}])

    def _fail(refresh_token, account=None):
        raise AssertionError("fresh token 不应触发刷新")

    service._request_access_token_refresh = _fail
    assert service.refresh_access_token(token) == token
    assert pool.rotation_calls == []


def test_expired_token_without_refresh_token_skips_refresh():
    token = expired_token()
    service, pool = make_service([{"access_token": token}])
    assert service.refresh_access_token(token) == token
    assert pool.rotation_calls == []


def test_expired_token_refreshes_and_applies_rotation():
    token = expired_token()
    service, pool = make_service([{"access_token": token, "refresh_token": "rt-old"}])
    service._request_access_token_refresh = lambda refresh_token, account=None: {
        "access_token": "new-token", "refresh_token": "rt-new", "id_token": "id-new",
    }

    result = service.refresh_access_token(token, event="test")

    assert result == "new-token"
    assert pool.rotation_calls == [(token, {"access_token": "new-token", "refresh_token": "rt-new", "id_token": "id-new"}, "test")]
    account = pool.get_account("new-token")
    assert account["refresh_token"] == "rt-new"


def test_refresh_failure_records_error_and_returns_active_token():
    token = expired_token()
    service, pool = make_service([{"access_token": token, "refresh_token": "rt"}])

    def _fail(refresh_token, account=None):
        raise RuntimeError("oauth_refresh_http_400: bad request")

    service._request_access_token_refresh = _fail
    assert service.refresh_access_token(token) == token
    assert len(pool.error_calls) == 1
    assert pool.error_calls[0][2] == "oauth_refresh_http_400: bad request"
    assert pool.rotation_calls == []


def test_app_session_terminated_triggers_relogin_callback():
    token = expired_token()
    service, pool = make_service([{
        "access_token": token, "refresh_token": "rt", "email": "a@b.c", "password": "pw",
    }])

    def _fail(refresh_token, account=None):
        raise RuntimeError("oauth_refresh_http_400: app_session_terminated")

    service._request_access_token_refresh = _fail
    done = threading.Event()
    captured: dict[str, Any] = {}

    def start_relogin(access_token, email, password, event, progress_id=None):
        captured.update(token=access_token, email=email, password=password, event=event)
        done.set()

    service.start_relogin = start_relogin
    service.refresh_access_token(token, event="test")
    assert done.wait(2.0)
    assert captured == {"token": token, "email": "a@b.c", "password": "pw", "event": "test"}


def test_recent_refresh_error_defers_retry_without_force():
    token = expired_token()
    service, pool = make_service([{"access_token": token, "refresh_token": "rt"}])
    pool.record_token_refresh_error(token, "test", "oauth_refresh_http_400")

    def _fail(refresh_token, account=None):
        raise AssertionError("退避期内不应重试刷新")

    service._request_access_token_refresh = _fail
    assert service.refresh_access_token(token) == token
    # force=True 绕过退避
    service._request_access_token_refresh = lambda refresh_token, account=None: {"access_token": "new-token"}
    assert service.refresh_access_token(token, force=True) == "new-token"


# ---- keepalive ----


def test_list_refresh_token_keepalive_tokens_picks_due_accounts():
    old = make_jwt({"exp": int(time.time()) + 30 * DAY})
    accounts = [
        {"access_token": "due-1", "refresh_token": "rt", "last_token_refresh_at": "2020-01-01 00:00:00"},
        {"access_token": "due-2", "refresh_token": "rt", "last_token_refresh_at": "2021-01-01 00:00:00"},
        {"access_token": "not-due", "refresh_token": "rt", "last_token_refresh_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())},
        {"access_token": "disabled", "refresh_token": "rt", "status": "禁用", "last_token_refresh_at": "2020-01-01 00:00:00"},
        {"access_token": "recent-error", "refresh_token": "rt", "last_token_refresh_error_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "last_token_refresh_at": "2020-01-01 00:00:00"},
        {"access_token": "no-rt", "last_token_refresh_at": "2020-01-01 00:00:00"},
    ]
    service, _ = make_service(accounts)
    assert service.list_refresh_token_keepalive_tokens() == ["due-1", "due-2"]


def test_list_refresh_token_keepalive_tokens_limits_batch_size_and_sorts():
    token = make_jwt({"exp": int(time.time()) + 30 * DAY})
    accounts = [
        {"access_token": f"due-{index}", "refresh_token": "rt",
         "last_token_refresh_at": f"2020-01-0{index + 1} 00:00:00"}
        for index in range(5)
    ]
    service, _ = make_service(accounts)
    # 按到期时间升序（最旧优先），最多 3 个
    assert service.list_refresh_token_keepalive_tokens() == ["due-0", "due-1", "due-2"]


def test_list_expiring_access_tokens_filters_by_jwt_exp():
    expired = expired_token()
    fresh = fresh_token()
    service, _ = make_service([
        {"access_token": expired, "refresh_token": "rt"},
        {"access_token": fresh, "refresh_token": "rt"},
        {"access_token": fresh},  # 无 refresh_token
        {"refresh_token": "rt"},  # 无 access_token
    ])
    assert service.list_expiring_access_tokens() == [expired]


# ---- refresh_accounts 批量编排 ----


class FakeProgress:
    def __init__(self):
        self.calls: list[tuple] = []

    def start(self, progress_id: str, total: int) -> None:
        self.calls.append(("start", progress_id, total))

    def update(self, progress_id: str, payload: Any) -> None:
        self.calls.append(("update", progress_id, payload))

    def finish(self, progress_id: str, result: dict | None = None, error: str | None = None) -> None:
        self.calls.append(("finish", progress_id, result, error))


def test_refresh_accounts_counts_successes_and_reports_progress():
    token = expired_token()
    service, pool = make_service([{"access_token": token, "status": "正常", "quota": 3}])
    progress = FakeProgress()
    service.refresh_progress = progress
    service.verify_callback = lambda token_arg, event, defer_invalid_removal=True: {"access_token": token_arg}

    result = service.refresh_accounts([token], progress_id="p1")

    assert result["refreshed"] == 1
    assert result["errors"] == []
    assert result["relogined"] == 0
    assert ("start", "p1", 1) in progress.calls
    updates = [call for call in progress.calls if call[0] == "update"]
    assert updates and updates[0][2] == ("正常", 3)
    assert progress.calls[-1][0] == "finish"


def test_refresh_accounts_records_non_tls_errors_only():
    token_a = expired_token(seconds_ago=100)
    token_b = expired_token(seconds_ago=5000)
    service, _ = make_service([
        {"access_token": token_a, "status": "正常", "quota": 3},
        {"access_token": token_b, "status": "正常", "quota": 3},
    ])

    def verify(token_arg, event, defer_invalid_removal=True):
        if token_arg == token_a:
            raise RuntimeError("curl: (35) TLS connect error")
        raise RuntimeError("upstream boom")

    service.verify_callback = verify
    result = service.refresh_accounts([token_a, token_b])

    assert result["refreshed"] == 0
    # TLS 连接错误是网络问题，不计入账号失败
    assert len(result["errors"]) == 1
    assert result["errors"][0]["error"] == "upstream boom"


def test_refresh_accounts_requires_verify_callback():
    service, _ = make_service([{"access_token": "tok-a"}])
    with pytest.raises(RuntimeError, match="verify_callback"):
        service.refresh_accounts(["tok-a"])


def test_refresh_accounts_empty_input_finishes_progress_immediately():
    service, pool = make_service([{"access_token": "tok-a"}])
    progress = FakeProgress()
    service.refresh_progress = progress
    service.verify_callback = lambda *args, **kwargs: None

    result = service.refresh_accounts([], progress_id="p1")

    assert result["refreshed"] == 0
    assert progress.calls[-1] == ("finish", "p1", result, None)


# ---- keepalive_refresh_tokens ----


def test_keepalive_refresh_tokens_summarizes_success_and_errors():
    token = expired_token()
    service, pool = make_service([{"access_token": token, "refresh_token": "rt", "status": "正常"}])

    service._request_access_token_refresh = lambda refresh_token, account=None: {"access_token": "new-token"}
    result = service.keepalive_refresh_tokens([token])
    assert result["refreshed"] == 1
    assert result["errors"] == []

    # 第二次对已轮换的新 token 强制刷新并失败
    def _fail(refresh_token, account=None):
        raise RuntimeError("oauth_refresh_http_400: bad")

    service._request_access_token_refresh = _fail
    result = service.keepalive_refresh_tokens(["new-token"])
    assert result["refreshed"] == 0
    assert len(result["errors"]) == 1
    assert "oauth_refresh_http_400" in result["errors"][0]["error"]
