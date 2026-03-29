<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import apiClient from '../../core/apiClient'

type DashboardState = 'idle' | 'calling' | 'active' | 'error'

interface Patient {
  patient_id: string
  patient_name: string
  email: string
}

interface SetupConsultationResponse {
  code: number
  patient: Patient
  appointment_id: number
  meet_link: string
  start_url: string
}

const state = ref<DashboardState>('idle')
const currentPatient = ref<Patient | null>(null)
const zoomStartUrl = ref<string | null>(null)
const currentAppointmentId = ref<number | null>(null)
const errorMsg = ref('')
const showEmptyToast = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function triggerEmptyToast() {
  if (toastTimer) clearTimeout(toastTimer)
  showEmptyToast.value = true
  toastTimer = setTimeout(() => { showEmptyToast.value = false }, 3000)
}

// HARD CODED DOCTOR ID
const DOCTOR_ID = 1

async function callNextPatient(isNoShow = false) {
  state.value = 'calling'
  try {
    const payload: Record<string, unknown> = { doctor_id: DOCTOR_ID }
    if (isNoShow && currentAppointmentId.value) {
      payload.no_show_appointment_id = currentAppointmentId.value
    }
    const { data } = await apiClient.post<SetupConsultationResponse>(
      '/setup-consultation/next-patient',
      payload
    )
    currentPatient.value = data.patient
    zoomStartUrl.value = data.start_url
    currentAppointmentId.value = data.appointment_id
    state.value = 'active'
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      state.value = 'idle'
      currentPatient.value = null
      zoomStartUrl.value = null
      currentAppointmentId.value = null
      triggerEmptyToast()
    } else {
      state.value = 'error'
      errorMsg.value = err instanceof Error ? err.message : 'Something went wrong. Please try again.'
    }
  }
}

function markDone() {
  currentPatient.value = null
  zoomStartUrl.value = null
  currentAppointmentId.value = null
  state.value = 'idle'
}

function openZoom() {
  if (zoomStartUrl.value) {
    window.open(zoomStartUrl.value, '_blank', 'noopener')
  }
}
</script>

<template>
  <div class="dashboard-page">
    <div class="bg-ambient" />

    <!-- Navbar -->
    <nav class="dashboard-nav">
      <div class="logo">
        <img src="/doctor-everywhere-logo.png" alt="Doctor Everywhere" class="logo-img" />
        <span class="logo-text">doctor everywhere</span>
      </div>
      <span class="nav-role">Doctor Dashboard</span>
    </nav>

    <!-- Content -->
    <main class="dashboard-main">

      <!-- ── Idle ── -->
      <div v-if="state === 'idle'" class="state-card">
        <div class="stethoscope-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="36" height="36" style="color: #4ade80">
            <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6 6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
            <path d="M8 15v1a6 6 0 0 0 6 6 6 6 0 0 0 6-6v-4" />
            <circle cx="20" cy="10" r="2" />
          </svg>
        </div>
        <h2 class="state-title">Ready for the next patient</h2>
        <p class="state-sub">Click below to dequeue the next patient and set up their consultation.</p>
        <button class="next-btn" @click="callNextPatient(false)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          Next Patient
        </button>
      </div>

      <!-- ── Calling (loading) ── -->
      <div v-else-if="state === 'calling'" class="state-card">
        <div class="spinner-ring" />
        <h2 class="state-title">Calling next patient…</h2>
        <p class="state-sub">Creating Zoom meeting and notifying patient.</p>
      </div>

      <!-- ── Active ── -->
      <div v-else-if="state === 'active'" class="state-card">
        <div class="check-wrap">
          <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        </div>

        <h2 class="state-title confirmed-title">Patient Called</h2>

        <!-- Patient card -->
        <div class="patient-card" v-if="currentPatient">
          <div class="patient-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="28" height="28">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <div class="patient-info">
            <span class="patient-name">{{ currentPatient.patient_name }}</span>
            <span class="patient-email">{{ currentPatient.email }}</span>
          </div>
        </div>

        <p class="state-sub">Patient has been emailed their Zoom join link.</p>

        <button class="zoom-btn" @click="openZoom" :disabled="!zoomStartUrl">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
            <polygon points="23 7 16 12 23 17 23 7" />
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
          </svg>
          Start Zoom Consultation
        </button>

        <button class="next-btn" @click="callNextPatient(true)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
            <polyline points="13 17 18 12 13 7" />
            <polyline points="6 17 11 12 6 7" />
          </svg>
          Next Patient (mark current as no-show)
        </button>

        <button class="done-btn" @click="markDone">Done with this patient</button>
      </div>

      <!-- ── Error ── -->
      <div v-else-if="state === 'error'" class="state-card">
        <div class="error-icon-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="36" height="36" style="color: #f87171">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h2 class="state-title">Something went wrong</h2>
        <p class="state-sub error-msg">{{ errorMsg }}</p>
        <button class="next-btn" @click="callNextPatient(false)">Try Again</button>
      </div>

    </main>

    <!-- ── Toast ── -->
    <Transition name="toast">
      <div v-if="showEmptyToast" class="toast">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <line x1="23" y1="11" x2="17" y2="11" />
        </svg>
        Queue is empty
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── Base ───────────────────────────────────────────────────── */
.dashboard-page {
  min-height: 100vh;
  background: #111d15;
  color: #fff;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  position: relative;
  overflow: hidden;
}

