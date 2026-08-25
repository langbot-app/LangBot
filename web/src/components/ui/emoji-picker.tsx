import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

interface EmojiPickerProps {
  value?: string;
  onChange: (emoji: string) => void;
  disabled?: boolean;
  ariaLabel?: string;
}

// 扩展的emoji分类
const EMOJI_CATEGORIES = {
  common: [
    '⚙️',
    '📚',
    '🔗',
    '📁',
    '💡',
    '🎯',
    '✨',
    '🚀',
    '📝',
    '🔧',
    '⚡',
    '🔥',
    '💎',
    '🎨',
    '🎭',
  ],
  objects: [
    '📦',
    '📂',
    '📋',
    '📌',
    '🔖',
    '💼',
    '🗂️',
    '📮',
    '🗃️',
    '📊',
    '📈',
    '📉',
    '🗄️',
    '📇',
    '🗳️',
  ],
  symbols: [
    '🔴',
    '🟠',
    '🟡',
    '🟢',
    '🔵',
    '🟣',
    '⚪',
    '⚫',
    '🟤',
    '🔺',
    '🔻',
    '🔶',
    '🔷',
    '🔸',
    '🔹',
  ],
  nature: [
    '🌟',
    '⭐',
    '🌈',
    '💧',
    '🌍',
    '🌙',
    '☀️',
    '🌱',
    '🌲',
    '🌳',
    '🌴',
    '🌵',
    '🌾',
    '🍀',
    '🌻',
  ],
  faces: [
    '😀',
    '😊',
    '🤔',
    '😎',
    '🤖',
    '👾',
    '💬',
    '💭',
    '❤️',
    '⚠️',
    '✅',
    '❌',
    '🎉',
    '🎊',
    '🎈',
  ],
  tech: [
    '💻',
    '📱',
    '⌨️',
    '🖥️',
    '🖱️',
    '💾',
    '💿',
    '📀',
    '🔌',
    '🔋',
    '📡',
    '🛰️',
    '🖨️',
    '🖲️',
    '💽',
  ],
  science: [
    '🔬',
    '🔭',
    '⚗️',
    '🧪',
    '🧬',
    '🧫',
    '🩺',
    '💊',
    '💉',
    '🌡️',
    '🧲',
    '⚛️',
    '🧬',
    '🦠',
    '🧫',
  ],
  business: [
    '💼',
    '📊',
    '📈',
    '💰',
    '💵',
    '💴',
    '💶',
    '💷',
    '💳',
    '💸',
    '📉',
    '💹',
    '🏦',
    '🏢',
    '🏭',
  ],
};

const CATEGORY_LABELS: { [key: string]: string } = {
  common: '常用',
  objects: '物品',
  symbols: '符号',
  nature: '自然',
  faces: '表情',
  tech: '科技',
  science: '科学',
  business: '商业',
};

// 每个分类的代表性 emoji（用于分页按钮）
const CATEGORY_ICONS: { [key: string]: string } = {
  common: '⭐',
  objects: '📦',
  symbols: '🔴',
  nature: '🌟',
  faces: '😀',
  tech: '💻',
  science: '🔬',
  business: '💼',
};

export default function EmojiPicker({
  value,
  onChange,
  disabled,
  ariaLabel,
}: EmojiPickerProps) {
  const [open, setOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('common');

  const handleEmojiSelect = (emoji: string) => {
    onChange(emoji);
    setOpen(false);
  };

  const currentEmojis =
    EMOJI_CATEGORIES[activeCategory as keyof typeof EMOJI_CATEGORIES];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          className="w-16 h-16 text-3xl p-0 hover:bg-gray-100 dark:hover:bg-gray-800"
          type="button"
          aria-label={ariaLabel}
        >
          {value || '😀'}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-4" align="start">
        <div className="space-y-3">
          {/* 分类标题 */}
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {CATEGORY_LABELS[activeCategory]}
          </h3>

          {/* Emoji 网格 */}
          <div className="grid grid-cols-6 gap-1">
            {currentEmojis.map((emoji, index) => (
              <button
                key={`${activeCategory}-${index}`}
                type="button"
                onClick={() => handleEmojiSelect(emoji)}
                className={`w-10 h-10 text-xl rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center justify-center ${
                  value === emoji ? 'bg-gray-200 dark:bg-gray-700' : ''
                }`}
              >
                {emoji}
              </button>
            ))}
          </div>

          {/* 分类切换按钮 */}
          <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
            <div className="flex justify-center gap-1">
              {Object.keys(EMOJI_CATEGORIES).map((category) => (
                <button
                  key={category}
                  type="button"
                  onClick={() => setActiveCategory(category)}
                  className={`w-7 h-7 text-base rounded transition-colors flex items-center justify-center ${
                    activeCategory === category
                      ? 'bg-gray-200 dark:bg-gray-700'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                  title={CATEGORY_LABELS[category]}
                >
                  {CATEGORY_ICONS[category]}
                </button>
              ))}
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
