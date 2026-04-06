<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { loadStripe, type Stripe, type StripeCardElement, type StripeElements, type StripeCardElementChangeEvent } from '@stripe/stripe-js'
import { useRouter, useRoute } from 'vue-router'
import { usePatientSessionStore } from '@/stores/patientSessionStore'
import {
  PostConsultService,
  type ConsultationData,
  type Delivery,
  type MakePaymentPayload,
} from '../domains/consultation/postConsultService'

const router = useRouter()
const route = useRoute()
const patientSessionStore = usePatientSessionStore()

function parseRouteId(value: string | number | null | undefined | Array<string | number | null>): number | undefined {
  if (value == null) return undefined
  const raw = Array.isArray(value) ? value[0] : value
  const numeric = Number(raw)
  return isNaN(numeric) ? undefined : numeric
}

const loading = ref(true)
const consultation = ref<ConsultationData | null>(null)

const deliveryAddress = ref('')
const deliveryState = ref<'idle' | 'scheduling' | 'scheduled'>('idle')
const delivery = ref<Delivery | null>(null)
const isAddressConfirmed = ref(false)

const email = ref('')
const defaultPaymentMethodId = import.meta.env.VITE_STRIPE_PAYMENT_METHOD || 'pm_card_visa'
const stripePublishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || ''

const stripe = ref<Stripe | null>(null)
const elements = ref<StripeElements | null>(null)
const card = ref<StripeCardElement | null>(null)
const cardElementRef = ref<HTMLDivElement | null>(null)
const cardError = ref('')
const paymentState = ref<'idle' | 'processing' | 'paid'>('idle')

