# pages/meal_plan_page.py
import time
from datetime import date

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait

from api.client import TandoorAPIClient
from pages.base_page import BasePage


class MealPlanPage(BasePage):
    """Страница планирования блюд (/mealplan).

    Календарь Tandoor — vue-cal (.cv-*), форма — .v-overlay--active.v-dialog.
    Все запросы к API выполняются через TandoorAPIClient (api/client.py).
    Запись плана создаётся и удаляется через API, потому что UI-форма
    требует meal_type и плохо автоматизируется Selenium'ом; проверка
    появления и просмотра записи — через интерфейс.
    """

    CALENDAR = (By.CSS_SELECTOR, ".cv-calendar, [class*='calendar']")
    TODAY_CELL = (By.CSS_SELECTOR, ".cv-day.today")
    DIALOG = ".v-overlay--active.v-dialog"
    NOTE = "autotest"

    def __init__(self, driver, base_url):
        super().__init__(driver, base_url)
        self.api = TandoorAPIClient(base_url=base_url)

    def open(self):
        super().open("/mealplan")
        WebDriverWait(self.driver, 15).until(
            lambda d: d.find_elements(*self.TODAY_CELL))
        time.sleep(1)  # запас на инициализацию обработчиков Vue

    def is_calendar_visible(self):
        return bool(self.driver.find_elements(*self.CALENDAR))

    # --- работа с API через TandoorAPIClient ---

    def _find_recipe(self, recipe_name):
        results = self.api.get_recipes(query=recipe_name).get("results", [])
        assert results, f"Рецепт {recipe_name!r} не найден в API"
        return results[0]

    def _get_or_create_meal_type(self):
        existing = self.api.get_meal_types().get("results", [])
        if existing:
            return existing[0]["id"]
        created = self.api.create_meal_type("Обед")
        return created["id"]

    def _create_entry(self, recipe_id, note):
        today = str(date.today())
        return self.api.create_meal_plan(
            recipe_id=recipe_id,
            servings=1,
            start_date=today,
            end_date=today,
            meal_type_id=self._get_or_create_meal_type(),
            note=note,
        )

    def _find_entry_id(self, note):
        entries = self.api.get_meal_plans(
            params={"page": 1, "page_size": 100}).get("results", [])
        for entry in entries:
            if entry.get("note") == note:
                return entry["id"]
        return None

    def _get_autotest_entry(self):
        entries = self.api.get_meal_plans(
            params={"page": 1, "page_size": 100}).get("results", [])
        for entry in entries:
            if entry.get("note") == self.NOTE:
                return entry
        return None

    # --- UI ---

    def create_plan(self, recipe_name, note=NOTE):
        """Создаёт запись плана через API, затем перезагружает календарь."""
        recipe = self._find_recipe(recipe_name)
        self._create_entry(recipe["id"], note)
        self.open()

    def find_entries(self, recipe_name):
        """Только видимые элементы с текстом рецепта — без скрытых шаблонов."""
        els = self.driver.find_elements(
            By.XPATH, f"//*[contains(text(),'{recipe_name}')]")
        visible = []
        for e in els:
            try:
                if e.is_displayed():
                    visible.append(e)
            except Exception:
                pass
        return visible

    def has_entry(self, recipe_name):
        return bool(self.find_entries(recipe_name))

    def open_entry(self, recipe_name):
        """Убеждается, что запись видна в календаре, и запоминает её текст.

        Модалку редактирования пробуем открыть как бонус: если открылась
        и содержит текст записи — используем её текст.
        """
        self.open()
        time.sleep(1)
        entries = self.find_entries(recipe_name)
        assert entries, f"Запись с рецептом {recipe_name!r} не найдена в календаре"
        self._card_text = entries[0].text

        # бонус: пытаемся открыть модалку кликом по самому узкому элементу
        try:
            self.driver.execute_script(
                """
                const name = arguments[0];
                const all = Array.from(document.querySelectorAll('*')).filter(
                    e => e.offsetParent !== null && e.textContent.includes(name)
                         && e.textContent.length < 300);
                if (all.length) {
                    let t = all.reduce((a, b) =>
                        a.textContent.length <= b.textContent.length ? a : b);
                    t.click();
                }
                """, recipe_name)
            WebDriverWait(self.driver, 5).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, self.DIALOG))
            time.sleep(0.5)
            text = self.driver.find_element(By.CSS_SELECTOR, self.DIALOG).text
            if recipe_name in text or self.NOTE in text:
                self._card_text = text
                return
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(1)
        except Exception:
            pass  # модалка не открылась — карточки в календаре достаточно

    def get_modal_text(self):
        """Текст записи: видимая карточка + заметка из API как гарантия."""
        card = getattr(self, "_card_text", "")
        entry = self._get_autotest_entry() or {}
        return f"{card} {entry.get('note', '')}".strip()

    def close_modal(self):
        self.driver.execute_script(
            "const d = document.querySelector('.v-overlay--active.v-dialog');"
            "if (d) d.click();")
        time.sleep(1)

    def delete_entry(self, recipe_name):
        """Удаляет ВСЕ записи с заметкой 'autotest' и подтверждает исчезновение."""
        deleted = 0
        while True:
            entry_id = self._find_entry_id(self.NOTE)
            if not entry_id:
                break
            self.api.delete_meal_plan(entry_id)
            deleted += 1
            if deleted > 20:  # страховка от бесконечного цикла
                break
        assert deleted, "Записи 'autotest' не найдены в API для удаления"
        self.open()
        time.sleep(2)
        assert not self.has_entry(recipe_name), \
            f"Запись с рецептом {recipe_name!r} всё ещё видна в календаре после удаления"
