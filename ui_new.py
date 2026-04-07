import sys
import queue
import time
import os
import requests
import json
import qtawesome as qta
import random
from tips import LOADING_TIPS  # Импортируем наш новый список
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from journal_engine import get_best_journal_profit

# Подключаем наши модули

from data_manager import DataManager
from calc_engine import calculate_craft_profit
from market_api import MarketFetcher

print("✅ Все модули (БД, DataManager, Engine, API) успешно подключены.")

SCROLLBAR_QSS = ""


class ModernProgressDialog(QDialog):
    def __init__(self, title, max_val, parent=None):
        super().__init__(parent)
        self.setFixedSize(400, 180)  # Чуть увеличили высоту под кнопку


        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Tool)
        self.setModal(True)
        self.cancelled = False

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QDialog { background-color: #0d1117; border: 1px solid #30363d; border-radius: 12px; }
            QLabel#TitleLabel { color: #58a6ff; font-size: 15px; font-weight: bold; background: transparent; }
            QLabel#TipLabel { color: #8b949e; font-size: 12px; font-style: italic; background: transparent; border: none; }
            QProgressBar { border: 1px solid #30363d; border-radius: 6px; background: #010409; color: white; text-align: center; font-weight: bold; height: 25px; }
            QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #238636, stop:1 #2ea043); border-radius: 5px; }
            QPushButton#CancelBtn { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 6px 15px; font-weight: bold; }
            QPushButton#CancelBtn:hover { background-color: #f85149; color: white; border-color: #f85149; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        # --- Шапка с анимацией ---
        header = QHBoxLayout()
        self.icon_label = QLabel()
        self.spin_anim = qta.Spin(self.icon_label)
        self.icon_label.setPixmap(qta.icon('fa5s.sync-alt', color='#58a6ff', animation=self.spin_anim).pixmap(20, 20))
        header.addWidget(self.icon_label)

        self.lbl = QLabel(title)
        self.lbl.setObjectName("TitleLabel")
        header.addWidget(self.lbl)
        header.addStretch()
        layout.addLayout(header)

        # --- Прогресс ---
        self.bar = QProgressBar()
        self.bar.setMaximum(max_val)
        layout.addWidget(self.bar)

        # --- Подсказки ---
        from tips import LOADING_TIPS
        self.tip_lbl = QLabel(random.choice(LOADING_TIPS))
        self.tip_lbl.setObjectName("TipLabel")
        self.tip_lbl.setAlignment(Qt.AlignCenter)
        self.tip_lbl.setWordWrap(True)
        layout.addWidget(self.tip_lbl)

        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self.change_tip)
        self.tip_timer.start(3500)

        # --- Кнопка отмены ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def change_tip(self):
        from tips import LOADING_TIPS
        self.tip_lbl.setText(random.choice(LOADING_TIPS))

    def on_cancel(self):
        self.cancelled = True
        self.lbl.setText("Остановка... Сохраняем...")
        self.cancel_btn.setEnabled(False)
        self.reject()  # Закрывает окно и генерирует сигнал rejected

    def setValue(self, val):
        if self.cancelled: return
        self.bar.setValue(val)
        if val >= self.bar.maximum():
            self.tip_timer.stop()
            self.spin_anim.stop()
            QTimer.singleShot(500, self.accept)

# ================= ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ =================
class ModernTableHelper:
    @staticmethod
    def style_tree(tree):
        tree.setStyleSheet("""
            QTreeWidget { background-color: #111419; color: #e6edf3; border: 1px solid #1f242c; outline: none; font-size: 13px; }
            QTreeWidget::item { background-color: transparent; padding: 6px; border-bottom: 1px solid #1f242c; }
            QTreeWidget::item:hover { background-color: #161b22; }
            QTreeWidget::item:selected { background-color: transparent; color: #e6edf3; }
            QHeaderView::section { background: #0d1117; color: #8b949e; border: none; border-bottom: 2px solid #30363d; font-weight: bold; padding: 10px; font-size: 12px; }
        """)

    @staticmethod
    def style_table(table):
        table.setStyleSheet("""
            QTableWidget { background-color: #111419; color: #e6edf3; border: 1px solid #1f242c; gridline-color: transparent; outline: none; }
            QTableWidget::item { background-color: transparent; border-bottom: 1px solid #1f242c; padding: 5px; }
            QTableWidget::item:hover { background-color: #161b22; }
            QTableWidget::item:selected { background-color: transparent; color: #e6edf3; }
            QHeaderView::section { background: #0d1117; color: #8b949e; border: none; border-bottom: 2px solid #30363d; font-weight: bold; padding: 10px; }
            QTableWidget QLineEdit { background-color: #07090c; color: #58a6ff; border: 1px solid #1f242c; border-radius: 4px; padding: 2px 5px; font-weight: bold; font-size: 14px; }
            QTableWidget QLineEdit:focus { border: 1px solid #00a3ff; }
        """)


class WorkerSignals(QObject):
    finished = Signal(object)


class QuickParseWorker(QRunnable):
    def __init__(self, item_ids, source_button):
        super().__init__()
        self.item_ids = item_ids
        self.btn = source_button
        self.signals = WorkerSignals()

    def run(self):
        try:
            update_all_market_data(self.item_ids)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
        self.signals.finished.emit(self.btn)


class ResourceSyncThread(QThread):
    finished = Signal()

    def __init__(self, item_ids):
        super().__init__()
        self.item_ids = item_ids

    def run(self):
        update_all_market_data(self.item_ids)
        self.finished.emit()


# ================= КАСТОМНЫЕ КОМПОНЕНТЫ =================
class CustomTitleBar(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        self.start_pos = None
        self.setStyleSheet("background-color: #07090c; border-bottom: 1px solid #1f242c;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 5, 0)
        layout.setSpacing(5)

        # Иконка-логотип в заголовке
        logo = QLabel()
        logo.setPixmap(qta.icon('fa5s.cogs', color='#58a6ff').pixmap(16, 16))
        layout.addWidget(logo)

        title = QLabel("Craft Help by Scar (ERP Mode v2)")
        title.setStyleSheet("color: #e6edf3; font-weight: bold; font-size: 12px; border: none;")
        layout.addWidget(title)
        layout.addStretch()

        btn_style = """
            QPushButton { background: transparent; border: none; padding: 5px; border-radius: 4px;} 
            QPushButton:hover { background: #1f242c; }
            QPushButton:pressed { background: #0d1117; }
        """
        btn_close_style = """
            QPushButton { background: transparent; border: none; padding: 5px; border-radius: 4px;} 
            QPushButton:hover { background: #f85149; }
            QPushButton:pressed { background: #b62324; }
        """

        btn_min = QPushButton(qta.icon('fa5s.minus', color='#8b949e', color_active='white'), "")
        btn_min.setStyleSheet(btn_style)
        btn_min.clicked.connect(self.parent.showMinimized)

        btn_max = QPushButton(qta.icon('fa5s.square', color='#8b949e', color_active='white'), "")
        btn_max.setStyleSheet(btn_style)
        btn_max.clicked.connect(self.toggle_max)

        btn_close = QPushButton(qta.icon('fa5s.times', color='#8b949e', color_active='white'), "")
        btn_close.setStyleSheet(btn_close_style)
        btn_close.clicked.connect(self.parent.close)

        layout.addWidget(btn_min)
        layout.addWidget(btn_max)
        layout.addWidget(btn_close)

    def toggle_max(self):
        self.parent.showNormal() if self.parent.isMaximized() else self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.parent.move(self.parent.pos() + (event.globalPosition().toPoint() - self.start_pos))
            self.start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.start_pos = None


class ModernSpinBox(QWidget):
    valueChanged = Signal(int)

    def __init__(self, value=1, min_val=0, max_val=99999, parent=None):
        super().__init__(parent)
        self.min_val, self.max_val = min_val, max_val
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.setAttribute(Qt.WA_TranslucentBackground)

        btn_style = """
            QPushButton { background: #111419; border: 1px solid #1f242c; } 
            QPushButton:hover { background: #1f242c; border-color: #30363d; }
            QPushButton:pressed { background: #07090c; border-color: #58a6ff; }
        """

        self.btn_minus = QPushButton(qta.icon('fa5s.minus', color='#8b949e', color_active='white'), "")
        self.btn_minus.setFixedSize(28, 28)
        self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setStyleSheet(
            btn_style + "border-top-left-radius: 4px; border-bottom-left-radius: 4px; border-right: none;")
        self.btn_minus.clicked.connect(self.decrease)

        self.line_edit = QLineEdit(str(value))
        self.line_edit.setFixedHeight(28)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setStyleSheet(
            "QLineEdit { background: #07090c; color: white; font-weight: bold; border: 1px solid #1f242c; border-radius: 0px; padding: 2px; } QLineEdit:focus { border: 1px solid #00a3ff; }")
        self.line_edit.textChanged.connect(self.on_text)

        self.btn_plus = QPushButton(qta.icon('fa5s.plus', color='#8b949e', color_active='white'), "")
        self.btn_plus.setFixedSize(28, 28)
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setStyleSheet(
            btn_style + "border-top-right-radius: 4px; border-bottom-right-radius: 4px; border-left: none;")
        self.btn_plus.clicked.connect(self.increase)

        lay.addWidget(self.btn_minus)
        lay.addWidget(self.line_edit)
        lay.addWidget(self.btn_plus)

    def decrease(self):
        val = int(self.line_edit.text() or 0)
        if val > self.min_val: self.line_edit.setText(str(val - 1))

    def increase(self):
        val = int(self.line_edit.text() or 0)
        if val < self.max_val: self.line_edit.setText(str(val + 1))

    def on_text(self, text):
        if text.isdigit():
            val = max(self.min_val, min(int(text), self.max_val))
            self.valueChanged.emit(val)


class AnimatedCellButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(48, 34)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.bg_color = QColor("#111419")
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setStartValue(QColor("#111419"))
        self._anim.setEndValue(QColor("#1f242c"))
        self._anim.valueChanged.connect(self._update_bg)

    def _update_bg(self, value):
        self.bg_color = value;
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        is_active = self.property("active")
        painter.setBrush(QColor("#00a3ff") if is_active else self.bg_color)
        painter.setPen(QPen(QColor("#1f242c"), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        painter.setPen(QColor("white" if is_active else "#8b949e"))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())

    def enterEvent(self, event):
        if not self.property("active"): self._anim.setDirection(QAbstractAnimation.Forward); self._anim.start()

    def leaveEvent(self, event):
        if not self.property("active"): self._anim.setDirection(QAbstractAnimation.Backward); self._anim.start()


# ================= ПОТОКИ И ЯДРО КАЛЬКУЛЯТОРА =================
class AsyncCalculator(QThread):
    result_ready = Signal(str, list, int)

    def __init__(self):
        super().__init__()
        self.q = queue.Queue()
        self.running = True

    def request_calc(self, item_id, active_cells, city, tax, premium, journals, rrr_nf, rrr_f, quality, calc_id):
        with self.q.mutex: self.q.queue.clear()
        self.q.put((item_id, active_cells, city, tax, premium, journals, rrr_nf, rrr_f, quality, calc_id))

    def run(self):
        dm = DataManager()
        from journal_engine import get_best_journal_profit
        from calc_engine import calculate_craft_profit

        # =====================================================================
        # СЛОВАРЬ ЗАМЕН АРТЕФАКТОВ (Настрой точные ID токенов под свою базу!)
        # Ключ: кусок названия артефакта. Значение: Суффикс токена.
        # =====================================================================
        TOKEN_MAP = {
            "_HELL": "_ARTEFACT_TOKEN_DEMONIC",  # Адские вещи -> Демонический токен (Crystallized Dread)
            "_DEMON": "_ARTEFACT_TOKEN_DEMONIC",
            "_UNDEAD": "_ARTEFACT_TOKEN_UNDEAD", # Нежить -> Токен нежити
            "_KEEPER": "_ARTEFACT_TOKEN_KEEPER", # Хранители -> Токен хранителей
            "_FEY": "_ARTEFACT_TOKEN_FEY",       # Фейские вещи -> Токен фей
            "_AVALON": "_ARTEFACT_TOKEN_AVALON", # Авалонские -> Осколок Авалона
        }

        while self.running:
            try:
                task = self.q.get(timeout=0.2)
                item_id, active_cells, city, tax, premium, journals_enabled, rrr_nf, rrr_f, quality, calc_id = task

                clean_item_id = item_id.split('@')[0]
                raw_suffix = clean_item_id.split('_', 1)[1] if '_' in clean_item_id else clean_item_id

                j_type = ""
                raw_s = raw_suffix.upper()
                if any(x in raw_s for x in ["SWORD", "AXE", "MACE", "HAMMER", "SHIELD", "_PLATE"]): j_type = "WARRIOR"
                elif any(x in raw_s for x in ["BOW", "CROSSBOW", "SPEAR", "DAGGER", "QUARTERSTAFF", "_LEATHER", "HORN", "TORCH"]): j_type = "HUNTER"
                elif any(x in raw_s for x in ["FIRESTAFF", "HOLYSTAFF", "FROSTSTAFF", "ARCANESTAFF", "CURSEDSTAFF", "NATURESTAFF", "_CLOTH", "TOME", "ORB"]): j_type = "MAGE"
                elif any(x in raw_s for x in ["BAG", "CAPE", "TOOL", "GATHERER"]): j_type = "TOOLMAKER"

                target_ids = [f"T{t}_{raw_suffix}{'@' + str(e) if e > 0 else ''}" for t, e in active_cells]

                all_mats = set()
                for tid in target_ids:
                    base_tid = tid.split('@')[0]
                    item_obj = dm.get_item(base_tid)
                    if not item_obj: continue

                    ench_level = int(tid.split('@')[1]) if '@' in tid else 0

                    for req in item_obj.get('mats', []):
                        res_id = req.get('id', '')
                        if "FAVOR" in res_id: continue

                        if ench_level > 0 and any(res in res_id for res in ["_PLANKS", "_METALBAR", "_LEATHER", "_CLOTH"]):
                            final_res_id = f"{res_id}_LEVEL{ench_level}@{ench_level}"
                        else:
                            final_res_id = res_id

                        all_mats.add(final_res_id)


                        if "ARTEFACT" in final_res_id:
                            tier_part = final_res_id.split('_')[0]
                            ench_part = "@" + final_res_id.split('@')[1] if '@' in final_res_id else ""
                            for key, token_suffix in TOKEN_MAP.items():
                                if key in final_res_id:
                                    all_mats.add(f"{tier_part}{token_suffix}{ench_part}")
                                    break

                    if j_type and journals_enabled:
                        item_tier = int(tid.split('_')[0].replace('T', ''))
                        for jt in range(4, item_tier + 1):
                            all_mats.add(f"T{jt}_JOURNAL_{j_type}_EMPTY")
                            all_mats.add(f"T{jt}_JOURNAL_{j_type}_FULL")

                if target_ids:
                    try:
                        for i in range(0, len(target_ids), 50):
                            chunk = target_ids[i:i+50]
                            url = f"https://europe.albion-online-data.com/api/v2/stats/prices/{','.join(chunk)}?locations={city}&qualities={quality}"
                            resp = requests.get(url, timeout=5).json()
                            for p in resp:
                                if p['sell_price_min'] > 0:
                                    dm.prices_cache[f"{p['city']}:{p['item_id']}"] = float(p['sell_price_min'])
                    except Exception as e:
                        pass

                if all_mats:
                    try:
                        mats_list = list(all_mats)
                        for i in range(0, len(mats_list), 50):
                            chunk = mats_list[i:i+50]
                            url = f"https://europe.albion-online-data.com/api/v2/stats/prices/{','.join(chunk)}?locations={city}&qualities=1"
                            resp = requests.get(url, timeout=5).json()
                            for p in resp:
                                if p['sell_price_min'] > 0:
                                    dm.prices_cache[f"{p['city']}:{p['item_id']}"] = float(p['sell_price_min'])
                    except Exception as e:
                        pass

                results = []
                tax_rate_decimal = 0.065 if premium else 0.105

                for tid in target_ids:
                    base_tid = tid.split('@')[0]
                    item_obj = dm.get_item(base_tid)
                    ench_level = int(tid.split('@')[1]) if '@' in tid else 0
                    mats = []

                    if not item_obj: continue

                    for req in item_obj.get('mats', []):
                        res_id = req.get('id', '')
                        if "FAVOR" in res_id: continue
                        if ench_level > 0 and any(res in res_id for res in ["_PLANKS", "_METALBAR", "_LEATHER", "_CLOTH"]):
                            mats.append({"id": f"{res_id}_LEVEL{ench_level}@{ench_level}", "amount": req.get('amount')})
                        else:
                            mats.append(req)

                    raw_mat_cost = 0
                    mats_list = []
                    calculated_val = 0

                    for req in mats:
                        req_id = req.get('id')
                        req_amount = req.get('amount')

                        best_id = req_id
                        best_price = dm.get_price(city, req_id)


                        if "ARTEFACT" in req_id:
                            tier_part = req_id.split('_')[0]
                            ench_part = "@" + req_id.split('@')[1] if '@' in req_id else ""
                            for key, token_suffix in TOKEN_MAP.items():
                                if key in req_id:
                                    token_id = f"{tier_part}{token_suffix}{ench_part}"
                                    token_price = dm.get_price(city, token_id)


                                    if 0 < token_price < (best_price if best_price > 0 else float('inf')):
                                        best_price = token_price
                                        best_id = token_id
                                    break

                        raw_mat_cost += best_price * req_amount
                        mats_list.append({"id": best_id, "amount": req_amount, "price": best_price})

                        mat_obj = dm.get_item(best_id)
                        mat_iv = mat_obj.get('item_value', 0) if isinstance(mat_obj, dict) else 2
                        calculated_val += mat_iv * req_amount

                    mat_count = sum(req.get('amount', 0) for req in mats)
                    item_tier = int(tid.split('_')[0].replace('T', ''))
                    iv_tier_base = {4: 4, 5: 16, 6: 64, 7: 256, 8: 1024}.get(item_tier, 0)
                    fallback_iv = mat_count * iv_tier_base * (2 ** ench_level)

                    item_val = float(item_obj.get('item_value') or fallback_iv)
                    station_fee = item_val * 0.1125 * (tax / 100)

                    craft_fame = float(item_obj.get('base_fame') or (item_val * 2.25))

                    journal_profit = 0
                    best_j_tier = item_tier
                    if j_type and journals_enabled:
                        j_res = get_best_journal_profit(item_tier, craft_fame, j_type, city, dm, tax_rate_decimal)
                        journal_profit = j_res["profit"]
                        best_j_tier = j_res["best_tier"]

                    sell_price = dm.get_price(city, tid)
                    res_nf = calculate_craft_profit(sell_price, raw_mat_cost, rrr_nf * 100, station_fee,
                                                    tax_rate_decimal * 100, craft_fame, {"profit_val": journal_profit})
                    res_f = calculate_craft_profit(sell_price, raw_mat_cost, rrr_f * 100, station_fee,
                                                   tax_rate_decimal * 100, craft_fame, {"profit_val": journal_profit})

                    results.append({
                        "id": tid,
                        "name": item_obj.get('localized_names', {}).get('RU-RU', tid),
                        "tier": f"{item_tier}.{ench_level}",
                        "raw_mat_cost": raw_mat_cost,
                        "base_item_value": item_val,
                        "station_fee": station_fee,
                        "cost_nf": res_nf['actual_craft_cost'],
                        "cost_f": res_f['actual_craft_cost'],
                        "best_journal": f"T{best_j_tier}" if best_j_tier > 0 else "",
                        "craft_fame": craft_fame,
                        "sell_price": sell_price,
                        "nf_profit": res_nf['net_profit'] if sell_price > 0 else None,
                        "f_profit": res_f['net_profit'] if sell_price > 0 else None,
                        "mats": mats_list, "j_type": j_type, "age": "Now"
                    })
                self.result_ready.emit(item_id, results, calc_id)
            except queue.Empty:
                pass
            except Exception as e:
                import traceback
                print(f"🔴 Ошибка калькулятора: {e}")
                traceback.print_exc()

class AsyncIconDownloader(QThread):
    icon_ready = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.q = queue.Queue()
        self.running = True
        self.cache_dir = "icons_cache"
        if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)

    def get_cached_path(self, iid):
        path = os.path.join(self.cache_dir, f"{iid}.png")
        return path if os.path.exists(path) else None

    def request_icon(self, iid):
        if not self.get_cached_path(iid): self.q.put(iid)

    def clear_queue(self):
        with self.q.mutex: self.q.queue.clear()

    def run(self):
        with ThreadPoolExecutor(max_workers=10) as executor:
            while self.running:
                try:
                    iid = self.q.get(timeout=0.5)
                    executor.submit(self.download_and_save, iid)
                except queue.Empty:
                    pass

    def download_and_save(self, iid):
        try:
            resp = requests.get(f"https://render.albiononline.com/v1/item/{iid}.png?size=80", timeout=5)
            if resp.status_code == 200:
                path = os.path.join(self.cache_dir, f"{iid}.png")
                with open(path, "wb") as f: f.write(resp.content)
                self.icon_ready.emit(iid, path)
        except Exception:
            pass


class CustomNotification(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMinimumWidth(450)
        self.setStyleSheet(
            "QDialog { background-color: #111419; border: 2px solid #30363d; border-radius: 12px; } QLabel { color: white; background: transparent; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(25, 25, 25, 25)
        lay.setSpacing(10)

        header_lay = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon('fa5s.info-circle', color='#00a3ff').pixmap(24, 24))
        header_lay.addWidget(icon_lbl)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #00a3ff; font-size: 18px; font-weight: bold; border: none;")
        header_lay.addWidget(lbl_title)
        header_lay.addStretch()
        lay.addLayout(header_lay)

        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #e6edf3; font-size: 14px; border: none; margin-bottom: 15px; margin-top: 10px;")
        lay.addWidget(lbl_msg)

        btn = QPushButton(qta.icon('fa5s.check', color='white'), " Понятно")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton { background-color: #00a3ff; color: white; border-radius: 6px; padding: 10px 24px; font-weight: bold; font-size: 13px; border: none; } 
            QPushButton:hover { background-color: #33b5ff; }
            QPushButton:pressed { background-color: #0077cc; }
        """)
        btn.clicked.connect(self.accept)
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        btn_lay.addWidget(btn)
        lay.addLayout(btn_lay)


def show_notification(title, message, parent=None): CustomNotification(title, message, parent).exec()


class ModernInputDialog(QDialog):
    def __init__(self, title, placeholder, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMinimumWidth(400)
        self.setStyleSheet(
            "QDialog { background-color: #111419; border: 2px solid #30363d; border-radius: 12px; } QLabel { color: #8b949e; font-size: 14px; background: transparent; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)
        lay.addWidget(QLabel(title))
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(placeholder)
        self.input_field.setStyleSheet(
            "QLineEdit { background: #07090c; color: white; border: 1px solid #1f242c; padding: 8px; border-radius: 6px; } QLineEdit:focus { border: 1px solid #00a3ff; }")
        lay.addWidget(self.input_field)

        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        btn_cancel = QPushButton(qta.icon('fa5s.times', color='#8b949e'), " Отмена")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton { background: transparent; color: #8b949e; border: 1px solid #1f242c; border-radius: 4px; padding: 8px 16px; font-weight: bold; } 
            QPushButton:hover { background: #1f242c; color: white; border-color: #30363d; }
            QPushButton:pressed { background: #0d1117; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton(qta.icon('fa5s.check', color='white'), " Создать план")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet("""
            QPushButton { background: #238636; color: white; border-radius: 4px; padding: 8px 16px; font-weight: bold; border: none; } 
            QPushButton:hover { background: #2ea043; }
            QPushButton:pressed { background: #1a6327; }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_lay.addWidget(btn_cancel)
        btn_lay.addWidget(btn_ok)
        lay.addLayout(btn_lay)
        self.input_field.setFocus()

    def get_text(self): return self.input_field.text()


class ItemAnalysisDialog(QDialog):
    def __init__(self, item_name, base_item_id, app_ref, parent=None):
        super().__init__(parent)
        self.app = app_ref
        self.base_item_id = base_item_id
        self.result_icons = {}
        self.current_calc_id = 0
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMinimumSize(1100, 700)
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        header_bar = QFrame()
        header_bar.setFixedHeight(35)
        header_bar.setStyleSheet(
            "background: #07090c; border-bottom: 1px solid #1f242c; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        h_lay = QHBoxLayout(header_bar)
        h_lay.setContentsMargins(15, 0, 5, 0)

        # Иконка анализа в шапке
        icon_top = QLabel()
        icon_top.setPixmap(qta.icon('fa5s.chart-bar', color='#00a3ff').pixmap(16, 16))
        h_lay.addWidget(icon_top)

        title_lbl = QLabel(f"Анализ крафта: {item_name}")
        title_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #00a3ff; border: none;")
        h_lay.addWidget(title_lbl)
        h_lay.addStretch()

        close_btn = QPushButton(qta.icon('fa5s.times', color='#8b949e', color_active='white'), "")
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; padding: 5px 15px; border-radius: 4px;} 
            QPushButton:hover { background: #f85149; }
            QPushButton:pressed { background: #b62324; }
        """)
        close_btn.clicked.connect(self.close)
        h_lay.addWidget(close_btn)
        main_lay.addWidget(header_bar)

        self.active_cells = set((t, e) for t in range(4, 9) for e in range(0, 2))
        content_lay = QHBoxLayout()
        content_lay.setContentsMargins(15, 15, 15, 15)
        content_lay.setSpacing(15)
        left_panel = QFrame()
        left_panel.setFixedWidth(300)
        left_panel.setStyleSheet("background: #111419; border: 1px solid #1f242c; border-radius: 8px;")
        left_lay = QVBoxLayout(left_panel)
        left_lay.addWidget(QLabel("Выбор тиров",
                                  styleSheet="font-size: 14px; font-weight: bold; color: #e6edf3; margin-bottom: 10px; border: none;"))
        grid = QGridLayout()
        grid.setSpacing(4)
        self.buttons = {}
        for r, t in enumerate([4, 5, 6, 7, 8]):
            for c, e in enumerate([0, 1, 2, 3, 4]):
                btn = AnimatedCellButton(f"{t}.{e}", self)
                btn.setProperty("active", (t, e) in self.active_cells)
                btn.clicked.connect(lambda ch, t=t, e=e: self.toggle(t, e))
                grid.addWidget(btn, r, c)
                self.buttons[(t, e)] = btn
        left_lay.addLayout(grid)

        btn_style = """
            QPushButton { background: #1f242c; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; padding: 8px; font-weight: bold; font-size: 12px;} 
            QPushButton:hover { background: #30363d; color: white; }
            QPushButton:pressed { background: #0d1117; border-color: #58a6ff; }
        """
        h_lay_btns = QHBoxLayout()
        h_lay_btns.setSpacing(5)
        btn_all = QPushButton(qta.icon('fa5s.check-double', color='#c9d1d9'), " Выбрать все")
        btn_all.setStyleSheet(btn_style)
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_none = QPushButton(qta.icon('fa5s.eraser', color='#c9d1d9'), " Сбросить")
        btn_none.setStyleSheet(btn_style)
        btn_none.setCursor(Qt.PointingHandCursor)
        h_lay_btns.addWidget(btn_all)
        h_lay_btns.addWidget(btn_none)
        btn_all.clicked.connect(self.select_all)
        btn_none.clicked.connect(self.deselect_all)
        left_lay.addLayout(h_lay_btns)
        left_lay.addStretch()
        content_lay.addWidget(left_panel)

        right_panel = QVBoxLayout()
        r_top_lay = QHBoxLayout()
        self.status_lbl = QLabel("Сбор цен и расчет...")
        self.status_lbl.setStyleSheet("color: #8b949e; font-weight: bold; border: none;")
        r_top_lay.addWidget(self.status_lbl)
        r_top_lay.addStretch()

        self.btn_refresh = QPushButton()
        self.btn_refresh.setFixedSize(36, 36)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Обновить цены с рынка")

        icon = qta.icon('fa5s.sync-alt', color='#58a6ff', color_active='white')
        self.btn_refresh.setIcon(icon)
        self.btn_refresh.setIconSize(QSize(18, 18))
        self.btn_refresh.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #161b22, stop:1 #07090c); border: 1px solid #1f242c; border-radius: 6px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f242c, stop:1 #111419); border-color: #00a3ff; }
            QPushButton:pressed { background: #07090c; border-color: #0088cc; }
        """)
        self.btn_refresh.clicked.connect(self.request_update)
        r_top_lay.addWidget(self.btn_refresh)
        right_panel.addLayout(r_top_lay)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.results_container = QWidget()
        self.results_container.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_layout.setSpacing(10)
        self.scroll.setWidget(self.results_container)
        right_panel.addWidget(self.scroll)
        content_lay.addLayout(right_panel)
        main_lay.addLayout(content_lay)
        self.start_pos = None
        header_bar.mousePressEvent = self.header_mouse_press
        header_bar.mouseMoveEvent = self.header_mouse_move
        header_bar.mouseReleaseEvent = self.header_mouse_release
        self.request_update()

    def header_mouse_press(self, event):
        if event.button() == Qt.LeftButton: self.start_pos = event.globalPosition().toPoint()

    def header_mouse_move(self, event):
        if self.start_pos: self.move(self.pos() + (
                    event.globalPosition().toPoint() - self.start_pos)); self.start_pos = event.globalPosition().toPoint()

    def header_mouse_release(self, event):
        self.start_pos = None

    def toggle(self, t, e):
        if (t, e) in self.active_cells:
            self.active_cells.remove((t, e))
        else:
            self.active_cells.add((t, e))
        self.refresh_grid();
        self.request_update()

    def select_all(self):
        self.active_cells = set((t, e) for t in range(4, 9) for e in range(5))
        self.refresh_grid();
        self.request_update()

    def deselect_all(self):
        self.active_cells.clear();
        self.refresh_grid();
        self.request_update()

    def refresh_grid(self):
        for (tt, ee), b in self.buttons.items(): b.setProperty("active", (tt, ee) in self.active_cells); b.update()

    def request_update(self):
        spin_anim = qta.Spin(self.btn_refresh, step=3)
        icon_spinning = qta.icon('fa5s.sync-alt', color='#58a6ff', animation=spin_anim)
        self.btn_refresh.setIcon(icon_spinning)
        self.current_calc_id += 1
        self.status_lbl.show()
        self.status_lbl.setText("Обновление данных...")
        self.app.start_calc(self.base_item_id, list(self.active_cells), self.current_calc_id)

    def render_results(self, results):
        self.status_lbl.hide()
        self.scroll.setUpdatesEnabled(False)
        saved_pos = self.scroll.verticalScrollBar().value()
        self.status_lbl.hide()
        for i in reversed(range(self.results_layout.count())):
            widget = self.results_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        self.btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color='#58a6ff'))
        self.result_icons.clear()

        for res in sorted(results, key=lambda x: float(x['tier'])):
            card = QFrame()
            card.setStyleSheet("background: #111419; border: 1px solid #1f242c; border-radius: 8px;")
            card.setMinimumHeight(125)
            c_lay = QHBoxLayout(card)
            icon_box = QVBoxLayout()
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(55, 55)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            self.result_icons[res['id']] = icon_lbl
            pix = self.app.get_local_icon(res['id'])
            if pix:
                icon_lbl.setPixmap(pix.scaled(55, 55, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.app.icon_downloader.request_icon(res['id'])

            tier_lbl = QLabel(f"T{res['tier']}")
            tier_lbl.setStyleSheet(
                "color: white; font-weight: bold; font-size: 14px; border: none; background: transparent;")
            tier_lbl.setAlignment(Qt.AlignCenter)
            icon_box.addWidget(icon_lbl)
            icon_box.addWidget(tier_lbl)
            icon_box.addStretch()
            c_lay.addLayout(icon_box)

            grid = QGridLayout()
            grid.setVerticalSpacing(6)
            grid.setHorizontalSpacing(15)

            def create_lbl(text, color="#8b949e", bold=False, size=12):
                lbl = QLabel(text)
                lbl.setStyleSheet(
                    f"color: {color}; font-size: {size}px; font-weight: {'bold' if bold else 'normal'}; border: none; background: transparent;")
                return lbl

            grid.addWidget(create_lbl("Продажа:"), 0, 0)
            grid.addWidget(
                create_lbl(f"{int(res['sell_price']):,} ({res['age']})" if res['sell_price'] > 0 else "Нет данных",
                           "#e6edf3", True), 0, 1)
            grid.addWidget(create_lbl("Материалы:"), 1, 0)
            grid.addWidget(create_lbl(f"{int(res['raw_mat_cost']):,}", "#e6edf3"), 1, 1)
            grid.addWidget(create_lbl("Налог станка:"), 2, 0)
            # Берем уже просчитанный налог прямо из калькулятора
            grid.addWidget(
                create_lbl(f"{int(res['station_fee']):,}" + (" (+Ж)" if res['best_journal'] else ""), "#e6edf3"), 2, 1)

            def format_p(p, c):
                if p is None: return create_lbl("Нет цен", "#8b949e")
                m = (p / c * 100) if c > 0 else 0
                color = "#3fb950" if p > 0 else "#f85149"
                lbl = QLabel(
                    f"<span style='color:{color}; font-size:15px; font-weight:bold;'>{'+' if p > 0 else ''}{int(p):,}</span> <span style='color:{color}; font-size:11px;'>({'+' if p > 0 else ''}{m:.1f}%)</span>")
                lbl.setStyleSheet("border: none; background: transparent;")
                return lbl

            grid.addWidget(create_lbl("БЕЗ ФОКУСА", "#00a3ff", True), 0, 2, 1, 2, Qt.AlignCenter)
            grid.addWidget(create_lbl("Себест:"), 1, 2)
            grid.addWidget(create_lbl(f"{int(res['cost_nf']):,}", "#e6edf3"), 1, 3)
            grid.addWidget(create_lbl("Прибыль:"), 2, 2)
            grid.addWidget(format_p(res['nf_profit'], res['cost_nf']), 2, 3)
            grid.addWidget(create_lbl("С ФОКУСОМ", "#3fb950", True), 0, 4, 1, 2, Qt.AlignCenter)
            grid.addWidget(create_lbl("Себест:"), 1, 4)
            grid.addWidget(create_lbl(f"{int(res['cost_f']):,}", "#e6edf3"), 1, 5)
            grid.addWidget(create_lbl("Прибыль:"), 2, 4)
            grid.addWidget(format_p(res['f_profit'], res['cost_f']), 2, 5)
            c_lay.addLayout(grid)
            c_lay.addStretch()

            cart_box = QVBoxLayout()
            qty_spin = ModernSpinBox(value=10, min_val=1)
            btn_add = QPushButton(qta.icon('fa5s.cart-plus', color='white'), " В план")
            btn_add.setCursor(Qt.PointingHandCursor)
            btn_add.setStyleSheet("""
                QPushButton { background-color: #238636; color: white; border-radius: 4px; padding: 8px 15px; font-weight: bold; border: none; } 
                QPushButton:hover { background-color: #2ea043; }
                QPushButton:pressed { background-color: #1a6327; }
            """)
            btn_add.clicked.connect(
                lambda ch, r=res, q=qty_spin: self.app.add_to_production(r, int(q.line_edit.text() or 1)))
            cart_box.addWidget(
                QLabel("Партия:", styleSheet="color: #8b949e; font-size: 11px; border:none; background: transparent;"))
            cart_box.addWidget(qty_spin)
            cart_box.addWidget(btn_add)
            cart_box.addStretch()
            c_lay.addLayout(cart_box)
            self.results_layout.addWidget(card)

        self.scroll.verticalScrollBar().setValue(saved_pos)
        self.scroll.setUpdatesEnabled(True)

    def update_icons(self, item_id, file_path):
        if item_id in self.result_icons: self.result_icons[item_id].setPixmap(
            QPixmap(file_path).scaled(55, 55, Qt.KeepAspectRatio, Qt.SmoothTransformation))


class ItemWidget(QFrame):
    def __init__(self, name_en, name_ru, item_id, app_ref, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.name_en = (name_en or "").lower()
        self.name_ru = (name_ru or "").lower()
        self.app = app_ref
        self.setObjectName("ItemCard")
        self.setFixedHeight(60)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setStyleSheet("background: #07090c; border: 1px solid #1f242c; border-radius: 6px;")
        layout.addWidget(self.icon_label)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.en_lbl = QLabel(name_en if name_en else item_id)
        self.en_lbl.setStyleSheet(
            "color: white; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        self.ru_lbl = QLabel(name_ru if name_ru else "Нет перевода")
        self.ru_lbl.setStyleSheet("color: #8b949e; font-size: 12px; border: none; background: transparent;")
        names.addWidget(self.en_lbl)
        names.addWidget(self.ru_lbl)
        layout.addLayout(names)
        layout.addStretch()

        self.analyze_btn = QPushButton(qta.icon('fa5s.wrench', color='#00a3ff', color_active='white'), " Анализ")
        self.analyze_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #00a3ff; border: 1px solid #1f242c; border-radius: 5px; padding: 7px 15px; font-weight: bold; } 
            QPushButton:hover { background: #1f242c; color: white; border-color: #30363d; }
            QPushButton:pressed { background: #0d1117; border-color: #58a6ff; }
        """)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self.open_analysis)
        layout.addWidget(self.analyze_btn)

        pix = self.app.get_local_icon(item_id)
        self.set_loaded_icon(pix) if pix else self.app.icon_downloader.request_icon(item_id)

    def open_analysis(self):
        dialog = ItemAnalysisDialog(self.en_lbl.text(), self.item_id, self.app, self)
        self.app.active_dialog = dialog
        dialog.exec()
        self.app.active_dialog = None

    def set_loaded_icon(self, pixmap):
        self.icon_label.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.icon_label.setStyleSheet("border: none; background: transparent;")


class ProductionItemCard(QFrame):
    dataChanged = Signal()

    def __init__(self, item_data, app_ref, parent=None):
        super().__init__(parent)
        self.data = item_data
        self.app = app_ref
        self.setFixedHeight(110)
        self.setStyleSheet("""
            QFrame#ProdCard { background: #111419; border: 1px solid #1f242c; border-radius: 8px; }
            QFrame#ProdCard:hover { border-color: #30363d; }
            QLabel { color: #e6edf3; border: none; background: transparent; }
        """)
        self.setObjectName("ProdCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        icon_box = QVBoxLayout()
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(50, 50)
        pix = self.app.get_local_icon(self.data['id'])
        if pix:
            self.icon_lbl.setPixmap(pix.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:

            self.app.icon_downloader.request_icon(self.data['id'])

        self.tier_lbl = QLabel(f"T{self.data['tier']}")
        self.tier_lbl.setAlignment(Qt.AlignCenter)
        self.tier_lbl.setStyleSheet("font-weight: bold; color: #8b949e;")
        icon_box.addWidget(self.icon_lbl)
        icon_box.addWidget(self.tier_lbl)
        layout.addLayout(icon_box)

        info_box = QVBoxLayout()
        self.name_lbl = QLabel(self.data['name'])
        self.name_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.buy_method = QComboBox()
        self.buy_method.addItems(["Market (Sell)", "Buy Order (+1.5%)"])
        self.buy_method.setCurrentIndex(1 if self.data.get('use_buy_order') else 0)
        self.buy_method.setFixedWidth(140)
        self.buy_method.setStyleSheet("""
            QComboBox { background: #07090c; color: #58a6ff; font-weight: bold; border: 1px solid #1f242c; border-radius: 4px; padding: 4px; }
            QComboBox:focus { border: 1px solid #00a3ff; }
        """)
        self.buy_method.currentIndexChanged.connect(self.on_ui_change)

        info_box.addWidget(self.name_lbl)
        info_box.addWidget(self.buy_method)
        layout.addLayout(info_box)

        input_box = QGridLayout()
        input_box.addWidget(QLabel("Кол-во:", styleSheet="color: #8b949e; font-size: 11px;"), 0, 0)
        self.qty_spin = ModernSpinBox(value=self.data['qty'], min_val=1)
        self.qty_spin.valueChanged.connect(self.on_ui_change)
        input_box.addWidget(self.qty_spin, 1, 0)

        input_box.addWidget(QLabel("Цена продажи:", styleSheet="color: #8b949e; font-size: 11px;"), 0, 1)
        self.price_edit = QLineEdit(str(self.data.get('sell_price', 0)))
        self.price_edit.setFixedWidth(120)
        self.price_edit.setStyleSheet(
            "QLineEdit { background: #07090c; color: #58a6ff; font-weight: bold; border: 1px solid #1f242c; padding: 5px; border-radius: 4px; } QLineEdit:focus { border: 1px solid #00a3ff; }")
        self.price_edit.textChanged.connect(self.on_ui_change)
        input_box.addWidget(self.price_edit, 1, 1)
        layout.addLayout(input_box)

        self.profit_nf_lbl = QLabel("0")
        self.profit_f_lbl = QLabel("0")
        res_box = QVBoxLayout()
        res_box.addWidget(QLabel("Без фокуса:", styleSheet="color: #00a3ff; font-size: 11px;"))
        res_box.addWidget(self.profit_nf_lbl)
        res_box.addWidget(QLabel("С фокусом:", styleSheet="color: #3fb950; font-size: 11px;"))
        res_box.addWidget(self.profit_f_lbl)
        layout.addLayout(res_box)

        self.del_btn = QPushButton(qta.icon('fa5s.trash-alt', color='#f85149', color_active='white'), "")
        self.del_btn.setFixedSize(32, 32)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 16px; } 
            QPushButton:hover { background: #f85149; }
            QPushButton:pressed { background: #b62324; }
        """)
        self.del_btn.clicked.connect(lambda: self.app.remove_prod_item_by_id(self.data['id']))
        layout.addWidget(self.del_btn)
        # В методе __init__ класса ProductionItemCard, добавь self.focus_lbl:
        self.focus_lbl = QLabel("Фокус: 0")
        self.focus_lbl.setStyleSheet("color: #e3b341; font-size: 11px; font-weight: bold;")
        # Добавь его в res_box или info_box
        res_box.addWidget(self.focus_lbl)

    def on_ui_change(self):
        try:
            txt = self.price_edit.text().replace(' ', '').replace(',', '.').strip()
            new_price = int(float(txt)) if txt else 0


            if self.price_edit.hasFocus():
                city = self.app.current_city
                if not hasattr(self.app, 'manual_market_prices'):
                    self.app.manual_market_prices = {}
                if city not in self.app.manual_market_prices:
                    self.app.manual_market_prices[city] = {}

                self.app.manual_market_prices[city][self.data['id']] = new_price

            self.data['qty'] = int(self.qty_spin.line_edit.text() or 1)
            self.data['use_buy_order'] = (self.buy_method.currentIndex() == 1)
            self.dataChanged.emit()
        except:
            pass



class CraftHelpApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(1250, 850)

        try:
            with open("theme.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"⚠️ Не удалось загрузить theme.qss: {e}")

        self.icons_dir = "icons_cache"
        self.dm = DataManager()
        self.thread_pool = QThreadPool.globalInstance()
        self.icon_downloader = AsyncIconDownloader()
        self.icon_downloader.icon_ready.connect(self.on_icon)
        self.icon_downloader.start()
        self.calc_worker = AsyncCalculator()
        self.calc_worker.result_ready.connect(self.on_calc_done)
        self.calc_worker.start()
        self.manual_market_prices = {}  # Формат: {city_name: {item_id: price_value}}
        self.widgets = {}
        self.res_icons = {}
        self.current_city = "Lymhurst"
        self.current_quality = 1
        self.menu_buttons = []
        self.active_dialog = None
        self.production_plans = []
        self.current_plan_idx = 0
        self.current_journal_report = "Нет данных."

        central = QWidget()
        self.setCentralWidget(central)
        self.main_vbox = QVBoxLayout(central)
        self.main_vbox.setContentsMargins(0, 0, 0, 0)
        self.main_vbox.setSpacing(0)
        self.title_bar = CustomTitleBar(self)
        self.main_vbox.addWidget(self.title_bar)

        self.root_l = QHBoxLayout()
        self.root_l.setContentsMargins(0, 0, 0, 0)
        self.root_l.setSpacing(0)
        self.main_vbox.addLayout(self.root_l)

        self.setup_sidebar()
        self.setup_content()
        self.load_plans_from_disk()
        self.render_production_sheet()
        self.load_db(
            ["_MAIN_", "_2H_", "BOW", "CROSSBOW", "SPEAR", "DAGGER", "STAFF", "AXE", "SWORD", "MACE", "HAMMER"])

        self.auto_sync_timer = QTimer(self)
        self.auto_sync_timer.timeout.connect(self.sync_resources)
        self.auto_sync_timer.start(30 * 60 * 1000)

    def on_tree_item_changed(self, item, column):
        if column == 3:
            iid = item.data(0, Qt.UserRole)
            if iid:
                val = item.text(3).replace(',', '').strip()
                if val.isdigit():
                    self.dm.set_manual_price(self.current_city, iid, val)
                else:
                    self.dm.clear_manual_price(self.current_city, iid)
                    item.setText(3, "")
                if self.stack.currentWidget() == self.prod_widget: self.recalc_production_totals()

    def get_local_icon(self, iid):
        path = os.path.join(self.icons_dir, f"{iid}.png")
        return QPixmap(path) if os.path.exists(path) else None

    def setup_sidebar(self):
        side = QFrame()
        side.setFixedWidth(240)
        side.setStyleSheet("background: #07090c; border-right: 1px solid #1f242c;")
        self.root_l.addWidget(side)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 10, 0, 10)
        cats = [
            ("Шлемы", ["_HEAD_"], "icons/helmet.png"),
            ("Броня", ["_ARMOR_"], "icons/armor.png"),
            ("Обувь", ["_SHOES_"], "icons/boots.png"),
            ("Оружие",
             ["_MAIN_", "_2H_", "BOW", "CROSSBOW", "SPEAR", "DAGGER", "STAFF", "AXE", "SWORD", "MACE", "HAMMER"],
             "icons/sword.png"),
            ("Инструменты", ["_TOOL_", "_GATHERER_"], "icons/pickaxe.png"),
            ("Аксессуары", ["_OFF_", "_CAPE_", "_BAG_"], "icons/accessories.png"),
            ("Ресурсы", ["_RESOURCES_"], "icons/metal.png"),
            ("Производство (ERP)", ["_PRODUCTION_"], "icons/erp.png")
        ]
        for i, (name, tags, path) in enumerate(cats):
            btn = QPushButton(f"  {name}")
            btn.setObjectName("SidebarItem")
            btn.setCursor(Qt.PointingHandCursor)
            if os.path.exists(path):
                btn.setIcon(QIcon(path))
                btn.setIconSize(QSize(18, 18))
            btn.setProperty("db_tags", tags)
            is_def = tags == cats[3][1]
            btn.setProperty("active", is_def)
            if is_def: self.current_active_btn = btn
            btn.clicked.connect(self.handle_sidebar_click)
            lay.addWidget(btn)
            self.menu_buttons.append(btn)
        lay.addStretch()
        lay.addWidget(QLabel(" Scar © 2026 ", styleSheet="color: #30363d; font-size: 11px; margin-left: 15px;"))

    def handle_sidebar_click(self):
        self.icon_downloader.clear_queue()
        sender = self.sender()
        if hasattr(self, 'current_active_btn') and sender == self.current_active_btn: return
        tags = sender.property("db_tags")

        if hasattr(self, 'current_active_btn'):
            self.current_active_btn.setProperty("active", False)
            self.current_active_btn.style().unpolish(self.current_active_btn)
            self.current_active_btn.style().polish(self.current_active_btn)

        sender.setProperty("active", True)
        sender.style().unpolish(sender)
        sender.style().polish(sender)
        self.current_active_btn = sender

        if "_RESOURCES_" in tags:
            self.city_container.show()
            self.quality_container.hide()
            self.stack.setCurrentWidget(self.res_tabs)
            if self.mats_tree.topLevelItemCount() == 0: self.load_resources_trees()
        elif "_PRODUCTION_" in tags:
            self.top_filters_bg.hide()
            self.stack.setCurrentWidget(self.prod_widget)
            self.render_production_sheet()
            return
        else:
            self.city_container.show()
            self.quality_container.show()
            self.stack.setCurrentWidget(self.grid_scroll)
            self.load_db(tags)

        if self.top_filters_bg.isHidden(): self.top_filters_bg.show()

    def setup_content(self):
        cont = QVBoxLayout()
        cont.setContentsMargins(20, 20, 20, 20)
        cont.setSpacing(15)
        self.root_l.addLayout(cont)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        self.srch = QLineEdit()
        self.srch.setPlaceholderText("Глобальный поиск...")

        search_icon = qta.icon('fa5s.search', color='#8b949e')
        self.srch.addAction(search_icon, QLineEdit.LeadingPosition)
        self.srch.textChanged.connect(self.do_filter)
        self.srch.setStyleSheet("""
            QLineEdit { background: #111419; color: white; border: 1px solid #1f242c; padding: 12px; border-radius: 8px; font-size: 14px; }
            QLineEdit:focus { border: 1px solid #58a6ff; }
        """)
        top_bar.addWidget(self.srch)

        def create_input(dv):
            inp = QLineEdit(dv)
            inp.setFixedWidth(55)
            inp.setStyleSheet(
                "QLineEdit { background: #07090c; color: #00a3ff; border: 1px solid #1f242c; padding: 10px; border-radius: 6px; font-weight: bold; } QLineEdit:focus { border: 1px solid #00a3ff; }")
            inp.textChanged.connect(self.on_global_settings_changed)
            return inp

        lbl = "color: #8b949e; font-size: 13px; font-weight: bold; margin-left: 5px; background: transparent;"
        top_bar.addWidget(QLabel("RRR №%:", styleSheet=lbl))
        self.rrr_nf_input = create_input("15.2")
        top_bar.addWidget(self.rrr_nf_input)
        top_bar.addWidget(QLabel("RRR Фокус%:", styleSheet=lbl))
        self.rrr_f_input = create_input("43.5")
        top_bar.addWidget(self.rrr_f_input)
        top_bar.addWidget(QLabel("Налог:", styleSheet=lbl))
        self.tax_input = create_input("500")
        top_bar.addWidget(self.tax_input)

        cb_style = "QCheckBox { color: #8b949e; margin-left: 10px; } QCheckBox::indicator { width: 16px; height: 16px; }"
        self.prem_cb = QCheckBox("Prem")
        self.prem_cb.setChecked(True)
        self.prem_cb.setStyleSheet(cb_style)
        self.prem_cb.stateChanged.connect(self.on_global_settings_changed)
        self.journal_cb = QCheckBox("Journals")
        self.journal_cb.setChecked(True)
        self.journal_cb.setStyleSheet(cb_style)
        self.journal_cb.stateChanged.connect(self.on_global_settings_changed)
        top_bar.addWidget(self.prem_cb)
        top_bar.addWidget(self.journal_cb)
        cont.addLayout(top_bar)

        self.top_filters_bg = QFrame()
        self.top_filters_bg.setStyleSheet("background: #111419; border: 1px solid #1f242c; border-radius: 10px;")
        filters_lay = QVBoxLayout(self.top_filters_bg)
        filters_lay.setContentsMargins(15, 12, 15, 12)
        filters_lay.setSpacing(10)

        self.city_container = QWidget()
        city_lay = QHBoxLayout(self.city_container)
        city_lay.setContentsMargins(0, 0, 0, 0)
        city_lay.addWidget(QLabel("Локация:",
                                  styleSheet="color: #e6edf3; font-weight: bold; margin-right: 10px; border: none; background: transparent;"))
        self.city_group = QButtonGroup(self)
        cities = [("Lymhurst", "#a3d95b"), ("Martlock", "#5b9ed9"), ("Thetford", "#b85bd9"),
                  ("Fort Sterling", "#e6edf3"), ("Bridgewatch", "#d98a5b"), ("Caerleon", "#d95b5b"),
                  ("Black Market", "#e8b83a")]

        for i, (name, color) in enumerate(cities):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(name == self.current_city)
            btn.clicked.connect(lambda ch, c=name: self.change_city(c))
            btn.setStyleSheet(
                f"QPushButton {{ background: #07090c; color: #8b949e; border: 1px solid #1f242c; border-radius: 14px; padding: 6px 16px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background: #1f242c; color: white; }} QPushButton:checked {{ background: {color}; color: #07090c; border: 1px solid {color}; }}")
            self.city_group.addButton(btn, i)
            city_lay.addWidget(btn)
        city_lay.addStretch()
        filters_lay.addWidget(self.city_container)

        self.quality_container = QWidget()
        qual_lay = QHBoxLayout(self.quality_container)
        qual_lay.setContentsMargins(0, 0, 0, 0)
        qual_lay.addWidget(QLabel("Качество:",
                                  styleSheet="color: #e6edf3; font-weight: bold; margin-right: 10px; border: none; background: transparent;"))
        self.quality_group = QButtonGroup(self)
        quala = [(1, "Обыч"), (2, "Хор"), (3, "Выд"), (4, "Отл"), (5, "Шед")]
        for q_id, q_name in quala:
            btn = QPushButton(q_name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(q_id == self.current_quality)
            btn.clicked.connect(lambda ch, q=q_id: self.change_quality(q))
            btn.setStyleSheet(
                "QPushButton { background: #07090c; color: #8b949e; border: 1px solid #1f242c; border-radius: 14px; padding: 6px 16px; font-weight: bold; font-size: 11px; } QPushButton:hover { background: #1f242c; color: white; } QPushButton:checked { background: #00a3ff; color: #07090c; border: 1px solid #00a3ff; }")
            self.quality_group.addButton(btn, q_id)
            qual_lay.addWidget(btn)
        qual_lay.addStretch()
        filters_lay.addWidget(self.quality_container)
        cont.addWidget(self.top_filters_bg)

        self.stack = QStackedWidget()
        cont.addWidget(self.stack)

        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setStyleSheet("background: transparent; border: none;")
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.grid_scroll.setWidget(self.grid_widget)

        self.stack.addWidget(self.grid_scroll)
        self.setup_resources_ui()
        self.stack.addWidget(self.res_tabs)
        self.setup_production_ui()
        self.stack.addWidget(self.prod_widget)

    def on_global_settings_changed(self):
        if self.active_dialog: self.active_dialog.request_update()
        if self.stack.currentWidget() == self.prod_widget: self.recalc_production_totals()

    def change_city(self, c):
        self.current_city = c
        self.on_global_settings_changed()
        if self.stack.currentWidget() == self.res_tabs: self.fast_update_tree_prices()

    def change_quality(self, q):
        self.current_quality = q
        self.on_global_settings_changed()

    def add_to_production(self, res, qty):
        if not self.production_plans: self.create_new_plan()
        cart = self.production_plans[self.current_plan_idx]['cart']
        found_item = next((item for item in cart if item['id'] == res['id']), None)
        if found_item:
            found_item['qty'] += qty
        else:
            new_entry = {
                'id': res['id'], 'name': res['name'], 'tier': res['tier'], 'qty': qty,
                'sell_price': res.get('sell_price', 0), 'base_item_value': res.get('base_item_value', 10),
                'mats': res.get('mats', []), 'craft_fame': res.get('craft_fame', 0),
                'j_type': res.get('j_type', ''), 'best_journal': res.get('best_journal', ''), 'use_buy_order': False
            }
            cart.append(new_entry)
        show_notification("Добавлено", f"{res['name']} x{qty} в план.", self)
        self.render_production_sheet()

    def setup_production_ui(self):
        self.prod_widget = QWidget()
        lay = QVBoxLayout(self.prod_widget)
        lay.setContentsMargins(0, 0, 0, 0)

        h_lay = QHBoxLayout()
        h_lay.addWidget(QLabel("Заказы производства:",
                               styleSheet="color: white; font-size: 16px; font-weight: bold; margin-right: 15px; border: none; background: transparent;"))
        self.plan_tabs = QTabBar()
        self.plan_tabs.setTabsClosable(True)
        self.plan_tabs.setExpanding(False)
        self.plan_tabs.setMovable(True)
        self.plan_tabs.currentChanged.connect(self.on_plan_tab_changed)
        self.plan_tabs.tabCloseRequested.connect(self.on_plan_tab_closed)
        h_lay.addWidget(self.plan_tabs)

        b_new = QPushButton(qta.icon('fa5s.folder-plus', color='#00a3ff', color_active='white'), " Новый")
        b_new.setCursor(Qt.PointingHandCursor)
        b_new.setStyleSheet("""
            QPushButton { background: #111419; color: #00a3ff; border: 1px solid #1f242c; border-radius: 6px; padding: 10px 18px; font-weight: bold; } 
            QPushButton:hover { background: #1f242c; color: white; border-color: #30363d; }
            QPushButton:pressed { background: #07090c; border-color: #58a6ff; }
        """)
        b_new.clicked.connect(self.create_new_plan)

        b_save = QPushButton(qta.icon('fa5s.save', color='white'), " Сейв в базу")
        b_save.setCursor(Qt.PointingHandCursor)
        b_save.setStyleSheet("""
            QPushButton { background: #238636; color: white; border-radius: 6px; padding: 10px 18px; font-weight: bold; border: none; } 
            QPushButton:hover { background: #2ea043; }
            QPushButton:pressed { background: #1a6327; }
        """)
        b_save.clicked.connect(self.save_plans_to_disk)

        h_lay.addStretch()
        h_lay.addWidget(b_new)
        h_lay.addWidget(b_save)
        lay.addLayout(h_lay)

        splitter = QSplitter(Qt.Vertical)

        self.prod_scroll = QScrollArea()
        self.prod_scroll.setWidgetResizable(True)
        self.prod_scroll.setStyleSheet("background: transparent; border: none;")
        self.prod_scroll.verticalScrollBar().setSingleStep(15)

        self.prod_container = QWidget()
        self.prod_container.setStyleSheet("background: transparent;")
        self.prod_layout = QVBoxLayout(self.prod_container)
        self.prod_layout.setContentsMargins(0, 0, 10, 0)
        self.prod_layout.setSpacing(10)
        self.prod_layout.setAlignment(Qt.AlignTop)

        self.prod_scroll.setWidget(self.prod_container)
        splitter.addWidget(self.prod_scroll)

        sum_w = QWidget()
        s_lay = QVBoxLayout(sum_w)
        s_lay.setContentsMargins(0, 10, 0, 0)
        s_lay.addWidget(QLabel("Смета ресурсов и журналов (Редактируемо):",
                               styleSheet="color: #8b949e; font-weight: bold; font-size: 14px; border: none; background: transparent;"))

        self.prod_bom_table = QTableWidget()
        self.prod_bom_table.setColumnCount(4)
        self.prod_bom_table.setHorizontalHeaderLabels(["Ресурс", "Требуется", "Цена (Double click)", "Итого стоимость"])
        self.prod_bom_table.verticalHeader().setVisible(False)
        ModernTableHelper.style_table(self.prod_bom_table)
        self.prod_bom_table.setFocusPolicy(Qt.NoFocus)

        self.prod_bom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.prod_bom_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.prod_bom_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.prod_bom_table.setColumnWidth(2, 160)
        self.prod_bom_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.prod_bom_table.setColumnWidth(3, 160)

        self.prod_bom_table.itemChanged.connect(self.on_bom_price_changed)
        s_lay.addWidget(self.prod_bom_table)

        tot = QFrame()
        tot.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111419, stop:1 #07090c); border-radius: 8px; border: 1px solid #1f242c;")
        t_lay = QHBoxLayout(tot)
        t_lay.setContentsMargins(15, 12, 15, 12)
        self.lbl_prod_total = QLabel("ИТОГО Профит (Нет фокуса): 0 | Налог: 0")
        self.lbl_prod_total.setStyleSheet(
            "color: #3fb950; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        t_lay.addWidget(self.lbl_prod_total)
        t_lay.addStretch()

        b_info = QPushButton(qta.icon('fa5s.info-circle', color='#00a3ff', color_active='white'), "")
        b_info.setFixedSize(30, 30)
        b_info.setCursor(Qt.PointingHandCursor)
        b_info.setStyleSheet("""
            QPushButton { background: #1f242c; border: 1px solid #30363d; border-radius: 15px; } 
            QPushButton:hover { background: #00a3ff; border-color: #00a3ff; }
            QPushButton:pressed { background: #0077cc; }
        """)
        b_info.clicked.connect(self.show_journal_info)
        t_lay.addWidget(b_info)

        s_lay.addWidget(tot)
        splitter.addWidget(sum_w)
        lay.addWidget(splitter)

        self.plan_tabs.setStyleSheet("""
                    QTabBar::tab {
                        background: #111419;
                        color: #8b949e;
                        padding: 8px 20px;
                        border: 1px solid #1f242c;
                        border-bottom: none;
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                        margin-right: 2px;
                        min-width: 100px;
                    }
                    QTabBar::tab:selected {
                        background: #1f242c;
                        color: #58a6ff;
                        border-bottom: 2px solid #58a6ff;
                    }
                    QTabBar::close-button {
                        image: url(close_icon.png); /* Если иконки нет, Qt подставит стандартный крестик */
                        subcontrol-origin: margin;
                        subcontrol-position: right;
                        margin-right: 4px;
                    }
                    QTabBar::close-button:hover {
                        background: #f85149;
                        border-radius: 2px;
                    }
                    /* Стилизуем те самые "белые хрени" (кнопки прокрутки) */
                    QTabBar QToolButton {
                        background: #111419;
                        border: 1px solid #1f242c;
                        color: #58a6ff;
                        width: 20px;
                    }
                    QTabBar QToolButton:hover { background: #1f242c; }
                """)
        h_lay.addWidget(self.plan_tabs)
        h_lay.addWidget(QLabel("Закупка ресурсов в:", styleSheet="color: #8b949e; margin-left: 20px;"))
        self.buy_city_combo = QComboBox()
        self.buy_city_combo.addItems(["Lymhurst", "Martlock", "Thetford", "Fort Sterling", "Bridgewatch", "Caerleon"])
        self.buy_city_combo.setFixedWidth(120)
        self.buy_city_combo.setStyleSheet(
            "QComboBox { background: #111419; color: #58a6ff; border: 1px solid #1f242c; padding: 5px; }")
        self.buy_city_combo.currentTextChanged.connect(self.recalc_production_totals)
        h_lay.addWidget(self.buy_city_combo)

    def on_bom_price_changed(self, item):
        if item.column() == 2:
            iid = item.data(Qt.UserRole)
            if not iid: return
            val = item.text().replace(',', '').strip()
            if val.isdigit():
                self.dm.set_manual_price(self.current_city, iid, val)
            else:
                self.dm.clear_manual_price(self.current_city, iid)
            self.recalc_production_totals()

    def setup_resources_ui(self):
        self.res_tabs = QTabWidget()
        ModernTableHelper.style_tree(self.res_tabs)
        self.tab_mats = QWidget()
        m_lay = QVBoxLayout(self.tab_mats)
        m_lay.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.addWidget(QLabel("Управление базой материалов:",
                           styleSheet="color: white; font-weight: bold; border: none; background: transparent;"))

        b_glob = QPushButton(qta.icon('fa5s.globe', color='white'), " ГЛОБАЛЬНАЯ Синхронизация")
        b_glob.setStyleSheet("""
            QPushButton { background-color: #238636; color: white; border-radius: 6px; padding: 10px 18px; font-weight: bold; border: none; } 
            QPushButton:hover { background-color: #2ea043; }
            QPushButton:pressed { background-color: #1a6327; }
        """)
        b_glob.setCursor(Qt.PointingHandCursor)
        b_glob.clicked.connect(self.sync_resources)

        h.addStretch()
        h.addWidget(b_glob)
        m_lay.addLayout(h)

        self.mats_tree = QTreeWidget()
        self.mats_tree.setColumnCount(5)
        self.mats_tree.setHeaderLabels(["Название", "Тир", "Синх", "Цена API / Ручная", "Иконка"])
        self.mats_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mats_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.mats_tree.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.mats_tree.setColumnWidth(2, 90)
        self.mats_tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.mats_tree.setColumnWidth(3, 140)
        ModernTableHelper.style_tree(self.mats_tree)
        m_lay.addWidget(self.mats_tree)

        self.tab_arts = QWidget()
        a_lay = QVBoxLayout(self.tab_arts)
        a_lay.setContentsMargins(0, 0, 0, 0)
        self.arts_tree = QTreeWidget()
        self.arts_tree.setColumnCount(5)
        self.arts_tree.setHeaderLabels(["Артефакт", "Тир", "Синх", "Цена API / Ручная", "Иконка"])
        self.arts_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.arts_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.arts_tree.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.arts_tree.setColumnWidth(2, 90)
        self.arts_tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.arts_tree.setColumnWidth(3, 140)
        ModernTableHelper.style_tree(self.arts_tree)
        a_lay.addWidget(self.arts_tree)

        self.tab_journals = QWidget()
        j_lay = QVBoxLayout(self.tab_journals)
        j_lay.setContentsMargins(0, 0, 0, 0)
        self.journals_tree = QTreeWidget()
        self.journals_tree.setColumnCount(5)
        self.journals_tree.setHeaderLabels(["Журнал", "Тир", "Синх", "Цена API / Ручная", "Иконка"])
        self.journals_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.journals_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.journals_tree.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.journals_tree.setColumnWidth(2, 90)
        self.journals_tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.journals_tree.setColumnWidth(3, 140)
        ModernTableHelper.style_tree(self.journals_tree)
        j_lay.addWidget(self.journals_tree)

        self.res_tabs.addTab(self.tab_mats, "Ресурсы")
        self.res_tabs.addTab(self.tab_arts, "Артефакты")
        self.res_tabs.addTab(self.tab_journals, "Журналы")

    def sync_specific_folder(self, ids, btn):
        btn.setEnabled(False)
        btn.setText("")
        spin = qta.Spin(btn)
        btn.setIcon(qta.icon('fa5s.sync-alt', color='white', animation=spin))
        worker = QuickParseWorker(ids, btn)
        worker.signals.finished.connect(self.on_quick_sync_finished)
        self.thread_pool.start(worker)

    @Slot(object)
    def on_quick_sync_finished(self, btn):
        self.dm.refresh_prices_cache()
        self.fast_update_tree_prices()
        btn.setEnabled(True)
        btn.setIcon(QIcon())
        btn.setText("Парсить")


    def load_resources_trees(self):
        self.mats_tree.clear()
        self.arts_tree.clear()
        self.journals_tree.clear()

        btn_style_tree = """
                QPushButton { background-color: #238636; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px; border: none; } 
                QPushButton:hover { background-color: #2ea043; }
                QPushButton:pressed { background-color: #1a6327; }
            """

        # --- ДЕРЕВО МАТЕРИАЛОВ ---
        m_groups = {"Доски": "PLANKS", "Слитки": "METALBAR", "Кожа": "LEATHER", "Ткань": "CLOTH"}
        for name, tag in m_groups.items():
            parent = QTreeWidgetItem(self.mats_tree, [name])
            btn_sync = QPushButton(qta.icon('fa5s.sync-alt', color='white'), " Обновить ветку")
            btn_sync.setStyleSheet(btn_style_tree)
            btn_sync.setCursor(Qt.PointingHandCursor)
            btn_sync.clicked.connect(lambda checked, t=tag, tree=self.mats_tree: self.sync_specific_branch(t, tree))
            self.mats_tree.setItemWidget(parent, 2, btn_sync)

            items = []
            for it in self.dm.items_cache.values():
                item_id = str(it.get('item_id') or it.get('id', ''))
                if item_id.startswith(('T4', 'T5', 'T6', 'T7', 'T8')) and f"_{tag}" in item_id:
                    if not any(bad in item_id for bad in ["_ARMOR_", "_HEAD_", "_SHOES_", "ARTEFACT"]):
                        items.append(it)

            # Сортируем по ID внутри словаря
            for it in sorted(items, key=lambda x: str(x.get('item_id') or x.get('id', ''))):
                self._add_res_row(parent, it)

        # --- ДЕРЕВО АРТЕФАКТОВ ---
        a_groups = {
            "Оружие": ["_MAIN_", "_2H_"],
            "Броня": ["_ARMOR_", "_HEAD_", "_SHOES_"],
            "Прочее": ["_CAPE_", "_BAG_"]
        }

        all_arts = []
        for it in self.dm.items_cache.values():
            item_id = str(it.get('item_id') or it.get('id', ''))
            if "ARTEFACT" in item_id and item_id.startswith(('T4', 'T5', 'T6', 'T7', 'T8')):
                all_arts.append(it)

        for name, tags in a_groups.items():
            parent = QTreeWidgetItem(self.arts_tree, [f"Артефакты: {name}"])
            btn_sync = QPushButton(qta.icon('fa5s.sync-alt', color='white'), " Обновить ветку")
            btn_sync.setMinimumWidth(130)
            btn_sync.setCursor(Qt.PointingHandCursor)
            btn_sync.setStyleSheet(btn_style_tree)
            btn_sync.clicked.connect(lambda checked, t=tags, tree=self.arts_tree: self.sync_specific_branch(t, tree))
            self.arts_tree.setItemWidget(parent, 2, btn_sync)

            items = [it for it in all_arts if any(t in str(it.get('item_id') or it.get('id', '')) for t in tags)]
            for it in sorted(items, key=lambda x: str(x.get('item_id') or x.get('id', ''))):
                self._add_res_row(parent, it)

        # --- ДЕРЕВО ЖУРНАЛОВ ---
        j_parent = QTreeWidgetItem(self.journals_tree, ["Все журналы рабочих"])
        btn_sync_j = QPushButton(qta.icon('fa5s.sync-alt', color='white'), " Обновить все")
        btn_sync_j.setMinimumWidth(150)
        btn_sync_j.setCursor(Qt.PointingHandCursor)
        btn_sync_j.setStyleSheet(btn_style_tree)
        btn_sync_j.clicked.connect(
            lambda checked, t="_JOURNAL_", tree=self.journals_tree: self.sync_specific_branch(t, tree))
        self.journals_tree.setItemWidget(j_parent, 2, btn_sync_j)

        journals = []
        for it in self.dm.items_cache.values():
            item_id = str(it.get('item_id') or it.get('id', ''))
            if "_JOURNAL_" in item_id and item_id.startswith(('T4', 'T5', 'T6', 'T7', 'T8')):
                journals.append(it)

        clean_journals = [it for it in journals if
                          "_EMPTY" in str(it.get('item_id') or it.get('id', '')) or "_FULL" in str(
                              it.get('item_id') or it.get('id', ''))]

        for it in sorted(clean_journals, key=lambda x: str(x.get('item_id') or x.get('id', ''))):
            self._add_res_row(j_parent, it)

        self.mats_tree.expandAll()

    def sync_specific_branch(self, tag_or_tags, tree):
        ids_to_update = []
        root = tree.invisibleRootItem()
        tags = tag_or_tags if isinstance(tag_or_tags, list) else [tag_or_tags]

        for i in range(root.childCount()):
            parent = root.child(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                iid = child.data(0, Qt.UserRole)
                if iid and any(t in iid for t in tags): ids_to_update.append(iid)

        if not ids_to_update: return

        self.prog_dlg = ModernProgressDialog("Синхронизация...", len(ids_to_update), self)
        self.prog_dlg.show()

        from market_api import MarketFetcher
        worker = MarketFetcher(ids_to_update, location=self.current_city)
        worker.signals.progress.connect(lambda cur, tot: self.prog_dlg.setValue(cur))
        worker.signals.finished.connect(self.on_global_sync_finished)
        self.thread_pool.start(worker)

    def _add_res_row(self, p, it_obj):
        # --- БЕЗОПАСНОЕ ЧТЕНИЕ СЛОВАРЯ ---
        item_id = str(it_obj.get('item_id') or it_obj.get('id', ''))
        item_name = str(it_obj.get('name') or item_id)

        c = QTreeWidgetItem(p)
        c.setData(0, Qt.UserRole, item_id)

        c.setText(0, f"  {item_name}")

        tn = item_id.split('_')[0].replace('T', '')
        en = item_id.split('@')[1] if '@' in item_id else "0"
        c.setText(1, f"{tn}.{en}")

        ap = self.dm.get_price(self.current_city, item_id)
        mp = self.dm.manual_prices.get(f"{self.current_city}:{item_id}", "")

        c.setText(3, str(mp) if mp else f"{float(ap):,.0f}")
        c.setForeground(3, QColor("#33b5ff") if mp else QColor("#8b949e"))
        c.setFlags(c.flags() | Qt.ItemIsEditable)

        pix = self.get_local_icon(item_id)
        if pix:
            c.setIcon(4, QIcon(pix.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        else:
            self.icon_downloader.request_icon(item_id)

        self.res_icons[item_id] = c

    def fast_update_tree_prices(self):
        for tree in [self.mats_tree, self.arts_tree, self.journals_tree]:
            for i in range(tree.topLevelItemCount()):
                parent = tree.topLevelItem(i)
                for j in range(parent.childCount()):
                    child = parent.child(j)
                    iid = child.data(0, Qt.UserRole)
                    if iid:
                        ap = self.dm.get_price(self.current_city, iid)
                        mp = self.dm.manual_prices.get(f"{self.current_city}:{iid}", "")
                        child.setText(3, str(mp) if mp else f"{float(ap or 0):,.0f}")
                        child.setForeground(3, QColor("#33b5ff") if mp else QColor("#8b949e"))

    def load_plans_from_disk(self):
        if os.path.exists("erp_sessions.json"):
            try:
                with open("erp_sessions.json", "r", encoding="utf-8") as f:
                    self.production_plans = json.load(f)
                for p in self.production_plans: self.plan_tabs.addTab(p['name'])
            except:
                self.production_plans = [{"name": "Default", "cart": []}];
                self.plan_tabs.addTab("Default")
        else:
            self.production_plans = [{"name": "Default", "cart": []}]; self.plan_tabs.addTab("Default")

    def on_plan_tab_changed(self, idx):
        self.current_plan_idx = idx
        self.render_production_sheet() if idx >= 0 else None

    def on_plan_tab_closed(self, idx):
        if len(self.production_plans) > 1:
            del self.production_plans[idx]
            self.plan_tabs.removeTab(idx)
            if self.current_plan_idx >= len(self.production_plans): self.current_plan_idx = len(
                self.production_plans) - 1
            self.render_production_sheet()

    def create_new_plan(self):
        dialog = ModernInputDialog("Новая корзина", "Название", self)
        if dialog.exec():
            n = dialog.get_text().strip() or f"Plan {len(self.production_plans) + 1}"
            self.production_plans.append({"name": n, "cart": []})
            self.plan_tabs.addTab(n)
            self.plan_tabs.setCurrentIndex(self.plan_tabs.count() - 1)

    def save_plans_to_disk(self):

        try:

            self.dm.sb.table('saved_plans').upsert({
                "id": "my_erp_profile",  # Твой уникальный ID профиля
                "data": self.production_plans
            }).execute()

            show_notification("Облачный Сейв", "Твои планы успешно сохранены в Supabase!", self)
        except Exception as e:
            show_notification("Ошибка сохранения", str(e), self)

    def remove_prod_item(self, idx):
        del self.production_plans[self.current_plan_idx]['cart'][idx]
        self.render_production_sheet()

    def on_cart_qty_changed(self, idx, val):
        self.production_plans[self.current_plan_idx]['cart'][idx]['qty'] = val
        self.recalc_production_totals()

    def on_cart_price_changed(self, idx, val):
        self.production_plans[self.current_plan_idx]['cart'][idx]['sell_price'] = int(val or 0)
        self.recalc_production_totals()

    def on_cart_buy_changed(self, idx, val):
        self.production_plans[self.current_plan_idx]['cart'][idx]['use_buy_order'] = (val == 1)
        self.recalc_production_totals()

    def recalc_production_totals(self):
        if not self.production_plans: return
        import math


        if not hasattr(self, 'manual_market_prices'):
            self.manual_market_prices = {}

        # 2. Константы
        JOURNAL_CAPACITIES = {4: 3600, 5: 7200, 6: 14400, 7: 28380, 8: 58590}
        RES_IV_BASE = {4: 4, 5: 16, 6: 64, 7: 256, 8: 1024}
        RES_FAME_BASE = {4: 30, 5: 90, 6: 270, 7: 810, 8: 2430}
        FOCUS_BASE = {"HEAD": 150, "ARMOR": 300, "SHOES": 150, "WEAPON": 300}

        # 3. Города
        buy_city = self.buy_city_combo.currentText()
        sell_city = self.current_city

        try:
            global_tax_rate = float(self.tax_input.text() or 990)
            r_nf = float(self.rrr_nf_input.text().replace(',', '.') or 15.2)
            r_f = float(self.rrr_f_input.text().replace(',', '.') or 43.5)
        except ValueError:
            global_tax_rate, r_nf, r_f = 990, 15.2, 43.5

        is_premium = self.prem_cb.isChecked()
        market_tax = 0.065 if is_premium else 0.105
        use_journals = self.journal_cb.isChecked()

        total_net_p_nf, total_net_p_f, total_station_fees = 0, 0, 0
        materials_summary, journals_summary = {}, {}


        for i in range(self.prod_layout.count()):
            card = self.prod_layout.itemAt(i).widget()
            if not isinstance(card, ProductionItemCard): continue

            it = card.data
            qty = int(it.get('qty', 1))
            item_id = it['id']


            try:
                t_parts = str(it.get('tier', '4.0')).split('.')
                tier = int(t_parts[0])
                enchant = int(t_parts[1]) if len(t_parts) > 1 else 0
            except Exception:
                tier, enchant = 4, 0


            manual_city_data = self.manual_market_prices.get(sell_city, {})
            manual_price = manual_city_data.get(item_id)

            if manual_price is not None:
                raw_sell_price = manual_price
                card.price_edit.setStyleSheet(
                    "QLineEdit { background: #07090c; color: #58a6ff; font-weight: bold; border: 1px solid #1f242c; padding: 5px; border-radius: 4px; }"
                )
            else:
                raw_sell_price = self.dm.get_price(sell_city, item_id)
                card.price_edit.setStyleSheet(
                    "QLineEdit { background: #07090c; color: white; border: 1px solid #1f242c; padding: 5px; border-radius: 4px; }"
                )


            try:
                current_sell_price = int(float(raw_sell_price)) if raw_sell_price else 0
            except (ValueError, TypeError):
                current_sell_price = 0

            # Г) Обновление текста в UI без зацикливания
            card.price_edit.blockSignals(True)
            card.price_edit.setText(str(current_sell_price))
            card.price_edit.blockSignals(False)

            # Д) Расчет IV, Fame, Focus
            mat_count = sum(m['amount'] for m in it.get('mats', []))
            item_iv = mat_count * RES_IV_BASE.get(tier, 4) * (2 ** enchant)
            item_fame = mat_count * RES_FAME_BASE.get(tier, 30) * (2 ** enchant)

            focus_type = "ARMOR" if "ARMOR" in item_id else "HEAD" if "HEAD" in item_id else "SHOES"
            base_focus = FOCUS_BASE.get(focus_type, 200)
            tier_focus_mod = {4: 1, 5: 1.4, 6: 2, 7: 2.8, 8: 4}.get(tier, 1)
            total_focus_for_card = int(base_focus * tier_focus_mod * qty)
            card.focus_lbl.setText(f"Фокус: {total_focus_for_card:,}")


            fee_per_unit = (item_iv * 0.1125 / 100) * global_tax_rate


            unit_mat_cost = 0
            for m in it.get('mats', []):
                price_mod = 1.015 if it.get('use_buy_order') else 1.0
                m_price = self.dm.get_price(buy_city, m['id']) * price_mod
                unit_mat_cost += m_price * m['amount']

                if m['id'] not in materials_summary:
                    materials_summary[m['id']] = {'amount': 0, 'price': m_price}
                materials_summary[m['id']]['amount'] += m['amount'] * qty


            journal_profit_unit = 0
            if use_journals and it.get('j_type'):
                cap = JOURNAL_CAPACITIES.get(tier, 3600)
                fill_rate = item_fame / cap
                j_id_empty = f"T{tier}_JOURNAL_{it['j_type']}_EMPTY"
                j_id_full = f"T{tier}_JOURNAL_{it['j_type']}_FULL"
                p_empty = self.dm.get_price(self.current_city, j_id_empty)
                p_full = self.dm.get_price(self.current_city, j_id_full)
                one_j_profit = (p_full * (1 - market_tax)) - p_empty
                journal_profit_unit = fill_rate * one_j_profit

                j_key = f"T{tier}_JOURNAL_{it['j_type']}"
                journals_summary[j_key] = journals_summary.get(j_key, 0) + (fill_rate * qty)


            from calc_engine import calculate_craft_profit
            res_nf = calculate_craft_profit(current_sell_price, unit_mat_cost, r_nf, fee_per_unit, market_tax * 100,
                                            item_fame,
                                            {"profit_val": journal_profit_unit})
            res_f = calculate_craft_profit(current_sell_price, unit_mat_cost, r_f, fee_per_unit, market_tax * 100,
                                           item_fame,
                                           {"profit_val": journal_profit_unit})

            card.profit_nf_lbl.setText(f"{int(res_nf['net_profit'] * qty):,}")
            card.profit_f_lbl.setText(f"{int(res_f['net_profit'] * qty):,}")

            total_net_p_nf += res_nf['net_profit'] * qty
            total_net_p_f += res_f['net_profit'] * qty
            total_station_fees += fee_per_unit * qty


        self.lbl_prod_total.setText(
            f"ПРИБЫЛЬ: (Без) {int(total_net_p_nf):,} | (Фок) {int(total_net_p_f):,} | НАЛОГ СТАНКОВ: {int(total_station_fees):,}")

        tips_text = "Необходимо журналов:\n"
        if journals_summary:
            for k, v in journals_summary.items():
                tips_text += f"• {k}: {math.ceil(v)} шт.\n"
        else:
            tips_text = "Журналы не требуются."
        self.current_journal_report = tips_text

        self.update_bom_table(materials_summary)

    def update_bom_table(self, materials_agg):
        self.prod_bom_table.blockSignals(True)
        self.prod_bom_table.setRowCount(len(materials_agg))

        for row, (mid, data) in enumerate(materials_agg.items()):
            self.prod_bom_table.setItem(row, 0, QTableWidgetItem(mid))
            self.prod_bom_table.setItem(row, 1, QTableWidgetItem(f"{data['amount']:,}"))

            p_item = QTableWidgetItem(f"{int(data['price']):,}")
            p_item.setData(Qt.UserRole, mid)
            p_item.setForeground(QColor("#33b5ff"))
            self.prod_bom_table.setItem(row, 2, p_item)

            total_cost = data['amount'] * data['price']
            self.prod_bom_table.setItem(row, 3, QTableWidgetItem(f"{int(total_cost):,}"))

        self.prod_bom_table.blockSignals(False)

    def remove_prod_item_by_id(self, item_id):
        cart = self.production_plans[self.current_plan_idx]['cart']
        self.production_plans[self.current_plan_idx]['cart'] = [i for i in cart if i['id'] != item_id]
        self.render_production_sheet()
        show_notification("Удалено", f"Предмет убран из текущего плана.", self)

    def render_production_sheet(self):
        while self.prod_layout.count():
            child = self.prod_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        cart = self.production_plans[self.current_plan_idx]['cart']
        if not cart:
            self.lbl_prod_total.setText("План пуст.")
            self.prod_bom_table.setRowCount(0)
            return

        for item_data in cart:
            card = ProductionItemCard(item_data, self)
            card.dataChanged.connect(self.recalc_production_totals)
            self.prod_layout.addWidget(card)

        self.recalc_production_totals()

    def show_journal_info(self):
        show_notification("Журналы", self.current_journal_report, self)

    def load_db(self, tags):

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        clean_items = []
        seen = set()
        is_tool_tab = any("TOOL" in t or "GATHERER" in t for t in tags)


        for item_id, it in self.dm.items_cache.items():
            item_id = str(item_id)

            if not item_id.startswith(('T4', 'T5', 'T6', 'T7', 'T8')): continue
            if "ARTEFACT" in item_id or "TOKEN" in item_id or "TRASH" in item_id: continue

            if not is_tool_tab:
                if "_TOOL_" in item_id or "_GATHERER_" in item_id: continue
            else:
                if "_TOOL_" not in item_id and "_GATHERER_" not in item_id: continue

            if not any(tag in item_id for tag in tags): continue

            fid = item_id.split('@')[0]
            for t in ['T4_', 'T5_', 'T6_', 'T7_', 'T8_']:
                fid = fid.replace(t, '')

            if fid in seen: continue
            seen.add(fid)

            item_name = str(it.get('name', ''))
            clean_items.append({'raw': it, 'id': item_id, 'name': item_name})


        row, col = 0, 0
        for item_data in clean_items:
            it = item_data['raw']
            item_id = item_data['id']
            item_name = item_data['name']

            n_ru = "Нет перевода"
            for attr in ['name_ru', 'localized_name', 'ru_name', 'display_name', 'localized_names']:
                if attr in it:
                    val = it.get(attr)
                    if isinstance(val, dict):
                        n_ru = val.get('RU-RU', "")
                    elif isinstance(val, str) and val:
                        n_ru = val
                    break

            if n_ru == item_name or not n_ru:
                n_ru = ""

            w = ItemWidget(item_name or item_id, n_ru, item_id, self)
            w.setMinimumHeight(85)
            self.grid_layout.addWidget(w, row, col)

            col += 1
            if col > 1:
                col = 0
                row += 1

    def do_filter(self, t):
        q = t.lower()

        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            if hasattr(widget, 'item_id'):
                # Безопасное чтение строк (защита от None)
                n_en = (widget.name_en or "").lower()
                n_ru = (widget.name_ru or "").lower()
                i_id = (widget.item_id or "").lower()

                match = q in n_en or q in n_ru or q in i_id
                widget.setHidden(not match)


        for tree in [self.mats_tree, self.arts_tree, self.journals_tree]:
            if not tree: continue
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                parent = root.child(i)
                parent_match = False
                for j in range(parent.childCount()):
                    child = parent.child(j)
                    text = (child.text(0) + " " + (child.data(0, Qt.UserRole) or "")).lower()
                    if q in text:
                        child.setHidden(False)
                        parent_match = True
                    else:
                        child.setHidden(True)

                if parent_match or q in parent.text(0).lower():
                    parent.setHidden(False)
                    if q: parent.setExpanded(True)
                else:
                    parent.setHidden(True)

    def start_calc(self, iid, cells, calc_id):
        self.calc_worker.request_calc(iid, cells, self.current_city, int(self.tax_input.text() or 0),
                                      self.prem_cb.isChecked(), self.journal_cb.isChecked(),
                                      float(self.rrr_nf_input.text().replace(',', '.') or 15.2) / 100,
                                      float(self.rrr_f_input.text().replace(',', '.') or 43.5) / 100,
                                      self.current_quality, calc_id)

    def on_calc_done(self, iid, data, calc_id):
        if self.active_dialog and self.active_dialog.current_calc_id == calc_id: self.active_dialog.render_results(data)

    def sync_resources(self):
        """Глобальная синхронизация всех цен без зависаний UI"""
        all_ids = list(self.dm.items_cache.keys())
        if not all_ids: return

        self.prog_dlg = ModernProgressDialog("Глобальное обновление цен...", len(all_ids), self)

        from market_api import MarketFetcher
        self.sync_worker = MarketFetcher(all_ids, location=self.current_city)

        # Сигналы прогресса и успешного завершения
        self.sync_worker.signals.progress.connect(lambda cur, tot: self.prog_dlg.setValue(cur))
        self.sync_worker.signals.finished.connect(self.on_global_sync_finished)

        # ФИКС ЗАВИСАНИЯ: Если от сервера пришел сброс или 502, закрываем окно
        self.sync_worker.signals.error.connect(self.on_sync_error)

        # ФИКС ОТМЕНЫ: Если юзер нажал "Отмена"
        self.prog_dlg.rejected.connect(self.cancel_sync_worker)

        self.thread_pool.start(self.sync_worker)
        self.prog_dlg.show()

    def on_sync_error(self, err_msg):
        """Обработка обрыва связи с сервером Альбиона"""
        if hasattr(self, 'prog_dlg') and self.prog_dlg:
            self.prog_dlg.close()  # Жестко убиваем окно загрузки
        show_notification("Ошибка сервера", str(err_msg), self)
        # Сохраняем те цены, которые успели скачаться до обрыва
        self.dm.refresh_prices_cache()
        self.fast_update_tree_prices()

    def cancel_sync_worker(self):
        """Прерывание парсинга по кнопке пользователя"""
        if hasattr(self, 'sync_worker') and self.sync_worker:
            # Даем сигнал воркеру остановиться
            self.sync_worker.running = False

            # Записываем в интерфейс те крохи данных, что успели прийти
        self.dm.refresh_prices_cache()
        self.fast_update_tree_prices()
        show_notification("Отменено", "Сохранены цены, скачанные до отмены.", self)

    def on_global_sync_finished(self, final_prices):
        # Закрываем окно загрузки
        if hasattr(self, 'prog_dlg') and self.prog_dlg:
            self.prog_dlg.accept()


        self.dm.update_parsed_prices(self.current_city, final_prices)


        self.fast_update_tree_prices()

        if self.stack.currentWidget() == self.prod_widget:
            self.recalc_production_totals()

        show_notification("Синхронизация завершена", f"Успешно обновлено {len(final_prices)} цен в облаке.", self)

    def on_icon(self, iid, path):

        if iid in self.widgets:
            self.widgets[iid].set_loaded_icon(QPixmap(path))


        if self.active_dialog and hasattr(self.active_dialog, 'update_icons'):
            self.active_dialog.update_icons(iid, path)


        if self.stack.currentWidget() == self.prod_widget:
            for i in range(self.prod_layout.count()):
                card = self.prod_layout.itemAt(i).widget()
                if hasattr(card, 'data') and card.data['id'] == iid:
                    card.icon_lbl.setPixmap(QPixmap(path).scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def closeEvent(self, e):
        self.calc_worker.running = False
        self.icon_downloader.running = False
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = CraftHelpApp()
    w.show()
    sys.exit(app.exec())