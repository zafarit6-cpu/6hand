import csv
import io
import math
import os
from collections import defaultdict, deque
from typing import List, Tuple

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from . import db
from .models import Edge, User

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    """Главная страница с приветствием."""
    return render_template("index.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация пользователя."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip() or None
        discord_tag = request.form.get("discord_tag", "").strip() or None

        if not username or not password:
            flash("Никнейм и пароль обязательны")
            return redirect(url_for("main.register"))

        if User.query.filter_by(username=username).first():
            flash("Такой пользователь уже существует")
            return redirect(url_for("main.register"))

        user = User(username=username, email=email, discord_tag=discord_tag)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Регистрация успешна")
        return redirect(url_for("main.profile"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Логин пользователя."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Добро пожаловать")
            return redirect(url_for("main.profile"))
        flash("Неверный логин или пароль")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы")
    return redirect(url_for("main.index"))


@bp.route("/profile")
@login_required
def profile():
    """Профиль пользователя с уровнем и достижениями."""
    user_edges = Edge.query.filter_by(user_id=current_user.id).count()
    level = int(math.floor(math.log2(user_edges + 1))) if user_edges else 0
    achievements = []
    for threshold in [1, 10, 50, 100, 500]:
        if user_edges >= threshold:
            achievements.append(f"{threshold} связей")
    return render_template("profile.html", user_edges=user_edges, level=level, achievements=achievements)


@bp.route("/add_edge", methods=["GET", "POST"])
@login_required
def add_edge():
    """Добавление связи между двумя никами с автоматическим замыканием."""
    if request.method == "POST":
        nick1 = request.form.get("nick1", "").strip()
        nick2 = request.form.get("nick2", "").strip()
        role = request.form.get("role", "").strip()
        avatar_url = request.form.get("avatar_url", "").strip() or None
        if not nick1 or not nick2 or not role:
            flash("Все поля обязательны")
            return redirect(url_for("main.add_edge"))

        if nick1 == nick2:
            flash("Нельзя добавить связь с самим собой")
            return redirect(url_for("main.add_edge"))

        direct_exists = Edge.query.filter_by(nick1=nick1, nick2=nick2, role=role).first()
        if direct_exists:
            flash("Такая связь уже существует")
            return redirect(url_for("main.add_edge"))

        # Проверка, существует ли путь длиной > 1 между этими никами.
        path = find_path(nick1, nick2, max_depth=6)
        if path and len(path) > 2:
            edge = Edge(nick1=nick1, nick2=nick2, role=role, avatar_url=avatar_url, user_id=current_user.id, is_transitive=True)
            db.session.add(edge)
            current_user.edges_added += 1
            db.session.commit()
            flash("Обнаружен существующий путь, добавлена транзитивная связь")
            return redirect(url_for("main.add_edge"))

        edge = Edge(nick1=nick1, nick2=nick2, role=role, avatar_url=avatar_url, user_id=current_user.id, is_transitive=False)
        db.session.add(edge)
        current_user.edges_added += 1
        db.session.commit()
        flash("Связь добавлена")
        return redirect(url_for("main.add_edge"))

    return render_template("add_edge.html")


@bp.route("/search")
def search():
    """Поиск соседей по нику."""
    query = request.args.get("q", "").strip()
    neighbors = []
    if query:
        neighbors = [
            (edge.nick2, edge.role, edge.is_transitive)
            for edge in Edge.query.filter((Edge.nick1 == query) | (Edge.nick2 == query)).all()
            if edge.nick1 != query
        ]
    return render_template("search.html", query=query, neighbors=neighbors)


@bp.route("/path")
def path():
    """Поиск кратчайшего пути между двумя никами."""
    nick1 = request.args.get("nick1", "").strip()
    nick2 = request.args.get("nick2", "").strip()
    path_result = []
    if nick1 and nick2:
        path_result = find_path(nick1, nick2, max_depth=6)
    return render_template("path.html", nick1=nick1, nick2=nick2, path_result=path_result)


@bp.route("/stats")
def stats():
    """Статистика по графу."""
    all_edges = Edge.query.all()
    degree_map = defaultdict(int)
    for edge in all_edges:
        degree_map[edge.nick1] += 1
        degree_map[edge.nick2] += 1
    average_degree = round(sum(degree_map.values()) / len(degree_map), 2) if degree_map else 0
    diameter = longest_path_length(all_edges)
    random_edge = None
    if all_edges:
        random_edge = all_edges[0]
    return render_template("stats.html", degree_map=degree_map, average_degree=average_degree, diameter=diameter, random_edge=random_edge)


@bp.route("/visualize")
def visualize():
    """Страница визуализации графа."""
    edges = Edge.query.all()
    return render_template("visualize.html", edges=edges)


@bp.route("/report/<int:edge_id>", methods=["POST"])
@login_required
def report_edge(edge_id: int):
    """Заглушка для жалобы на ребро."""
    edge = Edge.query.get_or_404(edge_id)
    edge.is_reported = True
    db.session.commit()
    flash("Жалоба принята")
    return redirect(request.referrer or url_for("main.index"))


@bp.route("/import_csv", methods=["GET", "POST"])
@login_required
def import_csv():
    """Импорт связей из CSV."""
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Файл не выбран")
            return redirect(url_for("main.import_csv"))
        stream = io.StringIO(file.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        for row in reader:
            nick1 = (row.get("nick1") or "").strip()
            nick2 = (row.get("nick2") or "").strip()
            role = (row.get("role") or "").strip()
            if not nick1 or not nick2 or not role:
                continue
            edge = Edge(nick1=nick1, nick2=nick2, role=role, user_id=current_user.id, is_transitive=False)
            db.session.add(edge)
        db.session.commit()
        flash("CSV импортирован")
        return redirect(url_for("main.profile"))
    return render_template("import_csv.html")


def find_path(start: str, end: str, max_depth: int = 6) -> List[str]:
    """Поиск кратчайшего пути через BFS."""
    if start == end:
        return [start]
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        for edge in Edge.query.filter((Edge.nick1 == node) | (Edge.nick2 == node)).all():
            nxt = edge.nick2 if edge.nick1 == node else edge.nick1
            if nxt in seen:
                continue
            new_path = path + [nxt]
            if nxt == end:
                return new_path
            queue.append((nxt, new_path))
            seen.add(nxt)
    return []


def longest_path_length(edges: List[Edge]) -> int:
    """Простая оценка диаметра графа: максимум по степеням."""
    if not edges:
        return 0
    nodes = set()
    adjacency = defaultdict(list)
    for edge in edges:
        nodes.add(edge.nick1)
        nodes.add(edge.nick2)
        adjacency[edge.nick1].append(edge.nick2)
        adjacency[edge.nick2].append(edge.nick1)
    longest = 0
    for node in nodes:
        visited = set([node])
        stack = [(node, 0)]
        while stack:
            current, depth = stack.pop()
            longest = max(longest, depth)
            for nxt in adjacency[current]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append((nxt, depth + 1))
    return longest
