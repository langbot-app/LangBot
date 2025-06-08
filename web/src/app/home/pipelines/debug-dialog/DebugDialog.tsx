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
      <DialogContent className="!max-w-[60vw] max-w-6xl h-[60vh] p-0 flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-4">
              {t('pipelines.debugDialog.title')}
              <Select
                value={selectedPipelineId}
                onValueChange={(value) => {
                  setSelectedPipelineId(value);
                  loadMessages();
                }}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {pipelines.map((pipeline) => (
                    <SelectItem key={pipeline.uuid} value={pipeline.uuid || ''}>
                      {pipeline.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </DialogTitle>
          </div>
        </DialogHeader>

        <div className="flex flex-1 h-full min-h-0">
          <div className="w-48 border-r bg-muted p-4 h-full flex-shrink-0">
            <h3 className="font-medium mb-3">
              {t('pipelines.debugDialog.sessionType')}
            </h3>
            <div className="space-y-2">
              <Button
                variant={sessionType === 'person' ? 'default' : 'outline'}
                className="w-full justify-start"
                onClick={() => setSessionType('person')}
              >
                {t('pipelines.debugDialog.privateChat')}
              </Button>
              <Button
                variant={sessionType === 'group' ? 'default' : 'outline'}
                className="w-full justify-start"
                onClick={() => setSessionType('group')}
              >
                {t('pipelines.debugDialog.groupChat')}
              </Button>
            </div>
            <Button
              variant="destructive"
              className="w-full mt-4"
              onClick={resetSession}
            >
              {t('pipelines.debugDialog.reset')}
            </Button>
          </div>

          <div className="flex-1 flex flex-col w-[10rem] h-full min-h-0">
            <ScrollArea className="flex-1 p-4 overflow-y-auto min-h-0">
              <div className="space-y-4">
                {messages.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
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
                          'max-w-xs lg:max-w-md px-4 py-2 rounded-lg',
                          message.role === 'user'
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted',
                        )}
                      >
                        <div className="text-sm whitespace-pre-wrap">
                          {message.content}
                        </div>
                        <div
                          className={cn(
                            'text-xs mt-1',
                            message.role === 'user'
                              ? 'text-primary-foreground/70'
                              : 'text-muted-foreground',
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

            <div className="border-t p-4">
              <div className="flex gap-2">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={t('pipelines.debugDialog.inputPlaceholder')}
                  disabled={loading}
                />
                <Button
                  onClick={sendMessage}
                  disabled={!inputValue.trim() || loading}
                >
                  {loading ? '...' : t('pipelines.debugDialog.send')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
