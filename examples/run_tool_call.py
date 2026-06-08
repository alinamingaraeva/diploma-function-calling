"""Примеры запуска с тремя тестовыми запросами"""

import sys
from pathlib import Path

# Добавляем корневую папку в путь поиска модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm.client import AssistantClient

def main():
    """Запуск трёх тестовых запросов"""
    
    # Создаём клиента
    client = AssistantClient(product_name="AcmeCloud")
    
    print("=" * 60)
    print("ТЕСТ 1: ЗАПРОС, КОТОРЫЙ ТРЕБУЕТ ВЫЗОВ ФУНКЦИИ")
    print("=" * 60)
    
    query_a = "Как сбросить пароль?"
    print(f"\nВопрос: {query_a}")
    answer = client.chat(query_a)
    print(f"Ответ: {answer}")
    
    print("\n" + "=" * 60)
    print("ТЕСТ 2: ЗАПРОС, КОТОРЫЙ НЕ ТРЕБУЕТ ВЫЗОВ ФУНКЦИИ")
    print("=" * 60)
    
    query_b = "Привет! Как дела?"
    print(f"\nВопрос: {query_b}")
    answer = client.chat(query_b)
    print(f"Ответ: {answer}")
    
    print("\n" + "=" * 60)
    print("ТЕСТ 3: ПОГРАНИЧНЫЙ СЛУЧАЙ")
    print("=" * 60)
    
    # Пограничный - вопрос про продукт, но не явно спрашивает инструкцию
    query_c = "Расскажи что-нибудь о своём сервисе"
    print(f"\nВопрос: {query_c}")
    answer = client.chat(query_c)
    print(f"Ответ: {answer}")
    
    print("\n" + "=" * 60)
    print("ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 60)

if __name__ == "__main__":
    main()