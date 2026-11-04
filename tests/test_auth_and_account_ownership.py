def login_as(client, email: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_register_login_and_me(client):
    payload = {"email": "alice@example.com", "password": "secret123"}

    register_response = client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201, register_response.text
    assert register_response.json()["email"] == payload["email"]

    token = login_as(client, payload["email"], payload["password"])
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == payload["email"]


def test_logout_revokes_refresh_token_but_new_login_can_refresh(client):
    payload = {"email": "logout@example.com", "password": "secret123"}
    register_response = client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201, register_response.text

    first_login = client.post("/api/v1/auth/login", data=payload)
    assert first_login.status_code == 200, first_login.text
    first_tokens = first_login.json()
    headers = {"Authorization": f"Bearer {first_tokens['access_token']}"}

    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200, logout_response.text

    revoked_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_tokens["refresh_token"]},
    )
    assert revoked_refresh.status_code == 401

    second_login = client.post("/api/v1/auth/login", data=payload)
    assert second_login.status_code == 200, second_login.text
    valid_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_login.json()["refresh_token"]},
    )
    assert valid_refresh.status_code == 200, valid_refresh.text


def test_account_is_private_to_owner(client):
    first = {"email": "alice@example.com", "password": "secret123"}
    second = {"email": "bob@example.com", "password": "secret123"}

    client.post("/api/v1/auth/register", json=first)
    client.post("/api/v1/auth/register", json=second)

    alice_token = login_as(client, first["email"], first["password"])
    bob_token = login_as(client, second["email"], second["password"])

    create_response = client.post(
        "/api/v1/accounts/create",
        json={"name": "Alice account", "currency": "USD"},
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert create_response.status_code == 201, create_response.text
    account_id = create_response.json()["id"]

    alice_accounts = client.get(
        "/api/v1/accounts/",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob_accounts = client.get(
        "/api/v1/accounts/",
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert alice_accounts.status_code == 200
    assert bob_accounts.status_code == 200
    assert [item["id"] for item in alice_accounts.json()] == [account_id]
    assert bob_accounts.json() == []

    forbidden = client.get(
        f"/api/v1/accounts/{account_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert forbidden.status_code == 404, forbidden.text
