import { httpClient } from '@/app/infra/http/HttpClient';
import {
  BotLog,
  GetBotLogsResponse,
} from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';

export class BotLogManager {
  private botId: string;
  private callbacks: ((_: BotLog[]) => void)[] = [];
  private intervalIds: number[] = [];

  constructor(botId: string) {
    this.botId = botId;
  }

  startListenServerPush() {
    const timerNumber = setInterval(() => {
      this.getLogList(-1, 50).then((response) => {
        this.callbacks.forEach((callback) =>
          callback(this.parseResponse(response)),
        );
      });
    }, 3000);
    this.intervalIds.push(Number(timerNumber));
  }

  stopServerPush() {
    this.intervalIds.forEach((id) => clearInterval(id));
    this.intervalIds = [];
  }

  subscribeLogPush(callback: (_: BotLog[]) => void) {
    if (!this.callbacks.includes(callback)) {
      this.callbacks.push(callback);
    }
  }

  dispose() {
    this.callbacks = [];
  }

  /**
   * 获取日志页的基本信息
   */
  private getLogList(next: number, count: number = 20) {
    return httpClient.getBotLogs(this.botId, {
      from_index: next,
      max_count: count,
    });
  }

  async loadFirstPage() {
    return this.parseResponse(await this.getLogList(-1, 10));
  }

  async loadMore(position: number, total: number) {
    return this.parseResponse(await this.getLogList(position, total));
  }

  private parseResponse(httpResponse: GetBotLogsResponse): BotLog[] {
    return httpResponse.logs;
  }
}
