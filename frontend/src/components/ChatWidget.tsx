import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { cartSessionKey } from '../lib/cartSession'
import { useSite } from '../store/SettingsContext'
import { useAuth } from '../store/AuthContext'
import { Icon } from './icons'
import { Spinner } from './ui'

interface ChatMessage {
  id: number
  author_type: 'customer' | 'staff'
  author_name: string
  body: string
  created_at: string
}

interface ChatThread {
  id: number
  name: string
  phone: string
  status: 'open' | 'closed'
  unread_customer: number
  last_message_at: string
}

export default function ChatWidget() {
  const { site } = useSite()
  const { user } = useAuth()
  const enabled = Boolean(site?.features?.chat)
  const [open, setOpen] = useState(false)
  const [thread, setThread] = useState<ChatThread | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState('')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [unread, setUnread] = useState(0)
  const sessionKey = useRef<string>('')
  const scroller = useRef<HTMLDivElement | null>(null)
  const messagesRef = useRef<ChatMessage[]>([])

  if (!sessionKey.current) sessionKey.current = cartSessionKey()

  useEffect(() => {
    if (user) {
      setName((value) => value || user.full_name || '')
      setPhone((value) => value || user.phone || '')
    }
  }, [user])

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  const merge = useCallback((incoming: ChatMessage[]) => {
    if (!incoming.length) return
    setMessages((current) => {
      const seen = new Set(current.map((item) => item.id))
      const next = [...current]
      for (const message of incoming) {
        if (!seen.has(message.id)) next.push(message)
      }
      return next.sort((a, b) => a.id - b.id)
    })
  }, [])

  const poll = useCallback(
    async (read: boolean) => {
      if (!enabled) return
      try {
        const after = read ? messagesRef.current[messagesRef.current.length - 1]?.id ?? 0 : 0
        const result = await api<{
          enabled: boolean
          thread: ChatThread | null
          messages: ChatMessage[]
        }>(
          `/chat/thread?session_key=${encodeURIComponent(sessionKey.current)}&after_id=${after}&read=${read ? 'true' : 'false'}`,
        )
        if (!result.enabled) return
        setThread(result.thread)
        if (read) merge(result.messages)
        setUnread(result.thread?.unread_customer ?? 0)
      } catch {
        // Чат не должен мешать покупкам: сетевую ошибку просто игнорируем.
      }
    },
    [enabled, merge],
  )

  useEffect(() => {
    if (!enabled) return
    void poll(false)
    const timer = window.setInterval(() => void poll(false), 25000)
    return () => window.clearInterval(timer)
  }, [enabled, poll])

  useEffect(() => {
    if (!open) return
    void poll(true)
    const timer = window.setInterval(() => void poll(true), 4500)
    return () => window.clearInterval(timer)
  }, [open, poll])

  useEffect(() => {
    if (!open || !scroller.current) return
    scroller.current.scrollTop = scroller.current.scrollHeight
  }, [open, messages])

  if (!enabled) return null

  const send = async () => {
    setError('')
    const body = text.trim()
    if (!body) return
    if (!user && !thread?.name && name.trim().length < 2) {
      setError('Представьтесь, чтобы магазин знал, кому отвечать')
      return
    }
    setSending(true)
    try {
      const result = await api<{ thread: ChatThread; message: ChatMessage }>('/chat/messages', {
        method: 'POST',
        body: {
          session_key: sessionKey.current,
          body,
          name: name.trim(),
          phone: phone.trim(),
        },
      })
      setThread(result.thread)
      merge([result.message])
      setText('')
      setUnread(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить сообщение')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {!open && (
        <button
          type="button"
          className="chat-fab"
          onClick={() => {
            setOpen(true)
            setUnread(0)
          }}
          aria-label="Чат с магазином"
        >
          <Icon name="mail" size={22} />
          {unread > 0 && <span className="chat-fab__badge">{unread}</span>}
        </button>
      )}

      {open && (
        <section className="chat-panel" aria-label="Чат с магазином">
          <header className="chat-panel__head">
            <span className="chat-panel__avatar">
              {site?.settings.brand_name?.slice(0, 1).toUpperCase() || 'М'}
            </span>
            <div>
              <strong>{site?.settings.brand_name || 'Магазин'}</strong>
              <small>{thread?.status === 'closed' ? 'Диалог закрыт — напишите, и мы откроем его снова' : 'Обычно отвечаем в течение дня'}</small>
            </div>
            <button type="button" className="chat-panel__close" onClick={() => setOpen(false)} aria-label="Свернуть чат">
              <Icon name="close" size={18} />
            </button>
          </header>

          <div className="chat-panel__messages" ref={scroller}>
            {messages.length === 0 && (
              <div className="chat-panel__intro">
                <Icon name="mail" size={24} />
                <p>Здравствуйте! Спросите о наличии, доставке или заказе — ответим здесь.</p>
              </div>
            )}
            {messages.map((message) => (
              <div
                className={`chat-bubble chat-bubble--${message.author_type === 'staff' ? 'staff' : 'customer'}`}
                key={message.id}
              >
                <p>{message.body}</p>
                <small>
                  {message.author_type === 'staff' ? message.author_name || 'Магазин' : 'Вы'} ·{' '}
                  {new Date(message.created_at).toLocaleTimeString('ru-BY', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </small>
              </div>
            ))}
          </div>

          {!user && !thread?.name && (
            <div className="chat-panel__contact">
              <input
                className="input input--sm"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Как вас зовут"
                maxLength={120}
              />
              <input
                className="input input--sm"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="Телефон (необязательно)"
                inputMode="tel"
                maxLength={20}
              />
            </div>
          )}

          {error && <div className="chat-panel__error">{error}</div>}

          <div className="chat-panel__form">
            <textarea
              className="chat-panel__input"
              rows={2}
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void send()
                }
              }}
              maxLength={2000}
              placeholder="Ваше сообщение…"
            />
            <button
              type="button"
              className="chat-panel__send"
              onClick={send}
              disabled={sending || !text.trim()}
              aria-label="Отправить"
            >
              {sending ? <Spinner size={16} /> : <Icon name="send" size={17} />}
            </button>
          </div>
        </section>
      )}
    </>
  )
}
