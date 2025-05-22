import { httpClient } from '@/app/infra/http/HttpClient';
import { GetBotLogsRequest } from '@/app/infra/http/requestParam/bots/GetBotLogsRequest';
import { GetBotLogsResponse } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';

export class BotLogManager {
  private botId: string;
  private callbacks: ((_: GetBotLogsResponse) => void)[] = [];
  private intervalIds: number[] = [];

  constructor(botId: string) {
    this.botId = botId;
  }

  startListenServerPush() {
    const timerNumber = setInterval(() => {
      httpClient
        .getBotLogs(this.botId, {
          from_index: -1,
          max_count: 50,
        })
        .then((response) => {
          this.callbacks.forEach((callback) => callback(response));
        });
    }, 3000);
    this.intervalIds.push(Number(timerNumber));
  }

  stopServerPush() {
    this.intervalIds.forEach((id) => clearInterval(id));
  }

  subscribeLogPush(callback: () => void) {
    this.callbacks.push(callback);
  }

  unsubscribeLogPush(callback: () => void) {
    this.callbacks = this.callbacks.filter((cb) => cb !== callback);
  }

  dispose() {
    this.callbacks = [];
  }

  /**
   * 获取日志页的基本信息
   */
  getLogPageInfo(next: number, count: number = 50) {
    httpClient
      .getBotLogs(this.botId, {
        from_index: next,
        max_count: count,
      })
      .then((response) => {
        this.callbacks.forEach((callback) => callback(response));
      });
  }

  getLogVOList() {}

  private parseResponse(httpResponse: GetBotLogsResponse) {}
}
