from __future__ import annotations

import bcrypt
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from . import db, login_manager


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """Пользователь приложения."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    discord_tag = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    edges_added = db.Column(db.Integer, default=0)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))


class Edge(db.Model):
    """Связь между двумя никами."""

    id = db.Column(db.Integer, primary_key=True)
    nick1 = db.Column(db.String(80), nullable=False)
    nick2 = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_transitive = db.Column(db.Boolean, default=False, nullable=False)
    is_reported = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (
        UniqueConstraint("nick1", "nick2", "role", name="uq_edge_pair_role"),
    )

    user = db.relationship("User", backref=db.backref("edges", lazy=True))
