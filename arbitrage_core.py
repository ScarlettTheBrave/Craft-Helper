import pandas as pd
import requests
import traceback
from PySide6.QtCore import QThread, Signal
from concurrent.futures import ThreadPoolExecutor, as_completed


class ArbitrageEngine(QThread):
    finished = Signal(list)
    progress = Signal(int, int)
    error = Signal(str)

    def __init__(self, buy_city, sell_city, tax_percent, min_profit_percent, items_cache, filter_tags=None,
                 filter_tiers=None):
        super().__init__()
        self.buy_city = buy_city
        self.sell_city = sell_city
        self.tax_rate = tax_percent / 100.0
        self.min_profit_pct = min_profit_percent
        self.items_cache = items_cache
        self.filter_tags = filter_tags if filter_tags else []
        self.filter_tiers = filter_tiers if filter_tiers else ['T4', 'T5', 'T6', 'T7', 'T8']

    def fetch_chunk(self, url):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return []

    def run(self):
        print(
            f"[CORE] Анализ: {self.buy_city} -> {self.sell_city}. Теги: {self.filter_tags}, Тиры: {self.filter_tiers}")
        try:
            base_equipment_ids = []
            valid_tiers = tuple(self.filter_tiers)

            for item_id in self.items_cache.keys():
                iid = str(item_id)
                if '@' in iid:
                    continue

                if iid.startswith(valid_tiers) and "ARTEFACT" not in iid and "TRASH" not in iid:
                    if not self.filter_tags or any(tag in iid for tag in self.filter_tags):
                        base_equipment_ids.append(iid)

            equipment_ids = []
            for base_id in base_equipment_ids:
                equipment_ids.append(base_id)
                equipment_ids.append(f"{base_id}@1")
                equipment_ids.append(f"{base_id}@2")
                equipment_ids.append(f"{base_id}@3")
                equipment_ids.append(f"{base_id}@4")

            total_items = len(equipment_ids)
            print(f"[CORE] Сгенерировано {total_items} ID для сканирования.")

            if total_items == 0:
                self.error.emit("В выбранной категории/тирах нет предметов.")
                return

            chunk_size = 50
            chunks = [equipment_ids[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
            all_prices = []

            completed = 0
            with ThreadPoolExecutor(max_workers=15) as executor:
                future_to_url = {}
                for chunk in chunks:
                    url = (f"https://europe.albion-online-data.com/api/v2/stats/prices/{','.join(chunk)}"
                           f"?locations={self.buy_city},{self.sell_city}&qualities=1,2,3,4,5")
                    future = executor.submit(self.fetch_chunk, url)
                    future_to_url[future] = url

                for future in as_completed(future_to_url):
                    data = future.result()
                    if data:
                        all_prices.extend(data)
                    completed += 1
                    self.progress.emit(completed, len(chunks))

            if not all_prices:
                self.finished.emit([])
                return

            df = pd.DataFrame(all_prices)

            if 'sell_price_min' not in df.columns or 'buy_price_max' not in df.columns:
                self.finished.emit([])
                return

            df_buy = df[df['city'] == self.buy_city][['item_id', 'quality', 'sell_price_min']].rename(
                columns={'sell_price_min': 'buy_price'})
            df_sell = df[df['city'] == self.sell_city][['item_id', 'quality', 'buy_price_max']].rename(
                columns={'buy_price_max': 'sell_price'})

            # OUTER MERGE
            merged = pd.merge(df_buy, df_sell, on=['item_id', 'quality'], how='outer').fillna(0)

            merged['has_data'] = (merged['buy_price'] > 0) & (merged['sell_price'] > 0)
            merged['profit_silver'] = 0.0
            merged['profit_pct'] = 0.0

            mask = merged['has_data']
            if mask.any():
                merged.loc[mask, 'profit_silver'] = (merged.loc[mask, 'sell_price'] * (1 - self.tax_rate)) - merged.loc[
                    mask, 'buy_price']
                merged.loc[mask, 'profit_pct'] = (merged.loc[mask, 'profit_silver'] / merged.loc[
                    mask, 'buy_price']) * 100

            # --- ИСПРАВЛЕННАЯ ЛОГИКА ---
            is_global = len(self.filter_tags) == 0

            if is_global:
                # Если смотрим ВСЁ: оставляем только то, что проходит Мин %
                final_df = merged[mask & (merged['profit_pct'] >= self.min_profit_pct)].copy()
            else:
                # Если смотрим ветку (Булавы и т.д.): ОСТАВЛЯЕМ ВООБЩЕ ВСЁ (и минуса, и пустышки)
                final_df = merged.copy()

            final_df = final_df.sort_values(by=['has_data', 'profit_pct', 'profit_silver'],
                                            ascending=[False, False, False])

            results = final_df.to_dict('records')
            self.finished.emit(results)

        except Exception as e:
            print(f"[CORE] ОШИБКА:\n{traceback.format_exc()}")
            self.error.emit(str(e))