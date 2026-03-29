import apiClient from "../../core/apiClient";

export interface QueueEntry {
  queue_id: number;
  queue_position: number;
  waiting_time: number;
}

export const QueueService = {
  async joinQueue(patient_id: string): Promise<QueueEntry> {
    const { data } = await apiClient.post<QueueEntry>("/join-queue", { patient_id });
    return { queue_id: data.queue_id, queue_position: data.queue_position, waiting_time: data.waiting_time };
  },

  async getQueueStatus(patient_id: string): Promise<QueueEntry> {
    const { data } = await apiClient.get<QueueEntry>(`/join-queue/status/${patient_id}`);
    return { queue_id: data.queue_id, queue_position: data.queue_position, waiting_time: data.waiting_time };
  },
};
