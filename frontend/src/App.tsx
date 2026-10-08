import { Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import About from './pages/About'
import Account from './pages/Account'
import Bag from './pages/Bag'
import CreateAccount from './pages/CreateAccount'
import Home from './pages/Home'
import Login from './pages/Login'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="products" element={<Products />} />
        <Route path="products/:id" element={<ProductDetail />} />
        <Route path="about" element={<About />} />
        <Route path="login" element={<Login />} />
        <Route path="create-account" element={<CreateAccount />} />
        <Route path="account" element={<Account />} />
        <Route path="bag" element={<Bag />} />
        <Route
          path="*"
          element={
            <div className="empty">
              <h2>Page not found</h2>
              <Link to="/" className="btn btn-primary">
                Go home
              </Link>
            </div>
          }
        />
      </Route>
    </Routes>
  )
}
