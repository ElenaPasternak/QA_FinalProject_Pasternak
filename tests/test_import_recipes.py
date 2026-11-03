import json
import os

import allure
import pytest

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "recipe_urls.json")


def load_urls():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["recipes"]


def norm(name):
    return " ".join(name.split()).casefold()


@pytest.mark.api
def test_import_recipe(api_client):
    """Импорт одного рецепта по ссылке завершается успехом.

    Если рецепт с таким названием уже есть в Tandoor,
    повторный импорт не выполняется — тест не создаёт дубликатов."""
    with allure.step("Загрузить список ссылок из data/recipe_urls.json"):
        urls = load_urls()
        assert urls, "В data/recipe_urls.json нет ни одной ссылки"

    url = urls[0]

    with allure.step("Разобрать рецепт по ссылке и получить его название"):
        scraped = api_client.scrape_recipe_from_url(url)
        scraped = scraped.get("recipe", scraped) if isinstance(scraped, dict) else {}
        name = (scraped.get("name") or "").strip()
        assert name, f"Не удалось извлечь название рецепта из {url}"

    with allure.step(f"Проверить, есть ли рецепт {name!r} в Tandoor"):
        existing = [
            r for r in api_client.get_recipes(query=name).get("results", [])
            if norm(r["name"]) == norm(name)
        ]

    if existing:
        with allure.step(f"Рецепт уже существует (id={existing[0]['id']}) — импорт не нужен"):
            print(f"SKIP: рецепт {name!r} уже существует, id={existing[0]['id']}")
            return

    with allure.step(f"Импортировать рецепт по ссылке {url!r}"):
        result = api_client.import_recipe_by_url(url)
        assert result is not None
        assert result.get("id"), f"У рецепта нет id: {result}"

    with allure.step("Зафиксировать результат импорта"):
        print(f"Импортирован рецепт: id={result['id']}, name={result.get('name')}")
