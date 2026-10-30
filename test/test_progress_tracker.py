"""ProgressTracker 泛型进度追踪器单测。

覆盖点：
- `start` / `update` / `finish` / `get` / `clean` 基本生命周期
- `apply_update` 回调写入单条进度详情、`processed` 计数自动累加
- `auto_complete` 开关：处理数达到总数时自动置 done
- 不存在的 progress_id 更新/完成/清理均为 no-op
- `get` 返回副本（外部修改不影响内部状态）、不存在时返回 None
- 多线程并发 update 下计数不丢失
"""

from concurrent.futures import ThreadPoolExecutor

from services.account.progress import ProgressTracker


def make_tracker(**kwargs) -> ProgressTracker:
    return ProgressTracker(
        build_initial=lambda total: {"total": total, "processed": 0, "done": False, "result": None, "items": []},
        **kwargs,
    )


def test_start_update_finish_lifecycle():
    tracker = make_tracker(apply_update=lambda progress, payload: progress["items"].append(payload))
    tracker.start("p1", 3)

    assert tracker.get("p1") == {"total": 3, "processed": 0, "done": False, "result": None, "items": []}

    tracker.update("p1", "account-a")
    tracker.update("p1", "account-b")
    progress = tracker.get("p1")
    assert progress["processed"] == 2
    assert progress["items"] == ["account-a", "account-b"]
    assert progress["done"] is False

    tracker.finish("p1", result={"ok": 2})
    progress = tracker.get("p1")
    assert progress["done"] is True
    assert progress["result"] == {"ok": 2}
    assert "error" not in progress


def test_finish_with_error_records_error_field():
    tracker = make_tracker()
    tracker.start("p1", 1)
    tracker.finish("p1", error="boom")
    progress = tracker.get("p1")
    assert progress["done"] is True
    assert progress["error"] == "boom"


def test_finish_without_result_keeps_result_none():
    tracker = make_tracker()
    tracker.start("p1", 1)
    tracker.finish("p1")
    assert tracker.get("p1")["result"] is None


def test_auto_complete_marks_done_when_processed_reaches_total():
    tracker = make_tracker(auto_complete=True)
    tracker.start("p1", 2)
    tracker.update("p1", "a")
    assert tracker.get("p1")["done"] is False
    tracker.update("p1", "b")
    assert tracker.get("p1")["done"] is True
    # 超出总数后保持 done
    tracker.update("p1", "c")
    assert tracker.get("p1")["done"] is True
    assert tracker.get("p1")["processed"] == 3


def test_no_auto_complete_keeps_done_false_until_finish():
    tracker = make_tracker()
    tracker.start("p1", 1)
    tracker.update("p1", "a")
    assert tracker.get("p1")["done"] is False


def test_unknown_progress_id_is_noop():
    tracker = make_tracker(apply_update=lambda progress, payload: progress.setdefault("touched", True))
    tracker.update("missing", "x")
    tracker.finish("missing", result={"r": 1})
    tracker.clean("missing")
    assert tracker.get("missing") is None


def test_get_returns_copy_isolated_from_internal_state():
    tracker = make_tracker()
    tracker.start("p1", 2)
    snapshot = tracker.get("p1")
    snapshot["processed"] = 999
    assert tracker.get("p1")["processed"] == 0


def test_apply_update_without_callback_only_counts():
    tracker = make_tracker()
    tracker.start("p1", 1)
    tracker.update("p1", {"anything": True})
    assert tracker.get("p1")["processed"] == 1


def test_clean_removes_record():
    tracker = make_tracker()
    tracker.start("p1", 1)
    tracker.clean("p1")
    assert tracker.get("p1") is None


def test_concurrent_updates_keep_processed_consistent():
    tracker = make_tracker()
    tracker.start("p1", 200)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda i: tracker.update("p1", i), range(200)))
    assert tracker.get("p1")["processed"] == 200
