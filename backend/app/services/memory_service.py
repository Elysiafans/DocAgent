from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Memory, User


def add_memory(
    db: Session,
    user: User,
    content: str,
    kind: str = "note",
    conv_id: int | None = None,
) -> Memory:
    m = Memory(user_id=user.id, conv_id=conv_id, kind=kind, content=content)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def list_memories(db: Session, user: User, limit: int | None = None) -> list[Memory]:
    q = (
        select(Memory)
        .where(Memory.user_id == user.id)
        .order_by(Memory.id.desc())
    )
    if limit:
        q = q.limit(limit)
    return list(db.execute(q).scalars())


def search_memories(db: Session, user: User, keyword: str) -> list[Memory]:
    return list(
        db.execute(
            select(Memory)
            .where(
                Memory.user_id == user.id,
                Memory.content.ilike(f"%{keyword}%"),
            )
            .order_by(Memory.id.desc())
        ).scalars()
    )


def delete_memory(db: Session, user: User, memory_id: int) -> None:
    m = db.get(Memory, memory_id)
    if m is None or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.delete(m)
    db.commit()


def build_memory_context(db: Session, user: User, limit: int = 10) -> str:
    """把最近记忆拼成提示文本块;无记忆返回空串(agent 不注入)。"""
    mems = list_memories(db, user, limit=limit)
    if not mems:
        return ""
    lines = [f"- [{m.kind}] {m.content}" for m in mems]
    return "用户长期记忆(回答时参考;与本次提问冲突时以提问为准):\n" + "\n".join(
        lines
    )
