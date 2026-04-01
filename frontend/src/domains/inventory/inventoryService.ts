/**
 * Inventory Service - manages medicine stock
 */
import apiClient from '@/core/apiClient';

export interface Medicine {
  medicine_code: string;
  medicine_name: string;
  stock_available: number;
  unit_price: number;
}

export interface Reservation {
  reservation_id: number;
  medicine_code: string;
  appointment_id: number;
  amount: number;
}

export const inventoryService = {
  /**
   * Get all medicines in stock
   */
  getAllMedicines: async () => {
    const { data } = await apiClient.get<Medicine[]>('/inventory/medicines');
    return data;
  },

  /**
   * Get all reservations
   */
  getReservations: async () => {
    const { data } = await apiClient.get<Reservation[]>('/inventory/reservations/');
    return data;
  },

  /**
   * Get reservations by appointment ID
   */
  getReservationsByAppointment: async (appointmentId: number) => {
    const { data } = await apiClient.get<Reservation[]>(
      `/inventory/reservations/appointment/${appointmentId}`
    );
    return data;
  },

  /**
   * Reserve medicine for an appointment
   */
  reserve: async (medicineCode: string, appointmentId: number, amount: number) => {
    const { data } = await apiClient.post<{
      message: string;
      reservation: Reservation;
      medicine: Medicine;
    }>('/inventory/reservations/', {
      medicine_code: medicineCode,
      appointment_id: appointmentId,
      amount,
    });
    return data;
  },

  /**
   * Fulfill reservations for an appointment
   */
  fulfill: async (appointmentId: number) => {
    const { data } = await apiClient.post<{
      message: string;
      appointment_id: number;
      fulfilled_count: number;
    }>(`/inventory/reservations/appointment/${appointmentId}/fulfill`);
    return data;
  },
};

export default inventoryService;