const formattedDate = computed(() => {
  if (!consultation.value) return ''
  return new Date(consultation.value.appointment.datetime).toLocaleString('en-SG', {
    weekday: 'short', day: 'numeric', month: 'short',
    year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
})
const canPay = computed(() => {
  return isAddressConfirmed.value && paymentState.value === 'idle'
})
function confirmAddress() {
  if (!deliveryAddress.value.trim()) return
  isAddressConfirmed.value = true
}

async function setupStripe() {
  if (!stripePublishableKey) {
    cardError.value = 'Stripe publishable key is not configured.'
    return
  }

  const stripeInstance = await loadStripe(stripePublishableKey)
  if (!stripeInstance) {
    cardError.value = 'Stripe failed to initialize.'
    return
  }

  stripe.value = stripeInstance
  elements.value = stripeInstance.elements()

  await nextTick()

  if (!cardElementRef.value || !elements.value) return

  const cardElement = elements.value.create('card', {
    style: {
      base: {
        fontSize: '16px',
        color: '#ffffff',
        '::placeholder': { color: '#aab7c4' },
      },
      invalid: {
        color: '#ff6b6b',
      },
    },
    hidePostalCode: true,
  })

  card.value = cardElement
  cardElement.mount(cardElementRef.value)
  cardElement.on('change', (event: StripeCardElementChangeEvent) => {
    cardError.value = event.error?.message ?? ''
  })
}

async function createPaymentMethod(): Promise<string | null> {
  if (stripe.value && card.value) {
    const result = await stripe.value.createPaymentMethod({
      type: 'card',
      card: card.value,
    })

    if (result.error) {
      cardError.value = result.error.message ?? 'Payment method creation failed.'
      return null
    }

    return result.paymentMethod?.id ?? null
  }

  if (!stripePublishableKey) {
    return defaultPaymentMethodId
  }

  cardError.value = 'Stripe has not been initialized properly.'
  return null
}

onMounted(async () => {
  const patientId = parseRouteId(route.query.patientId) ?? 1
  const appointmentId = parseRouteId(route.query.appointmentId)
  consultation.value = await PostConsultService.getConsultation(patientId, appointmentId)
  const storePatient = patientSessionStore.selectedPatient
  const patient = storePatient

  if (patient?.address) {
    deliveryAddress.value = patient.address
  }

  email.value = storePatient?.email || patient?.email || ''
  if (consultation.value.delivery) {
    delivery.value = consultation.value.delivery
    deliveryState.value = 'scheduled'
  }
  if (consultation.value.invoice.status === 'PAID') {
    paymentState.value = 'paid'
  }
  loading.value = false
  await setupStripe()
})

async function makePayment() {
  if (!consultation.value || paymentState.value !== 'idle') return
  paymentState.value = 'processing'

  const patient_address = deliveryAddress.value.trim() || delivery.value?.address || consultation.value.delivery?.address || ''
  if (!patient_address) {
    cardError.value = 'Please provide a delivery address before paying.'
    paymentState.value = 'idle'
    return
  }

  let reserve_amount = consultation.value.prescription.items.reduce(
    (sum: number, item: { quantity: number }) => sum + (item.quantity ?? 0),
    0,
  )
  if (reserve_amount <= 0) {
    reserve_amount = 1
  }

  const payload: MakePaymentPayload = {
    appointment_id: consultation.value.appointment.id,
    patient_id: consultation.value.appointment.patient_id,
    amount: Math.round(consultation.value.invoice.total),
    currency: consultation.value.invoice.currency.toLowerCase(),
    paymentMethodId: '',
    patient_address,
    reserve_amount,
    email: email.value,
  }

  try {
    const paymentMethodId = await createPaymentMethod()
    if (!paymentMethodId) {
      throw new Error(cardError.value || 'Payment method creation failed')
    }

    payload.paymentMethodId = paymentMethodId
    const response = await PostConsultService.makePayment(payload)
    if (response.code === 200) {
      paymentState.value = 'paid'
      consultation.value.invoice.status = 'PAID'
    } else {
      throw new Error(response.message || 'Payment failed')
    }
  } catch (error) {
    paymentState.value = 'idle'
    if (error instanceof Error) {
      cardError.value = error.message
    }
  }
}

function fmt(amount: number) {
  return amount.toFixed(2)
}
</script>

<template>
  <div class="pc-page">
    <div class="bg-ambient" />

    <!-- Navbar -->
    <nav class="pc-nav">
      <div class="logo" @click="router.push('/')">
        <img src="/doctor-everywhere-logo.png" alt="Doctor Everywhere" class="logo-img" />
        <span class="logo-text">doctor everywhere</span>
      </div>
      <button class="back-btn" @click="router.back()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
          <path d="M19 12H5M12 5l-7 7 7 7" />
        </svg>
        Back
      </button>
    </nav>

    <!-- Loading -->
    <main class="pc-main" v-if="loading">
      <div class="loading-wrap">
        <div class="spinner-ring" />
        <p class="loading-text">Loading your consultation summary…</p>
      </div>
    </main>

    <!-- Content -->
    <main class="pc-main" v-else-if="consultation">
      <div class="pc-content">

        <!-- Page header -->
        <div class="page-header">
          <div>
            <h1 class="page-title">Post-Consultation Summary</h1>
            <span class="consult-id">{{ consultation.appointment.consult_id }}</span>
          </div>
          <span class="consult-date">{{ formattedDate }}</span>
        </div>

        <!-- ─── 1. Appointment ─────────────────────────────────── -->
        <section class="pc-card">
          <div class="card-header">
            <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            <span class="card-title">Consultation</span>
          </div>

          <div class="doctor-row">
            <div class="doctor-avatar">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="26" height="26">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <div>
              <p class="doctor-name">{{ consultation.appointment.doctor.name }}</p>
              <p class="doctor-specialty">{{ consultation.appointment.doctor.specialty }}</p>
            </div>
          </div>

          <div class="notes-box">
            <p class="notes-label">Doctor's Notes</p>
            <p class="notes-text">{{ consultation.appointment.notes || 'No doctor notes recorded for this consultation.' }}</p>
          </div>
        </section>

        <!-- ─── 2. Prescription ───────────────────────────────── -->
        <section class="pc-card">
          <div class="card-header">
            <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8z" />
              <polyline points="17 2 17 8 11 8" />
              <line x1="9" y1="13" x2="15" y2="13" /><line x1="9" y1="17" x2="12" y2="17" />
            </svg>
            <span class="card-title">Prescription</span>
            <span class="card-badge">{{ consultation.prescription.items.length }} items</span>
          </div>

          <ul class="rx-list">
            <li
              v-for="(item, i) in consultation.prescription.items"
              :key="item.id"
              class="rx-item"
              :class="{ 'rx-item--border': i < consultation.prescription.items.length - 1 }"
            >
              <div class="rx-top">
                <div>
                  <span class="rx-name">{{ item.name }}</span>
                  <span v-if="item.dosage" class="rx-dosage">{{ item.dosage }}</span>
                </div>
                <div class="rx-right">
                  <span class="rx-qty">{{ item.quantity }} {{ item.unit }}</span>
                  <span v-if="item.line_total != null" class="rx-price">
                    {{ consultation.invoice.currency }} {{ fmt(Number(item.line_total)) }}
                  </span>
                </div>
              </div>
              <p v-if="item.frequency || item.duration" class="rx-freq">
                {{ [item.frequency, item.duration].filter(Boolean).join(' · ') }}
              </p>
              <p v-if="item.instructions" class="rx-instructions">{{ item.instructions }}</p>
              <p v-else-if="!item.dosage" class="rx-instructions rx-instructions--muted">Dosage instructions unavailable.</p>
            </li>
          </ul>
        </section>

        <!-- ─── 3. Medicine Delivery ──────────────────────────── -->
        <section class="pc-card">
          <div class="card-header">
            <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <rect x="1" y="3" width="15" height="13" rx="1" />
              <path d="M16 8h4l3 5v3h-7V8z" /><circle cx="5.5" cy="18.5" r="2.5" /><circle cx="18.5" cy="18.5" r="2.5" />
            </svg>
            <span class="card-title">Medicine Delivery</span>
          </div>

          <!-- Idle / form -->
          <div v-if="deliveryState === 'idle'" class="delivery-form">
            <p class="delivery-hint">Please confirm your delivery address to have your medicine delivered after payment.</p>
            <div class="input-wrap">
              <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
              </svg>
              <input
                v-model="deliveryAddress"
                class="address-input"
                :disabled="isAddressConfirmed"
                placeholder="e.g. 80 Stamford Rd, Singapore 178902"
                @keyup.enter="isAddressConfirmed = true"
              />
            </div>
            <button
              class="action-btn"
              :disabled="!deliveryAddress.trim() || isAddressConfirmed"
              @click="confirmAddress"
            >
              {{ isAddressConfirmed ? 'Address Confirmed' : 'Confirm Address' }}
              <!-- <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="15" height="15">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg> -->
            </button>
          </div>

          <!-- Scheduling -->
          <div v-else-if="deliveryState === 'scheduling'" class="delivery-loading">
            <div class="spinner-ring spinner-sm" />
            <p class="delivery-hint">Scheduling your delivery…</p>
          </div>

          <!-- Scheduled -->
          <div v-else-if="deliveryState === 'scheduled' && delivery" class="delivery-confirmed">
            <div class="status-badge status-badge--green">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Delivery Scheduled
            </div>
            <div class="delivery-details">
              <div class="delivery-detail-row">
                <span class="detail-label">Tracking</span>
                <span class="detail-value tracking-num">{{ delivery.tracking_number }}</span>
              </div>
              <div class="delivery-detail-row">
                <span class="detail-label">Address</span>
                <span class="detail-value">{{ delivery.address }}</span>
              </div>
              <div class="delivery-detail-row">
                <span class="detail-label">Est. Delivery</span>
                <span class="detail-value">{{ delivery.estimated_date }}</span>
              </div>
              <div class="delivery-detail-row">
                <span class="detail-label">Status</span>
                <span class="detail-value">{{ delivery.status }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ─── 4. Payment ─────────────────────────────────────── -->
        <section class="pc-card">
          <div class="card-header">
            <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
            <span class="card-title">Payment</span>
            <span v-if="paymentState === 'paid'" class="card-badge card-badge--green">Paid</span>
          </div>

          <!-- Invoice breakdown -->
          <div class="invoice-table">
            <div class="invoice-row">
              <span>Consultation Fee</span>
              <span>{{ consultation.invoice.currency }} {{ fmt(consultation.invoice.consultation_fee) }}</span>
            </div>
            <div class="invoice-row">
              <span>Medication</span>
              <span>{{ consultation.invoice.currency }} {{ fmt(consultation.invoice.medicine_fee) }}</span>
            </div>
            <div class="invoice-divider" />
            <div class="invoice-row invoice-row--total">
              <span>Total</span>
              <span>{{ consultation.invoice.currency }} {{ fmt(consultation.invoice.total) }}</span>
            </div>
          </div>

          <div v-show="paymentState === 'idle'" class="stripe-card-wrapper">
            <label class="stripe-label">Card details</label>
            <div ref="cardElementRef" class="stripe-card"></div>
            <p v-if="cardError" class="stripe-error">{{ cardError }}</p>
            <p v-else-if="!stripePublishableKey" class="stripe-hint">
              Stripe publishable key is not configured. Falling back to a test payment token.
            </p>
          </div>

          <!-- Pay button -->
          <div v-if="paymentState === 'idle'">
            <button class="action-btn pay-btn" :disabled="!canPay" @click="makePayment">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2" /><line x1="1" y1="10" x2="23" y2="10" />
              </svg>
              Pay {{ consultation.invoice.currency }} {{ fmt(consultation.invoice.total) }}
            </button>
            <p class="pay-sub">Processed securely via Stripe. You'll receive an email receipt.</p>
          </div>

          <!-- Processing -->
          <div v-else-if="paymentState === 'processing'" class="delivery-loading">
            <div class="spinner-ring spinner-sm" />
            <p class="delivery-hint">Processing payment…</p>
          </div>

          <!-- Paid -->
          <div v-else-if="paymentState === 'paid'" class="payment-success">
            <div class="status-badge status-badge--green">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Payment Confirmed
            </div>
            <p class="delivery-hint">A receipt has been sent to your email.</p>
          </div>
        </section>

        <!-- Done CTA -->
        <button class="home-btn" @click="router.push('/')">Back to Home</button>

      </div>
    </main>
  </div>
</template>

<style scoped>
/* ── Base ───────────────────────────────────────────────────── */
.pc-page {
  min-height: 100vh;
  background: #111d15;
  color: #fff;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  position: relative;
}

.bg-ambient {
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 65% 50% at 70% 20%, rgba(20, 80, 35, 0.35) 0%, transparent 65%),
    radial-gradient(ellipse 45% 45% at 10% 80%, rgba(10, 50, 20, 0.2) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}

/* ── Navbar ─────────────────────────────────────────────────── */
.pc-nav {
  position: sticky;
  top: 0;
  z-index: 200;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2.5rem;
  background: rgba(17, 29, 21, 0.85);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  cursor: pointer;
  user-select: none;
}

.logo-img {
  height: 34px; width: 34px;
  object-fit: contain;
  mix-blend-mode: screen;
  flex-shrink: 0;
}

.logo-text {
  font-weight: 700;
  font-size: 0.9rem;
  color: #fff;
  letter-spacing: -0.01em;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.6rem;
  padding: 0.4rem 0.85rem;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.82rem;
  font-family: 'Inter', sans-serif;
  cursor: pointer;
  transition: background 0.18s, color 0.18s;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }
}

/* ── Main ───────────────────────────────────────────────────── */
.pc-main {
  position: relative;
  z-index: 10;
  padding: 2.5rem 1.5rem 5rem;
  display: flex;
  justify-content: center;
}

.pc-content {
  width: 100%;
  max-width: 660px;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* ── Loading ────────────────────────────────────────────────── */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding-top: 6rem;
}

.loading-text {
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.4);
}

.spinner-ring {
  width: 48px; height: 48px;
  border-radius: 50%;
  border: 3px solid rgba(34, 197, 94, 0.15);
  border-top-color: #22c55e;
  animation: spin 0.9s linear infinite;
}

.spinner-sm {
  width: 28px; height: 28px;
  border-width: 2.5px;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Page header ────────────────────────────────────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.page-title {
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin: 0 0 0.3rem;
}

.consult-id {
  font-size: 0.75rem;
  color: #4ade80;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.consult-date {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
  padding-top: 0.35rem;
}

/* ── Cards ──────────────────────────────────────────────────── */
.pc-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1.25rem;
  padding: 1.4rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.card-icon {
  width: 17px; height: 17px;
  color: #4ade80;
  flex-shrink: 0;
}

.card-title {
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.45);
}

.card-badge {
  margin-left: auto;
  font-size: 0.72rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 2rem;
  padding: 0.2rem 0.7rem;
  color: rgba(255, 255, 255, 0.5);
}

.card-badge--green {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

/* ── Appointment ────────────────────────────────────────────── */
.doctor-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.doctor-avatar {
  width: 48px; height: 48px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4ade80;
  flex-shrink: 0;
}

.doctor-name {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 0.2rem;
}

.doctor-specialty {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.45);
  margin: 0;
}

.notes-box {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem;
}

.notes-label {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.3);
  margin: 0 0 0.5rem;
}

