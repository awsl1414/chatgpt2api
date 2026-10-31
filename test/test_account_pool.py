"""AccountPool 号池单测。

覆盖点：
- 账号 CRUD：`add_accounts` 去重与累计计数、`delete_accounts` 连带清理
  别名与图片在途计数、`update_account` 状态更新
- token 别名解析：`apply_token_rotation` 轮换后旧 token 可解析、在途图片
  计数迁移、空 token 回退旧值
- token 获取：`get_text_access_token` 轮询分配与刷新回调、模型路由缺失时
  的 ModelUnavailableError；`get_available_access_token` 远程校验回调的
  成功 / 异常重试 / 配额耗尽 QuotaExhaustedError
- 图片槽位并发（Condition 等待/唤醒）：并发上限占满时阻塞、释放后唤醒；
  `release_image_slot` 计数递减与归零清理
- 结果回写：`mark_image_result` 成功/失败计数、额度归零转限流
- 失效处理：`record_invalid_token_seen` 新账号宽限与重复失效判定、
  `record_token_refresh_error` 错误落池

日志单例与累计计数文件打桩，不发任何网络请求。
"""

import threading
from typing import Any

import pytest

from services.account.pool import AccountPool
from services.config import config
from services.errors import ModelUnavailableError, QuotaExhaustedError
from services.log_service import log_service


class MemoryStorage:
    """StorageBackend 最小假实现（与既有测试一致）。"""

    def __init__(self, accounts: list[dict[str, Any]] | None = None) -> None:
        self.accounts = list(accounts or [])
        self.saved: list[list[dict[str, Any]]] = []

    def load_accounts(self) -> list[dict[str, Any]]:
        return list(self.accounts)

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = list(accounts)
        self.saved.append(list(accounts))

    def load_auth_keys(self) -> list[dict[str, Any]]:
        return []

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"ok": True}

    def get_backend_info(self) -> dict[str, Any]:
        return {"type": "memory"}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """打桩：账号日志、累计计数文件、自动移除开关关闭。"""
    monkeypatch.setattr(log_service, "add", lambda *args, **kwargs: None)
    monkeypatch.setattr(AccountPool, "_get_cumulative_file", lambda self: tmp_path / "cumulative_total")
    monkeypatch.setattr(config, "data", {
        **config.data,
        "auto_remove_invalid_accounts": False,
        "auto_remove_rate_limited_accounts": False,
        "image_account_concurrency": 1,
    })


def make_pool(accounts: list[dict[str, Any]] | None = None) -> AccountPool:
    return AccountPool(MemoryStorage(accounts))


def make_account(token: str, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"access_token": token, "status": "正常", "quota": 5}
    fields.update(overrides)
    return fields


# ---- 账号 CRUD ----


def test_add_accounts_dedups_and_counts():
    pool = make_pool()
    result = pool.add_accounts(["tok-a", "tok-a", "tok-b"])
    assert result["added"] == 2
    assert result["skipped"] == 0
    assert set(pool.list_tokens()) == {"tok-a", "tok-b"}

    result_again = pool.add_accounts(["tok-a", "tok-c"])
    assert result_again["added"] == 1
    assert result_again["skipped"] == 1
    assert pool.get_stats()["cumulative_total"] == 3


def test_add_accounts_ignores_empty_tokens():
    pool = make_pool()
    result = pool.add_accounts(["", "  "])
    assert result["added"] == 0
    assert pool.list_tokens() == []


def test_delete_accounts_removes_and_cleans_alias_and_inflight():
    pool = make_pool([make_account("tok-a")])
    pool.add_account_items([make_account("tok-old")])
    pool.apply_token_rotation("tok-old", {"access_token": "tok-new"}, "test")
    assert pool.resolve_access_token("tok-old") == "tok-new"

    pool._acquire_next_candidate_token(excluded_tokens={"tok-a"})  # 让 tok-new 产生在途计数
    result = pool.delete_accounts(["tok-new"])
    assert result["removed"] == 1
    assert pool.list_tokens() == ["tok-a"]
    # 别名与在途计数一并清理
    assert pool.resolve_access_token("tok-old") == "tok-old"
    assert pool.get_account("tok-old") is None
    assert all(account.get("image_inflight", 0) == 0 for account in pool.list_accounts())


