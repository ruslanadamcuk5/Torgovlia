import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../../lib/useApi'
import { formatMoney } from '../../lib/format'
import { track } from '../../lib/track'
import { Icon, type IconName } from '../../components/icons'
import MarketingShell from './MarketingShell'
import type { CategoryPreset, PlanInfo, PublicService, SignupCatalog } from '../../lib/types'

interface ServiceDemoInfo {
  enabled: boolean
  slug?: string
  name?: string
  storefront_url?: string
  admin_url?: string
  booking_url?: string
}

interface DemoInfo {
  enabled: boolean
  slug: string
  name: string
  storefront_url: string
  admin_url: string
  phone: string
  password: string
  reset_every_hours: number
  service_demo?: ServiceDemoInfo
}

interface DesignTemplateInfo {
  code: string
  title: string
  description: string
  mood: string
  tokens: Record<string, string>
}

const PRESET_ICONS: Record<string, IconName> = {
  fish: 'fish',
  box: 'box',
  heart: 'heart',
  tag: 'tag',
  cart: 'cart',
  sparkles: 'sparkles',
  smartphone: 'smartphone',
}

const FEATURES = [
  {
    icon: 'cart' as IconName,
    title: 'Витрина, которая продаёт',
    text: 'Каталог товаров или услуг с фото, ценами и остатками, баннеры, акции, отзывы и статьи. 18 дизайн-шаблонов под категорию.',
    bullets: ['Категории и карточки', 'Поиск и фильтры', 'Установка на телефон'],
  },
  {
    icon: 'list' as IconName,
    title: 'Заказы и записи',
    text: 'Самовывоз по слотам, доставка по зонам или онлайн-запись к специалисту. Статусы, история, уведомления.',
    bullets: ['Интервалы и лимиты', 'Доставка и зоны', 'Свободные окна и запись'],
  },
  {
    icon: 'box' as IconName,
    title: 'Склад и закупки',
    text: 'Остатки, приход, списание, инвентаризация. Поставщики, заявки и приёмка пополняют склад автоматически.',
    bullets: ['История движения', 'Поставщики и закупки', 'Штрихкоды и этикетки'],
  },
  {
    icon: 'users' as IconName,
    title: 'Клиенты и CRM',
    text: 'Общая база из аккаунтов и гостевых заказов. Сегменты, заметки, метки, бонусные уровни и история покупок.',
    bullets: ['Сегменты по покупкам', 'Бонусы и уровни', 'Карточка клиента'],
  },
  {
    icon: 'send' as IconName,
    title: 'Маркетинг, который считается',
    text: 'Промокоды, брошенные корзины, допродажи, рассылки Email и SMS, импорт прайсов из Excel и почты.',
    bullets: ['Кампании и сегменты', 'Напоминания о корзине', 'Импорт прайсов'],
  },
  {
    icon: 'shield' as IconName,
    title: 'Платформа и поддержка',
    text: 'Домен, SSL, резервные копии, изоляция данных магазинов, мониторинг, счета и поддержка в одном окне.',
    bullets: ['Свой домен', 'Мониторинг 24/7', 'Счёт и активация'],
  },
]

const STEPS = [
  { title: 'Откройте демо', text: 'Посмотрите витрину магазина и салона услуг — вместе с админкой и записью.' },
  { title: 'Выберите категорию', text: 'Рыба, цветы, одежда, салон, клиника или свой вариант: шаблон уже настроен.' },
  { title: 'Создайте сайт', text: 'Название, адрес на платформе и тариф. Счёт формируется сразу.' },
  { title: 'Начните продавать', text: 'Добавьте товары или услуги, включите доставку и запись, отправьте ссылку клиентам.' },
]

const TRUST = [
  { value: '89', label: 'сервисов в реестре' },
  { value: '18', label: 'дизайн-шаблонов' },
  { value: '5 мин', label: 'до первого сайта' },
  { value: '24/7', label: 'мониторинг сайтов' },
]

