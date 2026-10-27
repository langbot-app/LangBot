import { defineMintlifyI18n, mintlifyPlugin, readMintlifyDocs } from "@fumapress/mintlify";
import { defineConfig } from "fumapress";
import type { Folder, Node as PageTreeNode, Root, Separator } from "fumadocs-core/page-tree";
import { fumadocsMdx } from "fumapress/adapters/mdx";
import { flexsearchPlugin } from "fumapress/plugins/flexsearch";
import { openapiPlugin } from "fumapress/plugins/openapi";
import { robotsPlugin } from "fumapress/plugins/robots";
import { update } from "fumadocs-core/source";
import { uiTranslations } from "fumadocs-ui/i18n";
import { defineDocs } from "fumadocs-mdx/macro";
import { createOpenAPI, type OpenAPIServer } from "fumadocs-openapi/server";
import { Blocks, Bot, Cloud, ExternalLink, Map as MapIcon, Newspaper } from "lucide-react";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { LocalePreferenceProvider } from "./src/locale-preference-provider";

const SITE_URL = "https://langbot.app/docs";
const LOCALES = ["en", "zh", "ja"] as const;
const MINTLIFY_LOCALE = { en: "en", zh: "cn", ja: "jp" } as const;
const HREFLANG = { en: "en", zh: "zh-CN", ja: "ja" } as const;
const mintlifyDocs = readMintlifyDocs();

function nodeName(node: PageTreeNode) {
  return typeof node.name === "string" ? node.name : "";
}

function renderNavigationIcon(icon: PageTreeNode["icon"]) {
  if (icon === "robot") {
    return <Bot aria-hidden="true" className="size-4 shrink-0" />;
  }
  if (typeof icon !== "string" || !icon.startsWith("/")) return icon;
  return (
    <img
      src={icon}
      alt=""
      aria-hidden="true"
      className="size-4 shrink-0 object-contain"
    />
  );
}

function renderNavigationIcons(node: PageTreeNode): PageTreeNode {
  if (node.type === "folder") {
    return {
      ...node,
      icon: renderNavigationIcon(node.icon),
      index: node.index
        ? { ...node.index, icon: renderNavigationIcon(node.index.icon) }
        : undefined,
      children: node.children.map(renderNavigationIcons),
    };
  }
  return { ...node, icon: renderNavigationIcon(node.icon) };
}


type ConfiguredNavigationGroup = {
  group: string;
  icon?: string;
  pages?: unknown[];
};

function restoreConfiguredFolderIcons(
  nodes: PageTreeNode[],
  configuredPages: unknown[],
): PageTreeNode[] {
  const configuredGroups = new Map<string, ConfiguredNavigationGroup>();
  for (const entry of configuredPages) {
    if (!entry || typeof entry !== "object" || !("group" in entry)) continue;
    const group = entry as ConfiguredNavigationGroup;
    configuredGroups.set(group.group, group);
  }
  return nodes.map((node) => {
    if (node.type !== "folder") return node;
    const configured = configuredGroups.get(nodeName(node));
    if (!configured) return node;
    return {
      ...node,
      icon: configured.icon ?? node.icon,
      children: restoreConfiguredFolderIcons(node.children, configured.pages ?? []),
    };
  });
}

const openApiTagOrder = Object.fromEntries(LOCALES.map((locale) => {
  const spec = JSON.parse(readFileSync(`openapi/service-api-${locale}.json`, "utf8"));
  const tags: string[] = [];
  for (const pathItem of Object.values(spec.paths ?? {}) as Record<string, any>[]) {
    for (const operation of Object.values(pathItem)) {
      if (!operation || typeof operation !== "object") continue;
      for (const tag of operation.tags ?? []) if (!tags.includes(tag)) tags.push(tag);
    }
  }
  return [locale, tags];
})) as Record<(typeof LOCALES)[number], string[]>;

function generatedOpenApiGroups(tree: Root, locale: (typeof LOCALES)[number]) {
  const apiRoot = tree.children.find(
    (node) => node.type === "folder" && node.$ref?.folder === "api-reference",
  );
  if (!apiRoot || apiRoot.type !== "folder") return [];
  const order = openApiTagOrder[locale];
  const rank = (name: string) => order.findIndex((tag) => tag.toLocaleLowerCase() === name.toLocaleLowerCase());
  return [...apiRoot.children]
    .sort((left, right) => {
      const leftIndex = rank(nodeName(left));
      const rightIndex = rank(nodeName(right));
      return (leftIndex < 0 ? Number.MAX_SAFE_INTEGER : leftIndex)
        - (rightIndex < 0 ? Number.MAX_SAFE_INTEGER : rightIndex);
    })
    .map((node) => {
      const index = rank(nodeName(node));
      return index >= 0 ? { ...node, name: order[index] } : node;
    });
}

