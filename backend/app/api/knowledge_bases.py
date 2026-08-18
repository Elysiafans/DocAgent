from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import KnowledgeBase, User
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from app.services import knowledge_base_service

router = APIRouter(prefix="/knowledge_bases", tags=["knowledge_bases"])


@router.get("", response_model=list[KnowledgeBaseOut])
def list_kbs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[KnowledgeBase]:
    return knowledge_base_service.list_knowledge_bases(db, current_user)


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def create_kb(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return knowledge_base_service.create_knowledge_base(db, current_user, payload)


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
def get_kb(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return knowledge_base_service.get_owned_knowledge_base(db, current_user, kb_id)


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
def update_kb(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return knowledge_base_service.update_knowledge_base(
        db, current_user, kb_id, payload
    )


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    knowledge_base_service.delete_knowledge_base(db, current_user, kb_id)