const PRESET_FALLBACK: CategoryPreset[] = [
  { code: 'fish', title: 'Рыба и морепродукты', description: 'Свежая рыба, копчёности, икра', examples: ['охлаждённая рыба', 'икра'], icon: 'fish' },
  { code: 'meat', title: 'Мясо и птица', description: 'Вырезка, фарш, курица, индейка', examples: ['стейки', 'птица'], icon: 'box' },
  { code: 'flowers', title: 'Цветы и растения', description: 'Букеты, растения, подарки', examples: ['букеты', 'растения'], icon: 'heart' },
  { code: 'grocery', title: 'Продукты', description: 'Бакалея, молочное, напитки', examples: ['бакалея', 'напитки'], icon: 'cart' },
]

// Запасная галерея: если /api/templates ещё не ответил, показываем те же
// десять характеров, что и на витрине, без пустого места в секции.
const FALLBACK_DESIGNS: DesignTemplateInfo[] = [
  { code: 'market', title: 'Рынок', description: 'Универсальный', mood: 'спокойный, традиционный', tokens: { ink: '#08272e', teal: '#0b6b6b', gold: '#bd8c3e', cream: '#f7f5ef', 'teal-soft': '#e4f2ee' } },
  { code: 'forest', title: 'Лес', description: 'Фермерские продукты', mood: 'природный, уверенный', tokens: { ink: '#0f2f24', teal: '#1c5a43', gold: '#b98a3c', cream: '#f7f6ef', 'teal-soft': '#e3efe8' } },
  { code: 'bloom', title: 'Цветение', description: 'Цветы и подарки', mood: 'нежный, праздничный', tokens: { ink: '#3d2438', teal: '#b04a7a', gold: '#bd8c3e', cream: '#fdf7f5', 'teal-soft': '#fbe9f0' } },
  { code: 'berry', title: 'Ягода', description: 'Деликатесы и кондитерка', mood: 'выразительный, премиальный', tokens: { ink: '#2c1226', teal: '#8c2f5f', gold: '#bd8c3e', cream: '#faf5f2', 'teal-soft': '#f6e6ee' } },
  { code: 'ocean', title: 'Океан', description: 'Рыба, техника, аптека', mood: 'чистый, деловой', tokens: { ink: '#0b2545', teal: '#1667a8', gold: '#bd8c3e', cream: '#f5f8fb', 'teal-soft': '#e6f0f8' } },
  { code: 'sun', title: 'Солнце', description: 'Овощи и выпечка', mood: 'тёплый, витринный', tokens: { ink: '#3b2416', teal: '#c25a24', gold: '#b9822f', cream: '#fbf6ee', 'teal-soft': '#fdeee2' } },
  { code: 'fresh', title: 'Свежесть', description: 'Зелень и здоровое питание', mood: 'лёгкий, энергичный', tokens: { ink: '#173626', teal: '#2f8f4e', gold: '#bd8c3e', cream: '#f8fbf7', 'teal-soft': '#e8f6ec' } },
  { code: 'mono', title: 'Графит', description: 'Электроника и услуги', mood: 'минималистичный, строгий', tokens: { ink: '#1c1c1c', teal: '#3a3a3a', gold: '#a67c2e', cream: '#fafafa', 'teal-soft': '#efefef' } },
  { code: 'lux', title: 'Люкс', description: 'Ювелирное и премиум', mood: 'дорогой, сдержанный', tokens: { ink: '#14110c', teal: '#8a6a2f', gold: '#a67c2e', cream: '#fcfaf4', 'teal-soft': '#f5efe2' } },
  { code: 'latte', title: 'Латте', description: 'Кофейни и hand-made', mood: 'уютный, крафтовый', tokens: { ink: '#2f241d', teal: '#8a5a3b', gold: '#b9822f', cream: '#faf6f1', 'teal-soft': '#f1e8e0' } },
]

