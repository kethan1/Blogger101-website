import json


def test_main_route_status_code(client) -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_sign_up_route_status_code(client) -> None:
    response = client.get("/sign_up")
    assert response.status_code == 200


def test_login_route_status_code(client) -> None:
    response = client.get("/login")
    assert response.status_code == 200


def test_blogs_api_route_status_code(client) -> None:
    response = client.get("/api/v1/blogs")
    assert response.status_code == 200


def test_login(client) -> None:
    response = client.post(
        "/login",
        data={"email": "joe@smoe.com", "password": "Password123"},
        content_type="multipart/form-data",
    )
    with client.session_transaction() as session:
        assert session["logged_in"] == {
            "email": "joe@smoe.com",
            "first_name": "Joe",
            "last_name": "Smoe",
            "username": "JoeSmoe",
        }
    assert response.status_code == 302


def test_logout(client) -> None:
    response = client.post(
        "/login",
        data={"email": "joe@smoe.com", "password": "Password123"},
        content_type="multipart/form-data",
    )
    with client.session_transaction() as session:
        assert session["logged_in"] == {
            "email": "joe@smoe.com",
            "first_name": "Joe",
            "last_name": "Smoe",
            "username": "JoeSmoe",
        }
    assert response.status_code == 302

    response = client.get("/logout")
    with client.session_transaction() as session:
        assert session["logged_in"] in [{}, None]
    assert response.status_code == 302


def test_check_user_api(client) -> None:
    response = client.post("/api/v1/auth/check-user", json={"email": "joe@smoe.com", "password": "Password123"})
    response_wrong_password = client.post("/api/v1/auth/check-user", json={"email": "joe@smoe.com", "password": "WrongPassword"})
    response_email_not_found = client.post("/api/v1/auth/check-user", json={"email": "wrongemail@smoe.com", "password": "Password123"})
    response_json = json.loads(response.get_data(as_text=True))
    response_wrong_password_json = json.loads(response_wrong_password.get_data(as_text=True))
    response_email_not_found_json = json.loads(response_email_not_found.get_data(as_text=True))
    assert response_json["found"] is True
    assert response_wrong_password_json["found"] is False
    assert response_wrong_password_json["message"] == "Incorrect Password"
    assert response_email_not_found_json["found"] is False
    assert response_email_not_found_json["message"] == "A User With That Email Was Not Found"


def test_add_user_api(client) -> None:
    response = client.post("/api/v1/auth/add-user", json={
        "first_name": "Bob",
        "last_name": "Builder",
        "username": "BobBuilder",
        "email": "bob@builder.com",
        "password": "Password12",
    })
    response_email_taken = client.post("/api/v1/auth/add-user", json={
        "first_name": "Bob",
        "last_name": "Builder",
        "username": "NotTaken",
        "email": "bob@builder.com",
        "password": "Password12",
    })
    response_username_taken = client.post("/api/v1/auth/add-user", json={
        "first_name": "Bob",
        "last_name": "Builder",
        "username": "BobBuilder",
        "email": "nottaken@builder.com",
        "password": "Password12",
    })
    response_json = json.loads(response.get_data(as_text=True))
    response_email_taken_json = json.loads(response_email_taken.get_data(as_text=True))
    response_username_taken_json = json.loads(response_username_taken.get_data(as_text=True))
    assert response_json["success"] is True
    assert response_email_taken_json["success"] is False
    assert response_email_taken_json["already"] == "email"
    assert response_username_taken_json["success"] is False
    assert response_username_taken_json["already"] == "username"
