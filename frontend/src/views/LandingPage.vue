<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { patientService, type Patient } from '../domains/patient/patientService'

const router = useRouter()
const profileOpen = ref(false)
const loadingPatients = ref(false)
const patientOptions = ref<Patient[]>([])
const selectedPatientId = ref('')

const tags = ['Instant Access', 'No Appointments', 'Telehealth']

interface Pill {
  w: number; h: number; x: number; y: number; r: number
  colorIdx: number; anim: number; delay: number
}

const pills: Pill[] = [
  { w: 160, h: 52, x: 30,  y: 40,  r: -40, colorIdx: 0, anim: 4.2, delay: 0.0 },
  { w: 115, h: 38, x: 250, y: 15,  r:  18, colorIdx: 1, anim: 3.8, delay: 0.6 },
  { w: 138, h: 46, x: 390, y: 100, r: -65, colorIdx: 2, anim: 4.5, delay: 1.2 },
  { w: 88,  h: 30, x: 90,  y: 165, r:  52, colorIdx: 3, anim: 3.5, delay: 0.3 },
  { w: 155, h: 50, x: 210, y: 200, r:  -8, colorIdx: 0, anim: 4.8, delay: 0.9 },
  { w: 124, h: 42, x: 400, y: 270, r:  80, colorIdx: 1, anim: 3.7, delay: 1.5 },
  { w: 98,  h: 34, x: 40,  y: 335, r: -75, colorIdx: 2, anim: 4.1, delay: 0.4 },
  { w: 144, h: 48, x: 225, y: 375, r:  28, colorIdx: 3, anim: 4.4, delay: 1.0 },
  { w: 116, h: 39, x: 385, y: 440, r: -45, colorIdx: 0, anim: 3.9, delay: 0.7 },
  { w: 132, h: 43, x: 110, y: 495, r:  63, colorIdx: 1, anim: 4.6, delay: 1.3 },
  { w: 94,  h: 32, x: 300, y: 530, r: -22, colorIdx: 2, anim: 3.6, delay: 0.2 },
  { w: 150, h: 50, x: 55,  y: 595, r:  42, colorIdx: 3, anim: 4.3, delay: 0.8 },
  { w: 108, h: 36, x: 345, y: 620, r: -58, colorIdx: 0, anim: 4.0, delay: 1.4 },
  { w: 128, h: 43, x: 185, y: 665, r:  12, colorIdx: 1, anim: 4.7, delay: 0.5 },
]

const pillGradients = [
  'linear-gradient(90deg, #4ade80 49%, #22c55e 51%)',
  'linear-gradient(90deg, #22c55e 49%, #166534 51%)',
  'linear-gradient(90deg, #86efac 49%, #4ade80 51%)',
  'linear-gradient(90deg, #16a34a 49%, #14532d 51%)',
]

function pillStyle(pill: Pill) {
  return {
    left: `${pill.x}px`,
    top: `${pill.y}px`,
    width: `${pill.w}px`,
    height: `${pill.h}px`,
    background: pillGradients[pill.colorIdx],
    '--r': `${pill.r}deg`,
    '--anim': `${pill.anim}s`,
    '--delay': `${pill.delay}s`,
  }
}

const activePatientLabel = computed(() => {
  const selected = patientOptions.value.find((p) => String(p.patient_id) === selectedPatientId.value)
  if (!selected) return 'No patient selected'
  return `${selected.patient_name} (${selected.patient_id})`
})

async function loadPatients() {
  loadingPatients.value = true
  try {
    const response = await patientService.getAll()
    patientOptions.value = response?.data ?? []

    const saved = localStorage.getItem('demoPatientId')
    const hasSaved = saved && patientOptions.value.some((p) => String(p.patient_id) === saved)
    selectedPatientId.value = hasSaved
      ? String(saved)
      : (patientOptions.value[0] ? String(patientOptions.value[0].patient_id) : '')
  } finally {
    loadingPatients.value = false
  }
}

function persistSelectedPatient() {
  if (!selectedPatientId.value) return
  localStorage.setItem('demoPatientId', selectedPatientId.value)
}

function toggleProfilePanel() {
  profileOpen.value = !profileOpen.value
}

onMounted(() => {
  document.documentElement.classList.add('p-dark')
  loadPatients()
})
onUnmounted(() => {
  document.documentElement.classList.remove('p-dark')
})
</script>

