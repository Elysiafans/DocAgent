from typing import ClassVar

from app.rag.chat_provider import DeepSeekChatProvider


def test_deepseek_complete_uses_v4_flash(monkeypatch):
    # dummy key:构造需要非空 api_key,但测试不调真实 API(下面替换 _client)
    provider = DeepSeekChatProvider(api_key="test-key")
    calls = []

    class FakeResp:
        choices: ClassVar = [
            type("C", (), {"message": type("M", (), {"content": "根据资料[1],答案是……"})})()
        ]

    class FakeCompletions:
        def create(self, *args, **kwargs):
            calls.append(kwargs)
            return FakeResp()

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    # 直接替换实例内部 client,避免模块点路径解析问题
    monkeypatch.setattr(provider, "_client", FakeClient())
    answer = provider.complete([{"role": "user", "content": "hi"}], temperature=0.1)
    assert answer.startswith("根据资料")
    assert calls and calls[0]["model"] == "deepseek-v4-flash"
    assert calls[0]["temperature"] == 0.1
