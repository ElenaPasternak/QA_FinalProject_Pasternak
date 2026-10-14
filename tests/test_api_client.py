import pytest

from api.client import TandoorAPIClient

pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def client():
    return TandoorAPIClient()


def test_connection(client):
    """Соединение с API устанавливается успешно."""
    recipes = client.get_recipes()
    assert isinstance(recipes, dict)
    assert "results" in recipes


def test_get_recipes_returns_results(client):
    """Список рецептов содержит поле results, а внутри — рецепты с id и name."""
    recipes = client.get_recipes()
    assert isinstance(recipes["results"], list)
    if recipes["results"]:
        first = recipes["results"][0]
        assert "id" in first
        assert "name" in first


def test_create_and_delete_recipe(client):
    """Рецепт создаётся через API, возвращает корректные данные
    и удаляется без остатка."""
    payload = {
        "name": "API Test Recipe",
        "description": "temporary test recipe",
        "steps": [{"instruction": "Mix ingredients", "time": 5, "ingredients": [], "subrecipes": []}],

    }

    created = client.create_recipe(payload)
    recipe_id = created["id"]
    try:
        assert created["name"] == "API Test Recipe"

        # Рецепт доступен в общем списке
        recipes = client.get_recipes(query="API Test Recipe")
        names = [r["name"] for r in recipes.get("results", [])]
        assert "API Test Recipe" in names
    finally:
        # Удаляем в любом случае — даже если проверки выше упали
        client.delete_recipe(recipe_id)

    # После удаления рецепт больше не возвращается
    recipes = client.get_recipes(query="API Test Recipe")
    names = [r["name"] for r in recipes.get("results", [])]
    assert "API Test Recipe" not in names


def test_get_recipe_by_id(client):
    """Получение рецепта по ID возвращает его данные."""
    recipes = client.get_recipes()
    results = recipes.get("results", [])
    assert results, "В аккаунте нет рецептов для проверки"
    recipe = client.get_recipe(results[0]["id"])
    assert recipe["id"] == results[0]["id"]
    assert recipe["name"] == results[0]["name"]


def test_error_handling(client):
    """Запрос несуществующего рецепта вызывает ошибку, а не молчит."""
    with pytest.raises(Exception):
        client.get_recipe(99999999)