function sectionizeMintlifyTree(
  tree: Root,
  sourceTree: Root,
  locale: (typeof LOCALES)[number],
): Root {
  const language = mintlifyDocs.navigation.languages?.find(
    (entry) => entry.language === MINTLIFY_LOCALE[locale],
  );
  const generatedApiGroups = generatedOpenApiGroups(sourceTree, locale);
  return {
    ...tree,
    children: tree.children.map((node): PageTreeNode => {
      if (node.type !== "folder") return node;
      const configuredTab = language?.tabs?.find((tab) => tab.tab === nodeName(node));
      const sourceGroups = new Map(
        node.children
          .filter((child): child is Folder => child.type === "folder")
          .map((child) => [nodeName(child), child]),
      );
      const children: PageTreeNode[] = [];
      for (const group of configuredTab?.groups ?? []) {
        if (group.hidden) continue;
        const separator: Separator = {
          $id: `${node.$id}:${group.group}:section`,
          type: "separator",
          name: group.group,
        };
        children.push(separator);
        if ("openapi" in group && group.openapi) {
          children.push(...generatedApiGroups);
          continue;
        }
        const sourceGroup = sourceGroups.get(group.group);
        if (!sourceGroup) continue;
        if (sourceGroup.index) children.push(sourceGroup.index);
        children.push(...restoreConfiguredFolderIcons(
          sourceGroup.children,
          "pages" in group ? group.pages ?? [] : [],
        ));
      }
      const tab: Folder = { ...node, root: true, children };
      return tab;
    }),
  };
}

const i18n = defineMintlifyI18n(mintlifyDocs, {
  localeMap: { en: "en", cn: "zh", jp: "ja" },
});
const translations = i18n.translations()
  .extend(uiTranslations())
  .add({
    en: { displayName: "English" },
    zh: { displayName: "简体中文" },
    ja: { displayName: "日本語" },
  });
// Fumapress stores translations.config as its runtime i18n config. Preserve
// the Mintlify adapter's locale bridge there so navigation.languages selects
// the matching English, Chinese, or Japanese tree instead of always using en.
Object.assign(translations.config, {
  _getMintlifyLanguage: (i18n as typeof i18n & {
    _getMintlifyLanguage?: (locale: string) => string | undefined;
  })._getMintlifyLanguage,
});
// Locale-only files must not inherit the English storage and create indexed
// pages in locales where no canonical source translation exists.
i18n.fallbackLanguage = null;
translations.config.fallbackLanguage = null;

function collectRouteLocales() {
  const routes = new Map<string, Set<string>>();
  function visit(directory: string, prefix: string, locale: string) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const relative = path.posix.join(prefix, entry.name);
      if (entry.isDirectory()) visit(path.join(directory, entry.name), relative, locale);
      else if (entry.isFile() && entry.name.endsWith(".mdx")) {
        let route = relative.slice(0, -4);
        if (route === "index") route = "";
        else if (route.endsWith("/index")) route = route.slice(0, -6);
        const available = routes.get(route) ?? new Set<string>();
        available.add(locale);
        routes.set(route, available);
      }
    }
  }
  for (const locale of LOCALES) visit(path.resolve(locale), "", locale);
  return routes;
}

const routeLocales = collectRouteLocales();

function GithubMark(props: import("react").ComponentProps<"svg">) {
  return <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.02c-3.22.7-3.9-1.37-3.9-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.16.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.74-1.55-2.57-.29-5.27-1.28-5.27-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.47.11-3.05 0 0 .97-.31 3.16 1.18a10.96 10.96 0 0 1 5.75 0c2.2-1.49 3.16-1.18 3.16-1.18.63 1.58.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.07.79 2.16v3.2c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z" />
  </svg>;
}

const QUICK_LINK_ICONS = {
  blocks: Blocks,
  cloud: Cloud,
  github: GithubMark,
  map: MapIcon,
  newspaper: Newspaper,
} as const;

type QuickLinkIcon = keyof typeof QUICK_LINK_ICONS;
type ConfiguredNavbarLink = {
  href: string;
  icon?: QuickLinkIcon;
  label?: string;
};
type ConfiguredNavbar = {
  links?: ConfiguredNavbarLink[];
  primary?: ConfiguredNavbarLink & { type?: string };
};

function quickLinkIcon(name: QuickLinkIcon | undefined) {
  if (!name) return undefined;
  const Icon = QUICK_LINK_ICONS[name];
  return <Icon aria-hidden="true" className="size-4 shrink-0" />;
}

function quickLinkText(text: string) {
  return <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
    <span>{text}</span>
    <ExternalLink aria-hidden="true" className="size-3 shrink-0 text-fd-muted-foreground" />
  </span>;
}

