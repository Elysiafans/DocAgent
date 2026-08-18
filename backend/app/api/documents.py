from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Document, User
from app.schemas.document import DocumentOut
from app.services import document_service, ingestion_service

router = APIRouter(tags=["documents"])


@router.post(
    "/knowledge_bases/{kb_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    kb_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    kb = document_service.get_owned_kb(db, current_user, kb_id)
    file_type = (file.filename or "file").rsplit(".", 1)[-1].lower()
    raw = file.file.read()
    doc = Document(
        kb_id=kb.id,
        name=file.filename or "untitled",
        file_type=file_type,
        size=len(raw),
        status="uploading",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    background.add_task(ingestion_service.ingest_document, db, doc, raw)
    return doc


@router.get("/knowledge_bases/{kb_id}/documents", response_model=list[DocumentOut])
def list_docs(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    return document_service.list_documents(db, current_user, kb_id)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    return document_service.get_document(db, current_user, doc_id)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    doc = document_service.delete_document(db, current_user, doc_id)
    ingestion_service._make_vector_store(doc.kb_id).delete_document_chunks(doc.id)
