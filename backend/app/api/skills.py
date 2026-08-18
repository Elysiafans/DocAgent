from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.protocols import skills

router = APIRouter(tags=["skills"])


@router.get("/skills")
def list_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """列出可用的 Agent Skills(SKILL.md 目录扫描)。"""
    return skills.list_skills()
