import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useSidebarData,
  SidebarEntityItem,
} from '../home-sidebar/SidebarDataContext';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Check, ChevronsUpDown, GitBranch, Workflow } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

export type BindingType = 'pipeline' | 'workflow';

export interface BindingValue {
  type: BindingType;
  id: string | null;
}

interface UnifiedBindingSelectorProps {
  value: BindingValue;
  onChange: (value: BindingValue) => void;
  disabled?: boolean;
  className?: string;
}

export default function UnifiedBindingSelector({
  value,
  onChange,
  disabled = false,
  className,
}: UnifiedBindingSelectorProps) {
  const { t } = useTranslation();
  const { pipelines, workflows, refreshPipelines, refreshWorkflows } =
    useSidebarData();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    refreshPipelines();
    refreshWorkflows();
  }, [refreshPipelines, refreshWorkflows]);

  // Get current selection display
  const getSelectionDisplay = () => {
    if (!value.id) {
      return t('bots.selectBinding');
    }

    if (value.type === 'pipeline') {
      const pipeline = pipelines.find((p) => p.id === value.id);
      return pipeline ? (
        <div className="flex items-center gap-2">
          {pipeline.emoji && <span>{pipeline.emoji}</span>}
          <span>{pipeline.name}</span>
          <Badge variant="outline" className="text-xs">
            Pipeline
          </Badge>
        </div>
      ) : (
        value.id
      );
    } else {
      const workflow = workflows.find((w) => w.id === value.id);
      return workflow ? (
        <div className="flex items-center gap-2">
          {workflow.emoji && <span>{workflow.emoji}</span>}
          <span>{workflow.name}</span>
          <Badge variant="secondary" className="text-xs">
            Workflow
          </Badge>
        </div>
      ) : (
        value.id
      );
    }
  };

  // Handle type change
  const handleTypeChange = (newType: BindingType) => {
    onChange({
      type: newType,
      id: null,
    });
  };

  // Handle selection
  const handleSelect = (id: string, type: BindingType) => {
    onChange({
      type,
      id,
    });
    setOpen(false);
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Binding type selection */}
      <div className="space-y-2">
        <Label>{t('bots.bindingType')}</Label>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={value.type === 'pipeline' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleTypeChange('pipeline')}
            disabled={disabled}
            className="flex-1"
          >
            <GitBranch className="size-4 mr-1.5" />
            Pipeline
          </Button>
          <Button
            type="button"
            variant={value.type === 'workflow' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleTypeChange('workflow')}
            disabled={disabled}
            className="flex-1"
          >
            <Workflow className="size-4 mr-1.5" />
            Workflow
          </Button>
        </div>
      </div>

      {/* Entity selection */}
      <div className="space-y-2">
        <Label>
          {value.type === 'pipeline'
            ? t('bots.selectPipeline')
            : t('bots.selectWorkflow')}
        </Label>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={open}
              className="w-full justify-between"
              disabled={disabled}
            >
              {getSelectionDisplay()}
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[400px] p-0" align="start">
            <ScrollArea className="h-[300px]">
              <div className="p-2 space-y-1">
                {value.type === 'pipeline' ? (
                  pipelines.length === 0 ? (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                      {t('bots.noPipelinesFound')}
                    </div>
                  ) : (
                    pipelines.map((pipeline) => (
                      <Button
                        key={pipeline.id}
                        variant="ghost"
                        className="w-full justify-start"
                        onClick={() => handleSelect(pipeline.id, 'pipeline')}
                      >
                        <Check
                          className={cn(
                            'mr-2 h-4 w-4',
                            value.id === pipeline.id
                              ? 'opacity-100'
                              : 'opacity-0',
                          )}
                        />
                        <div className="flex items-center gap-2 flex-1 text-left">
                          {pipeline.emoji && <span>{pipeline.emoji}</span>}
                          <span className="truncate">{pipeline.name}</span>
                        </div>
                        {pipeline.description && (
                          <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                            {pipeline.description}
                          </span>
                        )}
                      </Button>
                    ))
                  )
                ) : workflows.length === 0 ? (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    {t('bots.noWorkflowsFound')}
                  </div>
                ) : (
                  workflows.map((workflow) => (
                    <Button
                      key={workflow.id}
                      variant="ghost"
                      className="w-full justify-start"
                      onClick={() => handleSelect(workflow.id, 'workflow')}
                    >
                      <Check
                        className={cn(
                          'mr-2 h-4 w-4',
                          value.id === workflow.id
                            ? 'opacity-100'
                            : 'opacity-0',
                        )}
                      />
                      <div className="flex items-center gap-2 flex-1 text-left">
                        {workflow.emoji && <span>{workflow.emoji}</span>}
                        <span className="truncate">{workflow.name}</span>
                      </div>
                      {workflow.description && (
                        <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                          {workflow.description}
                        </span>
                      )}
                    </Button>
                  ))
                )}
              </div>
            </ScrollArea>
          </PopoverContent>
        </Popover>
      </div>

      {/* Helper text */}
      <p className="text-xs text-muted-foreground">
        {value.type === 'pipeline'
          ? t('bots.pipelineBindingHelp')
          : t('bots.workflowBindingHelp')}
      </p>
    </div>
  );
}
