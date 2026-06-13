import { useEffect, useState, useRef, useCallback } from 'react';
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
import { DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CustomApiError } from '@/app/infra/entities/common';
import { cn } from '@/lib/utils';
import { Check, ChevronDown, Search } from 'lucide-react';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.providerNameRequired') }),
    requester: z.string().min(1, { message: t('models.requesterRequired') }),
    base_url: z.string(),
    api_key: z.string().optional(),
  });

interface ProviderFormProps {
  providerId?: string;
  onFormSubmit: () => void;
  onFormCancel: () => void;
}

export default function ProviderForm({
  providerId,
  onFormSubmit,
  onFormCancel,
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
  const { setValue } = form;

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
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const loadRequesters = useCallback(async () => {
    const resp = await httpClient.getProviderRequesters();
    setRequesterList(
      resp.requesters
        .filter((item) => item.name !== 'space-chat-completions')
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
  }, []);

  const loadProvider = useCallback(
    async (id: string) => {
      const resp = await httpClient.getModelProvider(id);
      const provider = resp.provider;

      setValue('name', provider.name);
      setValue('requester', provider.requester);
      setValue('base_url', provider.base_url);
      setValue('api_key', provider.api_keys?.[0] || '');
    },
    [setValue],
  );

  useEffect(() => {
    async function init() {
      await loadRequesters();
      if (providerId) {
        await loadProvider(providerId);
      }
    }
    init();
  }, [providerId, loadProvider, loadRequesters]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setSearchQuery('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);

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
    const data = {
      name: values.name,
      requester: values.requester,
      base_url: values.base_url,
      api_keys: values.api_key ? [values.api_key] : [],
    };

    try {
      if (providerId) {
        await httpClient.updateModelProvider(providerId, data);
        toast.success(t('models.providerSaved'));
      } else {
        await httpClient.createModelProvider(data);
        toast.success(t('models.providerCreated'));
      }
      onFormSubmit();
    } catch (err) {
      toast.error(t('models.providerSaveError') + (err as CustomApiError).msg);
    }
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
                <Input {...field} />
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
                <div ref={dropdownRef} className="relative">
                  {/* Trigger button */}
                  <button
                    type="button"
                    onClick={() => setIsOpen(!isOpen)}
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

                  {/* Dropdown */}
                  {isOpen && (
                    <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95">
                      {/* Search input */}
                      <div className="flex items-center border-b px-3">
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
                      <div className="max-h-[300px] overflow-y-auto p-1">
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
                    </div>
                  )}
                </div>
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

        <FormField
          control={form.control}
          name="base_url"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('models.requestURL')}</FormLabel>
              <FormControl>
                <Input {...field} />
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

        <DialogFooter>
          <Button type="submit">{t('common.save')}</Button>
          <Button type="button" variant="outline" onClick={onFormCancel}>
            {t('common.cancel')}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}
