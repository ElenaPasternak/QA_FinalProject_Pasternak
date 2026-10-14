import json
import os

import allure
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from api.client import TandoorAPIClient

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "imported_recipes.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


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


@pytest.fixture
def driver():
    """Запускает Chrome для одного UI-теста и закрывает его после."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """При падении теста сохраняет скриншот и прикрепляет его к Allure-отчёту."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        driver = item.funcargs.get("driver")
        if driver is None:
            return
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        filename = f"{item.name}.png"
        path = os.path.join(SCREENSHOTS_DIR, filename)
        driver.save_screenshot(path)
        with open(path, "rb") as f:
            allure.attach(
                f.read(),
                name=filename,
                attachment_type=allure.attachment_type.PNG,
            )
        print(f"Скриншот падения сохранён: {path}")
