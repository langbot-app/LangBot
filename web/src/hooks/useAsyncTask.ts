import { useState, useEffect, useRef } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { AsyncTask } from '@/app/infra/entities/api';

export enum AsyncTaskStatus {
  WAIT_INPUT = 'WAIT_INPUT',
  RUNNING = 'RUNNING',
  SUCCESS = 'SUCCESS',
  ERROR = 'ERROR',
}

export interface UseAsyncTaskOptions {
  onSuccess?: () => void;
  onError?: (error: string) => void;
  pollInterval?: number;
}

export interface UseAsyncTaskResult {
  status: AsyncTaskStatus;
  error: string | null;
  startTask: (taskId: number) => void;
  reset: () => void;
}

export function useAsyncTask(
  options: UseAsyncTaskOptions = {},
): UseAsyncTaskResult {
  const { onSuccess, onError, pollInterval = 1000 } = options;

  const [status, setStatus] = useState<AsyncTaskStatus>(
    AsyncTaskStatus.WAIT_INPUT,
  );
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const alreadySuccessRef = useRef<boolean>(false);

  const clearPollingInterval = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const reset = () => {
    clearPollingInterval();
    setStatus(AsyncTaskStatus.WAIT_INPUT);
    setError(null);
    alreadySuccessRef.current = false;
  };

  const startTask = (taskId: number) => {
    setStatus(AsyncTaskStatus.RUNNING);
    setError(null);
    alreadySuccessRef.current = false;

    const interval = setInterval(() => {
      httpClient
        .getAsyncTask(taskId)
        .then((res: AsyncTask) => {
          if (res.runtime.done) {
            clearPollingInterval();
            if (res.runtime.exception) {
              setError(res.runtime.exception);
              setStatus(AsyncTaskStatus.ERROR);
              onError?.(res.runtime.exception);
            } else {
              if (!alreadySuccessRef.current) {
                alreadySuccessRef.current = true;
                setStatus(AsyncTaskStatus.SUCCESS);
                onSuccess?.();
              }
            }
          }
        })
        .catch((error) => {
          clearPollingInterval();
          const errorMessage = error.message || 'Unknown error';
          setError(errorMessage);
          setStatus(AsyncTaskStatus.ERROR);
          onError?.(errorMessage);
        });
    }, pollInterval);

    intervalRef.current = interval;
  };

  useEffect(() => {
    return () => {
      clearPollingInterval();
    };
  }, []);

  return {
    status,
    error,
    startTask,
    reset,
  };
}
