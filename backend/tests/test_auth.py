def _register(client, email="a@test.com", password="password123"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )


def test_register_login_me(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.json()["email"] == "a@test.com"
    assert "hashed_password" not in r.json()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "a@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@test.com"


def test_register_duplicate_email(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_login_wrong_password(client):
    _register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "a@test.com", "password": "wrongpass"},
    )
    assert r.status_code == 401


def test_me_unauthenticated(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        ).status_code
        == 401
    )
