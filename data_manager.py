import os
from dotenv import load_dotenv
from supabase import create_client, Client


class DataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return

        print("☁️ Инициализация Cloud DataManager (Supabase)...")
        load_dotenv()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("❌ Ключи Supabase не найдены в .env файле!")

        self.sb: Client = create_client(url, key)


        self.items_cache = {}
        self.prices_cache = {}
        self.manual_prices = {}

        self.preload_data()
        self._initialized = True

    def preload_data(self):
        print("⏳ Загрузка предметов из облака (обходим лимит в 1000 штук)...")
        try:
            offset = 0
            limit = 1000

            while True:

                response = self.sb.table('items').select('*').range(offset, offset + limit - 1).execute()

                if not response.data:
                    break

                for row in response.data:
                    self.items_cache[row['item_id']] = row['data']


                if len(response.data) < limit:
                    break

                offset += limit

            print(f"✅ Загружено предметов ВСЕГО: {len(self.items_cache)}")
        except Exception as e:
            print(f"❌ Ошибка загрузки базы предметов: {e}")

        self.refresh_prices_cache()

    def refresh_prices_cache(self):
        print("⏳ Обновление кэша цен из облака...")
        self.prices_cache.clear()
        self.manual_prices.clear()
        try:

            offset = 0
            limit = 1000
            while True:
                res_auto = self.sb.table('market_prices').select('*').range(offset, offset + limit - 1).execute()
                if not res_auto.data: break
                for row in res_auto.data:
                    self.prices_cache[f"{row['city']}:{row['item_id']}"] = float(row['price'])
                if len(res_auto.data) < limit: break
                offset += limit


            offset = 0
            while True:
                res_manual = self.sb.table('manual_prices').select('*').range(offset, offset + limit - 1).execute()
                if not res_manual.data: break
                for row in res_manual.data:
                    self.manual_prices[f"{row['city']}:{row['item_id']}"] = float(row['price'])
                if len(res_manual.data) < limit: break
                offset += limit

            print(f"✅ Кэш цен обновлен! (Авто: {len(self.prices_cache)}, Ручные: {len(self.manual_prices)})")
        except Exception as e:
            print(f"❌ Ошибка загрузки цен: {e}")

    def get_price(self, city, item_id):
        """Отдает цену мгновенно из кэша RAM"""
        cache_key = f"{city}:{item_id}"
        if cache_key in self.manual_prices:
            return self.manual_prices[cache_key]
        return self.prices_cache.get(cache_key, 0.0)

    def set_manual_price(self, city, item_id, price):
        cache_key = f"{city}:{item_id}"
        self.manual_prices[cache_key] = float(price)


        try:
            self.sb.table('manual_prices').upsert({
                "id": f"{city}_{item_id}",
                "city": city,
                "item_id": item_id,
                "price": float(price)
            }).execute()
        except Exception as e:
            print(f"❌ Ошибка сохранения ручной цены: {e}")

    def clear_manual_price(self, city, item_id):
        cache_key = f"{city}:{item_id}"
        if cache_key in self.manual_prices:
            del self.manual_prices[cache_key]

        try:
            self.sb.table('manual_prices').delete().eq("id", f"{city}_{item_id}").execute()
        except Exception as e:
            print(f"❌ Ошибка удаления ручной цены: {e}")

    def get_item(self, item_id):
        """Возвращает словарь (JSON) с данными предмета"""
        return self.items_cache.get(item_id)

    def update_parsed_prices(self, city, final_prices_dict):
        """Новый метод: Сохраняет пачку спаршенных цен от MarketFetcher в облако"""
        data_to_upload = []
        for item_id, price in final_prices_dict.items():
            cache_key = f"{city}:{item_id}"
            self.prices_cache[cache_key] = float(price)  # Обновляем локально

            data_to_upload.append({
                "id": f"{city}_{item_id}",
                "city": city,
                "item_id": item_id,
                "price": float(price)
            })

        if data_to_upload:
            try:

                for i in range(0, len(data_to_upload), 500):
                    chunk = data_to_upload[i:i + 500]
                    self.sb.table('market_prices').upsert(chunk).execute()
            except Exception as e:
                print(f"❌ Ошибка сохранения спаршенных цен: {e}")