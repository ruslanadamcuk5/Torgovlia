import { useState } from 'react'
import { platformApi, usePlatformApi } from '../../lib/platformApi'
import { useToast } from '../../store/ToastContext'
import { humanDate } from '../../lib/format'
import type { PlatformUser } from '../../lib/types'

const ROLE_LABEL: Record<string, string> = {
  owner: 'Владелец',
  admin: 'Администратор',
  support: 'Поддержка',
  accountant: 'Бухгалтер',
}

const ROLE_BADGE: Record<string, string> = {
  owner: 'badge--fresh',
  admin: 'badge--gold',
  support: 'badge--muted',
  accountant: 'badge--muted',
}

export default function PlatformTeam() {
  const { toast } = useToast()
  const { data: team, loading, reload } = usePlatformApi<PlatformUser[]>('/team')
  const { data: me } = usePlatformApi<PlatformUser>('/auth/me')
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('support')
  const [busy, setBusy] = useState('')
  const [resetUser, setResetUser] = useState<PlatformUser | null>(null)
  const [newPassword, setNewPassword] = useState('')

  const isOwner = me?.role === 'owner'

  const create = async () => {
    if (phone.trim().length < 6 || password.length < 8) {
      toast('Укажите телефон и пароль не короче 8 символов', 'error')
      return
    }
    setBusy('create')
    try {
      await platformApi('/team', {
        method: 'POST',
        body: { phone: phone.trim(), full_name: name.trim(), email: email.trim() || null, password, role },
      })
      setPhone('')
      setName('')
      setEmail('')
      setPassword('')
      setRole('support')
      toast('Сотрудник добавлен')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось добавить сотрудника', 'error')
    } finally {
      setBusy('')
    }
  }

  const patch = async (user: PlatformUser, changes: Record<string, unknown>, message: string) => {
    setBusy(`user-${user.id}`)
    try {
      await platformApi(`/team/${user.id}`, { method: 'PATCH', body: changes })
      toast(message)
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить сотрудника', 'error')
    } finally {
      setBusy('')
    }
  }

  const savePassword = async () => {
    if (!resetUser || newPassword.length < 8) {
      toast('Пароль должен быть не короче 8 символов', 'error')
      return
    }
    await patch(resetUser, { password: newPassword }, 'Пароль обновлён')
    setResetUser(null)
    setNewPassword('')
  }

  return (
    <div className="platform-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Сотрудники платформы</h2>
            <p className="muted">Отдельные входы для поддержки, бухгалтерии и администраторов. Владелец управляет ролями и доступом.</p>
          </div>
          <span className="badge badge--muted">{team?.length ?? '—'} человек</span>
        </div>

        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead>
              <tr><th>Сотрудник</th><th>Телефон</th><th>Роль</th><th>2FA</th><th>Последний вход</th><th>Доступ</th><th /></tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={7} className="muted">Загрузка…</td></tr>}
              {(team ?? []).map((user) => (
                <tr key={user.id} className={user.is_active ? '' : 'is-muted'}>
                  <td>
                    <strong>{user.full_name || 'Без имени'}</strong>
                    {user.email && <span className="muted team-email">{user.email}</span>}
                  </td>
                  <td>{user.phone}</td>
                  <td>
                    {isOwner && user.id !== me?.id ? (
                      <select
                        className="input input--sm input--select"
                        value={user.role}
                        disabled={busy === `user-${user.id}`}
                        onChange={(event) => void patch(user, { role: event.target.value }, 'Роль изменена')}
                      >
                        {Object.entries(ROLE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    ) : (
                      <span className={`badge ${ROLE_BADGE[user.role] ?? 'badge--muted'}`}>{ROLE_LABEL[user.role] ?? user.role}</span>
                    )}
                  </td>
                  <td>{user.totp_enabled ? <span className="badge badge--fresh">Вкл.</span> : <span className="muted">—</span>}</td>
                  <td>{user.last_login_at ? humanDate(user.last_login_at) : 'Никогда'}</td>
                  <td>
                    <span className={`badge ${user.is_active ? 'badge--fresh' : 'badge--danger'}`}>
                      {user.is_active ? 'Активен' : 'Отключён'}
                    </span>
                  </td>
                  <td>
                    {isOwner && user.id !== me?.id && (
                      <div className="team-actions">
                        <button
                          type="button"
                          className="btn btn--sm btn--ghost"
                          disabled={busy === `user-${user.id}`}
                          onClick={() => void patch(user, { is_active: !user.is_active }, user.is_active ? 'Доступ отключён' : 'Доступ включён')}
                        >
                          {user.is_active ? 'Отключить' : 'Включить'}
                        </button>
                        <button type="button" className="btn btn--sm btn--ghost" onClick={() => { setResetUser(user); setNewPassword('') }}>
                          Пароль
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {resetUser && (
        <section className="panel">
          <div className="panel__head">
            <div>
              <h2>Новый пароль</h2>
              <p className="muted">{resetUser.full_name || resetUser.phone}. После смены старые сессии перестанут действовать после истечения токена.</p>
            </div>
          </div>
          <div className="team-reset">
            <input className="input input--sm" type="password" placeholder="Не короче 8 символов" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            <button type="button" className="btn btn--sm btn--primary" disabled={busy === `user-${resetUser.id}`} onClick={() => void savePassword()}>Сохранить</button>
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => setResetUser(null)}>Отмена</button>
          </div>
        </section>
      )}

      {isOwner && (
        <section className="panel">
          <div className="panel__head">
            <div>
              <h2>Добавить сотрудника</h2>
              <p className="muted">Пароль передайте лично; сотрудник сможет включить 2FA в настройках.</p>
            </div>
          </div>
          <div className="team-create">
            <input className="input input--sm" placeholder="+375 29 000-00-00" value={phone} onChange={(event) => setPhone(event.target.value)} />
            <input className="input input--sm" placeholder="Имя" value={name} onChange={(event) => setName(event.target.value)} />
            <input className="input input--sm" type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
            <select className="input input--sm input--select" value={role} onChange={(event) => setRole(event.target.value)}>
              {Object.entries(ROLE_LABEL).filter(([value]) => value !== 'owner').map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <input className="input input--sm" type="password" placeholder="Пароль" value={password} onChange={(event) => setPassword(event.target.value)} />
            <button type="button" className="btn btn--sm btn--outline" disabled={busy === 'create'} onClick={() => void create()}>Добавить</button>
          </div>
        </section>
      )}
    </div>
  )
}
