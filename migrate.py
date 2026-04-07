import os
from dotenv import load_dotenv
from supabase import create_client

from data_manager import DataManager


def serialize_sqlalchemy(obj):
    """Превращает объект базы данных в обычный словарь"""
    if not obj: return {}
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def run_migration():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")  # Тут нужен secret (service_role) ключ
    supabase = create_client(url, key)

    print("⏳ Подключение к локальной базе и Redis...")
    dm = DataManager()


    print(f"📦 Найдено {len(dm.manual_prices)} ручных цен. Переносим...")
    manual_upserts = []
    for cache_key, price in dm.manual_prices.items():
        city, item_id = cache_key.split(":")
        manual_upserts.append({
            "id": f"{city}_{item_id}",
            "city": city,
            "item_id": item_id,
            "price": float(price)
        })

    if manual_upserts:
        for i in range(0, len(manual_upserts), 500):
            supabase.table("manual_prices").upsert(manual_upserts[i:i + 500]).execute()
    print("✅ Ручные цены перенесены!")


    print(f"📦 Найдено {len(dm.items_cache)} предметов. Готовим данные...")
    items_upserts = []

    for item_id, item_obj in dm.items_cache.items():
        base_dict = serialize_sqlalchemy(item_obj)


        mats = []
        if hasattr(item_obj, 'recipes') and item_obj.recipes:
            recipe = item_obj.recipes[0]

            reqs = getattr(recipe, 'requirements', None) or getattr(recipe, 'resources', [])
            for r in reqs:

                mats.append({
                    "id": getattr(r, 'resource_id', getattr(r, 'item_id', '')),
                    "amount": getattr(r, 'amount', getattr(r, 'qty', 1))
                })

        base_dict['mats'] = mats
        items_upserts.append({"item_id": item_id, "data": base_dict})

    print(" Отправляем предметы в Supabase...")
    for i in range(0, len(items_upserts), 100):
        try:
            supabase.table("items").upsert(items_upserts[i:i + 100]).execute()
            print(f"   Отправлено {min(i + 100, len(items_upserts))} / {len(items_upserts)}")
        except Exception as e:
            print(f"Ошибка на пакете {i}: {e}")

    print("🎉 МИГРАЦИЯ ПОЛНОСТЬЮ ЗАВЕРШЕНА!")


if __name__ == "__main__":
    run_migration()