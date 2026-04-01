<script setup lang="ts">
import { computed } from "vue";
import type { ActivePatient, ConsultationStatus } from "./types";

const props = defineProps<{
  activePatient: ActivePatient | null;
  notes: string;
  emptyStateMessage: string;
  issuedDrugCount: number;
  issuedMcCount: number;
  sessionStartedAt: string;
  consultationStatus: ConsultationStatus;
}>();

const emit = defineEmits<{
  (e: "update:notes", value: string): void;
  (e: "end-consultation"): void;
  (e: "patient-no-show"): void;
  (e: "start-consultation"): void;
}>();

function formatTime(value: string): string {
  if (!value || value === "Not started") return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-SG", {
    day: "2-digit",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function getStatusDisplay(status: ConsultationStatus): { label: string; icon: string } {
  switch (status) {
    case "idle": return { label: "Ready", icon: "○" };
    case "connecting": return { label: "Starting...", icon: "◐" };
    case "active": return { label: "Active", icon: "●" };
    case "ended": return { label: "Completed", icon: "✓" };
    default: return { label: "Ready", icon: "○" };
  }
}

const notesComplete = computed(() => props.notes.trim().length > 0);
</script>

<template>
  <div class="consult-panel">
    <template v-if="activePatient">
      <!-- Header -->
      <div class="panel-header">
        <div class="header-left">
          <span class="status-indicator" :class="'status--' + consultationStatus">
            {{ getStatusDisplay(consultationStatus).icon }}
          </span>
          <div class="header-text">
            <h2>Clinical Notes</h2>
            <span class="status-label">{{ getStatusDisplay(consultationStatus).label }}</span>
          </div>
        </div>
        <div class="patient-chip">{{ activePatient.patient_name }}</div>
      </div>

      <!-- Video Call Section -->
      <div class="video-section">
        <div v-if="consultationStatus === 'idle'" class="video-idle">
          <div class="video-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="24" height="24">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </div>
          <div class="video-info">
            <span class="video-title">Video Consultation</span>
            <span class="video-hint">Start the video call to begin</span>
          </div>
          <button class="start-btn" @click="emit('start-consultation')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Start Consultation
          </button>
        </div>

        <div v-else-if="consultationStatus === 'connecting'" class="video-connecting">
          <div class="spinner"></div>
          <span>Connecting...</span>
        </div>

        <div v-else-if="consultationStatus === 'active'" class="video-active">
          <div class="video-info-row">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
            <span>Video call in progress</span>
          </div>
          <a v-if="activePatient.join_url" :href="activePatient.join_url" target="_blank" rel="noopener" class="zoom-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="12" height="12">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            Join Zoom Meeting
          </a>
        </div>

        <div v-else class="video-ended">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <span>Consultation completed</span>
        </div>
      </div>

      <!-- Clinical Notes -->
      <div class="notes-section">
        <div class="section-header">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="15" height="15">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <span>Consultation Notes</span>
          <span v-if="notesComplete" class="saved-badge">✓ Saved</span>
        </div>
        <textarea
          :value="notes"
          placeholder="Document symptoms, diagnosis, treatment plan, and advice..."
          class="notes-textarea"
          @input="emit('update:notes', ($event.target as HTMLTextAreaElement).value)"
        ></textarea>
      </div>

      <!-- Summary -->
      <div class="summary-section">
        <div class="summary-grid">
          <div class="summary-item">
            <span class="summary-label">Started</span>
            <span class="summary-value">{{ formatTime(sessionStartedAt) }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">Prescriptions</span>
            <span class="summary-value" :class="{ 'value--set': issuedDrugCount > 0 }">{{ issuedDrugCount }} medicine(s)</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">MC Issued</span>
            <span class="summary-value" :class="{ 'value--set': issuedMcCount > 0 }">{{ issuedMcCount > 0 ? 'Yes' : 'No' }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">Notes</span>
            <span class="summary-value" :class="{ 'value--set': notesComplete }">{{ notesComplete ? 'Complete' : 'Pending' }}</span>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="actions-section">
        <button class="action-btn action-btn--ghost" @click="emit('patient-no-show')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          No-Show
        </button>
        <button class="action-btn action-btn--end" @click="emit('end-consultation')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" />
          </svg>
          End Consultation
        </button>
      </div>
    </template>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="42" height="42">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
        </svg>
      </div>
      <h3>Ready for Patients</h3>
      <p>{{ emptyStateMessage }}</p>
    </div>
  </div>
</template>

<style scoped>
.consult-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(16, 185, 129, 0.08);
  border-radius: 1rem;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.status-indicator {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
}

.status--idle {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.4);
}
.status--connecting {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
  animation: pulse 1.5s ease-in-out infinite;
}
.status--active {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
}
.status--ended {
  background: rgba(156, 163, 175, 0.12);
  color: #9ca3af;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
}

h2 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.status-label {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
}

.patient-chip {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  color: #34d399;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 2rem;
}

/* Video Section */
.video-section {
  padding: 0.75rem 1rem;
}

.video-idle,
.video-connecting,
.video-active,
.video-ended {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0.7rem;
  padding: 1rem;
}

.video-idle {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.video-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.6rem;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #34d399;
  flex-shrink: 0;
}

.video-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.video-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.video-hint {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.4);
}

.start-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: linear-gradient(135deg, #10b981, #059669);
  border: none;
  border-radius: 0.55rem;
  padding: 0.6rem 0.9rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
}

.start-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.3);
}

