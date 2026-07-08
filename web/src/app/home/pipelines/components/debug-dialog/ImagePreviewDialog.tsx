import React from 'react';
import { X } from 'lucide-react';

interface ImagePreviewDialogProps {
  open: boolean;
  imageUrl: string;
  onClose: () => void;
}

export default function ImagePreviewDialog({
  open,
  imageUrl,
  onClose,
}: ImagePreviewDialogProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-8 animate-in fade-in duration-200"
      onClick={onClose}
    >
      {/* 背景遮罩 */}
      <div className="absolute inset-0 bg-black/20 " />

      {/* 内容区域 */}
      <div className="relative z-10 flex flex-col items-center gap-2">
        {/* 关闭按钮 - 在图片上方 */}
        <button
          onClick={onClose}
          className="self-end w-9 h-9 rounded-full bg-white hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-100 shadow-lg transition-all hover:scale-105 flex items-center justify-center"
        >
          <X className="w-4 h-4" />
        </button>

        {/* 图片 */}
        <img
          src={imageUrl}
          alt="Preview"
          className="max-w-[50vw] max-h-[50vh] object-contain rounded-lg shadow-2xl bg-white"
          onClick={(e) => e.stopPropagation()}
        />
      </div>
    </div>
  );
}
