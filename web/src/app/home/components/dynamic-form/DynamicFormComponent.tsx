import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
  SYSTEM_FIELD_PREFIX,
} from '@/app/infra/entities/form/dynamic';
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
import { normalizeDynamicFormValuesForSave } from '@/app/home/components/dynamic-form/DynamicFormSaveValues';
import QrCodeLoginDialog, {
  QrLoginPlatform,
} from '@/app/home/components/qrcode-login/QrCodeLoginDialog';
import { useEffect, useMemo, useRef, useState } from 'react';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Copy,
  Check,
  Globe,
  Info,
  QrCode,
  Download,
  ExternalLink,
} from 'lucide-react';
import { copyToClipboard } from '@/app/utils/clipboard';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { systemInfo } from '@/app/infra/http';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';

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
  if (field.startsWith(SYSTEM_FIELD_PREFIX)) {
    const key = field.slice(SYSTEM_FIELD_PREFIX.length);
    return systemContext?.[key];
  }
  if (watchedValues[field] !== undefined) {
    return watchedValues[field];
  }
  return externalDependentValues?.[field];
}

type DynamicFormValueSpec = Pick<
  IDynamicFormItemSchema,
  'default' | 'name' | 'required' | 'type'
>;

function getValueSpecs(item: IDynamicFormItemSchema): DynamicFormValueSpec[] {
  if (item.type === DynamicFormItemType.RICH_TOOLS_SELECTOR) {
    return [
      item,
      {
        name: 'enable-all-tools',
        type: DynamicFormItemType.BOOLEAN,
        required: false,
        default: true,
      },
    ];
  }

  if (item.type === DynamicFormItemType.RESOURCES_SELECTOR) {
    return [
      item,
      {
        name: 'mcp-resources',
        type: DynamicFormItemType.UNKNOWN,
        required: false,
        default: [],
      },
      {
        name: 'mcp-resource-agent-read-enabled',
        type: DynamicFormItemType.BOOLEAN,
        required: false,
        default: true,
      },
    ];
  }

  return [item];
}

function getValueSchema(spec: DynamicFormValueSpec) {
  if (spec.name === 'mcp-resources') {
    return z.array(z.any());
  }

  switch (spec.type) {
    case DynamicFormItemType.INT:
      return z.number();
    case DynamicFormItemType.FLOAT:
      return z.number();
    case DynamicFormItemType.BOOLEAN:
      return z.boolean();
    case DynamicFormItemType.STRING:
      return z.string();
    case DynamicFormItemType.STRING_ARRAY:
      return z.array(z.string());
    case DynamicFormItemType.SELECT:
      return z.string();
    case DynamicFormItemType.LLM_MODEL_SELECTOR:
      return z.string();
    case DynamicFormItemType.EMBEDDING_MODEL_SELECTOR:
      return z.string();
    case DynamicFormItemType.RERANK_MODEL_SELECTOR:
      return z.string();
    case DynamicFormItemType.KNOWLEDGE_BASE_SELECTOR:
      return z.string();
    case DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR:
    case DynamicFormItemType.RESOURCES_SELECTOR:
    case DynamicFormItemType.RICH_TOOLS_SELECTOR:
    case DynamicFormItemType.TOOLS_SELECTOR:
      return z.array(z.string());
    case DynamicFormItemType.BOT_SELECTOR:
      return z.string();
    case DynamicFormItemType.MODEL_FALLBACK_SELECTOR:
      return z.object({
        primary: z.string(),
        fallbacks: z.array(z.string()),
      });
    case DynamicFormItemType.PROMPT_EDITOR:
      return z.array(
        z.object({
          content: z.string(),
          role: z.string(),
        }),
      );
    default:
      return z.string();
  }
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
    <FormItem className="min-w-0">
      <FormLabel className="break-words">{label}</FormLabel>
      <div className="flex min-w-0 items-center gap-2">
        <Input
          value={url}
          readOnly
          className="min-w-0 flex-1 bg-muted"
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
        <div className="mt-2 flex min-w-0 items-center gap-2">
          <Input
            value={extraUrl}
            readOnly
            className="min-w-0 flex-1 bg-muted"
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
        <p className="text-sm break-words text-muted-foreground">
          {description}
        </p>
      )}
      {systemInfo.edition === 'community' && (
        <div className="mt-1 flex max-w-full min-w-0 items-start gap-2.5 rounded-md border border-border/60 bg-muted/40 px-3 py-2.5">
          <Globe className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <p className="text-sm leading-relaxed break-words text-muted-foreground">
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

function DownloadLinkField({
  label,
  description,
  url,
  filename,
  helpUrl,
  helpLabel,
}: {
  label: string;
  description?: string;
  url: string;
  filename?: string;
  helpUrl?: string | null;
  helpLabel: string;
}) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  const downloadUrl = url.startsWith('http') ? url : `${baseUrl}${url}`;

  return (
    <FormItem className="min-w-0">
      <FormLabel className="break-words">{label}</FormLabel>
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <Button asChild variant="outline" size="sm">
          <a href={downloadUrl} download={filename}>
            <Download className="h-4 w-4" />
            {label}
          </a>
        </Button>
        {helpUrl && (
          <Button asChild variant="ghost" size="sm">
            <a href={helpUrl} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />
              {helpLabel}
            </a>
          </Button>
        )}
      </div>
      {description && (
        <p className="max-w-2xl text-sm break-words text-muted-foreground">
          {description}
        </p>
      )}
    </FormItem>
  );
}

/**
 * Display-only component for `__system.*` fields (e.g. the deployment's
 * outbound IPs that the operator must add to a platform's trusted-IP list).
 * Renders one read-only row per value, each with a copy button. Rendered
 * outside of react-hook-form binding since the values come from
 * systemContext, not user input.
 */
function SystemInfoField({
  label,
  description,
  values,
}: {
  label: string;
  description?: string;
  values: string[];
}) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = (text: string, index: number) => {
    copyToClipboard(text).catch(() => {});
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <FormItem className="min-w-0">
      <FormLabel className="break-words">{label}</FormLabel>
      <div className="space-y-2">
        {values.map((value, index) => (
          <div key={index} className="flex min-w-0 items-center gap-2">
            <Input
              value={value}
              readOnly
              className="min-w-0 flex-1 bg-muted"
              onClick={(e) => (e.target as HTMLInputElement).select()}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleCopy(value, index)}
            >
              {copiedIndex === index ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>
        ))}
      </div>
      {description && (
        <p className="text-sm break-words text-muted-foreground">
          {description}
        </p>
      )}
    </FormItem>
  );
}

