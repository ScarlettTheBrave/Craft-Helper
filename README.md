# Craft Help by Scar 

🌍 Choose language: [English](#-english-version) | SOON
---

## 🇬🇧 English Version
# An advanced crafting calculator for **Albion Online**. Craft Help by Scar 

 The program allows you to analyze current market prices, calculate crafting costs including taxes, Resource Return Rate (RRR), laborers' journals, and focus, as well as manage production estimates in the cloud.

## Core Features
* **Price Synchronization.** Automatic price parsing via the [Albion Data Project](https://www.albion-online-data.com/).
* **Smart Calculator.** Automatic profit calculation factoring in enchantments (.1, .2, .3, .4), journal filling, and station taxes.
* **Substitution System (Tokens).** The program can determine whether it's more profitable to buy a ready-made artifact or exchange essences/tokens (e.g., Crystallized Dread).
* **Cloud ERP.** Creation of procurement and production plans with profile saving to a cloud database.
* **Manual Adjustment.** The ability to set your own price for any item if the API data is outdated.

## 🛠 Technologies
* **Language:** Python 3.12
* **GUI:** PySide6 (Qt) + custom design (QSS)
* **Database:** Supabase (PostgreSQL + REST API)
* **Concurrency:** QThreadPool, QRunnable, thread queuing for icon loading and API parsing.
* **Build:** PyInstaller

## Installation and Running from Source

1. Clone the repository:
```bash
git clone [https://github.com/YOUR_NICKNAME/REPOSITORY_NAME.git](https://github.com/YOUR_NICKNAME/REPOSITORY_NAME.git)
Create and activate a virtual environment:
```

2. Create and activate locale env

```bash
python -m venv venv
venv\Scripts\activate  # Для Windows
```
3. Install requirements
```
pip install -r requirements.txt
```

4. Deploy
```bash
python ui_new.py
```

---
