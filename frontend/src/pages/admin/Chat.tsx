import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'

interface ChatMessage {
  id: number
  author_type: 'customer' | 'staff'
  author_name: string
  body: string
  created_at: string
}

interface Thread {
  id: number
  name: string
  phone: string
  phone_raw: string
  email: string
  status: 'open' | 'closed'
  unread_staff: number
  unread_customer: number
  last_message: string
  last_message_at: string
  created_at: string
}

interface ThreadList {
  items: Thread[]
  total: number
  summary: { open: number; unread: number }
}

type Tab = 'open' | 'closed' | 'all'

const TABS: { code: Tab; title: string }[] = [
  { code: 'open', title: 'Открытые' },
  { code: 'closed', title: 'Закрытые' },
  { code: 'all', title: 'Все' },
]

function timeLabel(value: string): string {
  const date = new Date(value)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString('ru-BY', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('ru-BY', { day: '2-digit', month: '2-digit' })
}

export default function Chat() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>(
    '/admin/services/features',
  )
  const enabled = Boolean(features?.services.support_chat)

  const [tab, setTab] = useState<Tab>('open')
  const [search, setSearch] = useState('')
  const { data: list, loading: listLoading, reload: reloadList } = useApi<ThreadList>(
    enabled ? `/admin/chat/threads?status=${tab}&search=${encodeURIComponent(search.trim())}` : null,
  )

  const [activeId, setActiveId] = useState<number | null>(null)
  const [thread, setThread] = useState<Thread | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [busyStatus, setBusyStatus] = useState(false)
  const messagesRef = useRef<ChatMessage[]>([])
  const scroller = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  const merge = useCallback((incoming: ChatMessage[]) => {
    if (!incoming.length) return
    setMessages((current) => {
      const seen = new Set(current.map((item) => item.id))
      const next = [...current]
      for (const message of incoming) if (!seen.has(message.id)) next.push(message)
      return next.sort((a, b) => a.id - b.id)
    })
  }, [])

  const loadThread = useCallback(
    async (id: number, after = 0) => {
      try {
        const result = await api<{ thread: Thread; messages: ChatMessage[] }>(
          `/admin/chat/threads/${id}${after ? `?after_id=${after}` : ''}`,
        )
        setThread(result.thread)
        if (after) merge(result.messages)
        else setMessages(result.messages)
      } catch (err) {
        toast(err instanceof Error ? err.message : 'Не удалось открыть диалог', 'error')
        setActiveId(null)
      }
    },
    [merge, toast],
  )

  useEffect(() => {
    if (!activeId) {
      setThread(null)
      setMessages([])
      return
    }
    setMessages([])
    void loadThread(activeId)
    reloadList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId])

  useEffect(() => {
    if (!enabled || !activeId) return
    const timer = window.setInterval(() => {
      const last = messagesRef.current[messagesRef.current.length - 1]?.id ?? 0
      void loadThread(activeId, last)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [enabled, activeId, loadThread])

  useEffect(() => {
    if (!list?.items.length) {
      setActiveId(null)
      return
    }
    if (!activeId || !list.items.some((item) => item.id === activeId)) {
      setActiveId(list.items[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list])

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight
  }, [messages])

  const unreadTotal = useMemo(
    () => (list?.items ?? []).reduce((sum, item) => sum + item.unread_staff, 0),
    [list],
  )

  const send = async () => {
    if (!activeId || !text.trim()) return
    setSending(true)
    try {
      const result = await api<{ thread: Thread; message: ChatMessage }>(
        `/admin/chat/threads/${activeId}/messages`,
        { method: 'POST', body: { body: text.trim() } },
      )
      setThread(result.thread)
      merge([result.message])
      setText('')
      reloadList()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отправить ответ', 'error')
    } finally {
      setSending(false)
    }
  }

  const toggleStatus = async () => {
    if (!activeId || !thread) return
    setBusyStatus(true)
    try {
      const next = thread.status === 'open' ? 'closed' : 'open'
      const updated = await api<Thread>(`/admin/chat/threads/${activeId}`, {
        method: 'PATCH',
        body: { status: next },
      })
      setThread(updated)
      reloadList()
      toast(next === 'open' ? 'Диалог открыт' : 'Диалог закрыт')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить статус', 'error')
    } finally {
      setBusyStatus(false)
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Чат с покупателем</h2></div>
          <p>
            Онлайн-чат на витрине доступен на тарифе <strong>«Бизнес»</strong>. Покупатель
            пишет с сайта, вы отвечаете из этой панели.
          </p>
          <Link to="/admin/services" className="btn btn--primary">
            Перейти к сервисам <Icon name="arrow-right" size={17} />
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="admin-page chat-page">
      <section className="panel chat-layout">
        <div className="chat-sidebar">
          <div className="chat-sidebar__head">
            <div>
              <h2>Чат</h2>
              <p className="muted">
                {list?.summary.open ?? 0} открытых
                {unreadTotal > 0 ? ` · ${unreadTotal} новых` : ''}
              </p>
            </div>
          </div>

          <div className="chat-search">
            <Icon name="search" size={15} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Имя, телефон или текст"
            />
          </div>

          <div className="chat-tabs">
            {TABS.map((item) => (
              <button
                key={item.code}
                type="button"
                className={tab === item.code ? 'is-active' : ''}
                onClick={() => setTab(item.code)}
              >
                {item.title}
              </button>
            ))}
          </div>

          <div className="chat-threads">
            {listLoading && <p className="muted chat-threads__loading">Загружаем диалоги…</p>}
            {(list?.items ?? []).map((item) => (
              <button
                type="button"
                key={item.id}
                className={`chat-thread${activeId === item.id ? ' is-active' : ''}${item.unread_staff ? ' is-unread' : ''}`}
                onClick={() => setActiveId(item.id)}
              >
                <span className="chat-thread__avatar">{item.name.slice(0, 1).toUpperCase()}</span>
                <span className="chat-thread__main">
                  <span className="chat-thread__top">
                    <strong>{item.name}</strong>
                    <small>{timeLabel(item.last_message_at)}</small>
                  </span>
                  <span className="chat-thread__preview">{item.last_message || 'Без сообщений'}</span>
                  <span className="chat-thread__meta">
                    {item.phone || 'без телефона'}
                    {item.status === 'closed' && <em>закрыт</em>}
                  </span>
                </span>
                {item.unread_staff > 0 && <span className="chat-thread__badge">{item.unread_staff}</span>}
              </button>
            ))}
            {!listLoading && (list?.items ?? []).length === 0 && (
              <div className="chat-empty">
                <Icon name="mail" size={22} />
                <p>
                  {search
                    ? 'По запросу диалогов нет.'
                    : tab === 'open'
                      ? 'Открытых диалогов нет. Сообщения с витрины появятся здесь.'
                      : 'В этом списке пусто.'}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="chat-conversation">
          {!thread && (
            <div className="chat-conversation__empty">
              <Icon name="mail" size={30} />
              <h3>Выберите диалог</h3>
              <p className="muted">Покупатели пишут с витрины, ответ приходит в эту панель.</p>
            </div>
          )}

          {thread && (
            <>
              <header className="chat-conversation__head">
                <div>
                  <h3>{thread.name}</h3>
                  <p className="muted">
                    {thread.phone || 'без телефона'}
                    {thread.email ? ` · ${thread.email}` : ''}
                  </p>
                </div>
                <div className="chat-conversation__actions">
                  <span className={`chat-status chat-status--${thread.status}`}>
                    {thread.status === 'open' ? 'Открыт' : 'Закрыт'}
                  </span>
                  <button
                    type="button"
                    className="btn btn--sm btn--ghost"
                    onClick={toggleStatus}
                    disabled={busyStatus}
                  >
                    {busyStatus ? <Spinner size={14} /> : <Icon name={thread.status === 'open' ? 'check' : 'refresh'} size={15} />}
                    {thread.status === 'open' ? 'Закрыть' : 'Открыть'}
                  </button>
                </div>
              </header>

              <div className="chat-conversation__messages" ref={scroller}>
                {messages.length === 0 && <p className="muted chat-conversation__note">Сообщений пока нет.</p>}
                {messages.map((message) => (
                  <div
                    className={`chat-bubble chat-bubble--${message.author_type === 'staff' ? 'staff' : 'customer'}`}
                    key={message.id}
                  >
                    <p>{message.body}</p>
                    <small>
                      {message.author_type === 'staff' ? message.author_name || 'Магазин' : thread.name} ·{' '}
                      {new Date(message.created_at).toLocaleString('ru-BY', {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </small>
                  </div>
                ))}
              </div>

              <div className="chat-conversation__form">
                <textarea
                  className="chat-conversation__input"
                  rows={3}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      void send()
                    }
                  }}
                  maxLength={2000}
                  placeholder="Ответ покупателю…"
                />
                <div className="chat-conversation__send">
                  <span className="muted">Enter — отправить, Shift+Enter — новая строка</span>
                  <button type="button" className="btn btn--primary btn--sm" onClick={send} disabled={sending || !text.trim()}>
                    {sending ? <Spinner size={15} /> : <Icon name="send" size={15} />} Отправить
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  )
}