def test_update_account_applies_fields():
    pool = make_pool([make_account("tok-a")])
    updated = pool.update_account("tok-a", {"status": "限流", "quota": 0})
    assert updated is not None
    assert updated["status"] == "限流"


# ---- token 别名与轮换 ----


def test_apply_token_rotation_rotates_and_migrates_inflight():
    pool = make_pool([make_account("tok-a", refresh_token="rt-old", invalid_count=3)])
    pool._acquire_next_candidate_token()  # tok-a 在途 1

    new_token = pool.apply_token_rotation(
        "tok-a",
        {"access_token": "tok-a2", "refresh_token": "rt-new", "id_token": "id-new"},
        "test",
    )
    assert new_token == "tok-a2"
    # 旧 token 仍可解析，且账号字段被新值覆盖
    account = pool.get_account("tok-a")
    assert account is not None
    assert account["access_token"] == "tok-a2"
    assert account["refresh_token"] == "rt-new"
    assert account["id_token"] == "id-new"
    assert account["invalid_count"] == 0
    assert account["last_token_refresh_error"] is None
    # 在途计数迁移到新 token
    inflight = {item["access_token"]: item["image_inflight"] for item in pool.list_accounts()}
    assert inflight.get("tok-a2") == 1

    # 旧 token 再次轮换（别名链）也能落到新账号
    assert pool.resolve_access_token("tok-a") == "tok-a2"


def test_apply_token_rotation_keeps_old_token_when_new_token_empty():
    pool = make_pool([make_account("tok-a")])
    assert pool.apply_token_rotation("tok-a", {"access_token": "  "}, "test") == "tok-a"


def test_apply_token_rotation_unknown_token_returns_resolved():
    pool = make_pool()
    assert pool.apply_token_rotation("missing", {"access_token": "x"}, "test") == "missing"


def test_record_token_refresh_error_persists_fields():
    pool = make_pool([make_account("tok-a")])
    pool.record_token_refresh_error("tok-a", "event-1", "oauth_refresh_http_400: bad")
    account = pool.get_account("tok-a")
    assert account["last_token_refresh_error"] == "oauth_refresh_http_400: bad"
    assert account["last_token_refresh_error_at"]


# ---- 文本链路取 token ----


def test_get_text_access_token_round_robins_and_calls_refresh_callback():
    pool = make_pool([make_account("tok-a"), make_account("tok-b")])
    refreshed: list[str] = []
    pool.refresh_callback = lambda token, event=None: (refreshed.append(token), token.upper())[1]

    first = pool.get_text_access_token()
    second = pool.get_text_access_token()
    assert {first, second} == {"TOK-A", "TOK-B"}
    assert refreshed == [first.lower(), second.lower()]


def test_get_text_access_token_returns_callback_result():
    pool = make_pool([make_account("tok-a")])
    pool.refresh_callback = lambda token, event=None: "rotated-token"
    assert pool.get_text_access_token() == "rotated-token"


def test_get_text_access_token_requires_refresh_callback():
    pool = make_pool([make_account("tok-a")])
    with pytest.raises(RuntimeError, match="refresh_callback"):
        pool.get_text_access_token()


def test_get_text_access_token_respects_exclusions_and_empty_pool():
    pool = make_pool([make_account("tok-a"), make_account("tok-b")])
    pool.refresh_callback = lambda token, event=None: token
    assert pool.get_text_access_token(excluded_tokens={"tok-a", "tok-b"}) == ""

    empty_pool = make_pool()
    empty_pool.refresh_callback = lambda token, event=None: token
    assert empty_pool.get_text_access_token() == ""


