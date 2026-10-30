# 手动验证脚本：需要真实上游 / 本地运行中的服务，不作为 pytest 单元测试运行。
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.protocol import openai_v1_image_generations
from test.utils import save_image


def main() -> None:
    prompt = "一只橘猫坐在窗台上，午后阳光，写实摄影"
    data = openai_v1_image_generations.handle({"prompt": prompt, "model": "gpt-5-3", "n": 1})
    for index, item in enumerate(data["data"], start=1):
        print(save_image(item["b64_json"], f"image_{index}"))


if __name__ == "__main__":
    main()
