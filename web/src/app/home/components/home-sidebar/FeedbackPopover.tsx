import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, ImagePlus, Loader2, Paperclip, Send, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { httpClient } from '@/app/infra/http/HttpClient';

const MAX_ATTACHMENTS = 3;
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

type FeedbackAttachment = {
  name: string;
  mime_type: string;
  data_url: string;
};

function bytesFromDataUrl(dataUrl: string): number {
  const payload = dataUrl.split(',')[1] || '';
  return Math.ceil((payload.length * 3) / 4);
}

function readImageFile(file: File): Promise<FeedbackAttachment> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      reject(new Error('not_image'));
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      reject(new Error('too_large'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result || '');
      if (!dataUrl.startsWith('data:image/')) {
        reject(new Error('not_image'));
        return;
      }
      resolve({
        name: file.name || 'pasted-image.png',
        mime_type: file.type || 'image/png',
        data_url: dataUrl,
      });
    };
    reader.onerror = () => reject(reader.error || new Error('read_failed'));
    reader.readAsDataURL(file);
  });
}

async function captureScreen(): Promise<FeedbackAttachment> {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error('unsupported');
  }
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: false,
  });
  try {
    const video = document.createElement('video');
    video.srcObject = stream;
    await video.play();
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('canvas_unavailable');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/png');
    if (bytesFromDataUrl(dataUrl) > MAX_IMAGE_BYTES) {
      throw new Error('too_large');
    }
    return {
      name: `screenshot-${Date.now()}.png`,
      mime_type: 'image/png',
      data_url: dataUrl,
    };
  } finally {
    stream.getTracks().forEach((track) => track.stop());
  }
}

export function FeedbackPopoverContent({
  onSubmitted,
}: {
  onSubmitted?: () => void;
}) {
  const { t } = useTranslation();
  const [content, setContent] = useState('');
  const [attachments, setAttachments] = useState<FeedbackAttachment[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    async (files: File[]) => {
      const slots = MAX_ATTACHMENTS - attachments.length;
      if (slots <= 0) {
        toast.error(t('feedback.tooManyImages'));
        return;
      }
      const picked = files.slice(0, slots);
      const next: FeedbackAttachment[] = [];
      for (const file of picked) {
        try {
          next.push(await readImageFile(file));
        } catch (error) {
          const msg = error instanceof Error ? error.message : '';
          toast.error(
            msg === 'too_large'
              ? t('feedback.imageTooLarge')
              : t('feedback.imageOnly'),
          );
        }
      }
      if (next.length > 0) {
        setAttachments((prev) => [...prev, ...next].slice(0, MAX_ATTACHMENTS));
      }
    },
    [attachments.length, t],
  );

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files || []).filter((file) =>
        file.type.startsWith('image/'),
      );
      if (files.length > 0) {
        event.preventDefault();
        void addFiles(files);
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [addFiles]);

  const handleCapture = async () => {
    try {
      if (attachments.length >= MAX_ATTACHMENTS) {
        toast.error(t('feedback.tooManyImages'));
        return;
      }
      setCapturing(true);
      const screenshot = await captureScreen();
      setAttachments((prev) => [...prev, screenshot].slice(0, MAX_ATTACHMENTS));
    } catch (error) {
      const msg = error instanceof Error ? error.message : '';
      toast.error(
        msg === 'too_large'
          ? t('feedback.imageTooLarge')
          : t('feedback.screenshotFailed'),
      );
    } finally {
      setCapturing(false);
    }
  };

  const handleSubmit = async () => {
    const trimmed = content.trim();
    if (!trimmed) {
      toast.error(t('feedback.contentRequired'));
      return;
    }
    try {
      setSubmitting(true);
      await httpClient.submitFeedback({
        content: trimmed,
        attachments,
        page_url: window.location.href,
        user_agent: navigator.userAgent,
      });
      toast.success(t('feedback.submitSuccess'));
      setContent('');
      setAttachments([]);
      onSubmitted?.();
    } catch {
      toast.error(t('feedback.submitFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-80 space-y-3 p-1" onClick={(e) => e.stopPropagation()}>
      <div>
        <div className="text-sm font-medium">{t('feedback.title')}</div>
        <p className="mt-1 text-xs text-muted-foreground">
          {t('feedback.description')}
        </p>
      </div>
      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={t('feedback.placeholder')}
        maxLength={5000}
        className="min-h-28 resize-none text-sm"
      />
      <div className="flex flex-wrap gap-2">
        {attachments.map((item, index) => (
          <div key={`${item.name}-${index}`} className="relative size-16 overflow-hidden rounded-md border">
            <img src={item.data_url} alt={item.name} className="h-full w-full object-cover" />
            <button
              type="button"
              onClick={() => setAttachments((prev) => prev.filter((_, i) => i !== index))}
              className="absolute right-1 top-1 rounded-full bg-black/60 p-0.5 text-white"
              aria-label={t('feedback.removeImage')}
            >
              <X className="size-3" />
            </button>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => {
              void addFiles(Array.from(e.target.files || []));
              e.target.value = '';
            }}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
          >
            <ImagePlus className="mr-1 size-4" />
            {t('feedback.attachImage')}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleCapture}
            disabled={capturing}
          >
            {capturing ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Camera className="mr-1 size-4" />}
            {t('feedback.screenshot')}
          </Button>
        </div>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Paperclip className="size-3" />
          {attachments.length}/{MAX_ATTACHMENTS}
        </span>
      </div>
      <Button className="w-full" onClick={handleSubmit} disabled={submitting}>
        {submitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Send className="mr-2 size-4" />}
        {t('feedback.submit')}
      </Button>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t('feedback.privacyHint')}
      </p>
    </div>
  );
}
