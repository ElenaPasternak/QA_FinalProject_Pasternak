import json
import os
from datetime import date, timedelta

from api.client import TandoorAPIClient

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "recipe_urls.json")
RESULT_FILE = os.path.join(os.path.dirname(__file__), "data", "imported_recipes.json")


def norm(name):
    return " ".join(name.split()).casefold()


def build_meal_plan_data(recipe_id, servings=2, days=3, meal_type_id=1):
    """Формирует словарь с параметрами для создания плана питания:
    рецепт, даты начала и окончания, тип питания, количество порций."""
    start_date = date.today()
    end_date = start_date + timedelta(days=days)
    return {
        "recipe": recipe_id,
        "servings": servings,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "meal_type": meal_type_id,
    }


def generate_test_data():
    """Импортирует рецепты из recipe_urls.json без дубликатов
    и сохраняет их ID для тестов."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        urls = json.load(f)["recipes"]

    client = TandoorAPIClient()
    existing = {
        norm(r["name"]): r["id"]
        for r in client.get_recipes().get("results", [])
    }
    print("Existing recipes in Tandoor:", len(existing))

    imported = []
    for url in urls:
        try:
            recipe = client.import_recipe_by_url(url)
            name, recipe_id = recipe["name"], recipe["id"]
            if norm(name) in existing:
                print(f"SKIP  id={existing[norm(name)]}  {name!r} (already exists)")
                imported.append({"id": existing[norm(name)], "name": name, "url": url})
            else:
                print(f"OK    id={recipe_id}  {name!r}")
                imported.append({"id": recipe_id, "name": name, "url": url})
                existing[norm(name)] = recipe_id
        except Exception as e:
            print(f"FAIL  {url} -> {e}")

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump({"recipes": imported}, f, ensure_ascii=True, indent=2)

    print(f"Done: {len(imported)} recipes saved to data/imported_recipes.json")
    return imported


if __name__ == "__main__":
    generate_test_data()
