import asyncio
import time
import logging
from typing import List

from openai import OpenAI

# Добавляем путь к проекту, чтобы импортировать наш клиент.
import sys
sys.path.append('.')

from app.services.llm_client import AsyncLLMClient

# Настройка логирования (можно отключить для чистоты измерений)
logging.basicConfig(level=logging.WARNING)

# Конфигурация
API_KEY = "your-api-key-here"  # Замените на ваш ключ
MODEL = "gpt-4o-mini"
PROMPTS_COUNT = 20
# Генерируем 20 различных промптов, чтобы избежать эффекта кэширования.
PROMPTS = [f"Explain in one paragraph the concept of concurrency in computing. Variant {i}" for i in range(PROMPTS_COUNT)]


def benchmark_sync(api_key: str, model: str, prompts: List[str]) -> float:
    """Выполняет запросы синхронно и последовательно."""
    print("\n--- Running SYNC benchmark (sequential) ---")
    sync_client = OpenAI(api_key=api_key)

    start_time = time.perf_counter()
    for i, prompt in enumerate(prompts):
        try:
            # Синхронный вызов блокирует выполнение программы.
            response = sync_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
            # Небольшая печать для индикации прогресса.
            print(f"  Processed {i+1}/{len(prompts)}...", end='\r')
        except Exception as e:
            print(f"\n  Error on prompt {i}: {e}")
    end_time = time.perf_counter()
    total_duration = end_time - start_time
    print(f"\n  Total time: {total_duration:.2f} seconds")
    return total_duration


async def benchmark_async_batch(api_key: str, model: str, prompts: List[str], concurrency: int) -> float:
    """Выполняет запросы асинхронно и конкурентно с помощью batch_chat."""
    print(f"\n--- Running ASYNC benchmark (batch_chat, concurrency={concurrency}) ---")
    async_client = AsyncLLMClient(api_key=api_key, model=model, max_concurrent=concurrency)

    start_time = time.perf_counter()
    # batch_chat выполнит все запросы конкурентно, ограниченные Semaphore.
    results = await async_client.batch_chat(prompts, concurrency=concurrency)
    end_time = time.perf_counter()

    # Подсчитываем успешные ответы и ошибки.
    successful = sum(1 for r in results if not isinstance(r, Exception))
    failed = len(results) - successful
    print(f"  Completed {successful}/{len(prompts)} requests, {failed} failed.")
    total_duration = end_time - start_time
    print(f"  Total time: {total_duration:.2f} seconds")
    return total_duration


async def main():
    """Запускает все бенчмарки и выводит сводную таблицу."""
    print(f"Benchmarking with {PROMPTS_COUNT} prompts.")

    # 1. Синхронный бенчмарк
    sync_time = benchmark_sync(API_KEY, MODEL, PROMPTS)

    # 2. Асинхронные бенчмарки с разной конкурентностью
    async_times = {}
    for concurrency in [1, 5, 10]:
        async_time = await benchmark_async_batch(API_KEY, MODEL, PROMPTS, concurrency)
        async_times[concurrency] = async_time

    # 3. Вывод результатов
    print("\n\n" + "="*50)
    print("BENCHMARK RESULTS")
    print("="*50)
    print(f"{'Mode':<20} {'Total Time (s)':<15} {'Speedup vs Sync':<20}")
    print("-"*55)
    print(f"{'Sync (sequential)':<20} {sync_time:<15.2f} {'1.00x':<20}")
    for concurrency, async_time in async_times.items():
        speedup = sync_time / async_time if async_time > 0 else 0
        print(f"{f'Async (batch, concurrency={concurrency})':<20} {async_time:<15.2f} {speedup:.2f}x")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())