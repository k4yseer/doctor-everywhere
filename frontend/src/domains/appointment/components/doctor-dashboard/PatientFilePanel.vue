<script setup lang="ts">
import { ref, watch, computed } from "vue";
import type { MedicineItem, MedicalCertificateDraft, ActivePatient, Medicine } from "./types";

const props = defineProps<{
  activePatient: ActivePatient | null;
  prescribedMedicines: MedicineItem[];
  emptyStateMessage: string;
  medicines: Medicine[];
}>();

const emit = defineEmits<{
  (e: "add-medicine", medicine: { name: string; medicineCode: string }): void;
  (e: "remove-medicine", medicineId: number): void;
  (e: "update-instruction", payload: { id: number; value: string }): void;
  (e: "update-quantity", payload: { id: number; value: number }): void;
  (e: "update-mc", payload: MedicalCertificateDraft): void;
}>();

const mcDays = ref(1);
const mcStartDate = ref(new Date().toISOString().slice(0, 10));
const mcSummary = ref("");
const medicineSearch = ref("");
const showDropdown = ref(false);
const activeTab = ref<"prescription" | "mc">("prescription");

const filteredMedicines = computed(() => {
  const query = medicineSearch.value.toLowerCase().trim();
  if (!query) return props.medicines.slice(0, 12);
  return props.medicines
    .filter((m) => m.medicine_name.toLowerCase().includes(query) || m.medicine_code.toLowerCase().includes(query))
    .slice(0, 10);
});

function selectMedicine(med: Medicine): void {
  emit("add-medicine", { name: med.medicine_name, medicineCode: med.medicine_code });
  medicineSearch.value = "";
  showDropdown.value = false;
}

function handleInputFocus(): void {
  showDropdown.value = true;
}

function handleBlur(): void {
  setTimeout(() => {
    showDropdown.value = false;
  }, 150);
}

watch(
  [mcDays, mcStartDate, mcSummary],
  () => {
    emit("update-mc", {
      leaveDays: mcDays.value,
      diagnosisSummary: mcSummary.value.trim(),
      startDate: mcStartDate.value,
    });
  },
  { immediate: true }
);

// Reset MC form whenever patient changes
watch(
  () => props.activePatient?.patient_id,
  () => {
    mcDays.value = 1;
    mcStartDate.value = new Date().toISOString().slice(0, 10);
    mcSummary.value = "";
    activeTab.value = "prescription";
    medicineSearch.value = "";
    showDropdown.value = false;
  }
);

const hasAllergies = computed(
  () => props.activePatient?.allergies && props.activePatient.allergies.length > 0
);
const mcReady = computed(() => mcSummary.value.trim().length > 0 && mcDays.value > 0);

