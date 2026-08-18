from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Memory, User
from app.schemas.memory import MemoryCreate, MemoryOut
from app.services import memory_service

router = APIRouter(tags=["memories"])


@router.post("/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def add_memory(
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryOut:
    return memory_service.add_memory(
        db, current_user, payload.content, kind=payload.kind, conv_id=payload.conv_id
    )


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryOut]:
    return memory_service.list_memories(db, current_user)


@router.get("/memories/search", response_model=list[MemoryOut])
def search_memories(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryOut]:
    return memory_service.search_memories(db, current_user, q)


@router.delete(
    "/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    memory_service.delete_memory(db, current_user, memory_id)