// Hover-only Radix tooltips never open on touch devices (no pointer hover),
// so the ``disabled_tooltip`` explaining why a field is locked was invisible on
// mobile. This wrapper makes the info icon also toggle the tooltip on tap while
// keeping hover behavior on desktop.
function DisabledTooltipIcon({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip open={open} onOpenChange={setOpen}>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={text}
            className="inline-flex shrink-0"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen((v) => !v);
            }}
          >
            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help shrink-0" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{text}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
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
  const { t, i18n } = useTranslation();

  // Normalize a form value according to its field type.
  // This ensures legacy/malformed data (e.g. a plain string for
  // model-fallback-selector) is coerced to the expected shape
  // so that downstream components never crash.
  const normalizeFieldValue = (
    item: DynamicFormValueSpec,
    value: unknown,
  ): unknown => {
    if (
      item.name === 'mcp-resources' ||
      item.type === DynamicFormItemType.RESOURCES_SELECTOR ||
      item.type === DynamicFormItemType.RICH_TOOLS_SELECTOR
    ) {
      return Array.isArray(value) ? value : [];
    }
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

  // Filter out display-only fields (webhook-url/embed-code/qr-code-login types
  // and `__system.*`-named fields) that should not participate in form state,
  // validation, or value emission.
  const editableItems = useMemo(
    () =>
      itemConfigList.filter(
        (item) =>
          item.type !== 'webhook-url' &&
          item.type !== 'embed-code' &&
          item.type !== 'qr-code-login' &&
          item.type !== 'download-link' &&
          !item.name.startsWith(SYSTEM_FIELD_PREFIX),
      ),
    [itemConfigList],
  );

  const editableValueSpecs = useMemo(
    () => editableItems.flatMap(getValueSpecs),
    [editableItems],
  );

  // 根据 itemConfigList 动态生成 zod schema
  const formSchema = z.object(
    editableValueSpecs.reduce(
      (acc, item) => {
        let fieldSchema = getValueSchema(item);

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
    defaultValues: editableValueSpecs.reduce((acc, item) => {
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
      const mergedValues = editableValueSpecs.reduce(
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
  }, [initialValues, form, editableValueSpecs]);

  // Get reactive form values for conditional rendering
  const watchedValues = form.watch();
  const setFormValue = (name: string, value: unknown) => {
    form.setValue(name as keyof FormValues, value as never, {
      shouldDirty: true,
      shouldValidate: true,
    });
  };

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
    const initialFinalValues = normalizeDynamicFormValuesForSave(
      editableValueSpecs,
      formValues as Record<string, unknown>,
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
      const finalValues = normalizeDynamicFormValuesForSave(
        editableValueSpecs,
        formValues as Record<string, unknown>,
      );
      onSubmitRef.current?.(finalValues);
      previousInitialValues.current = finalValues as Record<string, object>;
    });
    return () => subscription.unsubscribe();
  }, [form, editableValueSpecs]);

  // State for QR code login dialog
  const [qrDialogOpen, setQrDialogOpen] = useState(false);
  const [qrDialogPlatform, setQrDialogPlatform] =
    useState<QrLoginPlatform>('feishu');

  return (
    <Form {...form}>
      <div className="min-w-0 max-w-full space-y-4 overflow-x-hidden">
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

          // ``disable_if`` mirrors ``show_if``'s evaluator but instead of
          // hiding the field, leaves it visible and inert. Use it when the
          // operator needs to see that the field exists yet cannot edit it
          // under the current runtime state (e.g. sandbox-bound fields when
          // Box is disabled).
          let isDisabledByCondition = false;
          if (config.disable_if) {
            const dependValue = resolveShowIfValue(
              config.disable_if.field,
              watchedValues as Record<string, unknown>,
              externalDependentValues,
              systemContext,
            );
            const cond = config.disable_if;
            if (cond.operator === 'eq' && dependValue === cond.value) {
              isDisabledByCondition = true;
            } else if (cond.operator === 'neq' && dependValue !== cond.value) {
              isDisabledByCondition = true;
            } else if (
              cond.operator === 'in' &&
              Array.isArray(cond.value) &&
              cond.value.includes(dependValue)
            ) {
              isDisabledByCondition = true;
            }
          }

          // All fields are disabled when editing (creation_settings are
          // immutable) or when ``disable_if`` matches.
          const isFieldDisabled = !!isEditing || isDisabledByCondition;
          const disabledTooltip =
            isDisabledByCondition && config.disabled_tooltip
              ? extractI18nObject(config.disabled_tooltip)
              : '';
          const renderDisabledTooltipIcon = () =>
            disabledTooltip ? (
              <DisabledTooltipIcon text={disabledTooltip} />
            ) : null;

          // `__system.*` fields are display-only; their value is resolved
          // from systemContext (same namespace as show_if), not user input.
          // Hidden entirely when the deployment doesn't provide the value.
          if (config.name.startsWith(SYSTEM_FIELD_PREFIX)) {
            const rawValue =
              systemContext?.[config.name.slice(SYSTEM_FIELD_PREFIX.length)];
            const values = (Array.isArray(rawValue) ? rawValue : [rawValue])
              .filter((v) => v !== undefined && v !== null && v !== '')
              .map(String);
            if (values.length === 0) return null;

            return (
              <SystemInfoField
                key={config.id}
                label={extractI18nObject(config.label)}
                description={
                  config.description
                    ? extractI18nObject(config.description)
                    : undefined
                }
                values={values}
              />
            );
          }

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

          if (config.type === 'download-link') {
            if (!config.url) return null;

            return (
              <DownloadLinkField
                key={config.id}
                label={extractI18nObject(config.label)}
                description={
                  config.description
                    ? extractI18nObject(config.description)
                    : undefined
                }
                url={config.url}
                filename={config.download_filename}
                helpUrl={getAdapterDocUrl(config.help_links, i18n.language)}
                helpLabel={
                  config.help_label
                    ? extractI18nObject(config.help_label)
                    : t('bots.viewAdapterDocs')
                }
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

          if (
            config.type === DynamicFormItemType.RICH_TOOLS_SELECTOR ||
            config.type === DynamicFormItemType.RESOURCES_SELECTOR
          ) {
            return (
              <FormField
                key={config.id}
                control={form.control}
                name={config.name as keyof FormValues}
                render={({ field }) => (
                  <FormItem className="min-w-0">
                    <FormControl>
                      <div
                        className={cn(
                          'min-w-0 max-w-full overflow-x-hidden',
                          isFieldDisabled && 'pointer-events-none opacity-60',
                        )}
                      >
                        <DynamicFormItemComponent
                          config={config}
                          field={field}
                          formValues={watchedValues as Record<string, unknown>}
                          onFileUploaded={onFileUploaded}
                          setFormValue={setFormValue}
                          systemContext={systemContext}
                        />
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
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
                  <FormItem className="min-w-0">
                    <div
                      className={cn(
                        'flex w-full min-w-0 max-w-full flex-row items-center justify-between rounded-lg border p-4',
                        isFieldDisabled && 'pointer-events-none opacity-60',
                      )}
                    >
                      <div className="min-w-0 space-y-0.5">
                        <FormLabel className="flex min-w-0 items-center gap-1.5 text-base">
                          {extractI18nObject(config.label)}
                          {renderDisabledTooltipIcon()}
                        </FormLabel>
                        {config.description && (
                          <p className="text-sm break-words text-muted-foreground">
                            {extractI18nObject(config.description)}
                          </p>
                        )}
                      </div>
                      <FormControl>
                        <DynamicFormItemComponent
                          config={config}
                          field={field}
                          formValues={watchedValues as Record<string, unknown>}
                          onFileUploaded={onFileUploaded}
                          setFormValue={setFormValue}
                          systemContext={systemContext}
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
                <FormItem className="min-w-0">
                  <FormLabel className="flex min-w-0 items-center gap-1.5">
                    <span className="min-w-0 break-words">
                      {extractI18nObject(config.label)}{' '}
                      {config.required && (
                        <span className="text-red-500">*</span>
                      )}
                    </span>
                    {renderDisabledTooltipIcon()}
                  </FormLabel>
                  <FormControl>
                    <div
                      className={cn(
                        'min-w-0 max-w-full overflow-x-hidden',
                        isFieldDisabled && 'pointer-events-none opacity-60',
                      )}
                    >
                      <DynamicFormItemComponent
                        config={config}
                        field={field}
                        formValues={watchedValues as Record<string, unknown>}
                        onFileUploaded={onFileUploaded}
                        setFormValue={setFormValue}
                        systemContext={systemContext}
                      />
                    </div>
                  </FormControl>
                  {config.description && (
                    <p className="text-sm break-words text-muted-foreground">
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
