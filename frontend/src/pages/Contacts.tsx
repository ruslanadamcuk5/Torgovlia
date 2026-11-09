import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { assetUrl } from '../lib/api'
import { SocialLinks } from '../components/SocialLinks'
import { Icon } from '../components/icons'

export default function Contacts() {
  const { site } = useSite()
  if (!site) return null
  const s = site.settings
  const mapQuery = encodeURIComponent(s.address)
  const mapUrl = s.map_url || `https://yandex.by/maps/?text=${mapQuery}`

  return (
    <div className="contacts-page">
      <div className="page-head">
        <div className="container">
          <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Контакты</span></div>
          <div className="page-head__row">
            <div>
              <span className="eyebrow">Приходите в магазин</span>
              <h1>Контакты и адрес</h1>
              <p className="page-head__sub">Наш адрес и режим работы — ниже. Заказывайте онлайн и забирайте без очереди.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="container section">
        <div className="contacts-grid">
          <div className="contacts-card contacts-card--main">
            <span className="contacts-card__icon"><Icon name="pin" size={26} /></span>
            <h2>{s.city || 'Наш магазин'}</h2>
            {(s.market_name || s.pavilion) && <p className="contacts-card__place">{[s.market_name, s.pavilion].filter(Boolean).join(', ')}</p>}
            {s.address && <p>{s.address}</p>}
            <a href={mapUrl} target="_blank" rel="noreferrer" className="btn btn--primary"><Icon name="map" size={17} /> Построить маршрут</a>
          </div>

          <div className="contacts-card">
            <span className="contacts-card__icon"><Icon name="phone" size={24} /></span>
            <h3>Телефон</h3>
            {s.phone ? <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="contacts-card__big">{s.phone}</a> : <span className="muted">Телефон не указан</span>}
            {s.phone_secondary && <a href={`tel:${s.phone_secondary.replace(/[^\d+]/g, '')}`}>{s.phone_secondary}</a>}
            <p className="muted">Звоните в часы работы магазина</p>
          </div>

          <div className="contacts-card">
            <span className="contacts-card__icon"><Icon name="mail" size={24} /></span>
            <h3>E-mail</h3>
            <a href={`mailto:${s.email}`} className="contacts-card__big contacts-card__big--mail">{s.email}</a>
            <p className="muted">Ответим в течение рабочего дня</p>
          </div>

          <div className="contacts-card">
            <span className="contacts-card__icon"><Icon name="clock" size={24} /></span>
            <h3>Режим работы</h3>
            <ul className="hours-list hours-list--compact">
              {s.working_hours.map((day) => (
                <li key={day.weekday} className={day.closed ? 'is-closed' : ''}>
                  <span>{day.label}</span>
                  <strong>{day.closed ? 'выходной' : `${day.open}–${day.close}`}</strong>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="contacts-map">
          {s.map_embed_url ? (
            <iframe title="Карта" src={s.map_embed_url} loading="lazy" referrerPolicy="no-referrer-when-downgrade" />
          ) : (
            <div className="map-placeholder">
              <div className="map-placeholder__grid" />
              <div className="map-placeholder__pin"><Icon name="pin" size={30} /></div>
              <div className="map-placeholder__card">
                <strong>{s.market_name}</strong>
                <span>{s.address}</span>
                <a href={mapUrl} target="_blank" rel="noreferrer">Открыть в Яндекс.Картах <Icon name="external" size={15} /></a>
              </div>
            </div>
          )}
        </div>

        <div className="contacts-bottom">
          <div className="panel">
            <h2>Мы в соцсетях</h2>
            <p>Публикуем новые поступления, советы и акции магазина.</p>
            <SocialLinks socials={s.socials} variant="hero" />
          </div>

          <div className="panel">
            <h2>Реквизиты</h2>
            <div className="requisites-list">
              <div><span>Продавец</span><strong>{s.legal_name}</strong></div>
              <div><span>УНП</span><strong>{s.unp}</strong></div>
              <div><span>Адрес</span><strong>{s.legal_address || s.address}</strong></div>
              <div><span>Телефон</span><strong>{s.phone}</strong></div>
              <div><span>E-mail</span><strong>{s.email}</strong></div>
            </div>
            <p className="muted">
              Свидетельство о государственной регистрации индивидуального предпринимателя предоставляется по запросу.
              Информация на сайте не является публичной офертой.
            </p>
          </div>

          <div className="panel panel--qr">
            <h2>QR-код сайта</h2>
            <p>Наведите камеру телефона — откроется сайт с каталогом и оформлением заказа.</p>
            <img src={assetUrl('/api/qr/site.png?size=400')} alt={`QR-код сайта ${s.brand_name}`} />
            <a href="/api/qr/site.png?size=1000&download=1" className="btn btn--outline btn--sm" download>
              <Icon name="download" size={16} /> Скачать PNG
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