.notes-text {
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.7;
  margin: 0;
}

/* ── Prescription ───────────────────────────────────────────── */
.rx-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
}

.rx-item {
  padding: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;

  &.rx-item--border {
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  &:first-child { padding-top: 0; }
  &:last-child  { padding-bottom: 0; }
}

.rx-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
}

.rx-right {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
}

.rx-name {
  font-size: 0.97rem;
  font-weight: 700;
  color: #fff;
  margin-right: 0.5rem;
}

.rx-dosage {
  font-size: 0.82rem;
  color: #4ade80;
  font-weight: 600;
}

.rx-qty {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 2rem;
  padding: 0.15rem 0.6rem;
}

.rx-price {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.65);
  font-weight: 600;
}

.rx-freq {
  font-size: 0.83rem;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.rx-instructions {
  font-size: 0.79rem;
  color: rgba(255, 255, 255, 0.3);
  margin: 0;
  font-style: italic;
}

.rx-instructions--muted {
  color: rgba(255, 255, 255, 0.22);
}

/* ── Delivery ───────────────────────────────────────────────── */
.delivery-hint {
  font-size: 0.87rem;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.6;
  margin: 0;
}

.input-wrap {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.8rem;
  padding: 0.75rem 1rem;
  transition: border-color 0.18s;

  &:focus-within {
    border-color: rgba(34, 197, 94, 0.4);
  }
}

.input-icon {
  width: 16px; height: 16px;
  color: rgba(255, 255, 255, 0.3);
  flex-shrink: 0;
}

.address-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 0.88rem;
  font-family: 'Inter', sans-serif;

  &::placeholder {
    color: rgba(255, 255, 255, 0.25);
  }
}

