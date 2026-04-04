<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { QueueService } from '../domains/appointment/queueService'
import { AppointmentService } from '../domains/appointment/appointmentService'
import { patientService } from '../domains/patient/patientService'

type PageState = 'joining' | 'queued' | 'called' | 'no_show' | 'error'

const router = useRouter()

const state = ref<PageState>('joining')
const queue = ref<{ queue_position: number; waiting_time: number } | null>(null)
const errorMsg = ref('')
const refreshing = ref(false)
const showNoDoctersToast = ref(false)
const selectedPatientId = ref('')
const selectedPatientName = ref('')

type ApiErrorLike = {
  message?: string
  response?: {
    status?: number
    data?: {
      message?: string
    }
  }
}

function asApiError(err: unknown): ApiErrorLike | null {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    return err as ApiErrorLike
  }
  if (err instanceof Error) {
    return { message: err.message }
  }
  return null
}

function getErrorMessage(err: unknown, fallback: string): string {
  const apiErr = asApiError(err)
  return apiErr?.response?.data?.message ?? apiErr?.message ?? fallback
}

function isDequeuedFromQueue(err: unknown): boolean {
  const apiErr = asApiError(err)
  if (!apiErr) {
    return false
  }

  const status = apiErr.response?.status
  const message = String(apiErr.response?.data?.message ?? '').toLowerCase()

  if (status !== 404) {
    return false
  }

  // Avoid false positives on generic gateway 404s.
  return message.includes('queue') || message.includes('patient') || message.includes('not found')
}

async function getLatestAppointmentStatus(patientId: string): Promise<string | null> {
  const numericId = Number(patientId)
  if (!Number.isFinite(numericId)) {
    return null
  }

  try {
    const appointments = await AppointmentService.getAppointmentsByPatient(numericId)
    if (!appointments.length) {
      return null
    }

    const latest = [...appointments].sort((a, b) =>
      new Date(b.slot_datetime).getTime() - new Date(a.slot_datetime).getTime(),
    )[0]

    return latest?.status ?? null
  } catch {
    return null
  }
}

function mapStatusToPostQueueState(status: string | null): 'called' | 'no_show' | null {
  if (status === 'CONFIRMED') {
    return 'called'
  }
  if (status === 'NO_SHOW') {
    return 'no_show'
  }
  return null
}

function triggerNoDoctersToast() {
  showNoDoctersToast.value = true
  setTimeout(() => router.push('/'), 3000)
}

async function joinQueueForSelectedPatient() {
  state.value = 'joining'

  try {
    queue.value = await QueueService.joinQueue(selectedPatientId.value)
    state.value = 'queued'
  } catch (err) {
    if (getErrorMessage(err, '') === 'No doctors available') {
      triggerNoDoctersToast()
    } else {
      state.value = 'error'
      errorMsg.value = getErrorMessage(err, 'Unable to join the queue. Please try again.')
    }
  }
}

async function refresh() {
  refreshing.value = true
  try {
    const entry = await QueueService.getQueueStatus(selectedPatientId.value)
    queue.value = entry
    if (state.value !== 'called') {
      state.value = 'queued'
    }
  } catch (err) {
    if (isDequeuedFromQueue(err)) {
      const latestStatus = await getLatestAppointmentStatus(selectedPatientId.value)
      const postQueueState = mapStatusToPostQueueState(latestStatus)

      if (postQueueState === 'no_show') {
        state.value = 'no_show'
        queue.value = null
        return
      }

      // If queue no longer has this patient, treat it as called by default.
      // Appointment status can still later move to NO_SHOW on a subsequent refresh.
      state.value = 'called'
      return
    }

    // keep last known state on transient failure
  } finally {
    refreshing.value = false
  }
}

async function init() {
  try {
    const saved = localStorage.getItem('demoPatientId')

    if (saved) {
      const details = await patientService.getById(saved)
      const payload = details?.data
      selectedPatientId.value = String(payload?.patient_id ?? saved)
      selectedPatientName.value = String(payload?.patient_name ?? `Patient ${saved}`)
    } else {
      const listing = await patientService.getAll()
      const first = listing?.data?.[0]
      if (!first) {
        throw new Error('No patients available. Please set a profile on the landing page.')
      }
      selectedPatientId.value = String(first.patient_id)
      selectedPatientName.value = String(first.patient_name)
      localStorage.setItem('demoPatientId', selectedPatientId.value)
    }

    await joinQueueForSelectedPatient()
  } catch (err) {
    state.value = 'error'
    errorMsg.value = getErrorMessage(
      err,
      'Unable to resolve active profile. Please choose one on the landing page.',
    )
  }
}

function leaveQueue() {
  router.push('/')
}

onMounted(init)
</script>

