# calc_engine.py

def calculate_craft_profit(
        sell_price: float,
        total_resource_cost: float,
        active_rrr_percent: float,
        station_fee: float,
        market_tax_percent: float = 6.5,
        craft_fame: float = 0,
        journal_data: dict = None
) -> dict:
    """
    Универсальный движок расчета прибыли.
    Безопасно обрабатывает данные журналов.
    """

    return_value = total_resource_cost * (active_rrr_percent / 100.0)


    actual_craft_cost = (total_resource_cost - return_value) + station_fee


    market_tax_amount = sell_price * (market_tax_percent / 100.0)


    journal_profit = 0
    if journal_data:

        if 'profit_val' in journal_data:
            journal_profit = journal_data['profit_val']


        elif 'full_p' in journal_data and 'empty_p' in journal_data:
            capacity = journal_data.get('capacity', 600)
            journal_profit = (craft_fame / capacity) * (journal_data['full_p'] - journal_data['empty_p'])


    net_income = sell_price - market_tax_amount
    net_profit = (net_income - actual_craft_cost) + journal_profit


    roi_percent = (net_profit / actual_craft_cost * 100) if actual_craft_cost > 0 else 0.0

    return {
        "actual_craft_cost": round(actual_craft_cost),
        "net_profit": round(net_profit),
        "roi_percent": round(roi_percent, 2),
        "journal_profit": round(journal_profit)
    }