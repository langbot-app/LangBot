import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';

interface DebugDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pipelineId: string;
}

interface Message {
  id: number;
  type: 'user' | 'bot';
  content: string;
  timestamp: string;
}

interface Pipeline {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
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
  }, [sessionType]);

  const loadPipelines = async () => {
    try {
      const response = await httpClient.getDebugPipelines();
      setPipelines(response.pipelines);
    } catch (error) {
      console.error('Failed to load pipelines:', error);
    }
  };

  const loadMessages = async () => {
    try {
      const response = await httpClient.getDebugMessages(sessionType);
      setMessages(response.messages);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    setLoading(true);
    try {
      await httpClient.sendDebugMessage(
        sessionType,
        inputValue.trim(),
        selectedPipelineId,
      );
      setInputValue('');
      setTimeout(() => {
        loadMessages();
      }, 500);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };

  const resetSession = async () => {
    try {
      await httpClient.resetDebugSession(sessionType);
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

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold">
              {t('pipelines.debugDialog.title')}
            </h2>
            <select
              value={selectedPipelineId}
              onChange={(e) => setSelectedPipelineId(e.target.value)}
              className="px-3 py-1 border rounded-md text-sm"
            >
              {pipelines.map((pipeline) => (
                <option key={pipeline.id} value={pipeline.id}>
                  {pipeline.name}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          <div className="w-48 border-r bg-gray-50 p-4">
            <h3 className="font-medium mb-3">
              {t('pipelines.debugDialog.sessionType')}
            </h3>
            <div className="space-y-2">
              <button
                onClick={() => setSessionType('person')}
                className={`w-full text-left px-3 py-2 rounded-md text-sm ${
                  sessionType === 'person'
                    ? 'bg-blue-100 text-blue-700 border border-blue-300'
                    : 'bg-white border border-gray-200 hover:bg-gray-50'
                }`}
              >
                {t('pipelines.debugDialog.privateChat')}
              </button>
              <button
                onClick={() => setSessionType('group')}
                className={`w-full text-left px-3 py-2 rounded-md text-sm ${
                  sessionType === 'group'
                    ? 'bg-blue-100 text-blue-700 border border-blue-300'
                    : 'bg-white border border-gray-200 hover:bg-gray-50'
                }`}
              >
                {t('pipelines.debugDialog.groupChat')}
              </button>
            </div>
            <button
              onClick={resetSession}
              className="w-full mt-4 px-3 py-2 bg-red-100 text-red-700 border border-red-300 rounded-md text-sm hover:bg-red-200"
            >
              {t('pipelines.debugDialog.reset')}
            </button>
          </div>

          <div className="flex-1 flex flex-col">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  {t('pipelines.debugDialog.noMessages')}
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                        message.type === 'user'
                          ? 'bg-blue-500 text-white'
                          : 'bg-gray-200 text-gray-800'
                      }`}
                    >
                      <div className="text-sm">{message.content}</div>
                      <div
                        className={`text-xs mt-1 ${
                          message.type === 'user'
                            ? 'text-blue-100'
                            : 'text-gray-500'
                        }`}
                      >
                        {message.type === 'user'
                          ? t('pipelines.debugDialog.userMessage')
                          : t('pipelines.debugDialog.botMessage')}
                      </div>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="border-t p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={t('pipelines.debugDialog.inputPlaceholder')}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={loading}
                />
                <button
                  onClick={sendMessage}
                  disabled={!inputValue.trim() || loading}
                  className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? '...' : t('pipelines.debugDialog.send')}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
