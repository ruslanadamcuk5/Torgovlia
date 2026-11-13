import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
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

type DemoTab = 'shop-store' | 'shop-admin' | 'salon-store' | 'salon-admin'

const DEMO_ORDER: DemoTab[] = ['shop-store', 'shop-admin', 'salon-store', 'salon-admin']

const DEMO_TABS: { id: DemoTab; label: string; hint: string }[] = [
  { id: 'shop-store', label: 'Магазин', hint: 'витрина' },
  { id: 'shop-admin', label: 'Магазин', hint: 'админка' },
  { id: 'salon-store', label: 'Услуги', hint: 'витрина' },
  { id: 'salon-admin', label: 'Услуги', hint: 'админка' },
]

const PRESET_ICONS: Record<string, IconName> = {
  fish: 'fish',
  box: 'box',
  heart: 'heart',
  tag: 'tag',
  cart: 'cart',
  sparkles: 'sparkles',
  smartphone: 'smartphone',
  scissors: 'scissors',
  calendar: 'calendar',
  users: 'users',
}

const PRESET_FALLBACK: CategoryPreset[] = [
  { code: 'odezhda', title: 'Одежда', description: 'Гардероб, обувь и аксессуары', examples: ['худи', 'куртки', 'джинсы'], icon: 'tag' },
  { code: 'flowers', title: 'Цветы', description: 'Букеты и композиции', examples: ['розы', 'пионы', 'упаковка'], icon: 'heart' },
  { code: 'grocery', title: 'Продукты', description: 'Бакалея, молочное, напитки', examples: ['сыр', 'молоко', 'кофе'], icon: 'cart' },
  { code: 'hairdresser', title: 'Салон красоты', description: 'Стрижки, окрашивание, уход', examples: ['стрижка', 'окрашивание', 'укладка'], icon: 'scissors' },
  { code: 'barber', title: 'Барбершоп', description: 'Мужские стрижки и борода', examples: ['фейд', 'борода', 'бритьё'], icon: 'scissors' },
  { code: 'clinic', title: 'Клиника', description: 'Приём врачей и процедуры', examples: ['терапевт', 'УЗИ', 'анализы'], icon: 'heart' },
  { code: 'studio', title: 'Студия', description: 'Мастер-классы и занятия', examples: ['керамика', 'рисование', 'йога'], icon: 'sparkles' },
  { code: 'auto', title: 'Автосервис', description: 'Ремонт и обслуживание', examples: ['ТО', 'шины', 'диагностика'], icon: 'tools' },
]

const FALLBACK_DESIGNS: DesignTemplateInfo[] = [
  { code: 'market', title: 'Рынок', description: 'Универсальный', mood: 'спокойный', tokens: { ink: '#1b2a33', teal: '#2c7a76', gold: '#c39a5a', cream: '#f8f5ef', 'teal-soft': '#e6f2ef' } },
  { code: 'bloom', title: 'Цветение', description: 'Цветы и подарки', mood: 'нежный', tokens: { ink: '#3d2438', teal: '#b04a7a', gold: '#c79a5e', cream: '#fdf7f5', 'teal-soft': '#fbe9f0' } },
  { code: 'ocean', title: 'Океан', description: 'Рыба и техника', mood: 'чистый', tokens: { ink: '#0b2545', teal: '#1667a8', gold: '#c39a5a', cream: '#f5f8fb', 'teal-soft': '#e6f0f8' } },
  { code: 'sun', title: 'Солнце', description: 'Овощи и выпечка', mood: 'тёплый', tokens: { ink: '#3b2416', teal: '#c25a24', gold: '#b9822f', cream: '#fbf6ee', 'teal-soft': '#fdeee2' } },
  { code: 'fresh', title: 'Свежесть', description: 'Здоровое питание', mood: 'лёгкий', tokens: { ink: '#173626', teal: '#2f8f4e', gold: '#c39a5a', cream: '#f8fbf7', 'teal-soft': '#e8f6ec' } },
  { code: 'mono', title: 'Графит', description: 'Электроника и услуги', mood: 'строгий', tokens: { ink: '#1c1c1c', teal: '#3a3a3a', gold: '#a67c2e', cream: '#fafafa', 'teal-soft': '#efefef' } },
  { code: 'lux', title: 'Люкс', description: 'Ювелирное и премиум', mood: 'дорогой', tokens: { ink: '#14110c', teal: '#8a6a2f', gold: '#a67c2e', cream: '#fcfaf4', 'teal-soft': '#f5efe2' } },
  { code: 'latte', title: 'Латте', description: 'Кофейни и hand-made', mood: 'уютный', tokens: { ink: '#2f241d', teal: '#8a5a3b', gold: '#b9822f', cream: '#faf6f1', 'teal-soft': '#f1e8e0' } },
]

const FALLBACK_PLANS: PlanInfo[] = [
  { code: 'start', title: 'Старт', description: 'Магазин, каталог, заказы и базовые шаблоны.', price_month: 19, price_year: 190, quotas: { products: 500, storage_gb: 1, sms_month: 100, users: 1 } },
  { code: 'business', title: 'Бизнес', description: 'Доставка, промокоды, отзывы, сотрудники и запись.', price_month: 49, price_year: 490, quotas: { products: 5000, storage_gb: 5, sms_month: 500, users: 3 } },
  { code: 'pro', title: 'Про', description: 'CRM, склад, рассылки, импорт прайсов и поддержка.', price_month: 99, price_year: 990, quotas: { products: 0, storage_gb: 20, sms_month: 2000, users: 10 } },
]