def test_get_text_access_token_unroutable_model_raises():
    pool = make_pool([make_account("tok-a")])
    pool.refresh_callback = lambda token, event=None: token
    with pytest.raises(ModelUnavailableError, match="model catalog is unavailable"):
        pool.get_text_access_token(model="gpt-5-5")


# ---- 图片槽位并发 ----


def test_acquire_next_candidate_token_raises_without_candidates():
    pool = make_pool()
    with pytest.raises(QuotaExhaustedError, match="no available image quota"):
        pool._acquire_next_candidate_token()


def test_acquire_next_candidate_token_blocks_until_release():
    pool = make_pool([make_account("tok-a")])
    first = pool._acquire_next_candidate_token()
    assert first == "tok-a"

    result: dict[str, str] = {}

    def acquire() -> None:
        result["token"] = pool._acquire_next_candidate_token()

    thread = threading.Thread(target=acquire, daemon=True)
    thread.start()
    thread.join(0.3)
    # 并发槽位占满，第二个获取被 Condition 阻塞
    assert thread.is_alive()
    assert result == {}

    pool.release_image_slot(first)
    thread.join(2.0)
    assert not thread.is_alive()
    assert result["token"] == "tok-a"
    # 释放的槽位立即被等待者重新占用（在途数回到 1）
    assert pool.list_accounts()[0]["image_inflight"] == 1
    # 再次释放后归零清理
    pool.release_image_slot("tok-a")
    assert pool.list_accounts()[0]["image_inflight"] == 0


def test_acquire_next_candidate_token_rotates_across_accounts():
    pool = make_pool([make_account("tok-a"), make_account("tok-b")])
    acquired = []
    for _ in range(4):
        token = pool._acquire_next_candidate_token()
        acquired.append(token)
        pool.release_image_slot(token)  # concurrency=1，每次取用后立即释放
    assert set(acquired) == {"tok-a", "tok-b"}
    assert all(item["image_inflight"] == 0 for item in pool.list_accounts())


def test_acquire_next_candidate_token_respects_exclusions():
    pool = make_pool([make_account("tok-a"), make_account("tok-b")])
    token = pool._acquire_next_candidate_token(excluded_tokens={"tok-a"})
    assert token == "tok-b"


def test_acquire_next_candidate_token_skips_limited_accounts():
    pool = make_pool([make_account("tok-a", status="限流", quota=0), make_account("tok-b")])
    assert pool._acquire_next_candidate_token() == "tok-b"


def test_release_image_slot_unknown_token_is_noop():
    pool = make_pool()
    pool.release_image_slot("missing")
    pool.release_image_slot("")
    assert pool.list_accounts() == []


def test_get_available_access_token_returns_verified_token():
    pool = make_pool([make_account("tok-a")])

    def verify(token: str, event: str) -> dict | None:
        return {"access_token": token, "status": "正常", "quota": 5}

    pool.verify_callback = verify
    assert pool.get_available_access_token() == "tok-a"


def test_get_available_access_token_retries_after_verify_exception():
    pool = make_pool([make_account("tok-a"), make_account("tok-b")])
    attempts: list[str] = []

    def verify(token: str, event: str) -> dict | None:
        attempts.append(token)
        if len(attempts) == 1:
            raise RuntimeError("network glitch")
        return {"access_token": token, "status": "正常", "quota": 5}

    pool.verify_callback = verify
    token = pool.get_available_access_token()
    assert token == attempts[-1]
    assert len(attempts) == 2


def test_get_available_access_token_raises_when_all_candidates_rejected():
    pool = make_pool([make_account("tok-a")])

    def verify(token: str, event: str) -> dict | None:
        # 远端校验返回无额度账号：本地候选被全部拒绝
        return {"access_token": token, "status": "正常", "quota": 0}

    pool.verify_callback = verify
    with pytest.raises(QuotaExhaustedError, match="no available image quota"):
        pool.get_available_access_token()


