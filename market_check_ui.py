import sys
import json
import os
import time
import random
import keyboard
import pyautogui
import qtawesome as qta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
                               QTreeWidgetItem, QGroupBox, QCheckBox, QPushButton,
                               QLineEdit, QLabel, QMessageBox, QHeaderView, QInputDialog,
                               QTreeWidgetItemIterator)
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap

# =========================================================
# ИМПОРТ ТВОЕЙ БАЗЫ
# =========================================================
try:
    from data_manager import DataManager
except ImportError:
    pass

# =========================================================
# ХАРДКОД-СЛОВАРЬ (Перевод ID -> Названия как в игре)
# =========================================================
ALBION_EN_NAMES = {
    # CLOTH (Ткань)
    "HEAD_CLOTH_SET1": "Scholar Cowl", "ARMOR_CLOTH_SET1": "Scholar Robe", "SHOES_CLOTH_SET1": "Scholar Sandals",
    "HEAD_CLOTH_SET2": "Cleric Cowl", "ARMOR_CLOTH_SET2": "Cleric Robe", "SHOES_CLOTH_SET2": "Cleric Sandals",
    "HEAD_CLOTH_SET3": "Mage Cowl", "ARMOR_CLOTH_SET3": "Mage Robe", "SHOES_CLOTH_SET3": "Mage Sandals",
    "HEAD_CLOTH_ROYAL": "Royal Cowl", "ARMOR_CLOTH_ROYAL": "Royal Robe", "SHOES_CLOTH_ROYAL": "Royal Sandals",
    "HEAD_CLOTH_KEEPER": "Druid Cowl", "ARMOR_CLOTH_KEEPER": "Druid Robe", "SHOES_CLOTH_KEEPER": "Druid Sandals",
    "HEAD_CLOTH_HELL": "Fiend Cowl", "ARMOR_CLOTH_HELL": "Fiend Robe", "SHOES_CLOTH_HELL": "Fiend Sandals",
    "HEAD_CLOTH_MORGANA": "Cultist Cowl", "ARMOR_CLOTH_MORGANA": "Cultist Robe",
    "SHOES_CLOTH_MORGANA": "Cultist Sandals",
    "HEAD_CLOTH_AVALON": "Cowl of Purity", "ARMOR_CLOTH_AVALON": "Robe of Purity",
    "SHOES_CLOTH_AVALON": "Sandals of Purity",
    "HEAD_CLOTH_FEY": "Feyscale Hat", "ARMOR_CLOTH_FEY": "Feyscale Robe", "SHOES_CLOTH_FEY": "Feyscale Shoes",

    # LEATHER (Кожа)
    "HEAD_LEATHER_SET1": "Mercenary Hood", "ARMOR_LEATHER_SET1": "Mercenary Jacket",
    "SHOES_LEATHER_SET1": "Mercenary Shoes",
    "HEAD_LEATHER_SET2": "Hunter Hood", "ARMOR_LEATHER_SET2": "Hunter Jacket", "SHOES_LEATHER_SET2": "Hunter Shoes",
    "HEAD_LEATHER_SET3": "Assassin Hood", "ARMOR_LEATHER_SET3": "Assassin Jacket",
    "SHOES_LEATHER_SET3": "Assassin Shoes",
    "HEAD_LEATHER_ROYAL": "Royal Hood", "ARMOR_LEATHER_ROYAL": "Royal Jacket", "SHOES_LEATHER_ROYAL": "Royal Shoes",
    "HEAD_LEATHER_UNDEAD": "Stalker Hood", "ARMOR_LEATHER_UNDEAD": "Stalker Jacket",
    "SHOES_LEATHER_UNDEAD": "Stalker Shoes",
    "HEAD_LEATHER_HELL": "Hellion Hood", "ARMOR_LEATHER_HELL": "Hellion Jacket", "SHOES_LEATHER_HELL": "Hellion Shoes",
    "HEAD_LEATHER_MORGANA": "Specter Hood", "ARMOR_LEATHER_MORGANA": "Specter Jacket",
    "SHOES_LEATHER_MORGANA": "Specter Shoes",
    "HEAD_LEATHER_AVALON": "Hood of Tenacity", "ARMOR_LEATHER_AVALON": "Jacket of Tenacity",
    "SHOES_LEATHER_AVALON": "Shoes of Tenacity",
    "HEAD_LEATHER_FEY": "Mistwalker Hood", "ARMOR_LEATHER_FEY": "Mistwalker Jacket",
    "SHOES_LEATHER_FEY": "Mistwalker Shoes",

    # PLATE (Латы)
    "HEAD_PLATE_SET1": "Soldier Helmet", "ARMOR_PLATE_SET1": "Soldier Armor", "SHOES_PLATE_SET1": "Soldier Boots",
    "HEAD_PLATE_SET2": "Knight Helmet", "ARMOR_PLATE_SET2": "Knight Armor", "SHOES_PLATE_SET2": "Knight Boots",
    "HEAD_PLATE_SET3": "Guardian Helmet", "ARMOR_PLATE_SET3": "Guardian Armor", "SHOES_PLATE_SET3": "Guardian Boots",
    "HEAD_PLATE_ROYAL": "Royal Helmet", "ARMOR_PLATE_ROYAL": "Royal Armor", "SHOES_PLATE_ROYAL": "Royal Boots",
    "HEAD_PLATE_UNDEAD": "Graveguard Helmet", "ARMOR_PLATE_UNDEAD": "Graveguard Armor",
    "SHOES_PLATE_UNDEAD": "Graveguard Boots",
    "HEAD_PLATE_HELL": "Demon Helmet", "ARMOR_PLATE_HELL": "Demon Armor", "SHOES_PLATE_HELL": "Demon Boots",
    "HEAD_PLATE_KEEPER": "Judicator Helmet", "ARMOR_PLATE_KEEPER": "Judicator Armor",
    "SHOES_PLATE_KEEPER": "Judicator Boots",
    "HEAD_PLATE_AVALON": "Helmet of Valor", "ARMOR_PLATE_AVALON": "Armor of Valor",
    "SHOES_PLATE_AVALON": "Boots of Valor",
    "HEAD_PLATE_FEY": "Duskweaver Helmet", "ARMOR_PLATE_FEY": "Duskweaver Armor", "SHOES_PLATE_FEY": "Duskweaver Boots",
}