<template>
  <div class="queue-page">
    <div class="bg-ambient" />

    <!-- Navbar -->
    <nav class="queue-nav">
      <div class="logo" @click="leaveQueue">
        <img src="/doctor-everywhere-logo.png" alt="Doctor Everywhere" class="logo-img" />
        <span class="logo-text">doctor everywhere</span>
      </div>
    </nav>

    <!-- Content -->
    <main class="queue-main">

      <!-- ── Joining (initial load) ── -->
      <div v-if="state === 'joining'" class="state-card">
        <div class="spinner-ring" />
        <h2 class="state-title">Joining the queue…</h2>
        <p class="state-sub">Setting up your session, just a moment.</p>
      </div>

      <!-- ── Queued ── -->
      <div v-else-if="state === 'queued'" class="state-card">
        <!-- Radar pulse -->
        <div class="radar-wrap">
          <div class="radar-ring ring-1" />
          <div class="radar-ring ring-2" />
          <div class="radar-ring ring-3" />
          <div class="radar-core">
            <span class="queue-num">#{{ queue!.queue_position }}</span>
            <span class="queue-num-label">in queue</span>
          </div>
        </div>

        <h2 class="state-title">You're in the queue</h2>
        <p class="state-sub">Active patient: {{ selectedPatientName }} ({{ selectedPatientId }})</p>
        <p class="state-sub">
          Estimated wait: ~{{ queue!.waiting_time }} min
        </p>

        <!-- Info card -->
        <div class="info-card">
          <div class="info-row">
            <svg class="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
            <p>A doctor will be assigned to you automatically — no action needed.</p>
          </div>
          <div class="info-row">
            <svg class="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.63 3.4 2 2 0 0 1 3.6 1.22h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6 6l.92-.92a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 21.73 16z" />
            </svg>
            <p>You'll receive an email with your Zoom link once a doctor is ready.</p>
          </div>
        </div>

        <button class="refresh-btn" @click="refresh" :disabled="refreshing">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          {{ refreshing ? 'Refreshing…' : 'Refresh status' }}
        </button>

        <button class="leave-btn" @click="leaveQueue">Return to dashboard</button>
      </div>

      <!-- ── Called ── -->
      <div v-else-if="state === 'called'" class="state-card">
        <div class="called-icon-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="36" height="36" style="color: #4ade80">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </div>
        <h2 class="state-title">You have been called</h2>
        <p class="state-sub">Please check your email for the consultation link.</p>
        <p v-if="queue" class="state-sub">Last known queue position: #{{ queue.queue_position }}</p>
        <button class="refresh-btn" @click="refresh" :disabled="refreshing">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          {{ refreshing ? 'Refreshing…' : 'Refresh status' }}
        </button>
        <button class="join-consult-btn" @click="router.push('/')">Go back home</button>
      </div>

      <!-- ── No-show ── -->
      <div v-else-if="state === 'no_show'" class="state-card">
        <div class="error-icon-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="36" height="36" style="color: #f87171">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h2 class="state-title">You have been marked as no-show</h2>
        <p class="state-sub error-msg">Your appointment was marked as no-show by the doctor. Please book again if needed.</p>
        <button class="join-consult-btn" @click="router.push('/')">Go back home</button>
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
        <button class="join-consult-btn" @click="router.push('/')">Go back home</button>
      </div>

    </main>

    <!-- ── Toast ── -->
    <Transition name="toast">
      <div v-if="showNoDoctersToast" class="toast">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        No doctors are currently available. Redirecting you home…
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── Base ───────────────────────────────────────────────────── */
.queue-page {
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
.queue-nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  padding: 1.5rem 2.5rem;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  cursor: pointer;
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

/* ── Main ───────────────────────────────────────────────────── */
.queue-main {
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


.state-sub {
  font-size: 0.92rem;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
  line-height: 1.6;
}

/* ── Spinner (joining) ──────────────────────────────────────── */
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

/* ── Radar pulse ────────────────────────────────────────────── */
.radar-wrap {
  position: relative;
  width: 160px;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.radar-ring {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid rgba(34, 197, 94, 0.5);
  animation: radar-expand 2.4s ease-out infinite;
}

.ring-1 { width: 80px;  height: 80px;  animation-delay: 0s; }
.ring-2 { width: 80px;  height: 80px;  animation-delay: 0.8s; }
.ring-3 { width: 80px;  height: 80px;  animation-delay: 1.6s; }

@keyframes radar-expand {
  0%   { transform: scale(1);   opacity: 0.7; }
  100% { transform: scale(2.2); opacity: 0; }
}

.radar-core {
  position: relative;
  z-index: 2;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.12);
  border: 1.5px solid rgba(34, 197, 94, 0.4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.1rem;
}

.queue-num {
  font-size: 1.5rem;
  font-weight: 800;
  color: #4ade80;
  letter-spacing: -0.04em;
  line-height: 1;
}

.queue-num-label {
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* ── Info card ──────────────────────────────────────────────── */
.info-card {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  text-align: left;
}

.info-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.55;
}

.info-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: #4ade80;
  margin-top: 1px;
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

.called-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(74, 222, 128, 0.08);
  border: 1.5px solid rgba(74, 222, 128, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-msg {
  color: rgba(248, 113, 113, 0.75);
}

/* ── Buttons ────────────────────────────────────────────────── */
.join-consult-btn {
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

  &:hover:not(:disabled) {
    background: #16a34a;
    box-shadow: 0 6px 28px rgba(34, 197, 94, 0.45);
  }

  &:active:not(:disabled) {
    transform: scale(0.97);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.refresh-btn {
  width: 100%;
  background: transparent;
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 0.85rem;
  padding: 0.75rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.88rem;
  font-weight: 600;
  font-family: 'Inter', sans-serif;
  color: #4ade80;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;

  &:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.08);
    border-color: rgba(34, 197, 94, 0.5);
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

.leave-btn {
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