def test_get_available_access_token_requires_verify_callback():
    pool = make_pool([make_account("tok-a")])
    with pytest.raises(RuntimeError, match="verify_callback"):
        pool.get_available_access_token()


# ---- 结果回写 ----


def test_mark_image_result_success_decrements_quota_and_limits_at_zero():
    pool = make_pool([make_account("tok-a", quota=2)])
    pool.mark_image_result("tok-a", True)
    account = pool.get_account("tok-a")
    assert account["success"] == 1
    assert account["quota"] == 1
    assert account["status"] == "正常"

    pool.mark_image_result("tok-a", True)
    account = pool.get_account("tok-a")
    assert account["quota"] == 0
    assert account["status"] == "限流"


def test_mark_image_result_failure_counts_fail_and_keeps_status():
    pool = make_pool([make_account("tok-a", quota=3)])
    pool.mark_image_result("tok-a", False)
    account = pool.get_account("tok-a")
    assert account["fail"] == 1
    assert account["quota"] == 3
    assert account["status"] == "正常"


def test_mark_image_result_recovers_limited_account_on_success():
    pool = make_pool([make_account("tok-a", status="限流", quota=0)])
    pool.update_account("tok-a", {"quota": 2})  # 恢复额度但保持限流态
    pool.mark_image_result("tok-a", True)
    account = pool.get_account("tok-a")
    assert account["status"] == "正常"


def test_mark_image_result_releases_slot_first():
    pool = make_pool([make_account("tok-a")])
    pool._acquire_next_candidate_token()
    pool.mark_image_result("tok-a", True)
    assert pool.list_accounts()[0]["image_inflight"] == 0


# ---- 失效处理 ----


def test_record_invalid_token_seen_defers_for_new_account():
    pool = make_pool([make_account("tok-new")])  # created_at 为当前时间，处于宽限期
    assert pool.record_invalid_token_seen("tok-new", "test", "401 unauthorized") is False
    account = pool.get_account("tok-new")
    assert account["invalid_count"] == 1
    assert account["last_refresh_error"] == "401 unauthorized"


def test_record_invalid_token_seen_confirms_after_repeated_failures():
    pool = make_pool([make_account(
        "tok-old",
        created_at="2020-01-01 00:00:00",
        invalid_count=2,
        last_invalid_at="2020-01-01 00:00:00",
    )])
    assert pool.record_invalid_token_seen("tok-old", "test", "401 unauthorized") is True
    assert pool.get_account("tok-old")["invalid_count"] == 3


def test_record_invalid_token_seen_for_unknown_token_confirms():
    pool = make_pool()
    assert pool.record_invalid_token_seen("missing", "test", "401") is True


# ---- 查询与统计 ----


def test_list_limited_and_normal_tokens_split_by_status():
    pool = make_pool([make_account("tok-a"), make_account("tok-b", status="限流", quota=0)])
    assert pool.list_normal_tokens() == ["tok-a"]
    assert pool.list_limited_tokens() == ["tok-b"]


def test_get_stats_and_account_health():
    pool = make_pool([
        make_account("tok-a"),
        make_account("tok-b", status="限流", quota=0),
        make_account("tok-c", status="异常"),
        make_account("tok-d", status="禁用"),
    ])
    pool.mark_image_result("tok-a", True)
    pool.mark_image_result("tok-a", False)
    stats = pool.get_stats()
    assert stats["total"] == 4
    assert stats["active"] == 1
    assert stats["limited"] == 1
    assert stats["abnormal"] == 1
    assert stats["disabled"] == 1
    assert stats["total_success"] == 1
    assert stats["total_fail"] == 1
    health = pool.account_health()
    assert health["healthy"] is True
    assert health["status"] == "ok"


def test_snapshot_returns_copy_list():
    pool = make_pool([make_account("tok-a")])
    snapshot = pool.snapshot()
    snapshot[0]["quota"] = 999
    assert pool.get_account("tok-a")["quota"] == 5
