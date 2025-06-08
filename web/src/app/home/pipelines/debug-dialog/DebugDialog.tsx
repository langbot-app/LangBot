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
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
      loadMessages();
    }
  }, [open, pipelineId]);

  useEffect(() => {
    if (open) {
      loadMessages();
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

  const loadMessages = async () => {
    try {
      const response = await httpClient.getWebChatHistoryMessages(
        selectedPipelineId,
        sessionType,
      );
      setMessages(response.messages);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    setLoading(true);
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

      setMessages([...messages, userMessage]);

      console.log(messages);

      setInputValue('');

      const response = await httpClient.sendWebChatMessage(
        sessionType,
        inputValue.trim(),
        selectedPipelineId,
        120000,
      );
      console.log(messages);
      setMessages([...messages, userMessage, response.message]);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
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
      <DialogContent className="!max-w-[60vw] max-w-6xl h-[60vh] p-0 flex flex-col rounded-2xl shadow-2xl bg-white">
        <DialogHeader className="px-8 pt-8 pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-4 text-2xl font-bold">
              {t('pipelines.debugDialog.title')}
              <Select
                value={selectedPipelineId}
                onValueChange={(value) => {
                  setSelectedPipelineId(value);
                  loadMessages();
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

        <div className="flex flex-1 h-full min-h-0">
          <div className="w-56 bg-white border-r p-6 rounded-l-2xl shadow-md flex-shrink-0 flex flex-col justify-start gap-4">
            <div className="flex flex-col gap-2">
              <Button
                variant="ghost"
                className={`w-full justify-center rounded-md px-4 py-2 text-base text-sm font-medium transition-none ${
                  sessionType === 'person'
                    ? 'bg-blue-600 text-white hover:bg-blue-600 hover:text-white'
                    : 'bg-white text-gray-800 hover:bg-gray-100'
                } border-0 shadow-none`}
                onClick={() => setSessionType('person')}
              >
                {t('pipelines.debugDialog.privateChat')}
              </Button>
              <Button
                variant="ghost"
                className={`w-full justify-center rounded-md px-4 py-2 text-base text-sm font-medium transition-none ${
                  sessionType === 'group'
                    ? 'bg-blue-600 text-white hover:bg-blue-600 hover:text-white'
                    : 'bg-white text-gray-800 hover:bg-gray-100'
                } border-0 shadow-none`}
                onClick={() => setSessionType('group')}
              >
                {t('pipelines.debugDialog.groupChat')}
              </Button>
            </div>
            <div className="flex-1" />
          </div>

          <div className="flex-1 flex flex-col w-[10rem] h-full min-h-0">
            <ScrollArea className="flex-1 p-6 overflow-y-auto min-h-0 bg-white rounded-r-2xl">
              <div className="space-y-6">
                {messages.length === 0 ? (
                  <div className="text-center text-muted-foreground py-12 text-lg">
                    {t('pipelines.debugDialog.noMessages')}
                  </div>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id}
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
                            ? 'bg-blue-600 text-white rounded-br-none'
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

            <div className="border-t p-6 bg-white flex gap-2 rounded-b-2xl">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={t('pipelines.debugDialog.inputPlaceholder')}
                disabled={loading}
                className="flex-1 rounded-md px-3 py-2 border border-gray-300 focus:border-blue-600 transition-none text-base"
              />
              <Button
                onClick={sendMessage}
                disabled={!inputValue.trim() || loading}
                className="rounded-md bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 text-base font-medium transition-none flex items-center gap-2 shadow-none"
              >
                {loading ? (
                  <span>...</span>
                ) : (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="w-5 h-5 mr-1"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3 12l18-6m0 0l-6 18m6-18L9.75 15.75"
                    />
                  </svg>
                )}
                {t('pipelines.debugDialog.send')}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
