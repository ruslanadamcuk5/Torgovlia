import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { AuthProvider } from './store/AuthContext'
import { CartProvider } from './store/CartContext'
import { SettingsProvider } from './store/SettingsContext'
import { useSite } from './store/SettingsContext'
import { ToastProvider } from './store/ToastContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { PublicLayout, ScrollToTop } from './components/Layout'
import UpdatePrompt from './components/UpdatePrompt'
import { Analytics } from './components/Analytics'
import AdminLayout from './pages/admin/AdminLayout'
import Dashboard from './pages/admin/Dashboard'
import Reports from './pages/admin/Reports'
import Notifications from './pages/admin/Notifications'
import Inventory from './pages/admin/Inventory'
import Suppliers from './pages/admin/Suppliers'
import AdminOrders from './pages/admin/Orders'
import CatalogAdmin from './pages/admin/CatalogAdmin'
import Promotions from './pages/admin/Promotions'
import PromoCodes from './pages/admin/PromoCodes'
import Reviews from './pages/admin/Reviews'
import Delivery from './pages/admin/Delivery'
import AdminUsers from './pages/admin/Users'
import SettingsAdmin from './pages/admin/SettingsAdmin'
import AdminServices from './pages/admin/Services'
import AdminServiceDetail from './pages/admin/ServiceDetail'
import AdminBilling from './pages/admin/Billing'
import AdminQr from './pages/admin/Qr'
import PriceTags from './pages/admin/PriceTags'
import Barcodes from './pages/admin/Barcodes'
import PriceImport from './pages/admin/PriceImport'
import Campaigns from './pages/admin/Campaigns'
import Carts from './pages/admin/Carts'
import Upsells from './pages/admin/Upsells'
import Loyalty from './pages/admin/Loyalty'
import Crm from './pages/admin/Crm'
import Chat from './pages/admin/Chat'
import Tasks from './pages/admin/Tasks'
import Certificates from './pages/admin/Certificates'
import SubscriptionsAdmin from './pages/admin/Subscriptions'
import PlatformLogin from './pages/platform/PlatformLogin'
import PlatformLayout from './pages/platform/PlatformLayout'
import PlatformOverview from './pages/platform/PlatformOverview'
import PlatformTenants from './pages/platform/PlatformTenants'
import PlatformTenant from './pages/platform/PlatformTenant'
import PlatformCatalog from './pages/platform/PlatformCatalog'
import PlatformServiceDetail from './pages/platform/PlatformServiceDetail'
import PlatformAnalytics from './pages/platform/PlatformAnalytics'
import PlatformInvoices from './pages/platform/PlatformInvoices'
import PlatformOps from './pages/platform/PlatformOps'
import PlatformAudit from './pages/platform/PlatformAudit'
import PlatformIncidents from './pages/platform/PlatformIncidents'
import PlatformSettings from './pages/platform/PlatformSettings'
import PlatformTeam from './pages/platform/PlatformTeam'
import PlatformStatus from './pages/PlatformStatus'
import Seller from './pages/Seller'
import Home from './pages/Home'
import ServicesHome from './pages/ServicesHome'
import Catalog from './pages/Catalog'
import ProductPage from './pages/ProductPage'
import ServicesPage from './pages/ServicesPage'
import ServicePage from './pages/ServicePage'
import Booking from './pages/Booking'
import AdminAppointments from './pages/admin/Appointments'
import AdminSpecialists from './pages/admin/Specialists'
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
import GiftCertificates from './pages/GiftCertificates'
import Subscriptions from './pages/Subscriptions'
import Contacts from './pages/Contacts'
import AppPage from './pages/AppPage'
import NotFound from './pages/NotFound'
import MarketingHome from './pages/marketing/MarketingHome'
import SignupWizard from './pages/marketing/SignupWizard'
import { isPlatformHost } from './lib/host'
import { getDemoTenant, setDemoTenant } from './lib/demo'

/**
 * /shop/<slug>/... запоминает демо-магазин и перезагружает приложение,
 * чтобы все запросы ушли с заголовком X-Tenant-Slug.
 */
function DemoStorefront() {
  const { slug = '', '*': rest = '' } = useParams()
  useEffect(() => {
    if (!slug) return
    setDemoTenant(slug)
    const suffix = rest ? `/${rest}` : '/'
    window.location.replace(`${suffix}${window.location.search}${window.location.hash}`)
  }, [slug, rest])
  return <div className="loader-block">Открываем витрину…</div>
}