.delivery-form {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.delivery-loading {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.delivery-confirmed {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
  font-weight: 600;
  border-radius: 2rem;
  padding: 0.35rem 0.85rem;
  width: fit-content;
}

.status-badge--green {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.delivery-details {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem;
}

.delivery-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  font-size: 0.85rem;
}

.detail-label {
  color: rgba(255, 255, 255, 0.35);
  flex-shrink: 0;
}

.detail-value {
  color: rgba(255, 255, 255, 0.75);
  text-align: right;
}

.tracking-num {
  color: #4ade80;
  font-weight: 600;
  font-size: 0.82rem;
  letter-spacing: 0.04em;
}

/* ── Payment ────────────────────────────────────────────────── */
.invoice-table {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem;
}

.invoice-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.55);
}

.invoice-divider {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  margin: 0.2rem 0;
}

.invoice-row--total {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
}

.pay-sub {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.28);
  text-align: center;
  margin: 0.6rem 0 0;
}

.stripe-card-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-top: 1rem;
}

.stripe-label {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.55);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.stripe-card {
  min-height: 52px;
  padding: 0.95rem 0.95rem;
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.stripe-error {
  color: #f87171;
  font-size: 0.82rem;
  margin: 0;
}

.stripe-hint {
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.82rem;
  margin: 0;
}

.payment-success {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

/* ── Buttons ────────────────────────────────────────────────── */
.action-btn {
  width: 100%;
  background: #22c55e;
  border: none;
  border-radius: 0.85rem;
  padding: 0.85rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.92rem;
  font-weight: 700;
  font-family: 'Inter', sans-serif;
  letter-spacing: -0.01em;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(34, 197, 94, 0.25);
  transition: background 0.2s, box-shadow 0.2s, transform 0.1s;

  &:hover:not(:disabled) {
    background: #16a34a;
    box-shadow: 0 6px 28px rgba(34, 197, 94, 0.4);
  }

  &:active:not(:disabled) { transform: scale(0.97); }

  &:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
}

.pay-btn {
  margin-top: 0.25rem;
}

.home-btn {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.85rem;
  padding: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.85rem;
  font-family: 'Inter', sans-serif;
  cursor: pointer;
  transition: background 0.18s, color 0.18s, border-color 0.18s;
  margin-top: 0.5rem;

  &:hover {
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.7);
    border-color: rgba(255, 255, 255, 0.18);
  }
}
</style>
