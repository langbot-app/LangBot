import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface PromptEntry {
  role: string;
  content: string;
}

interface PromptEditorProps {
  value: PromptEntry[];
  onChange: (value: PromptEntry[]) => void;
}

const ROLE_OPTIONS = [
  { value: 'system', label: 'System' },
  { value: 'user', label: 'User' },
  { value: 'assistant', label: 'Assistant' },
];

export default function PromptEditorComponent({
  value,
  onChange,
}: PromptEditorProps) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<PromptEntry[]>(
    Array.isArray(value) && value.length > 0
      ? value
      : [{ role: 'system', content: '' }],
  );

  // Sync with external value changes
  useEffect(() => {
    if (Array.isArray(value) && value.length > 0) {
      setEntries(value);
    }
  }, [value]);

  const updateEntries = (newEntries: PromptEntry[]) => {
    setEntries(newEntries);
    onChange(newEntries);
  };

  const handleRoleChange = (index: number, role: string) => {
    const newEntries = [...entries];
    newEntries[index] = { ...newEntries[index], role };
    updateEntries(newEntries);
  };

  const handleContentChange = (index: number, content: string) => {
    const newEntries = [...entries];
    newEntries[index] = { ...newEntries[index], content };
    updateEntries(newEntries);
  };

  const handleAddEntry = () => {
    updateEntries([...entries, { role: 'system', content: '' }]);
  };

  const handleRemoveEntry = (index: number) => {
    if (entries.length <= 1) return;
    const newEntries = entries.filter((_, i) => i !== index);
    updateEntries(newEntries);
  };

  return (
    <div className="space-y-3 w-full">
      {entries.map((entry, index) => (
        <div
          key={index}
          className="flex gap-2 items-start p-3 rounded-lg border bg-card"
        >
          <div className="w-32 flex-shrink-0">
            <Select
              value={entry.role}
              onValueChange={(role) => handleRoleChange(index, role)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1">
            <Textarea
              value={entry.content}
              onChange={(e) => handleContentChange(index, e.target.value)}
              placeholder={t('workflows.promptContentPlaceholder', 'Enter prompt content...')}
              className="min-h-[80px] resize-y"
              rows={3}
            />
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0 text-muted-foreground hover:text-destructive mt-1"
            onClick={() => handleRemoveEntry(index)}
            disabled={entries.length <= 1}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        className="w-full border-dashed text-muted-foreground hover:text-foreground"
        onClick={handleAddEntry}
      >
        <Plus className="size-4 mr-1.5" />
        {t('workflows.addPromptEntry', 'Add Prompt Entry')}
      </Button>
    </div>
  );
}
