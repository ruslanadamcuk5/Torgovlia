import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../../lib/useApi'
import { formatMoney } from '../../lib/format'
import { track } from '../../lib/track'
import { Icon, type IconName } from '../../components/icons'
import MarketingShell from './MarketingShell'
import type { CategoryPreset, PlanInfo, PublicService, SignupCatalog } from '../../lib/types'

interface DemoInfo {
  enabled: boolean
  slug: string
  name: string
  storefront_url: string
  admin_url: string
  phone: string
  password: string
  reset_every_hours: number
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
    text: 'Каталог с фото, остатками и ценами, баннеры, акции, отзывы, статьи и QR-коды. 10 дизайн-шаблонов под категорию.',
    bullets: ['Категории и карточки', 'Поиск и фильтры', 'Установка на телефон'],
  },
  {
    icon: 'list' as IconName,
    title: 'Заказы без хаоса',
    text: 'Самовывоз по слотам или доставка по зонам. Статусы, история, уведомления в Telegram, SMS и на почту.',
    bullets: ['Интервалы и лимиты', 'Доставка и зоны', 'Статус для покупателя'],
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
  { title: 'Откройте демо', text: 'Посмотрите витрину и админку настоящего магазина — без регистрации и звонков.' },
  { title: 'Выберите категорию', text: 'Рыба, цветы, мясо, продукты, одежда или свой вариант: шаблон уже настроен.' },
  { title: 'Создайте магазин', text: 'Название, адрес на платформе и тариф. Счёт формируется сразу.' },
  { title: 'Начните продавать', text: 'Добавьте товары, включите доставку и отправьте ссылку покупателям.' },
]

const TRUST = [
  { value: '77', label: 'сервисов в реестре' },
  { value: '10', label: 'дизайн-шаблонов' },
  { value: '5 мин', label: 'до первого магазина' },
  { value: '24/7', label: 'мониторинг сайтов' },
]

