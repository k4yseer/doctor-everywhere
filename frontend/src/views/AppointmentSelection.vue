<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { PostConsultService, type ConsultationHistoryItem } from '../domains/consultation/postConsultService'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const appointments = ref<ConsultationHistoryItem[]>([])
const patientId = Number(import.meta.env.VITE_DEFAULT_PATIENT_ID ?? 1)

async function loadAppointments() {
  loading.value = true
  error.value = ''

  try {
    appointments.value = await PostConsultService.getConsultationHistory(patientId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load appointments.'
  } finally {
    loading.value = false
  }
}

function selectAppointment(appointmentId: number) {
  router.push({
    name: 'post-consult',
    query: {
      appointmentId: String(appointmentId),
      patientId: String(patientId),
    },
  })
}

onMounted(loadAppointments)
</script>

<template>
  <div class="appointments-page">
    <div class="bg-ambient" />

    <nav class="pc-nav">
      <button class="back-btn" @click="router.back()">Back</button>
      <h1 class="page-title">Select an Appointment</h1>
    </nav>

    <main class="pc-main">
      <div class="pc-content">
        <section class="pc-card">
          <p class="page-intro">Choose the appointment you want to review and pay for.</p>

          <div v-if="loading" class="loading-wrap">
            <p class="loading-text">Loading appointments…</p>
          </div>

          <div v-else-if="error" class="error-text">{{ error }}</div>

          <div v-else-if="appointments.length === 0" class="empty-text">
            No appointments found for this patient.
          </div>

          <ul v-else class="appointment-list">
            <li
              v-for="appointment in appointments"
              :key="appointment.appointmentId"
              class="appointment-card"
            >
              <button class="appointment-link" @click="selectAppointment(appointment.appointmentId)">
                <div class="appointment-row">
                  <span class="appointment-label">Appointment</span>
                  <span class="appointment-value">#{{ appointment.appointmentId }}</span>
                </div>
                <div class="appointment-row">
                  <span class="appointment-label">Date</span>
                  <span class="appointment-value">
                    {{ new Date(appointment.date).toLocaleString('en-SG', { dateStyle: 'medium', timeStyle: 'short' }) }}
                  </span>
                </div>
                <div class="appointment-row">
                  <span class="appointment-label">Status</span>
                  <span class="appointment-value">{{ appointment.status }}</span>
                </div>
                <div class="appointment-row">
                  <span class="appointment-label">Prescription</span>
                  <span class="appointment-value">{{ appointment.prescriptions?.length ?? 0 }} item(s)</span>
                </div>
              </button>
            </li>
          </ul>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.appointments-page {
  color: #fff;
  background: #111d15;
  min-height: 100vh;
  font-family: Inter, system-ui, -apple-system, sans-serif;
  position: relative;
}

.bg-ambient {
  pointer-events: none;
  z-index: 0;
  background: radial-gradient(65% 50% at 70% 20%, #14502359 0%, #0000 65%),
    radial-gradient(45% 45% at 10% 80%, #0a321433 0%, #0000 60%);
  position: fixed;
  inset: 0;
}

.pc-nav {
  z-index: 200;
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  background: #111d15d9;
  border-bottom: 1px solid #ffffff0f;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2.5rem;
  display: flex;
  position: sticky;
  top: 0;
}

.back-btn {
  color: #fff9;
  cursor: pointer;
  background: #ffffff0f;
  border: 1px solid #ffffff1a;
  border-radius: 0.6rem;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.85rem;
  font-family: Inter, sans-serif;
  font-size: 0.82rem;
  transition: background 0.18s, color 0.18s;
  display: flex;
}

.back-btn:hover {
  color: #fff;
  background: #ffffff1a;
}

.page-title {
  letter-spacing: -0.03em;
  margin: 0;
  font-size: 1.6rem;
  font-weight: 800;
}

.pc-main {
  z-index: 10;
  justify-content: center;
  padding: 2.5rem 1.5rem 5rem;
  display: flex;
  position: relative;
}

.pc-content {
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
  max-width: 660px;
  display: flex;
}

.pc-card {
  background: #ffffff0a;
  border: 1px solid #ffffff14;
  border-radius: 1.25rem;
  flex-direction: column;
  gap: 1.1rem;
  padding: 1.4rem 1.5rem;
  display: flex;
}

.page-intro {
  color: #ffffffb3;
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.7;
}

.loading-wrap {
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding-top: 1.5rem;
  display: flex;
}

.loading-text {
  color: #fff6;
  font-size: 0.88rem;
}

.error-text,
.empty-text {
  color: #fff6;
  padding: 1rem 0;
  font-size: 0.95rem;
}

.appointment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 1rem;
}

.appointment-card {
  background: transparent;
}

.appointment-link {
  width: 100%;
  text-align: left;
  background: #ffffff0f;
  border: 1px solid #ffffff14;
  border-radius: 1rem;
  padding: 1rem 1.2rem;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  cursor: pointer;
  transition: background 0.2s, transform 0.2s;
}

.appointment-link:hover {
  background: #ffffff17;
  transform: translateY(-1px);
}

.appointment-row {
  display: grid;
  grid-template-columns: auto minmax(0, auto);
  gap: 0.75rem;
  align-items: center;
}

.appointment-label {
  color: #ffffff73;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.appointment-value {
  color: #fff;
  font-weight: 600;
  font-size: 0.96rem;
  text-align: right;
}
</style>
