<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { QueueService, type QueueEntry } from '../domains/appointment/queueService'

type PageState = 'joining' | 'queued' | 'confirmed' | 'error'

const router = useRouter()

const state = ref<PageState>('joining')
const queue = ref<QueueEntry | null>(null)
const errorMsg = ref('')
const lastUpdated = ref<Date | null>(null)
const secondsUntilRefresh = ref(300) // 5 minutes

let pollInterval: ReturnType<typeof setInterval> | null = null
let countdownInterval: ReturnType<typeof setInterval> | null = null

const formattedLastUpdated = computed(() => {
  if (!lastUpdated.value) return ''
  return lastUpdated.value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})

const countdownDisplay = computed(() => {
  const m = Math.floor(secondsUntilRefresh.value / 60)
  const s = secondsUntilRefresh.value % 60
  return `${m}:${s.toString().padStart(2, '0')}`
})

async function pollStatus(queue_id: string) {
  try {
    const entry = await QueueService.getQueueStatus(queue_id)
    queue.value = entry
    lastUpdated.value = new Date()
    secondsUntilRefresh.value = 300

    if (entry.status === 'CONFIRMED') {
      state.value = 'confirmed'
      stopPolling()
    } else {
      state.value = 'queued'
    }
  } catch {
    // keep current state, silently retry next interval
  }
}

function stopPolling() {
  if (pollInterval) clearInterval(pollInterval)
  if (countdownInterval) clearInterval(countdownInterval)
}

function startPolling(queue_id: string) {
  pollInterval = setInterval(() => pollStatus(queue_id), 300_000)
  countdownInterval = setInterval(() => {
    secondsUntilRefresh.value = Math.max(0, secondsUntilRefresh.value - 1)
  }, 1000)
}

async function init() {
  const savedId = QueueService.getSavedQueueId()

  if (savedId) {
    // Returning visitor: just poll for latest status
    await pollStatus(savedId)
    if (state.value !== 'confirmed') startPolling(savedId)
    return
  }

  // Fresh join — POST /join-queue
  // TODO: replace hardcoded patient_id with value from auth store once login is implemented
  try {
    const entry = await QueueService.joinQueue(1)
    queue.value = entry
    lastUpdated.value = new Date()

    if (entry.status === 'CONFIRMED') {
      state.value = 'confirmed'
    } else {
      state.value = 'queued'
      startPolling(entry.queue_id)
    }
  } catch (err) {
    state.value = 'error'
    errorMsg.value = err instanceof Error ? err.message : 'Unable to join the queue. Please try again.'
  }
}

function leaveQueue() {
  stopPolling()
  QueueService.clearSavedQueueId()
  router.push('/')
}

function joinConsultation() {
  if (queue.value?.meet_link) {
    window.open(queue.value.meet_link, '_blank', 'noopener')
  }
}

onMounted(init)
onUnmounted(stopPolling)
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
            <span class="queue-num">#{{ queue?.position ?? '–' }}</span>
            <span class="queue-num-label">in queue</span>
          </div>
        </div>

        <h2 class="state-title">You're in the queue</h2>
        <p class="state-sub">
          {{ queue?.estimated_wait_minutes != null
              ? `Estimated wait: ~${queue.estimated_wait_minutes} min`
              : 'Estimated wait time will appear shortly' }}
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
            <p>You'll also receive an SMS confirmation once a doctor is ready.</p>
          </div>
        </div>

        <!-- Refresh status -->
        <div class="refresh-row">
          <span class="refresh-dot" />
          <span>Last updated {{ formattedLastUpdated }} · refreshing in {{ countdownDisplay }}</span>
        </div>

        <button class="leave-btn" @click="leaveQueue">Leave queue</button>
      </div>

      <!-- ── Confirmed ── -->
      <div v-else-if="state === 'confirmed'" class="state-card">
        <div class="check-wrap">
          <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        </div>

        <h2 class="state-title confirmed-title">Your doctor is ready!</h2>

        <!-- Doctor card -->
        <div class="doctor-card" v-if="queue?.doctor">
          <div class="doctor-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="28" height="28">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <div class="doctor-info">
            <span class="doctor-name">{{ queue.doctor.name }}</span>
            <span class="doctor-specialty">{{ queue.doctor.specialty }}</span>
          </div>
        </div>

        <button class="join-consult-btn" @click="joinConsultation" :disabled="!queue?.meet_link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
            <polygon points="23 7 16 12 23 17 23 7" />
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
          </svg>
          Join Consultation
        </button>

        <button class="leave-btn" @click="leaveQueue">Back to home</button>
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

.confirmed-title {
  color: #4ade80;
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

/* ── Refresh row ────────────────────────────────────────────── */
.refresh-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.3);
}

.refresh-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  animation: blink 1.8s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.25; }
}

/* ── Confirmed: check icon ──────────────────────────────────── */
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

/* ── Doctor card ────────────────────────────────────────────── */
.doctor-card {
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

.doctor-avatar {
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

.doctor-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.doctor-name {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
}

.doctor-specialty {
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
