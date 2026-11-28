"use client";

import { SearchDialog, SearchDialogClose, SearchDialogContent, SearchDialogHeader, SearchDialogIcon, SearchDialogInput, SearchDialogList, SearchDialogOverlay } from "fumadocs-ui/components/dialog/search";
import { useDocsSearch } from "fumadocs-core/search/client";
import { flexsearchStaticClient } from "fumadocs-core/search/client/flexsearch-static";
import { useI18n } from "fumadocs-ui/contexts/i18n";
import type { DefaultSearchDialogProps } from "fumadocs-ui/components/dialog/search-default";

export function LocaleSearchDialog({ open, onOpenChange, dialogHandle }: DefaultSearchDialogProps) {
  const { locale } = useI18n();
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL.slice(0, -1)
    : import.meta.env.BASE_URL;
  const { search, setSearch, query } = useDocsSearch({
    client: flexsearchStaticClient({ locale, from: `${base}/api/search/${locale}.json` }),
  });

  return (
    <SearchDialog open={open} onOpenChange={onOpenChange} dialogHandle={dialogHandle} search={search} onSearchChange={setSearch} isLoading={query.isLoading}>
      <SearchDialogOverlay />
      <SearchDialogContent>
        <SearchDialogHeader>
          <SearchDialogIcon />
          <SearchDialogInput />
          <SearchDialogClose />
        </SearchDialogHeader>
        <SearchDialogList items={query.data !== "empty" ? query.data : null} />
      </SearchDialogContent>
    </SearchDialog>
  );
}
