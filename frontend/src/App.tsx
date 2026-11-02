import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './store/AuthContext'
import { CartProvider } from './store/CartContext'
import { SettingsProvider } from './store/SettingsContext'
import { ToastProvider } from './store/ToastContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { PublicLayout, ScrollToTop } from './components/Layout'
import UpdatePrompt from './components/UpdatePrompt'
import AdminLayout from './pages/admin/AdminLayout'
import Dashboard from './pages/admin/Dashboard'
import AdminOrders from './pages/admin/Orders'
import CatalogAdmin from './pages/admin/CatalogAdmin'
import Promotions from './pages/admin/Promotions'
import AdminUsers from './pages/admin/Users'
import SettingsAdmin from './pages/admin/SettingsAdmin'
import AdminQr from './pages/admin/Qr'
import Seller from './pages/Seller'
import Home from './pages/Home'
import Catalog from './pages/Catalog'
import ProductPage from './pages/ProductPage'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Login from './pages/Login'
import Register from './pages/Register'
import ResetPassword from './pages/ResetPassword'
import Account from './pages/Account'
import Lookup from './pages/Lookup'
import Articles from './pages/Articles'
import Legal from './pages/Legal'
import Pickup from './pages/Pickup'
import Contacts from './pages/Contacts'
import AppPage from './pages/AppPage'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <AuthProvider>
          <CartProvider>
            <ToastProvider>
              <ScrollToTop />
              <UpdatePrompt />
              <Routes>
                <Route element={<PublicLayout />}>
                  <Route path="/" element={<Home />} />
                  <Route path="/catalog" element={<Catalog />} />
                  <Route path="/fish/:slug" element={<ProductPage />} />
                  <Route path="/cart" element={<Cart />} />
                  <Route path="/checkout" element={<Checkout />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                  <Route path="/reset" element={<ResetPassword />} />
                  <Route
                    path="/account"
                    element={(
                      <ProtectedRoute>
                        <Account />
                      </ProtectedRoute>
                    )}
                  />
                  <Route path="/lookup" element={<Lookup />} />
                  <Route path="/articles" element={<Articles />} />
                  <Route path="/legal/:kind" element={<Legal />} />
                  <Route path="/pickup" element={<Pickup />} />
                  <Route path="/contacts" element={<Contacts />} />
                  <Route path="/app" element={<AppPage />} />
                  <Route path="*" element={<NotFound />} />
                </Route>

                <Route
                  path="/admin"
                  element={(
                    <ProtectedRoute roles={['admin']}>
                      <AdminLayout />
                    </ProtectedRoute>
                  )}
                >
                  <Route index element={<Dashboard />} />
                  <Route path="orders" element={<AdminOrders />} />
                  <Route path="catalog" element={<CatalogAdmin />} />
                  <Route path="promotions" element={<Promotions />} />
                  <Route path="users" element={<AdminUsers />} />
                  <Route path="settings" element={<SettingsAdmin />} />
                  <Route path="qr" element={<AdminQr />} />
                  <Route path="*" element={<Navigate to="/admin" replace />} />
                </Route>

                <Route
                  path="/seller"
                  element={(
                    <ProtectedRoute roles={['admin', 'seller']}>
                      <Seller />
                    </ProtectedRoute>
                  )}
                />
              </Routes>
            </ToastProvider>
          </CartProvider>
        </AuthProvider>
      </SettingsProvider>
    </BrowserRouter>
  )
}
