from app.rag.client import get_qdrant

TEST_COLLECTION = "docagent_test_collection"


def test_qdrant_connect_and_collection_ops():
    client = get_qdrant()
    # 清理可能残留
    if client.collection_exists(TEST_COLLECTION):
        client.delete_collection(TEST_COLLECTION)
    client.create_collection(
        TEST_COLLECTION, vectors_config={"size": 4, "distance": "Cosine"}
    )
    assert client.collection_exists(TEST_COLLECTION)
    names = [c.name for c in client.get_collections().collections]
    assert TEST_COLLECTION in names
    client.delete_collection(TEST_COLLECTION)
    assert not client.collection_exists(TEST_COLLECTION)
