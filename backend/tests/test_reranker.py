from app.rag.reranker import SiliconFlowReranker, fake_rerank


def test_fake_rerank_orders_by_overlap():
    docs = ["完全不相关的文字 abc", "苹果香蕉", "苹果"]
    ranked = fake_rerank("苹果", docs, top_n=2)
    assert len(ranked) == 2
    # 与"苹果"重叠最多的是 "苹果",其次 "苹果香蕉"
    assert ranked[0][0] == 2
    assert ranked[1][0] == 1
    assert ranked[0][1] >= ranked[1][1]


def test_siliconflow_rerank(monkeypatch):
    provider = SiliconFlowReranker()
    calls = []

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            payload = calls[-1]
            assert payload["model"] == "BAAI/bge-reranker-v2-m3"
            assert payload["query"] == "苹果"
            # 返回乱序,验证 provider 会按分数排序
            return {
                "results": [
                    {"index": 0, "relevance_score": 0.1},
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 2, "relevance_score": 0.5},
                ]
            }

    def fake_post(self, *args, **kwargs):
        calls.append(kwargs["json"])
        return FakeResp()

    monkeypatch.setattr("app.rag.reranker.httpx.Client.post", fake_post)
    ranked = provider.rerank("苹果", ["a", "b", "c"], top_n=2)
    assert ranked == [(1, 0.9), (2, 0.5)]
