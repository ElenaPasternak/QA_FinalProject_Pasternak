import json
import os

import allure
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from api.client import TandoorAPIClient
from pages.login_page import LoginPage

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_URL = os.getenv("BASE_URL", "https://tandoor.vs1.srv.eduson.tv").rstrip("/")
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "imported_recipes.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
COOKIES_FILE = os.path.join(os.path.dirname(__file__), ".session_cookies.json")


@pytest.fixture(scope="session")
def api_client():
    """Возвращает экземпляр API-клиента для всех тестов сессии."""
    return TandoorAPIClient()


@pytest.fixture(scope="session")
def base_url():
    """Базовый адрес тестируемого Tandoor."""
    return BASE_URL


@pytest.fixture(scope="session")
def test_data():
    """Загружает тестовые данные из data/imported_recipes.json."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["recipes"]


@pytest.fixture
def get_or_create_recipe(api_client, test_data):
    """Возвращает существующий рецепт, а если рецептов нет — создаёт новый.

    Валидный рецепт гарантирован даже на чистой учётке."""
    recipes = api_client.get_recipes().get("results", [])
    if recipes:
        yield recipes[0]
        return

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
    """Запускает браузер: локальный headless Chrome или удалённый Selenium в CI."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    # обязательные флаги для запуска Chrome в docker-контейнере CI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    selenium_url = os.getenv("SELENIUM_URL")
    if selenium_url:
        # в GitLab CI подключаемся к контейнеру Selenium по переменной окружения
        driver = webdriver.Remote(command_executor=selenium_url, options=options)
    else:
        # локально — собственный Chrome с уже установленным драйвером
        driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()



@pytest.fixture
def logged_in_driver(driver):
    """Браузер с выполнённой авторизацией.
    Cookies сохраняются в файл и переиспользуются, чтобы не логиниться каждый раз."""
    page = LoginPage(driver, BASE_URL)

    # пробуем восстановить сессию из сохранённых cookies
    if os.path.exists(COOKIES_FILE):
        page.open("/")
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass  # просроченные или некорректные cookie пропускаем
        driver.refresh()
        if not page.is_login_form_visible():
            yield driver
            return

    # cookies нет или они просрочены — входим через форму
    page.open("/user/login")
    page.login(os.environ["TANDOOR_USERNAME"], os.environ["TANDOOR_PASSWORD"])
    assert not page.is_login_form_visible(), (
        "Не удалось авторизоваться: проверь TANDOOR_USERNAME и TANDOOR_PASSWORD в .env"
    )
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(driver.get_cookies(), f)
    yield driver


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
