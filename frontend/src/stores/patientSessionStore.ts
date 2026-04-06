import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { patientService, type Patient } from '@/domains/patient/patientService'

const PATIENT_STORAGE_KEY = 'demoPatientId'

function readPersistedPatientId(): number | null {
  try {
    const raw = localStorage.getItem(PATIENT_STORAGE_KEY)
    if (!raw) {
      return null
    }

    const parsed = Number(raw)
    if (!Number.isInteger(parsed) || parsed <= 0) {
      return null
    }

    return parsed
  } catch {
    return null
  }
}

function persistPatientId(patientId: number | null): void {
  try {
    if (patientId) {
      localStorage.setItem(PATIENT_STORAGE_KEY, String(patientId))
      return
    }
    localStorage.removeItem(PATIENT_STORAGE_KEY)
  } catch {
    // Ignore storage failures (private mode/quota/blocked storage).
  }
}

export const usePatientSessionStore = defineStore('patient-session', () => {
  const patients = ref<Patient[]>([])
  const selectedPatient = ref<Patient | null>(null)
  const isLoading = ref(false)

  const selectedPatientId = computed(() => selectedPatient.value?.patient_id ?? null)

  async function loadPatients(): Promise<Patient[]> {
    isLoading.value = true
    try {
      const response = await patientService.getAll()
      patients.value = response?.data ?? []
      return patients.value
    } finally {
      isLoading.value = false
    }
  }

  async function selectPatientById(patientId: number | null): Promise<Patient | null> {
    if (!patientId) {
      selectedPatient.value = null
      persistPatientId(null)
      return null
    }

    if (!patients.value.length) {
      await loadPatients()
    }

    const fallback = patients.value.find((p) => p.patient_id === patientId) ?? null

    try {
      const response = await patientService.getById(patientId)
      selectedPatient.value = response?.data ?? fallback
    } catch {
      selectedPatient.value = fallback
    }

    persistPatientId(selectedPatient.value?.patient_id ?? null)

    return selectedPatient.value
  }

  async function initialize(): Promise<void> {
    if (!patients.value.length) {
      await loadPatients()
    }

    if (selectedPatient.value) {
      persistPatientId(selectedPatient.value.patient_id)
      return
    }

    const persistedId = readPersistedPatientId()
    if (persistedId) {
      const restored = await selectPatientById(persistedId)
      if (restored) {
        return
      }
    }

    if (patients.value.length) {
      await selectPatientById(patients.value[0].patient_id)
    }
  }

  return {
    patients,
    selectedPatient,
    selectedPatientId,
    isLoading,
    loadPatients,
    selectPatientById,
    initialize,
  }
})
