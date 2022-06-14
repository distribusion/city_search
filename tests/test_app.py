"""
Example unit tests file
"""
import os

from fastapi.testclient import TestClient

from city_search.main import app

os.environ["TEST_ENV_VAR"] = "123"


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_index() -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_say_hello() -> None:
    response = client.get("/say_hello", params={"name": "World"})
    assert response.status_code == 200
