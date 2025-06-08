import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { Pipeline } from '@/app/infra/entities/api';
import { Message } from '@/app/infra/entities/message';
import { toast } from 'sonner';

interface DebugDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pipelineId: string;
}

export default function DebugDialog({
  open,
  onOpenChange,
  pipelineId,
}: DebugDialogProps) {
  const { t } = useTranslation();
  const [selectedPipelineId, setSelectedPipelineId] = useState(pipelineId);
  const [sessionType, setSessionType] = useState<'person' | 'group'>('person');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (open) {
      setSelectedPipelineId(pipelineId);
      loadPipelines();
      loadMessages(pipelineId);
    }
  }, [open, pipelineId]);

  useEffect(() => {
    if (open) {
      loadMessages(selectedPipelineId);
    }
  }, [sessionType, selectedPipelineId]);

  const loadPipelines = async () => {
    try {
      const response = await httpClient.getPipelines();
      setPipelines(response.pipelines);
    } catch (error) {
      console.error('Failed to load pipelines:', error);
    }
  };

  const loadMessages = async (pipelineId: string) => {
    try {
      const response = await httpClient.getWebChatHistoryMessages(
        pipelineId,
        sessionType,
      );
      setMessages(response.messages);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim()) return;

    try {
      const userMessage: Message = {
        id: -1,
        role: 'user',
        content: inputValue.trim(),
        timestamp: new Date().toISOString(),
        message_chain: [
          {
            type: 'Plain',
            text: inputValue.trim(),
          },
        ],
      };

      setMessages((prevMessages) => [...prevMessages, userMessage]);
      setInputValue('');

      const response = await httpClient.sendWebChatMessage(
        sessionType,
        [
          {
            type: 'Plain',
            text: inputValue.trim(),
          },
        ],
        selectedPipelineId,
        120000,
      );

      setMessages((prevMessages) => [...prevMessages, response.message]);
    } catch (error) {
      toast.error(t('pipelines.debugDialog.sendFailed'));
      console.error('Failed to send message:', error);
    } finally {
      inputRef.current?.focus();
    }
  };

  const resetSession = async () => {
    try {
      await httpClient.resetWebChatSession(selectedPipelineId, sessionType);
      setMessages([]);
    } catch (error) {
      console.error('Failed to reset session:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!max-w-[70vw] max-w-6xl h-[70vh] p-6 flex flex-col rounded-2xl shadow-2xl bg-white">
        <DialogHeader className="pl-2">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-4 font-bold">
              {t('pipelines.debugDialog.title')}
              <Select
                value={selectedPipelineId}
                onValueChange={(value) => {
                  setSelectedPipelineId(value);
                  loadMessages(value);
                }}
              >
                <SelectTrigger className="bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="rounded-xl shadow-lg">
                  {pipelines.map((pipeline) => (
                    <SelectItem
                      key={pipeline.uuid}
                      value={pipeline.uuid || ''}
                      className="rounded-lg"
                    >
                      {pipeline.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </DialogTitle>
          </div>
        </DialogHeader>
        <div className="flex flex-1 h-full min-h-0 border-t">
          <div className="w-50 bg-white border-r p-6 pl-0 rounded-l-2xl flex-shrink-0 flex flex-col justify-start gap-4">
            <div className="flex flex-col gap-2">
              <Button
                variant="ghost"
                className={`w-full justify-center rounded-md px-4 py-6 text-base font-medium transition-none ${
                  sessionType === 'person'
                    ? 'bg-[#2288ee] text-white hover:bg-[#2288ee] hover:text-white'
                    : 'bg-white text-gray-800 hover:bg-gray-100'
                } border-0 shadow-none`}
                onClick={() => setSessionType('person')}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M4 22C4 17.5817 7.58172 14 12 14C16.4183 14 20 17.5817 20 22H18C18 18.6863 15.3137 16 12 16C8.68629 16 6 18.6863 6 22H4ZM12 13C8.685 13 6 10.315 6 7C6 3.685 8.685 1 12 1C15.315 1 18 3.685 18 7C18 10.315 15.315 13 12 13ZM12 11C14.21 11 16 9.21 16 7C16 4.79 14.21 3 12 3C9.79 3 8 4.79 8 7C8 9.21 9.79 11 12 11Z"></path>
                </svg>
                {t('pipelines.debugDialog.privateChat')}
              </Button>
              <Button
                variant="ghost"
                className={`w-full justify-center rounded-md px-4 py-6 text-base font-medium transition-none ${
                  sessionType === 'group'
                    ? 'bg-[#2288ee] text-white hover:bg-[#2288ee] hover:text-white'
                    : 'bg-white text-gray-800 hover:bg-gray-100'
                } border-0 shadow-none`}
                onClick={() => setSessionType('group')}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M2 22C2 17.5817 5.58172 14 10 14C14.4183 14 18 17.5817 18 22H16C16 18.6863 13.3137 16 10 16C6.68629 16 4 18.6863 4 22H2ZM10 13C6.685 13 4 10.315 4 7C4 3.685 6.685 1 10 1C13.315 1 16 3.685 16 7C16 10.315 13.315 13 10 13ZM10 11C12.21 11 14 9.21 14 7C14 4.79 12.21 3 10 3C7.79 3 6 4.79 6 7C6 9.21 7.79 11 10 11ZM18.2837 14.7028C21.0644 15.9561 23 18.752 23 22H21C21 19.564 19.5483 17.4671 17.4628 16.5271L18.2837 14.7028ZM17.5962 3.41321C19.5944 4.23703 21 6.20361 21 8.5C21 11.3702 18.8042 13.7252 16 13.9776V11.9646C17.6967 11.7222 19 10.264 19 8.5C19 7.11935 18.2016 5.92603 17.041 5.35635L17.5962 3.41321Z"></path>
                </svg>
                {t('pipelines.debugDialog.groupChat')}
              </Button>
            </div>
            <div className="flex-1" />
          </div>

          <div className="flex-1 flex flex-col w-[10rem] h-full min-h-0">
            <ScrollArea className="flex-1 p-6 overflow-y-auto min-h-0 bg-white">
              <div className="space-y-6">
                {messages.length === 0 ? (
                  <div className="text-center text-muted-foreground py-12 text-lg">
                    {t('pipelines.debugDialog.noMessages')}
                  </div>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id + message.timestamp}
                      className={cn(
                        'flex',
                        message.role === 'user'
                          ? 'justify-end'
                          : 'justify-start',
                      )}
                    >
                      <div
                        className={cn(
                          'max-w-md px-5 py-3 rounded-2xl',
                          message.role === 'user'
                            ? 'bg-[#2288ee] text-white rounded-br-none'
                            : 'bg-gray-100 text-gray-900 rounded-bl-none',
                        )}
                      >
                        <div className="text-base whitespace-pre-wrap leading-relaxed">
                          {message.content}
                        </div>
                        <div
                          className={cn(
                            'text-xs mt-2',
                            message.role === 'user'
                              ? 'text-white/70'
                              : 'text-gray-500',
                          )}
                        >
                          {message.role === 'user'
                            ? t('pipelines.debugDialog.userMessage')
                            : t('pipelines.debugDialog.botMessage')}
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            <div className="border-t p-4 pb-0 bg-white flex gap-2 ">
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={t('pipelines.debugDialog.inputPlaceholder')}
                className="flex-1 rounded-md px-3 py-2 border border-gray-300 focus:border-[#2288ee] transition-none text-base"
              />
              <Button
                onClick={sendMessage}
                disabled={!inputValue.trim()}
                className="rounded-md bg-[#2288ee] hover:bg-[#2288ee] w-20 text-white px-6 py-2 text-base font-medium transition-none flex items-center gap-2 shadow-none"
              >
                <>{t('pipelines.debugDialog.send')}</>
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
