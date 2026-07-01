import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Heart,
} from 'lucide-react';
import { FeedbackRecord } from '../types/monitoring';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

interface FeedbackListProps {
  feedback: FeedbackRecord[];
  loading?: boolean;
  onViewMessage?: (messageId: string) => void;
}

export function FeedbackList({
  feedback,
  loading,
  onViewMessage,
}: FeedbackListProps) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (loading) {
    return (
      <div className="py-12 flex justify-center">
        <LoadingSpinner text={t('common.loading')} />
      </div>
    );
  }

  if (!feedback || feedback.length === 0) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-16">
        <Heart className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
        <p className="text-base font-medium mb-2">
          {t('monitoring.feedback.noFeedback')}
        </p>
        <p className="text-sm">
          {t('monitoring.feedback.noFeedbackDescription')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {feedback.map((item) => (
        <div
          key={item.id}
          className={`border rounded-xl overflow-hidden hover:shadow-md transition-all duration-200 ${
            item.feedbackType === 'like'
              ? 'border-green-200 dark:border-green-900'
              : 'border-red-200 dark:border-red-900'
          }`}
        >
          {/* Header */}
          <div
            className={`p-5 cursor-pointer transition-colors ${
              item.feedbackType === 'like'
                ? 'hover:bg-green-50 dark:hover:bg-green-950/50 bg-green-50/50 dark:bg-green-950/30'
                : 'hover:bg-red-50 dark:hover:bg-red-950/50 bg-red-50/50 dark:bg-red-950/30'
            }`}
            onClick={() => toggleExpand(item.id)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start flex-1">
                {/* Expand Icon */}
                <div className="mr-3 mt-0.5">
                  {expandedId === item.id ? (
                    <ChevronDown
                      className={`w-5 h-5 ${item.feedbackType === 'like' ? 'text-green-500' : 'text-red-500'}`}
                    />
                  ) : (
                    <ChevronRight
                      className={`w-5 h-5 ${item.feedbackType === 'like' ? 'text-green-500' : 'text-red-500'}`}
                    />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    {/* Feedback Type Icon */}
                    {item.feedbackType === 'like' ? (
                      <ThumbsUp className="w-5 h-5 text-green-500" />
                    ) : (
                      <ThumbsDown className="w-5 h-5 text-red-500" />
                    )}
                    <span
                      className={`text-sm font-medium ${item.feedbackType === 'like' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}
                    >
                      {item.feedbackType === 'like'
                        ? t('monitoring.feedback.like')
                        : t('monitoring.feedback.dislike')}
                    </span>
                    {item.botName && (
                      <>
                        <span className="text-gray-400">→</span>
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                          {item.botName}
                        </span>
                      </>
                    )}
                    {item.platform && (
                      <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
                        {item.platform}
                      </span>
                    )}
                    {item.streamId && onViewMessage && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-5 px-1.5 text-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          onViewMessage(item.streamId!);
                        }}
                      >
                        <ExternalLink className="w-3 h-3 mr-1" />
                        {t('monitoring.messageList.viewConversation')}
                      </Button>
                    )}
                  </div>

                  {item.feedbackContent && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                      {item.feedbackContent}
                    </p>
                  )}

                  {item.inaccurateReasons &&
                    item.inaccurateReasons.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {item.inaccurateReasons.map((reason, idx) => (
                          <span
                            key={idx}
                            className="text-xs px-2 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>
                    )}
                </div>
              </div>

              {/* Timestamp */}
              <div className="flex flex-col items-end gap-2 ml-4">
                <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                  {item.timestamp.toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Expanded Details */}
          {expandedId === item.id && (
            <div
              className={`border-t p-5 bg-white dark:bg-gray-900 ${
                item.feedbackType === 'like'
                  ? 'border-green-200 dark:border-green-900'
                  : 'border-red-200 dark:border-red-900'
              }`}
            >
              <div className="space-y-4 pl-8 border-l-2 border-gray-200 dark:border-gray-700 ml-4">
                {/* Context Info */}
                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                    {t('monitoring.feedback.contextInfo')}
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                    {item.botName && (
                      <div className="bg-white dark:bg-gray-900 rounded p-2">
                        <div className="text-gray-500 dark:text-gray-400">
                          {t('monitoring.messageList.bot')}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {item.botName}
                        </div>
                      </div>
                    )}
                    {item.pipelineName && (
                      <div className="bg-white dark:bg-gray-900 rounded p-2">
                        <div className="text-gray-500 dark:text-gray-400">
                          {t('monitoring.messageList.pipeline')}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {item.pipelineName}
                        </div>
                      </div>
                    )}
                    {item.sessionId && (
                      <div className="bg-white dark:bg-gray-900 rounded p-2">
                        <div className="text-gray-500 dark:text-gray-400">
                          {t('monitoring.sessions.sessionId')}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {item.sessionId}
                        </div>
                      </div>
                    )}
                    {item.userId && (
                      <div className="bg-white dark:bg-gray-900 rounded p-2">
                        <div className="text-gray-500 dark:text-gray-400">
                          {t('monitoring.feedback.userId')}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {item.userId}
                        </div>
                      </div>
                    )}
                    {item.messageId && (
                      <div className="bg-white dark:bg-gray-900 rounded p-2">
                        <div className="text-gray-500 dark:text-gray-400">
                          {t('monitoring.feedback.messageId')}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {item.messageId}
                        </div>
                      </div>
                    )}
                    {item.streamId && (
                      <div className="bg-white dark:bg-gray-900 rounded p-2">
                        <div className="text-gray-500 dark:text-gray-400">
                          {t('monitoring.feedback.streamId')}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {item.streamId}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Feedback Content */}
                {item.feedbackContent && (
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                      {t('monitoring.feedback.feedbackContent')}
                    </h4>
                    <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                      {item.feedbackContent}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
