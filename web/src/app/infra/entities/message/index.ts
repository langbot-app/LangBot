export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  message_chain: object[];
  timestamp: string;
}
