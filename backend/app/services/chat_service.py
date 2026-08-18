from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Conversation, Document, KnowledgeBase, Message, User
from app.rag.chat_provider import ChatProvider, DeepSeekChatProvider
from app.rag.embeddings import SiliconFlowEmbeddingProvider
from app.rag.reranker import Reranker, SiliconFlowReranker
from app.rag.retrieval import assemble_context, retrieve
from app.rag.vector_store import QdrantVectorStore
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource

SYSTEM_PROMPT = """你是一个严谨的知识库问答助手。
规则:
1. 只依据下方"资料"回答;资料中没有的信息,明确说明"资料中没有相关内容",不要编造。
2. 引用来源:回答中引用资料内容时,用 [数字] 标注,数字对应资料编号。
3. 默认用与用户提问相同的语言回答。"""


def _make_vector_store(kb_id: int) -> QdrantVectorStore:
    return QdrantVectorStore(
        get_settings().QDRANT_COLLECTION, SiliconFlowEmbeddingProvider()
    )


def _make_reranker() -> Reranker:
    return SiliconFlowReranker()


def _make_chat_provider() -> ChatProvider:
    return DeepSeekChatProvider()


def _get_owned_kb(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def _get_owned_conversation(db: Session, user: User, conv_id: int) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conv


def chat(db: Session, user: User, payload: ChatRequest) -> ChatResponse:
    kb = _get_owned_kb(db, user, payload.kb_id)
    store = _make_vector_store(kb.id)
    chunks = retrieve(
        store,
        _make_reranker(),
        payload.question,
        kb.id,
        top_k=payload.top_k,
        top_n=payload.top_n,
        hybrid=payload.hybrid,
        threshold=payload.threshold,
    )
    # 文档名映射(溯源展示)
    doc_names: dict[int, str] = {}
    if chunks:
        doc_ids = {c.doc_id for c in chunks}
        doc_names = {
            d.id: d.name
            for d in db.execute(
                select(Document).where(Document.id.in_(doc_ids))
            ).scalars()
        }
    context = assemble_context(chunks, doc_names)

    # 会话:新建或复用(多轮带历史)
    history: list[tuple[str, str]] = []
    if payload.conversation_id:
        conv = _get_owned_conversation(db, user, payload.conversation_id)
        if conv.kb_id != kb.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Conversation belongs to another knowledge base",
            )
        history = [
            (m.role, m.content)
            for m in db.execute(
                select(Message)
                .where(Message.conv_id == conv.id)
                .order_by(Message.id)
            ).scalars()
        ]
    else:
        conv = Conversation(user_id=user.id, kb_id=kb.id, title=payload.question[:30])
        db.add(conv)
        db.commit()
        db.refresh(conv)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(
        {"role": role, "content": content} for role, content in history[-8:]
    )
    user_content = (
        f"资料:\n{context}\n\n问题: {payload.question}"
        if context
        else f"资料: (无)\n\n问题: {payload.question}"
    )
    messages.append({"role": "user", "content": user_content})
    answer = _make_chat_provider().complete(messages)

    sources = [
        ChatSource(
            doc_id=c.doc_id,
            doc_name=doc_names.get(c.doc_id),
            chunk_index=c.chunk_index,
            content=c.content,
            score=round(c.score, 4),
        )
        for c in chunks
    ]
    db.add(Message(conv_id=conv.id, role="user", content=payload.question))
    db.add(
        Message(
            conv_id=conv.id,
            role="assistant",
            content=answer,
            sources=[s.model_dump() for s in sources] or None,
            agent_type="retrieval_qa",
        )
    )
    db.commit()
    return ChatResponse(answer=answer, sources=sources, conversation_id=conv.id)


def list_conversations(db: Session, user: User) -> list[Conversation]:
    return list(
        db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.id.desc())
        ).scalars()
    )


def list_messages(db: Session, user: User, conv_id: int) -> list[Message]:
    _get_owned_conversation(db, user, conv_id)
    return list(
        db.execute(
            select(Message)
            .where(Message.conv_id == conv_id)
            .order_by(Message.id)
        ).scalars()
    )
