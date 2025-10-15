import { useState } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = 'http://localhost:8000'

function HomePage() {
  const [isLoading, setIsLoading] = useState(false)

  const startSurvey = async () => {
    setIsLoading(true)
    try {
      // Создаем новую сессию
      const response = await axios.post(`${API_URL}/chat/start`)
      // Перенаправляем на страницу чата с session_id
      window.location.href = `/chat/${response.data.session_id}`
    } catch (error) {
      console.error('Error starting survey:', error)
      alert('Ошибка при запуске опроса. Попробуйте еще раз.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="welcome-screen">
      <div className="welcome-card">
        <h1>Чат-бот Социологического Опроса</h1>
        <p>Добро пожаловать! ИИ проведет с вами короткий опрос.</p>
        <p>Вы можете отвечать своими словами, и ИИ постарается вас понять.</p>
        <div className="buttons-container">
          <button 
            className="start-button" 
            onClick={startSurvey}
            disabled={isLoading}
          >
            {isLoading ? 'Загрузка...' : 'Начать опрос'}
          </button>
          <button 
            className="admin-toggle-button" 
            onClick={() => window.location.href = '/admin'}
          >
            Admin
          </button>
        </div>
      </div>
    </div>
  )
}

export default HomePage
