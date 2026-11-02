import { useRef, useState } from 'react'
import { assetUrl, uploadImage } from '../lib/api'
import { useToast } from '../store/ToastContext'
import { Icon } from './icons'
import { Spinner } from './ui'

interface Props {
  value?: string | null
  onChange: (url: string) => void
  label?: string
  endpoint?: string
  aspect?: 'wide' | 'square'
  hint?: string
}

export function ImageUpload({ value, onChange, label = 'Изображение', endpoint = '/admin/uploads', aspect = 'wide', hint }: Props) {
  const { toast } = useToast()
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file?: File) => {
    if (!file) return
    if (file.size > 8 * 1024 * 1024) {
      toast('Файл больше 8 МБ', 'error')
      return
    }
    setBusy(true)
    try {
      const result = await uploadImage(file, endpoint)
      onChange(result.url)
      toast('Изображение загружено')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не удалось загрузить изображение', 'error')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="image-upload">
      <div className={`image-upload__preview image-upload__preview--${aspect}`}>
        {value ? <img src={assetUrl(value)} alt={label} /> : <span><Icon name="image" size={26} />Нет изображения</span>}
        {busy && <div className="image-upload__loading"><Spinner size={26} /></div>}
      </div>
      <div className="image-upload__actions">
        <span className="field__label">{label}</span>
        <div className="row row--wrap">
          <button type="button" className="btn btn--sm btn--outline" onClick={() => inputRef.current?.click()} disabled={busy}>
            <Icon name="upload" size={16} /> Загрузить
          </button>
          {value && (
            <button type="button" className="btn btn--sm btn--ghost" onClick={() => onChange('')}>
              <Icon name="trash" size={16} /> Убрать
            </button>
          )}
        </div>
        {hint && <span className="field__hint">{hint}</span>}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(event) => void handleFile(event.target.files?.[0])}
      />
    </div>
  )
}
