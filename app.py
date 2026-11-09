from datetime import datetime
from functools import wraps
import json
import os
import secrets
import tempfile
from threading import RLock

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("BLOG_SECRET_KEY") or secrets.token_hex(32)
app.config["DATA_FILE"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog_data.json")
data_lock = RLock()


def _read_data():
    with open(app.config["DATA_FILE"], encoding="utf-8") as data_file:
        return json.load(data_file)


def _write_data(data):
    directory = os.path.dirname(app.config["DATA_FILE"])
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        delete=False,
    ) as data_file:
        json.dump(data, data_file, ensure_ascii=False, indent=2)
        data_file.write("\n")
        temp_path = data_file.name
    os.replace(temp_path, app.config["DATA_FILE"])


def init_data_file():
    with data_lock:
        if os.path.exists(app.config["DATA_FILE"]):
            return
        initial_data = {
            "users": [],
            "articles": [],
            "next_article_id": 1,
        }
        _write_data(initial_data)


def read_data():
    with data_lock:
        return _read_data()


def update_data(update):
    with data_lock:
        data = _read_data()
        result = update(data)
        _write_data(data)
        return result


def get_user(username):
    normalized_username = username.casefold()
    return next(
        (user for user in read_data()["users"] if user["username"].casefold() == normalized_username),
        None,
    )


def login_required(view):
    @wraps(view)
    def decorated_view(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return decorated_view


def get_articles(owner=None):
    articles = read_data()["articles"]
    if owner is not None:
        articles = [article for article in articles if article["author"].casefold() == owner.casefold()]
    return sorted(articles, key=lambda article: (article["date_published"], article["id"]), reverse=True)


def get_article_by_id(article_id):
    return next(
        (article for article in read_data()["articles"] if article["id"] == article_id),
        None,
    )


def save_article(title, content, author):
    def add(data):
        article_id = data["next_article_id"]
        article = {
            "id": article_id,
            "title": title,
            "content": content,
            "date_published": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "author": author,
        }
        data["articles"].append(article)
        data["next_article_id"] += 1
        return article

    return update_data(add)


def update_article(article_id, title, content):
    def update(data):
        article = next((item for item in data["articles"] if item["id"] == article_id), None)
        if article is not None:
            article["title"] = title
            article["content"] = content
        return article

    return update_data(update)


def delete_article(article_id):
    def delete(data):
        original_count = len(data["articles"])
        data["articles"] = [item for item in data["articles"] if item["id"] != article_id]
        return len(data["articles"]) != original_count

    return update_data(delete)


def article_belongs_to_user(article, username):
    return article is not None and article["author"].casefold() == username.casefold()


init_data_file()


@app.route("/")
def home():
    return render_template("home.html", articles=get_articles())


@app.route("/article/<int:article_id>")
def article(article_id):
    selected_article = get_article_by_id(article_id)
    if selected_article is None:
        abort(404)
    return render_template("article.html", article=selected_article)


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not content:
            flash("Title and content are required.", "error")
            return redirect(url_for("dashboard"))
        save_article(title, content, session["username"])
        flash("Article published.", "success")
        return redirect(url_for("dashboard"))
    return render_template("dashboard.html", articles=get_articles(session["username"]))


@app.route("/add_article", methods=["GET", "POST"])
@login_required
def add_article():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not content:
            flash("Title and content are required.", "error")
            return render_template("add_article.html"), 400
        save_article(title, content, session["username"])
        flash("Article published.", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_article.html")


@app.route("/edit_article/<int:article_id>", methods=["GET", "POST"])
@login_required
def edit_article(article_id):
    selected_article = get_article_by_id(article_id)
    if selected_article is None:
        abort(404)
    if not article_belongs_to_user(selected_article, session["username"]):
        abort(403)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not content:
            flash("Title and content are required.", "error")
            return render_template("edit_article.html", article=selected_article), 400
        update_article(article_id, title, content)
        flash("Article updated.", "success")
        return redirect(url_for("dashboard"))
    return render_template("edit_article.html", article=selected_article)


@app.route("/delete_article/<int:article_id>", methods=["POST"])
@login_required
def delete_article_route(article_id):
    selected_article = get_article_by_id(article_id)
    if selected_article is None:
        abort(404)
    if not article_belongs_to_user(selected_article, session["username"]):
        abort(403)
    delete_article(article_id)
    flash("Article deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(username) < 3 or len(username) > 32:
            flash("Username must be between 3 and 32 characters.", "error")
            return render_template("register.html", username=username), 400
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html", username=username), 400
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", username=username), 400

        def add_user(data):
            if any(user["username"].casefold() == username.casefold() for user in data["users"]):
                return False
            data["users"].append({
                "username": username,
                "password_hash": generate_password_hash(password),
            })
            return True

        if not update_data(add_user):
            flash("That username is already registered.", "error")
            return render_template("register.html", username=username), 409

        session.clear()
        session["username"] = username
        flash("Your account is ready.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html", username=username), 401
        session.clear()
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
