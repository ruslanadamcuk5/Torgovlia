import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Icon } from '../../components/icons'
import { EmptyState, Loader, Modal } from '../../components/ui'
import { formatMoney } from '../../lib/format'
import type { StaffTask, TaskListResponse, TaskSummary } from '../../lib/types'

const STATUS_LABEL: Record<string, string> = {
  todo: 'Новая',
  in_progress: 'В работе',
  done: 'Готово',
  cancelled: 'Отменена',
}

const STATUS_TONE: Record<string, string> = {
  todo: 'gold',
  in_progress: 'info',
  done: 'fresh',
  cancelled: 'muted',
}

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Низкий',
  normal: 'Обычный',
  high: 'Важный',
}

const FILTERS = [
  { code: 'open', title: 'Активные' },
  { code: 'todo', title: 'Новые' },
  { code: 'in_progress', title: 'В работе' },
  { code: 'done', title: 'Готовые' },
  { code: 'cancelled', title: 'Отменённые' },
  { code: 'all', title: 'Все' },
] as const

type Form = {
  title: string
  description: string
  assignee_id: string
  priority: 'low' | 'normal' | 'high'
  due_date: string
  order_id: string
  status: StaffTask['status']
}

const EMPTY_FORM: Form = {
  title: '',
  description: '',
  assignee_id: '',
  priority: 'normal',
  due_date: '',
  order_id: '',
  status: 'todo',
}

