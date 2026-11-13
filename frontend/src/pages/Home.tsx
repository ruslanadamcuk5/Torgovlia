import { Link } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { assetUrl } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { Advantage, ArticleShort, Product } from '../lib/types'
import { ProductCard } from '../components/ProductCard'
import { SocialLinks } from '../components/SocialLinks'
import { Icon, type IconName } from '../components/icons'
import { Loader } from '../components/ui'
import { humanDate, unitShort, formatMoney } from '../lib/format'

interface Promotions {
  daily_deal: Product | null
  discounts: Product[]
  banners: { id: string; title: string; subtitle: string; image_url: string; link: string; button_text: string }[]
}

const ICON_MAP: Record<string, IconName> = {
  fish: 'fish', shield: 'shield', clock: 'clock', scissors: 'scissors', star: 'star',
  heart: 'heart', scale: 'scale', wallet: 'wallet',
}

const STEPS = [
  { title: 'Выберите товары', text: 'Откройте каталог и добавьте нужные позиции. Для товара на вес укажите желаемое количество.' },
  { title: 'Соберите заказ', text: 'Проверьте состав корзины и сумму. Предоплата не нужна — оплата только при получении.' },
  { title: 'Подтвердите телефон', text: 'Пришлём SMS с кодом. Так мы знаем, кому и когда готовить заказ.' },
  { title: 'Заберите заказ', text: 'Приходите к выбранному времени по адресу магазина. Соберём и упакуем заказ к вашему приходу.' },
]

