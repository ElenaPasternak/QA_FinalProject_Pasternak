import json
import os

import pytest

from api.client import TandoorAPIClient

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "imported_recipes.json")


@pytest.fixture(scope="session")
def api_client():
    """Возвращает экземпляр API-клиента для всех тестов сессии."""
    return TandoorAPIClient()


@pytest.fixture(scope="session")
def test_data():
    """Загружает тестовые данные из data/imported_recipes.json."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["recipes"]


@pytest.fixture(scope="session")
def existing_recipe(api_client, test_data):
    """Возвращает существующий рецепт, а если рецептов нет — создаёт новый."""
    recipes = api_client.get_recipes().get("results", [])
    if recipes:
        return recipes[0]

    created = api_client.create_recipe(
        {
            "name": "Fixture Recipe",
            "description": "created by conftest fixture",
            "steps": [
                {"instruction": "Mix ingredients", "time": 5, "ingredients": [], "subrecipes": []}
            ],
        }
    )
    yield created
    api_client.delete_recipe(created["id"])
