
import sqlite3
import pytest
from app import app


@pytest.fixture
def client(tmp_path):
    test_db = tmp_path / "test_tasks.db"

    with sqlite3.connect(test_db) as db:
        db.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)

    app.config["TESTING"] = True
    app.config["DATABASE"] = test_db

    with app.test_client() as test_client:
        yield test_client

    app.config.pop("DATABASE", None)


def test_homepage_opens(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"My To-Do List" in response.data


def test_add_task(client):
    response = client.post(
        "/",
        data={"task": "Study Python"},
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Study Python" in response.data


def test_complete_task(client):
    client.post("/", data={"task": "Test completion"})

    with app.config["DATABASE"].open("rb") if False else app.test_client() as unused:
        pass

    test_db = app.config["DATABASE"]

    with sqlite3.connect(test_db) as db:
        task = db.execute(
            "SELECT id FROM tasks WHERE title = ?",
            ("Test completion",)
        ).fetchone()

    assert task is not None

    response = client.post(
        f"/toggle/{task[0]}",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"<del>Test completion</del>" in response.data


def test_delete_task(client):
    client.post("/", data={"task": "Task to delete"})

    test_db = app.config["DATABASE"]

    with sqlite3.connect(test_db) as db:
        task = db.execute(
            "SELECT id FROM tasks WHERE title = ?",
            ("Task to delete",)
        ).fetchone()

    assert task is not None

    response = client.post(
        f"/delete/{task[0]}",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Task to delete" not in response.data


def test_undo_completion(client):
    client.post("/", data={"task": "Undo test"})

    test_db = app.config["DATABASE"]

    with sqlite3.connect(test_db) as db:
        task = db.execute(
            "SELECT id FROM tasks WHERE title = ?",
            ("Undo test",)
        ).fetchone()

    assert task is not None

    client.post(f"/toggle/{task[0]}")
    response = client.post(
        f"/toggle/{task[0]}",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Undo test" in response.data
    assert b"<del>Undo test</del>" not in response.data
