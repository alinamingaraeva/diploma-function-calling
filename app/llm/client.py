"""Клиент для работы с OpenAI с поддержкой Function Calling"""

import json
import logging
from openai import OpenAI
from app.config import settings
from app.prompts.loader import render_system_prompt
from app.tools.schemas import ALL_TOOLS
from app.tools.handlers import search_knowledge_base

# Настройка логирования (как просит преподаватель)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AssistantClient:
    """Клиент для общения с ассистентом с поддержкой инструментов"""
    
    def __init__(self, product_name: str = "AcmeCloud"):
        """Инициализация клиента"""
        self.client = OpenAI(
    base_url="https://polza.ai/api/v1",  # 👈 Указываем URL API polza.ai
    api_key=settings.polza_ai_api_key,   # 👈 Используем наш новый ключ
)
        self.product_name = product_name
        # Доступные инструменты (функции)
        self.tools = ALL_TOOLS
    
    def _execute_tool_call(self, tool_call):
        """Выполняет функцию, которую вызвала модель"""
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        logger.info(f"Вызван инструмент: {tool_name}, аргументы: {arguments}")
        
        if tool_name == "search_knowledge_base":
            result = search_knowledge_base(**arguments)
        else:
            result = f"Неизвестный инструмент: {tool_name}"
        
        logger.info(f"Результат функции: {result[:100]}...")  # обрезаем для лога
        return result
    
    def chat(self, user_message: str, max_iterations: int = 2) -> str:
        """
        Основной метод для общения с ассистентом.
        Поддерживает автоматический вызов инструментов.
        """
        # 1. Загружаем system prompt из файла (как просит преподаватель)
        system_prompt = render_system_prompt(
            version="v1", 
            product_name=self.product_name
        )
        
        # Начинаем историю сообщений
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"Пользователь: {user_message}")
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # Отправляем запрос к OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # используем дешёвую модель для тестов
                messages=messages,
                tools=self.tools,
                tool_choice="auto",  # модель сама решает, вызывать ли функцию
            )
            
            # Получаем ответ модели
            assistant_message = response.choices[0].message
            usage = response.usage  # для логирования токенов
            
            # Логируем использование токенов
            logger.info(f"Токены: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
            
            # Добавляем ответ ассистента в историю
            messages.append(assistant_message.model_dump())
            
            # Проверяем, хочет ли модель вызвать функцию
            if assistant_message.tool_calls:
                logger.info(f"Модель вызвала функцию: {[tc.function.name for tc in assistant_message.tool_calls]}")
                
                # Выполняем каждую вызванную функцию
                for tool_call in assistant_message.tool_calls:
                    result = self._execute_tool_call(tool_call)
                    
                    # Добавляем результат функции в историю (role="tool")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
                
                # Продолжаем цикл - отправим всё модели для финального ответа
                continue
            else:
                # Функции не вызваны - это финальный ответ
                final_answer = assistant_message.content
                logger.info(f"Финальный ответ: {final_answer}")
                return final_answer
        
        return "Превышено максимальное количество итераций"