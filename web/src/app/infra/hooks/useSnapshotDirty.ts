import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { FieldValues, UseFormReturn } from 'react-hook-form';

/** Subscribe without rendering the form for every keystroke. Values remain synchronous. */
export function useSnapshotDirty<T extends FieldValues>(
  form: UseFormReturn<T>,
  savedSnapshot: RefObject<string>,
  enabled = true,
) {
  const [isDirty, setIsDirty] = useState(false);
  const dirtyRef = useRef(false);
  const refreshDirty = useCallback(() => {
    const next =
      enabled &&
      !!savedSnapshot.current &&
      JSON.stringify(form.getValues()) !== savedSnapshot.current;
    if (next !== dirtyRef.current) {
      dirtyRef.current = next;
      setIsDirty(next);
    }
    return next;
  }, [enabled, form, savedSnapshot]);

  useEffect(() => {
    refreshDirty();
    const subscription = form.watch(refreshDirty);
    return () => subscription.unsubscribe();
  }, [form, refreshDirty]);

  return { isDirty, dirtyRef, refreshDirty };
}
