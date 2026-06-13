# app/services/llm_client.py
import asyncio
import time
from typing import AsyncIterator, List, Union, Optional
import logging

from openai import AsyncOpenAI

# Настройка логирования
logger = logging.getLogger(__name__)

class AsyncLLMClient:
    """
    Асинхронный клиент для взаимодействия с OpenAI API.
    Поддерживает одиночные запросы, пакетную обработку и потоковую передачу.
    """

    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini", max_concurrent: int = 5):
        """
        Инициализирует клиент.

        Args:
            api_key: API-ключ OpenAI.
            model: Название модели для использования.
            max_concurrent: Максимальное количество одновременных запросов.
        """
        # Используем AsyncOpenAI для неблокирующих вызовов API.
        # Таймаут устанавливается на уровне SDK.
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://polza.ai/api/v1", timeout=30.0, max_retries=3)
        self.model = model
        # Semaphore — это атрибут экземпляра, создается один раз в __init__.
        # Он ограничивает количество одновременных запросов.
        self._sem = asyncio.Semaphore(max_concurrent)
        logger.info(f"AsyncLLMClient initialized with model={model}, max_concurrent={max_concurrent}")

    async def _call_openai(self, prompt: str) -> str:
        """
        Внутренний метод для совершения одного API-вызова.
        Содержит бизнес-логику с дополнительным таймаутом.
        """
        # asyncio.timeout добавляет дополнительный слой защиты поверх таймаута SDK.
        async with asyncio.timeout(15):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                # Для обычного вызова стриминг не нужен.
                stream=False,
            )
        # Извлекаем текст ответа, отбрасывая служебную информацию.
        return response.choices[0].message.content

    async def complete(self, prompt: str) -> str:
        """
        Выполняет одиночный запрос к LLM.

        Args:
            prompt: Текст запроса.

        Returns:
            Ответ от LLM.
        """
        start_time = time.perf_counter()
        status = "success"
        try:
            # Ограничиваем количество одновременных запросов через Semaphore.
            # async with self._sem: ожидает, пока не освободится "слот".
            async with self._sem:
                result = await self._call_openai(prompt)
            return result
        except Exception as e:
            status = f"error: {type(e).__name__}"
            # В случае ошибки пробрасываем её выше.
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            # Логируем каждый вызов в соответствии с заданием.
            logger.info(
                "llm.call",
                extra={
                    "duration_ms": duration_ms,
                    "model": self.model,
                    "prompt_chars": len(prompt),
                    "status": status,
                },
            )

    async def batch_chat(self, prompts: List[str], concurrency: Optional[int] = None) -> List[Union[str, Exception]]:
        """
        Обрабатывает список промптов с ограничением на количество одновременных вызовов.

        Args:
            prompts: Список текстов запросов.
            concurrency: Максимальное количество запросов, выполняемых одновременно.
                         Если не указано, используется значение из __init__.

        Returns:
            Список результатов. Если запрос завершился ошибкой, в список помещается
            объект исключения, а не текст ответа. Соответствие позиций сохраняется.
        """
        # Если concurrency не задан, используем значение по умолчанию из Semaphore.
        sem = self._sem if concurrency is None else asyncio.Semaphore(concurrency)

        async def _limited_complete(prompt: str) -> Union[str, Exception]:
            """
            Обёртка для вызова complete() с ограничением через Semaphore.
            Перехватывает исключения и возвращает их как объекты, чтобы не прерывать gather().
            """
            try:
                async with sem:
                    return await self.complete(prompt)
            except Exception as e:
                # Возвращаем исключение, чтобы asyncio.gather(return_exceptions=True) мог его обработать.
                return e

        # Создаем список корутин для всех промптов.
        tasks = [_limited_complete(prompt) for prompt in prompts]
        # asyncio.gather с return_exceptions=True выполнит все задачи, даже если какие-то упадут,
        # и вернет смешанный список результатов (строки и исключения).
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def stream_chat(self, prompt: str) -> AsyncIterator[str]:
        """
        Отправляет запрос и возвращает асинхронный генератор,
        который выдает текст по мере поступления от API.

        Args:
            prompt: Текст запроса.

        Yields:
            Части (дельта) ответа от LLM.
        """
        start_time = time.perf_counter()
        try:
            # Включаем стриминг и запрашиваем метаинформацию об использовании токенов.
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                stream_options={"include_usage": True},
            )

            async for chunk in response:
                # В стриминговых ответах токены могут быть в content.
                # Важно: последний chunk может содержать usage и не иметь choices.
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                # Отлавливаем последний chunk с метаинформацией.
                if chunk.usage:
                    logger.info(
                        "llm.stream_usage",
                        extra={
                            "total_tokens": chunk.usage.total_tokens,
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                        },
                    )
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            # Можно либо пробросить исключение, либо замолчать, чтобы не ломать SSE-соединение.
            # Пробросим его, чтобы FastAPI мог корректно обработать ошибку.
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Streaming finished in {duration_ms:.2f} ms")