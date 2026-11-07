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
  template: string
  accent_color: string
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

export interface ThemeInfo {
  code: string
  title: string
  description: string
  mood: string
  tokens: Record<string, string>
}

export interface DesignTemplate extends ThemeInfo {}

export interface SiteInfo {
  settings: Settings
  theme?: ThemeInfo
  features?: { promo_codes: boolean }
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
  discount_amount?: number
  promo_code?: string
  items_count: number
  source: string
  status_history: { status: string; at: string; by: string; comment?: string }[]
  created_at: string
  updated_at: string
  items: OrderItem[]
}

export interface PromoCode {
  id: number
  code: string
  kind: 'percent' | 'fixed'
  value: number
  min_order: number
  max_uses: number
  used_count: number
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
  note: string
  status: 'active' | 'scheduled' | 'expired' | 'used_up' | 'disabled'
  created_at: string | null
  updated_at: string | null
}

export interface PromoValidation {
  code: string
  kind: 'percent' | 'fixed'
  value: number
  discount: number
  total: number
  note: string
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

export interface OnboardingStep {
  code: string
  title: string
  description: string
  done: boolean
  href: string
}

export interface Onboarding {
  tenant_slug: string
  steps: OnboardingStep[]
  done: number
  total: number
  percent: number
  complete: boolean
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
  totp_enabled?: boolean
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
  hosting_provider: string
  hosting_tariff: string
  hosting_account: string
  deploy_status: string
  deploy_url: string
  ops_note: string
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
  payment_methods: PaymentMethod[]
}

export interface CategoryPreset {
  code: string
  title: string
  description: string
  examples: string[]
  icon: string
}

export interface SignupCatalog {
  plans: PlanInfo[]
  categories: CategoryPreset[]
}

export interface PaymentMethod {
  code: string
  title: string
  description: string
  instructions: string
  status: 'available' | 'setup'
  icon: string
}

export interface SignupResult {
  tenant_id: number
  slug: string
  name: string
  host: string
  status: string
  plan_code: string
  plan_title: string
  price_month: number
  owner_phone: string
  login_path: string
  invoice?: Invoice | null
}


export interface ProvisioningStep {
  code: string
  title: string
  detail: string
  status: 'pending' | 'in_progress' | 'done' | 'blocked' | 'skipped' | string
  note: string
  updated_at?: string | null
}

export interface ProvisioningJob {
  id: number
  tenant_id: number
  kind: string
  status: 'queued' | 'in_progress' | 'done' | 'blocked' | 'canceled' | string
  status_label: string
  steps: ProvisioningStep[]
  progress: number
  steps_done: number
  steps_total: number
  note: string
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface HostingInfo {
  hosting_provider: string
  hosting_tariff: string
  hosting_account: string
  deploy_status: string
  deploy_status_label: string
  deploy_url: string
  ops_note: string
  primary_host: string
  ssl_status: string
  dns_status: string
}

export interface ProvisioningState {
  tenant_id: number
  job?: ProvisioningJob | null
  template: ProvisioningStep[]
  hosting: HostingInfo
}

export interface UptimeSummary {
  checks: number
  uptime_24h: number | null
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  last_ok: boolean | null
  last_status_code: number | null
  last_latency_ms: number | null
  last_checked_at: string | null
}

export interface TenantHealth {
  tenant_id: number
  slug: string
  name: string
  tenant_status: string
  deploy_status: string
  deploy_status_label: string
  deploy_url: string
  primary_host: string
  ssl_status: string
  dns_status: string
  open_invoices: number
  job_id?: number | null
  job_status?: string | null
  job_progress: number
  level: 'ok' | 'attention' | 'error' | string
  issues: string[]
  uptime?: UptimeSummary
}

export interface UptimeCheck {
  id: number
  tenant_id: number
  url: string
  ok: boolean
  status_code: number | null
  latency_ms: number
  error: string
  checked_at: string
}

export interface UptimeRunResult {
  checked: number
  ok: number
  failed: number
  results: UptimeCheck[]
}

export interface SupportTemplate {
  code: string
  title: string
  body: string
}

export interface OpsOverview {
  tenants_total: number
  deployed: number
  by_status: Record<string, number>
  by_level: Record<string, number>
  queue_total: number
  attention_total: number
  queue: TenantHealth[]
  attention: TenantHealth[]
  items: TenantHealth[]
}

export interface DashboardMetrics {
  tenants_total: number
  tenants_active: number
  tenants_onboarding: number
  tenants_suspended: number
  tenants_archived: number
  new_30d: number
  mrr: number
  mrr_plans: number
  mrr_addons: number
  arr: number
  paying_tenants: number
  paid_30d: number
  paid_month: number
  open_invoices_total: number
  open_invoices_count: number
  queue_total: number
  attention_total: number
  by_status: Record<string, number>
}

export interface LifecycleAction {
  action: 'suspend' | 'resume' | 'archive' | 'restore'
  label: string
  enabled: boolean
}

export interface LifecycleState {
  tenant_id: number
  status: string
  actions: LifecycleAction[]
  hosting: HostingInfo
}

export interface ImpersonationResult {
  access_token: string
  token_type: string
  expires_in: number
  tenant_id: number
  tenant_slug: string
  host: string
  user: {
    id: number
    phone: string
    full_name: string
    role: string
  }
}

export interface AlertItem {
  tenant_id: number
  slug: string
  name: string
  severity: 'warning' | 'error'
  message: string
}

export interface AlertsDigest {
  generated_at: string
  total: number
  errors: number
  warnings: number
  telegram_configured: boolean
  alerts: AlertItem[]
  text: string
}

export interface AlertSendResult {
  sent: boolean
  count: number
  message: string
}

export interface SupportTicket {
  id: number
  tenant_id: number
  subject: string
  body: string
  priority: 'low' | 'normal' | 'high'
  status: 'open' | 'closed'
  author: string
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export interface AuditEntry {
  id: number
  tenant_id?: number | null
  user_id?: number | null
  platform_user_id?: number | null
  actor: string
  action: string
  entity: string
  entity_id?: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface AuditPage {
  items: AuditEntry[]
  total: number
  limit: number
  offset: number
}

export interface IncidentUpdate {
  id: number
  status: 'investigating' | 'identified' | 'monitoring' | 'resolved'
  body: string
  author: string
  created_at: string
}

export interface Incident {
  id: number
  tenant_id?: number | null
  tenant_name?: string | null
  title: string
  body: string
  severity: 'minor' | 'major' | 'critical'
  status: 'investigating' | 'identified' | 'monitoring' | 'resolved'
  created_by: string
  started_at: string
  resolved_at?: string | null
  created_at: string
  updated_at: string
  updates: IncidentUpdate[]
}

export interface IncidentList {
  items: Incident[]
  total: number
}

export interface StatusIncidentUpdate {
  id: number
  status: string
  body: string
  created_at: string
}

export interface StatusIncident {
  id: number
  title: string
  body: string
  severity: 'minor' | 'major' | 'critical'
  status: string
  started_at: string
  resolved_at?: string | null
  updates: StatusIncidentUpdate[]
}

export interface StatusPage {
  updated_at: string
  brand_name?: string
  maintenance_notice?: string
  active: StatusIncident[]
  resolved: StatusIncident[]
  overall: 'operational' | 'degraded' | 'outage'
}

export interface PlatformSettings {
  brand_name: string
  support_email: string
  support_phone: string
  default_plan_code: string
  allow_signups: boolean
  max_tenants: number
  maintenance_notice: string
  payment_instructions: string
  sms_sender: string
  updated_at?: string | null
}

export interface TwoFactorStatus {
  enabled: boolean
  pending: boolean
}

export interface TwoFactorSetup {
  secret: string
  uri: string
}
