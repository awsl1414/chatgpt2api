"""生图模型的尺寸遵循能力表（唯一事实源）与尺寸文本解析。

结论全部来自实测（工作区 `docs/size-verification.md`，103 条有效样本）：

1. **比例对所有模型都有效**：提示词里显式写出的尺寸或比例能决定出图宽高比
   （§4.3：四个模型写 `1792x1024 pixels` / `16:9` 全部生效；§5 逐档验证了
   2K/4K 档位提供的 1:1、16:9、9:16 比例同样精确兑现）。
2. **绝对像素对所有模型都无效**：出图面积恒定归一化到 1,572,864 px
   （= 1024×1536，§8.3）。请求 4K 也只兑现比例——这是**标注**问题，不是禁用问题。
3. **接口 `size` 只在 picture_v2 生效**：picture_v2 的接口 size 精确决定宽高比
   （§5）；codex 系列的上游 `tools[0].size` 收到但被完全忽略（§3：20+ 样本，
   含 plus- 前缀）。

由此得到提示词注入的形态：**接口 size 生效的链路（picture_v2）保持原措辞，
不额外加方向词**；**接口 size 不生效的链路（codex 系列）必须把方向一并写进
提示词**，那是它唯一能决定宽高比的通道。前端与后端共享同一份语义（前端见
`web/src/lib/image-composer-options.ts` 的 `IMAGE_MODEL_SIZE_CAPABILITIES`），
两侧改动必须同步。

依赖纪律：本模块只依赖 `utils.helper`（模型名解析），不依赖 services。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from utils.helper import split_image_model

# 出图面积归一化基准：1024x1536 = 1,572,864 px（实测所有模型恒定，见 §8.3）
NORMALIZED_OUTPUT_AREA_PX = 1_572_864

# `1024x1536` / `1024×1536` / `1024 x 1536` 三种写法都接受
_SIZE_PAIR_RE = re.compile(r"^\s*(\d{2,5})\s*[x×]\s*(\d{2,5})\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ImageSizeCapability:
    """单个生图模型对尺寸请求的遵循能力（实测结论的结构化表达）。

    字段语义：
    - `api_size_effective`：调用方请求里的 `size` 字段能否决定出图宽高比。
      picture_v2 为 True（服务端把它转成中文提示文本，实测精确跟随）；
      codex 系列为 False（上游 `tools[0].size` 收到但完全忽略）。
    - `prompt_size_effective`：提示词里显式写出的尺寸/比例能否决定出图宽高比。
      所有已测图片模型均为 True。

    两个字段共同决定提示词注入的形态：
    - `prompt_size_effective` 为 False 时不注入任何尺寸文本；
    - `api_size_effective` 为 False 时额外注入方向词——这是该链路唯一有效通道，
      而接口 size 已生效的链路保持原措辞，避免改变既有行为与对外 `revised_prompt`。

    任何字段都不代表绝对像素可兑现：出图面积恒约 1.57M 像素。
    """

    api_size_effective: bool
    prompt_size_effective: bool


# 键为「去掉 plus-/team-/pro- 前缀后的基础模型名」，与 `utils.helper.BASE_IMAGE_MODELS` 对齐。
IMAGE_SIZE_CAPABILITIES: dict[str, ImageSizeCapability] = {
    # picture_v2：接口 size 生效（§5 逐档实测），提示词措辞保持不变
    "gpt-image-2": ImageSizeCapability(
        api_size_effective=True,
        prompt_size_effective=True,
    ),
    # codex/responses 工具层：tools[0].size 被忽略（§3），只有提示词有效（§4.3）
    "codex-gpt-image-2": ImageSizeCapability(
        api_size_effective=False,
        prompt_size_effective=True,
    ),
    "codex-gpt-image-2.5-flare": ImageSizeCapability(
        api_size_effective=False,
        prompt_size_effective=True,
    ),
    "codex-gpt-image-2.5-sunburst": ImageSizeCapability(
        api_size_effective=False,
        prompt_size_effective=True,
    ),
}


def image_size_capability(model: object) -> ImageSizeCapability | None:
    """返回模型的尺寸能力；非图片模型（或未知模型）返回 None。"""
    _, base_model = split_image_model(model)
    if base_model is None:
        return None
    return IMAGE_SIZE_CAPABILITIES.get(base_model)


def image_size_uses_api_field(model: object) -> bool:
    """请求 `size` 字段是否对该模型生效（决定提示词是否追加方向词）。"""
    capability = image_size_capability(model)
    return bool(capability and capability.api_size_effective)


def image_size_uses_prompt(model: object) -> bool:
    """尺寸意图是否应写进提示词（所有已测图片模型均为 True）。"""
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
