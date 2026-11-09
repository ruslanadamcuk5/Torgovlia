import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { MarkdownText } from '../components/MarkdownText'
import { Icon } from '../components/icons'

export default function Pickup() {
  const { site } = useSite()
  if (!site) return null
  const s = site.settings

  return (
    <div className="pickup-page">
      <div className="page-head">
        <div className="container">
          <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Как забрать</span></div>
          <div className="page-head__row">
            <div>
              <span className="eyebrow">Самовывоз · без предоплаты</span>
              <h1>Как забрать заказ</h1>
              <p className="page-head__sub">Оформите заказ онлайн и заберите его в магазине или оформите доставку, если она доступна.</p>
            </div>
            <div className="page-head__badge page-head__badge--gold">
              <Icon name="pin" size={20} />
              <span>{s.address || [s.city, s.market_name, s.pavilion].filter(Boolean).join(', ') || 'Адрес магазина'}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="container section">
        <div className="pickup-steps">
          <div className="pickup-step">
            <span className="pickup-step__num">01</span>
            <h3>Соберите корзину</h3>
            <p>Выберите товары в каталоге. Для весового товара укажите нужное количество.</p>
          </div>
          <div className="pickup-step">
            <span className="pickup-step__num">02</span>
            <h3>Выберите время</h3>
            <p>Доступны интервалы каждые {s.slot_step_minutes} минут в часы работы магазина. Заказ можно оформить на {s.booking_days_ahead} дней вперёд.</p>
          </div>
          <div className="pickup-step">
            <span className="pickup-step__num">03</span>
            <h3>Подтвердите телефон</h3>
            <p>Код из SMS подтверждает номер. Это нужно, чтобы мы могли связаться с вами по заказу.</p>
          </div>
          <div className="pickup-step">
            <span className="pickup-step__num">04</span>
            <h3>Заберите и оплатите</h3>
            <p>Назовите номер заказа в магазине. Оплата наличными или картой при получении.</p>
          </div>
        </div>

        <div className="pickup-layout">
          <article className="panel legal-body">
            <MarkdownText text={s.pickup_rules} />
          </article>

          <aside className="pickup-side">
            <div className="panel">
              <h3><Icon name="pin" size={19} /> Адрес</h3>
              <p>{s.address}</p>
              <div className="pickup-side__row"><Icon name="clock" size={17} /><span>Сегодня: {site.today.is_closed ? 'выходной' : `${site.today.open}–${site.today.close}`}</span></div>
              <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--primary btn--block"><Icon name="phone" size={17} /> {s.phone}</a>
              {s.map_url && <a href={s.map_url} target="_blank" rel="noreferrer" className="btn btn--outline btn--block">Открыть на карте <Icon name="external" size={16} /></a>}
            </div>

            <div className="panel panel--soft">
              <h3>Часы работы</h3>
              <ul className="hours-list">
                {s.working_hours.map((day) => (
                  <li key={day.weekday} className={day.closed ? 'is-closed' : ''}>
                    <span>{day.label}</span>
                    <strong>{day.closed ? 'выходной' : `${day.open}–${day.close}`}</strong>
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel panel--accent">
              <h3><Icon name="wallet" size={19} /> Оплата</h3>
              <p>{s.payment_note}</p>
              <p className="muted">Минимальная сумма заказа — {s.min_order_amount.toFixed(2).replace('.', ',')} BYN.</p>
            </div>
          </aside>
        </div>

        <div className="pickup-cta">
          <div>
            <h2>Готовы сделать заказ?</h2>
            <p>Ассортимент обновляется каждый день. Оформление бесплатное.</p>
          </div>
          <div className="row">
            <Link to="/catalog" className="btn btn--gold btn--lg">В каталог</Link>
            <Link to="/lookup" className="btn btn--ghost-light btn--lg">Найти заказ</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
