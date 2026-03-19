<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'

const doctorName = ref('')
const selectedSpecialty = ref<{ label: string; value: string } | null>(null)
const selectedSymptom = ref<{ label: string; value: string } | null>(null)

const specialties = [
  { label: 'General Practitioner', value: 'gp' },
  { label: 'Cardiologist', value: 'cardiologist' },
  { label: 'Dermatologist', value: 'dermatologist' },
  { label: 'Neurologist', value: 'neurologist' },
  { label: 'Pediatrician', value: 'pediatrician' },
  { label: 'Psychiatrist', value: 'psychiatrist' },
  { label: 'Orthopedist', value: 'orthopedist' },
  { label: 'Oncologist', value: 'oncologist' },
]

const symptoms = [
  { label: 'Headache', value: 'headache' },
  { label: 'Fever', value: 'fever' },
  { label: 'Cough', value: 'cough' },
  { label: 'Fatigue', value: 'fatigue' },
  { label: 'Joint Pain', value: 'joint-pain' },
  { label: 'Skin Rash', value: 'skin-rash' },
  { label: 'Stomach Pain', value: 'stomach-pain' },
  { label: 'Anxiety', value: 'anxiety' },
  { label: 'Shortness of Breath', value: 'sob' },
]

const tags = ['some', 'tags', 'here']

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

onMounted(() => {
  document.documentElement.classList.add('p-dark')
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

      <button class="nav-menu-btn" aria-label="Open menu">
        <span class="dot" />
        <span class="dot" />
        <span class="dot" />
        <span class="dot" />
      </button>
    </nav>

    <!-- ─── Hero ───────────────────────────────────────────── -->
    <section class="hero">
      <!-- Left content -->
      <div class="hero-content">
        <h1 class="hero-headline">
          Doctor<br />Everywhere<span class="accent-dot">.</span>
        </h1>

        <!-- Search card -->
        <div class="search-card">
          <!-- Doctor name row -->
          <div class="search-name-row">
            <svg class="row-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
            </svg>
            <InputText
              v-model="doctorName"
              placeholder="Search"
              class="name-input"
            />
          </div>

          <!-- Filters row -->
          <div class="search-filter-row">
            <div class="filter-wrap">
              <svg class="row-icon small" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4.5 6.375a4.125 4.125 0 1 1 8.25 0 4.125 4.125 0 0 1-8.25 0ZM14.25 8.625a3.375 3.375 0 1 1 6.75 0 3.375 3.375 0 0 1-6.75 0ZM1.5 19.125a7.125 7.125 0 0 1 14.25 0v.003l-.001.119a.75.75 0 0 1-.363.63 13.067 13.067 0 0 1-6.761 1.873c-2.472 0-4.786-.684-6.76-1.873a.75.75 0 0 1-.364-.63l-.001-.122ZM17.25 19.128l-.001.144a2.25 2.25 0 0 1-.233.96 10.088 10.088 0 0 0 5.06-1.01.75.75 0 0 0 .42-.643 4.875 4.875 0 0 0-6.957-4.611 8.586 8.586 0 0 1 1.71 5.157v.003Z" />
              </svg>
              <Select
                v-model="selectedSpecialty"
                :options="specialties"
                option-label="label"
                placeholder="Specialty"
                class="filter-select"
              />
            </div>

            <div class="filter-wrap">
              <!-- pulse / symptom icon -->
              <svg class="row-icon small" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              <Select
                v-model="selectedSymptom"
                :options="symptoms"
                option-label="label"
                placeholder="Symptoms"
                class="filter-select"
              />
            </div>

            <button class="search-go-btn" aria-label="Search">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
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
      <span>Main Menu</span>
      <button class="mm-dots-btn" aria-label="Main menu">
        <span class="dot" />
        <span class="dot" />
        <span class="dot" />
        <span class="dot" />
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

.nav-menu-btn {
  background: #22c55e;
  border: none;
  width: 46px;
  height: 46px;
  border-radius: 0.85rem;
  cursor: pointer;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  place-items: center;
  gap: 4px;
  padding: 12px;
  transition: background 0.2s;

  &:hover {
    background: #16a34a;
  }
}

.dot {
  display: block;
  width: 5px;
  height: 5px;
  background: white;
  border-radius: 50%;
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

/* ─── Search card ─────────────────────────────────────────── */
.search-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 1.25rem;
  padding: 0.5rem;
  margin-bottom: 1.75rem;
  backdrop-filter: blur(14px);
}

.search-name-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.8rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  margin-bottom: 0.4rem;
}

.row-icon {
  width: 18px;
  height: 18px;
  color: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;

  &.small {
    width: 15px;
    height: 15px;
  }
}

/* override PrimeVue InputText for dark bg */
.name-input {
  width: 100%;
}

:deep(.name-input.p-inputtext) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: #fff !important;
  font-size: 0.92rem !important;
  padding: 0 !important;
  font-family: 'Inter', sans-serif !important;

  &::placeholder {
    color: rgba(255, 255, 255, 0.32) !important;
  }

  &:focus {
    outline: none !important;
    box-shadow: none !important;
  }
}

