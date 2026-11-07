import { Link } from 'react-router-dom'
import { useApi } from '../../lib/useApi'
import { formatMoney } from '../../lib/format'
import { Icon, type IconName } from '../../components/icons'
import MarketingShell from './MarketingShell'
import type { CategoryPreset, SignupCatalog } from '../../lib/types'

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
  { icon: 'cart' as IconName, title: 'Витрина и каталог', text: 'Товары, категории, цены, фото, остатки и товар дня. Клиент видит актуальный ассортимент.' },
  { icon: 'list' as IconName, title: 'Заказы и брони', text: 'Заказ с самовывозом или доставкой, статусы, уведомления и история покупателя.' },
  { icon: 'chart' as IconName, title: 'Аналитика', text: 'Выручка, средний чек, топ товаров и повторные покупки — без таблиц и Excel.' },
  { icon: 'users' as IconName, title: 'Клиенты и роли', text: 'База покупателей, сотрудники, продавцы и права доступа для каждого.' },
  { icon: 'send' as IconName, title: 'Рассылки и акции', text: 'SMS и сообщения по своей базе, промокоды, скидки и персональные предложения.' },
  { icon: 'shield' as IconName, title: 'Домен и защита', text: 'Поддомен сразу, свой домен позже. SSL, резервные копии и изоляция данных.' },
]

const STEPS = [
  { title: 'Выберите категорию', text: 'Рыба, цветы, мясо, продукты, одежда — шаблон уже настроен под ваш товар.' },
  { title: 'Назовите магазин', text: 'Получите адрес вида vash-magazin.torgovlia.by. Свой домен подключите позже.' },
  { title: 'Оплатите тариф', text: 'Счёт формируется сразу. Банковский перевод, карта или ЕРИП — как удобно.' },
  { title: 'Начните продавать', text: 'Добавьте товары, включите доставку и отправьте ссылку покупателям.' },
]

const PRESET_FALLBACK: CategoryPreset[] = [
  { code: 'fish', title: 'Рыба и морепродукты', description: 'Свежая рыба, копчёности, икра', examples: ['охлаждённая рыба', 'икра'], icon: 'fish' },
  { code: 'meat', title: 'Мясо и птица', description: 'Вырезка, фарш, курица, индейка', examples: ['стейки', 'птица'], icon: 'box' },
  { code: 'flowers', title: 'Цветы и растения', description: 'Букеты, растения, подарки', examples: ['букеты', 'растения'], icon: 'heart' },
  { code: 'grocery', title: 'Продукты', description: 'Бакалея, молочное, напитки', examples: ['бакалея', 'напитки'], icon: 'cart' },
]

export default function MarketingHome() {
  const { data } = useApi<SignupCatalog>('/signup/catalog')
  const plans = data?.plans ?? []
  const categories = data?.categories?.length ? data.categories : PRESET_FALLBACK

  return (
    <MarketingShell>
      <section className="mkt-hero">
        <div className="mkt-hero__copy">
          <span className="mkt-eyebrow"><Icon name="sparkles" size={14} /> Платформа для торговых мест</span>
          <h1>Магазин для вашего товара — <em>за 5 минут</em></h1>
          <p>
            Витрина, заказы, доставка, клиенты и оплата в одном месте. Без программиста,
            без отдельного хостинга и без таблиц Excel.
          </p>
          <div className="mkt-hero__actions">
            <Link to="/start/new" className="btn btn--gold btn--lg">Создать магазин</Link>
            <a href="#tariffs" className="btn btn--ghost-light btn--lg">Смотреть тарифы</a>
          </div>
          <div className="mkt-trust">
            <span><strong>5 минут</strong> до запуска</span>
            <span><strong>77</strong> готовых сервисов</span>
            <span><strong>3</strong> тарифа без скрытых платежей</span>
          </div>
        </div>

        <div className="mkt-preview" aria-hidden="true">
          <div className="mkt-preview__top">
            <span className="mkt-preview__dot" />
            <span>vash-magazin.torgovlia.by</span>
            <span className="mkt-preview__badge">открыт</span>
          </div>
          <div className="mkt-preview__body">
            <div className="mkt-preview__brand">
              <span className="mkt-preview__logo">М</span>
              <div><strong>Мясная лавка</strong><small>свежее мясо каждый день</small></div>
            </div>
            <div className="mkt-preview__grid">
              {['Вырезка говяжья', 'Куриная грудка', 'Стейк рибай', 'Фарш домашний'].map((title, index) => (
                <div key={title} className="mkt-preview__card">
                  <span className={`mkt-preview__img mkt-preview__img--${index + 1}`} />
                  <strong>{title}</strong>
                  <small>{(14.5 + index * 9).toFixed(2)} BYN</small>
                </div>
              ))}
            </div>
            <div className="mkt-preview__order">
              <span><Icon name="check" size={14} /> Заказ №1042 принят</span>
              <strong>58.50 BYN</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="mkt-strip">
        <span>Рыба</span><span>Мясо</span><span>Цветы</span><span>Продукты</span><span>Выпечка</span><span>Одежда</span><span>Электроника</span>
      </section>

      <section id="features" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Всё для продаж</span>
          <h2>Не просто сайт, а рабочий магазин</h2>
          <p>Бесплатные функции уже в тарифе. Платные подключаются в один клик, когда понадобятся.</p>
        </header>
        <div className="mkt-features">
          {FEATURES.map((item) => (
            <article key={item.title} className="mkt-feature">
              <span className="mkt-feature__icon"><Icon name={item.icon} size={22} /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="templates" className="mkt-section mkt-section--tint">
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

      <section id="tariffs" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Тарифы</span>
          <h2>Платите за магазин, а не за функции</h2>
          <p>Первый месяц — по выбранному тарифу. Повышение и платные сервисы — после оплаты счёта.</p>
        </header>
        <div className="mkt-plans">
          {plans.map((plan, index) => (
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
          {!plans.length && <div className="mkt-loading">Загружаем тарифы…</div>}
        </div>
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

      <section id="faq" className="mkt-section">
        <header className="mkt-section__head">
          <span className="mkt-eyebrow">Вопросы</span>
          <h2>Коротко о главном</h2>
        </header>
        <div className="mkt-faq">
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
            <p>Да. В админке виден полный каталог сервисов: бесплатные включаются сразу, платные — после оплаты. Платформа может управлять сервисами централизованно.</p>
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
          <p>Создайте сайт, добавьте товары и получите первую ссылку для покупателей.</p>
        </div>
        <Link to="/start/new" className="btn btn--gold btn--lg">Создать магазин</Link>
      </section>
    </MarketingShell>
  )
}
