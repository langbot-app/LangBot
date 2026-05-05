import { useCallback, useMemo, useState } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import {
  Search,
  Settings,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Layers,
  Cpu,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  NODE_ICONS,
  NODE_TYPE_I18N_KEYS,
  CATEGORY_I18N_KEYS,
  PALETTE_CATEGORY_COLORS as categoryColors,
  PALETTE_CATEGORY_BG as categoryBgColors,
  PALETTE_CATEGORY_BORDER as categoryBorderColors,
  CATEGORY_ICONS as categoryIcons,
  findNodeI18nKeys,
} from './workflow-constants';
import { resolveI18nLabel } from './workflow-i18n';

// Use shared icon mapping
const nodeIcons = NODE_ICONS;

// Use shared i18n key mapping
const nodeTypeI18nKeys = NODE_TYPE_I18N_KEYS;

// Use shared category i18n keys
const categoryI18nKeys = CATEGORY_I18N_KEYS;

// Common node type definition for UI purposes
interface NodeTypeForUI {
  type: string;
  category: string;
  labelKey?: string;
  descriptionKey?: string;
  // Also support raw label dict from backend
  label?: Record<string, string>;
  description?: Record<string, string>;
}

// Default node types generated from shared constants
const defaultNodeTypes: NodeTypeForUI[] = Object.entries(NODE_TYPE_I18N_KEYS).map(([type, keys]) => ({
  type,
  category: type.split('.')[0],
  labelKey: keys.labelKey,
  descriptionKey: keys.descriptionKey,
}));

