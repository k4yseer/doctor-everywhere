/**
 * Consultation History Service
 * Uses the get-consultation-history GraphQL composite service
 * to fetch past visit history for a patient (doctor-side view).
 */
import axios from 'axios';
import type { PatientHistory } from './components/doctor-dashboard/types';

/**
 * Fetch past consultations for a patient (doctor-relevant fields only).
 * Excludes billing/delivery — just appointment date, status, clinical notes, and prescriptions.
 */
export async function getPatientVisitHistory(patientId: string): Promise<PatientHistory[]> {
  const query = `
    query ($patientId: Int!) {
      consultationHistory(patientId: $patientId) {
        appointment {
          id
          datetime
          status
          notes
        }
      }
    }
  `;

  try {
    const { data } = await axios.post('/graphql', {
      query,
      variables: { patientId: parseInt(patientId, 10) },
    });

    const items = data?.data?.consultationHistory ?? [];

    return items.map((item: any) => ({
      appointment_id: item.appointment.id,
      date: item.appointment.datetime,
      status: item.appointment.status,
      clinical_notes: item.appointment.notes ?? null,
      prescriptions: [],
    }));
  } catch (e) {
    console.error('Failed to fetch consultation history:', e);
    return [];
  }
}
