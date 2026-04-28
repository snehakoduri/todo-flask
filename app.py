from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DB_NAME = "tasks.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            priority TEXT,
            due_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


create_tables()


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists."

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")

        return "Invalid username or password."

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    if request.method == "POST":
        task_name = request.form.get("task")
        priority = request.form.get("priority")
        due_date = request.form.get("due_date")

        if task_name:
            conn.execute(
                """
                INSERT INTO tasks (user_id, name, done, priority, due_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session["user_id"], task_name, 0, priority, due_date)
            )
            conn.commit()

        conn.close()
        return redirect("/")

    search = request.args.get("search", "")
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "newest")

    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [session["user_id"]]

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")

    if status == "pending":
        query += " AND done = 0"
    elif status == "completed":
        query += " AND done = 1"

    if sort == "oldest":
        query += " ORDER BY id ASC"
    elif sort == "priority":
        query += """
        ORDER BY
        CASE priority
            WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2
            WHEN 'Low' THEN 3
            ELSE 4
        END
        """
    elif sort == "due_date":
        query += " ORDER BY due_date ASC"
    else:
        query += " ORDER BY id DESC"

    tasks = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "index.html",
        tasks=tasks,
        username=session["username"],
        search=search,
        status=status,
        sort=sort
    )


@app.route("/toggle/<int:task_id>")
def toggle(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    task = conn.execute(
        "SELECT done FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    ).fetchone()

    if task:
        new_status = 0 if task["done"] == 1 else 1
        conn.execute(
            "UPDATE tasks SET done = ? WHERE id = ? AND user_id = ?",
            (new_status, task_id, session["user_id"])
        )
        conn.commit()

    conn.close()
    return redirect("/")


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    ).fetchone()

    if not task:
        conn.close()
        return redirect("/")

    if request.method == "POST":
        name = request.form.get("task")
        priority = request.form.get("priority")
        due_date = request.form.get("due_date")

        conn.execute(
            """
            UPDATE tasks
            SET name = ?, priority = ?, due_date = ?
            WHERE id = ? AND user_id = ?
            """,
            (name, priority, due_date, task_id, session["user_id"])
        )
        conn.commit()
        conn.close()
        return redirect("/")

    conn.close()
    return render_template("edit.html", task=task)


@app.route("/delete/<int:task_id>")
def delete(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/clear")
def clear_completed():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM tasks WHERE done = 1 AND user_id = ?",
        (session["user_id"],)
    )
    conn.commit()
    conn.close()

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)