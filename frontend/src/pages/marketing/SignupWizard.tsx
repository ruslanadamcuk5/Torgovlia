import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { formatMoney } from '../../lib/format'
import { storefrontUrl } from '../../lib/host'
import { Icon, type IconName } from '../../components/icons'
import MarketingShell from './MarketingShell'
import type { SignupCatalog, SignupResult } from '../../lib/types'

const PRESET_ICONS: Record<string, IconName> = {
  fish: 'fish',
  box: 'box',
  heart: 'heart',
  tag: 'tag',
  cart: 'cart',
  sparkles: 'sparkles',
  smartphone: 'smartphone',
  car: 'car',
  paw: 'paw',
  book: 'book',
  sofa: 'sofa',
  gift: 'gift',
  tools: 'tools',
  grid: 'grid',
  shirt: 'shirt',
  hammer: 'hammer',
  leaf: 'leaf',
}

const TRANSLIT: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z',
  и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r',
  с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh',
  щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .split('')
    .map((char) => TRANSLIT[char] ?? char)
    .join('')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
}

type SlugState = { checking: boolean; available: boolean | null; reason: string }

export default function SignupWizard() {
  const [params] = useSearchParams()
  const { data: catalog, loading: catalogLoading } = useApi<SignupCatalog>('/signup/catalog')

  const [step, setStep] = useState(1)
  const [category, setCategory] = useState(params.get('category') ?? 'other')
  const [planCode, setPlanCode] = useState(params.get('plan') ?? 'start')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)
  const [ownerName, setOwnerName] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [offer, setOffer] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [slugState, setSlugState] = useState<SlugState>({ checking: false, available: null, reason: '' })
  const [result, setResult] = useState<SignupResult | null>(null)

  const plans = catalog?.plans ?? []
  const categories = catalog?.categories ?? []
  const plan = plans.find((item) => item.code === planCode) ?? plans[0]

  useEffect(() => {
    if (!slugTouched && name) setSlug(slugify(name))
  }, [name, slugTouched])

  useEffect(() => {
    if (!params.get('plan') && plans.length && !plans.some((item) => item.code === planCode)) {
      setPlanCode(plans[0].code)
    }
  }, [plans, params, planCode])

  const selectedCategory = useMemo(
    () => categories.find((item) => item.code === category),
    [categories, category],
  )

  const checkSlug = async (value: string) => {
    if (value.length < 2) {
      setSlugState({ checking: false, available: false, reason: 'Минимум 2 символа' })
      return false
    }
    setSlugState({ checking: true, available: null, reason: '' })
    try {
      const data = await api<{ available: boolean; reason: string }>(`/signup/check-slug?slug=${encodeURIComponent(value)}`)
      setSlugState({ checking: false, available: data.available, reason: data.reason })
      return data.available
    } catch {
      setSlugState({ checking: false, available: null, reason: 'Не удалось проверить адрес' })
      return true
    }
  }

  const next = async () => {
    setError(null)
    if (step === 1) {
      if (name.trim().length < 2) return setError('Укажите название магазина')
      if (!/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(slug)) {
        return setError('Адрес: латиница, цифры и дефис, от 3 до 63 символов')
      }
      const ok = await checkSlug(slug)
      if (!ok) return setError('Адрес занят или зарезервирован. Выберите другой.')
      setStep(2)
      return
    }
    if (step === 2) {
      if (phone.replace(/\D/g, '').length < 9) return setError('Укажите телефон в формате +375 XX XXX-XX-XX')
      if (!/[A-Za-zА-Яа-я]/.test(password) || !/\d/.test(password) || password.length < 8) {
        return setError('Пароль: минимум 8 символов, буквы и цифры')
      }
      if (password !== password2) return setError('Пароли не совпадают')
      setStep(3)
    }
  }

  const submit = async () => {
    setError(null)
    if (!offer) return setError('Подтвердите согласие с условиями')
    setBusy(true)
    try {
      const data = await api<SignupResult>('/signup', {
        method: 'POST',
        body: {
          slug,
          name: name.trim(),
          category_preset: category,
          plan_code: planCode,
          owner_phone: phone,
          owner_name: ownerName.trim(),
          owner_password: password,
          offer_accepted: offer,
        },
      })
      setResult(data)
      setStep(4)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать магазин')
    } finally {
      setBusy(false)
    }
  }

  if (step === 4 && result) {
    return (
      <MarketingShell>
        <section className="signup-success">
          <span className="signup-success__icon"><Icon name="check" size={34} /></span>
          <h1>Магазин создан</h1>
          <p>«{result.name}» уже доступен по адресу. Осталось войти и добавить товары.</p>

          <div className="signup-success__card">
            <div>
              <span className="muted">Адрес магазина</span>
              <a href={storefrontUrl(result.slug, result.host)} target="_blank" rel="noreferrer">{result.host}</a>
            </div>
            <div>
              <span className="muted">Вход в админку</span>
              <a href={storefrontUrl(result.slug, result.host, '/login')} target="_blank" rel="noreferrer">Открыть страницу входа</a>
            </div>
            <div>
              <span className="muted">Телефон владельца</span>
              <strong>{result.owner_phone}</strong>
            </div>
            <div>
              <span className="muted">Тариф</span>
              <strong>{result.plan_title} · {formatMoney(result.price_month)} BYN / мес</strong>
            </div>
            {result.invoice && (
              <div>
                <span className="muted">Счёт на оплату</span>
                <strong>{result.invoice.number} · {formatMoney(result.invoice.amount)} {result.invoice.currency}</strong>
              </div>
            )}
          </div>

          {result.invoice ? (
            <div className="signup-success__note">
              <Icon name="info" size={18} />
              <p>
                Магазин откроется для покупателей после подтверждения оплаты. Счёт уже в кабинете:
                оплатите банковским переводом, картой или через ЕРИП — платформа подтвердит платёж.
              </p>
            </div>
          ) : (
            <div className="signup-success__note">
              <Icon name="info" size={18} />
              <p>Тариф бесплатный на старте. Можно сразу добавлять товары и отправлять ссылку покупателям.</p>
            </div>
          )}

          <div className="signup-success__actions">
            <a className="btn btn--primary btn--lg" href={storefrontUrl(result.slug, result.host, '/login')}>Войти в админку</a>
            <a className="btn btn--ghost btn--lg" href={storefrontUrl(result.slug, result.host)}>Открыть магазин</a>
          </div>
          <p className="muted">Сохраните адрес и пароль. Письмо с доступом придёт на указанный телефон после подключения SMS.</p>
        </section>
      </MarketingShell>
    )
  }

  return (
    <MarketingShell>
      <section className="signup">
        <div className="signup__intro">
          <Link to="/start" className="mkt-link"><Icon name="arrow-left" size={14} /> На главную</Link>
          <h1>Создайте магазин</h1>
          <p>Три коротких шага. Поддомен и админка появятся сразу после регистрации.</p>
          <ol className="signup__steps">
            {['Категория и адрес', 'Владелец', 'Тариф и оплата'].map((label, index) => (
              <li key={label} className={step === index + 1 ? 'is-current' : step > index + 1 ? 'is-done' : ''}>
                <span>{step > index + 1 ? <Icon name="check" size={14} /> : index + 1}</span>
                <strong>{label}</strong>
              </li>
            ))}
          </ol>
        </div>

        <div className="signup__panel">
          {step === 1 && (
            <>
              <h2>Что вы продаёте?</h2>
              <p className="muted">Шаблон настроит разделы и подсказки под категорию.</p>
              <div className="signup-categories">
                {categories.map((item) => (
                  <button
                    key={item.code}
                    type="button"
                    className={`signup-category ${category === item.code ? 'is-active' : ''}`}
                    onClick={() => setCategory(item.code)}
                  >
                    <Icon name={PRESET_ICONS[item.icon] ?? 'tag'} size={20} />
                    <strong>{item.title}</strong>
                    <span>{item.description}</span>
                  </button>
                ))}
                {catalogLoading && <div className="muted">Загружаем категории…</div>}
              </div>

              <label className="field">
                <span className="field__label">Название магазина</span>
                <input className="input" value={name} onChange={(event) => setName(event.target.value)} placeholder="Мясная лавка у рынка" maxLength={160} />
              </label>

              <label className="field">
                <span className="field__label">Адрес на платформе</span>
                <div className="signup-slug">
                  <input
                    className="input"
                    value={slug}
                    onChange={(event) => { setSlugTouched(true); setSlug(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '')) }}
                    onBlur={() => void checkSlug(slug)}
                    placeholder="myasnaya-lavka"
                  />
                  <span>.torgovlia.by</span>
                </div>
                {slugState.checking && <span className="field__hint">Проверяем адрес…</span>}
                {!slugState.checking && slugState.available === true && <span className="field__hint field__hint--ok">Адрес свободен</span>}
                {!slugState.checking && slugState.available === false && <span className="field__hint field__hint--error">{slugState.reason}</span>}
              </label>

              {selectedCategory && (
                <div className="signup-hint">
                  <Icon name="info" size={16} />
                  <span>Шаблон «{selectedCategory.title}» уже содержит категории: {selectedCategory.examples.join(', ')}.</span>
                </div>
              )}

              {error && <div className="form-error">{error}</div>}
              <button type="button" className="btn btn--primary btn--lg btn--block" onClick={() => void next()}>Дальше</button>
            </>
          )}

          {step === 2 && (
            <>
              <h2>Кто будет владельцем?</h2>
              <p className="muted">Этот телефон и пароль — вход в админку магазина.</p>
              <label className="field">
                <span className="field__label">Имя</span>
                <input className="input" value={ownerName} onChange={(event) => setOwnerName(event.target.value)} placeholder="Иван" maxLength={120} />
              </label>
              <label className="field">
                <span className="field__label">Телефон</span>
                <input className="input" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+375 29 123-45-67" autoComplete="tel" />
              </label>
              <label className="field">
                <span className="field__label">Пароль</span>
                <input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Минимум 8 символов" autoComplete="new-password" />
                <span className="field__hint">Буквы и цифры. Не используйте пароль от других сайтов.</span>
              </label>
              <label className="field">
                <span className="field__label">Повторите пароль</span>
                <input className="input" type="password" value={password2} onChange={(event) => setPassword2(event.target.value)} autoComplete="new-password" />
              </label>
              {error && <div className="form-error">{error}</div>}
              <div className="signup__buttons">
                <button type="button" className="btn btn--ghost" onClick={() => { setError(null); setStep(1) }}>Назад</button>
                <button type="button" className="btn btn--primary btn--lg" onClick={() => void next()}>Дальше</button>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h2>Выберите тариф</h2>
              <p className="muted">Первый счёт — за месяц. Повышение и платные сервисы подключаются после оплаты.</p>
              <div className="signup-plans">
                {plans.map((item) => (
                  <button
                    key={item.code}
                    type="button"
                    className={`signup-plan ${planCode === item.code ? 'is-active' : ''}`}
                    onClick={() => setPlanCode(item.code)}
                  >
                    <div>
                      <strong>{item.title}</strong>
                      <span>{formatMoney(item.price_month)} BYN / мес</span>
                    </div>
                    <span className="muted">{item.description}</span>
                  </button>
                ))}
              </div>

              <div className="signup-summary">
                <div><span>Магазин</span><strong>{name || '—'}</strong></div>
                <div><span>Адрес</span><strong>{slug}.torgovlia.by</strong></div>
                <div><span>Категория</span><strong>{selectedCategory?.title ?? category}</strong></div>
                <div><span>Тариф</span><strong>{plan?.title ?? planCode} · {formatMoney(plan?.price_month ?? 0)} BYN</strong></div>
              </div>

              <label className="signup-offer">
                <input type="checkbox" checked={offer} onChange={(event) => setOffer(event.target.checked)} />
                <span>Согласен с условиями платформы и обработкой персональных данных</span>
              </label>

              {error && <div className="form-error">{error}</div>}
              <div className="signup__buttons">
                <button type="button" className="btn btn--ghost" onClick={() => { setError(null); setStep(2) }}>Назад</button>
                <button type="button" className="btn btn--gold btn--lg" disabled={busy} onClick={() => void submit()}>
                  {busy ? 'Создаём магазин…' : 'Создать магазин'}
                </button>
              </div>
            </>
          )}
        </div>
      </section>
    </MarketingShell>
  )
}
