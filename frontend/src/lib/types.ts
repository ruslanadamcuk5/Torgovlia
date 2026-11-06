export type Role = 'customer' | 'seller' | 'admin'

export interface User {
  id: number
  phone: string
  full_name: string
  email?: string | null
  role: Role
  is_active: boolean
  is_phone_verified: boolean
  created_at: string
  last_login_at?: string | null
}

export interface WorkingDay {
  weekday: number
  label: string
  open: string
  close: string
  closed: boolean
}

export interface Socials {
  tiktok: string
  instagram: string
  youtube: string
  telegram: string
  viber: string
  vk: string
}

export interface Banner {
  id: string
  title: string
  subtitle: string
  image_url: string
  link: string
  button_text: string
  is_active: boolean
}

export interface Advantage {
  icon: string
  title: string
  text: string
}

export interface Settings {
  brand_name: string
  tagline: string
  legal_name: string
  unp: string
  legal_address: string
  city: string
  market_name: string
  pavilion: string
  address: string
  phone: string
  phone_secondary: string
  email: string
  working_hours: WorkingDay[]
  socials: Socials
  logo_url: string
  favicon_url: string
  hero_image_url: string
  hero_badge: string
  hero_title: string
  hero_subtitle: string
  hero_note: string
  about_title: string
  about_text: string
  announcement: string
  announcement_active: boolean
  banners: Banner[]
  advantages: Advantage[]
  pickup_rules: string
  payment_note: string
  privacy_policy: string
  offer_text: string
  contacts_extra: string
  min_order_amount: number
  lead_time_minutes: number
  slot_step_minutes: number
  booking_days_ahead: number
  slot_capacity: number
  max_items: number
  android_apk_url: string
  android_app_version: string
  android_app_size: string
  app_install_url: string
  seo_title: string
  seo_description: string
  seo_keywords: string
  map_url: string
  map_embed_url: string
}

export interface TodayInfo {
  date: string
  open: string | null
  close: string | null
  is_closed: boolean
  label: string
}

export interface SiteInfo {
  settings: Settings
  updated_at: string | null
  products_count: number
  today: TodayInfo
}

export interface Category {
  id: number
  slug: string
  title: string
  description: string
  image_url?: string | null
  sort_order: number
  is_active: boolean
  products_count: number
}

export interface Nutrition {
  kcal?: number
  protein?: number
  fat?: number
  omega3?: number
  [key: string]: number | undefined
}

export interface Product {
  id: number
  slug: string
  title: string
  subtitle: string
  category_id?: number | null
  category_title?: string | null
  category_slug?: string | null
  unit: 'kg' | 'piece'
  price: number
  final_price: number
  discount_percent: number
  is_daily_deal: boolean
  is_available: boolean
  is_active: boolean
  stock?: number | null
  weight_note: string
  image_url?: string | null
  gallery: string[]
  badges: string[]
  short_description: string
  description: string
  origin: string
  season: string
  nutrition: Nutrition
  cooking_tips: string
  storage_tips: string
  sort_order: number
  can_order: boolean
}

export interface ArticleShort {
  slug: string
  title: string
  subtitle: string
  image_url?: string | null
  short_description: string
  reading_minutes: number
  category?: string | null
  season: string
}

export interface OrderItem {
  id: number
  product_id?: number | null
  title: string
  image_url?: string | null
  unit: 'kg' | 'piece'
  price: number
  quantity: number
  line_total: number
}

export type OrderStatus = 'new' | 'confirmed' | 'ready' | 'completed' | 'cancelled' | 'rejected'

export interface Order {
  id: number
  number: string
  user_id?: number | null
  customer_name: string
  phone: string
  phone_formatted: string
  pickup_date: string
  pickup_time: string
  status: OrderStatus
  comment: string
  admin_comment: string
  total_amount: number
  items_count: number
  source: string
  status_history: { status: string; at: string; by: string; comment?: string }[]
  created_at: string
  updated_at: string
  items: OrderItem[]
}

