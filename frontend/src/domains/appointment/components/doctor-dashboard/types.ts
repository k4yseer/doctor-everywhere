export interface QueuePatient {
  id: number;
  patient_id: string;
  created_at: string;
}

export interface PrescriptionItem {
  medicine_name: string;
  quantity: number;
}

export interface PatientHistory {
  appointment_id: number;
  date: string | null;
  status: string;
  clinical_notes: string | null;
  prescriptions: PrescriptionItem[];
}

export interface ActivePatient {
  id: number;
  patient_id: string;
  patient_name: string;
  age: number | null;
  gender: string | null;
  allergies: string[];
  history: PatientHistory[];
  appointment_id: number;
  join_url: string | null;
}

export interface DrugItem {
  id: number;
  medicine_code: string;
  medication_name: string;
  instruction: string;
  dispense_quantity: number;
}

export interface MedicalCertificateDraft {
  leaveDays: number;
  diagnosisSummary: string;
  startDate: string;
}

export interface Medicine {
  medicine_code: string;
  medicine_name: string;
  stock_available: number;
  unit_price: number;
}

export type ConsultationStatus = "idle" | "connecting" | "active" | "ended";