const FEATURES: { icon: IconName; title: string; text: string; bullets: string[] }[] = [
  {
    icon: 'cart',
    title: 'Витрина, которая продаёт',
    text: 'Каталог товаров и услуг, фото, цены, остатки, акции и отзывы. 18 шаблонов под категорию.',
    bullets: ['Категории и поиск', 'Баннеры и акции', 'Установка на телефон'],
  },
  {
    icon: 'calendar',
    title: 'Заказы и онлайн-запись',
    text: 'Самовывоз по слотам, доставка по зонам или запись к специалисту с реальными свободными окнами.',
    bullets: ['Интервалы и лимиты', 'Защита от двойной записи', 'Перенос и отмена'],
  },
  {
    icon: 'box',
    title: 'Склад и закупки',
    text: 'Остатки, приход, списание, инвентаризация. Поставщики и приёмка пополняют склад автоматически.',
    bullets: ['История движения', 'Закупки и приёмка', 'Штрихкоды и этикетки'],
  },
  {
    icon: 'users',
    title: 'Клиенты и CRM',
    text: 'Общая база из аккаунтов и гостевых заказов. Сегменты, заметки, метки и бонусные уровни.',
    bullets: ['Сегменты по покупкам', 'История визитов', 'Бонусы и уровни'],
  },
  {
    icon: 'send',
    title: 'Маркетинг с цифрами',
    text: 'Промокоды, брошенные корзины, допродажи, рассылки Email и SMS, напоминания о записи.',
    bullets: ['Кампании и сегменты', 'Напоминания клиентам', 'Импорт прайсов'],
  },
  {
    icon: 'shield',
    title: 'Платформа и поддержка',
    text: 'Домен, SSL, резервные копии, изоляция данных, мониторинг, счета и поддержка в одном окне.',
    bullets: ['Свой домен', 'Мониторинг 24/7', 'Счёт и активация'],
  },
]

const STEPS = [
  { title: 'Откройте демо', text: 'Магазин и салон целиком: витрина, админка и запись. Без регистрации.' },
  { title: 'Выберите шаблон', text: 'Товары или услуги: тексты, разделы и палитра уже настроены.' },
  { title: 'Создайте сайт', text: 'Название, адрес на платформе и тариф. Счёт формируется сразу.' },
  { title: 'Работайте', text: 'Добавьте товары или услуги, включите доставку и запись — и делитесь ссылкой.' },
]

const FAQ = [
  {
    q: 'Можно ли всё потрогать без оплаты и регистрации?',
    a: 'Да. Демо магазина и салона открываются целиком: витрина и админка. Вход в админку выполняется автоматически — логин и пароль не нужны. Внутри настоящие тестовые данные: заказы, склад, клиенты, записи, специалисты и отчёты.',
  },
  {
    q: 'Подходит ли платформа для услуг?',
    a: 'Да, это не отдельный продукт. Услуги живут в том же каталоге, что и товары: категории, цены, отзывы и шаблоны общие. Для услуг добавляются длительность, специалисты, буфер между визитами и онлайн-запись по свободным окнам. Салон, барбершоп, клиника, студия и автосервис уже есть в пресетах.',
  },
  {
    q: 'Что если у меня и товары, и услуги?',
    a: 'Выберите гибридный тип бизнеса: главная останется товарной, а блок услуг и запись подключатся рядом. Переключение типа не удаляет данные.',
  },
  {
    q: 'Нужен ли свой хостинг или домен?',
    a: 'Нет. Сайт сразу работает на поддомене платформы. Свой домен подключается позже — поможем с DNS и SSL.',
  },
  {
    q: 'Как оплатить тариф?',
    a: 'Платформа выставляет счёт. Доступны банковский перевод и наличные, карта и ЕРИП подключаются. После подтверждения оплаты тариф активируется.',
  },
  {
    q: 'Данные магазинов не смешиваются?',
    a: 'Нет. У каждого арендатора своя область данных, доступы и настройки. Платформа видит только агрегированные показатели, а покупатели — только свой магазин.',
  },
]

function reducedMotion(): boolean {
  return typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function useInView<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T | null>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (reducedMotion() || typeof IntersectionObserver === 'undefined') {
      setSeen(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setSeen(true)
          observer.disconnect()
        }
      },
      { threshold, rootMargin: '0px 0px -8% 0px' },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [threshold])
  return { ref, seen }
}

function Reveal({
  children,
  delay = 0,
  className = '',
}: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  const { ref, seen } = useInView<HTMLDivElement>()
  return (
    <div
      ref={ref}
      className={`lp-reveal ${seen ? 'is-in' : ''} ${className}`.trim()}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}

function Counter({ to, suffix = '', prefix = '' }: { to: number; suffix?: string; prefix?: string }) {
  const { ref, seen } = useInView<HTMLSpanElement>(0.4)
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!seen) return
    if (reducedMotion()) {
      setValue(to)
      return
    }
    let frame = 0
    const started = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / 1400)
      setValue(Math.round(to * (1 - Math.pow(1 - progress, 3))))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [seen, to])
  return <span ref={ref}>{prefix}{value}{suffix}</span>
}

