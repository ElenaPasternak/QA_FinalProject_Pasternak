# pages/header_component.py
from selenium.webdriver.common.by import By

from pages.base_page import BasePage


class HeaderComponent(BasePage):
    """Верхняя панель навигации Tandoor."""

    NAV_MEAL_PLAN = (By.CSS_SELECTOR, "a[href*='meal-plan']")
    NAV_SHOPPING_LIST = (By.CSS_SELECTOR, "a[href*='shopping-list']")
    USER_MENU = (By.CSS_SELECTOR, ".dropdown-toggle, [data-testid='user-menu']")

    def go_to_meal_plan(self):
        """Переходит в раздел планов питания."""
        self.wait_for(self.NAV_MEAL_PLAN).click()

    def go_to_shopping_list(self):
        """Переходит в раздел списка покупок."""
        self.wait_for(self.NAV_SHOPPING_LIST).click()

    def is_logged_in(self):
        """Проверяет, что пользователь авторизован (виден элемент меню пользователя)."""
        elements = self.driver.find_elements(*self.USER_MENU)
        return len(elements) > 0

    def get_username(self):
        """Возвращает имя пользователя из меню или None, если не авторизован."""
        menu = self.driver.find_element(*self.USER_MENU)
        text = menu.text.strip()
        return text if text else None