.bg-ambient {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 55% at 50% 40%, rgba(20, 80, 35, 0.4) 0%, transparent 65%),
    radial-gradient(ellipse 45% 45% at 10% 90%, rgba(10, 50, 20, 0.25) 0%, transparent 60%);
  pointer-events: none;
}

/* ── Navbar ─────────────────────────────────────────────────── */
.dashboard-nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 2.5rem;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  user-select: none;
}

.logo-img {
  height: 38px; width: 38px;
  object-fit: contain;
  mix-blend-mode: screen;
  flex-shrink: 0;
}

.logo-text {
  font-weight: 700;
  font-size: 0.95rem;
  color: #fff;
  letter-spacing: -0.01em;
}

.nav-role {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

/* ── Main ───────────────────────────────────────────────────── */
.dashboard-main {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6rem 1.5rem 3rem;
  position: relative;
  z-index: 10;
}

/* ── State card ─────────────────────────────────────────────── */
.state-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  width: 100%;
  max-width: 440px;
  text-align: center;
}

.state-title {
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  margin: 0;
  color: #fff;
}

.confirmed-title {
  color: #4ade80;
}

.state-sub {
  font-size: 0.92rem;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
  line-height: 1.6;
}

/* ── Icons ──────────────────────────────────────────────────── */
.stethoscope-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.08);
  border: 1.5px solid rgba(34, 197, 94, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.check-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.12);
  border: 1.5px solid rgba(34, 197, 94, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}

.check-icon {
  width: 36px;
  height: 36px;
  color: #4ade80;
}

/* ── Spinner ────────────────────────────────────────────────── */
.spinner-ring {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 3px solid rgba(34, 197, 94, 0.15);
  border-top-color: #22c55e;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Patient card ───────────────────────────────────────────── */
.patient-card {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  text-align: left;
}

.patient-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #4ade80;
}

.patient-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.patient-name {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
}

.patient-email {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.45);
}

/* ── Error ──────────────────────────────────────────────────── */
.error-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(248, 113, 113, 0.08);
  border: 1.5px solid rgba(248, 113, 113, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-msg {
  color: rgba(248, 113, 113, 0.75);
}

/* ── Buttons ────────────────────────────────────────────────── */
.next-btn {
  width: 100%;
  background: #22c55e;
  border: none;
  border-radius: 0.85rem;
  padding: 0.9rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  font-size: 0.95rem;
  font-weight: 700;
  font-family: 'Inter', sans-serif;
  letter-spacing: -0.01em;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(34, 197, 94, 0.3);
  transition: background 0.2s, box-shadow 0.2s, transform 0.1s;

  &:hover {
    background: #16a34a;
    box-shadow: 0 6px 28px rgba(34, 197, 94, 0.45);
  }

  &:active {
    transform: scale(0.97);
  }
}

.zoom-btn {
  width: 100%;
  background: #1d4ed8;
  border: none;
  border-radius: 0.85rem;
  padding: 0.9rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  font-size: 0.95rem;
  font-weight: 700;
  font-family: 'Inter', sans-serif;
  letter-spacing: -0.01em;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(29, 78, 216, 0.3);
  transition: background 0.2s, box-shadow 0.2s, transform 0.1s;

  &:hover:not(:disabled) {
    background: #1e40af;
    box-shadow: 0 6px 28px rgba(29, 78, 216, 0.45);
  }

  &:active:not(:disabled) {
    transform: scale(0.97);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

/* ── Toast ──────────────────────────────────────────────────── */
.toast {
  position: fixed;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(30, 30, 30, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.75rem;
  padding: 0.7rem 1.1rem;
  font-size: 0.88rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  white-space: nowrap;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(0.5rem);
}

.done-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.3);
  font-size: 0.82rem;
  font-family: 'Inter', sans-serif;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  transition: color 0.18s;

  &:hover {
    color: rgba(255, 255, 255, 0.6);
  }
}
</style>
