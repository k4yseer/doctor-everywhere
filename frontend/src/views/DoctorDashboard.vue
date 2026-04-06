<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import apiClient from "@/core/apiClient";
import ConsultationHubPanel from "@/domains/appointment/components/doctor-dashboard/ConsultationHubPanel.vue";
import PatientFilePanel from "@/domains/appointment/components/doctor-dashboard/PatientFilePanel.vue";
import WaitingRoomPanel from "@/domains/appointment/components/doctor-dashboard/WaitingRoomPanel.vue";
import type { MedicineItem, MedicalCertificateDraft, QueuePatient, ActivePatient, ConsultationStatus, Medicine } from "@/domains/appointment/components/doctor-dashboard/types";
import { QueueService } from "@/domains/appointment/queueService";
import { patientService } from "@/domains/patient/patientService";
import { getPatientVisitHistory } from "@/domains/appointment/consultationHistoryService";
import { inventoryService } from "@/domains/inventory/inventoryService";
import { prescriptionService } from "@/domains/prescription/prescriptionService";

// ── Constants ───────────────────────────────────────────────────
const DOCTOR_ID = 1;

// ── State ───────────────────────────────────────────────────────

const queuePatients = ref<QueuePatient[]>([]);
const activePatient = ref<ActivePatient | null>(null);
const consultationNotes = ref("");
const prescribedMedicines = ref<MedicineItem[]>([]);
const sessionStartedAt = ref("");
const consultationStatus = ref<ConsultationStatus>("idle");
const medicines = ref<Medicine[]>([]);
const showEndConfirmation = ref(false);
const showNoShowConfirmation = ref(false);
const isCallingNext = ref(false);

// Toast system
const toastMessage = ref('');
const toastType = ref<'success' | 'warning' | 'error'>('success');
const showToast = ref(false);
let toastTimer: ReturnType<typeof setTimeout> | null = null;

function displayToast(message: string, type: 'success' | 'warning' | 'error' = 'success') {
  toastMessage.value = message;
  toastType.value = type;
  showToast.value = true;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { showToast.value = false; }, 4000);
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  const maybeResponse = (error as { response?: { data?: { message?: unknown } } })?.response;
  const message = maybeResponse?.data?.message;
  if (typeof message === "string" && message.trim()) {
    return message.trim();
  }
  return fallback;
}

const mcDraft = ref<MedicalCertificateDraft>({
  leaveDays: 1,
  diagnosisSummary: "",
  startDate: new Date().toISOString().slice(0, 10),
});

const issuedMcCount = computed(() => (mcDraft.value.diagnosisSummary.trim() ? 1 : 0));
const emptyStateMessage = "Ready for next patient. Click 'Call Next Patient' to begin.";

// ── Data Fetching ───────────────────────────────────────────────

let pollInterval: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  loadQueue();
  loadMedicines();
  
  // Auto-refresh queue every 15 seconds
  pollInterval = setInterval(loadQueue, 15000);
});

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval);
});

async function loadQueue() {
  try {
    const res = await QueueService.getAll();
    const entries = res.data ?? [];

    const uniquePatientIds = Array.from(new Set(entries.map((e) => e.patient_id)));
    const patientNameMap = new Map<number, string>();

    await Promise.all(
      uniquePatientIds.map(async (pid) => {
        try {
          const details = await patientService.getById(pid);
          const name = details?.data?.patient_name;
          if (name) patientNameMap.set(pid, name);
        } catch {
          // Keep queue rendering resilient when patient-details lookup fails.
        }
      }),
    );

    queuePatients.value = entries.map((entry) => ({
      ...entry,
      patient_name: patientNameMap.get(entry.patient_id) ?? `Patient ${entry.patient_id}`,
    }));
  } catch (e) { console.error("Failed to fetch queue:", e); }
}

async function loadMedicines() {
  try {
    medicines.value = await inventoryService.getAllMedicines();
  } catch (e) { console.error("Failed to fetch medicines:", e); }
}

