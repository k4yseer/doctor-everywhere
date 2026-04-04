/**
 * Prescription Service - handles prescription creation
 */
import apiClient from '@/core/apiClient';

export interface PrescriptionDrug {
  medicine_code: string;
  medicine_name: string;
  dosage_instructions: string;
  dispense_quantity: number;
}

export interface CreatePrescriptionPayload {
  appointment_id: number;
  patient_id: string;
  medicines: PrescriptionDrug[];
  mc_start_date?: string | null;
  mc_duration_days?: number | null;
  consultation_notes?: string;
}

export interface PrescriptionResponse {
  code: number;
  message: string;
  data?: {
    prescription_id: number;
    status: string;
  };
}

/**
 * Create a new prescription
 * @param payload - Prescription data including drugs and optional MC
 */
async function create(payload: CreatePrescriptionPayload): Promise<PrescriptionResponse> {
  const { data } = await apiClient.post<PrescriptionResponse>('/make-prescription', payload);
  return data;
}

export const prescriptionService = {
  create,
};