<template>
  <div class="landing">
    <!-- Background ambient -->
    <div class="bg-ambient" />

    <!-- ─── Navbar ─────────────────────────────────────────── -->
    <nav class="landing-nav">
      <div class="logo">
        <img src="/doctor-everywhere-logo.png" alt="Doctor Everywhere logo" class="logo-img" />
        <span class="logo-text">doctor everywhere</span>
      </div>

      <button class="profile-btn" aria-label="Open profile" @click="toggleProfilePanel">
        <svg class="profile-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      </button>
    </nav>

    <Transition name="profile-pop">
      <div v-if="profileOpen" class="profile-panel">
        <p class="profile-panel-title">Demo Profile</p>
        <p class="profile-panel-sub">Select patient identity for queue interactions.</p>

        <select
          v-model="selectedPatientId"
          class="profile-select"
          :disabled="loadingPatients || patientOptions.length === 0"
          @change="persistSelectedPatient"
        >
          <option v-for="patient in patientOptions" :key="patient.patient_id" :value="String(patient.patient_id)">
            {{ patient.patient_name }} ({{ patient.patient_id }})
          </option>
        </select>

        <p class="profile-active">Active: {{ activePatientLabel }}</p>
      </div>
    </Transition>

    <!-- ─── Hero ───────────────────────────────────────────── -->
    <section class="hero">
      <!-- Left content -->
      <div class="hero-content">
        <h1 class="hero-headline">
          Doctor<br />Everywhere<span class="accent-dot">.</span>
        </h1>

        <!-- Join Queue card -->
        <div class="join-card">
          <p class="join-card-label">How it works</p>

          <div class="steps-row">
            <div class="step">
              <div class="step-bubble">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <span class="step-label">Join the queue</span>
            </div>

            <div class="step-connector">
              <svg viewBox="0 0 24 6" fill="none" width="32" height="6">
                <path d="M0 3 Q8 0 16 3 Q24 6 32 3" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" stroke-dasharray="3 2" />
              </svg>
            </div>

            <div class="step">
              <div class="step-bubble">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
              </div>
              <span class="step-label">Doctor assigned</span>
            </div>

            <div class="step-connector">
              <svg viewBox="0 0 24 6" fill="none" width="32" height="6">
                <path d="M0 3 Q8 0 16 3 Q24 6 32 3" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" stroke-dasharray="3 2" />
              </svg>
            </div>

            <div class="step">
              <div class="step-bubble">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                  <polygon points="23 7 16 12 23 17 23 7" />
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                </svg>
              </div>
              <span class="step-label">Consult online</span>
            </div>
          </div>

          <div class="hero-actions" style="display: flex; align-items: center;">
            <button class="join-queue-btn" @click="router.push('/queue')">
              Join Queue Now
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="15" height="15">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
            <button class="join-queue-btn" @click="router.push('/appointments')" style="margin-left: 1rem;">
              View Consults
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="15" height="15">
                <path d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        <p class="hero-desc">
          Doctor Everywhere. Your health, anywhere.<br>Get your medicine delivered to your doorstep!
        </p>

        <div class="tag-row">
          <span v-for="tag in tags" :key="tag" class="tag-pill">{{ tag }}</span>
        </div>
      </div>

      <!-- Right: floating pill visual -->
      <div class="hero-visual">
        <div class="pill-glow" />
        <div class="pill-cluster">
          <div
            v-for="(pill, idx) in pills"
            :key="idx"
            class="pill"
            :style="pillStyle(pill)"
          />
        </div>
      </div>
    </section>

    <!-- ─── Bottom-right label ─────────────────────────────── -->
    <div class="main-menu-badge">
      <span>Profile</span>
      <button class="profile-mini-btn" aria-label="Profile" @click="toggleProfilePanel">
        <svg class="profile-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ─── Base ────────────────────────────────────────────────── */
.landing {
  min-height: 100vh;
  background: #111d15;
  color: #fff;
  overflow: hidden;
  position: relative;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

.bg-ambient {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 80% 50%, rgba(20, 80, 35, 0.45) 0%, transparent 65%),
    radial-gradient(ellipse 50% 50% at 10% 80%, rgba(10, 50, 20, 0.3) 0%, transparent 60%);
  pointer-events: none;
}

/* ─── Navbar ──────────────────────────────────────────────── */
.landing-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 200;
  display: flex;
  justify-content: space-between;
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
  height: 38px;
  width: 38px;
  object-fit: contain;
  /* screen blend removes the black PNG background, leaving only the green icon */
  mix-blend-mode: screen;
  flex-shrink: 0;
}

.logo-text {
  font-weight: 700;
  font-size: 0.95rem;
  color: #fff;
  letter-spacing: -0.01em;
}

.profile-btn {
  background: #22c55e;
  border: none;
  width: 46px;
  height: 46px;
  border-radius: 0.85rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.2s;

  &:hover {
    background: #16a34a;
  }
}

