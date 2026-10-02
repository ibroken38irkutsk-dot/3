# Дашборд «Бюджет ДДУС» для Apache Superset

Источник — лист «Бюджет ДДУС» (ТМ06). Проверено на Superset 6.1 + PostgreSQL.

## Состав
- `etl_ddus.py` — Excel → плоская таблица `ddus_budget` (CSV или PostgreSQL). Сверяет сумму статей со строкой «Итого».
- `build_dashboard.py` — создаёт датасет, метрики, графики и дашборд через REST API Superset.
- `ddus_dashboard_superset6.zip` — экспорт готового дашборда (Dashboards → Import).

## Развёртывание у себя
1. Загрузить данные в БД, подключённую к Superset:
   `python etl_ddus.py "файл.xlsx" --pg postgresql://user:pass@host:5432/db`
   (или `--csv ddus_budget.csv` и загрузить CSV через Superset: Datasets → Upload file).
2. Вариант А — импорт ZIP: Dashboards → Import → указать пароль к БД. В ZIP подключение
   называется `DDUS` и смотрит на `localhost:5432/ddus` — после импорта поправьте адрес в
   Settings → Database Connections.
   Вариант Б — скриптом против вашего Superset:
   `python build_dashboard.py --url http://<superset> --user <login> --password <pass> --db-name "<имя подключения>"`
3. Русский формат чисел (4 650,0) — в `superset_config.py`:
   `D3_FORMAT = {"decimal": ",", "thousands": " ", "grouping": [3], "currency": ["", " ₽"]}`

## Модель
- Все метрики в млн руб. и **без строк «в т.ч.»** (`is_detail = false`), чтобы не было двойного счёта.
- Фильтры дашборда: Деятельность (Текущая / Инвестиционная), Статья оборотов.
- Обновление: перезапустить `etl_ddus.py` на новом файле — таблица пересоздаётся, дашборд подхватит данные.
