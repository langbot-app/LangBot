export interface GetBotLogsRequest {
  from_index: number; // 从某索引开始往前找，-1代表结尾，也就是拉取最新的
  max_count: number; // 最大拉取数量
}
