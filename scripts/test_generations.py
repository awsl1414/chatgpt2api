# 手动验证脚本：需要真实上游 / 本地运行中的服务，不作为 pytest 单元测试运行。
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import post_json, save_image


def main() -> None:
    prompt = "A cute orange cat sitting on a chair"
    result = post_json("/v1/images/generations", {"prompt": prompt, "model": "gpt-image-2", "n": 1})
    for index, item in enumerate(result["data"], start=1):
        print(save_image(item["b64_json"], f"generations_{index}"))


if __name__ == "__main__":
    main()
