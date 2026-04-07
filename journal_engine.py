# journal_engine.py

JOURNAL_CAPACITIES = {
    4: 3600,
    5: 7200,
    6: 14400,
    7: 28380,
    8: 58590
}


def get_best_journal_profit(item_tier, craft_fame, j_type, city, dm, market_tax_rate):
    """
    Выбирает самый выгодный тир журнала (свой или ниже).
    market_tax_rate: 0.065 или 0.105
    """
    if not j_type or item_tier < 4:
        return {"best_tier": 0, "profit": 0, "count": 0}

    best_res = {"best_tier": 0, "profit": 0, "count": 0}

    # Проверяем текущий тир и все ниже до T4
    for t in range(item_tier, 3, -1):
        j_id = f"T{t}_JOURNAL_{j_type}"
        empty_p = dm.get_price(city, f"{j_id}_EMPTY")
        full_p = dm.get_price(city, f"{j_id}_FULL")

        if empty_p > 0 and full_p > 0:
            # Чистая прибыль с ОДНОГО полного журнала (учитываем налог на продажу)
            # Мы вычитаем налог из цены продажи и стоимость пустого журнала
            net_full = full_p * (1 - market_tax_rate)
            profit_per_one = net_full - empty_p

            # Сколько таких журналов заполнит один крафт
            capacity = JOURNAL_CAPACITIES.get(t, 600)
            fill_count = craft_fame / capacity

            total_j_profit = fill_count * profit_per_one

            if total_j_profit > best_res["profit"]:
                best_res = {
                    "best_tier": t,
                    "profit": total_j_profit,
                    "count": fill_count
                }

    return best_res