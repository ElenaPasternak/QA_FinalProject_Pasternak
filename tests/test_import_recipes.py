import json
import os

import pytest

from api.client import TandoorAPIClient


DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "recipe_urls.json")


def load_urls():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["recipes"]


@pytest.fixture(scope="session")
def api_client():
    return TandoorAPIClient()


@pytest.mark.api
def test_import_recipe(api_client):
    """Импорт одного рецепта по ссылке завершается успехом."""
    urls = load_urls()
    assert urls, "В data/recipe_urls.json нет ни одной ссылки"

    url = urls[0]
    result = api_client.import_recipe_by_url(url)
    assert result is not None
    assert result.get("id"), f"У рецепта нет id: {result}"
    print(f"Импортирован рецепт: id={result['id']}, name={result.get('name')}")

