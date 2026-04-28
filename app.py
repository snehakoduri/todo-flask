from flask import Flask, render_template, request, redirect, session
import os
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            name TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            priority TEXT,
            due_date TEXT
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


create_tables()


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
            conn.commit()
            cur.close()
            conn.close()
            return redirect("/login")
        except psycopg2.IntegrityError:
            conn.rollback()
            cur.close()
            conn.close()
            return "Username already exists."

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )
        user = cur.fetchone()

        cur.close()
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
    cur = conn.cursor()

    if request.method == "POST":
        task_name = request.form.get("task")
        priority = request.form.get("priority")
        due_date = request.form.get("due_date")

        if task_name:
            cur.execute(
                """
                INSERT INTO tasks (user_id, name, done, priority, due_date)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session["user_id"], task_name, 0, priority, due_date)
            )
            conn.commit()

        cur.close()
        conn.close()
        return redirect("/")

    search = request.args.get("search", "")
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "newest")

    query = "SELECT * FROM tasks WHERE user_id = %s"
    params = [session["user_id"]]

    if search:
        query += " AND name ILIKE %s"
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
        query += " ORDER BY due_date ASC NULLS LAST"
    else:
        query += " ORDER BY id DESC"

    cur.execute(query, params)
    tasks = cur.fetchall()

    cur.close()
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
    cur = conn.cursor()

    cur.execute(
        "SELECT done FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"])
    )
    task = cur.fetchone()

    if task:
        new_status = 0 if task["done"] == 1 else 1
        cur.execute(
            "UPDATE tasks SET done = %s WHERE id = %s AND user_id = %s",
            (new_status, task_id, session["user_id"])
        )
        conn.commit()

    cur.close()
    conn.close()
    return redirect("/")


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"])
    )
    task = cur.fetchone()

    if not task:
        cur.close()
        conn.close()
        return redirect("/")

    if request.method == "POST":
        name = request.form.get("task")
        priority = request.form.get("priority")
        due_date = request.form.get("due_date")

        cur.execute(
            """
            UPDATE tasks
            SET name = %s, priority = %s, due_date = %s
            WHERE id = %s AND user_id = %s
            """,
            (name, priority, due_date, task_id, session["user_id"])
        )
        conn.commit()

        cur.close()
        conn.close()
        return redirect("/")

    cur.close()
    conn.close()
    return render_template("edit.html", task=task)


@app.route("/delete/<int:task_id>")
def delete(task_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"])
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


@app.route("/clear")
def clear_completed():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM tasks WHERE done = 1 AND user_id = %s",
        (session["user_id"],)
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)