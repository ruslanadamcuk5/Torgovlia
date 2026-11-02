import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { assetUrl } from '../lib/api'
import { Icon } from '../components/icons'

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export default function AppPage() {
  const { site } = useSite()
  const { toast } = useToast()
  const [prompt, setPrompt] = useState<InstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  useEffect(() => {
    const standalone = window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
    setInstalled(standalone)
    const onPrompt = (event: Event) => {
      event.preventDefault()
      setPrompt(event as InstallPromptEvent)
    }
    const onInstalled = () => {
      setInstalled(true)
      setPrompt(null)
      toast('Приложение установлено')
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [toast])

  if (!site) return null
  const s = site.settings

  const install = async () => {
    if (!prompt) {
      setShowHelp(true)
      return
    }
    await prompt.prompt()
    const choice = await prompt.userChoice
    if (choice.outcome === 'accepted') {
      setInstalled(true)
      setPrompt(null)
    }
  }

  return (
    <div className="app-page">
      <section className="app-hero">
        <div className="container app-hero__grid">
          <div>
            <span className="eyebrow eyebrow--light">Android · iOS · PWA</span>
            <h1>Приложение «{s.brand_name}»</h1>
            <p className="app-hero__lead">
              Каталог, бронирование с самовывозом и история заказов — в телефоне.
              Установка занимает меньше минуты и не требует магазина приложений.
            </p>
            <div className="app-hero__actions">
              {installed ? (
                <span className="app-installed"><Icon name="check" size={19} /> Приложение уже установлено</span>
              ) : (
                <button type="button" className="btn btn--gold btn--lg" onClick={install}>
                  <Icon name="android" size={20} /> Установить приложение
                </button>
              )}
              {s.android_apk_url && (
                <a href={s.android_apk_url} className="btn btn--ghost-light btn--lg" download>
                  <Icon name="download" size={19} /> Скачать APK {s.android_app_version && `v${s.android_app_version}`}
                </a>
              )}
              <Link to="/catalog" className="btn btn--ghost-light btn--lg">Открыть каталог</Link>
            </div>
            <div className="app-hero__meta">
              <span><Icon name="shield" size={16} /> Без рекламы и слежки</span>
              <span><Icon name="smartphone" size={16} /> Работает на Android 7+</span>
              {s.android_app_size && <span><Icon name="download" size={16} /> {s.android_app_size}</span>}
            </div>
          </div>

          <div className="app-hero__visual">
            <div className="phone-mock phone-mock--large">
              <div className="phone-mock__notch" />
              <div className="phone-mock__screen">
                <img src={assetUrl(s.logo_url)} alt="" width={54} height={54} />
                <strong>{s.brand_name}</strong>
                <span>{s.city} · {s.market_name}</span>
                <div className="phone-mock__card">
                  <span>Каталог</span>
                  <strong>Свежая рыба сегодня</strong>
                  <small>{site.products_count} позиций · самовывоз</small>
                </div>
                <div className="phone-mock__btn">Забронировать</div>
                <div className="phone-mock__tabs"><span>Главная</span><span>Каталог</span><span>Брони</span><span>Профиль</span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section__head">
            <div><span className="eyebrow">Возможности</span><h2>Всё то же, что на сайте</h2></div>
          </div>
          <div className="app-features">
            {[
              { icon: 'fish' as const, title: 'Актуальный каталог', text: 'Наличие и цены обновляет продавец. Товары «нет в наличии» отмечены сразу.' },
              { icon: 'cart' as const, title: 'Бронь за минуту', text: 'Выберите вес, дату и время. Подтвердите номер по SMS — и заказ готов.' },
              { icon: 'clock' as const, title: 'История заказов', text: 'Все брони сохраняются в личном кабинете. Повторить заказ — один клик.' },
              { icon: 'qr' as const, title: 'Статьи по QR', text: 'Наведите камеру на QR-код у прилавка — узнайте о рыбе всё.' },
              { icon: 'wallet' as const, title: 'Без предоплаты', text: 'Оплата только при получении в павильоне: наличными или картой.' },
              { icon: 'shield' as const, title: 'Безопасность', text: 'Пароль хранится в виде хеша, номер подтверждается SMS-кодом.' },
            ].map((item) => (
              <div className="app-feature" key={item.title}>
                <span className="app-feature__icon"><Icon name={item.icon} size={24} /></span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--install">
        <div className="container install-grid">
          <div className="panel">
            <h2>Как установить на Android</h2>
            <ol className="install-steps">
              <li><span>1</span><p>Откройте этот сайт в Chrome на телефоне.</p></li>
              <li><span>2</span><p>Нажмите «Установить приложение» на этой странице или выберите «Добавить на главный экран» в меню браузера.</p></li>
              <li><span>3</span><p>Подтвердите установку — иконка появится на рабочем столе.</p></li>
            </ol>
            <button type="button" className="btn btn--primary" onClick={install}>
              <Icon name="download" size={18} /> Установить сейчас
            </button>
            {showHelp && (
              <div className="notice notice--info">
                <Icon name="info" size={18} />
                <span>
                  Браузер не показал окно установки автоматически. Откройте меню Chrome (⋮) и выберите
                  «Добавить на главный экран» / «Установить приложение».
                </span>
              </div>
            )}
          </div>

          <div className="panel panel--qr">
            <h2>Открыть на телефоне</h2>
            <p>Наведите камеру на QR-код — сайт откроется на телефоне, и вы сможете установить приложение.</p>
            <img src={assetUrl('/api/qr/site.png?size=420')} alt="QR-код приложения" />
            <a href="/api/qr/site.png?size=1000&download=1" className="btn btn--outline btn--sm" download>
              <Icon name="download" size={16} /> Скачать QR
            </a>
            {!s.android_apk_url && (
              <p className="muted install-note">
                APK-файл можно запросить в павильоне: {s.phone}. Установка через браузер (PWA) доступна уже сейчас.
              </p>
            )}
          </div>
        </div>
      </section>

      <div className="container">
        <div className="app-legal">
          <Icon name="lock" size={18} />
          <p>
            Приложение использует те же защищённые каналы, что и сайт. Персональные данные обрабатываются
            в соответствии с <Link to="/legal/privacy">политикой конфиденциальности</Link>. Уведомления можно
            отключить в настройках телефона.
          </p>
        </div>
      </div>
    </div>
  )
}
