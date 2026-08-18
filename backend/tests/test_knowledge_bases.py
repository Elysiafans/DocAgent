def _auth_headers(client, email="u@test.com", password="password123"):
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_list_get_kb(client):
    h = _auth_headers(client)
    r = client.post(
        "/api/v1/knowledge_bases",
        json={"name": "我的知识库", "description": "测试知识库"},
        headers=h,
    )
    assert r.status_code == 201
    kb = r.json()
    assert kb["name"] == "我的知识库"
    assert kb["chunk_strategy"] == "recursive"
    assert kb["chunk_size"] == 800

    assert len(client.get("/api/v1/knowledge_bases", headers=h).json()) == 1
    assert client.get(f"/api/v1/knowledge_bases/{kb['id']}", headers=h).json()["id"] == kb["id"]


def test_update_delete_kb(client):
    h = _auth_headers(client)
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "A"}, headers=h
    ).json()["id"]

    r = client.patch(
        f"/api/v1/knowledge_bases/{kb_id}",
        json={"name": "B", "chunk_size": 500},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "B"
    assert r.json()["chunk_size"] == 500

    assert client.delete(f"/api/v1/knowledge_bases/{kb_id}", headers=h).status_code == 204
    assert client.get(f"/api/v1/knowledge_bases/{kb_id}", headers=h).status_code == 404


def test_cannot_access_others_kb(client):
    h1 = _auth_headers(client, email="u1@test.com")
    h2 = _auth_headers(client, email="u2@test.com")
    kb_id = client.post(
        "/api/v1/knowledge_bases", json={"name": "private"}, headers=h1
    ).json()["id"]

    assert client.get(f"/api/v1/knowledge_bases/{kb_id}", headers=h2).status_code == 404
    assert (
        client.delete(f"/api/v1/knowledge_bases/{kb_id}", headers=h2).status_code
        == 404
    )


def test_kb_requires_auth(client):
    assert client.get("/api/v1/knowledge_bases").status_code == 401