function Stars() {
  return (
    <span className="lp-stars" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((item) => <i key={item} style={{ animationDelay: `${item * 140}ms` }} />)}
    </span>
  )
}

function MouseParallax() {
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const element = ref.current
    if (!element || reducedMotion()) return
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const host = element.parentElement ?? element
    const onMove = (event: PointerEvent) => {
      const rect = element.getBoundingClientRect()
      const x = (event.clientX - rect.left) / rect.width - 0.5
      const y = (event.clientY - rect.top) / rect.height - 0.5
      host.style.setProperty('--lp-rx', `${(-y * 6).toFixed(2)}deg`)
      host.style.setProperty('--lp-ry', `${(x * 8).toFixed(2)}deg`)
    }
    const reset = () => {
      host.style.setProperty('--lp-rx', '0deg')
      host.style.setProperty('--lp-ry', '0deg')
    }
    element.addEventListener('pointermove', onMove)
    element.addEventListener('pointerleave', reset)
    return () => {
      element.removeEventListener('pointermove', onMove)
      element.removeEventListener('pointerleave', reset)
    }
  }, [])
  return <div ref={ref} className="lp-hero__visual" aria-hidden="true" />
}

/* ─── Анимированные макеты ─────────────────────────────────────────── */

const SHOP_PRODUCTS = [
  { name: 'Худи оверсайз', price: '79.00', tone: 'a' },
  { name: 'Куртка-бомбер', price: '189.00', tone: 'b' },
  { name: 'Тренч', price: '249.00', tone: 'c' },
  { name: 'Свитшот', price: '99.00', tone: 'd' },
]

function BrowserBar({ url }: { url: string }) {
  return (
    <div className="lp-mock__bar">
      <span className="lp-mock__dots"><i /><i /><i /></span>
      <span className="lp-mock__url">{url}</span>
      <span className="lp-mock__live"><i /> live</span>
    </div>
  )
}

function ShopStoreMock() {
  return (
    <div className="lp-mock lp-mock--store">
      <BrowserBar url="demo/shop — витрина" />
      <div className="lp-store">
        <div className="lp-store__nav">
          <span className="lp-store__logo">М</span>
          <strong>Модная лавка</strong>
          <span className="lp-store__links"><i /><i /><i /></span>
          <span className="lp-store__cart"><Icon name="cart" size={14} /> 3</span>
        </div>
        <div className="lp-store__hero">
          <div>
            <span className="lp-store__kicker">новая коллекция</span>
            <strong>Базовый гардероб<br />на каждый день</strong>
            <em>доставка по городу · самовывоз со скидкой</em>
            <span className="lp-store__cta">Смотреть коллекцию <Icon name="arrow-right" size={13} /></span>
          </div>
          <span className="lp-store__sale">−20%</span>
        </div>
        <div className="lp-store__grid">
          {SHOP_PRODUCTS.map((item, index) => (
            <div className="lp-store__card" key={item.name} style={{ animationDelay: `${index * 120}ms` }}>
              <span className={`lp-store__img lp-store__img--${item.tone}`} />
              <strong>{item.name}</strong>
              <small>{item.price} BYN</small>
              <span className="lp-store__add"><Icon name="plus" size={12} /></span>
            </div>
          ))}
        </div>
        <div className="lp-store__toast">
          <Icon name="check" size={14} /> Товар добавлен в корзину
        </div>
      </div>
    </div>
  )
}

function ShopAdminMock() {
  const bars = [46, 68, 40, 84, 58, 94, 72]
  return (
    <div className="lp-mock lp-mock--admin">
      <BrowserBar url="demo/shop — админка" />
      <div className="lp-admin">
        <aside className="lp-admin__side">
          {['grid', 'cart', 'box', 'users', 'chart'].map((icon, index) => (
            <span key={icon} className={index === 0 ? 'is-active' : ''}>
              <Icon name={icon as IconName} size={15} />
            </span>
          ))}
        </aside>
        <div className="lp-admin__main">
          <div className="lp-admin__head">
            <div><small>Сегодня</small><strong>Сводка магазина</strong></div>
            <span className="lp-admin__online"><i /> онлайн</span>
          </div>
          <div className="lp-admin__kpis">
            <div><span>Выручка</span><strong>4 820 <em>BYN</em></strong><i className="up">+18%</i></div>
            <div><span>Заказы</span><strong>32</strong><i className="up">+6</i></div>
            <div><span>Средний чек</span><strong>150 <em>BYN</em></strong><i className="up">+4%</i></div>
          </div>
          <div className="lp-admin__chart">
            {bars.map((height, index) => (
              <span key={index} style={{ height: `${height}%`, animationDelay: `${index * 90}ms` }} />
            ))}
          </div>
          <div className="lp-admin__rows">
            <div style={{ animationDelay: '120ms' }}><i /><span>Заказ №1042</span><strong>158 BYN</strong><em>новый</em></div>
            <div style={{ animationDelay: '240ms' }}><i /><span>Заказ №1041</span><strong>249 BYN</strong><em>собран</em></div>
            <div style={{ animationDelay: '360ms' }}><i /><span>Заказ №1040</span><strong>79 BYN</strong><em>выдан</em></div>
          </div>
        </div>
        <div className="lp-admin__alert"><Icon name="bell" size={14} /> Новый заказ</div>
      </div>
    </div>
  )
}

