# 手动验证脚本：需要真实上游 / 本地运行中的服务，不作为 pytest 单元测试运行。
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.utils import post_json


def main() -> None:
    result = post_json(
        "/v1/images/generations",
        {
            "prompt": "一只橘猫坐在窗边，午后阳光，写实摄影",
            "model": "gpt-image-2",
            "n": 1,
            "response_format": "url",
        },
    )
    for item in result.get("data", []):
        print(item.get("url", ""))


if __name__ == "__main__":
    main()
