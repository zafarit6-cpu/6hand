import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
instance_dir = os.path.join(basedir, "instance")
os.makedirs(instance_dir, exist_ok=True)

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"


def create_app():
    """Создаёт и настраивает Flask-приложение."""
    app = Flask(__name__, instance_path=instance_dir)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(instance_dir, 'graph.db')}",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_ENABLED"] = True

    db.init_app(app)
    login_manager.init_app(app)

    from . import models
    from .routes import bp

    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        ensure_schema(app)

    return app


def ensure_schema(app: Flask) -> None:
    """Поддерживает совместимость со старой SQLite-базой после обновления модели."""
    with app.app_context():
        inspector = inspect(db.engine)
        if "edge" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("edge")}
        if "avatar_url" not in columns:
            db.session.execute(db.text("ALTER TABLE edge ADD COLUMN avatar_url VARCHAR(255)"))
            db.session.commit()
