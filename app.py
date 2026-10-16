
from flask import Flask, request, redirect, session, url_for
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import sqlite3
import os
import secrets

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
        margin: 0;
        padding: 24px;
        font-family: Inter, "Segoe UI", Arial, sans-serif;
        background: {bg};
        color: {fg};
        line-height: 1.6;
      }}
      .card {{
        background: {card};
        color: {fg};
        width: min(460px, 100%);
        margin: 30px auto;
        padding: 28px;
        border: 1px solid {border};
        border-radius: 18px;
        box-shadow: 0 8px 30px #00000012;
      }}
      .brand {{
        color: #7565ee;
        font-size: 23px;
        font-weight: 800;
      }}
      input, select {{
        display: block;
        width: 100%;
        padding: 13px;
        margin: 8px 0 16px;
        border: 1px solid {border};
        border-radius: 10px;
        background: {bg};
        color: {fg};
        font: inherit;
      }}
      input:focus, select:focus {{
        outline: 2px solid #7565ee;
        outline-offset: 1px;
      }}
      button, .button {{
        display: inline-block;
        padding: 12px 16px;
        background: #7565ee;
        color: white;
        border: 0;
        border-radius: 10px;
        text-decoration: none;
        cursor: pointer;
        font: inherit;
        font-weight: 600;
      }}
      button:hover, .button:hover {{
        background: #6553df;
      }}
      .card button {{ width: 100%; }}
      .muted {{ color: {muted}; font-size: 14px; }}
      .error {{ color: #ef4444; }}
      .success {{ color: #22a06b; }}
      a {{ color: #8878ff; }}
      @media (max-width: 480px) {{
        body {{ padding: 14px; }}
        .card {{ padding: 21px; }}
      }}
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
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Register | TaskFlow</title>
      {page_style()}
    </head>
    <body>
      <div class="card">
        <div class="brand">✓ TaskFlow</div>
        <h1>Create account</h1>
        <p class="error">{escape(error)}</p>
        <form method="POST">
          <label>Username</label>
          <input name="username" maxlength="80" required>
          <label>Email</label>
          <input name="email" type="email" maxlength="254" required>
          <label>Password</label>
          <input name="password" type="password" minlength="8"
                 autocomplete="new-password" required>
          <p class="muted">Use at least 8 characters, including uppercase, lowercase, a number and a symbol.</p>
          <label>Confirm password</label>
          <input name="confirm_password" type="password"
                 autocomplete="new-password" required>
          <button type="submit">Create account</button>
        </form>
        <p class="muted">Already registered? <a href="/login">Log in</a></p>
      </div>
    </body>
    </html>
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
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Login | TaskFlow</title>
      {page_style()}
    </head>
    <body>
      <div class="card">
        <div class="brand">✓ TaskFlow</div>
        <h1>Welcome back</h1>
        <p class="error">{escape(error)}</p>
        <form method="POST">
          <label>Username or email</label>
          <input name="identifier" autocomplete="username" required>
          <label>Password</label>
          <input name="password" type="password"
                 autocomplete="current-password" required>
          <button type="submit">Log in</button>
        </form>
        <p class="muted">New user? <a href="/register">Create account</a></p>
      </div>
    </body>
    </html>
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

            if not record or not check_password_hash(record["password_hash"], old):
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
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Account Settings | TaskFlow</title>
      {page_style(theme)}
    </head>
    <body>
      <div class="card">
        <div class="brand">✓ TaskFlow</div>
        <h1>Account settings</h1>
        <p class="success">{escape(message)}</p>
        <p class="error">{escape(error)}</p>

        <h2>Profile</h2>
        <form method="POST">
          <input type="hidden" name="action" value="profile">
          <label>Username</label>
          <input name="username" maxlength="80"
                 value="{escape(user['username'])}" required>
          <label>Email</label>
          <input name="email" type="email" maxlength="254"
                 value="{escape(user['email'])}" required>
          <button type="submit">Save profile</button>
        </form>

        <hr>
        <h2>Change password</h2>
        <form method="POST">
          <input type="hidden" name="action" value="password">
          <label>Current password</label>
          <input name="current_password" type="password" required>
          <label>New password</label>
          <input name="new_password" type="password" required>
          <label>Confirm new password</label>
          <input name="confirm_password" type="password" required>
          <button type="submit">Change password</button>
        </form>

        <hr>
        <h2>Appearance</h2>
        <form method="POST">
          <input type="hidden" name="action" value="theme">
          <label>Choose your theme</label>
          <select name="theme">
            <option value="light" {"selected" if theme == "light" else ""}>Light Mode</option>
            <option value="dark" {"selected" if theme == "dark" else ""}>Dark Mode</option>
          </select>
          <button type="submit">Save theme</button>
        </form>

        <p><a href="/">Back to dashboard</a></p>
      </div>
    </body>
    </html>
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
        tasks = db.execute("""
            SELECT id, title, completed
            FROM tasks
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user["id"],)).fetchall()

    total = len(tasks)
    completed = sum(task["completed"] for task in tasks)
    pending = total - completed
    progress = round(completed / total * 100) if total else 0

    theme = user["theme"]
    dark = theme == "dark"
    bg = "#0b1120" if dark else "#f4f6fb"
    card = "#151f32" if dark else "#ffffff"
    fg = "#f1f5f9" if dark else "#172033"
    muted = "#94a3b8" if dark else "#6b7280"
    border = "#29364d" if dark else "#e7eaf2"

    task_list = ""

    for task in tasks:
        task_id = task["id"]
        title_html = escape(task["title"])
        is_completed = bool(task["completed"])
        status = (
            '<span class="status done">Completed</span>'
            if is_completed
            else '<span class="status pending">In progress</span>'
        )

        action_label = "Undo" if is_completed else "Complete"
        action_class = "undo" if is_completed else "complete"

        task_list += f"""
        <div class="task-row"
             data-status="{'completed' if is_completed else 'pending'}">
          <div class="task-info">
            <div style="display:flex; align-items:center; gap:12px;">
              <input
                type="checkbox"
                class="task-checkbox"
                aria-label="Task completion status"
                {"checked" if is_completed else ""}
                disabled>
              <span class="task-title">{title_html}</span>
            </div>
            {status}
          </div>
          <div class="task-actions">
            <form method="POST" action="/toggle/{task_id}">
              <button type="submit" class="action-btn {action_class}">
                {action_label}
              </button>
            </form>
            <form method="POST" action="/delete/{task_id}"
                  onsubmit="return confirm('Delete this task?')">
              <button type="submit" class="action-btn delete">Delete</button>
            </form>
          </div>
        </div>
        """

    if not task_list:
        task_list = """
        <div class="empty-state">
          <div class="empty-icon">✓</div>
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
          margin: 0;
          padding: 36px 28px;
          min-height: 100vh;
          font-family: Inter, "Segoe UI", Arial, sans-serif;
          background:
            radial-gradient(ellipse at top left, #7565ee12, transparent 40%),
            {bg};
          color: {fg};
          line-height: 1.6;
        }}

        .container {{ max-width: 1160px; margin: 0 auto; }}

        .topbar {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 24px;
          flex-wrap: wrap;
          margin-bottom: 30px;
        }}

        .brand {{
          color: #8878ff;
          font-size: 20px;
          font-weight: 800;
          letter-spacing: .5px;
        }}

        h1 {{
          font-size: clamp(28px, 4vw, 36px);
          line-height: 1.2;
          letter-spacing: -1px;
          margin: 8px 0 10px;
        }}

        h2 {{ font-size: 21px; margin: 0 0 18px; }}

        .welcome {{ color: {muted}; font-size: 15px; }}

        .account {{ display: flex; gap: 10px; align-items: center; }}

        .account form {{ margin: 0; }}

        .card {{
          background: {card};
          border: 1px solid {border};
          border-radius: 20px;
          padding: 27px;
          margin-bottom: 22px;
          box-shadow: 0 8px 30px #00000008;
          transition: border-color .2s, transform .2s, box-shadow .2s;
        }}

        .stats {{
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 20px;
          margin-bottom: 22px;
        }}

        .stats .card {{ margin-bottom: 0; padding: 25px; }}

        .stats .card:hover {{
          transform: translateY(-3px);
          border-color: #7565ee80;
          box-shadow: 0 12px 28px #00000012;
        }}

        .stat-label {{ color: {muted}; font-size: 14px; }}

        .stat-value {{
          font-size: 34px;
          font-weight: 800;
          letter-spacing: -1px;
          margin-top: 8px;
        }}

        .stat-icon {{
          display: inline-grid;
          place-items: center;
          width: 44px;
          height: 44px;
          border-radius: 14px;
          background: #7565ee1a;
          color: #9285ff;
          font-size: 21px;
          margin-bottom: 13px;
        }}

        .muted {{ color: {muted}; font-size: 14px; }}

        .progress-track {{
          background: {border};
          height: 10px;
          border-radius: 30px;
          overflow: hidden;
          margin-top: 18px;
        }}

        .progress-fill {{
          background: linear-gradient(90deg, #7565ee, #ad91ff);
          height: 100%;
          width: {progress}%;
          border-radius: 30px;
          transition: width .4s ease;
        }}

        input, select {{
          display: block;
          width: 100%;
          min-width: 0;
          padding: 14px 16px;
          border: 1px solid {border};
          border-radius: 12px;
          background: {bg};
          color: {fg};
          font: inherit;
          font-size: 14px;
          outline: none;
          transition: border-color .2s, box-shadow .2s;
        }}

        input:focus, select:focus {{
          border-color: #8878ff;
          box-shadow: 0 0 0 3px #7565ee20;
        }}

        button, .button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          border: 1px solid transparent;
          border-radius: 11px;
          padding: 12px 17px;
          cursor: pointer;
          background: #7565ee;
          color: #fff;
          text-decoration: none;
          font: inherit;
          font-size: 14px;
          font-weight: 650;
          white-space: nowrap;
          transition: transform .15s, background .2s, box-shadow .2s;
        }}

        button:hover, .button:hover {{
          background: #6553df;
          box-shadow: 0 5px 15px #7565ee30;
          transform: translateY(-1px);
        }}

        .add-form {{ display: flex; align-items: center; gap: 12px; }}
        .add-form input {{ flex: 1; }}

        .task-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 15px;
          flex-wrap: wrap;
          margin-bottom: 8px;
        }}

        .task-header h2 {{ margin-bottom: 0; }}

        .filters {{ display: flex; gap: 8px; flex-wrap: wrap; }}

        .filters button {{
          background: {border};
          color: {fg};
          padding: 10px 15px;
        }}

        .filters button.active {{ background: #7565ee; color: #fff; }}

        .task-row {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 18px;
          padding: 19px 0;
          border-bottom: 1px solid {border};
        }}

        .task-row:last-child {{ border-bottom: 0; padding-bottom: 4px; }}

        .task-info {{ min-width: 0; flex: 1; }}

        .task-title {{
          display: block;
          font-weight: 600;
          overflow-wrap: anywhere;
        }}

        .completed {{ text-decoration: none; color: inherit; }}

        .task-checkbox {{
          display: inline-block;
          width: 19px;
          height: 19px;
          margin: 0;
          padding: 0;
          accent-color: #7565ee;
          cursor: pointer;
          flex-shrink: 0;
        }}

        .status {{ display: block; font-size: 12px; font-weight: 600; margin-top: 5px; }}
        .done {{ color: #22c58b; }}
        .pending {{ color: #f0ad4e; }}

        .task-actions {{ display: flex; align-items: center; gap: 8px; flex-shrink: 0; }}
        .task-actions form {{ margin: 0; }}

        .action-btn {{ padding: 9px 13px; font-size: 12px; border-radius: 9px; }}
        .undo {{ background: #16845b; }}
        .undo:hover {{ background: #11734e; }}
        .delete {{ background: #dc4c64; }}
        .delete:hover {{ background: #c63850; }}

        .empty-state {{ text-align: center; padding: 42px 14px; color: {muted}; }}

        .empty-icon {{
          margin: 0 auto 14px;
          width: 56px;
          height: 56px;
          display: grid;
          place-items: center;
          border-radius: 18px;
          background: #7565ee1a;
          color: #9285ff;
          font-size: 27px;
        }}

        a {{ color: inherit; }}

        @media (max-width: 760px) {{
          body {{ padding: 24px 18px; }}
          .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
          .stats .card {{ padding: 20px; }}
          .stats .card:first-child {{ grid-column: 1 / -1; }}
          .card {{ padding: 21px; }}
          .topbar {{ gap: 18px; }}
          .account {{ width: 100%; flex-wrap: wrap; }}
        }}

        @media (max-width: 520px) {{
          body {{ padding: 18px 12px; }}
          .stats {{ grid-template-columns: 1fr; }}
          .stats .card:first-child {{ grid-column: auto; }}
          .card {{ padding: 18px; border-radius: 16px; }}
          .add-form {{ flex-direction: column; align-items: stretch; }}
          .task-row {{ align-items: flex-start; flex-direction: column; gap: 12px; }}
          .task-actions {{ width: 100%; }}
          .task-actions form {{ flex: 1; }}
          .task-actions button {{ width: 100%; }}
          .filters {{ width: 100%; }}
          .filters button {{ flex: 1; padding: 10px 8px; }}
          .account .button, .account form {{ flex: 1; }}
          .account form button {{ width: 100%; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{
            scroll-behavior: auto !important;
            transition: none !important;
          }}
        }}
      </style>
    </head>
    <body>
      <main class="container">
        <header class="topbar">
          <div>
            <div class="brand">✓ TaskFlow</div>
            <h1>My To-Do List</h1>
            <div class="welcome">
              Welcome back, {escape(user["username"])}. Let's get things done.
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
            <div class="stat-icon">▤</div>
            <div class="stat-label">Total Tasks</div>
            <div class="stat-value">{total}</div>
          </div>
          <div class="card">
            <div class="stat-icon">✓</div>
            <div class="stat-label">Completed</div>
            <div class="stat-value">{completed}</div>
          </div>
          <div class="card">
            <div class="stat-icon">◷</div>
            <div class="stat-label">In Progress</div>
            <div class="stat-value">{pending}</div>
          </div>
        </section>

        <section class="card">
          <h2>Your progress</h2>
          <p class="muted">
            {completed} of {total} tasks completed · {progress}% complete
          </p>
          <div class="progress-track">
            <div class="progress-fill"></div>
          </div>
        </section>

        <section class="card">
          <h2>Add a task</h2>
          <form class="add-form" method="POST" action="/">
            <input name="task" maxlength="500"
                   placeholder="What do you need to do?" required>
            <button type="submit">+ Add Task</button>
          </form>
        </section>

        <section class="card">
          <div class="task-header">
            <h2>My Tasks</h2>
            <div class="filters">
              <button type="button" class="active" data-filter="all">All</button>
              <button type="button" data-filter="pending">In Progress</button>
              <button type="button" data-filter="completed">Completed</button>
            </div>
          </div>
          <div id="task-list">{task_list}</div>
        </section>

        <p class="muted">TaskFlow · Stay focused, one task at a time.</p>
      </main>

      <script>
        document.querySelectorAll("[data-filter]").forEach(function(button) {{
          button.addEventListener("click", function() {{
            document.querySelectorAll("[data-filter]").forEach(function(item) {{
              item.classList.remove("active");
            }});

            button.classList.add("active");
            const filter = button.dataset.filter;

            document.querySelectorAll(".task-row").forEach(function(row) {{
              row.style.display =
                filter === "all" || row.dataset.status === filter
                ? "flex" : "none";
            }});
          }});
        }});
      </script>
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
        db.execute("""
            UPDATE tasks
            SET completed = CASE WHEN completed = 0 THEN 1 ELSE 0 END
            WHERE id = ? AND user_id = ?
        """, (task_id, user["id"]))

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
