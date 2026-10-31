import { useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChevronDown,
  ChevronRight,
  Search,
  ShieldAlert,
  HelpCircle,
} from 'lucide-react';
import type {
  WorkspaceOperationItem,
  DomainMeta,
} from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

export interface WorkspaceOperationsPickerProps {
  operations: WorkspaceOperationItem[];
  domains?: DomainMeta[];
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
}

export default function WorkspaceOperationsPicker({
  operations,
  domains = [],
  value = [],
  onChange,
  disabled = false,
}: WorkspaceOperationsPickerProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState('');
  const [openDomains, setOpenDomains] = useState<Record<string, boolean>>({});

  const selectedSet = useMemo(() => new Set(value), [value]);

  // Map domain names to domain metadata
  const domainMetaMap = useMemo(() => {
    const map = new Map<string, DomainMeta>();
    for (const d of domains) {
      map.set(d.domain, d);
    }
    return map;
  }, [domains]);

  // Group operations by domain
  const groupedOperations = useMemo(() => {
    const groups = new Map<string, WorkspaceOperationItem[]>();
    for (const op of operations) {
      if (!groups.has(op.domain)) {
        groups.set(op.domain, []);
      }
      groups.get(op.domain)!.push(op);
    }
    return groups;
  }, [operations]);

  // Sorted domain list
  const domainList = useMemo(() => {
    return Array.from(groupedOperations.keys()).sort();
  }, [groupedOperations]);

  // Filtered operations based on search query
  const filteredDomainGroups = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return domainList.map((domain) => ({
        domain,
        operations: groupedOperations.get(domain) || [],
      }));
    }

    const result: Array<{
      domain: string;
      operations: WorkspaceOperationItem[];
    }> = [];

    for (const domain of domainList) {
      const ops = groupedOperations.get(domain) || [];
      const matchingOps = ops.filter((op) => {
        const idMatch = op.id.toLowerCase().includes(query);
        const zhLabelMatch = op.label?.zh_Hans?.toLowerCase().includes(query);
        const enLabelMatch = op.label?.en_US?.toLowerCase().includes(query);
        const summaryMatch = op.summary?.toLowerCase().includes(query);
        const domainMatch = domain.toLowerCase().includes(query);
        return (
          idMatch || zhLabelMatch || enLabelMatch || summaryMatch || domainMatch
        );
      });

      if (matchingOps.length > 0) {
        result.push({
          domain,
          operations: matchingOps,
        });
      }
    }

    return result;
  }, [domainList, groupedOperations, searchQuery]);

  const toggleDomainOpen = (domain: string) => {
    setOpenDomains((prev) => ({
      ...prev,
      [domain]: prev[domain] !== undefined ? !prev[domain] : false, // default is open (true)
    }));
  };

  const isDomainOpen = (domain: string) => {
    // If search active, always expand matching domains
    if (searchQuery.trim()) return true;
    return openDomains[domain] !== false; // defaults to true (open)
  };

  const handleToggleOperation = useCallback(
    (opId: string, checked: boolean) => {
      if (disabled) return;
      if (checked) {
        if (!selectedSet.has(opId)) {
          onChange([...value, opId]);
        }
      } else {
        onChange(value.filter((id) => id !== opId));
      }
    },
    [disabled, onChange, selectedSet, value],
  );

  const handleToggleDomainAll = useCallback(
    (domainOps: WorkspaceOperationItem[]) => {
      if (disabled) return;
      const grantableOps = domainOps.filter((op) => op.grantable);
      if (grantableOps.length === 0) return;

      const allGrantableSelected = grantableOps.every((op) =>
        selectedSet.has(op.id),
      );

      if (allGrantableSelected) {
        // Deselect all grantable ops in this domain
        const idsToRemove = new Set(grantableOps.map((op) => op.id));
        onChange(value.filter((id) => !idsToRemove.has(id)));
      } else {
        // Select all grantable ops in this domain
        const next = new Set(value);
        for (const op of grantableOps) {
          next.add(op.id);
        }
        onChange(Array.from(next));
      }
    },
    [disabled, onChange, selectedSet, value],
  );

  const getDomainLabel = (domain: string): string => {
    const meta = domainMetaMap.get(domain);
    if (meta?.label) {
      return (
        extractI18nObject(
          meta.label as unknown as Parameters<typeof extractI18nObject>[0],
        ) ||
        meta.label.zh_Hans ||
        meta.label.en_US ||
        domain
      );
    }
    return domain;
  };

  const renderRiskBadge = (risk: WorkspaceOperationItem['risk']) => {
    switch (risk) {
      case 'dangerous':
        return (
          <Badge
            variant="destructive"
            className="gap-1 px-1.5 py-0 text-[10px] font-semibold"
          >
            <ShieldAlert className="size-3" />
            {t('workspaceOperations.riskDangerous')}
          </Badge>
        );
      case 'write':
        return (
          <Badge
            variant="outline"
            className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400 px-1.5 py-0 text-[10px] font-semibold"
          >
            {t('workspaceOperations.riskWrite')}
          </Badge>
        );
      case 'read':
      default:
        return (
          <Badge
            variant="outline"
            className="border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400 px-1.5 py-0 text-[10px] font-semibold"
          >
            {t('workspaceOperations.riskRead')}
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Search Bar & Summary */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-sm flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('workspaceOperations.searchPlaceholder')}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>
            {t('workspaceOperations.selectedCount', {
              count: value.length,
            })}
          </span>
          <span>•</span>
          <span>
            {t('workspaceOperations.totalCount', {
              count: operations.length,
            })}
          </span>
        </div>
      </div>

      {/* Empty State */}
      {operations.length === 0 && (
        <div className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
          {t('workspaceOperations.noOperations')}
        </div>
      )}

      {operations.length > 0 && filteredDomainGroups.length === 0 && (
        <div className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
          {t('workspaceOperations.noSearchResults')}
        </div>
      )}

      {/* Domain Groups */}
      {filteredDomainGroups.length > 0 && (
        <div className="space-y-3">
          {filteredDomainGroups.map(({ domain, operations: domainOps }) => {
            const isOpen = isDomainOpen(domain);
            const grantableOps = domainOps.filter((op) => op.grantable);
            const selectedInDomain = domainOps.filter((op) =>
              selectedSet.has(op.id),
            );
            const allGrantableSelected =
              grantableOps.length > 0 &&
              grantableOps.every((op) => selectedSet.has(op.id));
            const someSelected =
              selectedInDomain.length > 0 && !allGrantableSelected;

            return (
              <Collapsible
                key={domain}
                open={isOpen}
                onOpenChange={() => toggleDomainOpen(domain)}
                className="rounded-lg border bg-card text-card-foreground shadow-sm"
              >
                {/* Domain Header */}
                <div className="flex items-center justify-between border-b bg-muted/40 px-3 py-2.5">
                  <CollapsibleTrigger asChild>
                    <button
                      type="button"
                      className="flex flex-1 items-center gap-2 text-left text-sm font-semibold hover:opacity-80 transition-opacity"
                    >
                      {isOpen ? (
                        <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                      )}
                      <span>{getDomainLabel(domain)}</span>
                      <span className="font-mono text-xs text-muted-foreground font-normal">
                        ({domain})
                      </span>
                      <Badge
                        variant="secondary"
                        className="ml-1 text-[11px] font-normal"
                      >
                        {selectedInDomain.length} / {domainOps.length}
                      </Badge>
                    </button>
                  </CollapsibleTrigger>

                  {/* Domain-level Select All */}
                  <div className="flex items-center gap-2 pl-3">
                    <label
                      className={cn(
                        'flex items-center gap-1.5 text-xs font-medium cursor-pointer select-none',
                        (disabled || grantableOps.length === 0) &&
                          'cursor-not-allowed opacity-50',
                      )}
                    >
                      <Checkbox
                        checked={
                          allGrantableSelected
                            ? true
                            : someSelected
                              ? 'indeterminate'
                              : false
                        }
                        disabled={disabled || grantableOps.length === 0}
                        onCheckedChange={() => handleToggleDomainAll(domainOps)}
                        aria-label={`${domain} ${t('workspaceOperations.selectAll')}`}
                      />
                      <span>{t('workspaceOperations.selectAll')}</span>
                    </label>
                  </div>
                </div>

                {/* Operations List in Domain */}
                <CollapsibleContent>
                  <div className="divide-y">
                    {domainOps.map((op) => {
                      const isChecked = selectedSet.has(op.id);
                      const isGrantable = op.grantable;
                      const hasBothLabels =
                        op.label?.zh_Hans &&
                        op.label?.en_US &&
                        op.label.zh_Hans !== op.label.en_US;

                      const content = (
                        <div
                          key={op.id}
                          className={cn(
                            'flex items-start gap-3 px-3 py-2.5 transition-colors',
                            !isGrantable && 'opacity-60 bg-muted/20',
                            isGrantable && 'hover:bg-muted/30',
                          )}
                        >
                          <Checkbox
                            id={`op-${op.id}`}
                            checked={isChecked}
                            disabled={disabled || !isGrantable}
                            onCheckedChange={(checked) =>
                              handleToggleOperation(op.id, checked === true)
                            }
                            className="mt-1"
                          />
                          <div className="flex-1 min-w-0">
                            <label
                              htmlFor={`op-${op.id}`}
                              className={cn(
                                'block font-medium text-sm leading-5',
                                isGrantable
                                  ? 'cursor-pointer'
                                  : 'cursor-not-allowed',
                              )}
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <span>
                                  {hasBothLabels
                                    ? `${op.label.zh_Hans} (${op.label.en_US})`
                                    : extractI18nObject(
                                        op.label as unknown as Parameters<
                                          typeof extractI18nObject
                                        >[0],
                                      ) ||
                                      op.label?.zh_Hans ||
                                      op.label?.en_US ||
                                      op.id}
                                </span>
                                {renderRiskBadge(op.risk)}
                              </div>
                            </label>
                            <div className="mt-0.5 font-mono text-xs text-muted-foreground">
                              {op.id}
                            </div>
                            {op.summary && (
                              <p className="mt-1 text-xs text-muted-foreground leading-normal">
                                {op.summary}
                              </p>
                            )}
                          </div>
                          {!isGrantable && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="inline-flex shrink-0 text-amber-600 dark:text-amber-400 mt-1 cursor-help">
                                  <HelpCircle className="size-4" />
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="left">
                                {t('workspaceOperations.requiresPermission', {
                                  permission: op.permission,
                                })}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      );

                      if (!isGrantable) {
                        return (
                          <Tooltip key={op.id}>
                            <TooltipTrigger asChild>
                              <div>{content}</div>
                            </TooltipTrigger>
                            <TooltipContent side="top">
                              {t('workspaceOperations.requiresPermission', {
                                permission: op.permission,
                              })}
                            </TooltipContent>
                          </Tooltip>
                        );
                      }

                      return content;
                    })}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            );
          })}
        </div>
      )}
    </div>
  );
}
