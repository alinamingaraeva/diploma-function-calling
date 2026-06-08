"""Описания инструментов в формате JSON Schema для Function Calling"""

# Константа с описанием инструмента (вынесена отдельно, как просит преподаватель)
SEARCH_KB_DESCRIPTION = """
Ищет информацию в базе знаний техподдержки.
Используй эту функцию, когда пользователь спрашивает про:
- как что-то настроить
- инструкции по использованию
- решение проблем
- документацию
"""

# JSON Schema для функции поиска по базе знаний
SEARCH_KNOWLEDGE_BASE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": SEARCH_KB_DESCRIPTION,  # используем вынесенную константу
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос пользователя на русском языке"
                },
                "product": {
                    "type": "string",
                    "description": "Название продукта (если указано пользователем)",
                    "enum": ["AcmeCloud", "AcmeMail", "AcmeDrive"],  # ограниченный список
                }
            },
            "required": ["query"],  # только query обязателен, product - опционально
        }
    }
}

# Список всех доступных инструментов
ALL_TOOLS = [SEARCH_KNOWLEDGE_BASE_TOOL]