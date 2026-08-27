import { useState } from 'react';
import type React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Bot, CheckCircle2, Workflow } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { AgentKind } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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

  const typeOptions: Array<{
    kind: AgentKind;
    icon: React.ElementType;
    title: string;
    description: string;
    badge: string;
  }> = [
    {
      kind: 'agent',
      icon: Bot,
      title: t('agents.agentType'),
      description: t('agents.agentTypeDescription'),
      badge: t('agents.allEvents'),
    },
    {
      kind: 'pipeline',
      icon: Workflow,
      title: t('agents.pipelineType'),
      description: t('agents.pipelineTypeDescription'),
      badge: t('agents.messageEventsOnly'),
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

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  {typeOptions.map((option) => {
                    const Icon = option.icon;
                    const selected = kind === option.kind;
                    return (
                      <Card
                        key={option.kind}
                        data-processor-kind={option.kind}
                        className={cn(
                          'gap-0 py-0 transition-[border-color,box-shadow,background-color]',
                          selected
                            ? 'border-primary bg-primary/[0.035] shadow-sm ring-1 ring-primary/20'
                            : 'hover:border-primary/50',
                        )}
                      >
                        <CardContent className="h-full p-0">
                          <Button
                            type="button"
                            variant="ghost"
                            aria-pressed={selected}
                            onClick={() => handleKindChange(option.kind)}
                            className="h-full min-h-32 w-full items-start justify-start whitespace-normal rounded-xl p-4 text-left hover:bg-transparent"
                          >
                            <span
                              className={cn(
                                'flex size-10 shrink-0 items-center justify-center rounded-lg border bg-background',
                                selected &&
                                  'border-primary/30 bg-primary/10 text-primary',
                              )}
                            >
                              <Icon className="size-5" />
                            </span>
                            <span className="min-w-0 flex-1 space-y-2">
                              <span className="flex items-center justify-between gap-3">
                                <span className="font-semibold">
                                  {option.title}
                                </span>
                                {selected && (
                                  <CheckCircle2 className="size-4 shrink-0 text-primary" />
                                )}
                              </span>
                              <Badge
                                variant={selected ? 'default' : 'secondary'}
                                className="font-normal"
                              >
                                {option.badge}
                              </Badge>
                              <span className="block text-sm leading-relaxed text-muted-foreground">
                                {option.description}
                              </span>
                            </span>
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
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