# =========================================================
# ПОТОК ЭМУЛЯЦИИ КЛАВИАТУРЫ И МЫШИ (БОТ)
# =========================================================
class MarketBotThread(QThread):
    progress_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.running = True

    def run(self):
        self.progress_signal.emit("⏳ Наведи курсор на поиск и жми F5... (ESC-отмена)")

        while self.running:
            if keyboard.is_pressed('esc'):
                self.finish_bot("Отменено (ESC)")
                return
            if keyboard.is_pressed('f5'):
                break
            time.sleep(0.05)

        search_x, search_y = pyautogui.position()
        self.progress_signal.emit("🚀 Погнали! (ESC для остановки)")
        time.sleep(0.3)

        for idx, item in enumerate(self.queue):
            if not self.running or keyboard.is_pressed('esc'):
                self.finish_bot("Остановлено (ESC)")
                return

            self.progress_signal.emit(f"📝 ({idx + 1}/{len(self.queue)}): {item}")

            pyautogui.click(search_x, search_y)
            time.sleep(0.2)

            keyboard.send('ctrl+a')
            time.sleep(0.1)
            keyboard.send('backspace')
            keyboard.send('delete')
            time.sleep(0.2)

            item_lower = item.lower()
            safe_string = "".join(c for c in item_lower if ord(c) < 128)

            for char in safe_string:
                if keyboard.is_pressed('esc'):
                    self.finish_bot("Остановлено (ESC)")
                    return

                try:
                    if char == ' ':
                        keyboard.send('space')
                    else:
                        keyboard.send(char)
                except ValueError:
                    pass

                time.sleep(random.uniform(0.12, 0.25))

            time.sleep(random.uniform(2.0, 3.0))

        self.finish_bot("✅ Очередь завершена!")

    def finish_bot(self, msg):
        self.progress_signal.emit(msg)
        self.finished_signal.emit()