export default function Home() {
  const { site } = useSite()
  const hybridMode = site?.tenant?.business_type === 'hybrid'
  const { data: featured } = useApi<{ items: Product[] }>('/products?limit=8', false)
  const { data: services } = useApi<{ items: Product[] }>(hybridMode ? '/services?limit=4' : null, false)
  const { data: promos } = useApi<Promotions>('/promotions', false)
  const { data: articlesData } = useApi<{ items: ArticleShort[] }>('/articles', false)

  if (!site) return <Loader />
  const s = site.settings
  const daily = promos?.daily_deal
  const banners = (promos?.banners ?? s.banners.filter((banner) => banner.is_active)).slice(0, 2)

  return (
    <>
      <section className="hero">
        <div className="container hero__grid">
          <div className="hero__content">
            <span className="eyebrow">{s.hero_badge}</span>

            <div className="hero__place">
              <span className="hero__place-label">Наш магазин</span>
              <strong className="hero__city">{s.city || s.brand_name}</strong>
              {s.market_name && <span className="hero__market">{s.market_name}</span>}
              {s.pavilion && <span className="hero__pavilion"><Icon name="pin" size={17} /> {s.pavilion}</span>}
            </div>

            <h1 className="hero__title">{s.hero_title}</h1>
            <p className="hero__lead">{s.hero_subtitle}</p>

            <div className="hero__actions">
              <Link to="/catalog" className="btn btn--primary btn--lg">
                Перейти в каталог <Icon name="arrow-right" size={18} />
              </Link>
              <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--outline btn--lg">
                <Icon name="phone" size={18} /> Позвонить
              </a>
            </div>

            <div className="hero__socials">
              <div className="hero__socials-head">
                <span className="hero__socials-label">Мы в соцсетях</span>
                <span className="hero__socials-note">Новости, поступления и жизнь магазина</span>
              </div>
              <SocialLinks socials={s.socials} />
            </div>

            <div className="hero__note">
              <span><Icon name="check" size={16} /> {s.hero_note}</span>
              <span>
                <Icon name="clock" size={16} />
                {site.today.is_closed
                  ? 'Сегодня выходной'
                  : `Сегодня ${site.today.open}–${site.today.close}`}
              </span>
            </div>
          </div>

          <div className="hero__visual">
            <div className="hero__image-wrap">
              <img src={assetUrl(s.hero_image_url)} alt="Витрина магазина" className="hero__image" />
            </div>
            <div className="hero__float hero__float--top">
              <span className="hero__float-icon"><Icon name="sparkles" size={20} /></span>
              <div><strong>Новые поступления</strong><span>каждую неделю</span></div>
            </div>
            <div className="hero__float hero__float--bottom">
              <span className="hero__float-icon hero__float-icon--gold"><Icon name="wallet" size={20} /></span>
              <div><strong>Без предоплаты</strong><span>оплата при получении</span></div>
            </div>
            <div className="hero__stamp">
              <span>заказ</span>
              <strong>24/7</strong>
              <span>на сайте</span>
            </div>
          </div>
        </div>
      </section>

      <section className="advantage-strip">
        <div className="container advantage-strip__grid">
          {s.advantages.map((item: Advantage) => (
            <div className="advantage" key={item.title}>
              <span className="advantage__icon"><Icon name={ICON_MAP[item.icon] ?? 'tag'} size={24} /></span>
              <div>
                <strong>{item.title}</strong>
                <p>{item.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {banners.length > 0 && (
        <section className="section section--tight">
          <div className="container">
            <div className="banner-grid">
              {banners.map((banner, index) => (
                <article
                  key={banner.id}
                  className={`banner-card ${index === 0 ? 'banner-card--wide' : ''}`}
                  style={banner.image_url ? { backgroundImage: `linear-gradient(100deg, rgba(6,32,39,.92), rgba(6,32,39,.35)), url(${assetUrl(banner.image_url)})` } : undefined}
                >
                  <div className="banner-card__content">
                    <span className="banner-card__tag"><Icon name="sparkles" size={15} /> Акция магазина</span>
                    <h3>{banner.title}</h3>
                    <p>{banner.subtitle}</p>
                    <Link to={banner.link || '/catalog'} className="btn btn--light btn--sm">
                      {banner.button_text || 'Смотреть'} <Icon name="arrow-right" size={16} />
                    </Link>
                  </div>
                  {!banner.image_url && (
                    <span className="banner-card__decor"><Icon name="grid" size={120} /></span>
                  )}
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      {(daily || (promos?.discounts.length ?? 0) > 0) && (
        <section className="section section--promo">
          <div className="container">
            <div className="section__head">
              <div>
                <span className="eyebrow">Выгодно сегодня</span>
                <h2>Акции и товар дня</h2>
              </div>
              <Link to="/catalog" className="link-arrow">Весь каталог <Icon name="arrow-right" size={17} /></Link>
            </div>

            {daily && (
              <article className="daily-deal">
                <div className="daily-deal__media">
                  {daily.image_url ? <img src={assetUrl(daily.image_url)} alt={daily.title} /> : <Icon name="image" size={90} />}
                  <span className="daily-deal__badge"><Icon name="star" size={15} /> Товар дня</span>
                </div>
                <div className="daily-deal__content">
                  <span className="daily-deal__kicker">Специальная цена до конца дня</span>
                  <h3>{daily.title}</h3>
                  <p>{daily.short_description}</p>
                  <div className="daily-deal__price">
                    <strong>{formatMoney(daily.final_price)}</strong>
                    <span>/ {unitShort(daily.unit)}</span>
                    {daily.discount_percent > 0 && <s>{formatMoney(daily.price)}</s>}
                  </div>
                  <div className="daily-deal__actions">
                    <Link to={`/fish/${daily.slug}`} className="btn btn--primary">
                      Перейти к товару <Icon name="arrow-right" size={17} />
                    </Link>
                    <Link to="/pickup" className="btn btn--ghost">
                      <Icon name="info" size={17} /> Как забрать
                    </Link>
                  </div>
                </div>
              </article>
            )}

            {(promos?.discounts.length ?? 0) > 0 && (
              <div className="product-grid product-grid--four">
                {promos!.discounts.slice(0, 4).map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      <section className="section">
        <div className="container">
          <div className="section__head">
            <div>
              <span className="eyebrow">Каталог магазина</span>
              <h2>Популярные товары</h2>
              <p className="section__sub">Наличие обновляется продавцом в течение дня. Если позиции нет — включите фильтр «только в наличии» или свяжитесь с нами.</p>
            </div>
            <Link to="/catalog" className="link-arrow">Смотреть всё <Icon name="arrow-right" size={17} /></Link>
          </div>

          {featured ? (
            <div className="product-grid">
              {featured.items.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          ) : (
            <Loader />
          )}
        </div>
      </section>

      {hybridMode && (services?.items.length ?? 0) > 0 && (
        <section className="section section--tight">
          <div className="container">
            <div className="section__head">
              <div>
                <span className="eyebrow">Ещё и услуги</span>
                <h2>Запись к специалистам</h2>
                <p className="section__sub">Помимо товаров можно записаться на услугу и выбрать удобное время.</p>
              </div>
              <Link to="/services" className="link-arrow">Все услуги <Icon name="arrow-right" size={17} /></Link>
            </div>
            <div className="product-grid product-grid--four">
              {services!.items.map((service) => (
                <ProductCard key={service.id} product={service} />
              ))}
            </div>
            <div className="steps-cta">
              <Link to="/booking" className="btn btn--primary">
                <Icon name="calendar" size={17} /> Записаться онлайн
              </Link>
            </div>
          </div>
        </section>
      )}

      <section className="section section--steps">
        <div className="container">
          <div className="steps-head">
            <span className="eyebrow">Просто и без предоплаты</span>
            <h2>Как сделать заказ</h2>
            <p>Выбираете товары на сайте и забираете заказ в магазине или оформляете доставку, если она доступна.</p>
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
            <Link to="/catalog" className="btn btn--primary btn--lg">Выбрать товары <Icon name="arrow-right" size={18} /></Link>
            <Link to="/pickup" className="btn btn--outline btn--lg">Правила самовывоза</Link>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container about-grid">
          <div className="about__text">
            <span className="eyebrow">О магазине</span>
            <h2>{s.about_title}</h2>
            {s.about_text.split('\n\n').slice(0, 3).map((paragraph) => (
              <p key={paragraph.slice(0, 24)}>{paragraph}</p>
            ))}
            <div className="about__facts">
              <div><strong>{site.products_count}</strong><span>позиций в каталоге</span></div>
              <div><strong>{s.booking_days_ahead}</strong><span>дней вперёд можно заказать</span></div>
              <div><strong>{s.min_order_amount.toFixed(0)} BYN</strong><span>минимальная сумма заказа</span></div>
            </div>
            <Link to="/contacts" className="link-arrow">Как нас найти <Icon name="arrow-right" size={17} /></Link>
          </div>

          <aside className="hours-card">
            <div className="hours-card__head">
              <span className="hours-card__icon"><Icon name="clock" size={22} /></span>
              <div>
                <strong>Режим работы</strong>
                <span>{[s.market_name, s.pavilion].filter(Boolean).join(', ') || 'График магазина'}</span>
              </div>
            </div>
            <ul className="hours-card__list">
              {s.working_hours.map((day) => {
                const isToday = day.weekday === new Date().getDay() - (new Date().getDay() === 0 ? -6 : 1)
                return (
                  <li key={day.weekday} className={day.closed ? 'is-closed' : ''}>
                    <span>{day.label}</span>
                    <strong>{day.closed ? 'выходной' : `${day.open}–${day.close}`}</strong>
                  </li>
                )
              })}
            </ul>
            {s.address && (
              <div className="hours-card__foot">
                <Icon name="pin" size={16} />
                <span>{s.address}</span>
              </div>
            )}
            {s.phone && (
              <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--primary btn--block">
                <Icon name="phone" size={17} /> {s.phone}
              </a>
            )}
          </aside>
        </div>
      </section>

      <section className="section section--articles">
        <div className="container">
          <div className="section__head">
            <div>
              <span className="eyebrow">Полезно знать</span>
              <h2>Полезные статьи</h2>
              <p className="section__sub">Как выбрать, использовать и ухаживать — коротко и по делу.</p>
            </div>
            <Link to="/articles" className="link-arrow">Все статьи <Icon name="arrow-right" size={17} /></Link>
          </div>
          <div className="article-grid">
            {articlesData?.items.slice(0, 3).map((article) => (
              <Link to={`/fish/${article.slug}`} className="article-card" key={article.slug}>
                <div className="article-card__media">
                  {article.image_url ? <img src={assetUrl(article.image_url)} alt={article.title} loading="lazy" /> : <Icon name="book" size={40} />}
                  <span className="article-card__time"><Icon name="clock" size={14} /> {article.reading_minutes} мин</span>
                </div>
                <div className="article-card__body">
                  {article.category && <span className="article-card__cat">{article.category}</span>}
                  <h3>{article.title}</h3>
                  <p>{article.short_description}</p>
                  <span className="link-arrow">Читать статью <Icon name="arrow-right" size={16} /></span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="app-promo">
            <div className="app-promo__content">
              <span className="eyebrow eyebrow--light">Android · iOS · PWA</span>
              <h2>Приложение «{s.brand_name}»</h2>
              <p>
                Каталог, заказы и история покупок — в приложении. Устанавливается в один клик
                на Android или через Safari на iPhone и iPad.
              </p>
              <ul className="app-promo__list">
                <li><Icon name="check" size={17} /> Статус заказа и история покупок</li>
                <li><Icon name="check" size={17} /> Быстрое повторение прошлого заказа</li>
                <li><Icon name="check" size={17} /> Работает как обычное приложение на Android и iPhone</li>
              </ul>
              <div className="app-promo__actions">
                <Link to="/app" className="btn btn--gold">Установить приложение <Icon name="download" size={17} /></Link>
                <Link to="/app" className="btn btn--ghost-light">Подробнее</Link>
              </div>
            </div>
            <div className="app-promo__visual">
              <div className="phone-mock">
                <div className="phone-mock__notch" />
                <div className="phone-mock__screen">
                  <img src="/assets/logo.svg" alt="" width={42} height={42} />
                  <strong>{s.brand_name}</strong>
                  <span>{s.city || 'Онлайн-витрина'}</span>
                  <div className="phone-mock__card">
                    <span>Товар дня</span>
                    <strong>{daily?.title ?? 'Новые поступления'}</strong>
                    <small>{daily ? formatMoney(daily.final_price) : 'Каждый день'}</small>
                  </div>
                  <div className="phone-mock__btn">Сделать заказ</div>
                </div>
              </div>
              <a className="app-qr" href="/api/qr/site.png?size=640" target="_blank" rel="noreferrer">
                <img src={assetUrl('/api/qr/site.png?size=320')} alt="QR-код на сайт" />
                <span>Наведите камеру,<br />чтобы открыть сайт</span>
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--faq">
        <div className="container faq-grid">
          <div>
            <span className="eyebrow">Вопросы</span>
            <h2>Коротко о главном</h2>
            <p className="section__sub">Если не нашли ответ — позвоните в магазин, поможем выбрать.</p>
            {s.phone && <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`} className="btn btn--outline"><Icon name="phone" size={17} /> {s.phone}</a>}
          </div>
          <div className="faq">
            {[
              { q: 'Есть ли доставка?', a: 'Условия доставки зависят от настроек магазина. Если доставка недоступна, заказ можно забрать в торговой точке. Оплата при получении.' },
              { q: 'Нужна ли предоплата?', a: 'Нет. Вы оплачиваете заказ при получении наличными или картой. Оформление заказа бесплатное.' },
              { q: 'Можно ли заказать без регистрации?', a: 'Да. Достаточно указать имя и подтвердить номер телефона кодом из SMS. Зарегистрированные покупатели видят историю заказов.' },
              { q: 'Почему цена за вес может отличаться?', a: 'Стоимость весового товара рассчитывается по фактическому весу при выдаче. Отклонение обычно не превышает ±5%.' },
              { q: 'Что если товар закончился?', a: 'Мы обновляем наличие в течение дня. Если позиция закончилась, продавец свяжется с вами и предложит замену или отменит заказ.' },
            ].map((item) => (
              <details key={item.q} className="faq__item">
                <summary>{item.q}<Icon name="chevron-down" size={19} /></summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--contact-cta">
        <div className="container contact-cta">
          <span className="eyebrow eyebrow--light">Ждём вас</span>
          <h2>Ждём вас в магазине</h2>
          <p className="contact-cta__place">{s.address || [s.city, s.market_name, s.pavilion].filter(Boolean).join(', ')}</p>
          <div className="contact-cta__row">
            <span><Icon name="clock" size={18} /> Сегодня: {site.today.is_closed ? 'выходной' : `${site.today.open}–${site.today.close}`}</span>
            {s.phone && <span><Icon name="phone" size={18} /> {s.phone}</span>}
            {s.email && <span><Icon name="mail" size={18} /> {s.email}</span>}
          </div>
          <div className="contact-cta__actions">
            <Link to="/catalog" className="btn btn--gold btn--lg">Перейти в каталог</Link>
            <Link to="/contacts" className="btn btn--ghost-light btn--lg">Контакты и схема</Link>
          </div>
        </div>
      </section>
    </>
  )
}