function localizedNavbar(lang: string | undefined) {
  const locale = LOCALES.includes(lang as (typeof LOCALES)[number]) ? lang as (typeof LOCALES)[number] : "en";
  const language = mintlifyDocs.navigation.languages?.find(
    (entry) => entry.language === MINTLIFY_LOCALE[locale],
  );
  const navbar = (language?.navbar ?? mintlifyDocs.navbar) as ConfiguredNavbar | undefined;
  const linkItem = (link: ConfiguredNavbarLink) => ({
    text: quickLinkText(link.label ?? link.href),
    url: link.href,
    icon: quickLinkIcon(link.icon),
    external: true,
  });
  return [
    ...(navbar?.links ?? []).map(linkItem),
    ...(navbar?.primary ? [{ ...linkItem(navbar.primary), type: "button" as const }] : []),
  ];
}

function docsBrand() {
  return <span className="inline-flex items-center gap-2">
    <img
      src="/langbot-logo.png"
      alt=""
      aria-hidden="true"
      className="size-6 shrink-0 rounded-md object-contain"
    />
    <span>LangBot Docs</span>
  </span>;
}
const enOpenAPI = createOpenAPI({ input: ["openapi/service-api-en.json"] });
const zhOpenAPI = createOpenAPI({ input: ["openapi/service-api-zh.json"] });
const jaOpenAPI = createOpenAPI({ input: ["openapi/service-api-ja.json"] });

function legacyOpenApiSlug(value: string) {
  return value.replace(/\s+/g, "-").toLowerCase();
}

const legacyOpenApiLayout = {
  groupBy: "tag" as const,
  name: (entry: { info: { title: string } }) => legacyOpenApiSlug(entry.info.title),
};

function encodeRoute(route: string) {
  return route.split("/").map((segment) => encodeURIComponent(segment)).join("/");
}

const openApiAlternates = new Map<string, Partial<Record<(typeof LOCALES)[number], string>>>();
for (const locale of LOCALES) {
  const spec = JSON.parse(readFileSync(`openapi/service-api-${locale}.json`, "utf8"));
  for (const [apiPath, pathItem] of Object.entries(spec.paths ?? {}) as [string, Record<string, any>][]) {
    for (const [method, operation] of Object.entries(pathItem)) {
      if (!/^(?:get|post|put|patch|delete|head|options)$/i.test(method) || !operation?.summary) continue;
      const tag = operation.tags?.[0] ?? "unknown";
      const route = encodeRoute(`api-reference/${legacyOpenApiSlug(tag)}/${legacyOpenApiSlug(operation.summary)}`);
      const key = `${method.toLowerCase()} ${apiPath}`;
      const alternates = openApiAlternates.get(key) ?? {};
      alternates[locale] = route;
      openApiAlternates.set(key, alternates);
    }
  }
}
const openApiAlternatesByRoute = new Map<string, Partial<Record<(typeof LOCALES)[number], string>>>();
for (const alternates of openApiAlternates.values()) {
  for (const locale of LOCALES) {
    const route = alternates[locale];
    if (route) openApiAlternatesByRoute.set(`${locale}:${route}`, alternates);
  }
}

function localizeOpenAPISource(
  source: Awaited<ReturnType<OpenAPIServer["staticSource"]>>,
  locale: string,
) {
  return update(source)
    .page((page) => ({
      ...page,
      // Fumadocs' dot parser owns the URL locale prefix. Mark each virtual
      // file with its locale and remove the same prefix from its route slugs.
      path: page.path
        .slice(`${locale}/`.length)
        .replace(/\.mdx$/, `.${locale}.mdx`),
    }))
    .build();
}

const docs = defineDocs({
  dir: "content/docs",
  docs: {
    async: true,
    postprocess: { includeProcessedMarkdown: true },
  },
});

