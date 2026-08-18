from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def get_chat_llm() -> ChatOpenAI:
    """DeepSeek(deepseek-v4-flash)OpenAI 兼容绑定,供 create_react_agent / supervisor 使用。"""
    s = get_settings()
    return ChatOpenAI(
        model=s.DEEPSEEK_CHAT_MODEL,
        base_url=s.DEEPSEEK_BASE_URL,
        api_key=s.DEEPSEEK_API_KEY,
        temperature=0.2,
        timeout=60,
    )
