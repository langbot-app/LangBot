import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KnowledgeBase, EmbeddingModel } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z
      .string()
      .min(1, { message: t('knowledge.kbDescriptionRequired') }),
    embeddingModelUUID: z
      .string()
      .min(1, { message: t('knowledge.embeddingModelUUIDRequired') }),
    top_k: z
      .number()
      .min(1, { message: t('knowledge.topKRequired') })
      .max(30, { message: t('knowledge.topKMax') }),
  });

export default function KBForm({
  initKbId,
  onNewKbCreated,
  onKbUpdated,
}: {
  initKbId?: string;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated: (kbId: string) => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: t('knowledge.defaultDescription'),
      embeddingModelUUID: '',
      top_k: 5,
    },
  });

  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([]);

  useEffect(() => {
    getEmbeddingModelNameList().then(() => {
      if (initKbId) {
        getKbConfig(initKbId).then((val) => {
          form.setValue('name', val.name);
          form.setValue('description', val.description);
          form.setValue('embeddingModelUUID', val.embeddingModelUUID);
          form.setValue('top_k', val.top_k || 5);
        });
      }
    });
  }, []);

  const getKbConfig = async (
    kbId: string,
  ): Promise<z.infer<typeof formSchema>> => {
    return new Promise((resolve) => {
      httpClient.getKnowledgeBase(kbId).then((res) => {
        resolve({
          name: res.base.name,
          description: res.base.description,
          embeddingModelUUID: res.base.embedding_model_uuid,
          top_k: res.base.top_k || 5,
        });
      });
    });
  };

  const getEmbeddingModelNameList = async () => {
    const resp = await httpClient.getProviderEmbeddingModels();
    setEmbeddingModels(resp.models);
  };

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    console.log('data', data);

    if (initKbId) {
      // update knowledge base
      const updateKb: KnowledgeBase = {
        name: data.name,
        description: data.description,
        embedding_model_uuid: data.embeddingModelUUID,
        top_k: data.top_k,
      };
      httpClient
        .updateKnowledgeBase(initKbId, updateKb)
        .then((res) => {
          console.log('update knowledge base success', res);
          onKbUpdated(res.uuid);
          toast.success(t('knowledge.updateKnowledgeBaseSuccess'));
        })
        .catch((err) => {
          console.error('update knowledge base failed', err);
          toast.error(t('knowledge.updateKnowledgeBaseFailed'));
        });
    } else {
      // create knowledge base
      const newKb: KnowledgeBase = {
        name: data.name,
        description: data.description,
        embedding_model_uuid: data.embeddingModelUUID,
        top_k: data.top_k,
      };
      httpClient
        .createKnowledgeBase(newKb)
        .then((res) => {
          console.log('create knowledge base success', res);
          onNewKbCreated(res.uuid);
        })
        .catch((err) => {
          console.error('create knowledge base failed', err);
        });
    }
  };

  return (
    <>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          id="kb-form"
          className="space-y-8"
        >
          <div className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.kbName')}
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
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.kbDescription')}
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
              name="embeddingModelUUID"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.embeddingModelUUID')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Select
                        disabled={!!initKbId}
                        onValueChange={(value) => {
                          field.onChange(value);
                          console.log('value', value);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="w-[180px] bg-[#ffffff] dark:bg-[#2a2a2e]">
                          <SelectValue
                            placeholder={t('knowledge.selectEmbeddingModel')}
                          />
                        </SelectTrigger>
                        <SelectContent className="fixed z-[1000]">
                          <SelectGroup>
                            {embeddingModels.map((model) => (
                              <HoverCard
                                key={model.uuid}
                                openDelay={0}
                                closeDelay={0}
                              >
                                <HoverCardTrigger asChild>
                                  <SelectItem value={model.uuid}>
                                    {model.name}
                                  </SelectItem>
                                </HoverCardTrigger>
                                <HoverCardContent
                                  className="w-80 data-[state=open]:animate-none data-[state=closed]:animate-none"
                                  align="end"
                                  side="right"
                                  sideOffset={10}
                                >
                                  <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                      <img
                                        src={httpClient.getProviderRequesterIconURL(
                                          model.requester,
                                        )}
                                        alt="icon"
                                        className="w-8 h-8 rounded-full"
                                      />
                                      <h4 className="font-medium">
                                        {model.name}
                                      </h4>
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                      {model.description}
                                    </p>
                                    {model.requester_config && (
                                      <div className="flex items-center gap-1 text-xs">
                                        <svg
                                          className="w-4 h-4 text-gray-500"
                                          xmlns="http://www.w3.org/2000/svg"
                                          viewBox="0 0 24 24"
                                          fill="currentColor"
                                        >
                                          <path d="M13.0607 8.11097L14.4749 9.52518C17.2086 12.2589 17.2086 16.691 14.4749 19.4247L14.1214 19.7782C11.3877 22.5119 6.95555 22.5119 4.22188 19.7782C1.48821 17.0446 1.48821 12.6124 4.22188 9.87874L5.6361 11.293C3.68348 13.2456 3.68348 16.4114 5.6361 18.364C7.58872 20.3166 10.7545 20.3166 12.7072 18.364L13.0607 18.0105C15.0133 16.0578 15.0133 12.892 13.0607 10.9394L11.6465 9.52518L13.0607 8.11097ZM19.7782 14.1214L18.364 12.7072C20.3166 10.7545 20.3166 7.58872 18.364 5.6361C16.4114 3.68348 13.2456 3.68348 11.293 5.6361L10.9394 5.98965C8.98678 7.94227 8.98678 11.1081 10.9394 13.0607L12.3536 14.4749L10.9394 15.8891L9.52518 14.4749C6.79151 11.7413 6.79151 7.30911 9.52518 4.57544L9.87874 4.22188C12.6124 1.48821 17.0446 1.48821 19.7782 4.22188C22.5119 6.95555 22.5119 11.3877 19.7782 14.1214Z"></path>
                                        </svg>
                                        <span className="font-semibold">
                                          Base URL：
                                        </span>
                                        {model.requester_config.base_url}
                                      </div>
                                    )}
                                    {model.extra_args &&
                                      Object.keys(model.extra_args).length >
                                        0 && (
                                        <div className="text-xs">
                                          <div className="font-semibold mb-1">
                                            {t('models.extraParameters')}
                                          </div>
                                          <div className="space-y-1">
                                            {Object.entries(
                                              model.extra_args as Record<
                                                string,
                                                unknown
                                              >,
                                            ).map(([key, value]) => (
                                              <div
                                                key={key}
                                                className="flex items-center gap-1"
                                              >
                                                <span className="text-gray-500">
                                                  {key}：
                                                </span>
                                                <span className="break-all">
                                                  {JSON.stringify(value)}
                                                </span>
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                  </div>
                                </HoverCardContent>
                              </HoverCard>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </div>
                  </FormControl>
                  <FormDescription>
                    {initKbId
                      ? t('knowledge.cannotChangeEmbeddingModel')
                      : t('knowledge.embeddingModelDescription')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="top_k"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.topK')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      {...field}
                      onChange={(e) => field.onChange(Number(e.target.value))}
                      className="w-[180px] h-10 text-base appearance-none"
                    />
                  </FormControl>
                  <FormDescription>
                    {t('knowledge.topKdescription')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </form>
      </Form>
    </>
  );
}
