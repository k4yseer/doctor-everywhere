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

export interface MakePaymentPayload {
  appointment_id: number;
  patient_id: number;
  amount: number;
  currency: string;
  paymentMethodId: string;
  patient_address: string;
  medicine_code: string;
  reserve_amount: number;
  phone_number: string;
}

export interface MakePaymentResponse {
  code: number;
  message: string;
  data?: any;
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
   * GET /consultation-history/{patient_id}
   * Fetches merged consultation data: appointment + prescription + invoice + delivery
   */
  async getConsultation(patient_id: number): Promise<ConsultationData> {
    if (USE_MOCK) {
      await mockDelay();
      return buildMockData();
    }

    const { data } = await apiClient.get(`/consultation-history/${patient_id}`);
    
    // Take the most recent consultation (last in array)
    const raw = data[data.length - 1];

    return {
      appointment: {
        id: raw.appointment_id,
        consult_id: String(raw.appointment_id),
        patient_id: patient_id,
        doctor: {
          id: 0,
          name: "Unknown",
          specialty: "Unknown",
        },
        datetime: raw.date,
        notes: "",
        status: raw.status,
      },
      prescription: {
        id: 0,
        items: raw.prescriptions ?? [],
      },
      invoice: {
        id: raw.appointment_id,
        consultation_fee: raw.billing?.amount ?? 0,
        medicine_fee: 0,
        total: raw.billing?.amount ?? 0,
        status: raw.billing?.payment_status === "Paid" ? "PAID" : "PENDING_PAYMENT",
        currency: "SGD",
      },
      delivery: raw.billing?.delivery_status
        ? {
            id: 0,
            tracking_number: "",
            address: "",
            status: raw.billing.delivery_status === "Delivered"
              ? "DELIVERED"
              : raw.billing.delivery_status === "Dispatched"
              ? "DISPATCHED"
              : "PENDING",
            estimated_date: "",
          }
        : null,
    };
  },

  async scheduleDelivery(appointment_id: number, patient_address: string): Promise<Delivery> {
    if (USE_MOCK) {
      await mockDelay(900);
      return {
        id: 123,
        tracking_number: "TRK123456",
        address: patient_address,
        status: "PENDING",
        estimated_date: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
      };
    }

    const { data } = await apiClient.post(`/deliveries/order`, {
      appointment_id,
      patient_address,
    });

    return data.data;
  },

  /**
   * POST /make-payment
   * Processes payment via Stripe through the Make Payment microservice
   */
  async makePayment(payload: MakePaymentPayload): Promise<MakePaymentResponse> {
    if (USE_MOCK) {
      await mockDelay(1400);
      return { code: 200, message: "Payment processed successfully", data: { status: "PAID" } };
    }

    const { data } = await apiClient.post(`/make-payment`, payload);
    return data;
  },
};
