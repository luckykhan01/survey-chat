import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './AdminPanel.css'

const API_URL = 'http://localhost:8000'

function AdminPanel() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [token, setToken] = useState('')
  const [stats, setStats] = useState(null)
  const [responses, setResponses] = useState([])
  const [currentSurvey, setCurrentSurvey] = useState([])
  const [activeTab, setActiveTab] = useState('dashboard')
  const [loginData, setLoginData] = useState({ username: '', password: '' })


  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      const response = await axios.post(`${API_URL}/admin/login`, loginData)
      setToken(response.data.token)
      setIsLoggedIn(true)
      localStorage.setItem('admin_token', response.data.token)
    } catch (error) {
      alert('Ошибка авторизации: ' + error.response?.data?.detail)
    }
  }

  // проверка токена 
  useEffect(() => {
    const savedToken = localStorage.getItem('admin_token')
    if (savedToken) {
      setToken(savedToken)
      setIsLoggedIn(true)
    }
  }, [])

  // грузим данные
  useEffect(() => {
    if (isLoggedIn) {
      loadStats()
      loadResponses()
      loadCurrentSurvey()
    }
  }, [isLoggedIn])

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setStats(response.data)
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }

  const loadResponses = async () => {
    try {
      const response = await axios.get(`${API_URL}/admin/responses`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setResponses(response.data.responses)
    } catch (error) {
      console.error('Error loading responses:', error)
    }
  }

  const loadCurrentSurvey = async () => {
    try {
      const response = await axios.get(`${API_URL}/admin/survey/current`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setCurrentSurvey(response.data)
    } catch (error) {
      console.error('Error loading survey:', error)
    }
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    setToken('')
    localStorage.removeItem('admin_token')
  }

  const exportCSV = async () => {
    try {
      const response = await axios.get(`${API_URL}/admin/export/csv`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      
      // создаем и скачиваем файл
      const blob = new Blob([response.data.csv_data], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `survey_results_${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      alert('Ошибка экспорта: ' + error.response?.data?.detail)
    }
  }

  if (!isLoggedIn) {
    return (
      <div className="admin-login">
        <div className="login-card">
          <h1>Admin</h1>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Логин:</label>
              <input
                type="text"
                value={loginData.username}
                onChange={(e) => setLoginData({...loginData, username: e.target.value})}
                required
              />
            </div>
            <div className="form-group">
              <label>Пароль:</label>
              <input
                type="password"
                value={loginData.password}
                onChange={(e) => setLoginData({...loginData, password: e.target.value})}
                required
              />
            </div>
            <button type="submit" className="login-button">
              Войти
            </button>
          </form>
          <p className="login-hint">
            Логин: admin, Пароль: admin123
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-panel">
      <header className="admin-header">
        <h1>Admin</h1>
        <button onClick={handleLogout} className="logout-button">
          Выйти
        </button>
      </header>

      <nav className="admin-nav">
        <button 
          className={activeTab === 'dashboard' ? 'active' : ''}
          onClick={() => setActiveTab('dashboard')}
        >
          Дашборд
        </button>
        <button 
          className={activeTab === 'responses' ? 'active' : ''}
          onClick={() => setActiveTab('responses')}
        >
          Ответы
        </button>
        <button 
          className={activeTab === 'survey' ? 'active' : ''}
          onClick={() => setActiveTab('survey')}
        >
          Управление опросом
        </button>
      </nav>

      <main className="admin-content">
        {activeTab === 'dashboard' && (
          <div className="dashboard">
            <h2>Статистика</h2>
            {stats && (
              <div className="stats-grid">
                <div className="stat-card">
                  <h3>Всего сессий</h3>
                  <div className="stat-number">{stats.total_sessions}</div>
                </div>
                <div className="stat-card">
                  <h3>Завершенных опросов</h3>
                  <div className="stat-number">{stats.completed_surveys}</div>
                </div>
                <div className="stat-card">
                  <h3>Активных сессий</h3>
                  <div className="stat-number">{stats.active_sessions}</div>
                </div>
                <div className="stat-card">
                  <h3>Процент завершения</h3>
                  <div className="stat-number">
                    {stats.total_sessions > 0 
                      ? Math.round((stats.completed_surveys / stats.total_sessions) * 100)
                      : 0}%
                  </div>
                </div>
              </div>
            )}

            <div className="recent-responses">
              <h3>Последние ответы</h3>
              <div className="responses-list">
                {stats?.recent_responses.map((response, index) => (
                  <div key={index} className="response-item">
                    <div className="response-info">
                      <span className="session-id">{response.session_id.slice(0, 8)}...</span>
                      <span className="answers-count">{response.answers_count} ответов</span>
                      <span className="timestamp">
                        {new Date(response.started_at).toLocaleString('ru-RU')}
                      </span>
                    </div>
                    {response.last_answer && (
                      <div className="last-answer">
                        <strong>Последний ответ:</strong> {response.last_answer.original_answer}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="export-section">
              <button onClick={exportCSV} className="export-button">
                Экспорт в CSV
              </button>
            </div>
          </div>
        )}

        {activeTab === 'responses' && (
          <div className="responses-tab">
            <h2>Все ответы</h2>
            <div className="responses-table">
              {responses.map((response, index) => (
                <div key={index} className="response-card">
                  <div className="response-header">
                    <span className="session-id">Сессия: {response.session_id.slice(0, 8)}...</span>
                    <span className="timestamp">
                      {new Date(response.timestamp).toLocaleString('ru-RU')}
                    </span>
                    <span className={`status ${response.status || 'completed'}`}>
                      {response.status || 'completed'}
                    </span>
                  </div>
                  <div className="answers-list">
                    {response.answers.map((answer, answerIndex) => (
                      <div key={answerIndex} className="answer-item">
                        <div className="question">{answer.question}</div>
                        <div className="answer-details">
                          <span className="codes">Коды: {answer.answer_codes.join(', ')}</span>
                          <span className="original">Ответ: "{answer.original_answer}"</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'survey' && (
          <div className="survey-tab">
            <h2>Управление опросом</h2>
            
            <div className="current-survey">
              <h3>Текущий опрос</h3>
              <div className="questions-list">
                {currentSurvey.map((question, index) => (
                  <div key={index} className="question-card">
                    <div className="question-header">
                      <span className="question-id">Вопрос {question.id}</span>
                      <span className="question-type">{question.type}</span>
                    </div>
                    <div className="question-text">{question.question}</div>
                    <div className="question-options">
                      {question.options.map((option, optIndex) => (
                        <div key={optIndex} className="option">
                          <span className="option-code">{option.code}</span>
                          <span className="option-text">{option.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="upload-section">
              <h3>Загрузить новый опрос</h3>
              <textarea
                placeholder="Вставьте JSON с вопросами..."
                className="json-textarea"
                rows="10"
              />
              <button className="upload-button">
                Загрузить опрос
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default AdminPanel
