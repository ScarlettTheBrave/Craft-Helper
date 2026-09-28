import requests
from PySide6.QtCore import QRunnable, Slot, QObject, Signal


class ApiSignals(QObject):
    finished = Signal(dict)
    progress = Signal(int, int)  # Текущий индекс, Общее количество
    error = Signal(str)


class MarketFetcher(QRunnable):
    def __init__(self, item_ids: list, location: str = "Lymhurst"):
        super().__init__()
        self.item_ids = item_ids
        self.location = location
        self.signals = ApiSignals()
        self.base_url = "https://europe.albion-online-data.com/api/v2/stats/prices/"

        self.running = True

    @Slot()
    def run(self):
        try:
            if not self.item_ids:
                self.signals.finished.emit({})
                return

            chunk_size = 100
            final_prices = {}
            total = len(self.item_ids)

            for i in range(0, total, chunk_size):

                if not self.running:
                    break

                chunk = self.item_ids[i:i + chunk_size]
                url = f"{self.base_url}{','.join(chunk)}?locations={self.location}"

                self.signals.progress.emit(i, total)

                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()

                    for entry in data:
                        item_id = entry['item_id']
                        price = entry['sell_price_min']

                        # ЗАЩИТА ОТ ПЕРЕЗАПИСИ НУЛЯМИ:
                        if item_id not in final_prices:
                            final_prices[item_id] = price
                        elif final_prices[item_id] == 0 and price > 0:
                            # Если записан 0, а пришла реальная цена — обновляем
                            final_prices[item_id] = price
                        elif final_prices[item_id] > 0 and price > 0:
                            # Если пришли две реальные цены (например, разное качество),
                            # логично сохранить самую минимальную (для закупки)
                            final_prices[item_id] = min(final_prices[item_id], price)

            self.signals.progress.emit(total, total)
            self.signals.finished.emit(final_prices)

        except Exception as e:
            self.signals.error.emit(str(e))