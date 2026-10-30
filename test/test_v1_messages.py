from __future__ import annotations

import json
import os
import time
import unittest

import requests

AUTH_KEY = "chatgpt2api"
BASE_URL = "http://localhost:8000"
MODEL = "auto"

# live 用例需本地运行中的服务；默认跳过，设置 CHATGPT2API_LIVE=1 后执行
LIVE = unittest.skipUnless(
    os.environ.get("CHATGPT2API_LIVE") == "1",
    "live 用例需本地运行中的服务；设置 CHATGPT2API_LIVE=1 后执行",
)


@LIVE
class AnthropicMessagesTests(unittest.TestCase):
    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "x-api-key": AUTH_KEY,
            "anthropic-version": "2023-06-01",
        }

    def test_message_http(self):
        """测试 Anthropic Messages 的非流式 HTTP 调用。"""
        response = requests.post(
            f"{BASE_URL}/v1/messages",
            headers=self._headers(),
            json={
                "model": MODEL,
                "messages": [
                    {"role": "user", "content": "你好，请简单介绍一下你自己。"},
                ],
            },
            timeout=300,
        )
        print("messages non-stream status:")
        print(response.status_code)
        print("messages non-stream result:")
        try:
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(response.text)

    def test_message_stream_http(self):
        """测试 Anthropic Messages 的流式 HTTP 调用。"""
        started_at = time.time()
        response = requests.post(
            f"{BASE_URL}/v1/messages",
            headers=self._headers(),
            json={
                "model": MODEL,
                "stream": True,
                "messages": [
                    {"role": "user", "content": "你好，请简单介绍一下你自己。"},
                ],
            },
            stream=True,
            timeout=300,
        )
        headers_at = time.time()
        print("messages stream status:")
        print(response.status_code)
        print("messages stream content-type:")
        print(response.headers.get("content-type", ""))
        print("messages stream response headers:")
        print(f"{headers_at - started_at:6.2f}s")
        if response.status_code != 200:
            print(response.text)
            return
        print("messages stream chunks:")
        for line in response.iter_lines(chunk_size=1):
            if not line:
                continue
            text = line.decode("utf-8", errors="replace")
            print(f"{time.time() - started_at:6.2f}s {text}")
            if not text.startswith("data:"):
                continue
            try:
                payload = json.loads(text[5:].strip())
            except Exception:
                continue
            if payload.get("type") == "message_stop":
                break


if __name__ == "__main__":
    unittest.main()
