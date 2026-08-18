import pytest

from app.rag.chunking import chunk_document


def test_recursive_respects_chinese_separators():
    text = "第一句。第二句。第三句。\n\n第四句。\n\n第五句。\n\n第六句。"
    chunks = chunk_document(
        text, "recursive", chunk_size=16, chunk_overlap=4, source={"doc_id": 1}
    )
    assert len(chunks) > 1
    assert all(c.char_count > 0 for c in chunks)
    assert all(c.hash for c in chunks)
    # 幂等:同输入同哈希
    again = chunk_document(
        text, "recursive", chunk_size=16, chunk_overlap=4, source={"doc_id": 1}
    )
    assert [c.hash for c in chunks] == [c.hash for c in again]


def test_markdown_header_keeps_heading_context():
    text = "# 第一章\n\n内容甲。\n\n## 第一节\n\n内容乙。"
    chunks = chunk_document(
        text, "markdown_header", chunk_size=200, chunk_overlap=0, source={"doc_id": 2}
    )
    assert any("# 第一章" in c.content for c in chunks)


def test_unsupported_strategy_raises():
    with pytest.raises(ValueError):
        chunk_document("x", "unknown_strategy", 100, 0, source={})
