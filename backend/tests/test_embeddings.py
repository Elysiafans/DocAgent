from app.rag.embeddings import SiliconFlowEmbeddingProvider, fake_embed_texts


def test_fake_embed_deterministic_and_shared():
    v1 = fake_embed_texts(["你好", "世界"])
    v2 = fake_embed_texts(["你好", "世界"])
    assert len(v1) == 2
    assert len(v1[0]) == 8  # fake 维度
    assert v1 == v2
    assert v1[0] != v1[1]  # 不同文本不同向量


def test_provider_batches_and_parses(monkeypatch):
    provider = SiliconFlowEmbeddingProvider()
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            data = calls[-1]
            n = len(data["input"])
            return {
                "data": [
                    {"embedding": [float(i + 1) / 10.0] * 4, "index": i}
                    for i in range(n)
                ]
            }

    def fake_post(self, *args, **kwargs):
        calls.append(kwargs.get("json") or args[1])
        return FakeResponse()

    monkeypatch.setattr("app.rag.embeddings.httpx.Client.post", fake_post)
    result = provider.embed_texts(["a", "b"])
    assert len(result) == 2
    assert len(result[0]) == 4
    assert calls and len(calls) == 1  # 一次批量


def test_provider_instance_is_callable(monkeypatch):
    """回归:Provider 实例可直接作为 Embedder 传给 QdrantVectorStore。"""
    provider = SiliconFlowEmbeddingProvider()

    def fake_post(self, *args, **kwargs):
        class R:
            def raise_for_status(self):
                return None

            def json(self):
                data = kwargs["json"] or args[1]
                n = len(data["input"])
                return {"data": [{"embedding": [0.5] * 4, "index": i} for i in range(n)]}

        return R()

    monkeypatch.setattr("app.rag.embeddings.httpx.Client.post", fake_post)
    result = provider(["x", "y"])
    assert len(result) == 2
    assert result == provider.embed_texts(["x", "y"])
