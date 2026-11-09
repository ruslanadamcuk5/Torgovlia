import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { storefrontBase, useSite } from '../../store/SettingsContext'
import { useToast } from '../../store/ToastContext'
import { ImageUpload } from '../../components/ImageUpload'
import { TemplatePreview } from '../../components/TemplatePreview'
import { ACCENT_OPTIONS } from '../../lib/theme'
import { Loader, Spinner, Tabs } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Advantage, Banner, DesignTemplate, Settings, WorkingDay } from '../../lib/types'

const TABS = [
  { id: 'brand', label: 'Бренд и реквизиты' },
  { id: 'design', label: 'Дизайн' },
  { id: 'hero', label: 'Главная' },
  { id: 'contacts', label: 'Адрес и контакты' },
  { id: 'hours', label: 'Режим работы' },
  { id: 'blocks', label: 'Баннеры и преимущества' },
  { id: 'booking', label: 'Заказы' },
  { id: 'legal', label: 'Документы' },
  { id: 'app', label: 'Приложение' },
  { id: 'seo', label: 'SEO и аналитика' },
]

const ICON_OPTIONS = [
  ['tag', 'Товары'], ['shield', 'Гарантия'], ['clock', 'Время'], ['scissors', 'Сервис'],
  ['star', 'Звезда'], ['heart', 'Сердце'], ['scale', 'Весы'], ['wallet', 'Оплата'],
]