/** Главная выбирается по типу бизнеса арендатора: товары или услуги. */
function StorefrontHome() {
  const { site } = useSite()
  const serviceMode = site?.tenant?.business_type === 'services'
  return serviceMode ? <ServicesHome /> : <Home />
}

export default function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <AuthProvider>
          <CartProvider>
            <ToastProvider>
              <ScrollToTop />
              <Analytics />
              <UpdatePrompt />
              <Routes>
                <Route
                  path="/"
                  element={
                    isPlatformHost() && !getDemoTenant()
                      ? <MarketingHome />
                      : <PublicLayout><StorefrontHome /></PublicLayout>
                  }
                />
                <Route path="/start" element={<Navigate to="/" replace />} />
                <Route path="/new" element={<SignupWizard />} />
                <Route path="/start/new" element={<Navigate to="/new" replace />} />
                <Route path="/status" element={<PlatformStatus />} />
                <Route path="/shop/:slug/*" element={<DemoStorefront />} />
                <Route element={<PublicLayout />}>
                  <Route path="/catalog" element={<Catalog />} />
                  <Route path="/fish/:slug" element={<ProductPage />} />
                  <Route path="/services" element={<ServicesPage />} />
                  <Route path="/services/:slug" element={<ServicePage />} />
                  <Route path="/booking" element={<Booking />} />
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
                  <Route path="/gift" element={<GiftCertificates />} />
                  <Route path="/subscriptions" element={<Subscriptions />} />
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
                  <Route path="appointments" element={<AdminAppointments />} />
                  <Route path="specialists" element={<AdminSpecialists />} />
                  <Route path="reports" element={<Reports />} />
                  <Route path="notifications" element={<Notifications />} />
                  <Route path="catalog" element={<CatalogAdmin />} />
                  <Route path="inventory" element={<Inventory />} />
                  <Route path="suppliers" element={<Suppliers />} />
                  <Route path="promotions" element={<Promotions />} />
                  <Route path="promo-codes" element={<PromoCodes />} />
                  <Route path="reviews" element={<Reviews />} />
                  <Route path="delivery" element={<Delivery />} />
                  <Route path="users" element={<AdminUsers />} />
                  <Route path="services" element={<AdminServices />} />
                  <Route path="services/:code" element={<AdminServiceDetail />} />
                  <Route path="billing" element={<AdminBilling />} />
                  <Route path="settings" element={<SettingsAdmin />} />
                  <Route path="qr" element={<AdminQr />} />
                  <Route path="price-tags" element={<PriceTags />} />
                  <Route path="barcodes" element={<Barcodes />} />
                  <Route path="imports" element={<PriceImport />} />
                  <Route path="campaigns" element={<Campaigns />} />
                  <Route path="carts" element={<Carts />} />
                  <Route path="upsells" element={<Upsells />} />
                  <Route path="loyalty" element={<Loyalty />} />
                  <Route path="crm" element={<Crm />} />
                  <Route path="chat" element={<Chat />} />
                  <Route path="tasks" element={<Tasks />} />
                  <Route path="certificates" element={<Certificates />} />
                  <Route path="subscriptions" element={<SubscriptionsAdmin />} />
                  <Route path="*" element={<Navigate to="/admin" replace />} />
                </Route>

                <Route path="/platform/login" element={<PlatformLogin />} />
                <Route
                  path="/platform"
                  element={<PlatformLayout />}
                >
                  <Route index element={<PlatformOverview />} />
                  <Route path="tenants" element={<PlatformTenants />} />
                  <Route path="tenants/:id" element={<PlatformTenant />} />
                  <Route path="catalog" element={<PlatformCatalog />} />
                  <Route path="catalog/:code" element={<PlatformServiceDetail />} />
                  <Route path="analytics" element={<PlatformAnalytics />} />
                  <Route path="invoices" element={<PlatformInvoices />} />
                  <Route path="ops" element={<PlatformOps />} />
                  <Route path="audit" element={<PlatformAudit />} />
                  <Route path="incidents" element={<PlatformIncidents />} />
                  <Route path="settings" element={<PlatformSettings />} />
                  <Route path="team" element={<PlatformTeam />} />
                  <Route path="*" element={<Navigate to="/platform" replace />} />
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
