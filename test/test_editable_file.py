"""backend/editable_file 纯函数单测（PPT/PSD 导出链路的核心解析逻辑）。

覆盖点：
- `editable_prompt`：补充需求拼接与空值回退
- 文件名/路径处理：`sanitize_editable_filename`、`unique_editable_path`
  冲突避让、`editable_filename_from_content_disposition` 的 filename* 与
  filename= 两种形态
- MIME 推断：`clean_editable_mime_type`、`editable_extension_from_mime_type`
  （主文件 / zip / 通用回退）
- 产物识别与合并：`looks_like_editable_primary` / `looks_like_editable_zip`、
  `pick_editable_target_artifacts`（主文件+zip 齐备才返回）、
  `merge_editable_artifact` 字段级合并
- ID 提取：`match_editable_file_id`、`extract_editable_file_ids` 排除
  file-service 前缀、`extract_editable_export_paths`
"""

import pytest

from services.backend.editable_file import (
    EDITABLE_PPT_EXPORT_FILE_RE,
    EDITABLE_PPT_MIME_TYPES,
    EDITABLE_PSD_EXPORT_FILE_RE,
    EDITABLE_PSD_MIME_TYPES,
    EditableFileArtifact,
    clean_editable_mime_type,
    editable_artifact_from_dict,
    editable_extension_from_mime_type,
    editable_filename_from_content_disposition,
    editable_prompt,
    extract_editable_export_paths,
    extract_editable_file_ids,
    looks_like_editable_primary,
    looks_like_editable_zip,
    match_editable_file_id,
    merge_editable_artifact,
    pick_editable_target_artifacts,
    resolve_editable_output_name,
    sanitize_editable_filename,
    unique_editable_path,
)


def make_artifact(**overrides) -> EditableFileArtifact:
    fields = {
        "attachment_id": "", "file_id": "", "name": "", "mime_type": "",
        "create_time": 0.0, "author_role": "", "sandbox_path": "", "message_id": "",
    }
    fields.update(overrides)
    return EditableFileArtifact(**fields)


# ---- prompt 拼接 ----


def test_editable_prompt_appends_user_requirements():
    assert editable_prompt("FIXED", "") == "FIXED"
    assert editable_prompt("FIXED", "   ") == "FIXED"
    combined = editable_prompt("FIXED", "加一页目录")
    assert combined == "FIXED\n\n以下是用户补充需求，请直接结合执行：\n加一页目录"


# ---- 文件名与路径 ----


def test_sanitize_editable_filename_keeps_base_name_only():
    assert sanitize_editable_filename("/mnt/data/deck.pptx") == "deck.pptx"
    assert sanitize_editable_filename("  a\x00b.png ") == "ab.png"
    assert sanitize_editable_filename("") == ""
    assert sanitize_editable_filename(None) == ""


def test_editable_filename_from_content_disposition_variants():
    assert editable_filename_from_content_disposition(
        'attachment; filename="deck.pptx"'
    ) == "deck.pptx"
    assert editable_filename_from_content_disposition(
        "attachment; filename*=UTF-8''%E7%94%BB%E6%9D%BF.psd"
    ) == "画板.psd"
    assert editable_filename_from_content_disposition("inline") == ""
    assert editable_filename_from_content_disposition("") == ""


def test_unique_editable_path_avoids_conflicts(tmp_path):
    target = tmp_path / "out.zip"
    assert unique_editable_path(target) == target
    target.write_bytes(b"x")
    assert unique_editable_path(target) == tmp_path / "out_1.zip"
    (tmp_path / "out_1.zip").write_bytes(b"x")
    assert unique_editable_path(target) == tmp_path / "out_2.zip"


# ---- MIME 推断 ----


def test_clean_editable_mime_type_normalizes_and_rejects_non_mime():
    assert clean_editable_mime_type("Application/ZIP; charset=utf-8") == "application/zip"
    assert clean_editable_mime_type("") == ""
    assert clean_editable_mime_type("not-a-mime") == ""
    assert clean_editable_mime_type(None) == ""


