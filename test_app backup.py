
from app import app, get_db


def test_homepage_opens():
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert b"My To-Do List" in response.data


def test_add_task():
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.post(
            "/",
            data={"task": "Study Python"},
            follow_redirects=True
        )

    assert response.status_code == 200
    assert b"Study Python" in response.data


def test_complete_task():
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Add a task
        client.post(
            "/",
            data={"task": "Test completion"}
        )

        # Find the task ID
        with get_db() as db:
            task = db.execute(
                "SELECT id FROM tasks WHERE title = ? ORDER BY id DESC LIMIT 1",
                ("Test completion",)
            ).fetchone()

        assert task is not None

        # Mark the task as complete
        response = client.post(
            f"/toggle/{task['id']}",
            follow_redirects=True
        )

    assert response.status_code == 200
    assert b"<del>Test completion</del>" in response.data

def test_delete_task():
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Add a task
        client.post(
            "/",
            data={"task": "Task to delete"}
        )

        # Find the task ID
        with get_db() as db:
            task = db.execute(
                "SELECT id FROM tasks WHERE title = ? ORDER BY id DESC LIMIT 1",
                ("Task to delete",)
            ).fetchone()

        assert task is not None

        # Delete the task
        response = client.post(
            f"/delete/{task['id']}",
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b"Task to delete" not in response.data

    # Verify the task was removed from the database
    with get_db() as db:
        deleted_task = db.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task["id"],)
        ).fetchone()

    assert deleted_task is None

def test_undo_completion():
    app.config["TESTING"] = True

    with app.test_client() as client:
        # Add a task
        client.post(
            "/",
            data={"task": "Undo test"}
        )

        # Find the task ID
        with get_db() as db:
            task = db.execute(
                "SELECT id FROM tasks WHERE title = ? ORDER BY id DESC LIMIT 1",
                ("Undo test",)
            ).fetchone()

        assert task is not None

        # Complete the task
        client.post(f"/toggle/{task['id']}")

        # Undo completion
        response = client.post(
            f"/toggle/{task['id']}",
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b"Undo test" in response.data
        assert b"<del>Undo test</del>" not in response.data

    # Confirm the task is incomplete in SQLite
    with get_db() as db:
        task = db.execute(
            "SELECT completed FROM tasks WHERE id = ?",
            (task["id"],)
        ).fetchone()

    assert task["completed"] == 0
