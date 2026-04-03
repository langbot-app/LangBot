

import { Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTranslation } from 'react-i18next';
import { ExtraArg } from '../types';

interface ExtraArgsEditorProps {
  args: ExtraArg[];
  onChange: (args: ExtraArg[]) => void;
  disabled?: boolean;
}

export default function ExtraArgsEditor({
  args,
  onChange,
  disabled = false,
}: ExtraArgsEditorProps) {
  const { t } = useTranslation();

  const handleAdd = () => {
    onChange([...args, { key: '', type: 'string', value: '' }]);
  };

  const handleRemove = (index: number) => {
    onChange(args.filter((_, i) => i !== index));
  };

  const handleUpdate = (
    index: number,
    field: keyof ExtraArg,
    value: string,
  ) => {
    const newArgs = [...args];
    newArgs[index] = { ...newArgs[index], [field]: value };
    onChange(newArgs);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>{t('models.extraParameters')}</Label>
        {!disabled && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={handleAdd}
          >
            <Plus className="h-3 w-3 mr-1" />
            {t('models.addParameter')}
          </Button>
        )}
      </div>
      {args.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('common.none')}</p>
      ) : (
        args.map((arg, index) => (
          <div key={index} className="flex gap-2 items-center">
            <Input
              placeholder={t('models.keyName')}
              value={arg.key}
              className="flex-1"
              disabled={disabled}
              onChange={(e) => handleUpdate(index, 'key', e.target.value)}
            />
            <Select
              value={arg.type}
              disabled={disabled}
              onValueChange={(value) => handleUpdate(index, 'type', value)}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="string">{t('models.string')}</SelectItem>
                <SelectItem value="number">{t('models.number')}</SelectItem>
                <SelectItem value="boolean">{t('models.boolean')}</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder={t('models.value')}
              value={arg.value}
              className="flex-1"
              disabled={disabled}
              onChange={(e) => handleUpdate(index, 'value', e.target.value)}
            />
            {!disabled && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 flex-shrink-0"
                onClick={() => handleRemove(index)}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        ))
      )}
    </div>
  );
}
