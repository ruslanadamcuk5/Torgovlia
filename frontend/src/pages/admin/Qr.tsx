import { useMemo, useState } from 'react'
import { useApi } from '../../lib/useApi'
import { assetUrl } from '../../lib/api'
import { useToast } from '../../store/ToastContext'
import { Loader } from '../../components/ui'
import { Icon } from '../../components/icons'
import type { QrItem } from '../../lib/types'

function absolute(path: string) {
  const url = assetUrl(path)
  return /^https?:/i.test(url) ? url : new URL(url, window.location.origin).toString()
}

export default function AdminQr() {
  const { toast } = useToast()
  const { data, loading } = useApi<{ items: QrItem[]; total: number }>('/admin/qr/items')
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<'all' | 'site' | 'product'>('all')

  const items = useMemo(() => {
    const term = query.trim().toLowerCase()
    return (data?.items ?? []).filter((item) => {
      if (kind !== 'all' && item.kind !== kind) return false
      if (term && !`${item.title} ${item.target} ${item.url}`.toLowerCase().includes(term)) return false
      return true
    })
  }, [data, kind, query])

  const openPrint = (rows: QrItem[]) => {
    if (!rows.length) return
    const win = window.open('', '_blank', 'width=900,height=700')
    if (!win) {
      toast('Разрешите всплывающие окна, чтобы напечатать QR-коды', 'error')
      return
    }
    const cards = rows.map((item) => `
      <article class="card">
        <h2>${escapeHtml(item.title)}</h2>
        <img src="${absolute(item.qr_url)}" alt="QR ${escapeHtml(item.title)}" />
        <p>${escapeHtml(item.url)}</p>
        <small>Наведите камеру телефона — откроется ${item.kind === 'site' ? 'сайт с каталогом' : 'статья о рыбе и кнопка брони'}</small>
      </article>`).join('')
    win.document.write(`<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>QR-коды — Рыбная лавка</title>
      <style>
        *{box-sizing:border-box} body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#08272e}
        h1{font-size:24px;margin:0 0 4px} .head{display:flex;justify-content:space-between;align-items:end;margin-bottom:20px;border-bottom:2px solid #0b6b6b;padding-bottom:12px}
        .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
        .card{border:1.5px solid #d7e2df;border-radius:14px;padding:16px;break-inside:avoid;text-align:center}
        .card h2{font-size:16px;margin:0 0 8px;min-height:38px}.card img{width:220px;height:220px;display:block;margin:0 auto 8px}
        .card p{font-size:10px;color:#52706f;word-break:break-all;margin:0 0 6px}.card small{font-size:10px;color:#6b807e}
        @media print{body{margin:10mm}.grid{grid-template-columns:repeat(3,1fr);gap:8mm}.card img{width:52mm;height:52mm}.card{border-color:#eee}}
      </style></head><body>
      <div class="head"><div><h1>Рыбная лавка · QR-коды</h1><div>${new Date().toLocaleDateString('ru-BY')} · ${rows.length} шт.</div></div><div>г. Барановичи · рынок «Алексеевский»</div></div>
      <div class="grid">${cards}</div>
      <script>window.onload=()=>{setTimeout(()=>window.print(),500)}</script>
      </body></html>`)
    win.document.close()
  }

  const siteQr = (data?.items ?? []).find((item) => item.kind === 'site')

  return (
    <div className="admin-page">
      <div className="qr-hero">
        <div>
          <span className="eyebrow">Печать и размещение</span>
          <h2>QR-коды сайта и рыбы</h2>
          <p>Распечатайте код и разместите его на прилавке. Покупатель наведёт камеру и сразу откроет статью о рыбе с кнопкой бронирования.</p>
          <div className="qr-hero__actions">
            <button type="button" className="btn btn--primary" onClick={() => openPrint(data?.items ?? [])}>
              <Icon name="print" size={17} /> Распечатать все
            </button>
            {siteQr && <a href={assetUrl(siteQr.download_url)} className="btn btn--outline" download><Icon name="download" size={17} /> QR сайта PNG</a>}
          </div>
        </div>
        {siteQr && (
          <a href={assetUrl(siteQr.qr_url)} target="_blank" rel="noreferrer" className="qr-hero__code">
            <img src={assetUrl(siteQr.qr_url)} alt="QR-код сайта" />
            <span>Главная страница</span>
          </a>
        )}
      </div>

      <div className="admin-toolbar">
        <div className="admin-toolbar__left">
          <label className="search-field">
            <Icon name="search" size={17} />
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти товар" />
          </label>
        </div>
        <div className="admin-tabs admin-tabs--inline">
          {([['all', 'Все'], ['site', 'Сайт'], ['product', 'Товары']] as const).map(([value, label]) => (
            <button key={value} type="button" className={kind === value ? 'is-active' : ''} onClick={() => setKind(value)}>{label}</button>
          ))}
        </div>
        <div className="admin-toolbar__right">
          <button type="button" className="btn btn--sm btn--outline" disabled={!items.length} onClick={() => openPrint(items)}>
            <Icon name="print" size={16} /> Печать выбранных ({items.length})
          </button>
        </div>
      </div>

      {loading ? <Loader /> : (
        <div className="qr-grid">
          {items.map((item) => (
            <article className="qr-card" key={`${item.kind}-${item.target}`}>
              <a href={assetUrl(item.qr_url)} target="_blank" rel="noreferrer" className="qr-card__image">
                <img src={assetUrl(item.qr_url)} alt={`QR ${item.title}`} loading="lazy" />
              </a>
              <div className="qr-card__body">
                <span className={`badge ${item.kind === 'site' ? 'badge--gold' : 'badge--soft'}`}>{item.kind === 'site' ? 'Сайт' : 'Товар'}</span>
                <h3>{item.title}</h3>
                <span className="qr-card__url">{item.url}</span>
                <div className="qr-card__actions">
                  <a href={assetUrl(item.download_url)} className="btn btn--sm btn--outline" download><Icon name="download" size={15} /> PNG</a>
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => openPrint([item])}><Icon name="print" size={15} /> Печать</button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="empty-state">
          <span className="empty-state__icon"><Icon name="qr" size={28} /></span>
          <h3>Ничего не найдено</h3>
          <p>Измените фильтр или добавьте товары в каталог.</p>
        </div>
      )}

      <div className="notice notice--info">
        <Icon name="info" size={18} />
        <span>Печать на обычном принтере A4. Рекомендуемый размер кода на прилавке — не менее 5×5 см. Не меняйте адрес (slug) товара после печати QR — старые коды перестанут открывать статью.</span>
      </div>
    </div>
  )
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char] ?? char))
}
