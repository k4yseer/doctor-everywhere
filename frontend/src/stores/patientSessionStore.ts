import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { patientService, type Patient } from '@/domains/patient/patientService'

const PATIENT_STORAGE_KEY = 'demoPatientId'

function readPersistedPatientId(): string {
  try {
    return localStorage.getItem(PATIENT_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function persistPatientId(patientId: string): void {
  try {
    if (patientId) {
      localStorage.setItem(PATIENT_STORAGE_KEY, patientId)
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

  const selectedPatientId = computed(() =>
    selectedPatient.value ? String(selectedPatient.value.patient_id) : '',
  )

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

  async function selectPatientById(patientId: string): Promise<Patient | null> {
    if (!patientId) {
      selectedPatient.value = null
      persistPatientId('')
      return null
    }

    if (!patients.value.length) {
      await loadPatients()
    }

    const fallback = patients.value.find((p) => String(p.patient_id) === String(patientId)) ?? null

    try {
      const response = await patientService.getById(String(patientId))
      selectedPatient.value = response?.data ?? fallback
    } catch {
      selectedPatient.value = fallback
    }

    persistPatientId(selectedPatient.value ? String(selectedPatient.value.patient_id) : '')

    return selectedPatient.value
  }

  async function initialize(): Promise<void> {
    if (!patients.value.length) {
      await loadPatients()
    }

    if (selectedPatient.value) {
      persistPatientId(String(selectedPatient.value.patient_id))
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
      await selectPatientById(String(patients.value[0].patient_id))
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
