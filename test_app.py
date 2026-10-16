
import pytest

from app import app, get_db, init_db


@pytest.fixture
def client(tmp_path):
    old_database = app.config.get("DATABASE")
    old_testing = app.config.get("TESTING")

    app.config["DATABASE"] = str(tmp_path / "test_tasks.db")
    app.config["TESTING"] = True

    try:
        init_db()

        with app.test_client() as test_client:
            yield test_client
    finally:
        if old_database is None:
            app.config.pop("DATABASE", None)
        else:
            app.config["DATABASE"] = old_database

        if old_testing is None:
            app.config.pop("TESTING", None)
        else:
            app.config["TESTING"] = old_testing


def register_and_login(client):
    response = client.post(
        "/register",
        data={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.post(
        "/login",
        data={
            "identifier": "testuser",
            "password": "TestPass123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_homepage_opens(client):
    register_and_login(client)

    response = client.get("/")

    assert response.status_code == 200
    assert b"My To-Do List" in response.data


def test_add_task(client):
    register_and_login(client)

    response = client.post(
        "/",
        data={"task": "Study Python"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Study Python" in response.data


def test_complete_task(client):
    register_and_login(client)

    client.post("/", data={"task": "Test completion"})

    with get_db() as db:
        task = db.execute(
            "SELECT id FROM tasks WHERE title = ?",
            ("Test completion",),
        ).fetchone()

    assert task is not None

    response = client.post(
        f"/toggle/{task['id']}",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with get_db() as db:
        task = db.execute(
            "SELECT completed FROM tasks WHERE id = ?",
            (task["id"],),
        ).fetchone()

    assert task["completed"] == 1


def test_delete_task(client):
    register_and_login(client)

    client.post("/", data={"task": "Task to delete"})

    with get_db() as db:
        task = db.execute(
            "SELECT id FROM tasks WHERE title = ?",
            ("Task to delete",),
        ).fetchone()

    assert task is not None

    response = client.post(
        f"/delete/{task['id']}",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Task to delete" not in response.data

    with get_db() as db:
        deleted_task = db.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task["id"],),
        ).fetchone()

    assert deleted_task is None


def test_undo_completion(client):
    register_and_login(client)

    client.post("/", data={"task": "Undo test"})

    with get_db() as db:
        task = db.execute(
            "SELECT id FROM tasks WHERE title = ?",
            ("Undo test",),
        ).fetchone()

    assert task is not None

    client.post(f"/toggle/{task['id']}")

    response = client.post(
        f"/toggle/{task['id']}",
        follow_redirects=True,
    )
    assert response.status_code == 200

    with get_db() as db:
        task = db.execute(
            "SELECT completed FROM tasks WHERE id = ?",
            (task["id"],),
        ).fetchone()

    assert task["completed"] == 0
