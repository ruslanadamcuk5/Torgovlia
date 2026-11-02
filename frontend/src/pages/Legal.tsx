import { Link, useParams } from 'react-router-dom'
import { useSite } from '../store/SettingsContext'
import { MarkdownText } from '../components/MarkdownText'
import { Icon } from '../components/icons'

const RETURNS = `## Возврат и обмен

Рыба и морепродукты относятся к скоропортящимся товарам. В соответствии с законодательством Республики Беларусь товар надлежащего качества, приобретённый в розничной торговле, возврату и обмену не подлежит, если иное не установлено продавцом.

## Если товар оказался некачественным

• Осмотрите заказ в момент получения в павильоне — вместе с продавцом.
• При обнаружении недостатков сообщите продавцу сразу: мы заменим товар или вернём деньги.
• Сохраните чек и упаковку до рассмотрения обращения.

## Претензии

Претензии по качеству принимаются по телефону и на e-mail, указанным в разделе «Контакты». Срок рассмотрения — не более 15 рабочих дней. Если вопрос не удаётся решить на месте, вы вправе обратиться в местные органы торговли и защиты прав потребителей.

## Важно

Бронирование не является договором купли-продажи до момента передачи товара и его оплаты. Стоимость весового товара определяется по фактическому весу при выдаче.`

const DOCS = [
  { slug: 'privacy', title: 'Политика обработки персональных данных', short: 'Персональные данные' },
  { slug: 'offer', title: 'Правила бронирования', short: 'Бронирование' },
  { slug: 'pickup', title: 'Условия самовывоза', short: 'Самовывоз' },
  { slug: 'returns', title: 'Возврат и качество', short: 'Возврат' },
]

export function legalText(kind: string, privacy: string, offer: string, pickup: string): { title: string; text: string } {
  if (kind === 'privacy') return { title: 'Политика обработки персональных данных', text: privacy }
  if (kind === 'offer') return { title: 'Правила бронирования', text: offer }
  if (kind === 'pickup') return { title: 'Условия самовывоза', text: pickup }
  return { title: 'Возврат и качество', text: RETURNS }
}

export default function Legal() {
  const { kind = 'privacy' } = useParams()
  const { site } = useSite()
  if (!site) return null
  const s = site.settings
  const doc = legalText(kind, s.privacy_policy, s.offer_text, s.pickup_rules)

  return (
    <div className="container section legal-page">
      <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>{doc.title}</span></div>
      <div className="legal-head">
        <span className="eyebrow">Документы</span>
        <h1>{doc.title}</h1>
        <p>Редакция от {new Date().toLocaleDateString('ru-BY')} · {s.legal_name}, УНП {s.unp}</p>
      </div>

      <div className="legal-layout">
        <aside className="legal-nav">
          {DOCS.map((item) => (
            <Link key={item.slug} to={`/legal/${item.slug}`} className={kind === item.slug ? 'is-active' : ''}>
              {item.short}
              <Icon name="chevron-right" size={16} />
            </Link>
          ))}
          <div className="legal-nav__contact">
            <strong>Вопросы по документам</strong>
            <a href={`mailto:${s.email}`}>{s.email}</a>
            <a href={`tel:${s.phone.replace(/[^\d+]/g, '')}`}>{s.phone}</a>
          </div>
        </aside>

        <article className="legal-body panel">
          <MarkdownText text={doc.text} />
          <div className="legal-requisites">
            <h2>Реквизиты</h2>
            <p><strong>{s.legal_name}</strong></p>
            <p>УНП {s.unp}</p>
            <p>{s.legal_address || s.address}</p>
            <p>Режим работы: {s.working_hours.map((day) => `${day.label.slice(0, 2)} ${day.closed ? 'выходной' : `${day.open}–${day.close}`}`).join(', ')}</p>
          </div>
        </article>
      </div>
    </div>
  )
}
