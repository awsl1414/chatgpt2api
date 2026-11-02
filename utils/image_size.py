"""生图模型的尺寸遵循能力表（唯一事实源）与尺寸文本解析。

本模块回答一个问题：**给定模型，请求里的 `size` 到底该走哪条通道**。结论全部
来自实测（工作区 `docs/size-verification.md`，103 条有效样本），不是推测：

- `gpt-image-2`（picture_v2 链路）：接口 `size` 能决定宽高比（提示词里的比例/像素
  同样生效；两者冲突时上游一律落横版）；
- `codex-gpt-image-*` 全系列（含 plus-/team-/pro- 前缀）：接口 `size` **完全不生效**，
  唯一有效通道是提示词里显式写出的比例或像素；
- 所有模型都不兑现绝对像素：出图面积恒定归一化到 1,572,864 px（= 1024×1536）。

因此调用方必须先查本表再决定「要不要把 size 透传给上游」「要不要把尺寸写进提示词」，
不得在链路里硬编码模型名判断。前端 `web/src/lib/image-composer-options.ts` 持有
语义一一对应的 `IMAGE_MODEL_SIZE_CAPABILITIES`，两侧改动必须同步。

依赖纪律：本模块只依赖 `utils.helper`（模型名解析），不依赖 services。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from utils.helper import split_image_model

# `1024x1536` / `1024×1536` / `1024 x 1536` 三种写法都接受
_SIZE_PAIR_RE = re.compile(r"^\s*(\d{2,5})\s*[x×]\s*(\d{2,5})\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ImageSizeCapability:
    """单个生图模型对尺寸请求的遵循能力（实测结论的结构化表达）。

    字段语义：
    - `api_size_effective`：请求体 `size` 字段能否决定出图宽高比。为 False 时
      **不得**把该字段透传给上游（上游会收到但完全忽略，只会让日志与抓包误导人）；
    - `prompt_size_effective`：提示词里显式写出的尺寸/比例能否决定出图宽高比。
      为 True 时尺寸意图应写进提示词（codex 系列这是唯一有效通道）。

    两条通道都**不**兑现绝对像素：任何取值最终都按比例归一化到约 1.57M 像素。
    """

    api_size_effective: bool
    prompt_size_effective: bool


# 键为「去掉 plus-/team-/pro- 前缀后的基础模型名」，与 `utils.helper.BASE_IMAGE_MODELS` 对齐。
IMAGE_SIZE_CAPABILITIES: dict[str, ImageSizeCapability] = {
    # picture_v2：接口 size 生效，提示词尺寸也生效（冲突时上游落横版，见 size-verification.md §4.4）
    "gpt-image-2": ImageSizeCapability(api_size_effective=True, prompt_size_effective=True),
    # codex/responses 工具层：tools[0].size 进得去、出不来；只有提示词尺寸有效
    "codex-gpt-image-2": ImageSizeCapability(api_size_effective=False, prompt_size_effective=True),
    "codex-gpt-image-2.5-flare": ImageSizeCapability(api_size_effective=False, prompt_size_effective=True),
    "codex-gpt-image-2.5-sunburst": ImageSizeCapability(api_size_effective=False, prompt_size_effective=True),
}


def image_size_capability(model: object) -> ImageSizeCapability | None:
    """返回模型的尺寸能力；非图片模型（或未知模型）返回 None。"""
    _, base_model = split_image_model(model)
    if base_model is None:
        return None
    return IMAGE_SIZE_CAPABILITIES.get(base_model)


def image_size_uses_api_field(model: object) -> bool:
    """接口 `size` 字段是否对该模型生效（不生效时不得向上游透传该字段）。"""
    capability = image_size_capability(model)
    return bool(capability and capability.api_size_effective)


def image_size_uses_prompt(model: object) -> bool:
    """尺寸意图是否应写进提示词（codex 系列唯一有效通道，picture_v2 亦生效）。"""
    capability = image_size_capability(model)
    return bool(capability and capability.prompt_size_effective)


def parse_size_pair(size: object) -> tuple[int, int] | None:
    """把 `"1024x1536"` 之类的尺寸字符串解析为 `(width, height)`。

    无法解析（`None`、`"auto"`、`"1024"`、非正数）时返回 None——调用方据此
    退回「原样复述 size」的兜底文案。
    """
    match = _SIZE_PAIR_RE.match(str(size or ""))
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return width, height


def orientation_label(width: int, height: int) -> str:
    """返回中文方向描述：横版 / 竖版 / 方形。"""
    if width > height:
        return "横版"
    if height > width:
        return "竖版"
    return "方形"
