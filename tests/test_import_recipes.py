import json
import os

import allure
import pytest



DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "recipe_urls.json")


def load_urls():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["recipes"]



@pytest.mark.api
def test_import_recipe(api_client):
    """Импорт одного рецепта по ссылке завершается успехом."""
    with allure.step("Загрузить список ссылок из data/recipe_urls.json"):
        urls = load_urls()
        assert urls, "В data/recipe_urls.json нет ни одной ссылки"

    url = urls[0]
    with allure.step(f"Импортировать рецепт по ссылке {url!r}"):
        result = api_client.import_recipe_by_url(url)
        assert result is not None
        assert result.get("id"), f"У рецепта нет id: {result}"

    with allure.step("Зафиксировать результат импорта"):
        print(f"Импортирован рецепт: id={result['id']}, name={result.get('name')}")
