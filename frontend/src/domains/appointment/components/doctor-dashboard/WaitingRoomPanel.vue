<script setup lang="ts">
import type { QueuePatient } from "./types";

defineProps<{ queuePatients: QueuePatient[]; isCallDisabled?: boolean; isLoading?: boolean }>();
const emit = defineEmits<{ (e: "call-next"): void; (e: "refresh"): void }>();

function getWaitMinutes(index: number): number {
  return (index + 1) * 8;
}

function formatTime(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return "--:--";
  }
}
</script>

<template>
  <div class="queue-panel">
    <div class="panel-header">
      <div class="header-info">
        <h2>Waiting Room</h2>
        <span class="queue-count">{{ queuePatients.length }}</span>
        <button class="refresh-btn" title="Refresh queue" @click="emit('refresh')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="13" height="13">
            <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      </div>
    </div>

    <div class="call-action">
      <button class="call-btn" :disabled="queuePatients.length === 0 || isCallDisabled" @click="emit('call-next')">
        <template v-if="isLoading">
          <span class="spinner" />
          Setting up...
        </template>
        <template v-else>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          Call Next Patient
        </template>
      </button>
    </div>

    <div class="queue-list">
      <TransitionGroup name="queue">
        <div v-for="(patient, index) in queuePatients" :key="patient.id" class="queue-card">
          <div class="card-row">
            <div class="patient-avatar">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" width="18" height="18">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <div class="patient-info">
              <span class="patient-id">{{ patient.patient_id }}</span>
              <span class="patient-time">Joined {{ formatTime(patient.created_at) }}</span>
            </div>
            <div class="wait-badge">
              <span class="wait-time">~{{ getWaitMinutes(index) }} min</span>
            </div>
          </div>
        </div>
      </TransitionGroup>

      <div v-if="queuePatients.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="32" height="32">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </div>
        <h3>No Patients Waiting</h3>
        <p>The waiting room is empty</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.queue-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(16, 185, 129, 0.08);
  border-radius: 1rem;
  overflow: hidden;
}

.panel-header {
  padding: 1rem 1.1rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.header-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

h2 {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.4);
  margin: 0;
}

.queue-count {
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.2);
  color: #34d399;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 2rem;
  min-width: 1.5rem;
  text-align: center;
}

.refresh-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  padding: 0.2rem;
  border-radius: 0.3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  margin-left: auto;
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.refresh-btn:active {
  transform: scale(0.9);
}

.call-action {
  padding: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.call-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  background: linear-gradient(135deg, #10b981, #059669);
  border: none;
  border-radius: 0.65rem;
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.call-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 24px rgba(16, 185, 129, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.call-btn:active:not(:disabled) { transform: translateY(0); }

.call-btn:disabled {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.25);
  box-shadow: none;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.call-btn svg { flex-shrink: 0; }

.queue-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.queue-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.75rem;
  padding: 0.75rem;
  transition: all 0.15s ease;
  cursor: pointer;
}

.queue-card:hover {
  background: rgba(16, 185, 129, 0.04);
  border-color: rgba(16, 185, 129, 0.15);
  transform: translateX(2px);
}

.card-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.patient-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(6, 95, 70, 0.2));
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: #34d399;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.patient-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.patient-id {
  font-size: 0.85rem;
  font-weight: 600;
  color: #fff;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.patient-time {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.35);
}

.wait-badge { flex-shrink: 0; }

.wait-time {
  font-size: 0.68rem;
  font-weight: 600;
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
  padding: 0.25rem 0.5rem;
  border-radius: 0.35rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2.5rem 1rem;
  text-align: center;
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
  color: rgba(255, 255, 255, 0.2);
}

.empty-state h3 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.empty-state p {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.35);
}

/* Queue transition */
.queue-move,
.queue-enter-active,
.queue-leave-active { transition: all 0.3s ease; }

.queue-enter-from,
.queue-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.queue-leave-active { position: absolute; }
</style>