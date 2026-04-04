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
  line_total?: number;
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

function timeValue(dateLike: unknown): number {
  const t = new Date(String(dateLike ?? '')).getTime()
  return Number.isNaN(t) ? 0 : t
}

function mockDelay(ms = 900) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildMockData(appointmentId = 42, patientId = 1): ConsultationData {
  return {
    appointment: {
      id: appointmentId,
      consult_id: `CONSULT-${String(appointmentId).padStart(3, '0')}`,
      patient_id: patientId,
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

export interface ConsultationHistoryItem {
  appointmentId: number;
  date: string;
  status: string;
  prescriptions?: Array<{ medicineName: string; quantity: number }>;
  billing?: {
    amount?: number;
    paymentStatus?: string;
    deliveryStatus?: string;
  };
}

function buildMockHistory(): ConsultationHistoryItem[] {
  return [
    {
      appointmentId: 1,
      date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      status: 'PENDING_PAYMENT',
      prescriptions: [{ medicineName: 'Paracetamol', quantity: 20 }],
      billing: {
        amount: 78.5,
        paymentStatus: 'Pending Payment',
        deliveryStatus: 'Pending',
      },
    },
    {
      appointmentId: 2,
      date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      status: 'PAID',
      prescriptions: [{ medicineName: 'Amoxicillin', quantity: 21 }],
      billing: {
        amount: 120,
        paymentStatus: 'Paid',
        deliveryStatus: 'Delivered',
      },
    },
  ];
}

export const PostConsultService = {
  async getConsultationHistory(patient_id: number): Promise<ConsultationHistoryItem[]> {
    if (USE_MOCK) {
      await mockDelay();
      return buildMockHistory();
    }

    const query = `
      query ($patientId: Int!) {
        consultationHistory(patientId: $patientId) {
          appointment {
            id
            consultId
            datetime
            status
            notes
            doctor {
              id
              name
              specialty
            }
          }
          prescription {
            items {
              id
              medicineCode
              medicineName
              quantity
              dosage
              frequency
              duration
              unit
              instructions
              lineTotal
            }
          }
          invoice {
            id
            consultationFee
            medicineFee
            total
            status
            currency
          }
          delivery {
            id
            trackingNumber
            address
            status
            estimatedDate
          }
        }
      }
    `;

    const { data } = await apiClient.post('/graphql', {
      query,
      variables: { patientId: patient_id },
    });

    const rawData = data?.data?.consultationHistory;
    if (!Array.isArray(rawData)) {
      throw new Error('No consultation history found');
    }
    console.log(rawData)

    // Map GraphQL response to frontend structure
    const historyItems: ConsultationHistoryItem[] = rawData.map((r: any) => ({
      appointmentId: r.appointment.id,
      date: r.appointment.datetime ? new Date(r.appointment.datetime + 'Z').toISOString() : '',
      status: r.appointment.status,
      doctor: r.appointment.doctor,
      prescriptions: r.prescription?.items?.map((p: any) => ({
        medicineName: p.medicineName,
        quantity: p.quantity,
      })) ?? [],
      billing: r.invoice
        ? {
            medicine_fee: r.invoice.medicineFee ?? 0,
            consultation_fee: r.invoice.consultationFee ?? 0,
            amount: r.invoice.total ?? 0,
            paymentStatus: r.invoice.status ?? 'Pending',
            deliveryStatus: r.delivery ?? 'Pending',
          }
        : {
            amount: 0,
            paymentStatus: 'Pending',
            deliveryStatus: r.delivery ?? 'Pending',
          },
    }));

    historyItems.sort((a, b) => timeValue(b.date) - timeValue(a.date))
    return historyItems;
  },

  async getConsultation(patient_id: number, appointment_id?: number): Promise<ConsultationData> {
    if (USE_MOCK) {
      await mockDelay();
      return buildMockData(appointment_id ?? 42, patient_id);
    }

    const query = `
      query ($patientId: Int!) {
        consultationHistory(patientId: $patientId) {
          appointment {
            id
            consultId
            patientId
            doctor { id name specialty }
            datetime
            notes
            status
          }
          prescription {
            id
            items { id medicineCode medicineName dosage frequency duration quantity unit instructions lineTotal }
          }
          invoice {
            id consultationFee medicineFee total status currency
          }
          delivery {
            id trackingNumber address status estimatedDate
          }
        }
      }
    `;

    const { data } = await apiClient.post('/graphql', {
      query,
      variables: { patientId: patient_id },
    });

    const records: any[] = data?.data?.consultationHistory ?? [];
    if (records.length === 0) {
      throw new Error('No consultation data found');
    }

    const sortedRecords = [...records].sort(
      (a, b) => timeValue(b?.appointment?.datetime) - timeValue(a?.appointment?.datetime),
    )

    const r = appointment_id
      ? sortedRecords.find((item: any) => item.appointment.id === appointment_id)
      : sortedRecords[0];

    if (!r) {
      throw new Error(`Appointment ${appointment_id} not found`);
    }

    return {
      appointment: {
        id: r.appointment.id,
        consult_id: r.appointment.consultId ?? `CONSULT-${String(r.appointment.id).padStart(3, '0')}`,
        patient_id,
        doctor: r.appointment.doctor ?? { id: 0, name: 'Unknown', specialty: 'Unknown' },
        datetime: r.appointment.datetime,
        notes: r.appointment.notes ?? '',
        status: r.appointment.status,
      },
      prescription: {
        id: r.prescription?.id ?? 0,
        items: (r.prescription?.items ?? []).map((p: any) => ({
          id: p.id,
          name: p.medicineName ?? '',
          dosage: p.dosage ?? p.dosageInstructions ?? p.dosage_instructions ?? '',
          frequency: p.frequency ?? '',
          duration: p.duration ?? '',
          quantity: p.quantity ?? 0,
          unit: p.unit ?? '',
          instructions: p.instructions ?? '',
          line_total: Number(p.lineTotal ?? p.line_total ?? p.totalPrice ?? p.total_price ?? 0) || undefined,
        })),
      },
      invoice: {
        id: r.invoice?.id ?? r.appointment.id,
        consultation_fee: r.invoice?.consultationFee ?? 0,
        medicine_fee: r.invoice?.medicineFee ?? 0,
        total: r.invoice?.total ?? 0,
        status: r.invoice?.status === 'PAID' || r.invoice?.status === 'Paid' ? 'PAID' : 'PENDING_PAYMENT',
        currency: r.invoice?.currency ?? 'SGD',
      },
      delivery: r.delivery
        ? {
            id: r.delivery.id ?? 0,
            tracking_number: r.delivery.trackingNumber ?? '',
            address: r.delivery.address ?? '',
            status: r.delivery.status === 'DELIVERED' ? 'DELIVERED' : r.delivery.status === 'DISPATCHED' ? 'DISPATCHED' : 'PENDING',
            estimated_date: r.delivery.estimatedDate ?? '',
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
