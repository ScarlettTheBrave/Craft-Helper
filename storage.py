import json
import os

class SessionManager:
    def __init__(self, filename="erp_sessions.json"):
        self.filename = filename

    def save_tabs(self, tabs_data):
        """
        Сохраняет структуру вкладок.
        Ожидает список словарей: [{"name": "Т4 Посохи", "items": [...]}]
        """
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(tabs_data, f, ensure_ascii=False, indent=4)
            print(" Сессия успешно сохранена.")
        except Exception as e:
            print(f" Ошибка сохранения сессии: {e}")

    def load_tabs(self):
        """Загружает сохраненные вкладки при запуске"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f" Ошибка чтения файла сессии: {e}")
                return []
        return []