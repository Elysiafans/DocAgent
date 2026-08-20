import sys
from pathlib import Path

# 直接 `python backend/app/main.py` 运行时,脚本所在目录(backend/app)在 sys.path 上,
# 但包级导入 `from app.api...` 需要 backend/ 在 sys.path。此处仅直接运行时补上。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from app.api.a2a import router as a2a_router
from app.api.a2ui import router as a2ui_router
from app.api.agent_chat import router as agent_chat_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.mcp import router as mcp_router
from app.api.memories import router as memories_router
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
    app.include_router(a2ui_router, prefix=settings.API_V1_PREFIX)
    app.include_router(memories_router, prefix=settings.API_V1_PREFIX)
    app.include_router(mcp_router)  # 协议入口,根路径 /mcp
    app.include_router(a2a_router)  # 协议入口,根路径 /a2a
    return app


app = create_app()


if __name__ == "__main__":
    # 直接运行入口:python backend/app/main.py
    # app_dir 让 reload 子进程在任意 cwd 下都能定位 backend/。
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir=str(Path(__file__).resolve().parent.parent),
    )