.profile-mini-btn {
  background: #22c55e;
  border: none;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;

  &:hover {
    background: #16a34a;
  }
}

.profile-icon {
  width: 18px;
  height: 18px;
  color: #fff;
}

/* ─── Hero ────────────────────────────────────────────────── */
.hero {
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: 6rem 0 3rem 8%;
  position: relative;
  gap: 2rem;
}

.hero-content {
  flex: 0 0 auto;
  width: min(500px, 48%);
  position: relative;
  z-index: 10;
}

/* ─── Headline ────────────────────────────────────────────── */
.hero-headline {
  font-size: clamp(2.6rem, 4.5vw, 4.2rem);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: -0.04em;
  margin: 0 0 2rem;
  color: #fff;
}

.accent-dot {
  color: #22c55e;
}

/* ─── Join Queue card ─────────────────────────────────────── */
.join-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 1.25rem;
  padding: 1.25rem 1.4rem 1.4rem;
  margin-bottom: 1.75rem;
  backdrop-filter: blur(14px);
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.join-card-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.3);
  margin: 0;
}

.steps-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.step-bubble {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4ade80;
}

.step-label {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
  white-space: nowrap;
}

.step-connector {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  margin-bottom: 1.4rem;
}

.join-queue-btn {
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
  color: #fff;
  cursor: pointer;
  letter-spacing: -0.01em;
  transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
  box-shadow: 0 4px 20px rgba(34, 197, 94, 0.3);

  &:hover {
    background: #16a34a;
    box-shadow: 0 6px 28px rgba(34, 197, 94, 0.45);
  }

  &:active {
    transform: scale(0.97);
  }
}

/* ─── Description ─────────────────────────────────────────── */
.hero-desc {
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.75;
  margin: 0 0 1.75rem;
  max-width: 420px;
}

/* ─── Tags ────────────────────────────────────────────────── */
.tag-row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.tag-pill {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.11);
  color: rgba(255, 255, 255, 0.65);
  padding: 0.38rem 1rem;
  border-radius: 2rem;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: default;
  transition: background 0.18s, border-color 0.18s;

  &:hover {
    background: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.3);
    color: #86efac;
  }
}

/* ─── Hero visual ─────────────────────────────────────────── */
.hero-visual {
  flex: 1;
  position: relative;
  height: 100vh;
  overflow: visible;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.pill-glow {
  position: absolute;
  width: 680px;
  height: 680px;
  right: -60px;
  top: 50%;
  transform: translateY(-50%);
  background: radial-gradient(circle, rgba(34, 197, 94, 0.13) 0%, transparent 65%);
  pointer-events: none;
  z-index: 0;
}

.pill-cluster {
  position: relative;
  width: 520px;
  height: 720px;
  flex-shrink: 0;
  translate: 60px -20px;
  z-index: 1;
}

.pill {
  position: absolute;
  border-radius: 100px;
  transform: rotate(var(--r, 0deg));
  box-shadow:
    0 10px 28px rgba(0, 0, 0, 0.45),
    0 3px 10px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    inset 0 -2px 0 rgba(0, 0, 0, 0.18);
  animation: pill-float var(--anim, 4s) ease-in-out var(--delay, 0s) infinite;
}

@keyframes pill-float {
  0%, 100% { transform: rotate(var(--r, 0deg)) translateY(0px); }
  50%       { transform: rotate(var(--r, 0deg)) translateY(-10px); }
}

/* ─── Bottom badge ────────────────────────────────────────── */
.main-menu-badge {
  position: fixed;
  bottom: 1.75rem;
  right: 1.75rem;
  display: flex;
  align-items: center;
  gap: 0.9rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 3rem;
  padding: 0.45rem 0.45rem 0.45rem 1.1rem;
  backdrop-filter: blur(12px);
  z-index: 200;
}

.main-menu-badge > span {
  font-size: 0.82rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.65);
  letter-spacing: 0.01em;
}

.profile-panel {
  position: fixed;
  top: 5.2rem;
  right: 2.5rem;
  z-index: 260;
  width: min(320px, calc(100vw - 2rem));
  background: rgba(16, 28, 20, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 0.95rem;
  padding: 0.95rem;
  backdrop-filter: blur(14px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
}

.profile-panel-title {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 700;
  color: #fff;
}

.profile-panel-sub {
  margin: 0.35rem 0 0.8rem;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.56);
}

.profile-select {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  padding: 0.68rem 0.75rem;
  font-size: 0.86rem;
  outline: none;
}

.profile-select option {
  background: #1a2a20;
}

.profile-active {
  margin: 0.65rem 0 0.75rem;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.65);
}

.profile-pop-enter-active,
.profile-pop-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.profile-pop-enter-from,
.profile-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>

