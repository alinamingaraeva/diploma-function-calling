"""Загрузчик промптов из файлов"""

from functools import lru_cache
from pathlib import Path
from jinja2 import Template

# Папка, где лежат промпты
PROMPTS_DIR = Path(__file__).parent

@lru_cache(maxsize=8)  # кэшируем результат, чтобы не читать файл каждый раз
def render_system_prompt(version: str = "v1", **context) -> str:
    """
    Загружает системный промпт из файла и подставляет переменные.
    
    Аргументы:
        version: версия промпта (v1, v2 и т.д.)
        **context: переменные для подстановки (например, product_name)
    
    Возвращает:
        готовый текст промпта
    """
    # Читаем файл system_v1.j2 (или system_v2.j2 и т.д.)
    text = (PROMPTS_DIR / f"system_{version}.j2").read_text(encoding="utf-8")
    # Подставляем переменные (например, {{ product_name }})
    return Template(text).render(**context)