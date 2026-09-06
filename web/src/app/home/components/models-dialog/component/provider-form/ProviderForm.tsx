import { useEffect, useState, useRef } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { DialogFooter } from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { LANGBOT_MODELS_PROVIDER_REQUESTER } from '../../types';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CustomApiError } from '@/app/infra/entities/common';
import { cn } from '@/lib/utils';
import { Check, ChevronDown, Search } from 'lucide-react';
import { providerPayload } from './codexPolicy';
import { useCodexLogin } from './useCodexLogin';
import CodexAccountSection from './CodexAccountSection';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.providerNameRequired') }),
    requester: z.string().min(1, { message: t('models.requesterRequired') }),
    base_url: z.string(),
    api_key: z.string().optional(),
  });

interface ProviderFormProps {
  providerId?: string;
  onFormSubmit: (providerUuid: string) => void | Promise<void>;
  onFormCancel: () => void;
  onProviderDeleted?: (providerUuid: string) => void | Promise<void>;
}

export default function ProviderForm({
  providerId,
  onFormSubmit,
  onFormCancel,
  onProviderDeleted,
}: ProviderFormProps) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      requester: '',
      base_url: '',
      api_key: '',
    },
  });
  const { reset } = form;
  const isCodex = form.watch('requester') === 'openai-codex';
  const [savedProviderId, setSavedProviderId] = useState(providerId);
  const savedId = useRef(providerId);
  const submitting = useRef(false);
  const deleting = useRef(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [mutableProviderLoaded, setMutableProviderLoaded] = useState(false);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>(
    'loading',
  );
  const [loadAttempt, setLoadAttempt] = useState(0);
  const mounted = useRef(true);
  const login = useCodexLogin(isCodex, providerId);
  const loginActive = ['starting', 'pending', 'canceling', 'loading'].includes(
    login.phase,
  );
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const [requesterList, setRequesterList] = useState<
    {
      label: string;
      value: string;
      category: string;
      defaultUrl: string;
      description: string;
      alias: string;
    }[]
  >([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Ignore both success and failure from a closed form or superseded attempt.
    let canceled = false;
    setLoadState('loading');
    setMutableProviderLoaded(false);

    async function init() {
      try {
        const [requesters, detail] = await Promise.all([
          httpClient.getProviderRequesters(),
          providerId ? httpClient.getModelProvider(providerId) : null,
        ]);
        if (canceled) return;
        setRequesterList(
          requesters.requesters
            .filter((item) => item.name !== LANGBOT_MODELS_PROVIDER_REQUESTER)
            .map((item) => ({
              label: extractI18nObject(item.label),
              value: item.name,
              category: item.spec.provider_category || 'manufacturer',
              defaultUrl:
                item.spec.config
                  .find((c) => c.name === 'base_url')
                  ?.default?.toString() || '',
              description: extractI18nObject(item.description),
              alias: item.spec.alias || '',
            })),
        );
        if (detail) {
          const provider = detail.provider;
          reset({
            name: provider.name,
            requester: provider.requester,
            base_url: provider.base_url,
            api_key: provider.api_keys?.[0] || '',
          });
          setMutableProviderLoaded(
            provider.uuid === providerId &&
              provider.requester !== LANGBOT_MODELS_PROVIDER_REQUESTER,
          );
        }
        setLoadState('ready');
      } catch {
        if (!canceled) setLoadState('error');
      }
    }
    void init();
    return () => {
      canceled = true;
    };
  }, [providerId, reset, loadAttempt]);

  // Filter requesters based on search query
  const filteredRequesters = requesterList.filter(
    (r) =>
      r.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.value.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.alias.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Group filtered requesters by category
  const groupedRequesters = {
    builtin: filteredRequesters.filter((r) => r.category === 'builtin'),
    manufacturer: filteredRequesters.filter(
      (r) => r.category === 'manufacturer',
    ),
    maas: filteredRequesters.filter((r) => r.category === 'maas'),
    'self-hosted': filteredRequesters.filter(
      (r) => r.category === 'self-hosted',
    ),
  };

  const categoryLabels: Record<string, string> = {
    builtin: t('models.builtin'),
    manufacturer: t('models.modelManufacturer'),
    maas: t('models.aggregationPlatform'),
    'self-hosted': t('models.selfDeployed'),
  };

  async function handleFormSubmit(values: z.infer<typeof formSchema>) {
    if (
      loadState !== 'ready' ||
      submitting.current ||
      deleting.current ||
      (isCodex && loginActive)
    )
      return;
    submitting.current = true;
    const data = providerPayload(values);
    try {
      if (savedId.current) {
        await httpClient.updateModelProvider(savedId.current, data);
      } else {
        const response = await httpClient.createModelProvider(data);
        savedId.current = response.uuid;
        if (mounted.current) setSavedProviderId(response.uuid);
      }
      if (!mounted.current) return;
      if (isCodex && login.phase !== 'connected') {
        await login.start(savedId.current);
      } else {
        toast.success(t('models.providerSaved'));
        await onFormSubmit(savedId.current);
      }
    } catch (err) {
      if (mounted.current)
        toast.error(
          t('models.providerSaveError') + (err as CustomApiError).msg,
        );
    } finally {
      submitting.current = false;
    }
  }

  async function handleDelete() {
    if (
      loadState !== 'ready' ||
      !providerId ||
      !mutableProviderLoaded ||
      !onProviderDeleted ||
      deleting.current ||
      submitting.current ||
      (isCodex && loginActive)
    )
      return;
    deleting.current = true;
    setIsDeleting(true);
    setDeleteError('');
    try {
      await httpClient.deleteModelProvider(providerId, true);
    } catch (err) {
      const detail =
        (err as CustomApiError | null)?.msg ||
        (err instanceof Error ? err.message : '');
      setDeleteError(t('models.providerDeleteError') + detail);
      deleting.current = false;
      setIsDeleting(false);
      return;
    }
    toast.success(t('models.providerDeleted'));
    await onProviderDeleted(providerId);
  }

  if (loadState !== 'ready') {
    return (
      <>
        {loadState === 'loading' ? (
          <div
            role="status"
            aria-label={t('common.loading')}
            className="flex justify-center py-8"
          >
            <LoadingSpinner text={t('common.loading')} />
          </div>
        ) : (
          <p role="alert" className="py-8 text-sm text-destructive">
            {t('models.loadError')}
          </p>
        )}
        <DialogFooter>
          {loadState === 'error' && (
            <Button
              type="button"
              onClick={() => {
                setLoadState('loading');
                setLoadAttempt((attempt) => attempt + 1);
              }}
            >
              {t('common.retry')}
            </Button>
          )}
          <Button type="button" variant="outline" onClick={onFormCancel}>
            {t('common.cancel')}
          </Button>
        </DialogFooter>
      </>
    );
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleFormSubmit)}
        className="space-y-4"
      >
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {t('models.providerName')}
                <span className="text-red-500">*</span>
              </FormLabel>
              <FormControl>
                <Input
                  {...field}
                  disabled={
                    form.formState.isSubmitting || (isCodex && loginActive)
                  }
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="requester"
          render={({ field }) => {
            const selectedRequester = requesterList.find(
              (r) => r.value === field.value,
            );
            return (
              <FormItem>
                <FormLabel>
                  {t('models.requester')}
                  <span className="text-red-500">*</span>
                </FormLabel>
                <Popover
                  open={isOpen}
                  onOpenChange={(open) => {
                    setIsOpen(open);
                    if (!open) setSearchQuery('');
                  }}
                >
                  {/* Trigger button */}
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      disabled={
                        form.formState.isSubmitting ||
                        (isCodex && (!!savedProviderId || loginActive))
                      }
                      aria-expanded={isOpen}
                      className={cn(
                        'flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
                        isOpen && 'ring-2 ring-ring ring-offset-2',
                      )}
                    >
                      {selectedRequester ? (
                        <div className="flex items-center gap-2">
                          <img
                            src={httpClient.getProviderRequesterIconURL(
                              selectedRequester.value,
                            )}
                            alt={selectedRequester.label}
                            className="h-5 w-5 rounded"
                          />
                          <span>{selectedRequester.label}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">
                          {t('models.selectRequester')}
                        </span>
                      )}
                      <ChevronDown
                        className={cn(
                          'h-4 w-4 opacity-50 transition-transform',
                          isOpen && 'rotate-180',
                        )}
                      />
                    </button>
                  </PopoverTrigger>

                  {/* Unmount on close so an exiting layer cannot eat Dialog Escape. */}
                  {isOpen && (
                    <PopoverContent
                      align="start"
                      collisionPadding={8}
                      className="flex max-h-[var(--radix-popover-content-available-height)] w-[var(--radix-popover-trigger-width)] max-w-[calc(100vw-16px)] flex-col overflow-hidden p-0"
                      onOpenAutoFocus={(event) => {
                        event.preventDefault();
                        searchInputRef.current?.focus();
                      }}
                    >
                      {/* Search input */}
                      <div className="flex shrink-0 items-center border-b px-3">
                        <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
                        <input
                          ref={searchInputRef}
                          type="text"
                          placeholder={
                            t('models.searchProviders') || 'Search providers...'
                          }
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          className="flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
                        />
                      </div>

                      {/* Options list */}
                      <div
                        className="min-h-0 max-h-[300px] overflow-y-auto overscroll-contain p-1"
                        // The dialog's document-level scroll lock treats this portal as outside.
                        // Keep native list scrolling without forwarding gestures to that lock.
                        onWheel={(event) => event.stopPropagation()}
                        onTouchMove={(event) => event.stopPropagation()}
                      >
                        {Object.entries(groupedRequesters).map(
                          ([category, items]) => {
                            if (items.length === 0) return null;
                            return (
                              <div key={category}>
                                <div className="py-1.5 px-2 text-xs font-semibold text-muted-foreground">
                                  {categoryLabels[category]}
                                </div>
                                {items.map((r) => (
                                  <button
                                    key={r.value}
                                    type="button"
                                    disabled={
                                      !!providerId &&
                                      r.value === 'openai-codex' &&
                                      !isCodex
                                    }
                                    onClick={() => {
                                      field.onChange(r.value);
                                      const req = requesterList.find(
                                        (req) => req.value === r.value,
                                      );
                                      if (
                                        req &&
                                        (!providerId ||
                                          !form.getValues('base_url'))
                                      ) {
                                        form.setValue(
                                          'base_url',
                                          req.defaultUrl,
                                        );
                                      }
                                      setIsOpen(false);
                                      setSearchQuery('');
                                    }}
                                    className={cn(
                                      'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground cursor-pointer',
                                      field.value === r.value &&
                                        'bg-accent text-accent-foreground',
                                    )}
                                  >
                                    <img
                                      src={httpClient.getProviderRequesterIconURL(
                                        r.value,
                                      )}
                                      alt={r.label}
                                      className="h-5 w-5 rounded"
                                    />
                                    <span className="flex-1 text-left">
                                      {r.label}
                                    </span>
                                    {field.value === r.value && (
                                      <Check className="h-4 w-4" />
                                    )}
                                  </button>
                                ))}
                              </div>
                            );
                          },
                        )}
                        {filteredRequesters.length === 0 && (
                          <div className="py-6 text-center text-sm text-muted-foreground">
                            No results found.
                          </div>
                        )}
                      </div>
                    </PopoverContent>
                  )}
                </Popover>
                <FormMessage />
                {selectedRequester?.description && (
                  <p className="text-sm text-muted-foreground">
                    {selectedRequester.description}
                  </p>
                )}
              </FormItem>
            );
          }}
        />

        {isCodex ? (
          <CodexAccountSection login={login} providerId={savedProviderId} />
        ) : (
          <>
            <FormField
              control={form.control}
              name="base_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('models.requestURL')}</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      disabled={
                        form.formState.isSubmitting || (isCodex && loginActive)
                      }
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="api_key"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('models.apiKey')}</FormLabel>
                  <FormControl>
                    <Input {...field} type="password" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        )}

        <DialogFooter className="flex-row flex-wrap items-start justify-between sm:justify-between">
          {providerId && mutableProviderLoaded && onProviderDeleted && (
            <Button
              type="button"
              variant="destructive"
              disabled={
                isDeleting ||
                form.formState.isSubmitting ||
                (isCodex && loginActive)
              }
              onClick={() => {
                setDeleteError('');
                setDeleteConfirmOpen(true);
              }}
            >
              {t('common.delete')}
            </Button>
          )}
          <div className="ml-auto flex flex-col gap-2 sm:flex-row">
            {(!isCodex || !savedProviderId || login.phase === 'connected') && (
              <Button
                type="submit"
                disabled={
                  isDeleting ||
                  form.formState.isSubmitting ||
                  (isCodex && loginActive)
                }
              >
                {isCodex
                  ? t(
                      login.phase === 'connected'
                        ? 'models.codex.done'
                        : 'models.codex.saveAndSignIn',
                    )
                  : t('common.save')}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              disabled={isDeleting}
              onClick={onFormCancel}
            >
              {t('common.cancel')}
            </Button>
          </div>
        </DialogFooter>
        <AlertDialog
          open={deleteConfirmOpen}
          onOpenChange={(open) => {
            if (!deleting.current) setDeleteConfirmOpen(open);
          }}
        >
          {deleteConfirmOpen && (
            <AlertDialogContent className="max-w-[calc(100%-2rem)] max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-lg">
              <AlertDialogHeader>
                <AlertDialogTitle>{t('common.delete')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t('models.deleteProviderCascadeConfirmation')}
                </AlertDialogDescription>
              </AlertDialogHeader>
              {deleteError && (
                <p
                  role="alert"
                  className="text-sm text-destructive break-words"
                >
                  {deleteError}
                </p>
              )}
              <AlertDialogFooter>
                <AlertDialogCancel disabled={isDeleting}>
                  {t('common.cancel')}
                </AlertDialogCancel>
                <Button
                  type="button"
                  variant="destructive"
                  disabled={isDeleting}
                  aria-busy={isDeleting}
                  onClick={handleDelete}
                >
                  {t('common.delete')}
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          )}
        </AlertDialog>
      </form>
    </Form>
  );
}