// ── Call Next Patient (hydrates patient info on-demand) ─────────

async function callNextPatient() {
  if (isCallingNext.value) return;
  if (activePatient.value) return;

  isCallingNext.value = true;
  try {
    const payload: Record<string, unknown> = { doctor_id: DOCTOR_ID };

     // Call setup-consultation (handles dequeueing, Zoom creation, appointment creation, and emailing patient)
    const { data } = await apiClient.post('/setup-consultation/next-patient', payload);
    const pid = data.patient.patient_id;
    const appointmentId = data.appointment_id;
    
    // Refresh queue locally since we just dequeued
    loadQueue();

    // Calculate age from dob
    let age = null;
    if (data.patient.date_of_birth) {
      const diffDates = Date.now() - new Date(data.patient.date_of_birth).getTime();
      age = new Date(diffDates).getUTCFullYear() - 1970;
    }

    // Show patient immediately — don't wait for allergies/history
    activePatient.value = {
      id: 0,
      patient_id: pid,
      patient_name: data.patient.patient_name ?? `Patient ${pid}`,
      age: age,
      gender: data.patient.gender ?? null,
      allergies: [],
      history: [],
      appointment_id: appointmentId,
      join_url: data.start_url,
    };

    resetSessionState();
    consultationStatus.value = "idle";

    // Backfill allergies & history in background (non-blocking)
    Promise.all([
      patientService.getAllergies(pid).then(r => (r.data ?? []).map(a => a.allergy)).catch(() => [] as string[]),
      getPatientVisitHistory(pid),
    ]).then(([allergies, rawHistory]) => {
      if (!activePatient.value || activePatient.value.patient_id !== pid) return; // stale or cleared
      const currentAppointmentId = activePatient.value.appointment_id;
      const history = rawHistory
      .filter((item) => item.appointment_id !== currentAppointmentId)
      .sort((a, b) => {
        if (!a.date) return 1;
        if (!b.date) return -1;
        return new Date(b.date).getTime() - new Date(a.date).getTime();
      });
      activePatient.value = { ...activePatient.value!, allergies, history };
    });
    
  } catch (err: any) {
    if (err.response?.status === 404) {
      displayToast('Queue is empty.', 'warning');
      loadQueue();
    } else {
      console.error("Failed to setup consultation:", err);
      displayToast('Something went wrong setting up the consultation.', 'error');
    }
  } finally {
    isCallingNext.value = false;
  }
}

// ── Consultation Lifecycle ──────────────────────────────────────

function startConsultation() {
  if (activePatient.value?.join_url) {
    window.open(activePatient.value.join_url, '_blank', 'noopener');
  }
  consultationStatus.value = "connecting";
  setTimeout(() => {
    consultationStatus.value = "active";
    sessionStartedAt.value = new Date().toISOString();
  }, 1500);
}

function requestEndConsultation() { showEndConfirmation.value = true; }
function requestNoShow() { showNoShowConfirmation.value = true; }
function cancelConfirmation() { showEndConfirmation.value = false; showNoShowConfirmation.value = false; }

async function confirmEndConsultation() {
  showEndConfirmation.value = false;
  await submitConsultation();
}

async function confirmNoShow() {
  showNoShowConfirmation.value = false;
  await submitNoShow();
}

async function submitConsultation() {
  if (!activePatient.value?.appointment_id) return;
  const p = activePatient.value;

  try {
    await prescriptionService.create({
      appointment_id: p.appointment_id,
      patient_id: p.patient_id,
      consultation_notes: consultationNotes.value,
      medicines: prescribedMedicines.value.map(m => ({
        medicine_code: m.medicine_code,
        medicine_name: m.medicine_name,
        dosage_instructions: m.instruction || "",
        dispense_quantity: m.dispense_quantity || 1,
      })),
      mc_start_date: mcDraft.value.diagnosisSummary.trim() ? mcDraft.value.startDate : null,
      mc_duration_days: mcDraft.value.diagnosisSummary.trim() ? mcDraft.value.leaveDays : null,
      mc_diagnosis: mcDraft.value.diagnosisSummary.trim() || null,
    });

    displayToast(`Consultation for ${p.patient_name} submitted successfully.`, 'success');
    closeSession();
    loadMedicines();
  } catch (e: unknown) {
    console.error("Failed to submit consultation:", e);
    displayToast(getApiErrorMessage(e, 'Failed to submit consultation. Please try again.'), 'error');
  }
}

