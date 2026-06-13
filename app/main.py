# app/main.py
import os
from dotenv import load_dotenv
load_dotenv()
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Union

from .services.llm_client import AsyncLLMClient

# Настройка логирования для приложения
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Async LLM API")

# Инициализируем клиент. В реальном приложении ключ нужно брать из переменных окружения.
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Создаем экземпляр клиента.
# max_concurrent=10 — хороший баланс между производительностью и риском rate limit'ов.
llm_client = AsyncLLMClient(api_key=API_KEY, model="gpt-4o-mini", max_concurrent=10)


# Модели данных для валидации запросов
class ChatRequest(BaseModel):
    prompt: str


class BatchChatRequest(BaseModel):
    prompts: List[str]
    concurrency: Optional[int] = None


# ---- Обычный чат эндпоинт ----
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Принимает запрос и возвращает полный ответ.
    """
    try:
        response = await llm_client.complete(request.prompt)
        return {"response": response}
    except Exception as e:
        logger.error(f"Error in /chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Пакетный чат эндпоинт ----
@app.post("/chat/batch")
async def batch_chat_endpoint(request: BatchChatRequest):
    """
    Принимает несколько запросов и возвращает результаты.
    """
    try:
        results = await llm_client.batch_chat(request.prompts, concurrency=request.concurrency)
        # Преобразуем исключения в строки для JSON-ответа.
        serializable_results = [
            {"result": r, "is_error": False} if not isinstance(r, Exception)
            else {"result": str(r), "is_error": True}
            for r in results
        ]
        return {"results": serializable_results}
    except Exception as e:
        logger.error(f"Error in /chat/batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- SSE-эндпоинт для потоковой передачи ----
@app.post("/chat/stream")
async def stream_chat_endpoint(request: ChatRequest):
    """
    Возвращает потоковый ответ в формате Server-Sent Events (SSE).
    Клиент должен подключаться через EventSource с POST-запросом.
    """
    # Генератор, который будет передавать данные клиенту.
    async def event_generator():
        async for chunk in llm_client.stream_chat(request.prompt):
            # Формат данных для SSE: "data: <json>\n\n"
            yield f"data: {chunk}\n\n"
        # Сигнализируем об окончании потока.
        yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ---- Простой health-check ----
@app.get("/health")
async def health_check():
    return {"status": "ok"}