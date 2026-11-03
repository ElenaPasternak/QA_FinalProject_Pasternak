import os

import requests
from dotenv import load_dotenv

load_dotenv()


class TandoorAPIClient:
    """Клиент для работы с API Tandoor: рецепты, планы питания, список покупок."""

    def __init__(self, base_url=None, token=None):
        self.base_url = (base_url or os.getenv("BASE_URL", "")).rstrip("/")
        self.token = token or os.getenv("TANDOOR_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _make_request(self, method, endpoint, json=None, params=None):
        """Выполняет HTTP-запрос к API с обработкой ошибок."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(
                method, url, headers=self.headers, json=json, params=params, timeout=30
            )
            response.raise_for_status()
            return response
        except requests.HTTPError:
            # Ошибки API (4xx/5xx) пробрасываем как есть — тесты проверяют статусы
            raise
        except requests.ConnectionError as e:
            raise ConnectionError(f"Не удалось подключиться к {url}: {e}") from e
        except requests.Timeout as e:
            raise TimeoutError(f"Превышено время ожидания запроса {url}: {e}") from e
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка запроса к {url}: {e}") from e


    # ---------- Рецепты ----------

    def scrape_recipe_from_url(self, url):
        """Скачивает и разбирает рецепт с внешнего сайта (POST /api/recipe-from-source/)."""
        response = self._make_request("POST", "/api/recipe-from-source/", json={"url": url})
        data = response.json()
        # Tandoor может вернуть список рецептов — берём первый
        if isinstance(data, list):
            data = data[0] if data else {}
        return data

    def import_recipe_by_url(self, url):
        """Импортирует рецепт по ссылке: разбирает сайт и сохраняет рецепт в Tandoor."""
        data = self.scrape_recipe_from_url(url)
        # Tandoor возвращает {"recipe": {...}, "images": [...], ...} — рецепт внутри ключа "recipe"
        scraped = data.get("recipe", data) if isinstance(data, dict) else {}
        if not scraped or not scraped.get("name"):
            raise ValueError(f"Не удалось извлечь рецепт из {url}")
        response = self._make_request("POST", "/api/recipe/", json=scraped)
        return response.json()

    def get_recipes(self, query=None):
        """Возвращает список всех рецептов (GET /api/recipe/)."""
        params = {"query": query} if query else None
        response = self._make_request("GET", "/api/recipe/", params=params)
        return response.json()

    def delete_recipe(self, recipe_id):
        """Удаляет рецепт по ID (DELETE /api/recipe/{id}/)."""
        self._make_request("DELETE", f"/api/recipe/{recipe_id}/")
        return True

    def create_recipe(self, payload):
        """Создает рецепт вручную (POST /api/recipe/)."""
        response = self._make_request("POST", "/api/recipe/", json=payload)
        return response.json()

    def get_recipe(self, recipe_id):
        """Получает рецепт по ID (GET /api/recipe/{id}/)."""
        response = self._make_request("GET", f"/api/recipe/{recipe_id}/")
        return response.json()

    # ---------- Планы питания ----------

    def create_meal_plan(self, recipe_id, servings, start_date, end_date,
                         meal_type_id=None, note=None):
        """Создает план питания (POST /api/meal-plan/).

        Даты передаются в API как from_date/to_date — так эти поля
        называются в Tandoor; параметры метода оставлены читаемыми.
        Если тип питания не задан, берётся первый существующий в аккаунте.
        """
        if meal_type_id is None:
            types = self.get_meal_types().get("results", [])
            if not types:
                raise RuntimeError(
                    "В аккаунте нет ни одного типа питания — создайте его в UI")
            meal_type_id = types[0]["id"]
        payload = {
            "recipe": recipe_id,
            "servings": servings,
            "from_date": start_date,
            "to_date": end_date,
            "meal_type": meal_type_id,
        }
        if note:
            payload["note"] = note
        response = self._make_request("POST", "/api/meal-plan/", json=payload)
        return response.json()

    def get_meal_plan(self, plan_id):
        """Получает план питания по ID (GET /api/meal-plan/{id}/)."""
        response = self._make_request("GET", f"/api/meal-plan/{plan_id}/")
        return response.json()

    def delete_meal_plan(self, plan_id):
        """Удаляет план питания (DELETE /api/meal-plan/{id}/)."""
        self._make_request("DELETE", f"/api/meal-plan/{plan_id}/")
        return True

    def get_meal_plans(self, params=None):
        """GET /api/meal-plan/ — список записей плана питания."""
        response = self._make_request("GET", "/api/meal-plan/", params=params)
        return response.json()

    def get_meal_types(self):
        """GET /api/meal-type/ — типы питания."""
        response = self._make_request("GET", "/api/meal-type/")
        return response.json()

    def create_meal_type(self, name, order=0):
        """POST /api/meal-type/ — создаёт тип питания, возвращает его данные.

        Tandoor на разных сборках принимает разный набор полей,
        поэтому пробуем payload по убыванию полноты."""
        payloads = ({"name": name, "order": order, "icon": ""},
                    {"name": name, "order": order},
                    {"name": name})
        last_error = None
        for payload in payloads:
            try:
                response = self._make_request("POST", "/api/meal-type/", json=payload)
                return response.json()
            except RuntimeError as e:
                last_error = e
        raise RuntimeError(f"Не удалось создать тип питания: {last_error}")

    # ---------- Список покупок ----------

    def get_shopping_list(self):
        """Получает список покупок (GET /api/shopping-list/)."""
        response = self._make_request("GET", "/api/shopping-list/")
        return response.json()

    def get_shopping_list_entries(self):
        """GET /api/shopping-list-entry/ — позиции списка покупок."""
        response = self._make_request("GET", "/api/shopping-list-entry/")
        return response.json()

    def delete_shopping_list_entry(self, entry_id):
        """DELETE /api/shopping-list-entry/{id}/ — удаляет позицию списка."""
        self._make_request("DELETE", f"/api/shopping-list-entry/{entry_id}/")
        return True

    def get_foods(self, query=None):
        """GET /api/food/ — поиск продуктов."""
        params = {"query": query} if query else None
        response = self._make_request("GET", "/api/food/", params=params)
        return response.json()

    def create_food(self, name):
        """POST /api/food/ — создаёт продукт, возвращает его данные."""
        response = self._make_request("POST", "/api/food/", json={"name": name})
        return response.json()

    def create_shopping_list_entry(self, food_id, amount=1, list_id=None):
        """POST /api/shopping-list-entry/ — добавляет позицию списка покупок."""
        payload = {"food": food_id, "amount": amount}
        if list_id:
            payload["shopping_lists"] = [list_id]
        response = self._make_request("POST", "/api/shopping-list-entry/", json=payload)
        return response.json()

    # ---------- Проверка соединения ----------

    def test_connection(self):
        """Проверяет соединение с API, запрашивая список рецептов."""
        recipes = self.get_recipes()
        count = len(recipes.get("results", []))
        print(f"Соединение с API успешно. Получено рецептов: {count}")
        return recipes


if __name__ == "__main__":
    client = TandoorAPIClient()
    client.test_connection()
