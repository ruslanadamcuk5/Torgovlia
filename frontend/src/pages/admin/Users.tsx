import { useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useAuth } from '../../store/AuthContext'
import { useToast } from '../../store/ToastContext'
import { Loader, Modal, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { AdminUser, Role } from '../../lib/types'
import { normalizePhoneInput, phonePretty } from '../../lib/format'

const ROLE_LABEL: Record<Role, string> = {
  admin: 'Администратор',
  seller: 'Продавец',
  customer: 'Покупатель',
}

export default function AdminUsers() {
  const { user: me } = useAuth()
  const { toast } = useToast()
  const [query, setQuery] = useState('')
  const [role, setRole] = useState('all')
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<AdminUser | null>(null)
  const [busy, setBusy] = useState(false)

  const params = new URLSearchParams({ limit: '500' })
  if (query.trim()) params.set('q', query.trim())
  if (role !== 'all') params.set('role', role)
  const { data, loading, reload } = useApi<{ items: AdminUser[]; total: number }>(`/admin/users?${params.toString()}`)

  const [createForm, setCreateForm] = useState({ full_name: '', phone: '', role: 'seller' as Role, password: '' })
  const [editForm, setEditForm] = useState({ full_name: '', email: '', role: 'customer' as Role })

  const openEdit = (user: AdminUser) => {
    setEditing(user)
    setEditForm({
      full_name: user.full_name,
      email: user.email ?? '',
      role: user.role,
    })
  }

  const createStaff = async () => {
    if (createForm.full_name.trim().length < 2) return toast('Укажите имя сотрудника', 'error')
    if (createForm.phone.replace(/\D/g, '').length < 9) return toast('Укажите телефон', 'error')
    if (createForm.password.length < 8) return toast('Пароль должен быть не короче 8 символов', 'error')
    setBusy(true)
    try {
      await api('/admin/users', { method: 'POST', body: createForm })
      toast('Сотрудник создан. Передайте пароль лично.')
      setCreating(false)
      setCreateForm({ full_name: '', phone: '', role: 'seller', password: '' })
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось создать сотрудника', 'error')
    } finally {
      setBusy(false)
    }
  }

  const saveUser = async () => {
    if (!editing) return
    setBusy(true)
    try {
      await api(`/admin/users/${editing.id}`, {
        method: 'PATCH',
        body: {
          full_name: editForm.full_name.trim(),
          email: editForm.email.trim() || null,
          role: editForm.role,
        },
      })
      toast('Данные пользователя обновлены')
      setEditing(null)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить пользователя', 'error')
    } finally {
      setBusy(false)
    }
  }

  const updateRole = async (user: AdminUser, nextRole: Role) => {
    if (user.id === me?.id && nextRole !== 'admin') return toast('Нельзя снять права администратора с себя', 'error')
    try {
      await api(`/admin/users/${user.id}/role`, { method: 'POST', body: { role: nextRole } })
      toast(`Роль: ${ROLE_LABEL[nextRole].toLowerCase()}`)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить роль', 'error')
    }
  }

  const toggleBlock = async (user: AdminUser) => {
    if (user.id === me?.id) return toast('Нельзя заблокировать свою учётную запись', 'error')
    try {
      await api(`/admin/users/${user.id}/block`, { method: 'POST', body: { is_active: !user.is_active } })
      toast(user.is_active ? 'Пользователь заблокирован' : 'Доступ восстановлен')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить доступ', 'error')
    }
  }

  return (
    <div className="admin-page">
      <div className="admin-toolbar">
        <div className="admin-toolbar__left">
          <label className="search-field">
            <Icon name="search" size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Имя, телефон или e-mail" type="search" />
          </label>
        </div>
        <div className="admin-toolbar__right">
          <span className="muted">{data?.total ?? 0} пользователей</span>
          <button type="button" className="btn btn--sm btn--primary" onClick={() => setCreating(true)}>
            <Icon name="plus" size={16} /> Добавить сотрудника
          </button>
        </div>
      </div>

      <div className="admin-tabs">
        {(['all', 'customer', 'seller', 'admin'] as const).map((value) => (
          <button key={value} type="button" className={role === value ? 'is-active' : ''} onClick={() => setRole(value)}>
            {value === 'all' ? 'Все' : value === 'customer' ? 'Покупатели' : value === 'seller' ? 'Продавцы' : 'Администраторы'}
          </button>
        ))}
      </div>

      {loading ? <Loader /> : data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table data-table--users">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Роль</th>
                <th>Брони</th>
                <th>Регистрация</th>
                <th>Доступ</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((user) => (
                <tr key={user.id} className={!user.is_active ? 'is-muted' : ''}>
                  <td>
                    <div className="table-product">
                      <span className="avatar avatar--sm">{user.full_name.slice(0, 1).toUpperCase()}</span>
                      <div>
                        <strong>{user.full_name} {user.id === me?.id && <span className="badge badge--soft">вы</span>}</strong>
                        <span className="table-sub">{user.phone_formatted || user.phone} {user.email ? `· ${user.email}` : ''}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <select
                      className={`input input--sm input--select role-select role-select--${user.role}`}
                      value={user.role}
                      onChange={(event) => void updateRole(user, event.target.value as Role)}
                    >
                      {(['customer', 'seller', 'admin'] as Role[]).map((value) => <option key={value} value={value}>{ROLE_LABEL[value]}</option>)}
                    </select>
                  </td>
                  <td>
                    <strong>{user.orders_count}</strong>
                    <span className="table-sub">{user.last_order_at ? `последняя ${new Date(user.last_order_at).toLocaleDateString('ru-BY')}` : 'нет заказов'}</span>
                  </td>
                  <td>
                    {new Date(user.created_at).toLocaleDateString('ru-BY')}
                    {user.is_phone_verified && <span className="table-sub">телефон подтверждён</span>}
                  </td>
                  <td>
                    <span className={`badge ${user.is_active ? 'badge--fresh' : 'badge--muted'}`}>{user.is_active ? 'активен' : 'заблокирован'}</span>
                  </td>
                  <td>
                    <div className="row row--nowrap">
                      <button type="button" className="icon-btn" onClick={() => openEdit(user)} title="Редактировать"><Icon name="edit" size={17} /></button>
                      <button
                        type="button"
                        className={`icon-btn ${user.is_active ? 'icon-btn--danger' : ''}`}
                        onClick={() => void toggleBlock(user)}
                        title={user.is_active ? 'Заблокировать' : 'Разблокировать'}
                        disabled={user.id === me?.id}
                      >
                        <Icon name={user.is_active ? 'lock' : 'check'} size={17} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="users" size={28} /></span>
          <h3>Пользователи не найдены</h3>
          <p>Измените фильтр или поисковый запрос.</p>
        </div>
      )}

      <div className="notice notice--info">
        <Icon name="shield" size={18} />
        <span>
          Администратор видит и настраивает весь сайт. Продавец работает только в режиме каталога и броней.
          Роли назначаются мгновенно — при следующем входе сотрудник увидит новый интерфейс.
        </span>
      </div>

      {creating && (
        <Modal
          title="Новый сотрудник"
          subtitle="Создайте доступ для продавца или администратора"
          onClose={() => setCreating(false)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setCreating(false)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={createStaff} disabled={busy}>
                {busy ? <Spinner size={17} /> : 'Создать доступ'}
              </button>
            </>
          )}
        >
          <label className="field"><span className="field__label">Имя и фамилия *</span><input className="input" value={createForm.full_name} onChange={(event) => setCreateForm({ ...createForm, full_name: event.target.value })} /></label>
          <label className="field">
            <span className="field__label">Мобильный телефон *</span>
            <input className="input" value={createForm.phone} onChange={(event) => setCreateForm({ ...createForm, phone: normalizePhoneInput(event.target.value) })} onBlur={() => setCreateForm({ ...createForm, phone: phonePretty(createForm.phone) })} placeholder="+375 29 123-45-67" inputMode="tel" />
          </label>
          <label className="field">
            <span className="field__label">Роль</span>
            <select className="input input--select" value={createForm.role} onChange={(event) => setCreateForm({ ...createForm, role: event.target.value as Role })}>
              <option value="customer">Покупатель</option>
              <option value="seller">Продавец</option>
              <option value="admin">Администратор</option>
            </select>
          </label>
          <label className="field">
            <span className="field__label">Пароль *</span>
            <input className="input" type="text" value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} placeholder="Минимум 8 символов, буквы и цифры" />
            <span className="field__hint">Передайте пароль сотруднику лично. Сменить его можно в личном кабинете.</span>
          </label>
        </Modal>
      )}

      {editing && (
        <Modal
          title={`Пользователь: ${editing.full_name}`}
          subtitle={editing.phone_formatted || editing.phone}
          onClose={() => setEditing(null)}
          footer={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setEditing(null)}>Отмена</button>
              <button type="button" className="btn btn--primary" onClick={saveUser} disabled={busy}>
                {busy ? <Spinner size={17} /> : 'Сохранить'}
              </button>
            </>
          )}
        >
          <label className="field"><span className="field__label">Имя</span><input className="input" value={editForm.full_name} onChange={(event) => setEditForm({ ...editForm, full_name: event.target.value })} /></label>
          <label className="field"><span className="field__label">E-mail</span><input className="input" type="email" value={editForm.email} onChange={(event) => setEditForm({ ...editForm, email: event.target.value })} /></label>
          <label className="field">
            <span className="field__label">Роль</span>
            <select className="input input--select" value={editForm.role} onChange={(event) => setEditForm({ ...editForm, role: event.target.value as Role })} disabled={editing.id === me?.id}>
              {(['customer', 'seller', 'admin'] as Role[]).map((value) => <option key={value} value={value}>{ROLE_LABEL[value]}</option>)}
            </select>
          </label>
          <p className="field__hint">Телефон менять нельзя: он подтверждён по SMS и используется для входа.</p>
        </Modal>
      )}
    </div>
  )
}
