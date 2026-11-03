# pages/meal_plan_page.py
import time
from datetime import date

import allure
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from api.client import TandoorAPIClient
from pages.base_page import BasePage


class MealPlanPage(BasePage):
    """Страница планирования блюд (/mealplan).

    Календарь Tandoor — vue-cal (.cv-*), форма создания записи —
    Vuetify-диалог (.v-dialog.v-overlay--active .v-overlay__content),
    поля рецепта и типа питания — кастомный компонент multiselect
    (input.multiselect-search). Все запросы к API выполняются через
    TandoorAPIClient (api/client.py). Создание записи плана: сначала
    пробуем UI-форму, при неудаче — API. Проверка появления и просмотра
    записи — через интерфейс.
    """

    CALENDAR = (By.CSS_SELECTOR, ".cv-calendar, [class*='calendar']")
    TODAY_CELL = (By.CSS_SELECTOR, ".cv-day.today")
    # активный (видимый) Vuetify-диалог: v-overlay--active отличает
    # открытую форму от скрытого контейнера, который Vuetify держит в DOM
    DIALOG = ".v-dialog.v-overlay--active .v-overlay__content"
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

    def _close_dialog_with_escape(self):
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass

    def _attach_ui_failure(self, exc):
        """Прикладывает к отчёту скриншот и текст исключения —
        чтобы по отчёту было видно, на каком шаге оборвалась UI-ветка."""
        try:
            allure.attach(self.driver.get_screenshot_as_png(),
                          name="Провал UI-ветки",
                          attachment_type=allure.attachment_type.PNG)
            if exc is not None:
                allure.attach(f"{type(exc).__name__}: {exc}",
                              name="Ошибка UI-ветки",
                              attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass

    def _open_create_dialog(self):
        """Открывает форму создания записи кликом по ячейке сегодня.

        Обычный клик, при сбое — JS-клик; до 3 попыток, т.к. в headless
        обработчик Vue может не успеть навеситься к моменту первого клика.
        Возвращает True, если диалог стал видимым.
        """
        for attempt in range(3):
            try:
                cell = self.driver.find_element(*self.TODAY_CELL)
                try:
                    cell.click()
                except Exception:
                    self.driver.execute_script(
                        "arguments[0].click();", cell)
                WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, f"{self.DIALOG} .v-card")))
                return True
            except TimeoutException:
                continue
        allure.attach(self.driver.get_screenshot_as_png(),
                      name="Клик не открыл форму",
                      attachment_type=allure.attachment_type.PNG)
        return False

    def _select_first_multiselect_option(self, recipe_name):
        """Кликает по первому видимому варианту выпадающего списка,
        содержащему recipe_name. Опции multiselect могут рендериться
        вне диалога, поэтому ищем по всему документу; клик по опции
        при перехвате подложкой выполняем через JS."""
        candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(@class,'multiselect-option') or "
            "contains(@class,'v-list-item')]"
            f"[contains(., '{recipe_name}')]")
        for option in candidates:
            try:
                if option.is_displayed():
                    try:
                        option.click()
                    except Exception:
                        self.driver.execute_script(
                            "arguments[0].click();", option)
                    return True
            except Exception:
                continue
        return False

    def _dialog_contains(self, text):
        """Проверяет, что текст присутствует в открытом диалоге."""
        try:
            dialog = self.driver.find_element(
                By.CSS_SELECTOR, self.DIALOG)
            return text in dialog.text
        except Exception:
            return False

    def _select_first_meal_type(self):
        """Выбирает первый вариант в поле «Тип питания».

        Tandoor не сохраняет запись без типа питания: без него сервер
        возвращает 400 meal_type: Обязательное поле. Поле — второй
        input.multiselect-search в диалоге (первый — рецепт).

        Имя опции берём из API и ищем её по точному тексту, а не по
        CSS-классам: контейнеры выпадающих списков различаются между
        версиями Vuetify. После клика проверяем, что текст опции
        появился в диалоге. Возвращает True, если вариант выбран
        и применён.
        """
        try:
            fields = [f for f in self.driver.find_elements(
                By.CSS_SELECTOR, f"{self.DIALOG} input.multiselect-search")
                if f.is_displayed()]
        except Exception as e:
            allure.attach(f"{type(e).__name__}: {e}",
                          name="Ошибка при выборе типа питания",
                          attachment_type=allure.attachment_type.TEXT)
            return False

        if not fields:
            allure.attach("Не найдено ни одного видимого multiselect-поля",
                          name="Ошибка при выборе типа питания",
                          attachment_type=allure.attachment_type.TEXT)
            return False

        # имя первого типа питания берём из API — по нему и ищем опцию
        types = self.api.get_meal_types().get("results", [])
        if types:
            type_name = types[0]["name"]
        else:
            type_name = self.api.create_meal_type("Обед").get("name", "Обед")

        # второй multiselect — тип питания; если поле рецепта не найдено
        # (не должно случиться на этом шаге), берём единственный доступный
        field = fields[1] if len(fields) > 1 else fields[0]
        field.click()
        time.sleep(0.5)  # ждём рендер выпадающего списка

        # сначала ищем опцию среди элементов списков и ролей option,
        # затем — по всему документу (контейнер списка заранее неизвестен)
        candidates = self.driver.find_elements(
            By.XPATH,
            "//*[contains(@class,'v-list-item') or "
            "contains(@class,'multiselect__option') or "
            "contains(@class,'multiselect-option') or @role='option']"
            f"[normalize-space(text())='{type_name}']")
        if not candidates:
            candidates = self.driver.find_elements(
                By.XPATH, f"//*[normalize-space(text())='{type_name}']")

        for option in candidates:
            try:
                if not option.is_displayed():
                    continue
                try:
                    # клик может перехватить подложка v-overlay__scrim
                    option.click()
                except Exception:
                    # JS-клик игнорирует перекрытия элементов
                    self.driver.execute_script(
                        "arguments[0].click();", option)

                # проверяем, что выбор применился: текст опции должен
                # появиться в диалоге
                try:
                    WebDriverWait(self.driver, 3).until(
                        lambda d: self._dialog_contains(type_name))
                    return True
                except TimeoutException:
                    allure.attach(
                        f"Клик по опции {type_name!r} не применился",
                        name="Ошибка при выборе типа питания",
                        attachment_type=allure.attachment_type.TEXT)
                    return False
            except Exception:
                continue

        allure.attach(self.driver.get_screenshot_as_png(),
                      name="Опция типа питания не найдена",
                      attachment_type=allure.attachment_type.PNG)
        return False

    def _fill_servings(self, servings):
        """Заполняет поле «Порции». Пробуем несколько селекторов:
        сначала числовой input, затем поле с лейблом «Порции»."""
        selectors = [
            ".v-dialog input[type='number']",
            "//label[contains(., 'Порции')]/following::input[1]",
            "//span[contains(., 'Порции')]/following::input[1]",
        ]
        for selector in selectors:
            try:
                by = (By.XPATH if selector.startswith("//")
                      else By.CSS_SELECTOR)
                field = self.driver.find_element(by, selector)
                field.clear()
                field.send_keys(str(servings))
                return True
            except Exception:
                continue
        return False

    def create_plan_via_ui(self, recipe_name, servings=1, note=NOTE):
        """Пытается создать запись плана через UI-форму.

        Открывает форму кликом по ячейке сегодняшнего дня, заполняет
        рецепт, тип питания, порции и заметку, сохраняет. Сохранение
        считается успешным только если форма закрылась: при ошибке
        валидации Tandoor оставляет диалог открытым. Возвращает True,
        если запись создана через интерфейс, False — если форма не
        поддалась (тогда вызывающий код создаст план через API).
        """
        with allure.step("Пытаемся создать запись через UI-форму"):
            try:
                if not self._open_create_dialog():
                    raise TimeoutException(
                        "Клик по ячейке дня не открыл форму за 3 попытки")

                # поле рецепта — input.multiselect-search внутри активного
                # диалога; ждём видимость
                recipe_input = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR,
                         f"{self.DIALOG} input.multiselect-search")))
                recipe_input.click()
                recipe_input.send_keys(recipe_name)
                time.sleep(1)  # ждём загрузку вариантов выпадающего списка

                if not self._select_first_multiselect_option(recipe_name):
                    allure.attach("Выпадающий список рецептов не дал "
                                  "видимого варианта",
                                  name="Ошибка UI-ветки",
                                  attachment_type=allure.attachment_type.TEXT)
                    raise RuntimeError(
                        "multiselect не дал видимого варианта рецепта")

                # тип питания обязателен: без него сервер возвращает
                # 400 meal_type: Обязательное поле
                if not self._select_first_meal_type():
                    raise RuntimeError("Не удалось выбрать тип питания")

                # поле порций: селектор подбирается из списка кандидатов;
                # если не нашлось ни одного — продолжаем со значением
                # по умолчанию
                self._fill_servings(servings)

                # заметка: в форме один textarea — ищем по тегу внутри
                # диалога; вариант с placeholder оставляем как резерв,
                # т.к. Vuetify может рендерить лейбл отдельным элементом,
                # а не атрибутом placeholder
                try:
                    note_area = self.driver.find_element(
                        By.CSS_SELECTOR, f"{self.DIALOG} textarea")
                except Exception:
                    note_area = self.driver.find_element(
                        By.CSS_SELECTOR,
                        f"{self.DIALOG} textarea[placeholder*='аметка']")
                note_area.click()
                note_area.send_keys(note)

                # кнопка сохранения: в этом Tandoor она называется
                # «Создать» (Create); на всякий случай держим и другие
                # варианты текста
                save_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        ".//button[contains(@class,'v-btn') and ("
                        "contains(., 'Создать') or contains(., 'Добавить') "
                        "or contains(., 'Сохранить') or contains(., 'Create') "
                        "or contains(., 'Save'))]")))
                save_button.click()

                # сохранение считаем успешным только если форма закрылась:
                # при ошибке валидации Tandoor оставляет диалог открытым
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.invisibility_of_element_located(
                            (By.CSS_SELECTOR, self.DIALOG)))
                except TimeoutException:
                    allure.attach(
                        self.driver.get_screenshot_as_png(),
                        name="Форма не закрылась после «Создать»",
                        attachment_type=allure.attachment_type.PNG)
                    raise RuntimeError(
                        "Форма не закрылась после нажатия «Создать» — "
                        "сохранение не выполнено (проверь обязательные поля)")

                time.sleep(1)
                if not self.has_entry(recipe_name):
                    raise RuntimeError(
                        "Форма закрылась, но запись не появилась в календаре")
                allure.attach("Запись создана через UI-форму",
                              name="Путь создания",
                              attachment_type=allure.attachment_type.TEXT)
                return True
            except Exception as e:
                self._attach_ui_failure(e)
                self._close_dialog_with_escape()
                return False

    def create_plan(self, recipe_name, note=NOTE):
        """Создаёт запись плана: сначала через UI-форму, при неудаче — через API."""
        if self.create_plan_via_ui(recipe_name, note=note):
            return
        allure.attach(
            "Форма не поддалась — запись создана через API",
            name="Путь создания",
            attachment_type=allure.attachment_type.TEXT)
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
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, f"{self.DIALOG} .v-card")))
            time.sleep(0.5)
            text = self.driver.find_element(
                By.CSS_SELECTOR, self.DIALOG).text
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
            "const d = document.querySelector('.v-dialog .v-overlay__content');"
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
