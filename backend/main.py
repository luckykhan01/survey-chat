from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import uuid

load_dotenv()

app = FastAPI(title="Survey Chat Bot API")

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# вопросы опроса
with open("survey_questions.json", "r", encoding="utf-8") as f:
    SURVEY_QUESTIONS = json.load(f)

# хранение сессии (можно использоватьRedis/DB)
sessions: Dict[str, Dict[str, Any]] = {}


class ChatMessage(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    message: str
    current_question: Optional[Dict] = None
    is_completed: bool = False


def load_survey_questions():
    """Загрузка вопросов из JSON"""
    with open("survey_questions.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_survey_result(session_id: str, answers: List[Dict]):
    """Сохранение результатов в JSON"""
    os.makedirs("results", exist_ok=True)
    
    result = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "answers": answers
    }
    
    filename = f"results/survey_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return filename


def get_current_question(session: Dict) -> Optional[Dict]:
    """Получить вопрос для сессии"""
    current_index = session.get("current_question_index", 0)
    questions = load_survey_questions()
    
    if current_index < len(questions):
        return questions[current_index]
    return None


def match_answer_to_options(user_answer: str, question: Dict) -> List[str]:
    """
    Использование API для сопоставления ответа пользователя с вариантами
    """
    lines = []
    for opt in question["options"]:
        lines.append(f"{opt['code']}: {opt['text']}")
    options_text = "\n".join(lines)
    
    if question["type"] == "single_choice":
        prompt = f"""Пользователь ответил на вопрос: "{question['question']}"
        
    Его ответ: "{user_answer}"

    Доступные варианты ответов:
    {options_text}

    Задача: определи, какой вариант ответа наиболее подходит к ответу пользователя.
    Верни ТОЛЬКО код варианта (например: A1, B2, и т.д.), без дополнительного текста.
    Если ответ не подходит ни к одному варианту, верни "UNCLEAR"."""

    else:  # multiple_choice
        prompt = f"""Пользователь ответил на вопрос: "{question['question']}"
        
Его ответ: "{user_answer}"

    Доступные варианты ответов:
    {options_text}

    Задача: определи, какие варианты ответов подходят к ответу пользователя.
    Верни коды вариантов через запятую (например: C1,C3 или C1,C2,C5), без пробелов и дополнительного текста.
    Если ответ не подходит ни к одному варианту, верни "UNCLEAR"."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник для анализа ответов в социологическом опросе. Твоя задача - точно сопоставить ответ пользователя с предложенными вариантами."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=50
        )
        
        result = response.choices[0].message.content.strip()
        
        if result == "UNCLEAR":
            return []
        
        if question["type"] == "single_choice":
            return [result] if result in [opt["code"] for opt in question["options"]] else []
        else:
            codes = result.split(",")
            valid_codes = [opt["code"] for opt in question["options"]]
            return [code.strip() for code in codes if code.strip() in valid_codes]
    
    except Exception as e:
        print(f"Error matching answer: {e}")
        return []


def generate_bot_response(session: Dict, user_message: str) -> str:
    """Генерация ответа бота с использованием API"""
    current_question = get_current_question(session)
    
    if not current_question:
        return "Спасибо за участие в опросе! Ваши ответы сохранены."
    
    # контекст для GPT
    options_text = ""
    for opt in current_question["options"]:
        options_text += f"- {opt['text']}\n"
    options_text = options_text.strip()
        
    prompt = f"""Ты - дружелюбный ассистент, который проводит социологический опрос.

Текущий вопрос: "{current_question['question']}"

Варианты ответов:
{options_text}

Пользователь только что ответил: "{user_message}"

Твоя задача:
1. Если это первый вопрос сессии и пользователь только поздоровался - поприветствуй его и задай первый вопрос
2. Если пользователь дал ответ на вопрос - поблагодари его кратко и естественно
3. Будь дружелюбным и лаконичным

Ответь пользователю (1-2 предложения максимум):"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты дружелюбный ассистент для проведения опросов. Отвечай кратко и по-русски."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Понял, спасибо!"


@app.get("/")
async def root():
    return {"message": "API is running"}


@app.post("/chat/start")
async def start_chat():
    """Новая сессия опроса"""
    session_id = str(uuid.uuid4())
    
    sessions[session_id] = {
        "current_question_index": 0,
        "answers": [],
        "started_at": datetime.now().isoformat()
    }
    
    first_question = get_current_question(sessions[session_id])
    
    welcome_message = f"""Добрый день! Я бот для проведения социологического опроса. 
    
Сейчас я задам вам несколько вопросов. Вы можете отвечать своими словами, а я постараюсь понять ваш ответ.

Начнем! {first_question['question']}"""
    
    return ChatResponse(
        session_id=session_id,
        message=welcome_message,
        current_question=first_question,
        is_completed=False
    )


@app.post("/chat/message", response_model=ChatResponse)
async def send_message(chat_message: ChatMessage):
    """Обработка сообщения пользователя"""
    
    if not chat_message.session_id or chat_message.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session is not found. Please start a new chat.")
    
    session = sessions[chat_message.session_id]
    current_question = get_current_question(session)
    
    if not current_question:
        raise HTTPException(status_code=400, detail="Survey already completed")
    
    # сопоставить ответ пользователя с вариантами
    matched_codes = match_answer_to_options(chat_message.message, current_question)
    
    if not matched_codes:
        # если не удалось сопоставить, просим уточнить
        options_text = "\n".join([f"- {opt['text']}" for opt in current_question["options"]])
        return ChatResponse(
            session_id=chat_message.session_id,
            message=f"Ваш ответ не понятен. Пожалуйста, выберите из следующих вариантов:\n\n{options_text}",
            current_question=current_question,
            is_completed=False
        )
    
    # ответ сохраняется
    answer_record = {
        "question_id": current_question["id"],
        "question": current_question["question"],
        "answer_codes": matched_codes,
        "original_answer": chat_message.message
    }
    session["answers"].append(answer_record)
    
    # идет к следующему вопросу
    session["current_question_index"] += 1
    next_question = get_current_question(session)
    
    if next_question:
        # еще не закончился опрос
        bot_response = generate_bot_response(session, chat_message.message)
        full_message = f"{bot_response}\n\n{next_question['question']}"
        
        return ChatResponse(
            session_id=chat_message.session_id,
            message=full_message,
            current_question=next_question,
            is_completed=False
        )
    else:
        # опрос окончен
        filename = save_survey_result(chat_message.session_id, session["answers"])
        
        return ChatResponse(
            session_id=chat_message.session_id,
            message=f"Спасибо за участие в опросе! Ваши ответы сохранены. \n\nВсего вопросов: {len(session['answers'])}",
            current_question=None,
            is_completed=True
        )


@app.get("/survey/questions")
async def get_questions():
    """Получить все вопросы опроса"""
    return load_survey_questions()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

