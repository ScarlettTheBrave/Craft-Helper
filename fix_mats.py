import os
from dotenv import load_dotenv
from supabase import create_client
from sqlalchemy.orm import joinedload
from models import SessionLocal, Item

load_dotenv()
sb = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
db = SessionLocal()

print("⏳ Вытягиваем правильные (первые) рецепты...")
raw_items = db.query(Item).options(joinedload(Item.recipes)).filter(Item.id.like('T%')).all()
items_upserts = []

for item_obj in raw_items:
    base_dict = {c.name: getattr(item_obj, c.name) for c in item_obj.__table__.columns}
    mats = []


    if hasattr(item_obj, 'recipes') and item_obj.recipes:
        first_recipe = item_obj.recipes[0]
        reqs = getattr(first_recipe, 'requirements', getattr(first_recipe, 'resources', []))

        if reqs:
            for req in reqs:
                r_id = getattr(req, 'material_id', getattr(req, 'resource_id', getattr(req, 'item_id', None)))
                qty = getattr(req, 'amount', getattr(req, 'qty', getattr(req, 'count', 1)))
                if r_id: mats.append({"id": r_id, "amount": qty})
        else:
            r_id = getattr(first_recipe, 'material_id',
                           getattr(first_recipe, 'resource_id', getattr(first_recipe, 'item_id', None)))
            qty = getattr(first_recipe, 'amount', getattr(first_recipe, 'qty', getattr(first_recipe, 'count', 1)))
            if r_id: mats.append({"id": r_id, "amount": qty})

    base_dict['mats'] = mats
    items_upserts.append({"item_id": item_obj.id, "data": base_dict})

print(f"🚀 Собрано {len(items_upserts)} предметов. Заливаем...")
for i in range(0, len(items_upserts), 200):
    sb.table("items").upsert(items_upserts[i:i + 200]).execute()
    print(f"✅ {min(i + 200, len(items_upserts))} / {len(items_upserts)}")

print("🎉 ГОТОВО! Рецепты-мутанты уничтожены.")