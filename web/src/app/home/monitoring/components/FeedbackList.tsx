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
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { TabState } from './TabState';

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
    return <TabState loading rows={6} />;
  }

  if (!feedback || feedback.length === 0) {
    return (
      <TabState
        icon={<Heart className="w-16 h-16 text-muted-foreground/50" />}
        title={t('monitoring.feedback.noFeedback')}
        hint={t('monitoring.feedback.noFeedbackDescription')}
      />
    );
  }

  return (
    <div className="space-y-4">
      {feedback.map((item) => (
        <Card
          key={item.id}
          className={`gap-0 py-0 overflow-hidden hover:shadow-md transition-all duration-200 ${
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
                        <span className="text-muted-foreground">→</span>
                        <span className="text-sm text-muted-foreground">
                          {item.botName}
                        </span>
                      </>
                    )}
                    {item.platform && (
                      <Badge
                        variant="outline"
                        className="bg-muted text-muted-foreground"
                      >
                        {item.platform}
                      </Badge>
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
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {item.feedbackContent}
                    </p>
                  )}

                  {item.inaccurateReasons &&
                    item.inaccurateReasons.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {item.inaccurateReasons.map((reason, idx) => (
                          <Badge
                            key={idx}
                            variant="outline"
                            className="bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400"
                          >
                            {reason}
                          </Badge>
                        ))}
                      </div>
                    )}
                </div>
              </div>

              {/* Timestamp */}
              <div className="flex flex-col items-end gap-2 ml-4">
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {item.timestamp.toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Expanded Details */}
          {expandedId === item.id && (
            <div
              className={`border-t p-5 bg-background ${
                item.feedbackType === 'like'
                  ? 'border-green-200 dark:border-green-900'
                  : 'border-red-200 dark:border-red-900'
              }`}
            >
              <div className="space-y-4 pl-8 border-l-2 border-border ml-4">
                {/* Context Info */}
                <div className="bg-muted rounded-lg p-3">
                  <h4 className="text-sm font-semibold text-foreground mb-3">
                    {t('monitoring.feedback.contextInfo')}
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                    {item.botName && (
                      <div className="bg-background rounded p-2">
                        <div className="text-muted-foreground">
                          {t('monitoring.messageList.bot')}
                        </div>
                        <div className="font-medium text-foreground truncate">
                          {item.botName}
                        </div>
                      </div>
                    )}
                    {item.pipelineName && (
                      <div className="bg-background rounded p-2">
                        <div className="text-muted-foreground">
                          {t('monitoring.messageList.pipeline')}
                        </div>
                        <div className="font-medium text-foreground truncate">
                          {item.pipelineName}
                        </div>
                      </div>
                    )}
                    {item.sessionId && (
                      <div className="bg-background rounded p-2">
                        <div className="text-muted-foreground">
                          {t('monitoring.sessions.sessionId')}
                        </div>
                        <div className="font-medium text-foreground truncate">
                          {item.sessionId}
                        </div>
                      </div>
                    )}
                    {item.userId && (
                      <div className="bg-background rounded p-2">
                        <div className="text-muted-foreground">
                          {t('monitoring.feedback.userId')}
                        </div>
                        <div className="font-medium text-foreground truncate">
                          {item.userId}
                        </div>
                      </div>
                    )}
                    {item.messageId && (
                      <div className="bg-background rounded p-2">
                        <div className="text-muted-foreground">
                          {t('monitoring.feedback.messageId')}
                        </div>
                        <div className="font-medium text-foreground truncate">
                          {item.messageId}
                        </div>
                      </div>
                    )}
                    {item.streamId && (
                      <div className="bg-background rounded p-2">
                        <div className="text-muted-foreground">
                          {t('monitoring.feedback.streamId')}
                        </div>
                        <div className="font-medium text-foreground truncate">
                          {item.streamId}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Feedback Content */}
                {item.feedbackContent && (
                  <div className="bg-muted rounded-lg p-3">
                    <h4 className="text-sm font-semibold text-foreground mb-3">
                      {t('monitoring.feedback.feedbackContent')}
                    </h4>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                      {item.feedbackContent}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
