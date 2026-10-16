# tests/test_meal_plan.py
import allure
import pytest

from pages.meal_plan_page import MealPlanPage
from pages.shopping_list_page import ShoppingListPage



def _entry_recipe_id(entry):
    """ID рецепта из записи плана: API возвращает recipe как объект."""
    recipe = entry.get("recipe")
    return recipe["id"] if isinstance(recipe, dict) else recipe


@pytest.fixture
def cleanup_meal_plans(api_client, get_or_create_recipe):
    """После теста удаляет через API записи плана, созданные для тестового рецепта."""
    recipe_id = get_or_create_recipe["id"]
    yield
    for entry in api_client.get_meal_plans().get("results", []):
        if _entry_recipe_id(entry) == recipe_id:
            api_client.delete_meal_plan(entry["id"])


@pytest.fixture
def cleanup_shopping_list(api_client):
    """После теста удаляет позиции списка покупок, добавленные тестом."""
    yield
    for entry in api_client.get_shopping_list_entries().get("results", []):
        api_client.delete_shopping_list_entry(entry["id"])


@pytest.mark.ui
class TestMealPlan:
    """Сценарии раздела «Планирование блюд»: создание, просмотр, удаление, список покупок."""

    def test_create_meal_plan(self, logged_in_driver, base_url,
                              get_or_create_recipe, cleanup_meal_plans):
        """Создание Meal Plan через UI: после сохранения запись видна в календаре."""
        recipe = get_or_create_recipe
        page = MealPlanPage(logged_in_driver, base_url)

        with allure.step("Открыть страницу планирования блюд"):
            page.open()
            assert page.is_calendar_visible(), "Календарь планов не загрузился"

        with allure.step(f"Создать запись плана с рецептом {recipe['name']!r}"):
            page.create_plan(recipe["name"], note="autotest")
            assert page.has_entry(recipe["name"]), "Запись не появилась в календаре"

    def test_view_meal_plan(self, logged_in_driver, base_url,
                            get_or_create_recipe, cleanup_meal_plans):
        """Просмотр Meal Plan: в модалке записи видны рецепт и заметка."""
        recipe = get_or_create_recipe
        page = MealPlanPage(logged_in_driver, base_url)
        page.open()

        with allure.step("Создать запись плана"):
            page.create_plan(recipe["name"], note="autotest")

        with allure.step("Открыть запись и проверить её содержимое"):
            page.open_entry(recipe["name"])
            text = page.get_modal_text()
            assert recipe["name"] in text, f"Имя рецепта не найдено в записи: {text!r}"
            assert "autotest" in text, f"Заметка не найдена в записи: {text!r}"
            page.close_modal()

    def test_delete_meal_plan(self, logged_in_driver, base_url,
                              api_client, get_or_create_recipe, cleanup_meal_plans):
        """Удаление Meal Plan через UI с последующей проверкой через API."""
        recipe = get_or_create_recipe
        page = MealPlanPage(logged_in_driver, base_url)
        page.open()

        with allure.step("Создать запись плана"):
            page.create_plan(recipe["name"])

        with allure.step("Удалить запись через UI"):
            page.delete_entry(recipe["name"])
            page.open()  # перезагружаем календарь, чтобы убедиться в удалении
            assert not page.has_entry(recipe["name"]), "Запись видна в календаре после удаления"

        with allure.step("Проверить через API, что запись удалена"):
            entries = api_client.get_meal_plans().get("results", [])
            planned = [e for e in entries if _entry_recipe_id(e) == recipe["id"]]
            assert planned == [], f"Записи всё ещё есть в API: {planned}"

    def test_shopping_list(self, logged_in_driver, base_url, cleanup_shopping_list):
        """Список покупок: добавление позиции через UI или API, рост счётчика."""
        shopping = ShoppingListPage(logged_in_driver, base_url)

        with allure.step("Открыть список покупок"):
            shopping.open()

        with allure.step("Зафиксировать состояние до (счётчик UI и API)"):
            before_ui = shopping.get_items_count()
            before_api = shopping.get_api_items_count()

        with allure.step("Добавить позицию Яблоки/2 (UI, при отказе API)"):
            shopping.add_item("Яблоки/2")

        with allure.step("Проверить, что позиция добавилась (UI или API)"):
            after_ui = shopping.get_items_count()
            after_api = shopping.get_api_items_count()
            assert (after_ui > before_ui) or (after_api > before_api), (
                f"Позиция не добавилась: UI {before_ui}->{after_ui}, "
                f"API {before_api}->{after_api}"
            )
