import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useSite } from '../../store/SettingsContext'
import { useToast } from '../../store/ToastContext'
import { ImageUpload } from '../../components/ImageUpload'
import { Loader, Spinner, Tabs } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Advantage, Banner, Settings, WorkingDay } from '../../lib/types'

const TABS = [
  { id: 'brand', label: 'Бренд и реквизиты' },
  { id: 'hero', label: 'Главная' },
  { id: 'contacts', label: 'Адрес и контакты' },
  { id: 'hours', label: 'Режим работы' },
  { id: 'blocks', label: 'Баннеры и преимущества' },
  { id: 'booking', label: 'Бронирование' },
  { id: 'legal', label: 'Документы' },
  { id: 'app', label: 'Приложение' },
  { id: 'seo', label: 'SEO и карта' },
]

const ICON_OPTIONS = [
  ['fish', 'Рыба'], ['shield', 'Гарантия'], ['clock', 'Время'], ['scissors', 'Разделка'],
  ['star', 'Звезда'], ['heart', 'Сердце'], ['scale', 'Весы'], ['wallet', 'Оплата'],
]

export default function SettingsAdmin() {
  const { toast } = useToast()
  const { refresh } = useSite()
  const { data, loading, reload } = useApi<{ settings: Settings; updated_at: string | null }>('/admin/settings')
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
    const advantage: Advantage = { icon: 'fish', title: 'Новое преимущество', text: '' }
    set('advantages', [...form.advantages, advantage])
  }

  return (
    <div className="admin-page settings-admin">
      <div className="settings-head">
        <div>
          <h2>Настройки сайта</h2>
          <p>Реквизиты продавца, контакты, тексты и параметры бронирования. Изменения сразу видны покупателям.</p>
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

          {tab === 'hero' && (
            <>
              <section className="panel">
                <div className="panel__head"><h3>Первый экран</h3></div>
                <div className="form-grid">
                  <label className="field"><span className="field__label">Надзаголовок</span><input className="input" value={form.hero_badge} onChange={(event) => set('hero_badge', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Плашка под заголовком</span><input className="input" value={form.hero_note} onChange={(event) => set('hero_note', event.target.value)} /></label>
                </div>
                <label className="field"><span className="field__label">Главный заголовок</span><input className="input" value={form.hero_title} onChange={(event) => set('hero_title', event.target.value)} /></label>
                <label className="field"><span className="field__label">Подзаголовок</span><textarea className="textarea" rows={3} value={form.hero_subtitle} onChange={(event) => set('hero_subtitle', event.target.value)} /></label>
                <ImageUpload value={form.hero_image_url} onChange={(value) => set('hero_image_url', value)} label="Изображение на главной" hint="Горизонтальное фото павильона или рыбы, желательно от 1600 px." />
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Блок «О павильоне»</h3></div>
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
                <div className="panel__head"><h3>Адрес павильона</h3></div>
                <div className="form-grid form-grid--three">
                  <label className="field"><span className="field__label">Город</span><input className="input" value={form.city} onChange={(event) => set('city', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Рынок</span><input className="input" value={form.market_name} onChange={(event) => set('market_name', event.target.value)} /></label>
                  <label className="field"><span className="field__label">Павильон / место</span><input className="input" value={form.pavilion} onChange={(event) => set('pavilion', event.target.value)} /></label>
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
              <div className="panel__head"><h3>Режим работы павильона</h3><span className="muted">по местному времени (Минск)</span></div>
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
                <span>На основании режима работы формируются доступные интервалы самовывоза. После закрытия павильона новые брони на сегодня недоступны.</span>
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
                <div className="panel__head"><h3>Параметры бронирования</h3></div>
                <div className="form-grid form-grid--three">
                  <label className="field"><span className="field__label">Минимальная сумма, BYN</span><input className="input" type="number" step="0.01" value={form.min_order_amount} onChange={(event) => set('min_order_amount', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Готовность, минут</span><input className="input" type="number" value={form.lead_time_minutes} onChange={(event) => set('lead_time_minutes', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Шаг интервалов, минут</span><input className="input" type="number" value={form.slot_step_minutes} onChange={(event) => set('slot_step_minutes', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Дней вперёд</span><input className="input" type="number" value={form.booking_days_ahead} onChange={(event) => set('booking_days_ahead', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Броней на интервал</span><input className="input" type="number" value={form.slot_capacity} onChange={(event) => set('slot_capacity', Number(event.target.value))} /></label>
                  <label className="field"><span className="field__label">Позиций в заказе</span><input className="input" type="number" value={form.max_items} onChange={(event) => set('max_items', Number(event.target.value))} /></label>
                </div>
                <label className="field"><span className="field__label">Примечание об оплате</span><textarea className="textarea" rows={3} value={form.payment_note} onChange={(event) => set('payment_note', event.target.value)} /><span className="field__hint">Показывается в корзине, кабинете и документах.</span></label>
              </section>

              <section className="panel">
                <div className="panel__head"><h3>Правила самовывоза</h3></div>
                <textarea className="textarea textarea--code" rows={18} value={form.pickup_rules} onChange={(event) => set('pickup_rules', event.target.value)} />
                <span className="field__hint">Markdown. Используйте заголовки ##, списки • и подстановку {'{min_order}'} — она заменится на минимальную сумму брони.</span>
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
                <div className="panel__head"><h3>Правила бронирования</h3></div>
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
                <div className="panel__head"><h3>Поисковые системы</h3></div>
                <label className="field"><span className="field__label">Title</span><input className="input" value={form.seo_title} onChange={(event) => set('seo_title', event.target.value)} /></label>
                <label className="field"><span className="field__label">Description</span><textarea className="textarea" rows={3} value={form.seo_description} onChange={(event) => set('seo_description', event.target.value)} /></label>
                <label className="field"><span className="field__label">Keywords</span><input className="input" value={form.seo_keywords} onChange={(event) => set('seo_keywords', event.target.value)} /></label>
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
            <h3><Icon name="pin" size={18} /> Павильон</h3>
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
