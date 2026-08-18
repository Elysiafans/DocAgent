from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeBase, User
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


def list_knowledge_bases(db: Session, user: User) -> list[KnowledgeBase]:
    return list(
        db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.owner_id == user.id)
            .order_by(KnowledgeBase.id)
        ).scalars()
    )


def get_owned_knowledge_base(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )
    return kb


def create_knowledge_base(
    db: Session, user: User, payload: KnowledgeBaseCreate
) -> KnowledgeBase:
    kb = KnowledgeBase(owner_id=user.id, **payload.model_dump())
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def update_knowledge_base(
    db: Session, user: User, kb_id: int, payload: KnowledgeBaseUpdate
) -> KnowledgeBase:
    kb = get_owned_knowledge_base(db, user, kb_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kb, field, value)
    db.commit()
    db.refresh(kb)
    return kb


def delete_knowledge_base(db: Session, user: User, kb_id: int) -> None:
    kb = get_owned_knowledge_base(db, user, kb_id)
    db.delete(kb)
    db.commit()
