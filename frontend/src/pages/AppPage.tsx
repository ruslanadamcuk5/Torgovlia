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

  const iosSteps = [
    'Откройте главную страницу сайта на iPhone или iPad в Safari.',
    'Нажмите кнопку «Поделиться» внизу экрана.',
    'Выберите «На экран „Домой“» и подтвердите установку.',
    'Иконка магазина появится на рабочем столе и откроет каталог в полноэкранном режиме.',
  ]

  const scrollToIos = () => {
    document.getElementById('ios-install')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const install = async () => {
    if (platform === 'ios') {
      scrollToIos()
      return
    }
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
              Каталог, заказ с самовывозом и история покупок — в телефоне.
              Установка занимает меньше минуты и не требует магазина приложений.
            </p>
            <div className="app-hero__actions">
              {installed ? (
                <span className="app-installed"><Icon name="check" size={19} /> Приложение уже установлено</span>
              ) : (
                <button type="button" className="btn btn--gold btn--lg" onClick={install}>
                  <Icon name={platform === 'ios' ? 'apple' : platform === 'android' ? 'android' : 'download'} size={20} />
                  {platform === 'ios' ? 'Установить на iPhone' : 'Установить приложение'}
                </button>
              )}
              {s.android_apk_url && (
                <a href={assetUrl(s.android_apk_url)} className="btn btn--ghost-light btn--lg" download>
                  <Icon name="download" size={19} /> Скачать APK {s.android_app_version && `v${s.android_app_version}`}
                </a>
              )}
              {platform !== 'ios' && (
                <button type="button" className="btn btn--ghost-light btn--lg" onClick={scrollToIos}>
                  <Icon name="apple" size={19} /> iPhone и iPad
                </button>
              )}
              <Link to="/catalog" className="btn btn--ghost-light btn--lg">Открыть каталог</Link>
            </div>
            <div className="app-hero__meta">
              <span><Icon name="shield" size={16} /> Без рекламы и слежки</span>
              <span><Icon name="smartphone" size={16} /> Android 7+ и iPhone/iPad</span>
              {s.android_app_size && <span><Icon name="download" size={16} /> APK {s.android_app_size}</span>}
            </div>
          </div>

          <div className="app-hero__visual">
            <div className="phone-mock phone-mock--large">
              <div className="phone-mock__notch" />
              <div className="phone-mock__screen">
                <img src={assetUrl(s.logo_url)} alt="" width={54} height={54} />
                <strong>{s.brand_name}</strong>
                <span>{[s.city, s.market_name].filter(Boolean).join(' · ') || 'Онлайн-витрина'}</span>
                <div className="phone-mock__card">
                  <span>Каталог</span>
                  <strong>Новые поступления</strong>
                  <small>{site.products_count} позиций · самовывоз</small>
                </div>
                <div className="phone-mock__btn">Сделать заказ</div>
                <div className="phone-mock__tabs"><span>Главная</span><span>Каталог</span><span>Заказы</span><span>Профиль</span></div>
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
              { icon: 'box' as const, title: 'Актуальный каталог', text: 'Наличие и цены обновляет продавец. Товары «нет в наличии» отмечены сразу.' },
              { icon: 'cart' as const, title: 'Заказ за минуту', text: 'Выберите количество, дату и время. Подтвердите номер по SMS — и заказ готов.' },
              { icon: 'clock' as const, title: 'История заказов', text: 'Все заказы сохраняются в личном кабинете. Повторить заказ — один клик.' },
              { icon: 'qr' as const, title: 'Статьи по QR', text: 'Наведите камеру на QR-код у прилавка — откроется статья о товаре.' },
              { icon: 'wallet' as const, title: 'Без предоплаты', text: 'Оплата при получении в магазине: наличными или картой.' },
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
        <div className="container">
          <div className="app-platforms">
            <div className="app-platform">
              <span className="app-platform__icon"><Icon name="android" size={23} /></span>
              <div className="app-platform__text">
                <strong>Android</strong>
                <span>APK {s.android_app_version && `v${s.android_app_version}`}{s.android_app_size ? ` · ${s.android_app_size}` : ''}</span>
              </div>
              {s.android_apk_url ? (
                <a href={assetUrl(s.android_apk_url)} className="btn btn--primary btn--sm" download>
                  <Icon name="download" size={16} /> Скачать
                </a>
              ) : (
                <span className="muted">Скоро</span>
              )}
            </div>
            <div className="app-platform">
              <span className="app-platform__icon"><Icon name="apple" size={23} /></span>
              <div className="app-platform__text">
                <strong>iPhone и iPad</strong>
                <span>Установка через Safari, без App Store</span>
              </div>
              <button type="button" className="btn btn--outline btn--sm" onClick={scrollToIos}>
                Инструкция
              </button>
            </div>
          </div>

          <div className="install-grid">
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
                APK-файл можно запросить в магазине{s.phone ? `: ${s.phone}` : ''}. Установка через браузер (PWA) доступна уже сейчас.
              </p>
            )}
          </div>

          <div className="panel panel--ios" id="ios-install">
            <div className="panel__head">
              <div>
                <h2>iPhone и iPad</h2>
                <p className="muted">Веб-приложение устанавливается из Safari — без App Store и без оплаты.</p>
              </div>
              <span className="app-platform__icon"><Icon name="apple" size={23} /></span>
            </div>
            <ol className="install-steps">
              {iosSteps.map((step, index) => (
                <li key={step}><span>{index + 1}</span><p>{step}</p></li>
              ))}
            </ol>
            <div className="notice notice--info">
              <Icon name="info" size={18} />
              <span>
                На iPhone установка доступна только в Safari. Если сайт открыт в Telegram, Instagram или VK,
                нажмите ⋯ и выберите «Открыть в Safari».
              </span>
            </div>
            <Link to="/" className="btn btn--primary btn--sm panel__action">Открыть главную страницу</Link>
          </div>
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
