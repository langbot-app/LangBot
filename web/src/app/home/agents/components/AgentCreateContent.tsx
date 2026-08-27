import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Bot, Workflow } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { AgentKind } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';
import ProcessorTypeDiagram from './ProcessorTypeDiagram';

export default function AgentCreateContent({
  onCreated,
}: {
  onCreated: (agentId: string) => void;
}) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<AgentKind>('agent');
  const formSchema = z.object({
    name: z.string().min(1, { message: t('agents.nameRequired') }),
    description: z.string().optional(),
    emoji: z.string().optional(),
  });
  type FormValues = z.infer<typeof formSchema>;
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      emoji: '🤖',
    },
  });

  function handleKindChange(nextKind: AgentKind) {
    const previousDefaultEmoji = kind === 'pipeline' ? '⚙️' : '🤖';
    const nextDefaultEmoji = nextKind === 'pipeline' ? '⚙️' : '🤖';
    setKind(nextKind);
    const currentEmoji = form.getValues('emoji');
    if (!currentEmoji || currentEmoji === previousDefaultEmoji) {
      form.setValue('emoji', nextDefaultEmoji);
    }
  }

  function handleSubmit(values: FormValues) {
    httpClient
      .createAgent({
        kind,
        name: values.name,
        description: values.description ?? '',
        emoji: values.emoji || (kind === 'pipeline' ? '⚙️' : '🤖'),
      })
      .then((resp) => {
        toast.success(t('agents.createSuccess'));
        onCreated(resp.uuid);
      })
      .catch((err) => {
        toast.error(t('agents.createError') + err.msg);
      });
  }

  const typeOptions = [
    {
      kind: 'agent' as const,
      icon: Bot,
      title: t('agents.agentType'),
      description: t('agents.agentTypeDescription'),
    },
    {
      kind: 'pipeline' as const,
      icon: Workflow,
      title: t('agents.pipelineType'),
      description: t('agents.pipelineTypeDescription'),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between pb-4 shrink-0">
        <h1 className="text-xl font-semibold">{t('agents.create')}</h1>
        <Button type="submit" form="agent-create-form">
          {t('common.submit')}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto max-w-6xl pb-6">
          <div className="grid items-stretch gap-5 lg:grid-cols-[minmax(340px,0.78fr)_minmax(0,1.22fr)]">
            <div className="space-y-5">
              <section
                aria-labelledby="processor-kind-heading"
                className="space-y-3"
              >
                <div>
                  <h2
                    id="processor-kind-heading"
                    className="text-base font-semibold"
                  >
                    {t('agents.chooseType')}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {t('agents.chooseTypeDescription')}
                  </p>
                </div>

                <ToggleGroup
                  type="single"
                  value={kind}
                  onValueChange={(value) => {
                    if (value) handleKindChange(value as AgentKind);
                  }}
                  variant="outline"
                  spacing={3}
                  className="grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-1"
                >
                  {typeOptions.map((option) => {
                    const Icon = option.icon;
                    return (
                      <ToggleGroupItem
                        key={option.kind}
                        value={option.kind}
                        data-processor-kind={option.kind}
                        aria-label={`${option.title} ${option.description}`}
                        className="h-auto min-h-28 w-full items-start justify-start gap-3 rounded-lg border px-4 py-4 text-left whitespace-normal shadow-none hover:bg-muted/40 data-[state=on]:border-[#2288ee]/50 data-[state=on]:bg-blue-50/60 data-[state=on]:text-foreground data-[state=on]:shadow-none dark:data-[state=on]:border-blue-500/50 dark:data-[state=on]:bg-blue-500/10"
                      >
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-background text-[#2288ee] shadow-xs">
                          <Icon className="size-4" />
                        </span>
                        <span className="min-w-0 space-y-1.5">
                          <span className="block text-sm font-medium">
                            {option.title}
                          </span>
                          <span className="block text-sm font-normal leading-relaxed text-muted-foreground">
                            {option.description}
                          </span>
                        </span>
                      </ToggleGroupItem>
                    );
                  })}
                </ToggleGroup>
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>{t('agents.basicInfo')}</CardTitle>
                  <CardDescription>
                    {t('agents.basicInfoDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Form {...form}>
                    <form
                      id="agent-create-form"
                      onSubmit={form.handleSubmit(handleSubmit)}
                      className="space-y-4"
                    >
                      <div className="flex gap-4 items-start">
                        <FormField
                          control={form.control}
                          name="name"
                          render={({ field }) => (
                            <FormItem className="flex-1">
                              <FormLabel>
                                {t('common.name')}
                                <span className="text-destructive">*</span>
                              </FormLabel>
                              <FormControl>
                                <Input {...field} value={field.value ?? ''} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="emoji"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>{t('common.icon')}</FormLabel>
                              <FormControl>
                                <EmojiPicker
                                  value={field.value}
                                  onChange={field.onChange}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <FormField
                        control={form.control}
                        name="description"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t('common.description')}</FormLabel>
                            <FormControl>
                              <Input {...field} value={field.value ?? ''} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </form>
                  </Form>
                </CardContent>
              </Card>
            </div>

            <Card className="min-h-[600px] overflow-hidden py-0 lg:min-h-[680px]">
              <CardContent className="flex h-full items-center p-0">
                <ProcessorTypeDiagram kind={kind} />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
