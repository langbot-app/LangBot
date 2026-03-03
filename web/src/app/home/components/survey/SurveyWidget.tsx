'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  SurveyQuestion,
  SurveyOption,
} from '@/app/infra/http/BackendClient';
import { X, ChevronRight, ChevronLeft, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';

/**
 * Get i18n text from a Record<string, string> based on browser locale.
 */
function getI18nText(obj?: Record<string, string> | null): string {
  if (!obj) return '';
  const lang = typeof navigator !== 'undefined' ? navigator.language : 'en';
  if (lang.startsWith('zh'))
    return obj['zh_Hans'] || obj['en_US'] || Object.values(obj)[0] || '';
  if (lang.startsWith('ja'))
    return obj['ja_JP'] || obj['en_US'] || Object.values(obj)[0] || '';
  return obj['en_US'] || Object.values(obj)[0] || '';
}

interface SurveyData {
  survey_id: string;
  version: number;
  title: Record<string, string>;
  description: Record<string, string>;
  questions: SurveyQuestion[];
}

export default function SurveyWidget() {
  const [survey, setSurvey] = useState<SurveyData | null>(null);
  const [visible, setVisible] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [otherInputs, setOtherInputs] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Poll for pending survey
  useEffect(() => {
    let timer: NodeJS.Timeout;
    let cancelled = false;

    const checkSurvey = async () => {
      try {
        const resp = await httpClient.getSurveyPending();
        if (!cancelled && resp?.survey) {
          setSurvey(resp.survey);
          setVisible(true);
        }
      } catch {
        // Silently ignore
      }
    };

    // Check after 5 seconds, then every 60 seconds
    timer = setTimeout(() => {
      checkSurvey();
      timer = setInterval(checkSurvey, 60000) as unknown as NodeJS.Timeout;
    }, 5000);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      clearInterval(timer);
    };
  }, []);

  const handleDismiss = useCallback(async () => {
    if (survey) {
      try {
        await httpClient.dismissSurvey(survey.survey_id);
      } catch {
        /* ignore */
      }
    }
    setVisible(false);
  }, [survey]);

  const handleSubmit = useCallback(async () => {
    if (!survey) return;

    // Merge "other" text inputs into answers
    const finalAnswers = { ...answers };
    for (const [qId, text] of Object.entries(otherInputs)) {
      if (text.trim()) {
        const current = finalAnswers[qId];
        if (Array.isArray(current)) {
          // Replace 'other' with the text
          finalAnswers[qId] = (current as string[]).map((v) =>
            v === 'other' ? `other:${text}` : v,
          );
        } else if (current === 'other') {
          finalAnswers[qId] = `other:${text}`;
        }
      }
    }

    try {
      await httpClient.submitSurveyResponse(
        survey.survey_id,
        finalAnswers,
        true,
      );
      setSubmitted(true);
      setTimeout(() => setVisible(false), 2000);
    } catch {
      /* ignore */
    }
  }, [survey, answers, otherInputs]);

  const setAnswer = useCallback((qId: string, value: unknown) => {
    setAnswers((prev) => ({ ...prev, [qId]: value }));
  }, []);

  if (!visible || !survey) return null;

  const questions = survey.questions || [];
  const totalSteps = questions.length;
  const currentQuestion = questions[currentStep];

  if (submitted) {
    return (
      <div className="fixed bottom-6 right-6 z-50 w-80 bg-card border rounded-xl shadow-lg p-6 animate-in slide-in-from-bottom-4">
        <div className="text-center">
          <div className="text-3xl mb-2">🎉</div>
          <p className="text-sm font-medium">
            {getI18nText({
              zh_Hans: '感谢你的反馈！',
              en_US: 'Thanks for your feedback!',
            })}
          </p>
        </div>
      </div>
    );
  }

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="fixed bottom-6 right-6 z-50 w-12 h-12 bg-primary text-primary-foreground rounded-full shadow-lg flex items-center justify-center hover:scale-105 transition-transform"
      >
        <MessageSquare className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[340px] bg-card border rounded-xl shadow-lg animate-in slide-in-from-bottom-4">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">
            {getI18nText(survey.title)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCollapsed(true)}
            className="p-1 hover:bg-accent rounded"
          >
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </button>
          <button
            onClick={handleDismiss}
            className="p-1 hover:bg-accent rounded"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Progress */}
      <div className="px-4 pt-3">
        <div className="flex gap-1">
          {questions.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= currentStep ? 'bg-primary' : 'bg-secondary'
              }`}
            />
          ))}
        </div>
        <span className="text-xs text-muted-foreground mt-1 block">
          {currentStep + 1} / {totalSteps}
        </span>
      </div>

      {/* Question */}
      <div className="px-4 py-3">
        <p className="text-sm font-medium mb-1">
          {getI18nText(currentQuestion?.title)}
        </p>
        {currentQuestion?.subtitle && (
          <p className="text-xs text-muted-foreground mb-3">
            {getI18nText(currentQuestion.subtitle)}
          </p>
        )}

        <div className="space-y-2 max-h-[260px] overflow-y-auto">
          {currentQuestion?.type === 'single_select' &&
            currentQuestion.options && (
              <SingleSelectField
                options={currentQuestion.options}
                value={answers[currentQuestion.id] as string}
                onChange={(v) => setAnswer(currentQuestion.id, v)}
                otherText={otherInputs[currentQuestion.id] || ''}
                onOtherChange={(t) =>
                  setOtherInputs((prev) => ({
                    ...prev,
                    [currentQuestion.id]: t,
                  }))
                }
              />
            )}

          {currentQuestion?.type === 'multi_select' &&
            currentQuestion.options && (
              <MultiSelectField
                options={currentQuestion.options}
                value={(answers[currentQuestion.id] as string[]) || []}
                onChange={(v) => setAnswer(currentQuestion.id, v)}
                otherText={otherInputs[currentQuestion.id] || ''}
                onOtherChange={(t) =>
                  setOtherInputs((prev) => ({
                    ...prev,
                    [currentQuestion.id]: t,
                  }))
                }
              />
            )}

          {currentQuestion?.type === 'text' && (
            <textarea
              className="w-full h-20 text-sm border rounded-lg p-2 bg-background resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder={getI18nText(currentQuestion.placeholder)}
              maxLength={currentQuestion.max_length || 500}
              value={(answers[currentQuestion.id] as string) || ''}
              onChange={(e) => setAnswer(currentQuestion.id, e.target.value)}
            />
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-3 border-t">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
          disabled={currentStep === 0}
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>

        <div className="flex gap-2">
          {!currentQuestion?.required && currentStep < totalSteps - 1 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentStep(currentStep + 1)}
            >
              {getI18nText({ zh_Hans: '跳过', en_US: 'Skip' })}
            </Button>
          )}

          {currentStep < totalSteps - 1 ? (
            <Button
              size="sm"
              onClick={() => setCurrentStep(currentStep + 1)}
              disabled={
                currentQuestion?.required && !answers[currentQuestion?.id]
              }
            >
              {getI18nText({ zh_Hans: '下一题', en_US: 'Next' })}
            </Button>
          ) : (
            <Button size="sm" onClick={handleSubmit}>
              {getI18nText({ zh_Hans: '提交', en_US: 'Submit' })}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- Sub-components for flat radio/checkbox style ----

function SingleSelectField({
  options,
  value,
  onChange,
  otherText,
  onOtherChange,
}: {
  options: SurveyOption[];
  value?: string;
  onChange: (v: string) => void;
  otherText: string;
  onOtherChange: (t: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      {options.map((opt) => (
        <div key={opt.id}>
          <button
            onClick={() => onChange(opt.id)}
            className={`w-full text-left text-sm px-3 py-2 rounded-lg border transition-colors ${
              value === opt.id
                ? 'border-primary bg-primary/5 text-primary'
                : 'border-border hover:bg-accent'
            }`}
          >
            {getI18nText(opt.label)}
          </button>
          {opt.has_input && value === opt.id && (
            <input
              type="text"
              className="mt-1 w-full text-sm border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="..."
              value={otherText}
              onChange={(e) => onOtherChange(e.target.value)}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function MultiSelectField({
  options,
  value,
  onChange,
  otherText,
  onOtherChange,
}: {
  options: SurveyOption[];
  value: string[];
  onChange: (v: string[]) => void;
  otherText: string;
  onOtherChange: (t: string) => void;
}) {
  const toggle = (id: string) => {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      onChange([...value, id]);
    }
  };

  return (
    <div className="space-y-1.5">
      {options.map((opt) => {
        const selected = value.includes(opt.id);
        return (
          <div key={opt.id}>
            <button
              onClick={() => toggle(opt.id)}
              className={`w-full text-left text-sm px-3 py-2 rounded-lg border transition-colors flex items-center gap-2 ${
                selected
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-border hover:bg-accent'
              }`}
            >
              <Checkbox checked={selected} className="pointer-events-none" />
              {getI18nText(opt.label)}
            </button>
            {opt.has_input && selected && (
              <input
                type="text"
                className="mt-1 w-full text-sm border rounded-lg px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="..."
                value={otherText}
                onChange={(e) => onOtherChange(e.target.value)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
