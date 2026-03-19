import { defineStore } from "pinia";
import { ref } from "vue";
import {
  AppointmentService,
  type Appointment,
  type AppointmentStatus,
  type CreateAppointmentPayload,
} from "./appointmentService";

export const useAppointmentStore = defineStore("appointment", () => {
  // state
  const appointments = ref<Map<number, Appointment>>(new Map());
  const loading = ref(false);
  const error = ref<string | null>(null);

  // helpers
  function setError(err: unknown) {
    error.value =
      err instanceof Error ? err.message : "An unexpected error occurred";
  }

  function clearError() {
    error.value = null;
  }

  // actions
  async function fetchAppointment(id: number): Promise<Appointment | null> {
    // return from cache if already loaded
    if (appointments.value.has(id)) return appointments.value.get(id)!;

    loading.value = true;
    clearError();
    try {
      const appointment = await AppointmentService.getAppointment(id);
      appointments.value.set(appointment.id, appointment);
      return appointment;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createAppointment(
    payload: CreateAppointmentPayload,
  ): Promise<Appointment | null> {
    loading.value = true;
    clearError();
    try {
      const response = await AppointmentService.createAppointment(payload);
      appointments.value.set(response.data.id, response.data);
      return response.data;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function updateAppointmentStatus(
    id: number,
    status: AppointmentStatus,
  ): Promise<Appointment | null> {
    loading.value = true;
    clearError();
    try {
      const updated = await AppointmentService.updateAppointmentStatus(id, {
        status,
      });
      appointments.value.set(updated.id, updated);
      return updated;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      loading.value = false;
    }
  }

  // getters
  function getById(id: number): Appointment | undefined {
    return appointments.value.get(id);
  }

  return {
    // state
    appointments,
    loading,
    error,
    // actions
    fetchAppointment,
    createAppointment,
    updateAppointmentStatus,
    // getters
    getById,
  };
});
