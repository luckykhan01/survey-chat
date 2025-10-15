import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import './App.css'

const API_URL = 'http://localhost:8000'

function ChatPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)
  const [currentQuestion, setCurrentQuestion] = useState(null)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (sessionId) {
      // начальное сообщение
      loadInitialMessage()
    }
  }, [sessionId])

  const loadInitialMessage = async () => {
    try {
      // чекаем есть ли сессия на бэкенде
      const response = await axios.post(`${API_URL}/chat/start/${sessionId}`)
      
      setMessages([{
        type: 'bot',
        text: response.data.message,
        timestamp: new Date().toISOString()
      }])
      setCurrentQuestion(response.data.current_question)
      setIsCompleted(response.data.is_completed)
      
    } catch (error) {
      console.error('Error loading initial message:', error)
      navigate('/')
    }
  }

  const sendMessage = async (e) => {
    e.preventDefault()
    
    if (!inputMessage.trim() || isLoading || isCompleted) return

    const userMessage = inputMessage.trim()
    
    // Добавляем сообщение пользователя
    setMessages(prev => [...prev, {
      type: 'user',
      text: userMessage,
      timestamp: new Date().toISOString()
    }])
    
    setInputMessage('')
    setIsLoading(true)

    try {
      const response = await axios.post(`${API_URL}/chat/message`, {
        session_id: sessionId,
        message: userMessage
      })

      // Добавляем ответ бота
      setMessages(prev => [...prev, {
        type: 'bot',
        text: response.data.message,
        timestamp: new Date().toISOString()
      }])

      setCurrentQuestion(response.data.current_question)
      setIsCompleted(response.data.is_completed)

    } catch (error) {
      console.error('Error sending message:', error)
      setMessages(prev => [...prev, {
        type: 'bot',
        text: 'Извините, произошла ошибка. Попробуйте еще раз.',
        timestamp: new Date().toISOString()
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const restartSurvey = () => {
    navigate('/')
  }

  if (isCompleted) {
    return (
      <div className="welcome-screen">
        <div className="welcome-card">
          <h1>Опрос завершен!</h1>
          <p>Спасибо за участие в опросе!</p>
          <p>Ваши ответы сохранены и будут использованы для исследования.</p>
          <div className="buttons-container">
            <button className="start-button" onClick={restartSurvey}>
              Пройти опрос снова
            </button>
            <button 
              className="admin-toggle-button" 
              onClick={() => navigate('/')}
            >
              На главную
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Чат-бот Опроса</h2>
        <button onClick={() => navigate('/')} className="back-button">
          ← Назад
        </button>
      </div>

      <div className="messages-container">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.type}`}>
            <div className="message-content">
              <div className="message-text">{msg.text}</div>
              <div className="message-time">
                {new Date(msg.timestamp).toLocaleTimeString('ru-RU', { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message bot">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {currentQuestion && currentQuestion.options && (
        <div className="options-hint">
          <strong>Варианты ответов:</strong>
          <ul>
            {currentQuestion.options.map((option, idx) => (
              <li key={idx}>{option.text}</li>
            ))}
          </ul>
        </div>
      )}

      {!isCompleted ? (
        <form className="input-form" onSubmit={sendMessage}>
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Введите ваш ответ..."
            disabled={isLoading}
            className="message-input"
          />
          <button 
            type="submit" 
            disabled={isLoading || !inputMessage.trim()}
            className="send-button"
          >
            {isLoading ? '...' : '➤'}
          </button>
        </form>
      ) : (
        <div className="completion-actions">
          <button className="restart-button" onClick={restartSurvey}>
            Пройти опрос заново
          </button>
        </div>
      )}
    </div>
  )
}

export default ChatPage
