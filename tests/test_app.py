import os

import pytest

from app import create_app, db


@pytest.fixture()
def client():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        with app.app_context():
            db.drop_all()
            db.create_all()
        yield client


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Revolve 6 Hand" in body
