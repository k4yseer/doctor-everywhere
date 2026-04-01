import apiClient from "@/core/apiClient";

export type AppointmentStatus = "CONFIRMED" | "PENDING_PAYMENT" | "PAID" | "NO_SHOW";

export interface Appointment {
  id: number;
  patient_id: number;
  doctor_id: number;
  slot_datetime: string;
  meet_link: string | null;
  status: AppointmentStatus;
}

export interface CreateAppointmentPayload {
  patient_id: number;
  doctor_id: number;
  slot_datetime: string;
  meet_link?: string;
}

export interface UpdateAppointmentStatusPayload {
  status: AppointmentStatus;
}

interface GetAppointmentResponse {
  code: 200;
  data: Appointment;
}

interface CreateAppointmentResponse {
  code: 201;
  appointment_id: number;
  data: Appointment;
}

interface UpdateAppointmentStatusResponse {
  code: 200;
  message: string;
  data: Appointment;
}

// TODO: proxy routes through the API gateway once it is live
// gateway is expected to forward /appointments/* to the appointment microservice
const BASE = "/appointments";

export const AppointmentService = {
  /**
   * Fetch a single appointment by ID.
   * GET /appointments/:id
   */
  async getAppointment(id: number): Promise<Appointment> {
    const { data } = await apiClient.get<GetAppointmentResponse>(
      `${BASE}/${id}`,
    );
    return data.data;
  },

  /**
   * Create a new appointment.
   * POST /appointments
   */
  async createAppointment(
    payload: CreateAppointmentPayload,
  ): Promise<CreateAppointmentResponse> {
    const { data } = await apiClient.post<CreateAppointmentResponse>(
      BASE,
      payload,
    );
    return data;
  },

  /**
   * Update the status of an existing appointment.
   * PUT /appointments/:id/status
   */
  async updateAppointmentStatus(
    id: number,
    payload: UpdateAppointmentStatusPayload,
  ): Promise<Appointment> {
    const { data } = await apiClient.put<UpdateAppointmentStatusResponse>(
      `${BASE}/${id}/status`,
      payload,
    );
    return data.data;
  },
};