function todayStart(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

function dueInfo(task: StaffTask): { label: string; tone: 'danger' | 'warn' | 'muted' } | null {
  if (!task.due_date) return null
  const due = new Date(`${task.due_date}T00:00:00`)
  const diff = Math.round((due.getTime() - todayStart().getTime()) / 86400000)
  if (diff < 0) return { label: `Просрочено на ${Math.abs(diff)} дн.`, tone: 'danger' }
  if (diff === 0) return { label: 'Сегодня', tone: 'warn' }
  if (diff === 1) return { label: 'Завтра', tone: 'warn' }
  return {
    label: due.toLocaleDateString('ru-BY', { day: 'numeric', month: 'short' }),
    tone: 'muted',
  }
}

export default function Tasks() {
  const { toast } = useToast()
  const features = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = features.data?.services.tasks === true
  const { data, loading, error, reload } = useApi<TaskListResponse>(enabled ? '/admin/tasks' : null)

  const [filter, setFilter] = useState<string>('open')
  const [assignee, setAssignee] = useState('all')
  const [query, setQuery] = useState('')
  const [form, setForm] = useState<Form>(EMPTY_FORM)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<StaffTask | null>(null)
  const [editForm, setEditForm] = useState<Form>(EMPTY_FORM)

  const items = data?.items ?? []
  const summary: TaskSummary | undefined = data?.summary
  const staff = data?.staff ?? []
  const orders = data?.orders ?? []

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    return items.filter((task) => {
      if (filter === 'open' && !['todo', 'in_progress'].includes(task.status)) return false
      if (!['open', 'all'].includes(filter) && task.status !== filter) return false
      if (assignee !== 'all' && String(task.assignee?.id ?? '') !== assignee) return false
      if (term && !`${task.title} ${task.description} ${task.assignee?.full_name ?? ''}`.toLowerCase().includes(term)) {
        return false
      }
      return true
    })
  }, [items, filter, assignee, query])

  const submit = async () => {
    if (form.title.trim().length < 2) {
      toast('Укажите, что нужно сделать', 'error')
      return
    }
    setBusy(true)
    try {
      await api('/admin/tasks', {
        method: 'POST',
        body: {
          title: form.title.trim(),
          description: form.description.trim(),
          assignee_id: form.assignee_id ? Number(form.assignee_id) : null,
          priority: form.priority,
          due_date: form.due_date || null,
          order_id: form.order_id ? Number(form.order_id) : null,
        },
      })
      toast('Задача создана')
      setForm(EMPTY_FORM)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать задачу', 'error')
    } finally {
      setBusy(false)
    }
  }

  const patch = async (task: StaffTask, body: Record<string, unknown>, message: string) => {
    setBusy(true)
    try {
      await api(`/admin/tasks/${task.id}`, { method: 'PATCH', body })
      toast(message)
      reload()
      return true
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось обновить задачу', 'error')
      return false
    } finally {
      setBusy(false)
    }
  }

  const openEdit = (task: StaffTask) => {
    setEditing(task)
    setEditForm({
      title: task.title,
      description: task.description,
      assignee_id: task.assignee ? String(task.assignee.id) : '',
      priority: task.priority,
      due_date: task.due_date ?? '',
      order_id: task.order?.id ? String(task.order.id) : '',
      status: task.status,
    })
  }

  const saveEdit = async () => {
    if (!editing) return
    if (editForm.title.trim().length < 2) {
      toast('Укажите, что нужно сделать', 'error')
      return
    }
    const ok = await patch(
      editing,
      {
        title: editForm.title.trim(),
        description: editForm.description.trim(),
        assignee_id: editForm.assignee_id ? Number(editForm.assignee_id) : null,
        priority: editForm.priority,
        due_date: editForm.due_date || null,
        order_id: editForm.order_id ? Number(editForm.order_id) : null,
        status: editForm.status,
      },
      'Задача обновлена',
    )
    if (ok) setEditing(null)
  }

  if (features.loading) return <Loader label="Проверяем сервис" />

  if (!enabled) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="list" size={26} /></div>
        <h3>Задачи сотрудникам не подключены</h3>
        <p>Включите сервис «Задачи», чтобы назначать поручения, сроки и ответственных.</p>
        <Link to="/admin/services/tasks" className="btn btn--primary">Открыть сервис</Link>
      </div>
    )
  }

  if (loading) return <Loader label="Загружаем задачи" />
  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="alert" size={26} /></div>
        <h3>Не удалось загрузить задачи</h3>
        <p>{error}</p>
        <button type="button" className="btn btn--primary" onClick={reload}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="tasks-page">
      <section className="tasks-stats">
        <div className="panel tasks-stat">
          <span>Активные</span>
          <strong>{summary?.open ?? 0}</strong>
          <small>новые и в работе</small>
        </div>
        <div className={`panel tasks-stat ${(summary?.overdue ?? 0) > 0 ? 'is-danger' : ''}`}>
          <span>Просроченные</span>
          <strong>{summary?.overdue ?? 0}</strong>
          <small>срок уже прошёл</small>
        </div>
        <div className={`panel tasks-stat ${(summary?.today ?? 0) > 0 ? 'is-warn' : ''}`}>
          <span>На сегодня</span>
          <strong>{summary?.today ?? 0}</strong>
          <small>нужно закрыть</small>
        </div>
        <div className="panel tasks-stat">
          <span>Сделано за неделю</span>
          <strong>{summary?.done_week ?? 0}</strong>
          <small>закрытые задачи</small>
        </div>
      </section>

      <div className="tasks-layout">
        <section className="panel tasks-board">
          <div className="tasks-toolbar">
            <div className="services-tabs">
              {FILTERS.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  className={filter === item.code ? 'is-active' : ''}
                  onClick={() => setFilter(item.code)}
                >
                  {item.title}
                </button>
              ))}
            </div>
            <div className="tasks-toolbar__filters">
              <input
                className="input"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Найти задачу"
              />
              <select className="input" value={assignee} onChange={(event) => setAssignee(event.target.value)}>
                <option value="all">Все сотрудники</option>
                {staff.map((member) => (
                  <option key={member.id} value={String(member.id)}>{member.full_name}</option>
                ))}
              </select>
            </div>
          </div>

          {visible.length ? (
            <div className="tasks-list">
              {visible.map((task) => {
                const due = dueInfo(task)
                return (
                  <article
                    key={task.id}
                    className={`task-card task-card--${task.status} ${task.overdue ? 'is-overdue' : ''}`}
                  >
                    <div className="task-card__main">
                      <header>
                        <div>
                          <h3>{task.title}</h3>
                          <div className="task-card__badges">
                            <span className={`badge badge--${STATUS_TONE[task.status]}`}>{STATUS_LABEL[task.status]}</span>
                            <span className={`task-priority task-priority--${task.priority}`}>
                              {PRIORITY_LABEL[task.priority]}
                            </span>
                            {due && <span className={`task-due task-due--${due.tone}`}>{due.label}</span>}
                          </div>
                        </div>
                        <button type="button" className="icon-btn" title="Изменить" onClick={() => openEdit(task)}>
                          <Icon name="edit" size={17} />
                        </button>
                      </header>

                      {task.description && <p>{task.description}</p>}

                      <div className="task-card__meta">
                        <span>
                          <Icon name="users" size={13} />
                          {task.assignee ? task.assignee.full_name : 'Без ответственного'}
                        </span>
                        {task.order && (
                          <Link to="/admin/orders">
                            <Icon name="list" size={13} />
                            {task.order.number} · {formatMoney(task.order.total)}
                          </Link>
                        )}
                        <span className="task-card__author">
                          {task.created_by ? `Поставил: ${task.created_by.full_name}` : ''}
                        </span>
                      </div>
                    </div>

                    <div className="task-card__actions">
                      {task.status === 'todo' && (
                        <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void patch(task, { status: 'in_progress' }, 'Задача взята в работу')}>
                          В работу
                        </button>
                      )}
                      {['todo', 'in_progress'].includes(task.status) && (
                        <button type="button" className="btn btn--sm btn--primary" disabled={busy} onClick={() => void patch(task, { status: 'done' }, 'Задача закрыта')}>
                          <Icon name="check" size={14} /> Готово
                        </button>
                      )}
                      {['done', 'cancelled'].includes(task.status) && (
                        <button type="button" className="btn btn--sm btn--outline" disabled={busy} onClick={() => void patch(task, { status: 'todo' }, 'Задача возвращена')}>
                          Вернуть
                        </button>
                      )}
                      {task.status !== 'cancelled' && (
                        <button type="button" className="btn btn--sm btn--ghost" disabled={busy} onClick={() => void patch(task, { status: 'cancelled' }, 'Задача отменена')}>
                          Отменить
                        </button>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <EmptyState
              icon="check"
              title="Задач нет"
              text="Измените фильтр или создайте первое поручение справа."
            />
          )}
        </section>

        <aside className="panel tasks-form">
          <div className="panel__head">
            <div>
              <h2>Новая задача</h2>
              <p className="muted">Поручение появится у сотрудника в рабочем режиме.</p>
            </div>
          </div>
          <label className="field">
            <span className="field__label">Что сделать</span>
            <input
              className="input"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder="Например: проверить остатки трикотажа"
              maxLength={160}
            />
          </label>
          <label className="field">
            <span className="field__label">Подробности</span>
            <textarea
              className="textarea"
              rows={3}
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              placeholder="Что именно сделать и на что обратить внимание"
            />
          </label>
          <div className="tasks-form__row">
            <label className="field">
              <span className="field__label">Ответственный</span>
              <select className="input" value={form.assignee_id} onChange={(event) => setForm({ ...form, assignee_id: event.target.value })}>
                <option value="">Без ответственного</option>
                {staff.map((member) => (
                  <option key={member.id} value={String(member.id)}>{member.full_name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Приоритет</span>
              <select className="input" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as Form['priority'] })}>
                <option value="low">Низкий</option>
                <option value="normal">Обычный</option>
                <option value="high">Важный</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span className="field__label">Срок</span>
            <input className="input" type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Связать с заказом</span>
            <select className="input" value={form.order_id} onChange={(event) => setForm({ ...form, order_id: event.target.value })}>
              <option value="">Без заказа</option>
              {orders.map((order) => (
                <option key={order.id} value={String(order.id)}>
                  {order.number} · {order.customer_name} · {formatMoney(order.total)}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void submit()}>
            <Icon name="plus" size={16} /> {busy ? 'Сохраняем…' : 'Создать задачу'}
          </button>
        </aside>
      </div>

      {editing && (
        <Modal
          title="Изменить задачу"
          subtitle={editing.title}
          onClose={() => setEditing(null)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setEditing(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void saveEdit()}>
                {busy ? 'Сохраняем…' : 'Сохранить'}
              </button>
            </>
          )}
        >
          <label className="field">
            <span className="field__label">Что сделать</span>
            <input className="input" value={editForm.title} onChange={(event) => setEditForm({ ...editForm, title: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Подробности</span>
            <textarea className="textarea" rows={3} value={editForm.description} onChange={(event) => setEditForm({ ...editForm, description: event.target.value })} />
          </label>
          <div className="tasks-form__row">
            <label className="field">
              <span className="field__label">Ответственный</span>
              <select className="input" value={editForm.assignee_id} onChange={(event) => setEditForm({ ...editForm, assignee_id: event.target.value })}>
                <option value="">Без ответственного</option>
                {staff.map((member) => (
                  <option key={member.id} value={String(member.id)}>{member.full_name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Статус</span>
              <select className="input" value={editForm.status} onChange={(event) => setEditForm({ ...editForm, status: event.target.value as Form['status'] })}>
                {Object.entries(STATUS_LABEL).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="tasks-form__row">
            <label className="field">
              <span className="field__label">Приоритет</span>
              <select className="input" value={editForm.priority} onChange={(event) => setEditForm({ ...editForm, priority: event.target.value as Form['priority'] })}>
                <option value="low">Низкий</option>
                <option value="normal">Обычный</option>
                <option value="high">Важный</option>
              </select>
            </label>
            <label className="field">
              <span className="field__label">Срок</span>
              <input className="input" type="date" value={editForm.due_date} onChange={(event) => setEditForm({ ...editForm, due_date: event.target.value })} />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Заказ</span>
            <select className="input" value={editForm.order_id} onChange={(event) => setEditForm({ ...editForm, order_id: event.target.value })}>
              <option value="">Без заказа</option>
              {orders.map((order) => (
                <option key={order.id} value={String(order.id)}>
                  {order.number} · {order.customer_name}
                </option>
              ))}
            </select>
          </label>
        </Modal>
      )}
    </div>
  )
}
