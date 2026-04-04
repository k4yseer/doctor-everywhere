/**
 * Patient Service - manages patient data
 */
import apiClient from '@/core/apiClient';

export interface Patient {
  patient_id: string;
  patient_name: string;
  gender?: string;
  address?: string;
  contact_number?: string;
  email?: string;
  date_of_birth?: string;
}

export interface Allergy {
  allergy: string;
}

export const patientService = {
  /**
   * Get all patients
   */
  getAll: async () => {
    const { data } = await apiClient.get<{ code: number; data: Patient[] }>('/patients');
    return data;
  },

  /**
   * Get patient details by ID
   */
  getById: async (patientId: string) => {
    const { data } = await apiClient.get<{ code: number; data: Patient }>(`/patient/${patientId}/details`);
    return data;
  },

  /**
   * Get patient allergies
   */
  getAllergies: async (patientId: string) => {
    const { data } = await apiClient.get<{ code: number; data: Allergy[] }>(`/patients/${patientId}/allergies`);
    return data;
  },

  /**
   * Check allergies against prescription
   */
  checkAllergies: async (patientId: string, prescription: string[]) => {
    const { data } = await apiClient.post<{ code: number; data: { check: 'PASSED' | 'FAILED'; allergic_drugs?: string[] } }>('/patient/check-allergies', {
      patient_id: patientId,
      prescription,
    });
    return data;
  },
};

export default patientService;
