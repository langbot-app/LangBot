import {
  AppWindow,
  AudioWaveform,
  Bot,
  Book,
  FileText,
  Hash,
  Wrench,
  type LucideIcon,
} from 'lucide-react';

export const pluginComponentIconMap: Record<string, LucideIcon> = {
  Tool: Wrench,
  EventListener: AudioWaveform,
  Command: Hash,
  KnowledgeEngine: Book,
  Parser: FileText,
  Page: AppWindow,
  AgentRunner: Bot,
};