export default function NodePalette() {
  const { t, i18n } = useTranslation();
  const { nodeTypes: backendNodeTypes, nodeCategories } = useWorkflowStore();
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  
  // Expanded categories state
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['trigger', 'process', 'control', 'action', 'integration'])
  );

  // Helper: get label string for a node using i18n
  const getNodeLabel = useCallback((node: NodeTypeForUI): string => {
    if (node.labelKey) {
      return t(node.labelKey, { defaultValue: node.labelKey });
    }
    if (node.label) {
      const labelValue = resolveI18nLabel(node.label);
      return labelValue || node.type;
    }
    return node.type;
  }, [t]);

  // Helper: get description string for a node using i18n
  const getNodeDescription = useCallback((node: NodeTypeForUI): string => {
    if (node.descriptionKey) {
      return t(node.descriptionKey, { defaultValue: '' });
    }
    if (node.description) {
      const descValue = resolveI18nLabel(node.description);
      return descValue || '';
    }
    return '';
  }, [t]);

  // Use backend node types if available, otherwise use defaults
  const nodeTypes = useMemo((): NodeTypeForUI[] => {
    if (backendNodeTypes && backendNodeTypes.length > 0) {
      return backendNodeTypes.map((node) => {
        const i18nKeys = findNodeI18nKeys(node.type);
        
        return {
          type: node.type,
          category: node.category,
          labelKey: i18nKeys?.labelKey,
          descriptionKey: i18nKeys?.descriptionKey,
          // Keep raw label dict as fallback for unknown nodes
          label: i18nKeys ? undefined : node.label,
          description: i18nKeys ? undefined : node.description,
        };
      });
    }
    return defaultNodeTypes;
  }, [backendNodeTypes]);

  // Filter nodes based on search query
  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) {
      return nodeTypes;
    }
    const query = searchQuery.toLowerCase();
    return nodeTypes.filter((node) => {
      const label = getNodeLabel(node);
      const description = getNodeDescription(node);
      return (
        label.toLowerCase().includes(query) ||
        description.toLowerCase().includes(query) ||
        node.type.toLowerCase().includes(query)
      );
    });
  }, [nodeTypes, searchQuery, getNodeLabel, getNodeDescription]);

  // Group filtered nodes by category
  const groupedNodes = useMemo(() => {
    const groups: Record<string, typeof nodeTypes> = {};
    const categoryOrder = ['trigger', 'process', 'control', 'action', 'integration'];
    
    // Initialize groups in order
    categoryOrder.forEach((cat) => {
      groups[cat] = [];
    });
    
    for (const node of filteredNodes) {
      const category = node.category || node.type.split('.')[0];
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(node);
    }
    
    // Remove empty categories
    Object.keys(groups).forEach((key) => {
      if (groups[key].length === 0) {
        delete groups[key];
      }
    });
    
    return groups;
  }, [filteredNodes]);

  // Toggle category expansion
  const toggleCategory = useCallback((category: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }, []);

  // Handle drag start
  const onDragStart = useCallback(
    (event: React.DragEvent<HTMLDivElement>, nodeType: string) => {
      event.dataTransfer.setData('application/reactflow', nodeType);
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', nodeType);
    },
    []
  );

  // Get category label using i18n
  const getCategoryLabel = useCallback(
    (categoryName: string) => {
      const i18nKey = categoryI18nKeys[categoryName];
      if (i18nKey) {
        return t(i18nKey.labelKey, { defaultValue: categoryName });
      }
      // Fallback to backend category label dict
      const category = nodeCategories?.find((c) => c.name === categoryName);
      if (category?.label) {
        const lang = i18n.language;
        if (lang.startsWith('zh')) {
          return category.label['zh-CN'] || category.label['zh-Hans'] || category.label['en'] || categoryName;
        }
        return category.label['en'] || category.label['en-US'] || categoryName;
      }
      return categoryName;
    },
    [nodeCategories, t, i18n.language]
  );

  // Clear search
  const clearSearch = useCallback(() => {
    setSearchQuery('');
  }, []);

  return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="p-3 border-b">
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <Layers className="size-4" />
            {t('workflows.nodePalette')}
          </h3>
          
          {/* Search input */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder={t('workflows.searchNodes')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-8 h-8 text-sm"
            />
            {searchQuery && (
              <button
                onClick={clearSearch}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                ×
              </button>
            )}
          </div>
        </div>
        
        {/* Node list */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="p-2 space-y-1">
            {/* Show loading state if no nodes */}
            {Object.keys(groupedNodes).length === 0 && !searchQuery && (
              <div className="text-sm text-muted-foreground text-center py-8">
                <Cpu className="size-8 mx-auto mb-2 opacity-50" />
                <p>{t('workflows.loadingNodeTypes')}</p>
              </div>
            )}
            
            {/* Show no results message */}
            {Object.keys(groupedNodes).length === 0 && searchQuery && (
              <div className="text-sm text-muted-foreground text-center py-8">
                <Search className="size-8 mx-auto mb-2 opacity-50" />
                <p>{t('workflows.noNodesFound')}</p>
                <button
                  onClick={clearSearch}
                  className="text-primary hover:underline mt-2"
                >
                  {t('workflows.clearSearch')}
                </button>
              </div>
            )}
            
            {/* Category groups */}
            {Object.entries(groupedNodes).map(([category, nodes]) => {
              const isExpanded = expandedCategories.has(category);
              const CategoryIcon = categoryIcons[category] || Settings;
              const ChevronIcon = isExpanded ? ChevronDown : ChevronRight;

              return (
                <div key={category} className="mb-1">
                  {/* Category header */}
                  <button
                    onClick={() => toggleCategory(category)}
                    className={cn(
                      'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm font-medium transition-colors',
                      categoryBgColors[category],
                      categoryColors[category]
                    )}
                  >
                    <ChevronIcon className="size-4 flex-shrink-0" />
                    <CategoryIcon className="size-4 flex-shrink-0" />
                    <span className="flex-1 text-left">{getCategoryLabel(category)}</span>
                    <Badge variant="secondary" className="text-xs px-1.5 py-0">
                      {nodes.length}
                    </Badge>
                  </button>

                  {/* Node list */}
                  {isExpanded && (
                    <div className="mt-1 space-y-0.5 ml-2">
                      {nodes.map((node) => {
                        const Icon = nodeIcons[node.type] || Settings;
                        const label = getNodeLabel(node);
                        const description = getNodeDescription(node);

                        return (
                          <div
                            key={node.type}
                            draggable
                            onDragStart={(e) => onDragStart(e, node.type)}
                            className={cn(
                              'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-grab select-none',
                              'hover:bg-muted/80 active:cursor-grabbing transition-colors',
                              'border border-transparent hover:border-border',
                              'group'
                            )}
                            title={description || label}
                          >
                            <div className={cn(
                              'p-1 rounded',
                              categoryBgColors[category],
                              categoryBorderColors[category],
                              'border'
                            )}>
                              <Icon className={cn('size-3.5', categoryColors[category])} />
                            </div>
                            <span className="text-sm truncate flex-1">{label}</span>
                            <ExternalLink className="size-3 opacity-0 group-hover:opacity-50 transition-opacity" />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        
        {/* Footer hint */}
        <div className="p-2 border-t text-xs text-muted-foreground text-center">
          {t('workflows.dragToAdd')}
        </div>
      </div>
  );
}
