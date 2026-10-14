# pages/login_page.py
from selenium.webdriver.common.by import By

from pages.base_page import BasePage


class LoginPage(BasePage):
    """Страница авторизации Tandoor."""

    USERNAME_INPUT = (By.ID, "id_username")
    PASSWORD_INPUT = (By.ID, "id_password")
    SUBMIT_BUTTON = (By.CSS_SELECTOR, "button[type='submit']")

    def open(self):
        super().open("/user/login")

    def login(self, username, password):
        self.wait_for(self.USERNAME_INPUT).send_keys(username)
        self.driver.find_element(*self.PASSWORD_INPUT).send_keys(password)
        self.driver.find_element(*self.SUBMIT_BUTTON).click()

    def is_login_form_visible(self):
        """True, если на странице видна форма входа (значит, мы ещё не авторизованы)."""
        return len(self.driver.find_elements(*self.USERNAME_INPUT)) > 0
