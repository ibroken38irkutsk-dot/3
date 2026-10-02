import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "postgresql://bi:bi@db:5432/superset_meta"

FEATURE_FLAGS = {"DASHBOARD_NATIVE_FILTERS": True}
BABEL_DEFAULT_LOCALE = "ru"
LANGUAGES = {"ru": {"flag": "ru", "name": "Русский"}, "en": {"flag": "us", "name": "English"}}

# Русский формат чисел: 4 650,0
D3_FORMAT = {"decimal": ",", "thousands": " ", "grouping": [3], "currency": ["", " ₽"]}

CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache"}
DATA_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache"}
FILTER_STATE_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 86400}
EXPLORE_FORM_DATA_CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 86400}

# Разрешить загрузку CSV/Excel через интерфейс в базу analytics
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
