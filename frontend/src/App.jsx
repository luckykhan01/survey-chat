import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import HomePage from './HomePage'
import ChatPage from './ChatPage'
import AdminPanel from './AdminPanel'
import './App.css'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat/:sessionId" element={<ChatPage />} />
        <Route path="/admin" element={<AdminPanel />} />
      </Routes>
    </Router>
  )
}

export default App