# pages/login_page.py
from selenium.webdriver.common.by import By

from pages.base_page import BasePage


class LoginPage(BasePage):
    """Страница авторизации Tandoor (allauth: /accounts/login/)."""

    USERNAME_INPUT = (By.ID, "id_login")
    PASSWORD_INPUT = (By.ID, "id_password")
    SUBMIT_BUTTON = (By.CSS_SELECTOR, "button[type='submit']")

    def open(self, path="/accounts/login/"):
        super().open(path)


    def login(self, username, password):
        self.fill(self.USERNAME_INPUT, username)
        self.fill(self.PASSWORD_INPUT, password)
        self.click(self.SUBMIT_BUTTON)


    def is_login_form_visible(self):
        """True, если на странице видна форма входа (значит, мы ещё не авторизованы)."""
        return len(self.driver.find_elements(*self.USERNAME_INPUT)) > 0
