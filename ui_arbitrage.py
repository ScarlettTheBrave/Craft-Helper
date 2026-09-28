import os
import json
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QObject, Slot, Signal, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from arbitrage_core import ArbitrageEngine


class BackendBridge(QObject):
    def __init__(self, app_ref, widget_ref):
        super().__init__()
        self.app = app_ref
        self.widget = widget_ref
        self.engine = None

    @Slot(str, str, float, str, str)
    def start_scan(self, buy_city, sell_city, min_profit, tags_str, tiers_str):
        try:
            if self.engine and self.engine.isRunning():
                self.engine.terminate()
                self.engine.wait()

            is_premium = self.app.prem_cb.isChecked()
            current_tax = 6.5 if is_premium else 10.5
            target_tags = tags_str.split('|') if tags_str and tags_str != 'ALL' else []
            target_tiers = tiers_str.split('|') if tiers_str else ['T4', 'T5', 'T6', 'T7', 'T8']

            self.engine = ArbitrageEngine(
                buy_city, sell_city, current_tax, min_profit,
                self.app.dm.items_cache, target_tags, target_tiers
            )

            self.engine.progress.connect(self.widget.update_progress)
            self.engine.finished.connect(self.widget.update_results)
            self.engine.error.connect(self.widget.show_error)
            self.engine.start()
        except Exception as e:
            self.widget.show_error(str(e))


class ArbitrageWidget(QWidget):
    def __init__(self, app_ref, parent=None):
        super().__init__(parent)
        self.app = app_ref
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        self.browser.setContextMenuPolicy(Qt.NoContextMenu)

        self.channel = QWebChannel(self.browser.page())
        self.bridge = BackendBridge(self.app, self)
        self.channel.registerObject("backendBridge", self.bridge)
        self.browser.page().setWebChannel(self.channel)

        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "arbitrage_ui.html"))
        self.browser.setUrl(QUrl.fromLocalFile(html_path))
        lay.addWidget(self.browser)

    def update_progress(self, curr, tot):
        pct = int((curr / tot) * 100)
        self.browser.page().runJavaScript(f"if(window.setPct) window.setPct({pct});")

    def update_results(self, results):
        clean = []
        cache = self.app.dm.items_cache
        cache_dir = os.path.abspath("icons_cache")

        for d in results:
            iid = d['item_id']

            base_id = iid.split('@')[0] if '@' in iid else iid
            ench_level = iid.split('@')[1] if '@' in iid else "0"

            item_data = cache.get(base_id) or {}

            n_ru = ""
            for attr in ['name_ru', 'localized_name', 'ru_name', 'display_name', 'localized_names']:
                if attr in item_data:
                    val = item_data.get(attr)
                    if isinstance(val, dict):
                        n_ru = val.get('RU-RU', "")
                    elif isinstance(val, str) and val:
                        n_ru = val
                    break

            if not n_ru:
                n_ru = str(item_data.get('name', base_id.replace('_', ' ')))

            if ench_level != "0":
                n_ru = f"{n_ru} .{ench_level}"

            local_icon_exact = os.path.join(cache_dir, f"{iid}.png")
            local_icon_base = os.path.join(cache_dir, f"{base_id}.png")

            # ВЕБ-ССЫЛКИ: 100% рабочие, если локальные битые
            web_exact = f"https://render.albiononline.com/v1/item/{iid}.png?quality={d['quality']}"
            web_base = f"https://render.albiononline.com/v1/item/{base_id}.png"

            # ПРОВЕРКА > 100 БАЙТ: Защита от пустых иконок в кэше!
            if os.path.exists(local_icon_exact) and os.path.getsize(local_icon_exact) > 100:
                img_src = QUrl.fromLocalFile(local_icon_exact).toString()
                fallback_src = web_exact
            elif os.path.exists(local_icon_base) and os.path.getsize(local_icon_base) > 100:
                img_src = QUrl.fromLocalFile(local_icon_base).toString()
                fallback_src = web_base
            else:
                img_src = web_exact
                fallback_src = web_base
                if hasattr(self.app, 'icon_downloader'):
                    self.app.icon_downloader.request_icon(iid)

            clean.append({
                "id": iid,
                "n": n_ru,
                "q": d['quality'],
                "bp": d['buy_price'],
                "sp": d['sell_price'],
                "s": d['profit_silver'],
                "p": d['profit_pct'],
                "img": img_src,
                "f_img": fallback_src
            })

        self.browser.page().runJavaScript(f"if(window.render) window.render({json.dumps(clean)});")

    def show_error(self, m):
        safe_msg = str(m).replace("'", "\\'")
        self.browser.page().runJavaScript(f"alert('Ошибка: {safe_msg}'); if(window.hideLoader) window.hideLoader();")