def test_editable_extension_from_mime_type_priority():
    assert editable_extension_from_mime_type(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        EDITABLE_PPT_MIME_TYPES, ("presentationml.presentation", "ms-powerpoint"), ".pptx",
    ) == ".pptx"
    assert editable_extension_from_mime_type(
        "application/vnd.ms-powerpoint",
        EDITABLE_PPT_MIME_TYPES, ("presentationml.presentation", "ms-powerpoint"), ".pptx",
    ) == ".pptx"
    assert editable_extension_from_mime_type("application/zip", EDITABLE_PPT_MIME_TYPES, (), ".pptx") == ".zip"
    assert editable_extension_from_mime_type("text/plain", EDITABLE_PPT_MIME_TYPES, (), ".pptx") == ".txt"
    assert editable_extension_from_mime_type("", EDITABLE_PSD_MIME_TYPES, (), ".psd") == ""


# ---- 产物识别与合并 ----


def test_looks_like_editable_primary_and_zip():
    ppt_artifact = make_artifact(name="deck.PPTX")
    assert looks_like_editable_primary(ppt_artifact, (".ppt", ".pptx"), EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",))
    assert looks_like_editable_primary(
        make_artifact(mime_type="application/vnd.ms-powerpoint"),
        (".ppt", ".pptx"), EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",),
    )
    assert looks_like_editable_primary(
        make_artifact(sandbox_path="/mnt/data/x.psd"),
        (".psd",), EDITABLE_PSD_MIME_TYPES, ("photoshop",),
    )
    assert looks_like_editable_primary(
        make_artifact(name="deck.pptx"),
        (".psd",), EDITABLE_PSD_MIME_TYPES, ("photoshop",),
    ) is False

    assert looks_like_editable_zip(make_artifact(name="assets.ZIP"))
    assert looks_like_editable_zip(make_artifact(mime_type="application/x-zip-compressed"))
    assert looks_like_editable_zip(make_artifact(mime_type="image/zip"))
    assert looks_like_editable_zip(make_artifact(name="a.png")) is False


def test_pick_editable_target_artifacts_requires_both_primary_and_zip():
    primary = make_artifact(name="deck.pptx", create_time=1.0)
    other_primary = make_artifact(name="older.pptx", create_time=0.5)
    zip_item = make_artifact(name="assets.zip", create_time=2.0)
    picked = pick_editable_target_artifacts(
        [other_primary, primary, zip_item], (".ppt", ".pptx"), EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",),
    )
    # 从后往前取「最后一个」主文件与 zip
    assert picked == [primary, zip_item]

    assert pick_editable_target_artifacts(
        [primary], (".ppt", ".pptx"), EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",),
    ) == []
    assert pick_editable_target_artifacts(
        [zip_item], (".ppt", ".pptx"), EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",),
    ) == []


def test_merge_editable_artifact_keeps_latest_non_empty_fields():
    current = make_artifact(attachment_id="a1", file_id="", name="old.pptx", create_time=1.0, message_id="m1")
    latest = make_artifact(attachment_id="", file_id="f1", name="new.pptx", create_time=2.0, author_role="tool")
    merged = merge_editable_artifact(current, latest)
    assert merged.attachment_id == "a1"
    assert merged.file_id == "f1"
    assert merged.name == "new.pptx"
    assert merged.create_time == 2.0
    assert merged.author_role == "tool"
    assert merged.message_id == "m1"

    assert merge_editable_artifact(None, latest) is latest


# ---- ID / 导出路径提取 ----


def test_match_editable_file_id_excludes_file_service_prefix():
    assert match_editable_file_id("file-abc_123") == "file-abc_123"
    assert match_editable_file_id("file_00000000" + "a" * 24) == "file_00000000" + "a" * 24
    assert match_editable_file_id("file-service") == ""
    assert match_editable_file_id("no-id-here") == ""


def test_extract_editable_file_ids_dedups_asset_pointer_and_plain_ids():
    text = f"file-service://abc sediment://def file_00000000{'a' * 24} file-xyz abc"
    ids = extract_editable_file_ids(text)
    assert ids == ["abc", "def", f"file_00000000{'a' * 24}", "file-xyz"]


def test_extract_editable_export_paths_psd_and_ppt_patterns():
    text = "saved /mnt/data/deck.pptx and sandbox:/mnt/data/assets.ZIP and /mnt/data/art.psd"
    assert extract_editable_export_paths(text, EDITABLE_PPT_EXPORT_FILE_RE) == [
        "/mnt/data/deck.pptx", "/mnt/data/assets.ZIP",
    ]
    # PSD 导出正则同样收纳 zip（IGNORECASE）
    assert extract_editable_export_paths(text, EDITABLE_PSD_EXPORT_FILE_RE) == [
        "/mnt/data/assets.ZIP", "/mnt/data/art.psd",
    ]
    assert extract_editable_export_paths({"none": "here"}, EDITABLE_PPT_EXPORT_FILE_RE) == []


# ---- attachment dict → artifact ----


def test_editable_artifact_from_dict_builds_from_attachment_payload():
    payload = {
        "id": "att-1",
        "file_name": "deck.pptx",
        "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "asset_pointer": "sediment://sed-9",
    }
    artifact = editable_artifact_from_dict(payload, "m1", "tool", 5.0, EDITABLE_PPT_EXPORT_FILE_RE)
    assert artifact is not None
    # id 字段无法匹配 file[-_] 模式，attachment_id / file_id 均由 asset_pointer 兜底
    assert artifact.attachment_id == "sed-9"
    assert artifact.file_id == "sed-9"
    assert artifact.name == "deck.pptx"
    assert artifact.mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert artifact.create_time == 5.0
    assert artifact.message_id == "m1"


def test_editable_artifact_from_dict_ignores_unrelated_dicts():
    assert editable_artifact_from_dict({"unrelated": 1}, "m1", "tool", 1.0, EDITABLE_PPT_EXPORT_FILE_RE) is None
    # 有 name 字段但完全没有 id/file_id 时，也会从整体 JSON 里提取 file id
    artifact = editable_artifact_from_dict(
        {"name": "assets.zip", "file_id": "file-zip-1"}, "m1", "tool", 1.0, EDITABLE_PPT_EXPORT_FILE_RE,
    )
    assert artifact is not None
    assert artifact.file_id == "file-zip-1"


# ---- 输出文件名决策 ----


def test_resolve_editable_output_name_prefers_artifact_name():
    artifact = make_artifact(name="deck.pptx")
    name = resolve_editable_output_name(
        artifact, "https://blob/x", None,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",), ".pptx",
    )
    assert name == "deck.pptx"


def test_resolve_editable_output_name_falls_back_to_disposition_then_url():
    artifact = make_artifact(sandbox_path="/mnt/data/画板.psd")
    name = resolve_editable_output_name(
        artifact, "https://blob/x", 'attachment; filename="uploaded.pptx"',
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",), ".pptx",
    )
    assert name == "画板.psd"

    bare = make_artifact()
    name_from_url = resolve_editable_output_name(
        bare, "https://blob/path/remote.pptx", None, "application/zip",
        EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",), ".pptx",
    )
    assert name_from_url == "remote.pptx"


def test_resolve_editable_output_name_appends_extension_when_missing():
    artifact = make_artifact(name="deck")
    name = resolve_editable_output_name(
        artifact, "https://blob/x", None,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",), ".pptx",
    )
    assert name == "deck.pptx"

    no_ext = resolve_editable_output_name(
        make_artifact(), "https://blob/", None, "",
        EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",), ".pptx",
    )
    assert no_ext == "artifact"

    from_mime = resolve_editable_output_name(
        make_artifact(), "https://blob/", None,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        EDITABLE_PPT_MIME_TYPES, ("ms-powerpoint",), ".pptx",
    )
    assert from_mime == "artifact.pptx"
