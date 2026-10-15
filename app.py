
from flask import Flask, request, redirect
from markupsafe import escape
from pathlib import Path
import sqlite3

app = Flask(__name__)

# Store the database inside the project's instance folder
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "instance"
DATABASE = DATABASE_DIR / "tasks.db"



def get_db():
    database_path = app.config.get("DATABASE", DATABASE)

    Path(database_path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        title = request.form.get("task", "").strip()

        if title:
            with get_db() as db:
                db.execute(
                    "INSERT INTO tasks (title) VALUES (?)",
                    (title,)
                )

        return redirect("/")

    with get_db() as db:
        tasks = db.execute(
            "SELECT * FROM tasks ORDER BY id DESC"
        ).fetchall()

    task_list = ""

    for task in tasks:
        task_id = task["id"]
        title = escape(task["title"])

        if task["completed"]:
            title = f"<del>{title}</del>"
            button_text = "Undo"
        else:
            button_text = "Complete"

        task_list += f"""
        <li>
            <span>{title}</span>

            <form method="POST" action="/toggle/{task_id}">
                <button type="submit">{button_text}</button>
            </form>

            <form method="POST" action="/delete/{task_id}">
                <button type="submit" class="delete">Delete</button>
            </form>
        </li>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>My To-Do List</title>

        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f1f5f9;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
            }}

            h1, h2 {{
                color: #1e293b;
            }}

            input {{
                padding: 12px;
                width: 60%;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }}

            button {{
                padding: 10px 12px;
                margin: 4px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                background: #2563eb;
                color: white;
            }}

            button.delete {{
                background: #dc2626;
            }}

            li {{
                background: white;
                margin: 10px 0;
                padding: 12px;
                border-radius: 8px;
                overflow-wrap: anywhere;
            }}

            form {{
                display: inline;
            }}
        </style>
    </head>

    <body>
        <h1>My To-Do List</h1>

        <form method="POST" action="/">
            <input
                type="text"
                name="task"
                placeholder="Enter a task"
                required
            >
            <button type="submit">Add Task</button>
        </form>

        <h2>My Tasks</h2>
        <ul>{task_list}</ul>
    </body>
    </html>
    """


@app.route("/toggle/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    with get_db() as db:
        db.execute("""
            UPDATE tasks
            SET completed = CASE
                WHEN completed = 0 THEN 1
                ELSE 0
            END
            WHERE id = ?
        """, (task_id,))

    return redirect("/")


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    with get_db() as db:
        db.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )

    return redirect("/")


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
