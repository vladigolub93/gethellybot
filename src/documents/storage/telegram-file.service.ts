import { TelegramClient } from "../../telegram/telegram.client";

export class TelegramFileService {
  constructor(private readonly telegramClient: TelegramClient) {}

  async downloadFile(fileId: string): Promise<Buffer> {
    return this.telegramClient.downloadFileById(fileId);
  }
}
