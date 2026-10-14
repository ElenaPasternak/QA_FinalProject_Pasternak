# pages/recipes_page.py
from selenium.webdriver.common.by import By

from pages.base_page import BasePage


class RecipesPage(BasePage):
    """Страница списка рецептов."""

    RECIPE_CARDS = (By.CSS_SELECTOR, ".card")

    def open(self):
        super().open("/list")

    def get_recipe_titles(self):
        """Возвращает список названий рецептов на странице."""
        cards = self.driver.find_elements(*self.RECIPE_CARDS)
        return [c.text for c in cards]
