
import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState([])
  const [messages, setMessages] = useState([])

  const suggestedQuestions = [
    "Tell me about yourself",
    "What are your technical skills?",
    "Explain your projects",
    "What is your educational background?",
    "What are your strengths?",
    "Why should we hire you?"
  ]

  // Load saved chat history from MongoDB when page opens
  useEffect(() => {
    async function loadHistory() {
      try {
        const response = await fetch('http://127.0.0.1:8000/history')

        if (!response.ok) {
          throw new Error('Unable to load chat history')
        }

        const data = await response.json()

        const savedHistory = data.history.map((item) => ({
          id: item.id,
          question: item.question,
          answer: item.answer,
          loading: false
        }))

        setHistory(savedHistory)

      } catch (error) {
        console.error('History loading error:', error)
      }
    }

    loadHistory()
  }, [])

  // Send question to backend
  async function handleSend(selectedQuestion) {
    let finalQuestion = selectedQuestion || question

    if (finalQuestion.trim() === '') {
      return
    }

    const temporaryId = Date.now()

    const newMessage = {
      id: temporaryId,
      question: finalQuestion,
      answer: '',
      loading: true
    }

    setMessages((previousMessages) => [
      ...previousMessages,
      newMessage
    ])

    setHistory((previousHistory) => [
      ...previousHistory,
      newMessage
    ])

    setQuestion('')

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          question: finalQuestion
        })
      })

      if (!response.ok) {
        throw new Error('Something went wrong with the backend.')
      }

      const data = await response.json()

      const updatedMessage = {
        id: data.id,
        question: finalQuestion,
        answer: data.answer,
        loading: false
      }

      setMessages((previousMessages) =>
        previousMessages.map((item) => {
          if (item.id === temporaryId) {
            return updatedMessage
          }

          return item
        })
      )

      setHistory((previousHistory) =>
        previousHistory.map((item) => {
          if (item.id === temporaryId) {
            return updatedMessage
          }

          return item
        })
      )

    } catch (error) {
      const errorMessage =
        'Unable to get an answer. Please check whether the backend is running.'

      setMessages((previousMessages) =>
        previousMessages.map((item) => {
          if (item.id === temporaryId) {
            return {
              ...item,
              answer: errorMessage,
              loading: false
            }
          }

          return item
        })
      )

      setHistory((previousHistory) =>
        previousHistory.map((item) => {
          if (item.id === temporaryId) {
            return {
              ...item,
              answer: errorMessage,
              loading: false
            }
          }

          return item
        })
      )
    }
  }

  // Open an old conversation
  function openHistory(item) {
    setMessages([item])
    setQuestion('')
  }

  // Start a new chat without deleting saved history
  function handleNewChat() {
    setMessages([])
    setQuestion('')
  }

  return (
    <div className="app">

      {/* LEFT SIDEBAR */}

      <aside className="sidebar">

        <h2>Chat History</h2>

        <button
          className="new-chat"
          onClick={handleNewChat}
        >
          + New Chat
        </button>

        <div className="history-list">

          {history.map((item) => (
            <button
              className="history-item"
              key={item.id}
              onClick={() => openHistory(item)}
            >
              {item.question}
            </button>
          ))}

        </div>

      </aside>

      {/* MAIN CONTENT */}

      <main className="main-content">

        <div className="heading">
          <h1>PORTFOLIO</h1>
          <h3>Ishika's Portfolio</h3>
        </div>

        <div className="welcome">

          {messages.length === 0 && (
            <>
              <h2>Meet the Candidate</h2>

              <p>
                Ask me anything about the candidate's
                skills, projects and experience.
              </p>
            </>
          )}

          {/* CHAT CONVERSATION */}

          <div className="conversation">

            {messages.map((item) => (
              <div className="message-group" key={item.id}>

                <div className="user-message">
                  {item.question}
                </div>

                <div className="assistant-message">

                  <div className="assistant-header">
                    <div className="ai-avatar">✦</div>
                    <span>AI ASSISTANT</span>
                  </div>

                  <div className="assistant-content">
                    {item.loading ? (
                      'Thinking...'
                    ) : (
                      <ReactMarkdown>
                        {item.answer}
                      </ReactMarkdown>
                    )}
                  </div>

                </div>

              </div>
            ))}

          </div>

          {/* FREQUENTLY ASKED QUESTIONS */}

          <div className="frequent-questions">

            <h3>Frequently Asked Questions</h3>

            <div className="suggestions">

              {suggestedQuestions.map((item, index) => (
                <button
                  key={index}
                  className="suggestion-button"
                  onClick={() => handleSend(item)}
                >
                  {item}
                </button>
              ))}

            </div>

          </div>

          {/* CHAT INPUT */}

          <div className="chat-box">

            <input
              type="text"
              placeholder="Ask anything about the candidate..."
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleSend()
                }
              }}
            />

            <button onClick={() => handleSend()}>
              Send
            </button>

          </div>

        </div>

      </main>

    </div>
  )
}

export default App