function formatHistoryDate(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-SG', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}
</script>

<template>
  <div class="patient-panel">
    <template v-if="activePatient">
      <!-- Header -->
      <div class="panel-header">
        <h2>Patient File</h2>
      </div>

      <!-- Patient Card -->
      <div class="patient-card">
        <div class="patient-row">
          <div class="patient-avatar">{{ (activePatient.patient_name || '?').charAt(0).toUpperCase() }}</div>
          <div class="patient-details">
            <span class="patient-name">{{ activePatient.patient_name || 'Unknown' }}</span>
            <span class="patient-meta">{{ activePatient.patient_id }} · {{ activePatient.age || '--' }}y · {{ activePatient.gender || '--' }}</span>
          </div>
        </div>

        <!-- Allergies Banner - Always visible -->
        <div v-if="hasAllergies" class="allergy-banner">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <div class="allergy-content">
            <span class="allergy-label">Allergies:</span>
            <span class="allergy-list">{{ activePatient.allergies.join(', ') }}</span>
          </div>
        </div>
        <div v-else class="allergy-banner allergy-banner--none">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <span>No known allergies</span>
        </div>
      </div>

      <!-- Scrollable Content -->
      <div class="panel-content">
        <!-- History -->
        <section class="section">
          <div class="section-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>History</span>
          </div>
          <div class="history-list">
            <div v-for="visit in activePatient.history" :key="visit.appointment_id" class="history-item">
              <div class="history-date">{{ formatHistoryDate(visit.date) }}</div>
              <div class="history-content">
                <p v-if="visit.clinical_notes" class="history-note">{{ visit.clinical_notes }}</p>
                <p v-else class="history-note history-note--empty">No notes recorded</p>
              </div>
            </div>
            <div v-if="activePatient.history.length === 0" class="empty-note">No previous consultations</div>
          </div>
        </section>

        <!-- Tab Switcher -->
        <div class="tab-switcher">
          <button :class="['tab-btn', { active: activeTab === 'prescription' }]" @click="activeTab = 'prescription'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
              <path d="M10.5 20.5H3a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6" />
              <path d="M16 5v3a2 2 0 0 0 2 2h3" />
              <path d="M22 17.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z" />
            </svg>
            Prescription
            <span v-if="prescribedMedicines.length > 0" class="tab-count">{{ prescribedMedicines.length }}</span>
          </button>
          <button :class="['tab-btn', { active: activeTab === 'mc' }]" @click="activeTab = 'mc'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            MC
            <span v-if="mcReady" class="tab-badge">✓</span>
          </button>
        </div>

        <!-- Prescription Tab -->
        <section v-if="activeTab === 'prescription'" class="section section--tab">
          <!-- Medicine Search with + button -->
          <div class="search-container">
            <div class="search-wrap">
              <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
              </svg>
              <input
                v-model="medicineSearch"
                type="text"
                placeholder="Search medicines..."
                @focus="handleInputFocus"
                @blur="handleBlur"
                @keyup.enter="medicineSearch && filteredMedicines[0] && selectMedicine(filteredMedicines[0])"
              />
            </div>

            <!-- Dropdown -->
            <div v-if="showDropdown && filteredMedicines.length > 0" class="dropdown">
              <button
                v-for="med in filteredMedicines"
                :key="med.medicine_code"
                class="dropdown-item"
                @click="selectMedicine(med)"
              >
                <div class="med-info">
                  <span class="med-name">{{ med.medicine_name }}</span>
                  <span class="med-code">{{ med.medicine_code }}</span>
                </div>
                <div class="med-meta">
                  <span class="med-stock" :class="{ low: med.stock_available < 10 }">
                    {{ med.stock_available }} in stock
                  </span>
                  <span class="add-btn">+</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Prescribed List -->
          <div class="rx-list">
            <div v-for="medicine in prescribedMedicines" :key="medicine.id" class="rx-item">
              <div class="rx-header">
                <span class="rx-name">{{ medicine.medicine_name }}</span>
                <button class="rx-remove" @click="emit('remove-medicine', medicine.id)" aria-label="Remove">×</button>
              </div>
              <div class="rx-fields">
                <input
                  :value="medicine.instruction"
                  type="text"
                  class="rx-input"
                  placeholder="Dosage instructions..."
                  @input="emit('update-instruction', { id: medicine.id, value: ($event.target as HTMLInputElement).value })"
                />
                <input
                  :value="medicine.dispense_quantity"
                  type="number"
                  min="1"
                  max="99"
                  class="rx-qty"
                  @input="emit('update-quantity', { id: medicine.id, value: parseInt(($event.target as HTMLInputElement).value) || 1 })"
                />
              </div>
            </div>
            <div v-if="prescribedMedicines.length === 0" class="rx-empty">
              <p>No medicines prescribed</p>
              <span>Search and add medicines above</span>
            </div>
          </div>
        </section>

        <!-- MC Tab -->
        <section v-if="activeTab === 'mc'" class="section section--tab">
          <div class="mc-form">
            <div class="mc-field">
              <label>Diagnosis & Reason for Leave</label>
              <textarea v-model="mcSummary" placeholder="Enter diagnosis and reason for medical leave..." rows="3" />
            </div>
            <div class="mc-row">
              <div class="mc-field">
                <label>Start Date</label>
                <input v-model="mcStartDate" type="date" />
              </div>
              <div class="mc-field">
                <label>Days</label>
                <input v-model.number="mcDays" type="number" min="1" max="30" />
              </div>
            </div>
          </div>

          <div v-if="mcReady" class="mc-preview">
            <strong>{{ mcDays }} day(s)</strong> from {{ mcStartDate }}
            <p>{{ mcSummary }}</p>
          </div>
        </section>
      </div>
    </template>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="36" height="36">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
        </svg>
      </div>
      <h3>No Patient Selected</h3>
      <p>{{ emptyStateMessage }}</p>
    </div>
  </div>
</template>

<style scoped>
.patient-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(16, 185, 129, 0.08);
  border-radius: 1rem;
  overflow: hidden;
}

.panel-header {
  padding: 1rem 1.1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

h2 {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.4);
  margin: 0;
}

/* Patient Card */
.patient-card {
  padding: 0.9rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.patient-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.patient-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(6, 95, 70, 0.2));
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: #34d399;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  font-weight: 700;
  flex-shrink: 0;
}

.patient-details {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.patient-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: #fff;
}