export default defineConfig({
  mode: "static",
  site: {
    baseUrl: SITE_URL,
    name: "LangBot Docs",
  },
  content: {
    docs: docs.toFumadocsSource(),
    openapiEn: localizeOpenAPISource(
      await enOpenAPI.staticSource({ baseDir: "en/api-reference", ...legacyOpenApiLayout }),
      "en",
    ),
    openapiZh: localizeOpenAPISource(
      await zhOpenAPI.staticSource({ baseDir: "zh/api-reference", ...legacyOpenApiLayout }),
      "zh",
    ),
    openapiJa: localizeOpenAPISource(
      await jaOpenAPI.staticSource({ baseDir: "ja/api-reference", ...legacyOpenApiLayout }),
      "ja",
    ),
  },
  i18n,
  translations,
  defaultLayoutProps: ({ lang }) => {
    const locale = LOCALES.includes(lang as (typeof LOCALES)[number]) ? lang as (typeof LOCALES)[number] : "en";
    return {
      links: localizedNavbar(locale),
      nav: {
        title: docsBrand(),
        url: `/${locale}/insight/guide`,
      },
    };
  },
  meta: {
    page: (page) => {
      const locale = page.locale as (typeof LOCALES)[number];
      const route = page.slugs.join("/");
      const localizedRoutes = route.startsWith("api-reference/")
        ? openApiAlternatesByRoute.get(`${locale}:${route}`) ?? { [locale]: route }
        : Object.fromEntries([...routeLocales.get(route) ?? new Set<string>([locale])].map((candidate) => [candidate, route]));
      const alternates = LOCALES.filter((candidate) => localizedRoutes[candidate]);
      const defaultLocale = alternates.includes("en") ? "en" : alternates[0];
      return <>
        <link rel="canonical" href={`${SITE_URL}${page.url}`} />
        <link rel="alternate" type="text/markdown" href={`${SITE_URL}${page.url}.md`} />
        {alternates.map((candidate) => (
          <link
            key={candidate}
            rel="alternate"
            hrefLang={HREFLANG[candidate]}
            href={`${SITE_URL}/${candidate}/${localizedRoutes[candidate]}`.replace(/\/$/, "")}
          />
        ))}
        {defaultLocale && (
          <link
            rel="alternate"
            hrefLang="x-default"
            href={`${SITE_URL}/${defaultLocale}/${localizedRoutes[defaultLocale]}`.replace(/\/$/, "")}
          />
        )}
      </>;
    },
  },
})
  .adapters(fumadocsMdx())
  // One registration is intentional: its adapter and loader plugin handle all
  // OpenAPI virtual pages, regardless of which content source generated them.
  .plugins(
    // Replace the recommended generic Takumi artwork with our shared static
    // brand card. Keeping its plugin name suppresses duplicate og:image tags.
    { name: "core:takumi" },
    {
      name: "langbot:locale-preference",
      init() {
        const data = (this.data["core:provider"] ??= {});
        (data.transformers ??= []).push((props) => {
          if (props.i18n) props.children = <LocalePreferenceProvider i18n={props.i18n}>{props.children}</LocalePreferenceProvider>;
          return props;
        });
      },
    },
    flexsearchPlugin({
      async buildIndex(page) {
        const title = page.data.title ?? page.path;
        const description = page.data.description;
        const sourceStructuredData = typeof page.data.structuredData === "function"
          ? await page.data.structuredData()
          : page.data.structuredData;
        // FlexSearch's static serialization expands multilingual documents
        // considerably. Index titles, descriptions, a few headings, and the
        // opening content so search remains useful without exceeding Pages'
        // hard 25 MiB per-file limit. OpenAPI endpoints intentionally omit the
        // schema body, which is duplicated across every generated operation.
        const isOpenAPI = page.url.includes("/api-reference/");
        const headings = isOpenAPI
          ? []
          : sourceStructuredData.headings.slice(0, 4).map((heading) => ({
              ...heading,
              content: heading.content.slice(0, 100),
            }));
        const openingContent = isOpenAPI
          ? []
          : sourceStructuredData.contents.slice(0, 2).map((content) => content.content.slice(0, 300));
        const structuredData = {
          headings,
          contents: [{
            heading: undefined,
            content: [title, description, ...openingContent, page.url].filter(Boolean).join(" "),
          }],
        };
        return { id: page.url, title, description, url: page.url, structuredData };
      },
    }),
    mintlifyPlugin({ path: "content/fumapress-docs.json", features: { navbar: false } }),
    {
      name: "langbot:sectioned-navigation",
      enforce: "post",
      init() {
        const context = this;
        const sourceTrees = new Map<string, Root>();
        for (const key of ["core:docs-layout", "core:notebook-layout"] as const) {
          const data = (this.data[key] ??= {});
          (data.transformers ??= []).push(async ({ data: props, page }) => {
            const locale = page.locale as (typeof LOCALES)[number];
            let sourceTree = sourceTrees.get(locale);
            if (!sourceTree) {
              sourceTree = (await context.getLoader()).getPageTree(page.locale);
              sourceTrees.set(locale, sourceTree);
            }
            props.layoutProps.tree = {
              ...props.layoutProps.tree,
              children: sectionizeMintlifyTree(props.layoutProps.tree, sourceTree, locale)
                .children.map(renderNavigationIcons),
            };
            return props;
          });
        }
      },
    },
    openapiPlugin({ server: enOpenAPI }),
    robotsPlugin({
      rules: [{ userAgent: "*", allow: ["/", "/_next/"] }],
      sitemap: true,
      additionalContent: "Sitemap: https://langbot.app/docs/sitemap-alternates.xml",
    }),
  );
