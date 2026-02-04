'use client';

import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectTrigger,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Tag as TagIcon } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { PluginTag } from '@/app/infra/http/CloudServiceClient';

interface TagsFilterProps {
  availableTags: PluginTag[];
  selectedTags: string[];
  onTagsChange: (tags: string[]) => void;
}

export function TagsFilter({
  availableTags,
  selectedTags,
  onTagsChange,
}: TagsFilterProps) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);

  const handleTagToggle = (tag: string) => {
    const newTags = selectedTags.includes(tag)
      ? selectedTags.filter((t) => t !== tag)
      : [...selectedTags, tag];
    onTagsChange(newTags);
  };

  const handleClearAll = () => {
    onTagsChange([]);
  };

  const extractI18nObject = (obj: { zh_Hans?: string; en_US?: string }) => {
    const lang = i18n.language || 'en_US';
    return obj[lang as keyof typeof obj] || obj.zh_Hans || obj.en_US || '';
  };

  return (
    <Select open={open} onOpenChange={setOpen}>
      <SelectTrigger className="w-[140px]">
        <div className="flex items-center gap-2 w-full">
          <TagIcon className="h-4 w-4 flex-shrink-0" />
          {selectedTags.length === 0 ? (
            <span className="text-muted-foreground truncate text-sm">
              {t('market.tags.filterByTags')}
            </span>
          ) : (
            <span className="text-sm truncate">
              {selectedTags.length} {t('market.tags.selected')}
            </span>
          )}
        </div>
      </SelectTrigger>
      <SelectContent className="w-[240px]">
        <SelectGroup>
          <div className="px-2 py-1.5 flex items-center justify-between border-b">
            <span className="text-sm font-medium">
              {t('market.tags.selectTags')}
            </span>
            {selectedTags.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearAll}
                className="h-auto p-0 text-xs hover:bg-transparent hover:text-destructive"
              >
                {t('market.tags.clearAll')}
              </Button>
            )}
          </div>

          {availableTags.length === 0 ? (
            <div className="px-2 py-6 text-center text-sm text-muted-foreground">
              {t('market.tags.noTags')}
            </div>
          ) : (
            <div className="max-h-[300px] overflow-y-auto">
              {availableTags.map((tag) => (
                <div
                  key={tag.tag}
                  className="flex items-center space-x-2 px-2 py-2 hover:bg-accent cursor-pointer"
                  onClick={(e) => {
                    e.preventDefault();
                    handleTagToggle(tag.tag);
                  }}
                >
                  <Checkbox
                    id={`tag-${tag.tag}`}
                    checked={selectedTags.includes(tag.tag)}
                    onClick={(e) => e.stopPropagation()}
                    onCheckedChange={() => handleTagToggle(tag.tag)}
                  />
                  <Label
                    htmlFor={`tag-${tag.tag}`}
                    className="text-sm font-normal cursor-pointer flex-1"
                    onClick={(e) => e.preventDefault()}
                  >
                    {extractI18nObject(tag.display_name)}
                  </Label>
                </div>
              ))}
            </div>
          )}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
