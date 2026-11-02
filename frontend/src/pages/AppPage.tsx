import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { useToast } from '../store/ToastContext'
import { assetUrl } from '../lib/api'
import { detectPlatform, isInAppBrowser } from '../lib/pwa'
import { Icon } from '../components/icons'

export default function AppPage() {
  const { site } = useSite()
  const { toast } = useToast()
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(
    () => window.__deferredInstallPrompt || null,
  )
  const [installed, setInstalled] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const helpRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const standalone = window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
    setInstalled(standalone)
    const onPrompt = (event: Event) => {
      event.preventDefault()
      setPrompt(event as BeforeInstallPromptEvent)
    }
    const onAvailable = () => setPrompt(window.__deferredInstallPrompt || null)
    const onInstalled = () => {
      setInstalled(true)
      setPrompt(null)
      window.__deferredInstallPrompt = undefined
      toast('Приложение установлено')
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('pwa-install-available', onAvailable)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('pwa-install-available', onAvailable)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [toast])

  if (!site) return null
  const s = site.settings
  const platform = detectPlatform()
  const inAppBrowser = isInAppBrowser()
  const installSteps = platform === 'ios'
    ? [
        'Откройте сайт в Safari (не в приложении Telegram, Instagram или VK).',
        'Нажмите кнопку «Поделиться» внизу экрана.',
        'Выберите «На экран „Домой“» и подтвердите — иконка появится на рабочем столе.',
      ]
    : platform === 'android'
      ? [
          'Откройте сайт в Chrome (не в приложении Telegram, Instagram или VK).',
          'Нажмите «Установить приложение» или откройте меню Chrome (⋮) → «Установить приложение».',
          'Подтвердите установку — иконка появится на рабочем столе.',
        ]
      : [
          'Откройте сайт в Chrome или Edge на компьютере.',
          'Нажмите иконку установки в адресной строке или откройте меню (⋮) → «Установить приложение».',
          'На телефоне удобнее установить через Chrome: откройте сайт и выберите «Установить приложение».',
        ]

  const install = async () => {
    const current = prompt || window.__deferredInstallPrompt
    if (!current) {
      setShowHelp(true)
      window.setTimeout(() => helpRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
      return
    }
    await current.prompt()
    const choice = await current.userChoice
    if (choice.outcome === 'accepted') {
      setInstalled(true)
      setPrompt(null)
      window.__deferredInstallPrompt = undefined
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
                <a href={assetUrl(s.android_apk_url)} className="btn btn--ghost-light btn--lg" download>
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
            <h2>Как установить приложение</h2>
            <ol className="install-steps">
              {installSteps.map((step, index) => (
                <li key={step}><span>{index + 1}</span><p>{step}</p></li>
              ))}
            </ol>
            <button type="button" className="btn btn--primary" onClick={() => void install()}>
              <Icon name="download" size={18} /> Установить сейчас
            </button>
            {s.android_apk_url && (
              <>
                <a href={assetUrl(s.android_apk_url)} className="btn btn--outline" download>
                  <Icon name="android" size={18} /> Скачать APK {s.android_app_version && `v${s.android_app_version}`}
                </a>
                <p className="muted install-note">
                  APK — установщик для Android. После скачивания откройте файл и разрешите установку
                  из этого источника. Обновления приложение предложит само.
                </p>
              </>
            )}
            {showHelp && (
              <div className="notice notice--info" ref={helpRef}>
                <Icon name="info" size={18} />
                <span>
                  {inAppBrowser
                    ? 'Похоже, сайт открыт во встроенном браузере Telegram/Instagram/VK. Нажмите ⋯ в углу и выберите «Открыть в Chrome» или «Открыть в Safari», затем повторите установку.'
                    : platform === 'ios'
                      ? 'Если окно установки не появилось: в Safari нажмите «Поделиться» → «На экран „Домой“».'
                      : platform === 'android'
                        ? 'Если окно установки не появилось: откройте меню Chrome (⋮) → «Установить приложение» или «Добавить на главный экран».'
                        : 'Если окно установки не появилось: нажмите иконку установки в адресной строке Chrome/Edge или откройте меню (⋮) → «Установить приложение».'}
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
