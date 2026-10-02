// Types mirroring the backend's response schemas.

export type Role = 'admin' | 'business' | 'driver'
export type DriverStatus = 'available' | 'busy' | 'offline'
export type OrderStatus = 'pending' | 'assigned' | 'picked_up' | 'delivered' | 'failed'
export type VehicleType = 'motorbike' | 'car' | 'bicycle'
export type BusinessCategory = 'restaurant' | 'pharmacy' | 'grocery' | 'retail' | 'other'

export interface Business {
  id: string
  name: string
  category: BusinessCategory
  phone: string
  address: string
  lat: number
  lng: number
}

export interface DriverProfile {
  id: string
  phone: string
  vehicle_type: VehicleType
  status: DriverStatus
  current_lat: number | null
  current_lng: number | null
  location_updated_at: string | null
}

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
  business: Business | null
  driver: DriverProfile | null
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export interface Order {
  id: string
  business_id: string
  driver_id: string | null
  status: OrderStatus
  customer_name: string
  customer_phone: string
  pickup_address: string
  pickup_lat: number
  pickup_lng: number
  dropoff_address: string
  dropoff_lat: number
  dropoff_lng: number
  notes: string | null
  deliver_by: string
  is_overdue: boolean
  assignment_attempts: number
  assigned_at: string | null
  accepted_at: string | null
  picked_up_at: string | null
  delivered_at: string | null
  failed_at: string | null
  failure_reason: string | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface StatsOverview {
  orders_by_status: Record<OrderStatus, number>
  drivers_by_status: Record<DriverStatus, number>
  overdue_open_orders: number
  last_24h: {
    delivered: number
    failed: number
    on_time_rate: number | null
    avg_delivery_minutes: number | null
  }
  generated_at: string
}

export interface OrderDetail extends Order {
  business: { id: string; name: string; phone: string }
  driver: { id: string; full_name: string; phone: string; vehicle_type: VehicleType } | null
}

export interface DriverAdmin {
  id: string
  user_id: string
  full_name: string
  email: string
  phone: string
  vehicle_type: VehicleType
  status: DriverStatus
  current_lat: number | null
  current_lng: number | null
  location_updated_at: string | null
  active_order_id: string | null
  created_at: string
}

export interface AuditEntry {
  id: number
  actor_id: string | null
  actor_email: string | null
  actor_name: string | null
  action: string
  entity_type: string
  entity_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface DemoInfo {
  enabled: boolean
  accounts: { role: Role; full_name: string; description: string }[]
}

export interface DispatchResult {
  result: { outcome: string; driver_id: string | null; distance_km: number | null }
  order: Order
}