async function submitNoShow() {
  if (!activePatient.value?.appointment_id) return;
  const { appointment_id, patient_name } = activePatient.value;
  try {
    await apiClient.post('/setup-consultation/no-show', { appointment_id });
    displayToast(`${patient_name} marked as no-show.`, 'warning');
    closeSession();
    loadQueue();
  } catch (e) {
    console.error("Failed to mark no-show:", e);
    displayToast('Failed to mark no-show. Please try again.', 'error');
  }
}

function closeSession() {
  activePatient.value = null;
  resetSessionState();
}

function resetSessionState() {
  consultationNotes.value = "";
  prescribedMedicines.value = [];
  sessionStartedAt.value = "";
  mcDraft.value = { leaveDays: 1, diagnosisSummary: "", startDate: new Date().toISOString().slice(0, 10) };
  consultationStatus.value = "idle";
}

// ── Medicine Management ─────────────────────────────────────────

function addMedicine(medicine: { name: string; medicineCode: string }) {
  prescribedMedicines.value.push({ id: Date.now(), medicine_code: medicine.medicineCode, medicine_name: medicine.name, instruction: "", dispense_quantity: 1 });
}

function removeMedicine(medicineId: number) {
  prescribedMedicines.value = prescribedMedicines.value.filter(m => m.id !== medicineId);
}

function updateMedicineInstruction({ id, value }: { id: number; value: string }) {
  prescribedMedicines.value = prescribedMedicines.value.map(m => m.id === id ? { ...m, instruction: value } : m);
}

function updateMedicineQuantity({ id, value }: { id: number; value: number }) {
  prescribedMedicines.value = prescribedMedicines.value.map(m => m.id === id ? { ...m, dispense_quantity: value } : m);
}

function updateMedicalCertificateDraft(payload: MedicalCertificateDraft) {
  mcDraft.value = payload;
}
</script>