# =========================================================
# ИНТЕРФЕЙС ВКЛАДКИ
# =========================================================
class MarketCheckWidget(QWidget):
    def __init__(self, main_app=None):
        super().__init__()
        self.app = main_app
        self.setStyleSheet("background-color: #0d1117; color: #c9d1d9; font-family: Segoe UI, Arial;")

        try:
            self.dm = DataManager()
        except:
            self.dm = None
            print("⚠️ DataManager не загружен. Работаем без базы.")

        self.icons_cache = {}
        self.init_ui()
        if self.dm:
            self.populate_catalog()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        left_header = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search: Filter by item name...")
        self.search_input.textChanged.connect(self.filter_catalog)
        self.search_input.setStyleSheet("""
            QLineEdit { background: #111419; color: white; border: 1px solid #1f242c; 
                        padding: 10px; border-radius: 6px; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #58a6ff; }
        """)
        search_icon = qta.icon('fa5s.search', color='#8b949e')
        self.search_input.addAction(search_icon, QLineEdit.LeadingPosition)
        left_header.addWidget(self.search_input)

        btn_clear_search = QPushButton("Clear")
        btn_clear_search.clicked.connect(self.search_input.clear)
        btn_clear_search.setStyleSheet("background: transparent; color: #8b949e; border: none; font-weight: bold;")
        left_header.addWidget(btn_clear_search)
        left_panel.addLayout(left_header)

        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setHeaderHidden(True)
        self.catalog_tree.setColumnCount(2)
        self.catalog_tree.header().setStretchLastSection(False)
        self.catalog_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.catalog_tree.setColumnWidth(1, 50)
        self.catalog_tree.setStyleSheet(self.get_tree_stylesheet())
        self.catalog_tree.setIconSize(QSize(30, 30))
        left_panel.addWidget(self.catalog_tree)

        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(15)

        self.t_checks = {}
        tier_layout = QHBoxLayout()
        tier_layout.setContentsMargins(5, 5, 5, 5)
        for t in range(4, 9):
            cb = QCheckBox(f"T{t}")
            cb.setChecked(t in [4, 5, 6])
            cb.setStyleSheet("QCheckBox { color: #c9d1d9; font-weight: bold; }")
            self.t_checks[t] = cb
            tier_layout.addWidget(cb)
        tier_box = QGroupBox("Tiers")
        tier_box.setStyleSheet(
            "QGroupBox { border: 1px solid #1f242c; border-radius: 6px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; top: -8px; color: #8b949e; }")
        tier_box.setLayout(tier_layout)

        self.e_checks = {}
        ench_layout = QHBoxLayout()
        ench_layout.setContentsMargins(5, 5, 5, 5)
        for e in range(0, 5):
            cb = QCheckBox(f".{e}")
            cb.setChecked(e in [0, 1])
            cb.setStyleSheet("QCheckBox { color: #c9d1d9; font-weight: bold; }")
            self.e_checks[e] = cb
            ench_layout.addWidget(cb)
        ench_box = QGroupBox("Enchants")
        ench_box.setStyleSheet(
            "QGroupBox { border: 1px solid #1f242c; border-radius: 6px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; top: -8px; color: #8b949e; }")
        ench_box.setLayout(ench_layout)

        filters_layout.addWidget(tier_box)
        filters_layout.addWidget(ench_box)
        left_panel.addLayout(filters_layout)
        main_layout.addLayout(left_panel, stretch=1)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        right_header = QHBoxLayout()
        lbl_selected = QLabel("Selected Items")
        lbl_selected.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 14px;")
        right_header.addWidget(lbl_selected)
        right_header.addStretch()

        btn_config = QPushButton(qta.icon('fa5s.save', color='#c9d1d9'), " Config Load/Save")
        btn_config.setStyleSheet(
            "background: #21262d; border: 1px solid #30363d; padding: 6px 12px; border-radius: 6px; color: #c9d1d9; font-weight: bold;")
        right_header.addWidget(btn_config)
        right_panel.addLayout(right_header)

        self.queue_tree = QTreeWidget()
        self.queue_tree.setHeaderHidden(True)
        self.queue_tree.setColumnCount(2)
        self.queue_tree.header().setStretchLastSection(False)
        self.queue_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.queue_tree.setColumnWidth(1, 50)
        self.queue_tree.setStyleSheet(self.get_tree_stylesheet())
        self.queue_tree.setIconSize(QSize(24, 24))
        right_panel.addWidget(self.queue_tree)

        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton(qta.icon('fa5s.trash-alt', color='#f85149'), " Bulk Remove")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.queue_tree.clear)
        self.btn_clear.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d; padding: 12px; border-radius: 6px; color: #c9d1d9; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background: #30363d; border-color: #f85149; }
        """)

        self.btn_start = QPushButton(qta.icon('fa5s.play', color='white'), " START MARKET CHECK")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_automation)
        self.btn_start.setStyleSheet("""
            QPushButton { background: #238636; color: white; padding: 12px; border-radius: 6px; font-weight: bold; font-size: 14px; border: none; }
            QPushButton:hover { background: #2ea043; }
        """)

        btn_layout.addWidget(self.btn_clear, stretch=1)
        btn_layout.addWidget(self.btn_start, stretch=3)
        right_panel.addLayout(btn_layout)

        main_layout.addLayout(right_panel, stretch=1)

    # =========================================================
    # ЛОГИКА ДАННЫХ И ЛОКАЛИЗАЦИИ
    # =========================================================
    def get_real_name(self, data, item_id):
        parts = item_id.split('_', 1)
        base_id = parts[1] if len(parts) > 1 and parts[0].startswith('T') else item_id

        # ИСПОЛЬЗУЕМ ХАРДКОД СЛОВАРЬ (100% точность для брони)
        if base_id in ALBION_EN_NAMES:
            return ALBION_EN_NAMES[base_id]

        # Если предмета нет в словаре (например, оружие), пытаемся вытащить из JSON
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass

        name_en = ""
        if isinstance(data, dict):
            for attr in ['localizedNames', 'localized_names', 'LocalizedNames']:
                loc = data.get(attr)
                if isinstance(loc, dict):
                    name_en = loc.get('EN-US') or loc.get('en-US') or ""
                    if name_en: break

            if not name_en:
                for attr in ['name', 'name_en', 'en_name', 'english_name']:
                    val = data.get(attr)
                    if isinstance(val, str) and val and not any('\u0400' <= c <= '\u04FF' for c in val):
                        name_en = val
                        break

        clean_name = name_en.strip() if name_en else item_id

        en_prefixes = ["Beginner's ", "Novice's ", "Journeyman's ", "Adept's ", "Expert's ", "Master's ",
                       "Grandmaster's ", "Elder's "]
        for p in en_prefixes:
            if clean_name.startswith(p):
                clean_name = clean_name[len(p):].strip()

        # Фолбэк на ID: только если имя пустое или кириллица
        if not clean_name or any('\u0400' <= c <= '\u04FF' for c in clean_name):
            clean_name = base_id.replace('_', ' ').title()

        return clean_name

    def categorize_by_id(self, item_id):
        i = item_id.upper()
        if any(bad in i for bad in ["TRASH", "TOKEN", "JOURNAL", "RUNE", "SOUL", "RELIC", "ARTEFACT", "FRAGMENT"]):
            return "Skip", ""

        if "_HEAD_" in i:
            if "_CLOTH_" in i: return "Helmets", "Cloth Helmet"
            if "_LEATHER_" in i: return "Helmets", "Leather Helmet"
            if "_PLATE_" in i: return "Helmets", "Plate Helmet"
            return "Helmets", "Other"
        if "_ARMOR_" in i:
            if "_CLOTH_" in i: return "Armors", "Cloth Armor"
            if "_LEATHER_" in i: return "Armors", "Leather Armor"
            if "_PLATE_" in i: return "Armors", "Plate Armor"
            return "Armors", "Other"
        if "_SHOES_" in i:
            if "_CLOTH_" in i: return "Shoes", "Cloth Shoes"
            if "_LEATHER_" in i: return "Shoes", "Leather Shoes"
            if "_PLATE_" in i: return "Shoes", "Plate Shoes"
            return "Shoes", "Other"

        weapons = ["_MAIN_", "_2H_", "BOW", "CROSSBOW", "SPEAR", "DAGGER", "STAFF", "AXE", "SWORD", "MACE", "HAMMER"]
        if any(w in i for w in weapons):
            if "BOW" in i or "CROSSBOW" in i: return "Weapons", "Bows & Crossbows"
            if "STAFF" in i: return "Weapons", "Staffs"
            return "Weapons", "Melee"

        if "_OFF_" in i or "SHIELD" in i or "TOME" in i or "TORCH" in i:
            return "Off-Hand", "Off-Hand"
        if "_CAPE_" in i or "_BAG_" in i:
            return "Accessories", "Capes & Bags"

        return "Skip", ""

    def populate_catalog(self):
        tree_data = {}
        processed_base_ids = set()

        for item_id, data in self.dm.items_cache.items():
            if "@" in item_id:
                continue

            cat, sub_cat = self.categorize_by_id(item_id)
            if cat == "Skip":
                continue

            parts = item_id.split('_', 1)
            base_id = parts[1] if len(parts) > 1 and parts[0].startswith('T') else item_id

            if base_id in processed_base_ids:
                continue

            clean_name = self.get_real_name(data, item_id)
            icon_id = f"T4_{base_id}" if not item_id.startswith("T") else item_id

            if cat not in tree_data: tree_data[cat] = {}
            if sub_cat not in tree_data[cat]: tree_data[cat][sub_cat] = []

            tree_data[cat][sub_cat].append({"id": base_id, "name": clean_name, "icon_id": icon_id})
            processed_base_ids.add(base_id)

        for cat, subcats in sorted(tree_data.items()):
            cat_item = QTreeWidgetItem(self.catalog_tree, [cat])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)

            for subcat, items in sorted(subcats.items()):
                sub_item = QTreeWidgetItem(cat_item, [subcat])
                sub_item.setFlags(sub_item.flags() & ~Qt.ItemIsSelectable)

                for item in sorted(items, key=lambda x: x['name']):
                    child = QTreeWidgetItem(sub_item, [f"  {item['name']}"])
                    child.setData(0, Qt.UserRole, item)

                    if self.app:
                        pix = self.app.get_local_icon(item["icon_id"])
                        if pix:
                            child.setIcon(0, QIcon(pix.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                        else:
                            self.app.icon_downloader.request_icon(item["icon_id"])

                    self.add_action_button(self.catalog_tree, child, "fa5s.plus", "#238636", "#2ea043",
                                           self.add_to_queue)

        self.catalog_tree.expandToDepth(0)

    # =========================================================
    # ВЗАИМОДЕЙСТВИЕ
    # =========================================================
    def add_action_button(self, tree, item, icon_name, bg_color, hover_color, callback):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 8, 0)

        btn = QPushButton()
        btn.setIcon(qta.icon(icon_name, color='white'))
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color}; border: none; border-radius: 4px; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """)
        btn.clicked.connect(lambda checked=False, i=item: callback(i))

        layout.addWidget(btn)
        tree.setItemWidget(item, 1, widget)

    def add_to_queue(self, catalog_item):
        item_data = catalog_item.data(0, Qt.UserRole)
        base_name = item_data["name"]
        icon_id = item_data["icon_id"]

        tiers = [t for t, cb in self.t_checks.items() if cb.isChecked()]
        enchants = [e for e, cb in self.e_checks.items() if cb.isChecked()]

        if not tiers or not enchants:
            return

        parent_node = None
        for i in range(self.queue_tree.topLevelItemCount()):
            if self.queue_tree.topLevelItem(i).text(0).strip() == base_name:
                parent_node = self.queue_tree.topLevelItem(i)
                break

        if not parent_node:
            parent_node = QTreeWidgetItem(self.queue_tree, [f"  {base_name}"])
            if self.app:
                pix = self.app.get_local_icon(icon_id)
                if pix: parent_node.setIcon(0, QIcon(pix.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)))

            self.add_action_button(self.queue_tree, parent_node, "fa5s.minus", "#da3633", "#f85149",
                                   self.remove_from_queue)

        for t in tiers:
            for e in enchants:
                search_str = f"  {base_name} {t}.{e}" if e > 0 else f"  {base_name} {t}"
                exists = any(parent_node.child(i).text(0) == search_str for i in range(parent_node.childCount()))

                if not exists:
                    child = QTreeWidgetItem(parent_node, [search_str])
                    self.add_action_button(self.queue_tree, child, "fa5s.minus", "#da3633", "#f85149",
                                           self.remove_from_queue)

        self.queue_tree.expandAll()

    def remove_from_queue(self, queue_item):
        parent = queue_item.parent()
        if parent:
            parent.removeChild(queue_item)
            if parent.childCount() == 0:
                self.queue_tree.takeTopLevelItem(self.queue_tree.indexOfTopLevelItem(parent))
        else:
            self.queue_tree.takeTopLevelItem(self.queue_tree.indexOfTopLevelItem(queue_item))

    def filter_catalog(self, text):
        text = text.lower()
        iterator = QTreeWidgetItemIterator(self.catalog_tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                item.setHidden(text not in item.text(0).lower())
            if text and not item.isHidden() and item.parent():
                item.parent().setExpanded(True)
                if item.parent().parent():
                    item.parent().parent().setExpanded(True)
            iterator += 1

    def start_automation(self):
        queue = []
        for i in range(self.queue_tree.topLevelItemCount()):
            parent = self.queue_tree.topLevelItem(i)
            for j in range(parent.childCount()):
                queue.append(parent.child(j).text(0).strip())

        if not queue:
            QMessageBox.warning(self, "Пусто", "Очередь пуста! Добавьте предметы из каталога.")
            return

        self.btn_start.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_start.setStyleSheet("""
            QPushButton { background: #d29922; color: white; padding: 12px; border-radius: 6px; font-weight: bold; font-size: 14px; border: none; }
        """)

        self.bot_thread = MarketBotThread(queue)
        self.bot_thread.progress_signal.connect(self.update_bot_status)
        self.bot_thread.finished_signal.connect(self.bot_finished)
        self.bot_thread.start()

    def update_bot_status(self, msg):
        self.btn_start.setText(f" {msg}")

    def bot_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_start.setText(" START MARKET CHECK")
        self.btn_start.setStyleSheet("""
            QPushButton { background: #238636; color: white; padding: 12px; border-radius: 6px; font-weight: bold; font-size: 14px; border: none; }
            QPushButton:hover { background: #2ea043; }
        """)

    def get_tree_stylesheet(self):
        return """
            QTreeWidget {
                background-color: #0d1117; border: 1px solid #1f242c; border-radius: 8px; color: #c9d1d9; font-size: 14px; outline: none; padding: 5px;
            }
            QTreeWidget::item { padding: 6px; border-bottom: 1px solid #1f242c; }
            QTreeWidget::item:hover { background-color: #161b22; border-radius: 4px; }
            QTreeWidget::item:selected { background-color: #1f242c; color: white; }
            QTreeWidget::branch:has-siblings:!adjoins-item { border-image: none; }
            QTreeWidget::branch:has-siblings:adjoins-item { border-image: none; }
            QTreeWidget::branch:!has-children:!has-siblings:adjoins-item { border-image: none; }
            QTreeWidget::branch:has-children:!has-siblings:closed, QTreeWidget::branch:closed:has-children:has-siblings { border-image: none; image: none; }
            QTreeWidget::branch:open:has-children:!has-siblings, QTreeWidget::branch:open:has-children:has-siblings { border-image: none; image: none; }
        """