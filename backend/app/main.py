from fastapi import FastAPI

from app.api.a2a import router as a2a_router
from app.api.agent_chat import router as agent_chat_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.mcp import router as mcp_router
from app.api.skills import router as skills_router
from app.core.config import get_settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(knowledge_bases_router, prefix=settings.API_V1_PREFIX)
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
    app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
    app.include_router(conversations_router, prefix=settings.API_V1_PREFIX)
    app.include_router(agent_chat_router, prefix=settings.API_V1_PREFIX)
    app.include_router(skills_router, prefix=settings.API_V1_PREFIX)
    app.include_router(mcp_router)  # 协议入口,根路径 /mcp
    app.include_router(a2a_router)  # 协议入口,根路径 /a2a
    return app


app = create_app()