<template>
  <div class="dd-page">
    <div class="dd-bg" />

    <!-- Navbar -->
    <nav class="dd-nav">
      <div class="nav-left">
        <img src="/doctor-everywhere-logo.png" alt="Doctor Everywhere" class="nav-logo" />
        <span class="nav-title">Doctor Dashboard</span>
      </div>
      <div class="nav-right">
        <span class="nav-status" :class="{ 'nav-status--active': activePatient }">
          {{ activePatient ? 'In Consultation' : 'Available' }}
        </span>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="dd-main">
      <div class="dd-grid">
        <!-- Left: Queue -->
        <section class="dd-queue">
          <WaitingRoomPanel :queue-patients="queuePatients" :is-call-disabled="!!activePatient || isCallingNext" :is-loading="isCallingNext" @call-next="callNextPatient()" @refresh="loadQueue" />
        </section>

        <!-- Center: Consultation Notes -->
        <section class="dd-consultation">
          <ConsultationHubPanel
            :active-patient="activePatient"
            :notes="consultationNotes"
            :empty-state-message="emptyStateMessage"
            :issued-medicine-count="prescribedMedicines.length"
            :issued-mc-count="issuedMcCount"
            :session-started-at="sessionStartedAt || 'Not started'"
            :consultation-status="consultationStatus"
            @update:notes="consultationNotes = $event"
            @start-consultation="startConsultation"
            @end-consultation="requestEndConsultation"
            @patient-no-show="requestNoShow"
          />
        </section>

        <!-- Right: Patient File & Rx -->
        <section class="dd-patient">
          <PatientFilePanel
            :active-patient="activePatient"
            :prescribed-medicines="prescribedMedicines"
            :empty-state-message="emptyStateMessage"
            :medicines="medicines"
            @add-medicine="addMedicine"
            @remove-medicine="removeMedicine"
            @update-instruction="updateMedicineInstruction"
            @update-quantity="updateMedicineQuantity"
            @update-mc="updateMedicalCertificateDraft"
          />
        </section>
      </div>
    </main>

    <!-- End Consultation Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showEndConfirmation" class="modal-overlay" @click.self="cancelConfirmation">
          <div class="modal">
            <div class="modal-header">
              <h3>End Consultation?</h3>
            </div>
            <div class="modal-body">
              <p>Are you sure you want to end this consultation?</p>
              <div class="modal-summary">
                <div class="summary-item">
                  <span>Clinical Notes</span>
                  <span :class="consultationNotes.trim() ? 'status-ok' : 'status-pending'">
                    {{ consultationNotes.trim() ? 'Saved' : 'Empty' }}
                  </span>
                </div>
                <div class="summary-item">
                  <span>Prescriptions</span>
                  <span :class="prescribedMedicines.length > 0 ? 'status-ok' : 'status-pending'">
                    {{ prescribedMedicines.length }} medicine(s)
                  </span>
                </div>
                <div class="summary-item">
                  <span>Medical Certificate</span>
                  <span :class="issuedMcCount > 0 ? 'status-ok' : 'status-pending'">
                    {{ issuedMcCount > 0 ? 'Issued' : 'None' }}
                  </span>
                </div>
              </div>
            </div>
            <div class="modal-actions">
              <button class="btn btn-ghost" @click="cancelConfirmation">Cancel</button>
              <button class="btn btn-primary" @click="confirmEndConsultation">End & Submit</button>
            </div>
          </div>
        </div>
      </Transition>

      <Transition name="modal">
        <div v-if="showNoShowConfirmation" class="modal-overlay" @click.self="cancelConfirmation">
          <div class="modal modal--warning">
            <div class="modal-header">
              <h3>Patient No-Show</h3>
            </div>
            <div class="modal-body">
              <p>Mark <strong>{{ activePatient?.patient_name }}</strong> as no-show?</p>
              <p class="modal-hint">The patient will be removed from the queue.</p>
            </div>
            <div class="modal-actions">
              <button class="btn btn-ghost" @click="cancelConfirmation">Cancel</button>
              <button class="btn btn-warning" @click="confirmNoShow">Mark No-Show</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Toast Notification -->
    <Transition name="toast">
      <div v-if="showToast" class="toast" :class="'toast--' + toastType">
        <span class="toast-icon">
          <template v-if="toastType === 'success'">✓</template>
          <template v-else-if="toastType === 'warning'">⚠</template>
          <template v-else>✕</template>
        </span>
        <span class="toast-text">{{ toastMessage }}</span>
        <button class="toast-close" @click="showToast = false">×</button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dd-page {
  min-height: 100vh;
  background: #0a1410;
  color: #fff;
  font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
  position: relative;
  overflow: hidden;
}