export default function SettingsAdmin() {
  const { toast } = useToast()
  const { refresh } = useSite()
  const { data, loading, reload } = useApi<{ settings: Settings; updated_at: string | null }>('/admin/settings')
  const { data: templates } = useApi<DesignTemplate[]>('/templates')
  const [tab, setTab] = useState('brand')
  const [form, setForm] = useState<Settings | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (data?.settings) setForm(JSON.parse(JSON.stringify(data.settings)) as Settings)
  }, [data])

  if (loading || !form) return <Loader label="Загружаем настройки сайта…" />

  const set = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  const save = async () => {
    setBusy(true)
    try {
      await api('/admin/settings', { method: 'PUT', body: form })
      toast('Настройки сайта сохранены')
      await refresh()
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось сохранить настройки', 'error')
    } finally {
      setBusy(false)
    }
  }

  const updateDay = (index: number, patch: Partial<WorkingDay>) => {
    const next = form.working_hours.map((day, dayIndex) => (dayIndex === index ? { ...day, ...patch } : day))
    set('working_hours', next)
  }

  const addBanner = () => {
    const banner: Banner = {
      id: `banner-${Date.now()}`,
      title: 'Новый баннер',
      subtitle: '',
      image_url: '',
      link: '/catalog',
      button_text: 'Смотреть каталог',
      is_active: true,
    }
    set('banners', [...form.banners, banner])
  }

  const updateBanner = (index: number, patch: Partial<Banner>) => {
    set('banners', form.banners.map((banner, bannerIndex) => (bannerIndex === index ? { ...banner, ...patch } : banner)))
  }

  const addAdvantage = () => {
    const advantage: Advantage = { icon: 'tag', title: 'Новое преимущество', text: '' }
    set('advantages', [...form.advantages, advantage])
  }

  const publicBase = storefrontBase()

  return (
    <div className="admin-page settings-admin">
      <div className="settings-head">
        <div>
          <h2>Настройки сайта</h2>
          <p>Реквизиты продавца, контакты, тексты и параметры заказов. Изменения сразу видны покупателям.</p>
        </div>
        <div className="settings-head__actions">
          {data?.updated_at && <span className="muted">Сохранено {new Date(data.updated_at).toLocaleString('ru-BY')}</span>}
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
            {busy ? <Spinner size={17} /> : <Icon name="check" size={17} />} Сохранить настройки
          </button>
        </div>
      </div>

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      <div className="settings-grid">
        <div className="settings-main">
          {tab === 'brand' && (
            <>
              <section className="panel">
                <div className="panel__head"><h3>Название и позиционирование</h3></div>
                <div className="form-grid">
                  <label className="field"><span className="field__label">Название магазина</span><input className="input" value={form.brand_name} onChange={(event) => set('brand_name', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Короткий слоган</span><input className="input" value={form.tagline} onChange={(event) => set('tagline', event.target.value)} /></label>
                </div>
                <label className="field"><span className="field__label">Юридическое наименование продавца</span><input className="input" value={form.legal_name} onChange={(event) => set('legal_name', event.target.value)} /></label>
                <div className="form-grid">
                  <label className="field"><span className="field__label">УНП</span><input className="input" value={form.unp} onChange={(event) => set('unp', event.target.value)} placeholder="9 цифр" /></label>
                  <label className="field"><span className="field__label">Юридический адрес</span><input className="input" value={form.legal_address} onChange={(event) => set('legal_address', event.target.value)} placeholder="г. Барановичи, …" /></label>
                </div>
                <p className="field__hint">Эти данные показываются в подвале сайта, документах и на странице контактов.</p>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Логотип и иконка</h3></div>
                <ImageUpload value={form.logo_url} onChange={(value) => set('logo_url', value)} label="Логотип" aspect="square" hint="SVG или PNG с прозрачным фоном. Используется в шапке и приложении." />
                <ImageUpload value={form.favicon_url} onChange={(value) => set('favicon_url', value)} label="Favicon" aspect="square" hint="Небольшая иконка для вкладки браузера." />
              </section>
            </>
          )}

          {tab === 'design' && (
            <>
              <section className="panel">
                <div className="panel__head">
                  <h3>Живой предпросмотр</h3>
                  <span className="muted">{templates?.find((item) => item.code === form.template)?.title ?? form.template}</span>
                </div>
                <p className="muted">
                  Так будет выглядеть главная страница с вашими названием, текстами и фото.
                  Нажмите на карточку шаблона ниже — предпросмотр обновится сразу, без сохранения.
                </p>
                <TemplatePreview
                  template={templates?.find((item) => item.code === form.template) ?? null}
                  accent={form.accent_color}
                  brand={form.brand_name}
                  tagline={form.tagline}
                  heroBadge={form.hero_badge}
                  heroTitle={form.hero_title}
                  heroSubtitle={form.hero_subtitle}
                  phone={form.phone}
                  logo={form.logo_url}
                  heroImage={form.hero_image_url}
                />
              </section>

              <section className="panel">
                <div className="panel__head">
                  <h3>Акцентный цвет</h3>
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => set('accent_color', '')}>
                    Как в шаблоне
                  </button>
                </div>
                <p className="muted">
                  Меняет цвет кнопок, ссылок и плашек. Остальная палитра шаблона сохраняется,
                  а светлые оттенки подстраиваются автоматически.
                </p>
                <div className="accent-row">
                  {ACCENT_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`accent-swatch ${form.accent_color === option.value ? 'is-active' : ''}`}
                      style={{ background: option.value }}
                      onClick={() => set('accent_color', option.value)}
                      title={option.label}
                      aria-label={option.label}
                    />
                  ))}
                  <label className="accent-custom" title="Свой цвет">
                    <input
                      type="color"
                      value={form.accent_color || templates?.find((item) => item.code === form.template)?.tokens.teal || '#0b6b6b'}
                      onChange={(event) => set('accent_color', event.target.value)}
                    />
                    <span>Свой</span>
                  </label>
                </div>
                {form.accent_color ? (
                  <p className="field__hint">Выбран {form.accent_color}. Нажмите «Сохранить настройки», чтобы применить на витрине.</p>
                ) : (
                  <p className="field__hint">Сейчас используется акцент выбранного шаблона.</p>
                )}
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Шаблон витрины</h3></div>
                <p className="muted">
                  Шаблон меняет цвета и скругления витрины. Товары, тексты и фото остаются на месте —
                  можно переключаться сколько угодно раз.
                </p>
                <div className="template-grid">
                  {(templates ?? []).map((item) => (
                    <button
                      key={item.code}
                      type="button"
                      className={`template-card ${form.template === item.code ? 'is-active' : ''}`}
                      onClick={() => set('template', item.code)}
                    >
                      <span className="template-card__swatch">
                        {['ink', 'teal', 'teal-soft', 'gold', 'cream'].map((token) => (
                          <i key={token} style={{ background: item.tokens[token] }} />
                        ))}
                      </span>
                      <strong>{item.title}</strong>
                      <small>{item.description}</small>
                      <span className="template-card__mood">{item.mood}</span>
                    </button>
                  ))}
                </div>
                {!(templates ?? []).length && <p className="muted">Шаблоны загружаются…</p>}
              </section>

              <section className="panel panel--accent">
                <div className="panel__head"><h3>Как применяется</h3></div>
                <p>
                  Выбранный шаблон: <strong>{templates?.find((item) => item.code === form.template)?.title ?? form.template}</strong>.
                  Нажмите «Сохранить настройки» — витрина обновится сразу. Логотип, баннеры и фотографии
                  можно менять отдельно на вкладках «Бренд» и «Главная».
                </p>
              </section>
            </>
          )}

          {tab === 'hero' && (            <>
              <section className="panel">
                <div className="panel__head"><h3>Первый экран</h3></div>
                <div className="form-grid">
                  <label className="field"><span className="field__label">Надзаголовок</span><input className="input" value={form.hero_badge} onChange={(event) => set('hero_badge', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Плашка под заголовком</span><input className="input" value={form.hero_note} onChange={(event) => set('hero_note', event.target.value)} /></label>
                </div>
                <label className="field"><span className="field__label">Главный заголовок</span><input className="input" value={form.hero_title} onChange={(event) => set('hero_title', event.target.value)} /></label>
                <label className="field"><span className="field__label">Подзаголовок</span><textarea className="textarea" rows={3} value={form.hero_subtitle} onChange={(event) => set('hero_subtitle', event.target.value)} /></label>
                <ImageUpload value={form.hero_image_url} onChange={(value) => set('hero_image_url', value)} label="Изображение на главной" hint="Горизонтальное фото магазина или товара, желательно от 1600 px." />
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Блок «О магазине»</h3></div>
                <label className="field"><span className="field__label">Заголовок</span><input className="input" value={form.about_title} onChange={(event) => set('about_title', event.target.value)} /></label>
                <label className="field"><span className="field__label">Текст</span><textarea className="textarea" rows={8} value={form.about_text} onChange={(event) => set('about_text', event.target.value)} /><span className="field__hint">Абзацы разделяйте пустой строкой. В подвале используется первый абзац.</span></label>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Бегущая строка</h3></div>
                <label className="switch-row">
                  <span>Показывать объявление</span>
                  <input type="checkbox" checked={form.announcement_active} onChange={(event) => set('announcement_active', event.target.checked)} />
                  <span className="switch" />
                </label>
                <label className="field"><span className="field__label">Текст объявления</span><input className="input" value={form.announcement} onChange={(event) => set('announcement', event.target.value)} placeholder="Например: сегодня свежий привоз форели" /><span className="field__hint">Показывается в полосе под шапкой на всех страницах.</span></label>
              </section>
            </>
          )}

          {tab === 'contacts' && (
            <>
              <section className="panel">
                <div className="panel__head"><h3>Адрес магазина</h3></div>
                <div className="form-grid form-grid--three">
                  <label className="field"><span className="field__label">Город</span><input className="input" value={form.city} onChange={(event) => set('city', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Рынок</span><input className="input" value={form.market_name} onChange={(event) => set('market_name', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Торговая точка / место</span><input className="input" value={form.pavilion} onChange={(event) => set('pavilion', event.target.value)} /></label>
                </div>
                <label className="field"><span className="field__label">Полный адрес</span><input className="input" value={form.address} onChange={(event) => set('address', event.target.value)} /></label>
                <label className="field"><span className="field__label">Дополнительная информация</span><textarea className="textarea" rows={3} value={form.contacts_extra} onChange={(event) => set('contacts_extra', event.target.value)} /></label>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Связь</h3></div>
                <div className="form-grid">
                  <label className="field"><span className="field__label">Основной телефон</span><input className="input" value={form.phone} onChange={(event) => set('phone', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Дополнительный телефон</span><input className="input" value={form.phone_secondary} onChange={(event) => set('phone_secondary', event.target.value)} /></label>
                </div>
                <label className="field"><span className="field__label">E-mail</span><input className="input" type="email" value={form.email} onChange={(event) => set('email', event.target.value)} /></label>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Социальные сети</h3></div>
                <div className="form-grid">
                  <label className="field"><span className="field__label"><Icon name="tiktok" size={15} /> TikTok</span><input className="input" value={form.socials.tiktok} onChange={(event) => set('socials', { ...form.socials, tiktok: event.target.value })} placeholder="https://tiktok.com/@…" /></label>
                  <label className="field"><span className="field__label"><Icon name="instagram" size={15} /> Instagram</span><input className="input" value={form.socials.instagram} onChange={(event) => set('socials', { ...form.socials, instagram: event.target.value })} placeholder="https://instagram.com/…" /></label>
                  <label className="field"><span className="field__label"><Icon name="youtube" size={15} /> YouTube</span><input className="input" value={form.socials.youtube} onChange={(event) => set('socials', { ...form.socials, youtube: event.target.value })} placeholder="https://youtube.com/@…" /></label>
                  <label className="field"><span className="field__label"><Icon name="telegram" size={15} /> Telegram</span><input className="input" value={form.socials.telegram} onChange={(event) => set('socials', { ...form.socials, telegram: event.target.value })} placeholder="https://t.me/…" /></label>
                  <label className="field"><span className="field__label"><Icon name="viber" size={15} /> Viber</span><input className="input" value={form.socials.viber} onChange={(event) => set('socials', { ...form.socials, viber: event.target.value })} placeholder="viber://chat?number=…" /></label>
                </div>
                <p className="field__hint">Ссылки выводятся крупными кнопками на главной и в подвале. Пустые поля не показываются.</p>
              </section>
            </>
          )}

          {tab === 'hours' && (
            <section className="panel">
              <div className="panel__head"><h3>Режим работы магазина</h3><span className="muted">по местному времени (Минск)</span></div>
              <div className="hours-editor">
                {form.working_hours.map((day, index) => (
                  <div className={`hours-editor__row ${day.closed ? 'is-closed' : ''}`} key={day.weekday}>
                    <strong>{day.label}</strong>
                    <label className="checkbox checkbox--inline">
                      <input type="checkbox" checked={day.closed} onChange={(event) => updateDay(index, { closed: event.target.checked })} />
                      <span>выходной</span>
                    </label>
                    <input className="input input--sm" type="time" value={day.open} disabled={day.closed} onChange={(event) => updateDay(index, { open: event.target.value })} />
                    <span>—</span>
                    <input className="input input--sm" type="time" value={day.close} disabled={day.closed} onChange={(event) => updateDay(index, { close: event.target.value })} />
                  </div>
                ))}
              </div>
              <div className="notice notice--info">
                <Icon name="info" size={18} />
                <span>На основании режима работы формируются доступные интервалы самовывоза. После закрытия магазина новые заказы на сегодня недоступны.</span>
              </div>
            </section>
          )}

          {tab === 'blocks' && (
            <>
              <section className="panel">
                <div className="panel__head">
                  <div><h3>Баннеры на главной</h3><p className="muted">До 2 баннеров показываются под первым экраном</p></div>
                  <button type="button" className="btn btn--sm btn--outline" onClick={addBanner}><Icon name="plus" size={16} /> Добавить баннер</button>
                </div>
                {form.banners.length === 0 && <p className="muted">Баннеров пока нет. Добавьте акционное предложение.</p>}
                {form.banners.map((banner, index) => (
                  <div className="repeater" key={banner.id}>
                    <div className="repeater__head">
                      <strong>Баннер {index + 1}</strong>
                      <div className="row">
                        <label className="switch-row switch-row--compact">
                          <span>Активен</span>
                          <input type="checkbox" checked={banner.is_active} onChange={(event) => updateBanner(index, { is_active: event.target.checked })} />
                          <span className="switch" />
                        </label>
                        <button type="button" className="icon-btn icon-btn--danger" onClick={() => set('banners', form.banners.filter((_, bannerIndex) => bannerIndex !== index))}><Icon name="trash" size={17} /></button>
                      </div>
                    </div>
                    <div className="form-grid">
                      <label className="field"><span className="field__label">Заголовок</span><input className="input" value={banner.title} onChange={(event) => updateBanner(index, { title: event.target.value })} /></label>
                      <label className="field"><span className="field__label">Подзаголовок</span><input className="input" value={banner.subtitle} onChange={(event) => updateBanner(index, { subtitle: event.target.value })} /></label>
                    </div>
                    <div className="form-grid">
                      <label className="field"><span className="field__label">Ссылка</span><input className="input" value={banner.link} onChange={(event) => updateBanner(index, { link: event.target.value })} /></label>
                      <label className="field"><span className="field__label">Текст кнопки</span><input className="input" value={banner.button_text} onChange={(event) => updateBanner(index, { button_text: event.target.value })} /></label>
                    </div>
                    <ImageUpload value={banner.image_url} onChange={(value) => updateBanner(index, { image_url: value })} label="Фон баннера" aspect="wide" />
                  </div>
                ))}
              </section>

              <section className="panel">
                <div className="panel__head">
                  <div><h3>Преимущества</h3><p className="muted">Полоса из 4 пунктов под первым экраном</p></div>
                  <button type="button" className="btn btn--sm btn--outline" onClick={addAdvantage}><Icon name="plus" size={16} /> Добавить</button>
                </div>
                {form.advantages.map((advantage, index) => (
                  <div className="repeater repeater--compact" key={`${advantage.title}-${index}`}>
                    <div className="form-grid form-grid--three">
                      <label className="field">
                        <span className="field__label">Иконка</span>
                        <select className="input input--select" value={advantage.icon} onChange={(event) => set('advantages', form.advantages.map((item, itemIndex) => itemIndex === index ? { ...item, icon: event.target.value } : item))}>
                          {ICON_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </label>
                      <label className="field"><span className="field__label">Заголовок</span><input className="input" value={advantage.title} onChange={(event) => set('advantages', form.advantages.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item))} /></label>
                      <label className="field"><span className="field__label">Текст</span><input className="input" value={advantage.text} onChange={(event) => set('advantages', form.advantages.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value } : item))} /></label>
                    </div>
                    <button type="button" className="icon-btn icon-btn--danger" onClick={() => set('advantages', form.advantages.filter((_, itemIndex) => itemIndex !== index))}><Icon name="trash" size={17} /></button>
                  </div>
                ))}
              </section>
            </>
          )}

          {tab === 'booking' && (
            <>
              <section className="panel">
                <div className="panel__head"><h3>Параметры заказов</h3></div>
                <div className="form-grid form-grid--three">
                  <label className="field"><span className="field__label">Минимальная сумма, BYN</span><input className="input" type="number" step="0.01" value={form.min_order_amount} onChange={(event) => set('min_order_amount', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Готовность, минут</span><input className="input" type="number" value={form.lead_time_minutes} onChange={(event) => set('lead_time_minutes', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Шаг интервалов, минут</span><input className="input" type="number" value={form.slot_step_minutes} onChange={(event) => set('slot_step_minutes', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Дней вперёд</span><input className="input" type="number" value={form.booking_days_ahead} onChange={(event) => set('booking_days_ahead', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Заказов на интервал</span><input className="input" type="number" value={form.slot_capacity} onChange={(event) => set('slot_capacity', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Позиций в заказе</span><input className="input" type="number" value={form.max_items} onChange={(event) => set('max_items', Number(event.target.value))} /></label>
                </div>
                <label className="field"><span className="field__label">Примечание об оплате</span><textarea className="textarea" rows={3} value={form.payment_note} onChange={(event) => set('payment_note', event.target.value)} /><span className="field__hint">Показывается в корзине, кабинете и документах.</span></label>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Правила самовывоза</h3></div>
                <textarea className="textarea textarea--code" rows={18} value={form.pickup_rules} onChange={(event) => set('pickup_rules', event.target.value)} />
                <span className="field__hint">Markdown. Используйте заголовки ##, списки • и подстановку {'{min_order}'} — она заменится на минимальную сумму заказа.</span>
              </section>
            </>
          )}

          {tab === 'legal' && (
            <>
              <section className="panel">
                <div className="panel__head"><h3>Политика обработки персональных данных</h3></div>
                <textarea className="textarea textarea--code" rows={20} value={form.privacy_policy} onChange={(event) => set('privacy_policy', event.target.value)} />
              </section>
              <section className="panel">
                <div className="panel__head"><h3>Правила заказа</h3></div>
                <textarea className="textarea textarea--code" rows={20} value={form.offer_text} onChange={(event) => set('offer_text', event.target.value)} />
                <div className="notice notice--warn">
                  <Icon name="alert" size={18} />
                  <span>Тексты должны соответствовать законодательству Республики Беларусь. Перед публикацией проверьте формулировки с юристом.</span>
                </div>
              </section>
            </>
          )}

          {tab === 'app' && (
            <>
              <section className="panel">
                <div className="panel__head"><h3>Android-приложение</h3></div>
                <label className="field"><span className="field__label">Ссылка на APK</span><input className="input" value={form.android_apk_url} onChange={(event) => set('android_apk_url', event.target.value)} placeholder="/downloads/rybnaya-lavka.apk" /><span className="field__hint">Если файл не готов, оставьте поле пустым — покупатели увидят установку PWA.</span></label>
                <div className="form-grid">
                  <label className="field"><span className="field__label">Версия</span><input className="input" value={form.android_app_version} onChange={(event) => set('android_app_version', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Размер файла</span><input className="input" value={form.android_app_size} onChange={(event) => set('android_app_size', event.target.value)} placeholder="12,4 МБ" /></label>
                </div>
                <label className="field"><span className="field__label">Ссылка на установку</span><input className="input" value={form.app_install_url} onChange={(event) => set('app_install_url', event.target.value)} placeholder="https://…" /></label>
              </section>
              <section className="panel">
                <div className="panel__head"><h3>PWA и iPhone</h3></div>
                <p className="muted">Сайт устанавливается как приложение. На Android покупатель открывает сайт в Chrome и выбирает «Установить приложение». На iPhone/iPad — Safari → «Поделиться» → «На экран „Домой“». QR-код и инструкции размещены на странице /app.</p>
                <a href="/app" target="_blank" rel="noreferrer" className="btn btn--outline"><Icon name="external" size={16} /> Открыть страницу приложения</a>
              </section>
            </>
          )}

          {tab === 'seo' && (
            <>
              <section className="panel">
                <div className="panel__head">
                  <div>
                    <h3>Как магазин выглядит в поиске</h3>
                    <p className="muted">Предпросмотр сниппета Google и Яндекса. Длину лучше держать в пределах 60 и 160 символов.</p>
                  </div>
                </div>
                <div className="seo-preview">
                  <span className="seo-preview__url">{publicBase.replace(/^https?:\/\//, '')}</span>
                  <strong>{form.seo_title || `${form.brand_name} — ${form.city}`}</strong>
                  <p>{form.seo_description || form.tagline}</p>
                </div>
                <div className="seo-meter">
                  <span className={form.seo_title.length > 60 ? 'is-over' : ''}>Title: {form.seo_title.length}/60</span>
                  <span className={form.seo_description.length > 160 ? 'is-over' : ''}>Description: {form.seo_description.length}/160</span>
                </div>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Поисковые системы</h3></div>
                <label className="field"><span className="field__label">Title</span><input className="input" value={form.seo_title} onChange={(event) => set('seo_title', event.target.value)} /></label>
                <label className="field"><span className="field__label">Description</span><textarea className="textarea" rows={3} value={form.seo_description} onChange={(event) => set('seo_description', event.target.value)} /></label>
                <label className="field"><span className="field__label">Keywords</span><input className="input" value={form.seo_keywords} onChange={(event) => set('seo_keywords', event.target.value)} /></label>
                <ImageUpload value={form.seo_og_image_url} onChange={(value) => set('seo_og_image_url', value)} label="Картинка для соцсетей" aspect="wide" hint="Показывается при отправке ссылки в Telegram, Viber и соцсети. Если пусто — используется логотип." />
                <label className="checkbox seo-indexing">
                  <input type="checkbox" checked={form.seo_indexing} onChange={(event) => set('seo_indexing', event.target.checked)} />
                  <span><b>Разрешить индексацию</b><br />Если выключить, robots.txt закроет сайт от поиска, а страницы получат noindex. Используйте на время наполнения.</span>
                </label>
              </section>

              <section className="panel">
                <div className="panel__head">
                  <div>
                    <h3>Аналитика и пиксели</h3>
                    <p className="muted">Вставьте только идентификаторы — код счётчика подключится автоматически и только на витрине.</p>
                  </div>
                </div>
                <div className="form-grid">
                  <label className="field"><span className="field__label">Яндекс Метрика · номер счётчика</span><input className="input" value={form.analytics_yandex} onChange={(event) => set('analytics_yandex', event.target.value)} placeholder="12345678" inputMode="numeric" /></label>
                  <label className="field"><span className="field__label">Google Analytics 4 · Measurement ID</span><input className="input" value={form.analytics_google} onChange={(event) => set('analytics_google', event.target.value)} placeholder="G-XXXXXXXXXX" /></label>
                </div>
                <label className="field"><span className="field__label">Meta Pixel · ID</span><input className="input" value={form.analytics_meta_pixel} onChange={(event) => set('analytics_meta_pixel', event.target.value)} placeholder="123456789012345" inputMode="numeric" /></label>
                <p className="field__hint">Пустое поле — счётчик не подключается. События покупки и просмотра товара передаются автоматически после настройки целей в кабинете.</p>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Файлы для поисковиков</h3></div>
                <p className="muted">Карта сайта и правила обхода формируются автоматически из каталога и всегда актуальны.</p>
                <div className="seo-files">
                  <a className="btn btn--outline" href={`${publicBase}/sitemap.xml`} target="_blank" rel="noreferrer"><Icon name="external" size={16} /> sitemap.xml</a>
                  <a className="btn btn--outline" href={`${publicBase}/robots.txt`} target="_blank" rel="noreferrer"><Icon name="external" size={16} /> robots.txt</a>
                </div>
                <p className="field__hint">Добавьте карту сайта в Яндекс.Вебмастер и Google Search Console — так новые товары попадут в поиск быстрее.</p>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Карта</h3></div>
                <label className="field"><span className="field__label">Ссылка «Построить маршрут»</span><input className="input" value={form.map_url} onChange={(event) => set('map_url', event.target.value)} placeholder="https://yandex.by/maps/…" /></label>
                <label className="field"><span className="field__label">HTML-код встраиваемой карты (iframe src)</span><input className="input" value={form.map_embed_url} onChange={(event) => set('map_embed_url', event.target.value)} placeholder="https://yandex.by/map-widget/v1/?…" /><span className="field__hint">На странице контактов будет показана интерактивная карта. Оставьте пустым для схемы-заглушки.</span></label>
              </section>
            </>
          )}
        </div>

        <aside className="settings-side">
          <div className="panel panel--soft">
            <h3><Icon name="pin" size={18} /> Магазин</h3>
            <p><strong>{form.city}</strong><br />{form.market_name}<br />{form.pavilion}</p>
            <p className="muted">{form.address}</p>
          </div>
          <div className="panel panel--soft">
            <h3><Icon name="phone" size={18} /> Контакты</h3>
            <p>{form.phone}<br />{form.email}</p>
          </div>
          <div className="panel panel--highlight">
            <h3><Icon name="shield" size={18} /> Требования торговли</h3>
            <p>Указывайте актуальные УНП, юридический адрес и режим работы. Эти сведения обязательны для сайта продавца в Республике Беларусь.</p>
          </div>
          <button type="button" className="btn btn--primary btn--block" onClick={save} disabled={busy}>
            {busy ? <Spinner size={17} /> : <Icon name="check" size={17} />} Сохранить настройки
          </button>
        </aside>
      </div>
    </div>
  )
}