function SalonStoreMock() {
  const services = [
    { name: 'Женская стрижка', meta: '60 мин · 45 BYN ins' },
    { name: 'Окрашивание', meta: '120 мин · 95 BYN' },
    { name: 'Укладка', meta: '45 мин · 35 BYN' },
  ]
  return (
    <div className="lp-mock lp-mock--store lp-mock--salon">
      <BrowserBar url="demo/salon — витрина" />
      <div className="lp-salon">
        <div className="lp-salon__nav">
          <span className="lp-salon__logo">Л</span>
          <strong>Салон красоты «Локон»</strong>
          <span className="lp-salon__open"><i /> запись открыта</span>
        </div>
        <div className="lp-salon__hero">
          <div>
            <span className="lp-store__kicker">онлайн-запись · свободное время</span>
            <strong>Стрижка, окрашивание<br />и уход</strong>
            <em>выберите мастера и удобное окно</em>
          </div>
          <div className="lp-salon__masters">
            <span>А</span><span>М</span><span>Д</span>
          </div>
        </div>
        <div className="lp-salon__services">
          {services.map((item, index) => (
            <div key={item.name} style={{ animationDelay: `${index * 120}ms` }}>
              <span className={`lp-salon__ico lp-salon__ico--${index + 1}`}><Icon name="sparkles" size={15} /></span>
              <strong>{item.name.replace(' ins', '')}</strong>
              <small>{item.meta.replace(' ins', '')}</small>
              <Icon name="chevron-right" size={15} />
            </div>
          ))}
        </div>
        <div className="lp-salon__slots">
          <span className="lp-salon__day is-active"><small>сегодня</small><strong>14:00</strong></span>
          <span className="lp-salon__day"><small>сегодня</small><strong>15:30</strong></span>
          <span className="lp-salon__day lp-salon__day--pulse"><small>завтра</small><strong>10:00</strong></span>
          <span className="lp-salon__day"><small>завтра</small><strong>12:30</strong></span>
          <span className="lp-salon__book">Записаться</span>
        </div>
      </div>
    </div>
  )
}

function SalonAdminMock() {
  return (
    <div className="lp-mock lp-mock--admin lp-mock--salon-admin">
      <BrowserBar url="demo/salon — админка" />
      <div className="lp-admin">
        <aside className="lp-admin__side">
          {['calendar', 'users', 'chart', 'settings'].map((icon, index) => (
            <span key={icon} className={index === 0 ? 'is-active' : ''}>
              <Icon name={icon as IconName} size={15} />
            </span>
          ))}
        </aside>
        <div className="lp-admin__main">
          <div className="lp-admin__head">
            <div><small>Сегодня · 13 ноября</small><strong>Записи на день</strong></div>
            <span className="lp-admin__online"><i /> онлайн</span>
          </div>
          <div className="lp-admin__kpis">
            <div><span>Записи</span><strong>18</strong><i className="up">+4</i></div>
            <div><span>Выручка</span><strong>1 240 <em>BYN</em></strong><i className="up">+12%</i></div>
            <div><span>Загрузка</span><strong>78<em>%</em></strong><i className="up">+6%</i></div>
          </div>
          <div className="lp-admin__timeline">
            <div style={{ animationDelay: '100ms' }}><span>14:00</span><strong>Анна — стрижка</strong><em>45 BYN</em></div>
            <div style={{ animationDelay: '220ms' }}><span>15:30</span><strong>Марина — окрашивание</strong><em>95 BYN</em></div>
            <div style={{ animationDelay: '340ms' }}><span>17:00</span><strong>Дмитрий — борода</strong><em>25 BYN</em></div>
            <div className="lp-admin__free" style={{ animationDelay: '460ms' }}><span>18:00</span><strong>Свободное окно</strong><em>+</em></div>
          </div>
          <div className="lp-admin__load">
            <span>Анна <i style={{ width: '82%' }} /></span>
            <span>Марина <i style={{ width: '64%' }} /></span>
          </div>
        </div>
        <div className="lp-admin__alert"><Icon name="calendar" size={14} /> Новая запись</div>
      </div>
    </div>
  )
}

function DemoStage({ tab }: { tab: DemoTab }) {
  if (tab === 'shop-admin') return <ShopAdminMock />
  if (tab === 'salon-store') return <SalonStoreMock />
  if (tab === 'salon-admin') return <SalonAdminMock />
  return <ShopStoreMock />
}