const PRESET_FALLBACK: CategoryPreset[] = [
  { code: 'fish', title: 'Рыба и морепродукты', description: 'Свежая рыба, копчёности, икра', examples: ['охлаждённая рыба', 'икра'], icon: 'fish' },
  { code: 'meat', title: 'Мясо и птица', description: 'Вырезка, фарш, курица, индейка', examples: ['стейки', 'птица'], icon: 'box' },
  { code: 'flowers', title: 'Цветы и растения', description: 'Букеты, растения, подарки', examples: ['букеты', 'растения'], icon: 'heart' },
  { code: 'grocery', title: 'Продукты', description: 'Бакалея, молочное, напитки', examples: ['бакалея', 'напитки'], icon: 'cart' },
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

  return (
    <MarketingShell>
      <section className="mkt-hero mkt-hero--rich">
        <div className="mkt-hero__copy">
          <span className="mkt-eyebrow"><Icon name="sparkles" size={14} /> Платформа для торговых мест</span>
          <h1>Магазин, который <em>продаёт с первого дня</em></h1>
          <p>
            Витрина, заказы, склад, клиенты, рассылки и оплата — в одном окне. Без
            программиста, без отдельного хостинга и без таблиц Excel. Настройка
            занимает вечер, а не месяц.
          </p>
          <div className="mkt-hero__actions">
            {demo?.enabled ? (
              <a
                href={demo.storefront_url}
                target="_blank"
                rel="noreferrer"
                className="btn btn--gold btn--lg"
                onClick={openDemo}
              >
                <Icon name="eye" size={18} /> Открыть демо-магазин
              </a>
            ) : (
              <Link to="/start/new" className="btn btn--gold btn--lg">Создать магазин</Link>
            )}
            <Link to="/start/new" className="btn btn--ghost-light btn--lg">Создать магазин</Link>
          </div>
          <div className="mkt-hero__links">
            {demo?.enabled && (
              <a href={demo.admin_url} target="_blank" rel="noreferrer" onClick={openDemoAdmin}>
                <Icon name="dashboard" size={15} /> Войти в админку демо
                <Icon name="external" size={13} />
              </a>
            )}
            <a href="#tariffs">Смотреть тарифы <Icon name="arrow-right" size={14} /></a>
          </div>
          <div className="mkt-trust">
            <span><strong>{counts.ready || 42}</strong> сервисов уже работают</span>
            <span><strong>{TRUST[1].value}</strong> дизайн-шаблонов</span>
            <span><strong>3</strong> тарифа без скрытых платежей</span>
          </div>
        </div>

        <div className="mkt-preview mkt-preview--rich" aria-hidden="true">
          <div className="mkt-preview__top">
            <span className="mkt-preview__dot" />
            <span>torg.alwaysdata.net/shop/{demo?.slug ?? 'odezhda'}</span>
            <span className="mkt-preview__badge">демо</span>
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
      </section>

      <section className="mkt-strip">
        <span>Рыба</span><span>Мясо</span><span>Цветы</span><span>Продукты</span><span>Выпечка</span><span>Одежда</span><span>Электроника</span><span>Красота</span>
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
        </div>

        <div className="mkt-demo__cards">
          <article className="mkt-demo__card">
            <span className="mkt-demo__icon"><Icon name="grid" size={22} /></span>
            <h3>Витрина магазина</h3>
            <p>Каталог, карточки, корзина, оформление, личный кабинет, чат и бонусы.</p>
            {demo?.enabled ? (
              <a href={demo.storefront_url} target="_blank" rel="noreferrer" className="btn btn--primary btn--block" onClick={openDemo}>
                Открыть витрину <Icon name="external" size={15} />
              </a>
            ) : <span className="muted">Демо скоро появится</span>}
          </article>

          <article className="mkt-demo__card mkt-demo__card--accent">
            <span className="mkt-demo__icon"><Icon name="dashboard" size={22} /></span>
            <h3>Админка владельца</h3>
            <p>Заказы, склад, CRM, бонусы, рассылки, отчёты и настройка сервисов.</p>
            {demo?.enabled ? (
              <a href={demo.admin_url} target="_blank" rel="noreferrer" className="btn btn--gold btn--block" onClick={openDemoAdmin}>
                Войти в админку <Icon name="external" size={15} />
              </a>
            ) : <span className="muted">Демо скоро появится</span>}
          </article>

          <article className="mkt-demo__card mkt-demo__card--creds">
            <span className="mkt-demo__icon"><Icon name="lock" size={22} /></span>
            <h3>Доступ</h3>
            <p>Логин и пароль общие для демо. Ничего подтверждать не нужно.</p>
            <dl className="mkt-creds">
              <div><dt>Телефон</dt><dd>{demo?.phone ?? '+375 29 111-22-88'}</dd></div>
              <div><dt>Пароль</dt><dd>{demo?.password ?? 'ChangeMe123!'}</dd></div>
            </dl>
            <small className="muted">Перед продакшеном смените демо-пароль.</small>
          </article>
        </div>
      </section>

      <section id="features" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Всё для продаж</span>
          <h2>Не просто сайт, а рабочий магазин</h2>
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
          <h2>Готовый магазин под вашу категорию</h2>
          <p>Меняются тексты, разделы и подсказки. Ваши товары и бренд — сверху.</p>
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
              <Link to={`/start/new?category=${item.code}`} className="mkt-link">Выбрать шаблон <Icon name="arrow-right" size={14} /></Link>
            </article>
          ))}
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
              <Link to={`/start/new?plan=${plan.code}`} className={`btn ${index === 1 ? 'btn--gold' : 'btn--outline'} btn--block`}>
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
          <h2>Ваш магазин может работать уже сегодня</h2>
          <p>Откройте демо, посмотрите админку — и создайте свой магазин за пять минут.</p>
        </div>
        <div className="mkt-cta__actions">
          {demo?.enabled && (
            <a href={demo.storefront_url} target="_blank" rel="noreferrer" className="btn btn--ghost-light btn--lg" onClick={openDemo}>
              Смотреть демо
            </a>
          )}
          <Link to="/start/new" className="btn btn--gold btn--lg">Создать магазин</Link>
        </div>
      </section>
    </MarketingShell>
  )
}
