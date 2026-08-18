from app.rag.sparse import build_sparse_vector, tokenize


def test_tokenize_ascii_split_by_whitespace():
    assert tokenize("hello world") == ["hello", "world"]


def test_tokenize_chinese_adds_bigrams():
    toks = tokenize("多智能体知识库")
    assert "多智能体知识库" in toks
    assert "多智" in toks and "知识" in toks  # 字符二元组


def test_sparse_deterministic_across_calls():
    a1, v1 = build_sparse_vector("多智能体知识库 平台")
    a2, v2 = build_sparse_vector("多智能体知识库 平台")
    assert a1 == a2 and v1 == v2  # 稳定,跨进程一致


def test_sparse_indices_sorted_and_unique():
    indices, values = build_sparse_vector("A A B C C C")
    assert indices == sorted(indices)
    assert len(indices) == len(set(indices))
    assert sum(values) == 6  # A×2 + B×1 + C×3


def test_sparse_different_text_differs():
    i1, _ = build_sparse_vector("苹果")
    i2, _ = build_sparse_vector("香蕉")
    assert i1 != i2
