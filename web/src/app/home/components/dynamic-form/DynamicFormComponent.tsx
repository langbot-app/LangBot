import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import DynamicFormItemComponent from '@/app/home/components/dynamic-form/DynamicFormItemComponent';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import i18n from 'i18next';
import { resolveI18nLabel, maybeTranslateKey } from '@/app/home/workflows/components/workflow-editor/workflow-i18n';

// Helper function to translate i18n key if the value is an i18n key string
const translateIfKey = (value: string | undefined): string | undefined => {
  if (!value) return value;
  const translated = maybeTranslateKey(value);
  return translated || value;
};

// Helper to extract i18n label and translate if it's an i18n key
const extractAndTranslateI18n = (label: any): string => {
  if (!label) return '';
  if (typeof label === 'string') {
    return translateIfKey(label) || label;
  }
  return resolveI18nLabel(label) || '';
};
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Copy, Check, Globe } from 'lucide-react';
import { systemInfo } from '@/app/infra/http';

/**
 * Resolve the value referenced by a `show_if.field` string.
 *
 * Fields prefixed with `__system.` are looked up in the caller-supplied
 * `systemContext` dictionary (e.g. `__system.is_wizard` → `systemContext.is_wizard`).
 * All other field names are resolved from the live form values first, then
 * fall back to `externalDependentValues`.
 */
function resolveShowIfValue(
  field: string,
  watchedValues: Record<string, unknown>,
  externalDependentValues?: Record<string, unknown>,
  systemContext?: Record<string, unknown>,
): unknown {
  if (!field || typeof field !== 'string') {
    return undefined;
  }
  if (field.startsWith('__system.')) {
    const key = field.slice('__system.'.length);
    return systemContext?.[key];
  }
  if (watchedValues[field] !== undefined) {
    return watchedValues[field];
  }
  return externalDependentValues?.[field];
}

/**
 * Display-only component for webhook URL fields.
 * Rendered outside of react-hook-form binding since the value is
 * read-only and comes from systemContext, not user input.
 */
function WebhookUrlField({
  label,
  description,
  url,
  extraUrl,
}: {
  label: string;
  description?: string;
  url: string;
  extraUrl?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [extraCopied, setExtraCopied] = useState(false);
  const { t } = useTranslation();

  const handleCopy = (text: string, setter: (v: boolean) => void) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          setter(true);
          setTimeout(() => setter(false), 2000);
        })
        .catch(() => {});
    }
  };

  return (
    <FormItem>
      <FormLabel>{label}</FormLabel>
      <div className="flex items-center gap-2">
        <Input
          value={url}
          readOnly
          className="flex-1 bg-muted"
          onClick={(e) => (e.target as HTMLInputElement).select()}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handleCopy(url, setCopied)}
        >
          {copied ? (
            <Check className="h-4 w-4 text-green-600" />
          ) : (
            <Copy className="h-4 w-4" />
          )}
        </Button>
      </div>
      {extraUrl && (
        <div className="flex items-center gap-2 mt-2">
          <Input
            value={extraUrl}
            readOnly
            className="flex-1 bg-muted"
            onClick={(e) => (e.target as HTMLInputElement).select()}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => handleCopy(extraUrl, setExtraCopied)}
          >
            {extraCopied ? (
              <Check className="h-4 w-4 text-green-600" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
        </div>
      )}
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
      {systemInfo.edition === 'community' && (
        <div className="flex items-start gap-2.5 rounded-md border border-border/60 bg-muted/40 px-3 py-2.5 mt-1 max-w-2xl">
          <Globe className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <p className="text-sm text-muted-foreground leading-relaxed">
            {t('bots.webhookSaasHint')}{' '}
            <a
              href="https://space.langbot.app/cloud?utm_source=local_webui&utm_medium=webhook_alert&utm_campaign=saas_conversion"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline-offset-4 hover:underline font-medium"
            >
              {t('bots.webhookSaasLink')}
            </a>
          </p>
        </div>
      )}
    </FormItem>
  );
}