.dd-bg {
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 70% 10%, rgba(16, 185, 129, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse 50% 40% at 10% 90%, rgba(6, 78, 59, 0.12) 0%, transparent 50%),
    linear-gradient(180deg, #0a1410 0%, #071a12 100%);
  pointer-events: none;
  z-index: 0;
}

/* Navbar */
.dd-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1.5rem;
  background: rgba(10, 20, 16, 0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(16, 185, 129, 0.1);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.nav-logo {
  height: 28px;
  width: 28px;
  object-fit: contain;
  filter: brightness(1.2);
}

.nav-title {
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: rgba(255, 255, 255, 0.9);
}

.nav-status {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.4rem 0.9rem;
  border-radius: 2rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.nav-status--active {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.3);
  color: #34d399;
}

/* Main */
.dd-main {
  position: relative;
  z-index: 10;
  height: calc(100vh - 52px);
  padding: 1rem 1.25rem;
  overflow: hidden;
}

.dd-grid {
  display: grid;
  grid-template-columns: 260px 1fr 340px;
  gap: 1rem;
  height: 100%;
}

.dd-queue,
.dd-consultation,
.dd-patient {
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 1280px) {
  .dd-grid {
    grid-template-columns: 240px 1fr 300px;
  }
}

@media (max-width: 1100px) {
  .dd-main {
    height: auto;
    min-height: calc(100vh - 52px);
    overflow-y: auto;
  }
  .dd-grid {
    grid-template-columns: 1fr;
    height: auto;
    gap: 1rem;
  }
  .dd-queue,
  .dd-consultation,
  .dd-patient {
    max-height: none;
    overflow: visible;
  }
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal {
  background: linear-gradient(145deg, rgba(16, 32, 26, 0.98), rgba(10, 24, 18, 0.98));
  border: 1px solid rgba(16, 185, 129, 0.15);
  border-radius: 1rem;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(16, 185, 129, 0.05);
  width: 100%;
  max-width: 380px;
}

.modal--warning {
  border-color: rgba(251, 191, 36, 0.2);
}

.modal-header {
  padding: 1.25rem 1.5rem 0.75rem;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.modal-body {
  padding: 0 1.5rem 1rem;
}

.modal-body p {
  margin: 0 0 0.5rem;
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
}

.modal-hint {
  font-size: 0.8rem !important;
  color: rgba(255, 255, 255, 0.4) !important;
}

.modal-summary {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0.75rem;
  padding: 0.75rem;
  margin-top: 0.75rem;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.45rem 0;
  font-size: 0.82rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.summary-item:last-child {
  border-bottom: none;
}

.summary-item span:first-child {
  color: rgba(255, 255, 255, 0.5);
}

.status-ok {
  color: #34d399;
  font-weight: 600;
}
.status-pending {
  color: rgba(255, 255, 255, 0.35);
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.25rem;
}

.btn {
  border: none;
  border-radius: 0.6rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0.7rem 1.25rem;
  font-size: 0.88rem;
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}

.btn:hover {
  transform: translateY(-1px);
}
.btn:active {
  transform: translateY(0);
}

.btn-ghost {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.1);
}

.btn-primary {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  flex: 1;
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.25);
}

.btn-primary:hover {
  box-shadow: 0 6px 24px rgba(16, 185, 129, 0.35);
}

.btn-warning {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff;
  flex: 1;
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.25);
}

.btn-warning:hover {
  box-shadow: 0 6px 24px rgba(245, 158, 11, 0.35);
}

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal,
.modal-leave-active .modal {
  transition: transform 0.2s ease;
}
.modal-enter-from .modal,
.modal-leave-to .modal {
  transform: scale(0.95);
}

/* Toast */
.toast {
  position: fixed;
  top: 1.25rem;
  right: 1.25rem;
  z-index: 2000;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.8rem 1rem;
  border-radius: 0.65rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #fff;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  max-width: 380px;
}

.toast--success {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.92), rgba(5, 150, 105, 0.92));
  border: 1px solid rgba(52, 211, 153, 0.3);
}

.toast--warning {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.92), rgba(217, 119, 6, 0.92));
  border: 1px solid rgba(251, 191, 36, 0.3);
}

.toast--error {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.92), rgba(185, 28, 28, 0.92));
  border: 1px solid rgba(252, 165, 165, 0.3);
}

.toast-icon {
  font-size: 1rem;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.toast-text {
  flex: 1;
  line-height: 1.4;
}

.toast-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0 0.15rem;
  line-height: 1;
}

.toast-close:hover {
  color: #fff;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(60px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(60px);
}
</style>