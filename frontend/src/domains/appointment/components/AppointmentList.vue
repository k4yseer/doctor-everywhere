<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Skeleton from 'primevue/skeleton'
import Message from 'primevue/message'
import { useAppointmentStore } from '../appointmentStore'
import type { Appointment, AppointmentStatus } from '../appointmentService'

// props
const props = defineProps<{
  // IDs to display - sourced from a patient or doctor service
  appointmentIds: number[]
}>()

// store
const store = useAppointmentStore()

onMounted(() => {
  Promise.all(props.appointmentIds.map((id) => store.fetchAppointment(id)))
})

// derived data
const appointments = computed<Appointment[]>(() =>
  props.appointmentIds
    .map((id) => store.getById(id))
    .filter((a): a is Appointment => a !== undefined),
)

// helpers
const SKELETON_ROWS = 3

type Severity = 'success' | 'warn' | 'info' | 'danger'

const statusSeverity: Record<AppointmentStatus, Severity> = {
  CONFIRMED: 'success',
  PENDING_PAYMENT: 'warn',
  PAID: 'info',
  NO_SHOW: 'danger',
}

const statusLabel: Record<AppointmentStatus, string> = {
  CONFIRMED: 'Confirmed',
  PENDING_PAYMENT: 'Pending Payment',
  PAID: 'Paid',
  NO_SHOW: 'No Show',
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Error banner -->
    <Message v-if="store.error" severity="error" :closable="false">
      {{ store.error }}
    </Message>

    <!-- Loading skeletons -->
    <template v-if="store.loading && appointments.length === 0">
      <div
        v-for="i in SKELETON_ROWS"
        :key="i"
        class="flex items-center gap-4 rounded-xl border border-(--border) p-4"
      >
        <Skeleton width="3rem" height="3rem" border-radius="50%" />
        <div class="flex flex-1 flex-col gap-2">
          <Skeleton width="40%" height="1rem" />
          <Skeleton width="60%" height="0.75rem" />
        </div>
        <Skeleton width="6rem" height="1.5rem" border-radius="1rem" />
      </div>
    </template>

    <!-- Data table -->
    <DataTable
      v-else
      :value="appointments"
      :loading="store.loading"
      striped-rows
      class="rounded-xl border border-(--border) overflow-hidden"
    >
      <template #empty>
        <div class="py-10 text-center text-(--text) opacity-60">
          No appointments found.
        </div>
      </template>

      <Column field="id" header="ID" class="w-16 font-mono text-sm" />

      <Column header="Patient ID" field="patient_id" class="w-28" />

      <Column header="Doctor ID" field="doctor_id" class="w-28" />

      <Column header="Slot" field="slot_datetime">
        <template #body="{ data }: { data: Appointment }">
          {{ formatDateTime(data.slot_datetime) }}
        </template>
      </Column>

      <Column header="Meet Link">
        <template #body="{ data }: { data: Appointment }">
          <a
            v-if="data.meet_link"
            :href="data.meet_link"
            target="_blank"
            rel="noopener noreferrer"
            class="text-(--accent) underline underline-offset-2 hover:opacity-75 transition-opacity"
          >
            Join
          </a>
          <span v-else class="opacity-40">—</span>
        </template>
      </Column>

      <Column header="Status" field="status" class="w-40">
        <template #body="{ data }: { data: Appointment }">
          <Tag
            :severity="statusSeverity[data.status]"
            :value="statusLabel[data.status]"
            rounded
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>
