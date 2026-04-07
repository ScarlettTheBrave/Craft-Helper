import requests
from models import SessionLocal, Item, Recipe

FORMATTED_ITEMS_URL = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/formatted/items.json"
RAW_ITEMS_URL = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/items.json"


def download_data(url):
    print(f"📥 Скачивание: {url.split('/')[-1]}...")
    return requests.get(url).json()


def extract_recipes_recursive(data):
    recipes = []

    def traverse(obj, current_item_id=None):
        if isinstance(obj, dict):

            item_id = obj.get('@uniquename') or obj.get('UniqueName') or obj.get('uniquename')
            if item_id:
                current_item_id = item_id


            ench_level = obj.get('@enchantmentlevel')
            if ench_level and current_item_id:
                base_id = current_item_id.split('@')[0]
                current_item_id = f"{base_id}@{ench_level}"

            for key, value in obj.items():
                if key.lower() == 'craftingrequirements':
                    reqs = value if isinstance(value, list) else [value]
                    for req in reqs:
                        if isinstance(req, dict):
                            resources = req.get('craftresource') or req.get('CraftResource') or []
                            if isinstance(resources, dict): resources = [resources]
                            for res in resources:
                                if isinstance(res, dict):
                                    res_id = res.get('@uniquename') or res.get('uniquename') or res.get('UniqueName')
                                    count = res.get('@count') or res.get('count') or res.get('Count')

                                    if current_item_id and res_id and count:

                                        if "_LEVEL" in res_id and "@" not in res_id:
                                            level = res_id.split("_LEVEL")[-1]
                                            res_id = f"{res_id}@{level}"

                                        recipes.append({
                                            'item_id': current_item_id,
                                            'material_id': res_id,
                                            'amount': int(count)
                                        })
                else:
                    traverse(value, current_item_id)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item, current_item_id)

    traverse(data)
    return recipes


def load_data():
    db = SessionLocal()
    try:
        formatted_data = download_data(FORMATTED_ITEMS_URL)
        print("🗑 Очистка поврежденных данных...")
        db.query(Recipe).delete()
        db.commit()

        print(f"⚙️ Обработка {len(formatted_data)} предметов...")
        for entry in formatted_data:
            item_id = entry.get('UniqueName')
            if not item_id: continue

            item_value = entry.get('ItemValue', 0)
            fame = entry.get('CraftingFame', item_value * 2.125)
            names = entry.get('LocalizedNames') or {}
            name = names.get('RU-RU', names.get('EN-US', item_id))


            tier = entry.get('Tier', 0)
            if tier == 0 and item_id.startswith('T') and len(item_id) > 1 and item_id[1].isdigit():
                tier = int(item_id[1])

            db.merge(Item(id=item_id, name=name, tier=tier, item_value=item_value, base_fame=fame))
        db.commit()
        print("✅ Предметы сохранены.")

        raw_data = download_data(RAW_ITEMS_URL)
        print("⚙️ Глубокий поиск рецептов (исправленный алгоритм)...")
        found_recipes = extract_recipes_recursive(raw_data)
        unique_recipes = {f"{r['item_id']}_{r['material_id']}": r for r in found_recipes}

        valid_item_ids = {item.id for item in db.query(Item.id).all()}

        recipe_count = 0
        for r in unique_recipes.values():
            if r['item_id'] in valid_item_ids:
                db.add(Recipe(item_id=r['item_id'], material_id=r['material_id'], amount=r['amount']))
                recipe_count += 1

        db.commit()
        print(f" Успешно собрано ИДЕАЛЬНЫХ рецептов: {recipe_count}")
    except Exception as e:
        print(f" Ошибка: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    load_data()