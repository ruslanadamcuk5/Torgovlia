import { Link } from 'react-router-dom'
import { Icon } from '../components/icons'

export default function NotFound() {
  return (
    <div className="container section notfound">
      <span className="notfound__code">404</span>
      <h1>Такой страницы нет</h1>
      <p>Возможно, товар снят с продажи или ссылка устарела. Посмотрите каталог — там актуальные товары.</p>
      <div className="row">
        <Link to="/" className="btn btn--primary">На главную</Link>
        <Link to="/catalog" className="btn btn--outline">В каталог <Icon name="arrow-right" size={17} /></Link>
      </div>
    </div>
  )
}
