import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = 'http://localhost:8000'

function App() {
  const [sessionId, setSessionId] = useState(null)
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

  const startSurvey = async () => {
    setIsLoading(true)
    try {
      const response = await axios.post(`${API_URL}/chat/start`)
      setSessionId(response.data.session_id)
      setCurrentQuestion(response.data.current_question)
      setMessages([
        {
          type: 'bot',
          text: response.data.message,
          timestamp: new Date().toISOString()
        }
      ])
    } catch (error) {
      console.error('Error starting survey:', error)
      alert('Ошибка при запуске опроса. Проверить что backend запущен.')
    } finally {
      setIsLoading(false)
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

  const restartSurvey = () => {
    setSessionId(null)
    setMessages([])
    setInputMessage('')
    setIsCompleted(false)
    setCurrentQuestion(null)
    startSurvey()
  }

  if (!sessionId) {
    return (
      <div className="welcome-screen">
        <div className="welcome-card">
          <h1>Чат-бот Социологического Опроса</h1>
          <p>Добро пожаловать! ИИ проведет с вами короткий опрос.</p>
          <p>Вы можете отвечать своими словами, и ИИ постарается вас понять.</p>
          <button 
            className="start-button" 
            onClick={startSurvey}
            disabled={isLoading}
          >
            {isLoading ? 'Загрузка...' : 'Начать опрос'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Чат-бот Опроса</h2>
        {currentQuestion && (
          <span className="question-counter">
            Вопрос {currentQuestion.id} из 5
          </span>
        )}
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

export default App

