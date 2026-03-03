'use client';

import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import rehypeHighlight from 'rehype-highlight';
import i18n from 'i18next';
import { ExternalLink } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import '@/styles/github-markdown.css';
import { GitHubRelease } from '@/app/infra/http/CloudServiceClient';

interface NewVersionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  release: GitHubRelease | null;
}

export default function NewVersionDialog({
  open,
  onOpenChange,
  release,
}: NewVersionDialogProps) {
  const { t } = useTranslation();

  const getUpdateDocsUrl = () => {
    const language = i18n.language;
    if (language === 'zh-Hans' || language === 'zh-Hant') {
      return 'https://docs.langbot.app/zh/deploy/update.html';
    } else if (language === 'ja-JP') {
      return 'https://docs.langbot.app/ja/deploy/update.html';
    } else {
      return 'https://docs.langbot.app/en/deploy/update.html';
    }
  };

  const handleViewUpdateGuide = () => {
    window.open(getUpdateDocsUrl(), '_blank');
  };

  if (!release) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            {t('version.newVersionAvailable')}
            <span className="text-primary font-mono">{release.tag_name}</span>
          </DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto min-h-0 pr-2">
          <div className="markdown-body max-w-none text-sm">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw, rehypeSanitize, rehypeHighlight]}
              components={{
                ul: ({ children }) => <ul className="list-disc">{children}</ul>,
                ol: ({ children }) => (
                  <ol className="list-decimal">{children}</ol>
                ),
                li: ({ children }) => <li className="ml-4">{children}</li>,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {release.body || t('version.noReleaseNotes')}
            </ReactMarkdown>
          </div>
        </div>
        <DialogFooter className="flex-shrink-0 flex flex-col sm:flex-row gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="w-full sm:w-auto"
          >
            {t('common.close')}
          </Button>
          <Button
            onClick={handleViewUpdateGuide}
            className="w-full sm:w-auto flex items-center gap-2"
          >
            {t('version.viewUpdateGuide')}
            <ExternalLink className="w-4 h-4" />
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
