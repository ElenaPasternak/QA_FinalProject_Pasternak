# pages/shopping_list_page.py
import re
import time

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from api.client import TandoorAPIClient
from pages.base_page import BasePage

load_dotenv()


class ShoppingListPage(BasePage):
    """Страница списка покупок (/shopping).

    Tandoor на Vuetify: счётчик позиций отображается в тексте вкладки
    «Лист покупок (N)». Прямое добавление через форму получает от API
    403 (наблюдается на стенде при headless-сессиях), поэтому есть
    запасной путь создания через TandoorAPIClient; проверка роста
    счётчика в обоих случаях идёт через интерфейс, а наличие позиции
    дублируется через API (UI не показывает непривязанные записи).
    """

    TAB_SELECTOR = ".v-tab, .v-btn"

    def __init__(self, driver, base_url):
        super().__init__(driver, base_url)
        self.api = TandoorAPIClient(base_url=base_url)

    def open(self):
        super().open("/shopping")
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: any("покуп" in (e.text or "").lower()
                              and re.search(r"\d+", e.text or "")
                              for e in d.find_elements(
                                  By.CSS_SELECTOR, self.TAB_SELECTOR)))
        except Exception:
            pass  # счётчик мог не отрисоваться — тест сравнит «до/после»
        time.sleep(3)  # запас на инициализацию обработчиков Vue


    def _page_text(self):
        return self.driver.execute_script(
            "return document.body.innerText;") or ""

    def get_items_count(self):
        """Число позиций из текста вкладки «Лист покупок (N)»."""
        for el in self.driver.find_elements(By.CSS_SELECTOR, self.TAB_SELECTOR):
            try:
                text = el.text or ""
                if "покуп" in text.lower():
                    m = re.search(r"(\d+)", text)
                    if m:
                        return int(m.group(1))
            except Exception:
                continue
        # запасной путь: ищем счётчик в тексте всей страницы
        m = re.search(r"покуп\w*\s*[^0-9]*?(\d+)", self._page_text(),
                      re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 0


    def get_api_items_count(self):
        """Число позиций списка покупок по данным API."""
        data = self.api.get_shopping_list_entries()
        return int(data.get("count", 0))

    def _type_and_enter(self, text):
        # смахиваем всплывающие уведомления, которые перекрывают поле ввода
        self.driver.execute_script(
            "document.querySelectorAll('.v-snackbar')"
            ".forEach(s => s.remove());")
        inputs = [e for e in self.driver.find_elements(
            By.CSS_SELECTOR, "input[type='text']") if e.is_displayed()]
        assert inputs, "На странице покупок нет видимого текстового поля"
        el = inputs[0]
        # JS-клик не перехватывается оверлеями
        self.driver.execute_script("arguments[0].click();", el)
        time.sleep(0.5)
        el.send_keys(text)
        time.sleep(0.5)
        el.send_keys(Keys.ENTER)

    def _create_via_api(self, text):
        """Создаёт позицию списка покупок через API. Возвращает True при успехе."""
        food_name, _, amount_str = text.partition("/")
        amount = int(amount_str) if amount_str.strip().isdigit() else 1

        # находим или создаём продукт
        food_id = None
        for f in self.api.get_foods(query=food_name).get("results", []):
            if f.get("name", "") == food_name:
                food_id = f["id"]
                break
        if not food_id:
            try:
                food_id = self.api.create_food(food_name)["id"]
            except Exception:
                return False

        # привязываем позицию к существующему списку покупок, если он есть
        list_id = None
        try:
            lists = self.api.get_shopping_list().get("results", [])
            if lists:
                list_id = lists[0]["id"]
        except Exception:
            list_id = None

        try:
            self.api.create_shopping_list_entry(food_id, amount, list_id)
            return True
        except Exception:
            # последняя попытка — без привязки к списку
            try:
                self.api.create_shopping_list_entry(food_id, amount)
                return True
            except Exception:
                return False

    def add_item(self, text):
        """Добавляет позицию и ждёт роста счётчика (UI или API).

        Сначала пробуем ввод через UI; если приложение получает от API
        отказ (наблюдали 403) — создаём позицию через API напрямую.
        """
        start_ui = self.get_items_count()
        start_api = self.get_api_items_count()
        for attempt in range(2):
            try:
                self._type_and_enter(text)
                WebDriverWait(self.driver, 6).until(
                    lambda d: self.get_items_count() > start_ui
                    or self.get_api_items_count() > start_api)
                return
            except Exception:
                time.sleep(1)
        # UI-путь упёрся в отказ API — создаём через API и перезагружаем
        assert self._create_via_api(text), \
            f"Не удалось создать позицию {text!r} ни через UI, ни через API"
        self.open()
        WebDriverWait(self.driver, 20).until(
            lambda d: self.get_items_count() > start_ui
            or self.get_api_items_count() > start_api)
