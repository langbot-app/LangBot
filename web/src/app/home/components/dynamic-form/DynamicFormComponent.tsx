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
import QrCodeLoginDialog, {
  QrLoginPlatform,
} from '@/app/home/components/qrcode-login/QrCodeLoginDialog';
import { useEffect, useMemo, useRef, useState } from 'react';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Copy, Check, Globe, QrCode } from 'lucide-react';
import { copyToClipboard } from '@/app/utils/clipboard';
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
 * Display-only component for embed code fields with copy animation.
 */
function EmbedCodeField({
  label,
  description,
  snippet,
}: {
  label: string;
  description?: string;
  snippet: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    copyToClipboard(snippet).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium leading-none">{label}</label>
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
      <div className="flex items-center gap-2">
        <pre className="flex-1 overflow-x-auto rounded-md bg-muted p-3 text-sm font-mono select-all">
          <code>{snippet}</code>
        </pre>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="shrink-0"
          onClick={handleCopy}
        >
          {copied ? (
            <Check className="h-4 w-4 text-green-600" />
          ) : (
            <Copy className="size-4" />
          )}
        </Button>
      </div>
    </div>
  );
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
    copyToClipboard(text).catch(() => {});
    setter(true);
    setTimeout(() => setter(false), 2000);
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
  onValidate,
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
  /** Callback to expose validation function to parent component.
   *  Parent can call this function to trigger validation and get validity state. */
  onValidate?: (validateFn: () => Promise<boolean>) => void;
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
    return value;
  };

  // Filter out display-only field types (e.g. webhook-url, embed-code) that should not
  // participate in form state, validation, or value emission.
  const editableItems = useMemo(
    () =>
      itemConfigList.filter(
        (item) =>
          item.type !== 'webhook-url' &&
          item.type !== 'embed-code' &&
          item.type !== 'qr-code-login',
      ),
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

  // Expose validation function to parent component
  const validate = async (): Promise<boolean> => {
    // Trigger validation for all fields
    const result = await form.trigger();
    return result;
  };

  useEffect(() => {
    onValidate?.(validate);
  }, [onValidate]);

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

  // State for QR code login dialog
  const [qrDialogOpen, setQrDialogOpen] = useState(false);
  const [qrDialogPlatform, setQrDialogPlatform] =
    useState<QrLoginPlatform>('feishu');

  return (
    <Form {...form}>
      <div className="space-y-4">
        {/* QR code login dialog */}
        <QrCodeLoginDialog
          open={qrDialogOpen}
          onOpenChange={setQrDialogOpen}
          platform={qrDialogPlatform}
          onSuccess={(credentials) => {
            for (const [key, value] of Object.entries(credentials)) {
              if (value) {
                form.setValue(key as keyof FormValues, value as never);
              }
            }
          }}
        />

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
                key={config.id}
                label={extractI18nObject(config.label)}
                description={
                  config.description
                    ? extractI18nObject(config.description)
                    : undefined
                }
                url={webhookUrl}
                extraUrl={extraWebhookUrl || undefined}
              />
            );
          }

          if (config.type === 'embed-code') {
            const botUuid = (systemContext?.bot_uuid as string) || '';
            if (!botUuid) return null;

            const baseUrl =
              import.meta.env.VITE_API_BASE_URL || window.location.origin;
            const widgetTitle =
              ((systemContext?.adapter_config as Record<string, unknown>)
                ?.title as string) || 'LangBot';
            const safeTitle = widgetTitle
              .replace(/&/g, '&amp;')
              .replace(/"/g, '&quot;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;');
            const embedSnippet = `<script data-title="${safeTitle}" src="${baseUrl}/api/v1/embed/${botUuid}/widget.js"><\/script>`;

            return (
              <EmbedCodeField
                key={config.id}
                label={extractI18nObject(config.label)}
                description={
                  config.description
                    ? extractI18nObject(config.description)
                    : undefined
                }
                snippet={embedSnippet}
              />
            );
          }

          // QR code login button (e.g. Feishu one-click create, WeChat scan login)
          if (config.type === 'qr-code-login') {
            return (
              <FormItem key={config.id}>
                <div
                  className="relative flex items-center gap-4 p-4 rounded-xl border-2 border-dashed cursor-pointer transition-all hover:border-solid hover:shadow-md group"
                  style={{
                    borderColor:
                      'color-mix(in srgb, var(--primary) 25%, transparent)',
                    background:
                      'color-mix(in srgb, var(--primary) 3%, transparent)',
                  }}
                  onClick={() => {
                    if (!isEditing) {
                      setQrDialogPlatform(
                        (config.login_platform as QrLoginPlatform) || 'feishu',
                      );
                      setQrDialogOpen(true);
                    }
                  }}
                >
                  <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-primary/10 shrink-0">
                    <QrCode className="h-6 w-6 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">
                        {extractI18nObject(config.label)}
                      </span>
                      <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-primary text-primary-foreground">
                        {t('common.recommend')}
                      </span>
                    </div>
                    {config.description && (
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                        {extractI18nObject(config.description)}
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    disabled={!!isEditing}
                    className="shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      setQrDialogPlatform(
                        (config.login_platform as QrLoginPlatform) || 'feishu',
                      );
                      setQrDialogOpen(true);
                    }}
                  >
                    <QrCode className="h-3.5 w-3.5 mr-1" />
                    {t('common.start')}
                  </Button>
                </div>
              </FormItem>
            );
          }

          // Boolean fields use a special inline layout
          if (config.type === 'boolean') {
            return (
              <FormField
                key={config.id}
                control={form.control}
                name={config.name as keyof FormValues}
                render={({ field }) => (
                  <FormItem>
                    <div
                      className={cn(
                        'flex flex-row items-center justify-between rounded-lg border p-4 max-w-2xl',
                        isFieldDisabled && 'pointer-events-none opacity-60',
                      )}
                    >
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">
                          {extractI18nObject(config.label)}
                        </FormLabel>
                        {config.description && (
                          <p className="text-sm text-muted-foreground">
                            {extractI18nObject(config.description)}
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
              key={config.id}
              control={form.control}
              name={config.name as keyof FormValues}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {extractI18nObject(config.label)}{' '}
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
                  {config.description && (
                    <p className="text-sm text-muted-foreground">
                      {extractI18nObject(config.description)}
                    </p>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />
          );
        })}
      </div>
    </Form>
  );
}
