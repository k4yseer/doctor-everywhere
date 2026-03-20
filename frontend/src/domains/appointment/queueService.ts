import apiClient from "../../core/apiClient";

export type QueueStatus = "QUEUED" | "CONFIRMED";

export interface QueueDoctor {
  id: number;
  name: string;
  specialty: string;
}

export interface QueueEntry {
  queue_id: string;
  patient_id: number;
  position: number;
  status: QueueStatus;
  estimated_wait_minutes: number | null;
  appointment_id: number | null;
  meet_link: string | null;
  doctor: QueueDoctor | null;
}

interface JoinQueueResponse {
  code: 201;
  data: QueueEntry;
}

interface GetQueueStatusResponse {
  code: 200;
  data: QueueEntry;
}

const QUEUE_ID_KEY = "de_queue_id";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

// Simulates network latency for a realistic feel during development
function mockDelay(ms = 800) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const MOCK_QUEUE: QueueEntry = {
  queue_id: "mock-queue-001",
  patient_id: 1,
  position: 3,
  status: "QUEUED",
  estimated_wait_minutes: 15,
  appointment_id: null,
  meet_link: null,
  doctor: null,
};

const MOCK_CONFIRMED: QueueEntry = {
  queue_id: "mock-queue-001",
  patient_id: 1,
  position: 1,
  status: "CONFIRMED",
  estimated_wait_minutes: 0,
  appointment_id: 42,
  meet_link: "https://zoom.us/j/mock-meeting-link",
  doctor: {
    id: 7,
    name: "Dr. Sarah Chen",
    specialty: "General Practitioner",
  },
};

export const QueueService = {
  async joinQueue(patient_id: number): Promise<QueueEntry> {
    if (USE_MOCK) {
      await mockDelay();
      localStorage.setItem(QUEUE_ID_KEY, MOCK_QUEUE.queue_id);
      return { ...MOCK_QUEUE, patient_id };
    }

    const { data } = await apiClient.post<JoinQueueResponse>("/join-queue", {
      patient_id,
    });
    localStorage.setItem(QUEUE_ID_KEY, data.data.queue_id);
    return data.data;
  },

  async getQueueStatus(queue_id: string): Promise<QueueEntry> {
    if (USE_MOCK) {
      await mockDelay(600);
      // Simulate progression to CONFIRMED after the first poll
      const pollCount = Number(sessionStorage.getItem("de_mock_polls") ?? 0) + 1;
      sessionStorage.setItem("de_mock_polls", String(pollCount));
      return pollCount >= 2 ? MOCK_CONFIRMED : { ...MOCK_QUEUE, queue_id };
    }

    const { data } = await apiClient.get<GetQueueStatusResponse>(
      `/queue/${queue_id}`,
    );
    return data.data;
  },

  getSavedQueueId(): string | null {
    return localStorage.getItem(QUEUE_ID_KEY);
  },

  clearSavedQueueId(): void {
    localStorage.removeItem(QUEUE_ID_KEY);
    sessionStorage.removeItem("de_mock_polls");
  },
};
