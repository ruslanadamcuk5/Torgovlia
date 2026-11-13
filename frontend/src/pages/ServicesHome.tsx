import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { assetUrl } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { Category, Product, Specialist } from '../lib/types'
import { ProductCard } from '../components/ProductCard'
import { Icon } from '../components/icons'
import { Loader } from '../components/ui'

const STEPS = [
  {
    icon: 'calendar' as const,
    title: 'Выберите услугу',
    text: 'Откройте каталог услуг: цена и длительность видны сразу, без звонков и уточнений.',
  },
  {
    icon: 'users' as const,
    title: 'Выберите специалиста',
    text: 'Можно записаться к конкретному мастеру или доверить выбор свободному специалисту.',
  },
  {
    icon: 'clock' as const,
    title: 'Найдите свободное время',
    text: 'Календарь показывает реальные окна с учётом графика, длительности и занятости.',
  },
  {
    icon: 'check' as const,
    title: 'Подтвердите запись',
    text: 'Оставьте имя и телефон — номер записи придёт на экран. Отменить можно на сайте.',
  },
]

function durationLabel(minutes: number): string {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
}

export default function ServicesHome() {
  const { site } = useSite()
  const { data: services } = useApi<{ items: Product[] }>('/services?limit=12', false)
  const { data: categories } = useApi<Category[]>('/categories', false)
  const { data: specialists } = useApi<{ items: Specialist[] }>('/specialists', false)

  if (!site) return <Loader />
  const s = site.settings

  return (
    <>
      <section className="hero hero--service">
        <div className="container hero__grid">
          <div className="hero__content">
            <span className="eyebrow">{s.hero_badge || 'Онлайн-запись · Свободное время'}</span>

            <div className="hero__place">
              <span className="hero__place-label">Мы рядом</span>
              <strong className="hero__city">{s.city || s.brand_name}</strong>
              {s.address && <span className="hero__pavilion"><Icon name="pin" size={17} /> {s.address}</span>}
            </div>

            <h1 className="hero__title">{s.hero_title}</h1>
            <p className="hero__lead">{s.hero_subtitle}</p>

            <div className="hero__actions">
              <Link to="/booking" className="btn btn--primary btn--lg">
                <Icon name="calendar" size={18} /> Записаться онлайн
              </Link>
              <Link to="/services" className="btn btn--outline btn--lg">
                Услуги и цены <Icon name="arrow-right" size={18} />
              </Link>
            </div>

            <div className="hero__note">
              <span><Icon name="check" size={16} /> {s.hero_note || 'Без звонков и очередей'}</span>
              <span>
                <Icon name="clock" size={16} />
                {site.today.is_closed
                  ? 'Сегодня выходной'
                  : `Сегодня ${site.today.open}–${site.today.close}`}
              </span>
            </div>
          </div>

          <div className="hero__visual hero__visual--service">
            <div className="booking-teaser">
              <div className="booking-teaser__head">
                <span className="booking-teaser__badge"><Icon name="calendar" size={16} /> Ближайшая запись</span>
                <strong>Свободное время</strong>
              </div>
              <div className="booking-teaser__grid">
                {['09:30', '11:00', '12:30', '14:00', '15:30', '17:00'].map((time, index) => (
                  <span key={time} className={index === 2 ? 'is-active' : ''}>{time}</span>
                ))}
              </div>
              <div className="booking-teaser__foot">
                <span><Icon name="users" size={16} /> {specialists?.items.length ?? 3} специалиста</span>
                <span><Icon name="clock" size={16} /> {durationLabel(60)}</span>
              </div>
            </div>
            <div className="hero__float hero__float--top">
              <span className="hero__float-icon"><Icon name="check" size={20} /></span>
              <div><strong>Подтверждение сразу</strong><span>номер записи на экране</span></div>
            </div>
            <div className="hero__float hero__float--bottom">
              <span className="hero__float-icon hero__float-icon--gold"><Icon name="clock" size={20} /></span>
              <div><strong>Без ожидания</strong><span>приходите ко времени</span></div>
            </div>
          </div>
        </div>
      </section>

      {s.advantages.length > 0 && (
        <section className="advantage-strip">
          <div className="container advantage-strip__grid">
            {s.advantages.slice(0, 4).map((item) => (
              <div className="advantage" key={item.title}>
                <span className="advantage__icon"><Icon name="sparkles" size={24} /></span>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {(categories?.length ?? 0) > 0 && (
        <section className="section section--tight">
          <div className="container">
            <div className="section__head">
              <div>
                <span className="eyebrow">Направления</span>
                <h2>Что можно записать</h2>
              </div>
              <Link to="/services" className="link-arrow">Все услуги <Icon name="arrow-right" size={17} /></Link>
            </div>
            <div className="service-category-grid">
              {categories!.slice(0, 8).map((category) => (
                <Link key={category.id} to={`/services?category=${category.slug}`} className="service-category">
                  <span className="service-category__icon"><Icon name="sparkles" size={22} /></span>
                  <div>
                    <strong>{category.title}</strong>
                    <span>{category.products_count} услуг</span>
                  </div>
                  <Icon name="chevron-right" size={18} />
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="section">
        <div className="container">
          <div className="section__head">
            <div>
              <span className="eyebrow">Каталог услуг</span>
              <h2>Популярное у клиентов</h2>
              <p className="section__sub">Цена и длительность указаны заранее. Выберите услугу — покажем свободное время.</p>
            </div>
            <Link to="/services" className="link-arrow">Все услуги <Icon name="arrow-right" size={17} /></Link>
          </div>
          {services ? (
            services.items.length ? (
              <div className="product-grid product-grid--four">
                {services.items.slice(0, 8).map((service) => (
                  <ProductCard key={service.id} product={service} />
                ))}
              </div>
            ) : (
              <div className="notice">
                <Icon name="info" size={18} />
                <span>Услуги скоро появятся. Позвоните нам — подберём время вручную.</span>
              </div>
            )
          ) : (
            <Loader />
          )}
        </div>
      </section>

      <section className="section section--steps">
        <div className="container">
          <div className="steps-head">
            <span className="eyebrow">Четыре шага</span>
            <h2>Как записаться онлайн</h2>
            <p>Запись занимает меньше минуты. Никаких звонков и переписок — только свободное время и подтверждение.</p>
          </div>
          <div className="steps">
            {STEPS.map((step, index) => (
              <div className="step" key={step.title}>
                <span className="step__num">{String(index + 1).padStart(2, '0')}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
            ))}
          </div>
          <div className="steps-cta">
            <Link to="/booking" className="btn btn--primary btn--lg">
              <Icon name="calendar" size={18} /> Выбрать время
            </Link>
            <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--outline btn--lg">
              <Icon name="phone" size={18} /> {s.phone || 'Позвонить'}
            </a>
          </div>
        </div>
      </section>

      {(specialists?.items.length ?? 0) > 0 && (
        <section className="section">
          <div className="container">
            <div className="section__head">
              <div>
                <span className="eyebrow">Команда</span>
                <h2>Наши специалисты</h2>
                <p className="section__sub">Можно выбрать конкретного мастера или записаться к первому свободному.</p>
              </div>
            </div>
            <div className="specialist-grid">
              {specialists!.items.slice(0, 6).map((person) => (
                <article className="specialist-card" key={person.id}>
                  <div className="specialist-card__photo">
                    {person.photo_url ? (
                      <img src={assetUrl(person.photo_url)} alt={person.name} loading="lazy" />
                    ) : (
                      <span>{person.name.slice(0, 1)}</span>
                    )}
                  </div>
                  <div className="specialist-card__body">
                    <h3>{person.name}</h3>
                    <span className="specialist-card__role">{person.role}</span>
                    {person.bio && <p>{person.bio}</p>}
                    {person.services.length > 0 && (
                      <div className="specialist-card__services">
                        {person.services.slice(0, 3).map((service) => (
                          <span key={service.id}>{service.title}</span>
                        ))}
                      </div>
                    )}
                    <Link to={`/booking?specialist=${person.id}`} className="link-arrow">
                      Записаться <Icon name="arrow-right" size={16} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="section">
        <div className="container about-grid">
          <div className="about__text">
            <span className="eyebrow">О нас</span>
            <h2>{s.about_title}</h2>
            {s.about_text.split('\n\n').slice(0, 3).map((paragraph) => (
              <p key={paragraph.slice(0, 24)}>{paragraph}</p>
            ))}
            <div className="about__facts">
              <div><strong>{site.products_count}</strong><span>услуг в каталоге</span></div>
              <div><strong>{specialists?.items.length ?? 0}</strong><span>специалистов</span></div>
              <div><strong>{s.booking_days_ahead}</strong><span>дней вперёд открыта запись</span></div>
            </div>
            <Link to="/contacts" className="link-arrow">Как нас найти <Icon name="arrow-right" size={17} /></Link>
          </div>

          <aside className="hours-card">
            <div className="hours-card__head">
              <span className="hours-card__icon"><Icon name="clock" size={22} /></span>
              <div>
                <strong>Режим работы</strong>
                <span>{s.address || 'График заведения'}</span>
              </div>
            </div>
            <ul className="hours-card__list">
              {s.working_hours.map((day) => (
                <li key={day.weekday} className={day.closed ? 'is-closed' : ''}>
                  <span>{day.label}</span>
                  <strong>{day.closed ? 'выходной' : `${day.open}–${day.close}`}</strong>
                </li>
              ))}
            </ul>
            {s.phone && (
              <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--primary btn--block">
                <Icon name="phone" size={17} /> {s.phone}
              </a>
            )}
          </aside>
        </div>
      </section>

      <section className="section section--contact-cta">
        <div className="container contact-cta">
          <span className="eyebrow eyebrow--light">Запись открыта</span>
          <h2>Выберите удобное время</h2>
          <p className="contact-cta__place">{s.address || [s.city, s.address].filter(Boolean).join(', ')}</p>
          <div className="contact-cta__row">
            <span><Icon name="clock" size={18} /> Сегодня: {site.today.is_closed ? 'выходной' : `${site.today.open}–${site.today.close}`}</span>
            {s.phone && <span><Icon name="phone" size={18} /> {s.phone}</span>}
            {s.email && <span><Icon name="mail" size={18} /> {s.email}</span>}
          </div>
          <div className="contact-cta__actions">
            <Link to="/booking" className="btn btn--gold btn--lg">Записаться онлайн</Link>
            <Link to="/contacts" className="btn btn--ghost-light btn--lg">Контакты</Link>
          </div>
        </div>
      </section>
    </>
  )
}
