import apiClient from "../../core/apiClient";

export interface ConsultDoctor {
  id: number;
  name: string;
  specialty: string;
}

export interface ConsultAppointment {
  id: number;
  consult_id: string;
  patient_id: number;
  doctor: ConsultDoctor;
  datetime: string;
  notes: string;
  status: string;
}

export interface PrescriptionItem {
  id: number;
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  quantity: number;
  unit: string;
  instructions: string;
}

export interface Prescription {
  id: number;
  items: PrescriptionItem[];
}

export interface Invoice {
  id: number;
  consultation_fee: number;
  medicine_fee: number;
  total: number;
  status: "PENDING_PAYMENT" | "PAID";
  currency: string;
}

export interface Delivery {
  id: number;
  tracking_number: string;
  address: string;
  status: "PENDING" | "DISPATCHED" | "DELIVERED";
  estimated_date: string;
}

export interface ConsultationData {
  appointment: ConsultAppointment;
  prescription: Prescription;
  invoice: Invoice;
  delivery: Delivery | null;
}

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

function mockDelay(ms = 900) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildMockData(): ConsultationData {
  return {
    appointment: {
      id: 42,
      consult_id: "CONSULT-2026-001",
      patient_id: 1,
      doctor: {
        id: 7,
        name: "Dr. Sarah Chen",
        specialty: "General Practitioner",
      },
      datetime: new Date().toISOString(),
      notes:
        "Patient presents with mild fever (37.8 °C), sore throat, and nasal congestion. Likely viral upper respiratory tract infection. Advised rest, adequate hydration, and prescribed symptomatic relief medication. Follow up in 7 days if symptoms persist.",
      status: "CONFIRMED",
    },
    prescription: {
      id: 15,
      items: [
        {
          id: 1,
          name: "Paracetamol",
          dosage: "500 mg",
          frequency: "Every 6 hours as needed",
          duration: "5 days",
          quantity: 20,
          unit: "tablets",
          instructions: "Take with food. Do not exceed 4 g per day.",
        },
        {
          id: 2,
          name: "Amoxicillin",
          dosage: "250 mg",
          frequency: "3 times daily",
          duration: "7 days",
          quantity: 21,
          unit: "capsules",
          instructions:
            "Take with or without food. Complete the full course even if you feel better.",
        },
        {
          id: 3,
          name: "Loratadine",
          dosage: "10 mg",
          frequency: "Once daily",
          duration: "7 days",
          quantity: 7,
          unit: "tablets",
          instructions: "Take in the morning. May cause mild drowsiness.",
        },
      ],
    },
    invoice: {
      id: 88,
      consultation_fee: 50.0,
      medicine_fee: 28.5,
      total: 78.5,
      status: "PENDING_PAYMENT",
      currency: "SGD",
    },
    delivery: null,
  };
}

export const PostConsultService = {
  /**
   * GET /api/consults/{patient_id}
   * Fetches merged consultation data: appointment + prescription + invoice + delivery
   */
  async getConsultation(patient_id: number): Promise<ConsultationData> {
    if (USE_MOCK) {
      await mockDelay();
      return buildMockData();
    }

    const { data } = await apiClient.get(`/api/consults/${patient_id}`);
    return data.data;
  },

  /**
   * POST /api/consults/{consult_id}/delivery
   * Creates a medicine delivery order
   */
  async scheduleDelivery(consult_id: string, address: string): Promise<Delivery> {
    if (USE_MOCK) {
      await mockDelay(1000);
      const eta = new Date();
      eta.setDate(eta.getDate() + 2);
      return {
        id: 99,
        tracking_number: "DE-TRK-" + Math.floor(100000 + Math.random() * 900000),
        address,
        status: "PENDING",
        estimated_date: eta.toLocaleDateString("en-SG", {
          weekday: "short",
          day: "numeric",
          month: "short",
          year: "numeric",
        }),
      };
    }

    const { data } = await apiClient.post(`/api/consults/${consult_id}/delivery`, {
      address,
    });
    return data.data;
  },

  /**
   * POST /api/consults/{id}/pay
   * Processes payment via Stripe through the Make Payment microservice
   */
  async makePayment(consult_id: number): Promise<{ status: string }> {
    if (USE_MOCK) {
      await mockDelay(1400);
      return { status: "PAID" };
    }

    const { data } = await apiClient.post(`/api/consults/${consult_id}/pay`);
    return data;
  },
};
