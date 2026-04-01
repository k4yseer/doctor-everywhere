/**
 * Consultation History Service
 * Uses the get-consultation-history GraphQL composite service
 * to fetch past visit history for a patient (doctor-side view).
 */
import apiClient from '@/core/apiClient';
import type { PatientHistory } from './components/doctor-dashboard/types';

const GRAPHQL_PATH = '/get-consultation-history/graphql';

/**
 * Fetch past consultations for a patient (doctor-relevant fields only).
 * Excludes billing/delivery — just appointment date, status, clinical notes, and prescriptions.
 */
export async function getPatientVisitHistory(patientId: string): Promise<PatientHistory[]> {
  const query = `
    query ($patientId: Int!) {
      consultationHistory(patientId: $patientId) {
        appointmentId
        date
        status
        clinicalNotes
      }
    }
  `;

  try {
    const { data } = await apiClient.post(GRAPHQL_PATH, {
      query,
      variables: { patientId: parseInt(patientId, 10) },
    });

    const items = data?.data?.consultationHistory ?? [];

    return items.map((item: any) => ({
      appointment_id: item.appointmentId,
      date: item.date,
      status: item.status,
      clinical_notes: item.clinicalNotes ?? null,
      prescriptions: [],
    }));
  } catch (e) {
    console.error('Failed to fetch consultation history:', e);
    return [];
  }
}
