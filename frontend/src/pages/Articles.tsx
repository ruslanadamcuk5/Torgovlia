import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../lib/useApi'
import { assetUrl } from '../lib/api'
import { useSite } from '../store/SettingsContext'
import { Icon } from '../components/icons'
import { Loader } from '../components/ui'
import type { ArticleShort } from '../lib/types'

export default function Articles() {
  const { site } = useSite()
  const { data, loading } = useApi<{ items: ArticleShort[] }>('/articles', false)
  const [query, setQuery] = useState('')

  const items = useMemo(() => {
    if (!data) return []
    const term = query.trim().toLowerCase()
    if (!term) return data.items
    return data.items.filter((item) =>
      `${item.title} ${item.subtitle} ${item.short_description}`.toLowerCase().includes(term),
    )
  }, [data, query])

  if (!site) return null

  return (
    <div className="articles-page">
      <div className="page-head">
        <div className="container">
          <div className="breadcrumbs"><Link to="/">Главная</Link><Icon name="chevron-right" size={13} /><span>Статьи</span></div>
          <div className="page-head__row">
            <div>
              <span className="eyebrow">Полезные статьи</span>
              <h1>Всё о товарах — коротко и по делу</h1>
              <p className="page-head__sub">Как выбрать, использовать и ухаживать. Каждая статья привязана к товару в каталоге.</p>
            </div>
            <label className="search-field search-field--large">
              <Icon name="search" size={18} />
              <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти товар или статью" />
            </label>
          </div>
        </div>
      </div>

      <div className="container section">
        {loading ? <Loader /> : (
          <>
            <div className="article-grid article-grid--wide">
              {items.map((article) => (
                <Link to={`/fish/${article.slug}`} className="article-card" key={article.slug}>
                  <div className="article-card__media">
                    {article.image_url ? <img src={assetUrl(article.image_url)} alt={article.title} loading="lazy" /> : <Icon name="book" size={44} />}
                    <span className="article-card__time"><Icon name="clock" size={14} /> {article.reading_minutes} мин чтения</span>
                  </div>
                  <div className="article-card__body">
                    <div className="article-card__meta">
                      {article.category && <span className="article-card__cat">{article.category}</span>}
                      {article.season && <span className="muted">{article.season}</span>}
                    </div>
                    <h3>{article.title}</h3>
                    <p>{article.short_description}</p>
                    <span className="link-arrow">Читать и заказать <Icon name="arrow-right" size={16} /></span>
                  </div>
                </Link>
              ))}
            </div>
            {items.length === 0 && (
              <div className="empty-state">
                <span className="empty-state__icon"><Icon name="book" size={30} /></span>
                <h3>Статьи не найдены</h3>
                <p>Попробуйте другой запрос.</p>
              </div>
            )}
          </>
        )}

        <div className="articles-note">
          <Icon name="qr" size={24} />
          <div>
            <strong>QR-коды на прилавке</strong>
            <p>На упаковке или ценнике может быть QR-код со ссылкой на статью о товаре. Наведите камеру, чтобы узнать подробности, характеристики и советы по использованию.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