.patient-meta {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.allergy-banner {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.7rem;
  padding: 0.45rem 0.55rem;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 0.45rem;
  font-size: 0.75rem;
  color: #fca5a5;
}

.allergy-banner--none {
  background: rgba(16, 185, 129, 0.06);
  border-color: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.allergy-content {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
}

.allergy-label {
  font-size: 0.65rem;
  font-weight: 600;
  opacity: 0.8;
}

.allergy-list {
  font-weight: 500;
}

/* Content */
.panel-content {
  flex: 1;
  overflow: hidden;
  padding: 0.7rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 0.7rem;
  padding: 0.7rem;
}

.section--tab {
  background: transparent;
  border: none;
  padding: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.section-header svg {
  opacity: 0.7;
}

/* History */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 140px;
  overflow-y: auto;
}

.history-item {
  padding-left: 0.65rem;
  border-left: 2px solid rgba(16, 185, 129, 0.25);
}

.history-date {
  font-size: 0.65rem;
  color: #34d399;
  font-weight: 500;
  margin-bottom: 0.1rem;
}

.history-content {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
}

.history-doctor {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
}

.history-note {
  margin: 0;
  font-size: 0.76rem;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.4;
}

.history-note--empty {
  color: rgba(255, 255, 255, 0.25);
  font-style: italic;
}

.history-rx {
  font-size: 0.68rem;
  color: #34d399;
  margin-top: 0.15rem;
  display: block;
}

.empty-note {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
  padding: 0.4rem;
}

/* Tab Switcher */
.tab-switcher {
  display: flex;
  gap: 0.3rem;
  padding: 0.2rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 0.55rem;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  background: transparent;
  border: none;
  border-radius: 0.45rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: rgba(255, 255, 255, 0.7);
}

.tab-btn.active {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
}

.tab-count {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
  border-radius: 1rem;
}

.tab-badge {
  font-size: 0.65rem;
  color: #34d399;
}

/* Search */
.search-container {
  position: relative;
  margin-bottom: 0.5rem;
}

.search-wrap {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 0.7rem;
  top: 50%;
  transform: translateY(-50%);
  color: rgba(255, 255, 255, 0.3);
}

.search-wrap input {
  width: 100%;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.45rem;
  padding: 0.55rem 0.7rem 0.55rem 2.1rem;
  color: #fff;
  font-size: 0.8rem;
}

.search-wrap input:focus {
  outline: none;
  border-color: rgba(16, 185, 129, 0.4);
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.1);
}

.search-wrap input::placeholder {
  color: rgba(255, 255, 255, 0.25);
}

/* Dropdown */
.dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: rgba(10, 30, 20, 0.98);
  border: 1px solid rgba(16, 185, 129, 0.15);
  border-radius: 0.55rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  max-height: 160px;
  overflow-y: auto;
  z-index: 100;
}

.dropdown-item {
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  padding: 0.6rem 0.75rem;
  text-align: left;
  cursor: pointer;
  transition: background 0.1s;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dropdown-item:last-child {
  border-bottom: none;
}

.dropdown-item:hover {
  background: rgba(16, 185, 129, 0.08);
}

.med-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.med-name {
  font-size: 0.82rem;
  color: #fff;
  font-weight: 500;
}

.med-code {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.med-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.med-stock {
  font-size: 0.68rem;
  color: #34d399;
}

.med-stock.low {
  color: #fbbf24;
}

.add-btn {
  width: 22px;
  height: 22px;
  background: rgba(16, 185, 129, 0.15);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  color: #34d399;
  font-weight: 700;
}

/* Rx List */
.rx-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  overflow-y: auto;
  flex: 1;
}

.rx-item {
  background: rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0.5rem;
  padding: 0.55rem;
}

.rx-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.35rem;
}

.rx-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
}

.rx-remove {
  background: rgba(239, 68, 68, 0.12);
  border: none;
  color: #fca5a5;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
  transition: background 0.15s;
}

.rx-remove:hover {
  background: rgba(239, 68, 68, 0.2);
}

.rx-fields {
  display: flex;
  gap: 0.4rem;
}

.rx-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.35rem;
  padding: 0.35rem 0.45rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.72rem;
}

.rx-input:focus {
  outline: none;
  border-color: rgba(16, 185, 129, 0.4);
}

.rx-input::placeholder {
  color: rgba(255, 255, 255, 0.25);
}

.rx-qty {
  width: 50px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.35rem;
  padding: 0.35rem 0.35rem;
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.72rem;
  text-align: center;
}

.rx-qty:focus {
  outline: none;
  border-color: rgba(16, 185, 129, 0.4);
}

.rx-empty {
  text-align: center;
  padding: 0.75rem;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  border-radius: 0.5rem;
}

.rx-empty p {
  margin: 0 0 0.15rem;
  font-size: 0.76rem;
  color: rgba(255, 255, 255, 0.4);
}

.rx-empty span {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.25);
}

/* MC Form */
.mc-form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-y: auto;
}

.mc-field {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.mc-field label {
  font-size: 0.66rem;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 500;
}

.mc-field input,
.mc-field textarea {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.4rem;
  padding: 0.45rem 0.55rem;
  color: #fff;
  font-size: 0.78rem;
  font-family: inherit;
}

.mc-field input:focus,
.mc-field textarea:focus {
  outline: none;
  border-color: rgba(168, 85, 247, 0.4);
}

.mc-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.mc-preview {
  margin-top: 0.5rem;
  padding: 0.55rem;
  background: rgba(168, 85, 247, 0.06);
  border: 1px solid rgba(168, 85, 247, 0.15);
  border-radius: 0.4rem;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.7);
}

.mc-preview p {
  margin: 0.15rem 0 0;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.45);
  font-style: italic;
}

/* Empty */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.75rem;
  color: rgba(255, 255, 255, 0.25);
}

.empty-state h3 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.empty-state p {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.4);
  max-width: 200px;
}
</style>