.video-connecting {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
}

.spinner {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(16, 185, 129, 0.15);
  border-top-color: #34d399;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.video-active {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.video-info-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #34d399;
  font-size: 0.85rem;
  font-weight: 500;
}

.zoom-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.5);
  text-decoration: none;
  padding: 0.35rem 0.55rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.4rem;
  transition: all 0.15s ease;
}

.zoom-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.75);
}

.video-ended {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.85rem;
}

/* Notes */
.notes-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 1rem;
  margin-bottom: 0.5rem;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 0;
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.section-header svg {
  opacity: 0.7;
}

.saved-badge {
  margin-left: auto;
  font-size: 0.65rem;
  font-weight: 600;
  background: rgba(16, 185, 129, 0.1);
  color: #34d399;
  padding: 0.15rem 0.45rem;
  border-radius: 0.3rem;
  text-transform: none;
  letter-spacing: normal;
}

.notes-textarea {
  flex: 1;
  min-height: 120px;
  resize: none;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.65rem;
  padding: 0.85rem;
  color: #fff;
  font-size: 0.88rem;
  line-height: 1.55;
  font-family: 'DM Sans', system-ui, sans-serif;
}

.notes-textarea:focus {
  outline: none;
  border-color: rgba(16, 185, 129, 0.3);
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.1);
}

.notes-textarea::placeholder {
  color: rgba(255, 255, 255, 0.22);
}

/* Summary */
.summary-section {
  padding: 0 1rem 0.65rem;
}

.summary-grid {
  background: rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 0.65rem;
  padding: 0.65rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.3rem 0;
  font-size: 0.8rem;
}

.summary-label {
  color: rgba(255, 255, 255, 0.4);
}

.summary-value {
  color: rgba(255, 255, 255, 0.55);
  font-weight: 500;
}

.value--set {
  color: #34d399;
}

/* Actions */
.actions-section {
  display: flex;
  gap: 0.6rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  background: rgba(0, 0, 0, 0.08);
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  border: none;
  border-radius: 0.55rem;
  padding: 0.65rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn:active {
  transform: scale(0.98);
}

.action-btn--ghost {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.55);
}

.action-btn--ghost:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
}

.action-btn--end {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.action-btn--end:hover {
  background: rgba(239, 68, 68, 0.2);
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
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
  color: rgba(255, 255, 255, 0.25);
}

.empty-state h3 {
  margin: 0 0 0.3rem;
  font-size: 1rem;
  font-weight: 600;
}

.empty-state p {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.4);
  max-width: 260px;
}
</style>