export interface Slot {
  time: string
  available: boolean
  capacity_left: number
}

export interface Slots {
  date: string
  is_open: boolean
  slots: Slot[]
  message: string
}

export interface Stats {
  orders_total: number
  orders_new: number
  orders_today: number
  revenue_month: number
  revenue_today: number
  users_total: number
  customers_total: number
  products_active: number
  products_out_of_stock: number
  avg_order: number
  top_products: { title: string; quantity: number; revenue: number }[]
}

export interface QrItem {
  kind: 'site' | 'product'
  target: string
  title: string
  url: string
  qr_url: string
  download_url: string
}

export interface AdminUser extends User {
  orders_count: number
  last_order_at?: string | null
  phone_formatted: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface PhoneRequest {
  verification_id: string
  phone: string
  phone_formatted: string
  expires_in: number
  sms_sent: boolean
  debug_code?: string | null
  message: string
}

export interface PhoneConfirm {
  phone_token: string
  phone: string
  phone_formatted: string
  purpose: string
  expires_in: number
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface CartLine {
  productId: number
  slug: string
  title: string
  image_url?: string | null
  unit: 'kg' | 'piece'
  price: number
  quantity: number
  is_available: boolean
}

// ─── Сервисы и платформа ────────────────────────────────────────────

export type ServiceTier = 'free' | 'start' | 'business' | 'pro' | 'addon' | 'platform'

export interface ServiceItem {
  code: string
  title: string
  group: string
  description: string
  tier: ServiceTier
  price_month: number
  status: string
  enabled: boolean
  included_in_plan: boolean
  can_enable: boolean
  can_disable: boolean
  reason: string
  dependencies: string[]
  trial_days: number
  locked_by_platform: boolean
  icon: string
}

export interface ServiceList {
  plan_code: string
  items: ServiceItem[]
}

export interface PlatformUser {
  id: number
  phone: string
  full_name: string
  email?: string | null
  role: string
  is_active: boolean
  created_at: string
  last_login_at?: string | null
}

export interface PlatformTokenResponse {
  access_token: string
  token_type: string
  user: PlatformUser
}

export interface TenantDomain {
  id: number
  host: string
  kind: 'subdomain' | 'custom' | 'alias'
  is_primary: boolean
  verified_at?: string | null
  ssl_status: string
  dns_status: string
  created_at: string
}

export interface Tenant {
  id: number
  slug: string
  name: string
  status: string
  plan_code: string
  category_preset?: string | null
  locale: string
  currency: string
  timezone: string
  is_demo: boolean
  created_at: string
  updated_at: string
  domains: TenantDomain[]
}

export interface PlatformStats {
  tenants_total: number
  tenants_active: number
  tenants_trial: number
  tenants_suspended: number
  domains_total: number
  by_status: Record<string, number>
}

export interface PlatformPlan {
  code: string
  title: string
  description: string
  price_month: number
  price_year: number
  quotas: Record<string, number>
}

export interface PlatformCatalogService {
  code: string
  title: string
  group: string
  description: string
  tier: ServiceTier
  price_month: number
  dependencies: string[]
  included: Record<string, boolean>
}

export interface PlatformCatalog {
  plans: PlatformPlan[]
  services: PlatformCatalogService[]
}

export interface Invoice {
  id: number
  number: string
  kind: string
  status: string
  plan_code?: string | null
  service_code?: string | null
  description: string
  amount: number
  currency: string
  period_start?: string | null
  period_end?: string | null
  due_at?: string | null
  paid_at?: string | null
  payment_method: string
  note: string
  created_at: string
  tenant_id?: number
}

export interface PlanInfo {
  code: string
  title: string
  description: string
  price_month: number
  price_year: number
  quotas: Record<string, number>
}

export interface BillingOverview {
  plan_code: string
  plan_title: string
  price_month: number
  subscription_status: string
  period_end?: string | null
  pending_plan_code?: string | null
  open_invoices_total: number
  invoices: Invoice[]
  plans: PlanInfo[]
}
