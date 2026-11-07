import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { useToast } from '../../store/ToastContext'
import { Loader, Spinner } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { Review } from '../../lib/types'

const FILTERS = [
  { key: 'pending', label: 'На проверке' },
  { key: 'published', label: 'Опубликованные' },
  { key: 'rejected', label: 'Отклонённые' },
  { key: 'all', label: 'Все' },
] as const

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  pending: { label: 'На проверке', tone: 'warning' },
  published: { label: 'Опубликован', tone: 'success' },
  rejected: { label: 'Отклонён', tone: 'muted' },
}

function Stars({ value }: { value: number }) {
  return (
    <span className="stars" aria-label={`Оценка ${value} из 5`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} className={star <= value ? 'stars__item is-on' : 'stars__item'}>★</span>
      ))}
    </span>
  )
}

export default function Reviews() {
  const { toast } = useToast()
  const { data: features, loading: featuresLoading } = useApi<{ services: Record<string, boolean> }>('/admin/services/features')
  const enabled = Boolean(features?.services.reviews)
  const { data, loading, reload } = useApi<Review[]>(enabled ? '/admin/reviews' : null)
  const [filter, setFilter] = useState<(typeof FILTERS)[number]['key']>('pending')
  const [busyId, setBusyId] = useState<number | null>(null)

  const reviews = data ?? []
  const counts = useMemo(() => {
    const result: Record<string, number> = { all: reviews.length, pending: 0, published: 0, rejected: 0 }
    for (const review of reviews) result[review.status] = (result[review.status] ?? 0) + 1
    return result
  }, [reviews])

  const visible = filter === 'all' ? reviews : reviews.filter((review) => review.status === filter)

  const moderate = async (review: Review, status: Review['status']) => {
    setBusyId(review.id)
    try {
      await api(`/admin/reviews/${review.id}`, { method: 'PATCH', body: { status } })
      toast(
        status === 'published'
          ? 'Отзыв опубликован'
          : status === 'rejected'
            ? 'Отзыв отклонён'
            : 'Отзыв возвращён на проверку',
      )
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось изменить отзыв', 'error')
    } finally {
      setBusyId(null)
    }
  }

  const remove = async (review: Review) => {
    if (!window.confirm(`Удалить отзыв «${review.customer_name}»?`)) return
    setBusyId(review.id)
    try {
      await api(`/admin/reviews/${review.id}`, { method: 'DELETE' })
      toast('Отзыв удалён')
      reload()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось удалить отзыв', 'error')
    } finally {
      setBusyId(null)
    }
  }

  if (featuresLoading) return <Loader />

  if (!enabled) {
    return (
      <div className="admin-page">
        <section className="panel panel--accent">
          <div className="panel__head"><h2>Отзывы и рейтинги</h2></div>
          <p>
            Отзывы покупателей доступны на тарифе <strong>«Бизнес»</strong> и выше.
            Включите сервис в разделе «Сервисы» — после этого здесь появится модерация.
          </p>
          <Link to="/admin/services" className="btn btn--primary">Перейти к сервисам <Icon name="arrow-right" size={17} /></Link>
        </section>
      </div>
    )
  }

  if (loading) return <Loader />

  return (
    <div className="admin-page reviews-page">
      <section className="panel">
        <div className="panel__head">
          <div>
            <h2>Отзывы покупателей</h2>
            <p className="muted">
              Отзыв появляется на витрине только после публикации. Рейтинг товара считается по опубликованным отзывам.
            </p>
          </div>
          <span className="muted">{counts.pending} на проверке</span>
        </div>

        <div className="review-tabs">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={filter === item.key ? 'is-active' : ''}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
              <b>{counts[item.key] ?? 0}</b>
            </button>
          ))}
        </div>

        {visible.length === 0 ? (
          <p className="muted">
            {filter === 'pending' ? 'Новых отзывов нет — всё проверено.' : 'Здесь пока пусто.'}
          </p>
        ) : (
          <div className="review-admin-list">
            {visible.map((review) => {
              const state = STATUS_LABEL[review.status] ?? STATUS_LABEL.pending
              return (
                <article key={review.id} className="review-admin-card">
                  <div className="review-admin-card__head">
                    <div>
                      <strong>{review.product_title || 'Товар удалён'}</strong>
                      {review.product_slug && (
                        <a href={`/fish/${review.product_slug}`} target="_blank" rel="noreferrer" className="table-sub">
                          Открыть товар
                        </a>
                      )}
                    </div>
                    <span className={`badge badge--${state.tone}`}>{state.label}</span>
                  </div>

                  <div className="review-admin-card__meta">
                    <strong>{review.customer_name}</strong>
                    <Stars value={review.rating} />
                    {review.is_verified_purchase && <span className="badge badge--fresh">Покупка подтверждена</span>}
                    {review.phone_formatted && <span className="muted">{review.phone_formatted}</span>}
                    {review.created_at && (
                      <span className="muted">{new Date(review.created_at).toLocaleDateString('ru-RU')}</span>
                    )}
                  </div>

                  <p className="review-admin-card__text">{review.text}</p>
                  {review.admin_comment && <p className="muted">Комментарий: {review.admin_comment}</p>}

                  <div className="review-admin-card__actions">
                    {review.status !== 'published' && (
                      <button
                        type="button"
                        className="btn btn--sm btn--primary"
                        onClick={() => void moderate(review, 'published')}
                        disabled={busyId === review.id}
                      >
                        {busyId === review.id ? <Spinner size={14} /> : <Icon name="check" size={15} />}
                        Опубликовать
                      </button>
                    )}
                    {review.status !== 'rejected' && (
                      <button
                        type="button"
                        className="btn btn--sm btn--outline"
                        onClick={() => void moderate(review, 'rejected')}
                        disabled={busyId === review.id}
                      >
                        {review.status === 'published' ? 'Скрыть' : 'Отклонить'}
                      </button>
                    )}
                    {review.status === 'rejected' && (
                      <button
                        type="button"
                        className="btn btn--sm btn--ghost"
                        onClick={() => void moderate(review, 'pending')}
                        disabled={busyId === review.id}
                      >
                        Вернуть на проверку
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn--sm btn--ghost"
                      onClick={() => void remove(review)}
                      disabled={busyId === review.id}
                    >
                      Удалить
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
