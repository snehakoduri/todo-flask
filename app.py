from flask import Flask, render_template, request, redirect
import json
import os

app = Flask(__name__)

FILE_NAME = "tasks.json"


def load_tasks():
    if not os.path.exists(FILE_NAME):
        return []

    try:
        with open(FILE_NAME, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return []


def save_tasks(tasks):
    with open(FILE_NAME, "w", encoding="utf-8") as file:
        json.dump(tasks, file, indent=4)


tasks = load_tasks()


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        task_name = request.form.get("task")
        priority = request.form.get("priority")
        due_date = request.form.get("due_date")

        if task_name:
            tasks.append({
                "name": task_name,
                "done": False,
                "priority": priority,
                "due_date": due_date
            })
            save_tasks(tasks)

        return redirect("/")

    return render_template("index.html", tasks=tasks)


@app.route("/toggle/<int:index>")
def toggle(index):
    if 0 <= index < len(tasks):
        tasks[index]["done"] = not tasks[index]["done"]
        save_tasks(tasks)

    return redirect("/")


@app.route("/delete/<int:index>")
def delete(index):
    if 0 <= index < len(tasks):
        tasks.pop(index)
        save_tasks(tasks)

    return redirect("/")


@app.route("/clear")
def clear_completed():
    global tasks
    tasks = [task for task in tasks if not task["done"]]
    save_tasks(tasks)

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)