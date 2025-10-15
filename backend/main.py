from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import uuid
import hashlib
import secrets

load_dotenv()

app = FastAPI(title="Survey Chat Bot")

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

#  система авторизации
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin123")  # В продакшене использовать JWT
security = HTTPBearer()

# хранение сессии (можно использовать Redis/DB)
sessions: Dict[str, Dict[str, Any]] = {}

#  вопросы опроса
with open("survey_questions.json", "r", encoding="utf-8") as f:
    SURVEY_QUESTIONS = json.load(f)


class LoginRequest(BaseModel):
    username: str
    password: str


class SurveyUpload(BaseModel):
    questions: List[Dict[str, Any]]


class ChatMessage(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    message: str
    current_question: Optional[Dict] = None
    is_completed: bool = False


class AdminStats(BaseModel):
    total_sessions: int
    completed_surveys: int
    active_sessions: int
    recent_responses: List[Dict]


def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена пользователя для admin"""
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    return credentials.credentials


def load_survey_questions():
    """Загрузка вопросов из JSON"""
    with open("survey_questions.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_survey_result(session_id: str, answers: List[Dict]):
    """Сохранение результатов опроса в JSON файл"""
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


# Endpoints for users

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


@app.post("/chat/start/{session_id}")
async def start_chat_with_session(session_id: str):
    """Начать сессию с конкретным ID"""
    
    # Проверяем, существует ли уже сессия
    if session_id in sessions:
        session = sessions[session_id]
        current_question = get_current_question(session)
        
        if current_question:
            # Если это первый вопрос (индекс 0), показываем приветствие
            if session.get("current_question_index", 0) == 0:
                welcome_message = f"""Добрый день! Я бот для проведения социологического опроса. 
                
Сейчас я задам вам несколько вопросов. Вы можете отвечать своими словами, а я постараюсь понять ваш ответ.

Начнем! {current_question['question']}"""
                
                return ChatResponse(
                    session_id=session_id,
                    message=welcome_message,
                    current_question=current_question,
                    is_completed=False
                )
            else:
                return ChatResponse(
                    session_id=session_id,
                    message=f"Продолжаем опрос! {current_question['question']}",
                    current_question=current_question,
                    is_completed=False
                )
        else:
            return ChatResponse(
                session_id=session_id,
                message="Опрос уже завершен. Начните новый опрос.",
                current_question=None,
                is_completed=True
            )
    
    # Создаем новую сессию с указанным ID
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


# Endpoints for ADMIN

@app.post("/admin/login")
async def admin_login(login_data: LoginRequest):
    """Авторизация админа"""
    # просто проверка (можно использовать хеширование)
    if login_data.username == "admin" and login_data.password == "admin123":
        return {"token": ADMIN_TOKEN, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/admin/stats")
async def get_admin_stats(token: str = Depends(verify_admin_token)):
    """Статистика для админ панели"""
    total_sessions = len(sessions)
    completed_surveys = len([s for s in sessions.values() if s.get("current_question_index", 0) >= len(load_survey_questions())])
    active_sessions = total_sessions - completed_surveys
    
    # получаем последние ответы
    recent_responses = []
    for session_id, session_data in sessions.items():
        if session_data.get("answers"):
            recent_responses.append({
                "session_id": session_id,
                "started_at": session_data.get("started_at"),
                "answers_count": len(session_data["answers"]),
                "last_answer": session_data["answers"][-1] if session_data["answers"] else None
            })
    
    # сортировка по времени начала
    recent_responses.sort(key=lambda x: x["started_at"], reverse=True)
    
    return AdminStats(
        total_sessions=total_sessions,
        completed_surveys=completed_surveys,
        active_sessions=active_sessions,
        recent_responses=recent_responses[:10]  # ласт 10
    )


@app.get("/admin/responses")
async def get_all_responses(token: str = Depends(verify_admin_token)):
    """получить все ответы пользователей"""
    all_responses = []
    
    # читаем сохраненные результаты
    results_dir = "results"
    if os.path.exists(results_dir):
        for filename in os.listdir(results_dir):
            if filename.startswith("survey_") and filename.endswith(".json"):
                filepath = os.path.join(results_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        all_responses.append(data)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    
    # добавляем активные сессии
    for session_id, session_data in sessions.items():
        if session_data.get("answers"):
            all_responses.append({
                "session_id": session_id,
                "timestamp": session_data.get("started_at"),
                "answers": session_data["answers"],
                "status": "completed" if session_data.get("current_question_index", 0) >= len(load_survey_questions()) else "in_progress"
            })
    
    # сорт по времени
    all_responses.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return {"responses": all_responses}


@app.post("/admin/survey/upload")
async def upload_survey(survey_data: SurveyUpload, token: str = Depends(verify_admin_token)):
    """Загрузить новый опрос"""
    try:
        # валидация общего формата
        for question in survey_data.questions:
            if not all(key in question for key in ["id", "question", "type", "options"]):
                raise HTTPException(status_code=400, detail="Invalid question structure")
            
            if question["type"] not in ["single_choice", "multiple_choice"]:
                raise HTTPException(status_code=400, detail="Invalid question type")
        
        # сохраняем новый опрос
        with open("survey_questions.json", "w", encoding="utf-8") as f:
            json.dump(survey_data.questions, f, ensure_ascii=False, indent=2)
        
        return {"message": "Survey uploaded successfully", "questions_count": len(survey_data.questions)}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error uploading survey: {str(e)}")


@app.get("/admin/survey/current")
async def get_current_survey(token: str = Depends(verify_admin_token)):
    """Получить текущий опрос"""
    return load_survey_questions()


@app.get("/admin/export/csv")
async def export_csv(token: str = Depends(verify_admin_token)):
    """Экспорт результатов в CSV"""
    import csv
    import io
    
    # собираем все данные
    all_data = []
    results_dir = "results"
    
    if os.path.exists(results_dir):
        for filename in os.listdir(results_dir):
            if filename.startswith("survey_") and filename.endswith(".json"):
                filepath = os.path.join(results_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for answer in data.get("answers", []):
                            all_data.append({
                                "session_id": data["session_id"],
                                "timestamp": data["timestamp"],
                                "question_id": answer["question_id"],
                                "question": answer["question"],
                                "answer_codes": ",".join(answer["answer_codes"]),
                                "original_answer": answer["original_answer"]
                            })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    
    # создать CSV
    output = io.StringIO()
    if all_data:
        writer = csv.DictWriter(output, fieldnames=all_data[0].keys())
        writer.writeheader()
        writer.writerows(all_data)
    
    return {"csv_data": output.getvalue()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)