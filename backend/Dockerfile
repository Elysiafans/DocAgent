# DocAgent 后端镜像:alembic 迁移 + uvicorn 单进程(InMemorySaver 会话记忆需单 worker)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 依赖全部为 wheel(psycopg[binary]/qdrant-client/langgraph 等),无需编译工具链
COPY requirements.txt .
RUN pip install -r requirements.txt

# 运行所需:应用代码、alembic 迁移、skills(容器内 SKILLS_DIR = /app/skills)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY skills ./skills

EXPOSE 8000

# 启动前先迁移;单 worker 保证 InMemorySaver 会话记忆一致
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
