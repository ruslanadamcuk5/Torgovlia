import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/AuthContext'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { useApi } from '../lib/useApi'
import { api, authApi } from '../lib/api'
import { OrderCard, StatusTimeline } from '../components/OrderCard'
import { Modal, Spinner, EmptyState, Loader } from '../components/ui'
import { Icon } from '../components/icons'
import type { Order } from '../lib/types'
import { formatMoney, humanDate } from '../lib/format'

interface Summary {
  orders_total: number
  upcoming: Order[]
  spent_total: number
  bonus_note: string
}

export default function Account() {
  const { user, logout, reload, isAdmin, isStaff } = useAuth()
  const { site } = useSite()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'orders' | 'profile'>('orders')
  const [modal, setModal] = useState<'profile' | 'password' | 'delete' | null>(null)
  const [busy, setBusy] = useState(false)
  const [deleteForm, setDeleteForm] = useState({ password: '', confirmation: '' })

  const summary = useApi<Summary>('/account/summary')
  const orders = useApi<{ items: Order[] }>('/account/orders?limit=100')
  const [form, setForm] = useState({ full_name: user?.full_name ?? '', email: user?.email ?? '' })
  const [passwords, setPasswords] = useState({ current: '', next: '', repeat: '' })

  if (!site || !user) return null
  const s = site.settings
  const allOrders = orders.data?.items ?? []
  const upcoming = allOrders.filter((order) => ['new', 'confirmed', 'ready'].includes(order.status))
  const history = allOrders.filter((order) => !['new', 'confirmed', 'ready'].includes(order.status))

  const cancelOrder = async (order: Order) => {
    if (!window.confirm(`Отменить бронь ${order.number}? Товар снова станет доступен другим покупателям.`)) return
    setBusy(true)
    try {
      await api(`/account/orders/${order.number}/cancel`, { method: 'POST' })
      toast('Бронь отменена')
      summary.reload()
      orders.reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось отменить бронь', 'error')
    } finally {
      setBusy(false)
    }
  }

  const saveProfile = async () => {
    setBusy(true)
    try {
      await authApi.updateProfile({ full_name: form.full_name.trim(), email: form.email.trim() || undefined })
      await reload()
      toast('Профиль обновлён')
      setModal(null)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить профиль', 'error')
    } finally {
      setBusy(false)
    }
  }

  const savePassword = async () => {
    if (passwords.next.length < 8) return toast('Пароль должен содержать минимум 8 символов', 'error')
    if (passwords.next !== passwords.repeat) return toast('Пароли не совпадают', 'error')
    setBusy(true)
    try {
      const result = await authApi.changePassword(passwords.current, passwords.next)
      toast(result.message)
      setPasswords({ current: '', next: '', repeat: '' })
      setModal(null)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить пароль', 'error')
    } finally {
      setBusy(false)
    }
  }

  const deleteAccount = async () => {
    if (deleteForm.confirmation.trim().toUpperCase() !== 'УДАЛИТЬ') {
      return toast('Для подтверждения введите слово УДАЛИТЬ', 'error')
    }
    if (!deleteForm.password) return toast('Введите пароль', 'error')
    setBusy(true)
    try {
      const result = await authApi.deleteAccount(deleteForm.password, deleteForm.confirmation)
      setModal(null)
      setDeleteForm({ password: '', confirmation: '' })
      logout()
      toast(result.message)
      navigate('/')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить аккаунт', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container section account-page">
      <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Личный кабинет</span></div>

      <div className="account-head">
        <div className="account-head__user">
          <span className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</span>
          <div>
            <h1>{user.full_name}</h1>
            <p>{user.phone} · с нами с {humanDate(user.created_at.slice(0, 10))} {new Date(user.created_at).getFullYear()}</p>
          </div>
        </div>
        <div className="account-head__actions">
          {isAdmin && <Link to="/admin" className="btn btn--dark btn--sm"><Icon name="dashboard" size={17} /> Админ-панель</Link>}
          {isStaff && <Link to="/seller" className="btn btn--outline btn--sm"><Icon name="box" size={17} /> Рабочий режим</Link>}
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => { logout(); navigate('/') }}>
            <Icon name="logout" size={17} /> Выйти
          </button>
        </div>
      </div>

      <div className="account-tabs">
        <button type="button" className={tab === 'orders' ? 'is-active' : ''} onClick={() => setTab('orders')}>
          <Icon name="list" size={18} /> Мои брони
        </button>
        <button type="button" className={tab === 'profile' ? 'is-active' : ''} onClick={() => setTab('profile')}>
          <Icon name="user" size={18} /> Профиль
        </button>
      </div>

      {tab === 'orders' ? (
        <div className="account-grid">
          <aside className="account-side">
            <div className="account-stat">
              <span>Всего броней</span>
              <strong>{summary.data?.orders_total ?? '—'}</strong>
            </div>
            <div className="account-stat">
              <span>Активных</span>
              <strong>{upcoming.length}</strong>
            </div>
            <div className="account-stat">
              <span>Получено товаров на</span>
              <strong>{summary.data ? formatMoney(summary.data.spent_total) : '—'}</strong>
            </div>
            <div className="account-side__note">
              <Icon name="info" size={18} />
              <p>{s.payment_note}</p>
            </div>
            <Link to="/catalog" className="btn btn--primary btn--block">Забронировать ещё</Link>
          </aside>

          <div className="account-main">
            <section>
              <div className="section__head section__head--small">
                <div><h2>Активные брони</h2><p className="section__sub">Заказы, которые ждут вас в павильоне</p></div>
              </div>
              {summary.loading ? <Loader /> : upcoming.length > 0 ? (
                <div className="order-list">
                  {upcoming.map((order) => (
                    <div key={order.id}>
                      <OrderCard order={order} onCancel={cancelOrder} busy={busy} />
                      <StatusTimeline order={order} />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon="calendar"
                  title="Активных броней нет"
                  text="Выберите рыбу в каталоге — соберём заказ к вашему приходу."
                  action={<Link to="/catalog" className="btn btn--primary btn--sm">В каталог</Link>}
                />
              )}
            </section>

            <section>
              <div className="section__head section__head--small">
                <div><h2>История</h2><p className="section__sub">Все ваши прошлые брони</p></div>
              </div>
              {orders.loading ? <Loader /> : history.length > 0 ? (
                <div className="order-list">
                  {history.map((order) => <OrderCard key={order.id} order={order} />)}
                </div>
              ) : (
                <p className="muted">История появится после первой полученной брони.</p>
              )}
            </section>
          </div>
        </div>
      ) : (
        <div className="profile-grid">
          <section className="panel">
            <h2>Личные данные</h2>
            <div className="profile-field"><span>Имя</span><strong>{user.full_name}</strong></div>
            <div className="profile-field"><span>Телефон</span><strong>{user.phone} <em className="badge badge--fresh">подтверждён</em></strong></div>
            <div className="profile-field"><span>E-mail</span><strong>{user.email || 'не указан'}</strong></div>
            <div className="profile-field"><span>Роль</span><strong>{user.role === 'admin' ? 'Администратор' : user.role === 'seller' ? 'Продавец' : 'Покупатель'}</strong></div>
            <button type="button" className="btn btn--outline" onClick={() => { setForm({ full_name: user.full_name, email: user.email ?? '' }); setModal('profile') }}>
              <Icon name="edit" size={17} /> Изменить данные
            </button>
          </section>

          <section className="panel">
            <h2>Безопасность</h2>
            <p className="muted">Пароль хранится в виде необратимого хеша. Номер телефона подтверждён по SMS — это обязательное требование при бронировании.</p>
            <button type="button" className="btn btn--outline" onClick={() => setModal('password')}>
              <Icon name="lock" size={17} /> Сменить пароль
            </button>
            <hr />
            <h3>Удаление аккаунта</h3>
            <p className="muted">Профиль, номер телефона и комментарии будут удалены. Суммы и состав заказов сохранятся обезличенными в объёме, предусмотренном законодательством Республики Беларусь.</p>
            <button type="button" className="btn btn--danger-ghost" onClick={() => setModal('delete')}>Удалить аккаунт</button>
          </section>

          <section className="panel panel--highlight">
            <h2>Приложение для Android и iPhone</h2>
            <p>Все брони и каталог — в мобильном приложении. Установите его на телефон в один клик.</p>
            <Link to="/app" className="btn btn--primary"><Icon name="smartphone" size={18} /> Установить приложение</Link>
          </section>
        </div>
      )}

      {modal === 'profile' && (
        <Modal
          title="Личные данные"
          subtitle="Имя и e-mail видны только вам и продавцу при сборке заказа"
          onClose={() => setModal(null)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setModal(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={saveProfile} disabled={busy}>{busy ? <Spinner size={17} /> : 'Сохранить'}</button>
            </>
          )}
        >
          <label className="field">
            <span className="field__label">Имя</span>
            <input className="input" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">E-mail</span>
            <input className="input" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
          </label>
          <p className="field__hint">Телефон изменить нельзя: он подтверждён по SMS. Напишите в павильон, если номер изменился.</p>
        </Modal>
      )}

      {modal === 'password' && (
        <Modal
          title="Смена пароля"
          onClose={() => setModal(null)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setModal(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={savePassword} disabled={busy}>{busy ? <Spinner size={17} /> : 'Сохранить'}</button>
            </>
          )}
        >
          <label className="field">
            <span className="field__label">Текущий пароль</span>
            <input className="input" type="password" value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Новый пароль</span>
            <input className="input" type="password" value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} />
          </label>
          <label className="field">
            <span className="field__label">Повторите новый пароль</span>
            <input className="input" type="password" value={passwords.repeat} onChange={(event) => setPasswords({ ...passwords, repeat: event.target.value })} />
          </label>
        </Modal>
      )}

      {modal === 'delete' && (
        <Modal
          title="Удалить аккаунт?"
          subtitle="Действие необратимо. Профиль и номер телефона будут удалены, история заказов — обезличена."
          onClose={() => setModal(null)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setModal(null)}>Отмена</button>
              <button type="button" className="btn btn--danger-ghost" onClick={deleteAccount} disabled={busy}>
                {busy ? <Spinner size={17} /> : 'Удалить навсегда'}
              </button>
            </>
          )}
        >
          <label className="field">
            <span className="field__label">Текущий пароль</span>
            <input
              className="input"
              type="password"
              value={deleteForm.password}
              onChange={(event) => setDeleteForm({ ...deleteForm, password: event.target.value })}
              autoComplete="current-password"
            />
          </label>
          <label className="field">
            <span className="field__label">Введите слово УДАЛИТЬ</span>
            <input
              className="input"
              value={deleteForm.confirmation}
              onChange={(event) => setDeleteForm({ ...deleteForm, confirmation: event.target.value })}
            />
          </label>
        </Modal>
      )}
    </div>
  )
}