const FALLBACK_PLANS: PlanInfo[] = [
  { code: 'start', title: 'Старт', description: 'Магазин, каталог, заказы и базовые шаблоны.', price_month: 19, price_year: 190, quotas: { products: 500, storage_gb: 1, sms_month: 100, users: 1 } },
  { code: 'business', title: 'Бизнес', description: 'Доставка, оплата, промокоды, отзывы и сотрудники.', price_month: 49, price_year: 490, quotas: { products: 5000, storage_gb: 5, sms_month: 500, users: 3 } },
  { code: 'pro', title: 'Про', description: 'CRM, склад, рассылки, импорт прайсов и поддержка.', price_month: 99, price_year: 990, quotas: { products: 0, storage_gb: 20, sms_month: 2000, users: 10 } },
]

const GROUP_ORDER = ['Ядро', 'Продажи', 'Маркетинг', 'Операции', 'Add-on']

const GROUP_ICON: Record<string, IconName> = {
  Ядро: 'grid',
  Продажи: 'cart',
  Маркетинг: 'send',
  Операции: 'box',
  'Add-on': 'sparkles',
}

const STATUS_LABEL: Record<string, string> = {
  ready: 'Готово',
  partial: 'Частично',
  planned: 'В разработке',
}

export default function MarketingHome() {
  const { data } = useApi<SignupCatalog>('/signup/catalog', false)
  const { data: demo } = useApi<DemoInfo>('/platform/demo', false)
  const { data: designs } = useApi<DesignTemplateInfo[]>('/templates', false)
  const [demoView, setDemoView] = useState<'store' | 'admin'>('store')
  const plans = data?.plans ?? []
  const categories = data?.categories?.length ? data.categories : PRESET_FALLBACK
  const services = data?.services ?? []

  useEffect(() => {
    track('visit')
  }, [])

  const grouped = useMemo(() => {
    const map = new Map<string, PublicService[]>()
    for (const service of services) {
      if (!map.has(service.group)) map.set(service.group, [])
      map.get(service.group)!.push(service)
    }
    return GROUP_ORDER.filter((group) => map.has(group)).map((group) => ({
      group,
      items: map.get(group)!,
      ready: map.get(group)!.filter((item) => item.status === 'ready').length,
    }))
  }, [services])

  const counts = useMemo(
    () => ({
      ready: services.filter((item) => item.status === 'ready').length,
      partial: services.filter((item) => item.status === 'partial').length,
      planned: services.filter((item) => item.status === 'planned').length,
    }),
    [services],
  )

  const openDemo = () => track('demo_storefront', { detail: demo?.slug ?? '' })
  const openDemoAdmin = () => track('demo_admin', { detail: demo?.slug ?? '' })

  // Пока ответ /api/platform/demo не пришёл (или он не удался), демо считаем
  // доступным: это флагманский сценарий платформы. Явное `enabled: false`
  // скрывает кнопку. Так на первом кадре не бывает двух одинаковых CTA.
  const hasDemo = demo === null || demo.enabled
  const demoStorefront = demo?.storefront_url ?? '/shop/odezhda/'
  const demoAdmin = demo?.admin_url ?? '/shop/odezhda/admin'
  const serviceDemo = demo?.service_demo?.enabled ? demo.service_demo : null
  const openServiceDemo = () => track('demo_service', { detail: serviceDemo?.slug ?? '' })

  return (
    <MarketingShell>
      <section className="mkt-hero mkt-hero--rich">
        <div className="mkt-aurora" aria-hidden="true">
          <span className="mkt-aurora__blob mkt-aurora__blob--a" />
          <span className="mkt-aurora__blob mkt-aurora__blob--b" />
          <span className="mkt-aurora__blob mkt-aurora__blob--c" />
          <span className="mkt-aurora__grid" />
        </div>
        <div className="mkt-hero__copy">
          <span className="mkt-pill">
            <span className="mkt-pill__dot" />
            <span className="mkt-pill__text">
              Платформа для торговли и услуг
              <span className="mkt-pill__extra"> · {services.length || 89} сервисов</span>
            </span>
          </span>
          <h1>Магазин или салон — <em>с первого дня</em></h1>
          <p>
            Витрина, заказы, склад, клиенты, рассылки и оплата — в одном окне.
            Для услуг: каталог, специалисты и онлайн-запись. Включите сайт за
            вечер и растите без программиста и отдельных сервисов.
          </p>
          <div className="mkt-hero__actions">
            {hasDemo && (
              <a
                href={demoStorefront}
                target="_blank"
                rel="noreferrer"
                className="btn btn--gold btn--lg"
                onClick={openDemo}
              >
                <Icon name="eye" size={18} /> Открыть демо-магазин
              </a>
            )}
            <Link
              to="/new"
              className={`btn ${hasDemo ? 'btn--ghost-light' : 'btn--gold'} btn--lg`}
            >
              Создать сайт
            </Link>
          </div>
          <div className="mkt-hero__links">
            {hasDemo && (
              <a href={demoAdmin} target="_blank" rel="noreferrer" onClick={openDemoAdmin}>
                <Icon name="dashboard" size={15} /> Войти в админку демо
                <Icon name="external" size={13} />
              </a>
            )}
            {serviceDemo && (
              <a href={serviceDemo.storefront_url} target="_blank" rel="noreferrer" onClick={openServiceDemo}>
                <Icon name="calendar" size={15} /> Демо-салон: запись онлайн
                <Icon name="external" size={13} />
              </a>
            )}
            <a href="#tariffs">Смотреть тарифы <Icon name="arrow-right" size={14} /></a>
          </div>
          <div className="mkt-hero__stats">
            <div><strong>{counts.ready || 42}</strong><span>сервисов уже работают</span></div>
            <div><strong>{TRUST[1].value}</strong><span>дизайн-шаблонов</span></div>
            <div><strong>5 мин</strong><span>до первого сайта</span></div>
          </div>
        </div>

        <div className="mkt-preview-wrap">
          <div className="mkt-preview mkt-preview--rich" aria-hidden="true">
            <div className="mkt-preview__top">
              <span className="mkt-preview__dots"><i /><i /><i /></span>
              <span>torg.alwaysdata.net/shop/{demo?.slug ?? 'odezhda'}</span>
              <span className="mkt-preview__badge"><i /> демо</span>
            </div>
            <div className="mkt-preview__body">
              <div className="mkt-preview__brand">
                <span className="mkt-preview__logo">М</span>
                <div><strong>Модная лавка</strong><small>одежда, которая работает каждый день</small></div>
                <em className="mkt-preview__cart"><Icon name="cart" size={14} /> 3</em>
              </div>
              <div className="mkt-preview__hero">
                <div>
                  <span>Новая коллекция</span>
                  <strong>Базовый гардероб<br />на каждый день</strong>
                  <small>доставка по городу · самовывоз со скидкой</small>
                </div>
                <span className="mkt-preview__tag">−20%</span>
              </div>
              <div className="mkt-preview__grid">
                {['Худи оверсайз', 'Куртка-бомбер', 'Тренч', 'Свитшот'].map((title, index) => (
                  <div key={title} className="mkt-preview__card">
                    <span className={`mkt-preview__img mkt-preview__img--cloth-${index + 1}`} />
                    <strong>{title}</strong>
                    <small>{(79 + index * 45).toFixed(2)} BYN</small>
                  </div>
                ))}
              </div>
              <div className="mkt-preview__order">
                <span><Icon name="check" size={14} /> Заказ №1042 принят</span>
                <strong>158.00 BYN</strong>
              </div>
            </div>
            <span className="mkt-preview__float mkt-preview__float--a">
              <Icon name="chart" size={15} /> +18% выручки
            </span>
            <span className="mkt-preview__float mkt-preview__float--b">
              <Icon name="bell" size={15} /> Новый заказ
            </span>
          </div>
          <span className="mkt-preview__halo" aria-hidden="true" />
        </div>
      </section>

      <section className="mkt-marquee" aria-hidden="true">
        <div className="mkt-marquee__track">
          {[0, 1].map((copy) => (
            <div className="mkt-marquee__group" key={copy}>
              {(categories.length ? categories : PRESET_FALLBACK).map((item) => (
                <span key={`${copy}-${item.code}`}>{item.title}</span>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="mkt-demo" id="demo">
        <div className="mkt-demo__intro">
          <span className="mkt-eyebrow">Живое демо</span>
          <h2>Посмотрите изнутри — без регистрации</h2>
          <p>
            Один и тот же магазин с двух сторон: глазами покупателя и глазами
            владельца. Все сервисы включены, данные настоящие, менять можно всё.
          </p>
          <div className="mkt-demo__meta">
            <span><Icon name="refresh" size={14} /> демо обновляется каждые {demo?.reset_every_hours ?? 24} ч</span>
            <span><Icon name="lock" size={14} /> только демо-данные</span>
          </div>
          <div className="mkt-demo__actions">
            {hasDemo && (
              <a href={demoStorefront} target="_blank" rel="noreferrer" className="btn btn--gold" onClick={openDemo}>
                Открыть витрину <Icon name="external" size={15} />
              </a>
            )}
            {hasDemo && (
              <a href={demoAdmin} target="_blank" rel="noreferrer" className="btn btn--ghost-light" onClick={openDemoAdmin}>
                Войти в админку <Icon name="external" size={15} />
              </a>
            )}
          </div>
          <dl className="mkt-creds">
            <div><dt>Телефон</dt><dd>{demo?.phone ?? '+375 29 111-22-88'}</dd></div>
            <div><dt>Пароль</dt><dd>{demo?.password ?? 'ChangeMe123!'}</dd></div>
          </dl>
          <small className="mkt-demo__hint">Перед продакшеном смените демо-пароль.</small>
        </div>

        <div className="mkt-demo__showcase">
          <div className="mkt-demo__tabs">
            <button
              type="button"
              aria-pressed={demoView === 'store'}
              className={demoView === 'store' ? 'is-active' : ''}
              onClick={() => setDemoView('store')}
            >
              Витрина покупателя
            </button>
            <button
              type="button"
              aria-pressed={demoView === 'admin'}
              className={demoView === 'admin' ? 'is-active' : ''}
              onClick={() => setDemoView('admin')}
            >
              Админка владельца
            </button>
            <span className="mkt-demo__live"><i /> live</span>
          </div>

          {demoView === 'store' ? (
            <div className="mkt-mock mkt-mock--store">
              <div className="mkt-mock__bar">
                <span className="mkt-mock__brand">М</span>
                <strong>Модная лавка</strong>
                <i>Корзина · 3</i>
              </div>
              <div className="mkt-mock__hero">
                <div><small>Новая коллекция</small><strong>Базовый гардероб<br />на каждый день</strong></div>
                <span>−20%</span>
              </div>
              <div className="mkt-mock__tiles">
                <div><i className="t1" /><strong>Худи оверсайз</strong><small>79.00 BYN</small></div>
                <div><i className="t2" /><strong>Куртка-бомбер</strong><small>189.00 BYN</small></div>
                <div><i className="t3" /><strong>Тренч</strong><small>249.00 BYN</small></div>
                <div><i className="t4" /><strong>Свитшот</strong><small>99.00 BYN</small></div>
              </div>
              <div className="mkt-mock__foot"><span><Icon name="check" size={14} /> Заказ №1042 принят</span><strong>158.00 BYN</strong></div>
            </div>
          ) : (
            <div className="mkt-mock mkt-mock--admin">
              <div className="mkt-mock__side">
                <span className="is-active" /><span /><span /><span />
              </div>
              <div className="mkt-mock__main">
                <div className="mkt-mock__head"><strong>Сегодня</strong><i>Онлайн</i></div>
                <div className="mkt-mock__kpis">
                  <div><span>Выручка</span><strong>4 820 BYN</strong><em>+18%</em></div>
                  <div><span>Заказы</span><strong>32</strong><em>+6</em></div>
                  <div><span>Средний чек</span><strong>150 BYN</strong><em>+4%</em></div>
                </div>
                <div className="mkt-mock__chart">
                  {[42, 66, 38, 80, 54, 92, 70].map((height, index) => (
                    <span key={index} style={{ height: `${height}%` }} />
                  ))}
                </div>
                <div className="mkt-mock__rows">
                  <div><i /><span>Заказ №1042</span><strong>158 BYN</strong></div>
                  <div><i /><span>Заказ №1041</span><strong>249 BYN</strong></div>
                  <div><i /><span>Заказ №1040</span><strong>79 BYN</strong></div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <section id="features" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Всё для продаж и записи</span>
          <h2>Не просто сайт, а рабочий бизнес</h2>
          <p>Бесплатные функции уже в тарифе. Платные подключаются в один клик, когда понадобятся.</p>
        </header>
        <div className="mkt-features mkt-features--rich">
          {FEATURES.map((item) => (
            <article key={item.title} className="mkt-feature mkt-feature--rich">
              <span className="mkt-feature__icon"><Icon name={item.icon} size={22} /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
              <ul>
                {item.bullets.map((bullet) => (
                  <li key={bullet}><Icon name="check" size={13} /> {bullet}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className="mkt-section mkt-section--tint" id="services">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Реестр сервисов</span>
          <h2>{services.length || 77} сервисов — и каждый честно подписан</h2>
          <p>
            Мы показываем не только то, что уже работает, но и то, что ещё в
            разработке. Никаких «звёздочек» и мелкого шрифта.
          </p>
        </header>

        <div className="mkt-readiness">
          <span className="mkt-readiness__pill mkt-readiness__pill--ready"><strong>{counts.ready}</strong> готовы</span>
          <span className="mkt-readiness__pill mkt-readiness__pill--partial"><strong>{counts.partial}</strong> частично</span>
          <span className="mkt-readiness__pill mkt-readiness__pill--planned"><strong>{counts.planned}</strong> в разработке</span>
        </div>

        <div className="mkt-groups">
          {grouped.map((group) => (
            <article className="mkt-group" key={group.group}>
              <header>
                <span className="mkt-group__icon"><Icon name={GROUP_ICON[group.group] ?? 'tag'} size={18} /></span>
                <div><h3>{group.group}</h3><small>{group.items.length} сервисов</small></div>
                <span className="mkt-group__ready">{group.ready} готовы</span>
              </header>
              <ul>
                {group.items.slice(0, 6).map((service) => (
                  <li key={service.code}>
                    <span>{service.title}</span>
                    <em className={`mkt-status mkt-status--${service.status}`}>{STATUS_LABEL[service.status]}</em>
                  </li>
                ))}
              </ul>
              {group.items.length > 6 && (
                <p className="muted">и ещё {group.items.length - 6} сервисов в реестре</p>
              )}
            </article>
          ))}
        </div>
      </section>

      <section id="templates" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Шаблоны</span>
          <h2>Готовый сайт под вашу категорию</h2>
          <p>Меняются тексты, разделы и подсказки — для товаров и услуг. Ваши данные и бренд остаются на месте.</p>
        </header>
        <div className="mkt-templates">
          {categories.map((item) => (
            <article key={item.code} className="mkt-template">
              <span className="mkt-template__icon">
                <Icon name={PRESET_ICONS[item.icon] ?? 'tag'} size={24} />
              </span>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              <div className="mkt-chips">
                {item.examples.slice(0, 3).map((example) => <span key={example}>{example}</span>)}
              </div>
              <Link to={`/new?category=${item.code}`} className="mkt-link">Выбрать шаблон <Icon name="arrow-right" size={14} /></Link>
            </article>
          ))}
        </div>
      </section>

      <section id="designs" className="mkt-section mkt-section--ink">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Внешний вид</span>
          <h2>18 дизайнов с характером</h2>
          <p>
            Не безликий конструктор: у каждого шаблона своя палитра, типографика
            и настроение. Переключение — в один клик, товары и тексты остаются на месте.
          </p>
        </header>

        <div className="mkt-designs">
          {(designs?.length ? designs : FALLBACK_DESIGNS).map((design) => {
            const tokens = design.tokens
            const style = {
              '--d-ink': tokens.ink ?? '#08272e',
              '--d-teal': tokens.teal ?? '#0b6b6b',
              '--d-gold': tokens.gold ?? '#bd8c3e',
              '--d-cream': tokens.cream ?? '#f7f5ef',
              '--d-soft': tokens['teal-soft'] ?? '#e4f2ee',
            } as CSSProperties
            const swatches = [tokens.ink, tokens.teal, tokens.gold, tokens.cream].filter(Boolean) as string[]
            return (
              <article
                key={design.code}
                className="mkt-design"
                style={style}
                title={design.description}
              >
                <div className="mkt-design__screen">
                  <div className="mkt-design__chrome">
                    <i /><i /><i />
                    <span>{design.code}.torgovlia.by</span>
                  </div>
                  <div className="mkt-design__hero">
                    <span className="mkt-design__logo">Т</span>
                    <span className="mkt-design__kicker" />
                    <strong />
                    <em />
                    <div className="mkt-design__chips"><span /><span /><span /></div>
                  </div>
                  <div className="mkt-design__tiles"><span /><span /><span /></div>
                </div>
                <div className="mkt-design__meta">
                  <div>
                    <strong>{design.title}</strong>
                    <span>{design.mood}</span>
                  </div>
                  <div className="mkt-design__swatches" aria-hidden="true">
                    {swatches.map((color, index) => (
                      <i key={index} style={{ background: color }} />
                    ))}
                  </div>
                </div>
              </article>
            )
          })}
        </div>

        <div className="mkt-designs__cta">
          <span>Все дизайны входят в любой тариф — меняйте без доплат.</span>
          <Link to="/new" className="btn btn--gold">
            Подобрать дизайн <Icon name="arrow-right" size={15} />
          </Link>
        </div>
      </section>

      <section id="tariffs" className="mkt-section mkt-section--tint">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Тарифы</span>
          <h2>Платите за магазин, а не за функции</h2>
          <p>Первый месяц — по выбранному тарифу. Повышение и платные сервисы — после оплаты счёта.</p>
        </header>
        <div className="mkt-plans">
          {(plans.length ? plans : FALLBACK_PLANS).map((plan, index) => (
            <article key={plan.code} className={`mkt-plan ${index === 1 ? 'is-featured' : ''}`}>
              {index === 1 && <span className="mkt-plan__label">Популярный</span>}
              <h3>{plan.title}</h3>
              <strong>{formatMoney(plan.price_month)} <small>BYN / мес</small></strong>
              <p>{plan.description}</p>
              <ul>
                <li><Icon name="check" size={14} /> Товаров: {plan.quotas.products ? plan.quotas.products : 'без лимита'}</li>
                <li><Icon name="check" size={14} /> Хранилище: {plan.quotas.storage_gb} ГБ</li>
                <li><Icon name="check" size={14} /> SMS: {plan.quotas.sms_month} / мес</li>
                <li><Icon name="check" size={14} /> Сотрудников: {plan.quotas.users}</li>
              </ul>
              <Link to={`/new?plan=${plan.code}`} className={`btn ${index === 1 ? 'btn--gold' : 'btn--outline'} btn--block`}>
                Выбрать «{plan.title}»
              </Link>
            </article>
          ))}
        </div>
        <p className="mkt-plans__note">
          <Icon name="info" size={14} /> Платные add-on подключаются отдельно: SMS-рассылки, свой домен,
          AI-инструменты, интеграции и несколько точек.
        </p>
      </section>

      <section id="how" className="mkt-section mkt-section--dark">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Как это работает</span>
          <h2>От идеи до первого заказа</h2>
        </header>
        <ol className="mkt-steps">
          {STEPS.map((item, index) => (
            <li key={item.title}>
              <span>{index + 1}</span>
              <div><strong>{item.title}</strong><p>{item.text}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section className="mkt-section mkt-section--trust">
        <div className="mkt-trustgrid">
          {TRUST.map((item) => (
            <div key={item.label}><strong>{item.value}</strong><span>{item.label}</span></div>
          ))}
        </div>
        <div className="mkt-quote">
          <p>
            «Раньше заказы жили в блокноте и переписках. Теперь видно, что купили,
            кому напомнить и сколько осталось на складе. Вечером смотрю отчёт и
            закрываю смену за пару минут».
          </p>
          <span>Владелец демо-магазина · Модная лавка</span>
        </div>
      </section>

      <section id="faq" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Вопросы</span>
          <h2>Коротко о главном</h2>
        </header>
        <div className="mkt-faq">
          <details open>
            <summary>Можно ли всё потрогать до оплаты?</summary>
            <p>Да. Демо-магазин открыт целиком: витрина и админка с полным доступом. Смотрите заказы, склад, CRM, бонусы, рассылки и отчёты — без регистрации.</p>
          </details>
          <details>
            <summary>Нужен ли мне свой хостинг или домен?</summary>
            <p>Нет. Магазин сразу работает на поддомене платформы. Свой домен можно подключить позже — мы поможем с DNS и SSL.</p>
          </details>
          <details>
            <summary>А если у меня услуги, а не товары?</summary>
            <p>Выберите сервисную категорию: салон, барбершоп, клиника, массаж, репетитор, автосервис и другие. Получите каталог услуг, карточки специалистов и онлайн-запись с реальными свободными окнами — корзина и доставка при этом не мешают.</p>
          </details>
          <details>
            <summary>Что если мой товар не из списка?</summary>
            <p>Выберите «Другое»: шаблон универсальный. Названия категорий, карточки товаров и тексты настраиваются под любой ассортимент.</p>
          </details>
          <details>
            <summary>Как оплатить тариф?</summary>
            <p>Платформа выставляет счёт. Доступны банковский перевод и наличные, карта и ЕРИП подключаются. После подтверждения оплаты тариф активируется автоматически.</p>
          </details>
          <details>
            <summary>Можно ли подключить только нужные функции?</summary>
            <p>Да. В админке виден полный каталог сервисов со статусом каждого: готово, частично или в разработке. Бесплатные включаются сразу, платные — после оплаты.</p>
          </details>
          <details>
            <summary>Кому принадлежат данные и деньги покупателей?</summary>
            <p>Данные магазина изолированы. Платежи покупателей идут через ваш эквайринг; платформа выставляет счёт только за подписку и сервисы.</p>
          </details>
        </div>
      </section>

      <section className="mkt-cta">
        <div>
          <h2>Ваш сайт может работать уже сегодня</h2>
          <p>Откройте демо магазина или салона, посмотрите админку — и создайте свой сайт за пять минут.</p>
        </div>
        <div className="mkt-cta__actions">
          {hasDemo && (
            <a href={demoStorefront} target="_blank" rel="noreferrer" className="btn btn--ghost-light btn--lg" onClick={openDemo}>
              Смотреть демо
            </a>
          )}
          <Link to="/new" className="btn btn--gold btn--lg">Создать сайт</Link>
        </div>
      </section>
    </MarketingShell>
  )
}
