'use client';

import { ColumnDef } from '@tanstack/react-table';
import { MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { TFunction } from 'i18next';

export type DocumentFile = {
  uuid: string;
  name: string;
  status: string;
};

export const columns = (
  onDelete: (id: string) => void,
  t: TFunction,
): ColumnDef<DocumentFile>[] => {
  return [
    {
      accessorKey: 'name',
      header: t('knowledge.documentsTab.name'),
    },
    {
      accessorKey: 'status',
      header: t('knowledge.documentsTab.status'),
      cell: ({ row }) => {
        const document = row.original;

        switch (document.status) {
          case 'processing':
            return (
              <Badge variant="secondary">
                {t('knowledge.documentsTab.processing')}
              </Badge>
            );
          case 'completed':
            return (
              <Badge variant="outline" className="bg-blue-500 text-white">
                {t('knowledge.documentsTab.completed')}
              </Badge>
            );
          case 'failed':
            return (
              <Badge variant="outline" className="bg-yellow-500 text-white">
                {t('knowledge.documentsTab.failed')}
              </Badge>
            );
          default:
            return (
              <Badge variant="outline" className="bg-gray-500 text-white">
                {document.status}
              </Badge>
            );
        }
      },
    },
    {
      id: 'actions',
      cell: ({ row }) => {
        const document = row.original;

        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <span className="sr-only">
                  {t('knowledge.documentsTab.actions')}
                </span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>
                {t('knowledge.documentsTab.actions')}
              </DropdownMenuLabel>

              <DropdownMenuItem onClick={() => onDelete(document.uuid)}>
                {t('knowledge.documentsTab.delete')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];
};
