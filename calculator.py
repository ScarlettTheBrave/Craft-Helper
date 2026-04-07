import requests
from models import SessionLocal, Item, Recipe


class AlbionCalculator:
    def __init__(self):
        # Базовый URL для Европы
        self.api_url = "https://europe.albion-online-data.com/api/v2/stats/prices/"

    def get_prices(self, item_ids, city="Lymhurst"):
        """Получает свежие цены из API, которые прислал твой Data Client"""
        items_str = ",".join(item_ids)
        try:
            response = requests.get(f"{self.api_url}{items_str}?locations={city}")
            return response.json()
        except Exception as e:
            print(f"Ошибка API: {e}")
            return []

    def calculate_crafting_cost(self, item_id, use_buy_order=False):
        """
        Главный расчет:
        1. Ищет рецепт в БД.
        2. Суммирует стоимость ресурсов.
        3. Если use_buy_order=True -> добавляет налог 1.5%.
        """
        db = SessionLocal()
        recipe = db.query(Recipe).filter(Recipe.item_id == item_id).all()

        total_cost = 0
        tax_multiplier = 1.015 if use_buy_order else 1.0

        for material in recipe:

            price_data = self.get_prices([material.material_id])
            if price_data:
                price = price_data[0]['sell_price_min']
                total_cost += (price * material.amount) * tax_multiplier

        db.close()
        return total_cost

    @staticmethod
    def calculate_focus_cost(base_focus, mastery):

        return int(base_focus * (0.5 ** (mastery / 100)))

    @staticmethod
    def get_profit_per_focus(profit, focus_spent):
        if focus_spent == 0: return 0
        return round(profit / focus_spent, 2)