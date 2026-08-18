from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, KnowledgeBase, User


def get_owned_kb(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )
    return kb


def list_documents(db: Session, user: User, kb_id: int) -> list[Document]:
    get_owned_kb(db, user, kb_id)
    return list(
        db.execute(
            select(Document).where(Document.kb_id == kb_id).order_by(Document.id.desc())
        ).scalars()
    )


def get_document(db: Session, user: User, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    kb = db.get(KnowledgeBase, doc.kb_id) if doc else None
    if doc is None or kb is None or kb.owner_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return doc


def delete_document(db: Session, user: User, doc_id: int) -> Document:
    doc = get_document(db, user, doc_id)
    db.delete(doc)
    db.commit()
    return doc
