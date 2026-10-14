"""Удаляет дубликаты рецептов: оставляет самую старую копию по каждому имени."""
from collections import defaultdict

from api.client import TandoorAPIClient


def norm(name):
    return " ".join(name.split()).casefold()


def main():
    client = TandoorAPIClient()
    recipes = client.get_recipes().get("results", [])
    print(f"Всего рецептов в базе: {len(recipes)}")

    groups = defaultdict(list)
    for r in recipes:
        groups[norm(r["name"])].append(r)

    removed = 0
    for name, copies in sorted(groups.items()):
        if len(copies) <= 1:
            continue
        # сортируем по id: меньший id = более старый рецепт
        copies.sort(key=lambda r: r["id"])
        keep = copies[0]
        print(f"\n{keep['name']!r}: оставляю id={keep['id']}")
        for dup in copies[1:]:
            print(f"  удаляю дубликат id={dup['id']}")
            client.delete_recipe(dup["id"])
            removed += 1

    print(f"\nГотово: удалено {removed} дубликатов")


if __name__ == "__main__":
    main()