.search-filter-row {
  display: flex;
  gap: 0.4rem;
  padding: 0 0.4rem 0.4rem;
  align-items: center;
}

.filter-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 0.8rem;
  padding: 0.35rem 0.6rem 0.35rem 0.75rem;
  /* Override PrimeVue design tokens so the Select has no background of its own */
  --p-select-background: transparent;
  --p-select-border-color: transparent;
  --p-select-hover-border-color: transparent;
  --p-select-focus-border-color: transparent;
  --p-select-shadow: none;
  --p-select-color: rgba(255, 255, 255, 0.65);
  --p-select-placeholder-color: rgba(255, 255, 255, 0.4);

  &:focus-within {
    border-color: rgba(34, 197, 94, 0.4);
    background: rgba(34, 197, 94, 0.06);
  }
}

.filter-select {
  flex: 1;
}

/* Override PrimeVue Select internals */
:deep(.filter-select .p-select) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  min-width: 0 !important;
  display: flex;
  align-items: center;
}

:deep(.filter-select .p-select-label) {
  color: rgba(255, 255, 255, 0.65) !important;
  font-size: 0.83rem !important;
  padding: 0 !important;
  font-family: 'Inter', sans-serif !important;
}

:deep(.filter-select .p-select-dropdown) {
  color: rgba(255, 255, 255, 0.35) !important;
  width: 14px !important;
  margin-left: 4px;
}

:deep(.filter-select .p-select-dropdown svg) {
  width: 12px !important;
  height: 12px !important;
}


.search-go-btn {
  background: #22c55e;
  border: none;
  width: 46px;
  height: 46px;
  min-width: 46px;
  border-radius: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  transition: background 0.2s, transform 0.1s;

  &:hover {
    background: #16a34a;
  }

  &:active {
    transform: scale(0.93);
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

.mm-dots-btn {
  background: #22c55e;
  border: none;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  cursor: pointer;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  place-items: center;
  gap: 4px;
  padding: 10px;
  transition: background 0.2s;

  &:hover {
    background: #16a34a;
  }
}
</style>

<!-- Unscoped: targets teleported PrimeVue Select overlay -->
<style>
.p-dark .p-select-overlay {
  background: #192a1d !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 0.875rem !important;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.7) !important;
}

.p-dark .p-select-list {
  padding: 0.4rem !important;
}

.p-dark .p-select-option {
  color: rgba(255, 255, 255, 0.72) !important;
  font-size: 0.875rem !important;
  border-radius: 0.5rem !important;
  font-family: 'Inter', system-ui, sans-serif !important;
}

.p-dark .p-select-option:hover,
.p-dark .p-select-option.p-focus {
  background: rgba(34, 197, 94, 0.14) !important;
  color: #fff !important;
}

.p-dark .p-select-option.p-select-option-selected {
  background: rgba(34, 197, 94, 0.2) !important;
  color: #4ade80 !important;
}
</style>
