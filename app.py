from flask import Flask, request, redirect, session, url_for
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import sqlite3
import os
import secrets
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY", secrets.token_hex(32)
)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "instance" / "tasks.db"


def get_db():
    path = app.config.get("DATABASE", DATABASE)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                theme TEXT NOT NULL DEFAULT 'light'
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)

        user_columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(users)").fetchall()
        }
        if "theme" not in user_columns:
            db.execute("""
                ALTER TABLE users
                ADD COLUMN theme TEXT NOT NULL DEFAULT 'light'
            """)

        task_columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "user_id" not in task_columns:
            db.execute("""
                ALTER TABLE tasks
                ADD COLUMN user_id INTEGER REFERENCES users(id)
            """)


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None

    with get_db() as db:
        return db.execute(
            "SELECT id, username, email, theme FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()


def page_style(theme="light"):
    dark = theme == "dark"
    bg = "#111827" if dark else "#f5f7fb"
    card = "#1f2937" if dark else "#ffffff"
    fg = "#f9fafb" if dark else "#172033"
    muted = "#9ca3af" if dark else "#667085"
    border = "#374151" if dark else "#dbe1ea"

    return f"""
    <style>
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0; padding: 20px;
        font-family: Arial, sans-serif;
        background: {bg}; color: {fg};
      }}
      .card {{
        background: {card}; color: {fg};
        width: min(440px, 100%);
        margin: 30px auto; padding: 28px;
        border-radius: 16px;
        box-shadow: 0 8px 30px #00000012;
      }}
      .brand {{ color: #637cff; font-size: 22px; font-weight: bold; }}
      input, select {{
        display: block; width: 100%;
        padding: 12px; margin: 8px 0 16px;
        border: 1px solid {border}; border-radius: 8px;
        background: {bg}; color: {fg};
      }}
      button, .button {{
        display: inline-block; padding: 11px 15px;
        background: #4263eb; color: white;
        border: 0; border-radius: 8px;
        text-decoration: none; cursor: pointer;
      }}
      .card button {{ width: 100%; }}
      .muted {{ color: {muted}; font-size: 14px; }}
      .error {{ color: #ef4444; }}
      .success {{ color: #22a06b; }}
      a {{ color: #8094ff; }}
    </style>
    """


def strong_password(password):
    return (
        len(password) >= 8
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
        and any(not c.isalnum() for c in password)
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("home"))

    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm:
            error = "Please fill in every field."
        elif len(username) > 80 or len(email) > 254:
            error = "Username or email is too long."
        elif not strong_password(password):
            error = "Use 8+ characters with uppercase, lowercase, number and symbol."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            try:
                with get_db() as db:
                    db.execute("""
                        INSERT INTO users (username, email, password_hash)
                        VALUES (?, ?, ?)
                    """, (
                        username, email, generate_password_hash(password)
                    ))
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                error = "Username or email is already registered."

    return f"""
    <!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Register | TaskFlow</title>{page_style()}
    </head><body><div class="card">
    <div class="brand">✓ TaskFlow</div><h1>Create account</h1>
    <p class="error">{escape(error)}</p>
    <form method="POST">
      <label>Username</label>
      <input name="username" maxlength="80" required>
      <label>Email</label>
      <input name="email" type="email" maxlength="254" required>
      <label>Password</label>
      <input name="password" type="password" minlength="8"
             autocomplete="new-password" required>
      <p class="muted">At least 8 characters, uppercase, lowercase, number and symbol.</p>
      <label>Confirm password</label>
      <input name="confirm_password" type="password" required>
      <button>Create account</button>
    </form>
    <p class="muted">Already registered? <a href="/login">Log in</a></p>
    </div></body></html>
    """


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    error = ""

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        with get_db() as db:
            user = db.execute("""
                SELECT * FROM users
                WHERE username = ? COLLATE NOCASE
                   OR email = ? COLLATE NOCASE
            """, (identifier, identifier)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        error = "Invalid username/email or password."

    return f"""
    <!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login | TaskFlow</title>{page_style()}
    </head><body><div class="card">
    <div class="brand">✓ TaskFlow</div><h1>Welcome back</h1>
    <p class="error">{escape(error)}</p>
    <form method="POST">
      <label>Username or email</label>
      <input name="identifier" autocomplete="username" required>
      <label>Password</label>
      <input name="password" type="password"
             autocomplete="current-password" required>
      <button>Log in</button>
    </form>
    <p class="muted">New user? <a href="/register">Create account</a></p>
    </div></body></html>
    """


@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = current_user()
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    message = ""
    error = ""

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "profile":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()

            if not username or not email:
                error = "Username and email are required."
            elif len(username) > 80 or len(email) > 254:
                error = "Username or email is too long."
            else:
                try:
                    with get_db() as db:
                        db.execute("""
                            UPDATE users SET username = ?, email = ?
                            WHERE id = ?
                        """, (username, email, user["id"]))
                    message = "Profile updated."
                except sqlite3.IntegrityError:
                    error = "Username or email is already in use."

        elif action == "password":
            old = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")

            with get_db() as db:
                record = db.execute(
                    "SELECT password_hash FROM users WHERE id = ?",
                    (user["id"],)
                ).fetchone()

            if not check_password_hash(record["password_hash"], old):
                error = "Current password is incorrect."
            elif not strong_password(new):
                error = "New password needs uppercase, lowercase, number, symbol and 8+ characters."
            elif new != confirm:
                error = "New passwords do not match."
            else:
                with get_db() as db:
                    db.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(new), user["id"])
                    )
                message = "Password changed."

        elif action == "theme":
            theme = request.form.get("theme", "light")
            if theme not in ("light", "dark"):
                error = "Invalid theme."
            else:
                with get_db() as db:
                    db.execute(
                        "UPDATE users SET theme = ? WHERE id = ?",
                        (theme, user["id"])
                    )
                message = "Theme preference saved."

    user = current_user()
    theme = user["theme"]

    return f"""
    <!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Account Settings | TaskFlow</title>{page_style(theme)}
    </head><body><div class="card">
    <div class="brand">✓ TaskFlow</div><h1>Account settings</h1>
    <p class="success">{escape(message)}</p>
    <p class="error">{escape(error)}</p>

    <h2>Profile</h2>
    <form method="POST">
      <input type="hidden" name="action" value="profile">
      <label>Username</label>
      <input name="username" maxlength="80" value="{escape(user['username'])}" required>
      <label>Email</label>
      <input name="email" type="email" maxlength="254" value="{escape(user['email'])}" required>
      <button>Save profile</button>
    </form>

    <hr><h2>Change password</h2>
    <form method="POST">
      <input type="hidden" name="action" value="password">
      <label>Current password</label>
      <input name="current_password" type="password" required>
      <label>New password</label>
      <input name="new_password" type="password" required>
      <label>Confirm new password</label>
      <input name="confirm_password" type="password" required>
      <button>Change password</button>
    </form>

    <hr><h2>Appearance</h2>
    <form method="POST">
      <input type="hidden" name="action" value="theme">
      <label>Choose your theme</label>
      <select name="theme">
        <option value="light" {"selected" if theme == "light" else ""}>☀ Light Mode</option>
        <option value="dark" {"selected" if theme == "dark" else ""}>☾ Dark Mode</option>
      </select>
      <button>Save theme</button>
    </form>

    <p><a href="/">Back to dashboard</a></p>
    </div></body></html>
    """


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.route("/", methods=["GET", "POST"])
def home():
    user = current_user()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("task", "").strip()

        if title and len(title) <= 500:
            with get_db() as db:
                db.execute(
                    "INSERT INTO tasks (title, user_id) VALUES (?, ?)",
                    (title, user["id"])
                )

        return redirect(url_for("home"))

    with get_db() as db:
        tasks = db.execute(
            """
            SELECT id, title, completed
            FROM tasks
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user["id"],)
        ).fetchall()

    total = len(tasks)
    completed = sum(task["completed"] for task in tasks)
    pending = total - completed
    progress = round(completed / total * 100) if total else 0

    dark = user["theme"] == "dark"
    bg = "#111827" if dark else "#f5f7fb"
    card = "#1f2937" if dark else "#ffffff"
    fg = "#f9fafb" if dark else "#172033"
    muted = "#9ca3af" if dark else "#667085"
    border = "#374151" if dark else "#edf0f5"

    task_list = ""

    for task in tasks:
        task_id = task["id"]
        title_html = escape(task["title"])

        if task["completed"]:
            title_html = (
                f'<span class="task-title completed">{title_html}</span>'
            )
            status = '<span class="status done">Completed</span>'
            action = "Undo"
            action_class = "undo"
        else:
            title_html = f'<span class="task-title">{title_html}</span>'
            status = '<span class="status pending">In progress</span>'
            action = "Complete"
            action_class = "complete"

        task_list += f"""
        <div class="task-row">
            <div class="task-main">
                <div class="task-info">
                    {title_html}
                    {status}
                </div>
            </div>
            <div class="task-actions">
                <form method="POST" action="/toggle/{task_id}">
                    <button class="action-btn {action_class}">
                        {action}
                    </button>
                </form>
                <form method="POST" action="/delete/{task_id}">
                    <button class="action-btn delete">Delete</button>
                </form>
            </div>
        </div>
        """

    if not task_list:
        task_list = """
        <div class="empty-state">
            <h3>Your space is clear!</h3>
            <p>Add your first task and start making progress.</p>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>TaskFlow Dashboard</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0; padding: 24px;
                font-family: Arial, sans-serif;
                background: {bg}; color: {fg};
            }}
            .container {{ max-width: 1050px; margin: auto; }}
            .topbar {{
                display: flex; justify-content: space-between;
                align-items: center; gap: 12px; flex-wrap: wrap;
                margin-bottom: 28px;
            }}
            .brand {{ color: #637cff; font-size: 23px; font-weight: bold; }}
            .account {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
            .card {{
                background: {card}; border: 1px solid {border};
                border-radius: 15px; padding: 20px; margin-bottom: 20px;
            }}
            .stats {{
                display: grid; grid-template-columns: repeat(3, 1fr);
                gap: 15px; margin-bottom: 20px;
            }}
            .stat-value {{ font-size: 30px; font-weight: bold; margin-top: 10px; }}
            .muted {{ color: {muted}; font-size: 13px; }}
            .progress-track {{
                background: {border}; height: 9px;
                border-radius: 20px; overflow: hidden; margin-top: 15px;
            }}
            .progress-fill {{
                background: #4263eb; height: 100%;
                width: {progress}%;
            }}
            input {{
                flex: 1; min-width: 0; padding: 13px;
                border: 1px solid {border}; border-radius: 8px;
                background: {bg}; color: {fg};
            }}
            button, .button {{
                display: inline-block; border: 0; border-radius: 8px;
                padding: 11px 14px; cursor: pointer;
                background: #4263eb; color: white;
                text-decoration: none; font-size: 13px;
            }}
            .add-form {{ display: flex; gap: 10px; }}
            .task-row {{
                display: flex; justify-content: space-between;
                align-items: center; gap: 15px;
                padding: 16px 0; border-bottom: 1px solid {border};
            }}
            .task-row:last-child {{ border-bottom: 0; }}
            .task-title {{ overflow-wrap: anywhere; }}
            .completed {{ text-decoration: line-through; color: {muted}; }}
            .status {{ display: block; font-size: 12px; margin-top: 6px; }}
            .done {{ color: #22a06b; }}
            .pending {{ color: #d49a31; }}
            .task-actions {{ display: flex; gap: 7px; }}
            .task-actions form {{ margin: 0; }}
            .undo {{ background: #16845b; }}
            .delete {{ background: #d64545; }}
            .empty-state {{ text-align: center; padding: 25px; }}
            @media (max-width: 600px) {{
                .stats {{ grid-template-columns: 1fr; }}
                .add-form {{ flex-direction: column; }}
                .task-row {{ align-items: flex-start; flex-direction: column; }}
            }}
        </style>
    </head>
    <body>
        <main class="container">
            <header class="topbar">
                <div>
                    <div class="brand">✓ TaskFlow</div>
                    <h1>My To-Do List</h1>
                    <div class="muted">
                        Welcome, {escape(user["username"])}!
                    </div>
                </div>
                <div class="account">
                    <a class="button" href="/settings">Account settings</a>
                    <form method="POST" action="/logout">
                        <button type="submit">Log out</button>
                    </form>
                </div>
            </header>

            <section class="stats">
                <div class="card">
                    <div class="muted">Total Tasks</div>
                    <div class="stat-value">{total}</div>
                </div>
                <div class="card">
                    <div class="muted">Completed</div>
                    <div class="stat-value">{completed}</div>
                </div>
                <div class="card">
                    <div class="muted">In Progress</div>
                    <div class="stat-value">{pending}</div>
                </div>
            </section>

            <section class="card">
                <h2>Your progress</h2>
                <p class="muted">{completed} of {total} tasks completed</p>
                <div class="progress-track">
                    <div class="progress-fill"></div>
                </div>
                <p>{progress}% complete</p>
            </section>

            <section class="card">
                <h2>My Tasks</h2>
                <form class="add-form" method="POST" action="/">
                    <input name="task" maxlength="500"
                           placeholder="What do you need to do?" required>
                    <button type="submit">+ Add Task</button>
                </form>
            </section>

            <section class="card">
                {task_list}
            </section>
            <p class="muted">TaskFlow · Flask and SQLite</p>
        </main>
    </body>
    </html>
    """


@app.route("/toggle/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    user = current_user()
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    with get_db() as db:
        db.execute(
            """
            UPDATE tasks
            SET completed = CASE WHEN completed = 0 THEN 1 ELSE 0 END
            WHERE id = ? AND user_id = ?
            """,
            (task_id, user["id"])
        )

    return redirect(url_for("home"))


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    user = current_user()
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    with get_db() as db:
        db.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user["id"])
        )

    return redirect(url_for("home"))


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True)