export default function MarketingHome() {
  const { data } = useApi<SignupCatalog>('/signup/catalog', false)
  const { data: demo } = useApi<DemoInfo>('/platform/demo', false)
  const { data: designs } = useApi<DesignTemplateInfo[]>('/templates', false)

  const [demoTab, setDemoTab] = useState<DemoTab>('shop-store')
  const [paused, setPaused] = useState(false)
  const [auto, setAuto] = useState(!reducedMotion())

  const plans = data?.plans ?? []
  const categories = data?.categories?.length ? data.categories : PRESET_FALLBACK
  const services = data?.services ?? []

  const counts = {
    ready: services.filter((item) => item.status === 'ready').length,
    total: services.length || 89,
  }

  const shopSlug = demo?.slug ?? 'odezhda'
  const salonSlug = demo?.service_demo?.enabled ? demo.service_demo.slug ?? 'salon' : null
  const salonReady = salonSlug !== null || demo === null
  const shopName = demo?.name ?? 'Модная лавка'
  const salonName = demo?.service_demo?.name ?? 'Салон красоты «Локон»'

  const storeUrl = (kind: 'shop' | 'salon') => `/shop/${kind === 'shop' ? shopSlug : salonSlug ?? 'salon'}/`
  const adminUrl = (kind: 'shop' | 'salon') => `/shop/${kind === 'shop' ? shopSlug : salonSlug ?? 'salon'}/admin`

  const salonTab = demoTab.startsWith('salon')
  const adminTab = demoTab.endsWith('-admin')
  const activeKind: 'shop' | 'salon' = salonTab ? 'salon' : 'shop'

  useEffect(() => {
    track('visit')
  }, [])

  useEffect(() => {
    if (!auto || paused || !salonReady) return
    const timer = window.setInterval(() => {
      setDemoTab((current) => {
        const index = DEMO_ORDER.indexOf(current)
        return DEMO_ORDER[(index + 1) % DEMO_ORDER.length]
      })
    }, 7200)
    return () => window.clearInterval(timer)
  }, [auto, paused, salonReady])

  const chooseTab = (tab: DemoTab) => {
    if (tab.startsWith('salon') && !salonReady) return
    setAuto(false)
    setDemoTab(tab)
    track('demo_storefront', { detail: tab })
  }

  const designsList = designs?.length ? designs : FALLBACK_DESIGNS

  return (
    <MarketingShell>
      {/* ─── Hero ─────────────────────────────────────────────── */}
      <section className="lp-hero">
        <div className="lp-hero__bg" aria-hidden="true">
          <span className="lp-blob lp-blob--a" />
          <span className="lp-blob lp-blob--b" />
          <span className="lp-blob lp-blob--c" />
          <span className="lp-grid" />
        </div>

        <div className="lp-hero__copy">
          <span className="lp-pill">
            <i /> Торговля и услуги · одна платформа
          </span>
          <h1>
            Продавайте товары.<br />
            Принимайте записи.<br />
            <span className="lp-grad">В одном окне.</span>
          </h1>
          <p>
            Витрина, заказы, склад и клиенты — рядом с услугами, специалистами
            и онлайн-записью. Запустите сайт за вечер и управляйте всем из
            одной админки.
          </p>
          <div className="lp-hero__actions">
            <a href="#demos" className="lp-btn lp-btn--primary lp-btn--lg">
              <Icon name="eye" size={18} /> Потрогать демо
            </a>
            <Link to="/new" className="lp-btn lp-btn--ghost lp-btn--lg">
              Создать сайт <Icon name="arrow-right" size={16} />
            </Link>
          </div>
          <div className="lp-hero__note">
            <span><Icon name="check" size={14} /> без карты</span>
            <span><Icon name="check" size={14} /> демо без логина</span>
            <span><Icon name="check" size={14} /> запуск за 5 минут</span>
          </div>
          <div className="lp-hero__stats">
            <div><strong><Counter to={counts.total} /></strong><span>сервисов</span></div>
            <div><strong><Counter to={18} /></strong><span>шаблонов</span></div>
            <div><strong>24/7</strong><span>мониторинг</span></div>
          </div>
        </div>

        <div className="lp-hero__stage">
          <MouseParallax />
          <div className="lp-stage" aria-hidden="true">
            <span className="lp-stage__ring" />
            <div className="lp-stage__card lp-stage__card--store">
              <div className="lp-stage__bar"><i /><i /><i /><span>модная лавка</span></div>
              <div className="lp-stage__hero">
                <span>новая коллекция</span>
                <strong>Гардероб<br />на каждый день</strong>
                <em>−20%</em>
              </div>
              <div className="lp-stage__tiles">
                <span /><span /><span />
              </div>
            </div>
            <div className="lp-stage__card lp-stage__card--booking">
              <div className="lp-stage__booking-head">
                <span className="lp-stage__avatar">Л</span>
                <div><strong>Онлайн-запись</strong><small>салон · сегодня</small></div>
                <span className="lp-stage__dot" />
              </div>
              <div className="lp-stage__slots">
                <span>14:00</span><span className="is-active">15:30</span><span>17:00</span>
              </div>
              <div className="lp-stage__master">
                <span>А</span><span>М</span><em>свободно 2 мастера</em>
              </div>
            </div>
            <div className="lp-stage__chip lp-stage__chip--sales">
              <Icon name="chart" size={15} />
              <div><strong>+18%</strong><small>выручка за неделю</small></div>
            </div>
            <div className="lp-stage__chip lp-stage__chip--order">
              <span className="lp-stage__pulse" />
              <div><strong>Новый заказ</strong><small>158 BYN · только что</small></div>
            </div>
            <div className="lp-stage__chip lp-stage__chip--booking2">
              <Icon name="calendar" size={15} />
              <div><strong>Запись подтверждена</strong><small>Анна · 15:30</small></div>
            </div>
          </div>
        </div>
      </section>

      <div className="lp-ticker" aria-hidden="true">
        <div className="lp-ticker__track">
          {[0, 1].map((copy) => (
            <div className="lp-ticker__group" key={copy}>
              {[
                'Одежда', 'Цветы', 'Продукты', 'Салон красоты', 'Барбершоп',
                'Клиника', 'Студия', 'Автосервис', 'Электроника', 'Кофейня',
              ].map((item) => (
                <span key={`${copy}-${item}`}><i />{item}</span>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ─── Два бизнеса ──────────────────────────────────────── */}
      <section className="lp-section" id="possibilities">
        <Reveal>
          <header className="lp-head">
            <span className="lp-eyebrow">Одна платформа — два сценария</span>
            <h2>Товары и услуги <span className="lp-grad">без компромиссов</span></h2>
            <p>
              Не нужно выбирать между магазином и салоном. Каталог, касса,
              клиенты и отчёты общие, а запись и специалисты включаются там,
              где нужны.
            </p>
          </header>
        </Reveal>

        <div className="lp-pillars">
          <Reveal delay={80}>
            <article className="lp-pillar lp-pillar--shop">
              <div className="lp-pillar__top">
                <span className="lp-pillar__icon"><Icon name="cart" size={22} /></span>
                <span className="lp-pillar__tag">торговля</span>
              </div>
              <h3>Магазин, который считает каждую продажу</h3>
              <p>Каталог, корзина, самовывоз, доставка, склад и CRM — без отдельных подписок.</p>
              <ul>
                <li><Icon name="check" size={13} /> Заказы и статусы</li>
                <li><Icon name="check" size={13} /> Остатки и закупки</li>
                <li><Icon name="check" size={13} /> Промокоды и бонусы</li>
              </ul>
              <div className="lp-pillar__anim" aria-hidden="true">
                <div className="lp-mini-order">
                  <span className="lp-mini-order__dot" />
                  <div><strong>Заказ №1042</strong><small>2 товара · самовывоз</small></div>
                  <em>158 BYN</em>
                </div>
                <div className="lp-mini-order lp-mini-order--two">
                  <span className="lp-mini-order__dot" />
                  <div><strong>Заказ №1041</strong><small>оплачен картой</small></div>
                  <em>249 BYN</em>
                </div>
              </div>
              <div className="lp-pillar__actions">
                <a href={storeUrl('shop')} className="lp-link">Витрина магазина <Icon name="external" size={13} /></a>
                <a href={adminUrl('shop')} className="lp-link lp-link--dark">Админка без пароля <Icon name="arrow-right" size={13} /></a>
              </div>
            </article>
          </Reveal>

          <Reveal delay={160}>
            <article className="lp-pillar lp-pillar--salon">
              <div className="lp-pillar__top">
                <span className="lp-pillar__icon"><Icon name="scissors" size={22} /></span>
                <span className="lp-pillar__tag">услуги</span>
              </div>
              <h3>Салон, который не теряет клиентов</h3>
              <p>Услуги в общем каталоге, специалисты, свободные окна и напоминания о визите.</p>
              <ul>
                <li><Icon name="check" size={13} /> Онлайн-запись 24/7</li>
                <li><Icon name="check" size={13} /> График специалистов</li>
                <li><Icon name="check" size={13} /> Перенос и отмена</li>
              </ul>
              <div className="lp-pillar__anim" aria-hidden="true">
                <div className="lp-mini-cal">
                  <span className="lp-mini-cal__day is-active"><small>сегодня</small><strong>14:00</strong></span>
                  <span className="lp-mini-cal__day"><small>сегодня</small><strong>15:30</strong></span>
                  <span className="lp-mini-cal__day is-pulse"><small>завтра</small><strong>10:00</strong></span>
                </div>
                <div className="lp-mini-master">
                  <span>А</span><span>М</span>
                  <em>2 мастера свободны</em>
                </div>
              </div>
              <div className="lp-pillar__actions">
                <a href={storeUrl('salon')} className="lp-link">Витрина услуг <Icon name="external" size={13} /></a>
                <a href={adminUrl('salon')} className="lp-link lp-link--dark">Админка без пароля <Icon name="arrow-right" size={13} /></a>
              </div>
            </article>
          </Reveal>
        </div>
      </section>

      {/* ─── Живое демо ───────────────────────────────────────── */}
      <section className="lp-demo" id="demos">
        <div className="lp-demo__bg" aria-hidden="true" />
        <Reveal>
          <header className="lp-head lp-head--center">
            <span className="lp-eyebrow">Живое демо · без логина и пароля</span>
            <h2>Загляните внутрь <span className="lp-grad">прямо сейчас</span></h2>
            <p>
              Четыре экрана: магазин и салон, витрина и админка. В админку
              пускает сразу — вход выполняется автоматически.
            </p>
          </header>
        </Reveal>

        <div
          className="lp-demo__panel"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          <div className="lp-demo__tabs" role="tablist" aria-label="Демо платформы">
            {DEMO_TABS.map((tab) => {
              const disabled = tab.id.startsWith('salon') && !salonReady
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={demoTab === tab.id}
                  className={`lp-demo__tab ${demoTab === tab.id ? 'is-active' : ''} ${tab.hint === 'админка' ? 'is-admin' : ''}`}
                  disabled={disabled}
                  onClick={() => chooseTab(tab.id)}
                >
                  <span>{tab.label}</span>
                  <em>{tab.hint}</em>
                  {tab.hint === 'админка' && <i className="lp-demo__lock" title="вход без пароля"><Icon name="lock" size={11} /></i>}
                </button>
              )
            })}
            <span className="lp-demo__auto">
              <i className={paused || !auto ? '' : 'is-live'} />
              {auto && !paused ? 'авто-показ' : 'пауза'}
            </span>
          </div>

          <div className={`lp-demo__stage ${salonTab ? 'is-salon' : ''} ${adminTab ? 'is-admin' : ''}`}>
            <div className="lp-demo__screen" key={demoTab}>
              <DemoStage tab={demoTab} />
            </div>
            <aside className="lp-demo__side">
              <span className="lp-eyebrow">
                {salonTab ? 'бизнес услуг' : 'бизнес товаров'}
              </span>
              <h3>{salonTab ? salonName : shopName}</h3>
              <p>
                {salonTab
                  ? 'Каталог услуг, мастера, свободные окна и записи. Внутри — настоящие данные демо-салона.'
                  : 'Каталог, заказы, склад, клиенты и отчёты. Внутри — настоящие данные демо-магазина.'}
              </p>
              <ul className="lp-demo__facts">
                <li><Icon name="check" size={14} /> {adminTab ? 'вход без пароля' : 'открытая витрина'}</li>
                <li><Icon name="check" size={14} /> можно менять и заказывать</li>
                <li><Icon name="check" size={14} /> сброс каждые {demo?.reset_every_hours ?? 24} ч</li>
              </ul>
              <div className="lp-demo__actions">
                <a
                  href={storeUrl(activeKind)}
                  className="lp-btn lp-btn--primary"
                  onClick={() => track('demo_storefront', { detail: activeKind })}
                >
                  <Icon name="eye" size={16} /> Открыть витрину
                </a>
                <a
                  href={adminUrl(activeKind)}
                  className="lp-btn lp-btn--dark"
                  onClick={() => track('demo_admin', { detail: activeKind })}
                >
                  <Icon name="dashboard" size={16} /> Открыть админку
                </a>
                <span className="lp-demo__nologin">
                  <Icon name="lock" size={12} /> без логина и пароля
                </span>
              </div>
            </aside>
          </div>
        </div>
      </section>

      {/* ─── Возможности ──────────────────────────────────────── */}
      <section className="lp-section" id="features">
        <Reveal>
          <header className="lp-head">
            <span className="lp-eyebrow">Всё в одном окне</span>
            <h2>Не сайт-визитка, а <span className="lp-grad">рабочий бизнес</span></h2>
            <p>Бесплатные функции уже включены. Платные подключаются в один клик, когда понадобятся.</p>
          </header>
        </Reveal>
        <div className="lp-features">
          {FEATURES.map((item, index) => (
            <Reveal key={item.title} delay={index * 60}>
              <article className="lp-feature">
                <span className="lp-feature__icon"><Icon name={item.icon} size={21} /></span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <ul>
                  {item.bullets.map((bullet) => (
                    <li key={bullet}><Icon name="check" size={12} /> {bullet}</li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ─── Цифры ────────────────────────────────────────────── */}
      <section className="lp-numbers">
        <div className="lp-numbers__grid">
          <div><strong><Counter to={counts.total} /></strong><span>сервисов в реестре</span></div>
          <div><strong><Counter to={18} /></strong><span>дизайн-шаблонов</span></div>
          <div><strong><Counter to={16} /></strong><span>пресетов категорий</span></div>
          <div><strong>5 мин</strong><span>до первого сайта</span></div>
        </div>
        <div className="lp-numbers__quote">
          <Stars />
          <p>
            «Раньше заказы жили в блокноте и переписках. Теперь видно, что купили,
            кому напомнить и сколько осталось на складе. Вечером смотрю отчёт и
            закрываю смену за пару минут».
          </p>
          <span>Владелец демо-магазина · Модная лавка</span>
        </div>
      </section>

      {/* ─── Как это работает ─────────────────────────────────── */}
      <section className="lp-section lp-section--soft" id="how">
        <Reveal>
          <header className="lp-head">
            <span className="lp-eyebrow">Четыре шага</span>
            <h2>От идеи до первого <span className="lp-grad">заказа и визита</span></h2>
          </header>
        </Reveal>
        <div className="lp-steps">
          <span className="lp-steps__line" aria-hidden="true"><i /></span>
          {STEPS.map((item, index) => (
            <Reveal key={item.title} delay={index * 90}>
              <article className="lp-step">
                <span className="lp-step__num">{String(index + 1).padStart(2, '0')}</span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ─── Шаблоны ──────────────────────────────────────────── */}
      <section className="lp-section" id="templates">
        <Reveal>
          <header className="lp-head">
            <span className="lp-eyebrow">Шаблоны и дизайн</span>
            <h2>Готовый сайт под <span className="lp-grad">вашу категорию</span></h2>
            <p>Меняются тексты, разделы и палитра — для товаров и услуг. Данные и бренд остаются на месте.</p>
          </header>
        </Reveal>

        <div className="lp-cats">
          {categories.slice(0, 12).map((item) => (
            <Link key={item.code} to={`/new?category=${item.code}`} className="lp-cat">
              <span className="lp-cat__icon"><Icon name={PRESET_ICONS[item.icon] ?? 'tag'} size={17} /></span>
              <strong>{item.title}</strong>
              <small>{item.description}</small>
            </Link>
          ))}
        </div>

        <div className="lp-designs" aria-hidden="true">
          {[0, 1].map((row) => (
            <div className={`lp-designs__row ${row === 1 ? 'lp-designs__row--reverse' : ''}`} key={row}>
              <div className="lp-designs__track">
                {[...designsList, ...designsList].map((design, index) => {
                  const tokens = design.tokens
                  return (
                    <article
                      key={`${row}-${design.code}-${index}`}
                      className="lp-design"
                      style={{
                        '--d-ink': tokens.ink ?? '#1b2a33',
                        '--d-teal': tokens.teal ?? '#2c7a76',
                        '--d-gold': tokens.gold ?? '#c39a5a',
                        '--d-cream': tokens.cream ?? '#f8f5ef',
                        '--d-soft': tokens['teal-soft'] ?? '#e6f2ef',
                      } as CSSProperties}
                    >
                      <div className="lp-design__screen">
                        <span className="lp-design__bar"><i /><i /><i /></span>
                        <div className="lp-design__body">
                          <span className="lp-design__logo">Т</span>
                          <span className="lp-design__kicker" />
                          <strong />
                          <em />
                          <div className="lp-design__tiles"><span /><span /><span /></div>
                        </div>
                      </div>
                      <div className="lp-design__meta">
                        <strong>{design.title}</strong>
                        <span>{design.mood}</span>
                        <div className="lp-design__swatches">
                          {[tokens.ink, tokens.teal, tokens.gold, tokens.cream].filter(Boolean).map((color, i) => (
                            <i key={i} style={{ background: color }} />
                          ))}
                        </div>
                      </div>
                    </article>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
        <Reveal className="lp-center">
          <Link to="/new" className="lp-btn lp-btn--ghost">
            Подобрать шаблон <Icon name="arrow-right" size={15} />
          </Link>
        </Reveal>
      </section>

      {/* ─── Тарифы ───────────────────────────────────────────── */}
      <section className="lp-section lp-section--soft" id="pricing">
        <Reveal>
          <header className="lp-head lp-head--center">
            <span className="lp-eyebrow">Тарифы</span>
            <h2>Платите за бизнес, <span className="lp-grad">а не за функции</span></h2>
            <p>Первый месяц — по выбранному тарифу. Повышение и платные сервисы — после оплаты счёта.</p>
          </header>
        </Reveal>
        <div className="lp-plans">
          {(plans.length ? plans : FALLBACK_PLANS).map((plan, index) => (
            <Reveal key={plan.code} delay={index * 90}>
              <article className={`lp-plan ${index === 1 ? 'is-featured' : ''}`}>
                {index === 1 && <span className="lp-plan__label">Популярный</span>}
                <h3>{plan.title}</h3>
                <div className="lp-plan__price">
                  <strong>{formatMoney(plan.price_month)}</strong>
                  <span>BYN / мес</span>
                </div>
                <p>{plan.description}</p>
                <ul>
                  <li><Icon name="check" size={13} /> Товаров и услуг: {plan.quotas.products ? plan.quotas.products : 'без лимита'}</li>
                  <li><Icon name="check" size={13} /> Хранилище: {plan.quotas.storage_gb} ГБ</li>
                  <li><Icon name="check" size={13} /> SMS: {plan.quotas.sms_month} / мес</li>
                  <li><Icon name="check" size={13} /> Сотрудников: {plan.quotas.users}</li>
                </ul>
                <Link to={`/new?plan=${plan.code}`} className={`lp-btn ${index === 1 ? 'lp-btn--primary' : 'lp-btn--ghost'} lp-btn--block`}>
                  Выбрать «{plan.title}»
                </Link>
              </article>
            </Reveal>
          ))}
        </div>
        <Reveal>
          <p className="lp-plans__note">
            <Icon name="info" size={14} /> Платные add-on подключаются отдельно: SMS-рассылки, свой домен,
            AI-инструменты, интеграции и несколько точек.
          </p>
        </Reveal>
      </section>

      {/* ─── FAQ ──────────────────────────────────────────────── */}
      <section className="lp-section" id="faq">
        <Reveal>
          <header className="lp-head">
            <span className="lp-eyebrow">Вопросы</span>
            <h2>Коротко о <span className="lp-grad">главном</span></h2>
          </header>
        </Reveal>
        <div className="lp-faq">
          {FAQ.map((item, index) => (
            <Reveal key={item.q} delay={index * 40}>
              <details className="lp-faq__item">
                <summary>
                  <span>{item.q}</span>
                  <i><Icon name="plus" size={16} /></i>
                </summary>
                <p>{item.a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ─── CTA ──────────────────────────────────────────────── */}
      <section className="lp-cta">
        <div className="lp-cta__bg" aria-hidden="true">
          <span /><span /><span />
        </div>
        <Reveal>
          <div className="lp-cta__inner">
            <span className="lp-eyebrow">Демо открыто прямо сейчас</span>
            <h2>Посмотрите изнутри — <span className="lp-grad">без пароля</span></h2>
            <p>Магазин и салон, витрина и админка. Внутри настоящие данные, всё можно менять.</p>
            <div className="lp-cta__actions">
              <a href={storeUrl('shop')} className="lp-btn lp-btn--primary lp-btn--lg">
                <Icon name="eye" size={18} /> Демо магазина
              </a>
              <a href={adminUrl('shop')} className="lp-btn lp-btn--dark lp-btn--lg">
                <Icon name="dashboard" size={18} /> Админка магазина
              </a>
              <a href={adminUrl('salon')} className="lp-btn lp-btn--ghost lp-btn--lg">
                <Icon name="calendar" size={18} /> Админка салона
              </a>
            </div>
            <Link to="/new" className="lp-cta__link">
              Или сразу создать свой сайт <Icon name="arrow-right" size={15} />
            </Link>
          </div>
        </Reveal>
      </section>
    </MarketingShell>
  )
}