export default function DynamicFormComponent({
  itemConfigList,
  onSubmit,
  initialValues,
  onFileUploaded,
  isEditing,
  externalDependentValues,
  systemContext,
}: {
  itemConfigList: IDynamicFormItemSchema[];
  onSubmit?: (val: object) => unknown;
  initialValues?: Record<string, object>;
  onFileUploaded?: (fileKey: string) => void;
  isEditing?: boolean;
  externalDependentValues?: Record<string, unknown>;
  /** Extra variables accessible via the `__system.*` namespace in show_if conditions.
   *  e.g. `{ is_wizard: true }` makes `show_if: { field: "__system.is_wizard", ... }` work. */
  systemContext?: Record<string, unknown>;
}) {
  const isInitialMount = useRef(true);
  const previousInitialValues = useRef(initialValues);
  const { t } = useTranslation();

  // Normalize a form value according to its field type.
  // This ensures legacy/malformed data (e.g. a plain string for
  // model-fallback-selector) is coerced to the expected shape
  // so that downstream components never crash.
  const normalizeFieldValue = (
    item: IDynamicFormItemSchema,
    value: unknown,
  ): unknown => {
    if (item.type === 'model-fallback-selector') {
      if (value != null && typeof value === 'object' && !Array.isArray(value)) {
        const obj = value as Record<string, unknown>;
        return {
          primary: typeof obj.primary === 'string' ? obj.primary : '',
          fallbacks: Array.isArray(obj.fallbacks)
            ? (obj.fallbacks as unknown[]).filter(
                (v): v is string => typeof v === 'string',
              )
            : [],
        };
      }
      // Legacy string format or any other unexpected type
      return {
        primary: typeof value === 'string' ? value : '',
        fallbacks: [],
      };
    }
    if (item.type === 'prompt-editor') {
      if (Array.isArray(value)) {
        return value;
      }
      // Default to a single empty system prompt entry
      return [{ role: 'system', content: '' }];
    }
    if (
      item.type === 'string' ||
      item.type === 'text' ||
      item.type === 'secret' ||
      item.type === 'select' ||
      item.type === 'llm-model-selector' ||
      item.type === 'embedding-model-selector' ||
      item.type === 'rerank-model-selector' ||
      item.type === 'knowledge-base-selector' ||
      item.type === 'bot-selector'
    ) {
      return typeof value === 'string' ? value : '';
    }
    if (
      item.type === 'array[string]' ||
      item.type === 'knowledge-base-multi-selector' ||
      item.type === 'tools-selector'
    ) {
      return Array.isArray(value)
        ? value.filter((item): item is string => typeof item === 'string')
        : [];
    }
    if (item.type === 'boolean') {
      return typeof value === 'boolean' ? value : Boolean(value);
    }
    if (item.type === 'integer' || item.type === 'float') {
      return typeof value === 'number' && !Number.isNaN(value)
        ? value
        : typeof item.default === 'number'
          ? item.default
          : 0;
    }
    return value;
  };

  // Filter out display-only field types (e.g. webhook-url) that should not
  // participate in form state, validation, or value emission.
  const editableItems = useMemo(
    () => itemConfigList.filter((item) => item.type !== 'webhook-url'),
    [itemConfigList],
  );

  // 根据 itemConfigList 动态生成 zod schema
  const formSchema = z.object(
    editableItems.reduce(
      (acc, item) => {
        let fieldSchema;
        switch (item.type) {
          case 'integer':
            fieldSchema = z.number();
            break;
          case 'float':
            fieldSchema = z.number();
            break;
          case 'boolean':
            fieldSchema = z.boolean();
            break;
          case 'string':
            fieldSchema = z.string();
            break;
          case 'array[string]':
            fieldSchema = z.array(z.string());
            break;
          case 'select':
            fieldSchema = z.string();
            break;
          case 'llm-model-selector':
            fieldSchema = z.string();
            break;
          case 'embedding-model-selector':
            fieldSchema = z.string();
            break;
          case 'rerank-model-selector':
            fieldSchema = z.string();
            break;
          case 'knowledge-base-selector':
            fieldSchema = z.string();
            break;
          case 'knowledge-base-multi-selector':
            fieldSchema = z.array(z.string());
            break;
          case 'bot-selector':
            fieldSchema = z.string();
            break;
          case 'tools-selector':
            fieldSchema = z.array(z.string());
            break;
          case 'model-fallback-selector':
            fieldSchema = z.object({
              primary: z.string(),
              fallbacks: z.array(z.string()),
            });
            break;
          case 'prompt-editor':
            fieldSchema = z.array(
              z.object({
                content: z.string(),
                role: z.string(),
              }),
            );
            break;
          default:
            fieldSchema = z.string();
        }

        if (
          item.required &&
          (fieldSchema instanceof z.ZodString ||
            fieldSchema instanceof z.ZodArray)
        ) {
          fieldSchema = fieldSchema.min(1, {
            message: t('common.fieldRequired'),
          });
        }

        return {
          ...acc,
          [item.name]: fieldSchema,
        };
      },
      {} as Record<string, z.ZodTypeAny>,
    ),
  );

  type FormValues = z.infer<typeof formSchema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: editableItems.reduce((acc, item) => {
      // 优先使用 initialValues，如果没有则使用默认值
      const rawValue = initialValues?.[item.name] ?? item.default;
      return {
        ...acc,
        [item.name]: normalizeFieldValue(item, rawValue),
      };
    }, {} as FormValues),
  });

  // 当 initialValues 变化时更新表单值
  // 但要避免因为内部表单更新触发的 onSubmit 导致的 initialValues 变化而重新设置表单
  useEffect(() => {
    // 首次挂载时，使用 initialValues 初始化表单
    if (isInitialMount.current) {
      isInitialMount.current = false;
      previousInitialValues.current = initialValues;
      return;
    }

    // 检查 initialValues 是否真的发生了实质性变化
    // 使用 JSON.stringify 进行深度比较
    const hasRealChange =
      JSON.stringify(previousInitialValues.current) !==
      JSON.stringify(initialValues);

    if (initialValues && hasRealChange) {
      // 合并默认值和初始值
      const mergedValues = editableItems.reduce(
        (acc, item) => {
          const rawValue = initialValues[item.name] ?? item.default;
          acc[item.name] = normalizeFieldValue(item, rawValue) as object;
          return acc;
        },
        {} as Record<string, object>,
      );

      Object.entries(mergedValues).forEach(([key, value]) => {
        form.setValue(key as keyof FormValues, value);
      });

      previousInitialValues.current = initialValues;
    }
  }, [initialValues, form, editableItems]);

  // Get reactive form values for conditional rendering
  const watchedValues = form.watch();

  // Stable ref for onSubmit to avoid re-triggering the effect when the
  // parent passes a new closure on every render.
  const onSubmitRef = useRef(onSubmit);
  onSubmitRef.current = onSubmit;

  // 监听表单值变化
  useEffect(() => {
    // Emit initial form values immediately so the parent always has a valid snapshot,
    // even if the user saves without modifying any field.
    // form.watch(callback) only fires on subsequent changes, not on mount.
    const formValues = form.getValues();
    const initialFinalValues = editableItems.reduce(
      (acc, item) => {
        acc[item.name] = formValues[item.name] ?? item.default;
        return acc;
      },
      {} as Record<string, object>,
    );
    onSubmitRef.current?.(initialFinalValues);

    // Update previousInitialValues to the emitted snapshot so that if the
    // parent writes these values back as new initialValues, the deep
    // comparison in the initialValues-sync useEffect won't detect a change
    // and won't trigger an infinite update loop.
    previousInitialValues.current = initialFinalValues as Record<
      string,
      object
    >;

    const subscription = form.watch(() => {
      const formValues = form.getValues();
      const finalValues = editableItems.reduce(
        (acc, item) => {
          acc[item.name] = formValues[item.name] ?? item.default;
          return acc;
        },
        {} as Record<string, object>,
      );
      onSubmitRef.current?.(finalValues);
      previousInitialValues.current = finalValues as Record<string, object>;
    });
    return () => subscription.unsubscribe();
  }, [form, editableItems]);

  return (
    <Form {...form}>
      <div className="space-y-4 w-full overflow-x-hidden">
        {itemConfigList.map((config) => {
          if (config.show_if) {
            const dependValue = resolveShowIfValue(
              config.show_if.field,
              watchedValues as Record<string, unknown>,
              externalDependentValues,
              systemContext,
            );

            if (
              config.show_if.operator === 'eq' &&
              dependValue !== config.show_if.value
            ) {
              return null;
            }
            if (
              config.show_if.operator === 'neq' &&
              dependValue === config.show_if.value
            ) {
              return null;
            }
            if (
              config.show_if.operator === 'in' &&
              Array.isArray(config.show_if.value) &&
              !config.show_if.value.includes(dependValue)
            ) {
              return null;
            }
          }

          // All fields are disabled when editing (creation_settings are immutable)
          const isFieldDisabled = !!isEditing;

          // Webhook URL fields are display-only; render outside of form binding
          if (config.type === 'webhook-url') {
            const webhookUrl = (systemContext?.webhook_url as string) || '';
            const extraWebhookUrl =
              (systemContext?.extra_webhook_url as string) || '';

            if (!webhookUrl) return null;

            return (
              <WebhookUrlField
                key={`${config.id}-${config.name}`}
                label={extractAndTranslateI18n(config.label)}
                description={
                  config.description
                    ? (typeof config.description === 'string'
                        ? (config.description.startsWith('workflows.') ? String(t(config.description)) : config.description)
                        : extractAndTranslateI18n(config.description))
                    : undefined
                }
                url={webhookUrl}
                extraUrl={extraWebhookUrl || undefined}
              />
            );
          }

          // Boolean fields use a special inline layout
          if (config.type === 'boolean') {
            return (
              <FormField
                key={`${config.id}-${config.name}`}
                control={form.control}
                name={config.name as keyof FormValues}
                render={({ field }) => (
                  <FormItem>
                    <div
                      className={cn(
                        'flex flex-row items-center justify-between rounded-lg border p-4 w-full max-w-full overflow-hidden',
                        isFieldDisabled && 'pointer-events-none opacity-60',
                      )}
                    >
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">
                          {extractAndTranslateI18n(config.label)}
                        </FormLabel>
                        {config.description && (
                          <p className="text-sm text-muted-foreground">
                            {typeof config.description === 'string'
                              ? (config.description.startsWith('workflows.') ? String(t(config.description)) : translateIfKey(config.description))
                              : extractAndTranslateI18n(config.description)}
                          </p>
                        )}
                      </div>
                      <FormControl>
                        <DynamicFormItemComponent
                          config={config}
                          field={field}
                          onFileUploaded={onFileUploaded}
                        />
                      </FormControl>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            );
          }

          return (
            <FormField
              key={`${config.id}-${config.name}`}
              control={form.control}
              name={config.name as keyof FormValues}
              render={({ field }) => {
                // Use the i18n label from config.label (I18nObject), falling back to config.name
                const i18nLabel = config.label
                  ? extractAndTranslateI18n(config.label)
                  : config.name;
                return (
                <FormItem>
                  <FormLabel>
                    {i18nLabel}{' '}
                    {config.required && <span className="text-red-500">*</span>}
                  </FormLabel>
                  <FormControl>
                    <div
                      className={
                        isFieldDisabled ? 'pointer-events-none opacity-60' : ''
                      }
                    >
                      <DynamicFormItemComponent
                        config={config}
                        field={field}
                        onFileUploaded={onFileUploaded}
                      />
                    </div>
                  </FormControl>
                  {config.description && (() => {
                    const desc = config.description;
                    if (typeof desc === 'string') {
                      if (desc.startsWith('workflows.')) {
                        return <p className="text-sm text-muted-foreground">{String(t(desc))}</p>;
                      }
                      return <p className="text-sm text-muted-foreground">{translateIfKey(desc) || desc}</p>;
                    }
                    return <p className="text-sm text-muted-foreground">{extractAndTranslateI18n(desc)}</p>;
                  })()}
                  <FormMessage />
                </FormItem>
              );
              }}
            />
          );
        })}
      </div>
    </Form>
  );
}
