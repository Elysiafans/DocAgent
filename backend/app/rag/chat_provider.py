from typing import Protocol

from openai import OpenAI

from app.core.config import get_settings


class ChatProvider(Protocol):
    """对话 Provider 抽象:输入 OpenAI 风格 messages,返回纯文本回答。"""

    def complete(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str: ...


class DeepSeekChatProvider:
    """DeepSeek 对话(deepseek-v4-flash),OpenAI 兼容接口。"""

    def __init__(self, temperature: float = 0.2, api_key: str | None = None):
        s = get_settings()
        self.model = s.DEEPSEEK_CHAT_MODEL
        self.temperature = temperature
        self._client = OpenAI(
            # api_key 可显式注入(测试用 dummy,避免依赖环境密钥)
            api_key=api_key or s.DEEPSEEK_API_KEY,
            base_url=s.DEEPSEEK_BASE_URL,
        )

    def complete(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
        )
        return resp.choices[0].message.content or ""
