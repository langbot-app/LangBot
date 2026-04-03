module.exports = [
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginCardVO.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PluginCardVO",
    ()=>PluginCardVO
]);
class PluginCardVO {
    author;
    label;
    name;
    description;
    version;
    enabled;
    priority;
    debug;
    install_source;
    install_info;
    status;
    components;
    hasUpdate;
    constructor(prop){
        this.author = prop.author;
        this.label = prop.label;
        this.description = prop.description;
        this.enabled = prop.enabled;
        this.components = prop.components;
        this.name = prop.name;
        this.priority = prop.priority;
        this.status = prop.status;
        this.version = prop.version;
        this.debug = prop.debug;
        this.install_source = prop.install_source;
        this.install_info = prop.install_info;
        this.hasUpdate = prop.hasUpdate;
    }
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DropdownMenu",
    ()=>DropdownMenu,
    "DropdownMenuCheckboxItem",
    ()=>DropdownMenuCheckboxItem,
    "DropdownMenuContent",
    ()=>DropdownMenuContent,
    "DropdownMenuGroup",
    ()=>DropdownMenuGroup,
    "DropdownMenuItem",
    ()=>DropdownMenuItem,
    "DropdownMenuLabel",
    ()=>DropdownMenuLabel,
    "DropdownMenuPortal",
    ()=>DropdownMenuPortal,
    "DropdownMenuRadioGroup",
    ()=>DropdownMenuRadioGroup,
    "DropdownMenuRadioItem",
    ()=>DropdownMenuRadioItem,
    "DropdownMenuSeparator",
    ()=>DropdownMenuSeparator,
    "DropdownMenuShortcut",
    ()=>DropdownMenuShortcut,
    "DropdownMenuSub",
    ()=>DropdownMenuSub,
    "DropdownMenuSubContent",
    ()=>DropdownMenuSubContent,
    "DropdownMenuSubTrigger",
    ()=>DropdownMenuSubTrigger,
    "DropdownMenuTrigger",
    ()=>DropdownMenuTrigger
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-dropdown-menu/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$check$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__CheckIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/check.js [app-ssr] (ecmascript) <export default as CheckIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRightIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-right.js [app-ssr] (ecmascript) <export default as ChevronRightIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__CircleIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle.js [app-ssr] (ecmascript) <export default as CircleIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-ssr] (ecmascript)");
'use client';
;
;
;
;
function DropdownMenu({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Root"], {
        "data-slot": "dropdown-menu",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 12,
        columnNumber: 10
    }, this);
}
function DropdownMenuPortal({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Portal"], {
        "data-slot": "dropdown-menu-portal",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 19,
        columnNumber: 5
    }, this);
}
function DropdownMenuTrigger({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Trigger"], {
        "data-slot": "dropdown-menu-trigger",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 27,
        columnNumber: 5
    }, this);
}
function DropdownMenuContent({ className, sideOffset = 4, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Portal"], {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Content"], {
            "data-slot": "dropdown-menu-content",
            sideOffset: sideOffset,
            className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('bg-popover text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 max-h-(--radix-dropdown-menu-content-available-height) min-w-[8rem] origin-(--radix-dropdown-menu-content-transform-origin) overflow-x-hidden overflow-y-auto rounded-md border p-1 shadow-md', className),
            ...props
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
            lineNumber: 41,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 40,
        columnNumber: 5
    }, this);
}
function DropdownMenuGroup({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Group"], {
        "data-slot": "dropdown-menu-group",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 58,
        columnNumber: 5
    }, this);
}
function DropdownMenuItem({ className, inset, variant = 'default', ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Item"], {
        "data-slot": "dropdown-menu-item",
        "data-inset": inset,
        "data-variant": variant,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])("focus:bg-accent focus:text-accent-foreground data-[variant=destructive]:text-destructive data-[variant=destructive]:focus:bg-destructive/10 dark:data-[variant=destructive]:focus:bg-destructive/20 data-[variant=destructive]:focus:text-destructive data-[variant=destructive]:*:[svg]:!text-destructive [&_svg:not([class*='text-'])]:text-muted-foreground relative flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[inset]:pl-8 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4", className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 72,
        columnNumber: 5
    }, this);
}
function DropdownMenuCheckboxItem({ className, children, checked, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CheckboxItem"], {
        "data-slot": "dropdown-menu-checkbox-item",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])("focus:bg-accent focus:text-accent-foreground relative flex cursor-default items-center gap-2 rounded-sm py-1.5 pr-2 pl-8 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4", className),
        checked: checked,
        ...props,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                className: "pointer-events-none absolute left-2 flex size-3.5 items-center justify-center",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ItemIndicator"], {
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$check$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__CheckIcon$3e$__["CheckIcon"], {
                        className: "size-4"
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                        lineNumber: 103,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                    lineNumber: 102,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                lineNumber: 101,
                columnNumber: 7
            }, this),
            children
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 92,
        columnNumber: 5
    }, this);
}
function DropdownMenuRadioGroup({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RadioGroup"], {
        "data-slot": "dropdown-menu-radio-group",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 115,
        columnNumber: 5
    }, this);
}
function DropdownMenuRadioItem({ className, children, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RadioItem"], {
        "data-slot": "dropdown-menu-radio-item",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])("focus:bg-accent focus:text-accent-foreground relative flex cursor-default items-center gap-2 rounded-sm py-1.5 pr-2 pl-8 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4", className),
        ...props,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                className: "pointer-events-none absolute left-2 flex size-3.5 items-center justify-center",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ItemIndicator"], {
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__CircleIcon$3e$__["CircleIcon"], {
                        className: "size-2 fill-current"
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                        lineNumber: 138,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                    lineNumber: 137,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                lineNumber: 136,
                columnNumber: 7
            }, this),
            children
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 128,
        columnNumber: 5
    }, this);
}
function DropdownMenuLabel({ className, inset, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Label"], {
        "data-slot": "dropdown-menu-label",
        "data-inset": inset,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('px-2 py-1.5 text-sm font-medium data-[inset]:pl-8', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 154,
        columnNumber: 5
    }, this);
}
function DropdownMenuSeparator({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Separator"], {
        "data-slot": "dropdown-menu-separator",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('bg-border -mx-1 my-1 h-px', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 171,
        columnNumber: 5
    }, this);
}
function DropdownMenuShortcut({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
        "data-slot": "dropdown-menu-shortcut",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('text-muted-foreground ml-auto text-xs tracking-widest', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 184,
        columnNumber: 5
    }, this);
}
function DropdownMenuSub({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Sub"], {
        "data-slot": "dropdown-menu-sub",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 198,
        columnNumber: 10
    }, this);
}
function DropdownMenuSubTrigger({ className, inset, children, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SubTrigger"], {
        "data-slot": "dropdown-menu-sub-trigger",
        "data-inset": inset,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('focus:bg-accent focus:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground flex cursor-default items-center rounded-sm px-2 py-1.5 text-sm outline-hidden select-none data-[inset]:pl-8', className),
        ...props,
        children: [
            children,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRightIcon$3e$__["ChevronRightIcon"], {
                className: "ml-auto size-4"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
                lineNumber: 220,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 210,
        columnNumber: 5
    }, this);
}
function DropdownMenuSubContent({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dropdown$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SubContent"], {
        "data-slot": "dropdown-menu-sub-content",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('bg-popover text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 min-w-[8rem] origin-(--radix-dropdown-menu-content-transform-origin) overflow-hidden rounded-md border p-1 shadow-lg', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx",
        lineNumber: 230,
        columnNumber: 5
    }, this);
}
;
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginComponentList
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-ssr] (ecmascript) <export default as Wrench>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/audio-waveform.js [app-ssr] (ecmascript) <export default as AudioWaveform>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/hash.js [app-ssr] (ecmascript) <export default as Hash>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/book.js [app-ssr] (ecmascript) <export default as Book>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$file$2d$text$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__FileText$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/file-text.js [app-ssr] (ecmascript) <export default as FileText>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-ssr] (ecmascript)");
;
;
;
function PluginComponentList({ components, showComponentName, showTitle, useBadge, t, responsive = false }) {
    const kindIconMap = {
        Tool: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 21,
            columnNumber: 11
        }, this),
        EventListener: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__["AudioWaveform"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 22,
            columnNumber: 20
        }, this),
        Command: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__["Hash"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 23,
            columnNumber: 14
        }, this),
        KnowledgeEngine: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__["Book"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 24,
            columnNumber: 22
        }, this),
        Parser: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$file$2d$text$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__FileText$3e$__["FileText"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 25,
            columnNumber: 13
        }, this)
    };
    const componentKindList = Object.keys(components || {});
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            showTitle && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                children: t('plugins.componentsList')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                lineNumber: 32,
                columnNumber: 21
            }, this),
            componentKindList.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                children: componentKindList.map((kind)=>{
                    return useBadge ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                        variant: "outline",
                        className: "flex items-center gap-1",
                        children: [
                            kindIconMap[kind],
                            responsive ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "hidden md:inline",
                                children: t('plugins.componentName.' + kind)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                lineNumber: 45,
                                columnNumber: 19
                            }, this) : showComponentName && t('plugins.componentName.' + kind),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "ml-1",
                                children: components[kind]
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                lineNumber: 51,
                                columnNumber: 17
                            }, this)
                        ]
                    }, kind, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                        lineNumber: 37,
                        columnNumber: 15
                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex flex-row items-center justify-start gap-[0.2rem]",
                        children: [
                            kindIconMap[kind],
                            responsive ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "hidden md:inline",
                                children: t('plugins.componentName.' + kind)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                lineNumber: 61,
                                columnNumber: 19
                            }, this) : showComponentName && t('plugins.componentName.' + kind),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "ml-1",
                                children: components[kind]
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                lineNumber: 67,
                                columnNumber: 17
                            }, this)
                        ]
                    }, kind, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                        lineNumber: 54,
                        columnNumber: 15
                    }, this);
                })
            }, void 0, false),
            componentKindList.length === 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                children: t('plugins.noComponents')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                lineNumber: 74,
                columnNumber: 42
            }, this)
        ]
    }, void 0, true);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginCardComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$bug$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__BugIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/bug.js [app-ssr] (ecmascript) <export default as BugIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$external$2d$link$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ExternalLink$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/external-link.js [app-ssr] (ecmascript) <export default as ExternalLink>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ellipsis$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Ellipsis$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/ellipsis.js [app-ssr] (ecmascript) <export default as Ellipsis>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$trash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Trash$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/trash.js [app-ssr] (ecmascript) <export default as Trash>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$arrow$2d$up$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ArrowUp$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/arrow-up.js [app-ssr] (ecmascript) <export default as ArrowUp>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
;
;
;
function PluginCardComponent({ cardVO, onCardClick, onDeleteClick, onUpgradeClick }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [dropdownOpen, setDropdownOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "w-[100%] h-[10rem] bg-white rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] p-[1.2rem] cursor-pointer dark:bg-[#1f1f22] relative transition-all duration-200 hover:shadow-[0px_3px_6px_0_rgba(0,0,0,0.12)] hover:scale-[1.005]",
            onClick: ()=>onCardClick(),
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "w-full h-full flex flex-row items-start justify-start gap-[1.2rem]",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                        src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPluginIconURL(cardVO.author, cardVO.name),
                        alt: "plugin icon",
                        className: "w-16 h-16 rounded-[8%] flex-shrink-0"
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                        lineNumber: 39,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex-1 min-w-0 h-full flex flex-col items-start justify-between gap-[0.6rem]",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-col items-start justify-start w-full min-w-0 flex-1 overflow-hidden",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex flex-col items-start justify-start w-full min-w-0",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-[0.7rem] text-[#666] dark:text-[#999] truncate w-full",
                                                children: [
                                                    cardVO.author,
                                                    " / ",
                                                    cardVO.name
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                lineNumber: 50,
                                                columnNumber: 17
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "text-[1.2rem] text-black dark:text-[#f0f0f0] truncate max-w-[10rem]",
                                                        children: cardVO.label
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                        lineNumber: 54,
                                                        columnNumber: 19
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                        variant: "outline",
                                                        className: "text-[0.7rem] flex-shrink-0",
                                                        children: [
                                                            "v",
                                                            cardVO.version
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                        lineNumber: 57,
                                                        columnNumber: 19
                                                    }, this),
                                                    cardVO.debug && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                        variant: "outline",
                                                        className: "text-[0.7rem] border-orange-400 text-orange-400 flex-shrink-0",
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$bug$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__BugIcon$3e$__["BugIcon"], {
                                                                className: "w-4 h-4"
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                                lineNumber: 68,
                                                                columnNumber: 23
                                                            }, this),
                                                            t('plugins.debugging')
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                        lineNumber: 64,
                                                        columnNumber: 21
                                                    }, this),
                                                    !cardVO.debug && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                                        children: [
                                                            cardVO.install_source === 'github' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                                variant: "outline",
                                                                className: "text-[0.7rem] border-blue-400 text-blue-400 flex-shrink-0",
                                                                children: t('plugins.fromGithub')
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                                lineNumber: 75,
                                                                columnNumber: 25
                                                            }, this),
                                                            cardVO.install_source === 'local' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                                variant: "outline",
                                                                className: "text-[0.7rem] border-green-400 text-green-400 flex-shrink-0",
                                                                children: t('plugins.fromLocal')
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                                lineNumber: 83,
                                                                columnNumber: 25
                                                            }, this),
                                                            cardVO.install_source === 'marketplace' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                                variant: "outline",
                                                                className: "text-[0.7rem] border-purple-400 text-purple-400 flex-shrink-0",
                                                                children: t('plugins.fromMarketplace')
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                                lineNumber: 91,
                                                                columnNumber: 25
                                                            }, this)
                                                        ]
                                                    }, void 0, true)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                lineNumber: 53,
                                                columnNumber: 17
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                        lineNumber: 49,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-[0.8rem] text-[#666] line-clamp-2 dark:text-[#999] w-full",
                                        children: cardVO.description
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                        lineNumber: 103,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                lineNumber: 48,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "w-full flex flex-row items-start justify-start gap-[0.6rem] flex-shrink-0 min-h-[1.5rem]",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                                    components: (()=>{
                                        const componentKindCount = {};
                                        for (const component of cardVO.components){
                                            const kind = component.manifest.manifest.kind;
                                            if (componentKindCount[kind]) {
                                                componentKindCount[kind]++;
                                            } else {
                                                componentKindCount[kind] = 1;
                                            }
                                        }
                                        return componentKindCount;
                                    })(),
                                    showComponentName: false,
                                    showTitle: true,
                                    useBadge: false,
                                    t: t
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                    lineNumber: 110,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                lineNumber: 109,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                        lineNumber: 46,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex flex-col items-center justify-between h-full relative z-20 flex-shrink-0",
                        onClick: (e)=>e.stopPropagation(),
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center justify-center"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                lineNumber: 136,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center justify-center",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenu"], {
                                    open: dropdownOpen,
                                    onOpenChange: (open)=>{
                                        setDropdownOpen(open);
                                    },
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuTrigger"], {
                                            asChild: true,
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "relative",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                        variant: "ghost",
                                                        className: "bg-white dark:bg-[#1f1f22] hover:bg-gray-100 dark:hover:bg-[#2a2a2d]",
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ellipsis$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Ellipsis$3e$__["Ellipsis"], {
                                                            className: "w-4 h-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 151,
                                                            columnNumber: 23
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                        lineNumber: 147,
                                                        columnNumber: 21
                                                    }, this),
                                                    cardVO.hasUpdate && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white dark:border-[#1f1f22]"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                        lineNumber: 154,
                                                        columnNumber: 23
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                lineNumber: 146,
                                                columnNumber: 19
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                            lineNumber: 145,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuContent"], {
                                            children: [
                                                cardVO.install_source === 'marketplace' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                    className: "flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer",
                                                    onClick: (e)=>{
                                                        e.stopPropagation();
                                                        onUpgradeClick(cardVO);
                                                        setDropdownOpen(false);
                                                    },
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$arrow$2d$up$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ArrowUp$3e$__["ArrowUp"], {
                                                            className: "w-4 h-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 169,
                                                            columnNumber: 23
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            children: t('plugins.update')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 170,
                                                            columnNumber: 23
                                                        }, this),
                                                        cardVO.hasUpdate && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                            className: "ml-auto bg-red-500 hover:bg-red-500 text-white text-[0.6rem] px-1.5 py-0 h-4",
                                                            children: t('plugins.new')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 172,
                                                            columnNumber: 25
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                    lineNumber: 161,
                                                    columnNumber: 21
                                                }, this),
                                                (cardVO.install_source === 'github' || cardVO.install_source === 'marketplace') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                    className: "flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer",
                                                    onClick: (e)=>{
                                                        e.stopPropagation();
                                                        if (cardVO.install_source === 'github') {
                                                            window.open(cardVO.install_info.github_url, '_blank');
                                                        } else if (cardVO.install_source === 'marketplace') {
                                                            window.open((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().getPluginMarketplaceURL(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].cloud_service_url, cardVO.author, cardVO.name), '_blank');
                                                        }
                                                        setDropdownOpen(false);
                                                    },
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$external$2d$link$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ExternalLink$3e$__["ExternalLink"], {
                                                            className: "w-4 h-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 200,
                                                            columnNumber: 23
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            children: t('plugins.viewSource')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 201,
                                                            columnNumber: 23
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                    lineNumber: 181,
                                                    columnNumber: 21
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                    className: "flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer text-red-600 focus:text-red-600",
                                                    onClick: (e)=>{
                                                        e.stopPropagation();
                                                        onDeleteClick(cardVO);
                                                        setDropdownOpen(false);
                                                    },
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$trash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Trash$3e$__["Trash"], {
                                                            className: "w-4 h-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 212,
                                                            columnNumber: 21
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            children: t('plugins.delete')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                            lineNumber: 213,
                                                            columnNumber: 21
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                                    lineNumber: 204,
                                                    columnNumber: 19
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                            lineNumber: 158,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                    lineNumber: 139,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                                lineNumber: 138,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                        lineNumber: 132,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
                lineNumber: 37,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx",
            lineNumber: 33,
            columnNumber: 7
        }, this)
    }, void 0, false);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/entities/form/dynamic.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DynamicFormItemType",
    ()=>DynamicFormItemType
]);
var DynamicFormItemType = /*#__PURE__*/ function(DynamicFormItemType) {
    DynamicFormItemType["INT"] = "integer";
    DynamicFormItemType["FLOAT"] = "float";
    DynamicFormItemType["BOOLEAN"] = "boolean";
    DynamicFormItemType["STRING"] = "string";
    DynamicFormItemType["TEXT"] = "text";
    DynamicFormItemType["STRING_ARRAY"] = "array[string]";
    DynamicFormItemType["FILE"] = "file";
    DynamicFormItemType["FILE_ARRAY"] = "array[file]";
    DynamicFormItemType["SELECT"] = "select";
    DynamicFormItemType["LLM_MODEL_SELECTOR"] = "llm-model-selector";
    DynamicFormItemType["EMBEDDING_MODEL_SELECTOR"] = "embedding-model-selector";
    DynamicFormItemType["MODEL_FALLBACK_SELECTOR"] = "model-fallback-selector";
    DynamicFormItemType["PROMPT_EDITOR"] = "prompt-editor";
    DynamicFormItemType["UNKNOWN"] = "unknown";
    DynamicFormItemType["KNOWLEDGE_BASE_SELECTOR"] = "knowledge-base-selector";
    DynamicFormItemType["KNOWLEDGE_BASE_MULTI_SELECTOR"] = "knowledge-base-multi-selector";
    DynamicFormItemType["PLUGIN_SELECTOR"] = "plugin-selector";
    DynamicFormItemType["BOT_SELECTOR"] = "bot-selector";
    return DynamicFormItemType;
}({});
}),
"[project]/coding/projects/LangBot/web/src/components/ui/textarea.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Textarea",
    ()=>Textarea
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-ssr] (ecmascript)");
;
;
function Textarea({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("textarea", {
        "data-slot": "textarea",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30 flex field-sizing-content min-h-16 w-full rounded-md border bg-transparent px-3 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/textarea.tsx",
        lineNumber: 7,
        columnNumber: 5
    }, this);
}
;
}),
"[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>DynamicFormItemComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/entities/form/dynamic.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/select.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/switch.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$textarea$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/textarea.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/card.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/checkbox.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/plus.js [app-ssr] (ecmascript) <export default as Plus>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/x.js [app-ssr] (ecmascript) <export default as X>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$eye$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Eye$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/eye.js [app-ssr] (ecmascript) <export default as Eye>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-ssr] (ecmascript) <export default as Wrench>");
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
function DynamicFormItemComponent({ config, field, onFileUploaded }) {
    const [llmModels, setLlmModels] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [embeddingModels, setEmbeddingModels] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [knowledgeBases, setKnowledgeBases] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [bots, setBots] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [uploading, setUploading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [kbDialogOpen, setKbDialogOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [tempSelectedKBIds, setTempSelectedKBIds] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const handleFileUpload = async (file)=>{
        const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
        if (file.size > MAX_FILE_SIZE) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.fileUpload.tooLarge'));
            return null;
        }
        try {
            setUploading(true);
            const response = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].uploadPluginConfigFile(file);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('plugins.fileUpload.success'));
            // 通知父组件文件已上传
            onFileUploaded?.(response.file_key);
            return {
                file_key: response.file_key,
                mimetype: file.type
            };
        } catch (error) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.fileUpload.failed') + ': ' + error.message);
            return null;
        } finally{
            setUploading(false);
        }
    };
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].LLM_MODEL_SELECTOR) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getProviderLLMModels().then((resp)=>{
                let models = resp.models;
                // Filter out space-chat-completions models when not logged in with space account or when models service is disabled
                if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].disable_models_service || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["userInfo"]?.account_type !== 'space') {
                    models = models.filter((m)=>m.provider?.requester !== 'space-chat-completions');
                }
                setLlmModels(models);
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('models.getModelListError') + err.msg);
            });
        }
    }, [
        config.type
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].EMBEDDING_MODEL_SELECTOR) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getProviderEmbeddingModels().then((resp)=>{
                setEmbeddingModels(resp.models);
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('embedding.getModelListError') + err.msg);
            });
        }
    }, [
        config.type
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].MODEL_FALLBACK_SELECTOR) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getProviderLLMModels().then((resp)=>{
                let models = resp.models;
                if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].disable_models_service || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["userInfo"]?.account_type !== 'space') {
                    models = models.filter((m)=>m.provider?.requester !== 'space-chat-completions');
                }
                setLlmModels(models);
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error('Failed to get LLM model list: ' + err.msg);
            });
        }
    }, [
        config.type
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_SELECTOR || config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_MULTI_SELECTOR) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getKnowledgeBases().then((resp)=>{
                setKnowledgeBases(resp.bases);
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('knowledge.getKnowledgeBaseListError') + err.msg);
            });
        }
    }, [
        config.type
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].BOT_SELECTOR) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getBots().then((resp)=>{
                setBots(resp.bots);
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('bots.getBotListError') + err.msg);
            });
        }
    }, [
        config.type
    ]);
    switch(config.type){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].INT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].FLOAT:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                type: "number",
                ...field,
                onChange: (e)=>field.onChange(Number(e.target.value))
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 182,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].STRING:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                ...field
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 190,
                columnNumber: 14
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].TEXT:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$textarea$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Textarea"], {
                ...field,
                className: "min-h-[120px]"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 193,
                columnNumber: 14
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].BOOLEAN:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Switch"], {
                checked: field.value,
                onCheckedChange: field.onChange
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 196,
                columnNumber: 14
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].STRING_ARRAY:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    field.value.map((item, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex gap-2 items-center",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                    className: "w-[200px]",
                                    value: item,
                                    onChange: (e)=>{
                                        const newValue = [
                                            ...field.value
                                        ];
                                        newValue[index] = e.target.value;
                                        field.onChange(newValue);
                                    }
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 203,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    type: "button",
                                    className: "p-2 hover:bg-gray-100 rounded",
                                    onClick: ()=>{
                                        const newValue = field.value.filter((_, i)=>i !== index);
                                        field.onChange(newValue);
                                    },
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        className: "w-5 h-5 text-red-500",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 228,
                                            columnNumber: 19
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 222,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 212,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, index, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 202,
                            columnNumber: 13
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                        type: "button",
                        variant: "outline",
                        onClick: ()=>{
                            field.onChange([
                                ...field.value,
                                ''
                            ]);
                        },
                        children: t('common.add')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 233,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 200,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].SELECT:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('common.select')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 249,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 248,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                            children: config.options?.map((option)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: option.name,
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(option.label)
                                }, option.name, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 254,
                                    columnNumber: 17
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 252,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 251,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 247,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].LLM_MODEL_SELECTOR:
            // Group models by provider
            const groupedModels = llmModels.reduce((acc, model)=>{
                const providerName = model.provider?.name || model.provider?.requester || 'Unknown';
                if (!acc[providerName]) acc[providerName] = [];
                acc[providerName].push(model);
                return acc;
            }, {});
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('models.selectModel')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 279,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 278,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: Object.entries(groupedModels).map(([providerName, models])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                        children: providerName
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 284,
                                        columnNumber: 17
                                    }, this),
                                    models.map((model)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                            value: model.uuid,
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "inline-flex items-center gap-1",
                                                children: [
                                                    model.name,
                                                    model.abilities?.includes('vision') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$eye$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Eye$3e$__["Eye"], {
                                                        className: "h-3 w-3 text-muted-foreground"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 290,
                                                        columnNumber: 25
                                                    }, this),
                                                    model.abilities?.includes('func_call') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                                        className: "h-3 w-3 text-muted-foreground"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 293,
                                                        columnNumber: 25
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 287,
                                                columnNumber: 21
                                            }, this)
                                        }, model.uuid, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 286,
                                            columnNumber: 19
                                        }, this))
                                ]
                            }, providerName, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 283,
                                columnNumber: 15
                            }, this))
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 281,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 277,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].EMBEDDING_MODEL_SELECTOR:
            // Group embedding models by provider
            const groupedEmbeddingModels = embeddingModels.reduce((acc, model)=>{
                const providerName = model.provider?.name || 'Unknown';
                if (!acc[providerName]) acc[providerName] = [];
                acc[providerName].push(model);
                return acc;
            }, {});
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('knowledge.selectEmbeddingModel')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 319,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 318,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: Object.entries(groupedEmbeddingModels).map(([providerName, models])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                        children: providerName
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 325,
                                        columnNumber: 19
                                    }, this),
                                    models.map((model)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                            value: model.uuid,
                                            children: model.name
                                        }, model.uuid, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 327,
                                            columnNumber: 21
                                        }, this))
                                ]
                            }, providerName, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 324,
                                columnNumber: 17
                            }, this))
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 321,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 317,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].MODEL_FALLBACK_SELECTOR:
            {
                // Group models by provider
                const groupedModelsForFallback = llmModels.reduce((acc, model)=>{
                    const providerName = model.provider?.name || model.provider?.requester || 'Unknown';
                    if (!acc[providerName]) acc[providerName] = [];
                    acc[providerName].push(model);
                    return acc;
                }, {});
                const rawModelValue = field.value;
                const modelValue = rawModelValue != null && typeof rawModelValue === 'object' && !Array.isArray(rawModelValue) ? {
                    primary: typeof rawModelValue.primary === 'string' ? rawModelValue.primary : '',
                    fallbacks: Array.isArray(rawModelValue.fallbacks) ? rawModelValue.fallbacks.filter((v)=>typeof v === 'string') : []
                } : {
                    primary: typeof rawModelValue === 'string' ? rawModelValue : '',
                    fallbacks: []
                };
                const renderModelSelect = (value, onChange, placeholder)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                        value: value,
                        onValueChange: onChange,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                                className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                                    placeholder: placeholder
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 384,
                                    columnNumber: 13
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 383,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                                children: Object.entries(groupedModelsForFallback).map(([providerName, models])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                                children: providerName
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 390,
                                                columnNumber: 19
                                            }, this),
                                            models.map((model)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                    value: model.uuid,
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "inline-flex items-center gap-1",
                                                        children: [
                                                            model.name,
                                                            model.abilities?.includes('vision') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$eye$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Eye$3e$__["Eye"], {
                                                                className: "h-3 w-3 text-muted-foreground"
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 396,
                                                                columnNumber: 27
                                                            }, this),
                                                            model.abilities?.includes('func_call') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                                                className: "h-3 w-3 text-muted-foreground"
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 399,
                                                                columnNumber: 27
                                                            }, this)
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 393,
                                                        columnNumber: 23
                                                    }, this)
                                                }, model.uuid, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                    lineNumber: 392,
                                                    columnNumber: 21
                                                }, this))
                                        ]
                                    }, providerName, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 389,
                                        columnNumber: 17
                                    }, this))
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 386,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 382,
                        columnNumber: 9
                    }, this);
                const updateValue = (patch)=>{
                    field.onChange({
                        ...modelValue,
                        ...patch
                    });
                };
                const addFallbackModel = ()=>{
                    updateValue({
                        fallbacks: [
                            ...modelValue.fallbacks,
                            ''
                        ]
                    });
                };
                const updateFallbackModel = (index, value)=>{
                    const updated = [
                        ...modelValue.fallbacks
                    ];
                    updated[index] = value;
                    updateValue({
                        fallbacks: updated
                    });
                };
                const removeFallbackModel = (index)=>{
                    const updated = [
                        ...modelValue.fallbacks
                    ];
                    updated.splice(index, 1);
                    updateValue({
                        fallbacks: updated
                    });
                };
                const moveFallbackModel = (index, direction)=>{
                    const updated = [
                        ...modelValue.fallbacks
                    ];
                    const newIndex = direction === 'up' ? index - 1 : index + 1;
                    if (newIndex < 0 || newIndex >= updated.length) return;
                    [updated[index], updated[newIndex]] = [
                        updated[newIndex],
                        updated[index]
                    ];
                    updateValue({
                        fallbacks: updated
                    });
                };
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "space-y-3",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-xs text-muted-foreground mb-1",
                                    children: t('models.fallback.primary')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 446,
                                    columnNumber: 13
                                }, this),
                                renderModelSelect(modelValue.primary, (val)=>updateValue({
                                        primary: val
                                    }), t('models.selectModel'))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 445,
                            columnNumber: 11
                        }, this),
                        modelValue.fallbacks.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "space-y-2",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-xs text-muted-foreground",
                                    children: t('models.fallback.fallbackList')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 459,
                                    columnNumber: 15
                                }, this),
                                modelValue.fallbacks.map((fbUuid, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex items-center gap-2",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "text-xs text-muted-foreground w-4 shrink-0",
                                                children: [
                                                    index + 1,
                                                    "."
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 464,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex-1",
                                                children: renderModelSelect(fbUuid, (val)=>updateFallbackModel(index, val), t('models.selectModel'))
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 467,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex gap-1 shrink-0",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                        type: "button",
                                                        variant: "ghost",
                                                        size: "sm",
                                                        className: "h-8 w-8 p-0",
                                                        onClick: ()=>moveFallbackModel(index, 'up'),
                                                        disabled: index === 0,
                                                        children: "↑"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 475,
                                                        columnNumber: 21
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                        type: "button",
                                                        variant: "ghost",
                                                        size: "sm",
                                                        className: "h-8 w-8 p-0",
                                                        onClick: ()=>moveFallbackModel(index, 'down'),
                                                        disabled: index === modelValue.fallbacks.length - 1,
                                                        children: "↓"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 485,
                                                        columnNumber: 21
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                        type: "button",
                                                        variant: "ghost",
                                                        size: "sm",
                                                        className: "h-8 w-8 p-0 text-destructive",
                                                        onClick: ()=>removeFallbackModel(index),
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__["X"], {
                                                            className: "h-4 w-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                            lineNumber: 502,
                                                            columnNumber: 23
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 495,
                                                        columnNumber: 21
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 474,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, index, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 463,
                                        columnNumber: 17
                                    }, this))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 458,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                            type: "button",
                            variant: "outline",
                            size: "sm",
                            className: "w-full",
                            onClick: addFallbackModel,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__["Plus"], {
                                    className: "h-4 w-4 mr-1"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 518,
                                    columnNumber: 13
                                }, this),
                                t('models.fallback.addFallback')
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 511,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                    lineNumber: 443,
                    columnNumber: 9
                }, this);
            }
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_SELECTOR:
            // Group KBs by Knowledge Engine name
            const kbsByEngine = knowledgeBases.reduce((acc, kb)=>{
                const engineName = kb.knowledge_engine?.name ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(kb.knowledge_engine.name) : t('knowledge.unknownEngine');
                if (!acc[engineName]) {
                    acc[engineName] = [];
                }
                acc[engineName].push(kb);
                return acc;
            }, {});
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('knowledge.selectKnowledgeBase')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 544,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 543,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: "__none__",
                                    children: t('knowledge.empty')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 548,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 547,
                                columnNumber: 13
                            }, this),
                            Object.entries(kbsByEngine).map(([engineName, kbs])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                            children: engineName
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 553,
                                            columnNumber: 17
                                        }, this),
                                        kbs.map((base)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                value: base.uuid ?? '',
                                                children: base.name
                                            }, base.uuid, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 555,
                                                columnNumber: 19
                                            }, this))
                                    ]
                                }, engineName, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 552,
                                    columnNumber: 15
                                }, this))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 546,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 542,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_MULTI_SELECTOR:
            // Group KBs by Knowledge Engine name for multi-selector
            const multiKbsByEngine = knowledgeBases.reduce((acc, kb)=>{
                const engineName = kb.knowledge_engine?.name ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(kb.knowledge_engine.name) : t('knowledge.unknownEngine');
                if (!acc[engineName]) {
                    acc[engineName] = [];
                }
                acc[engineName].push(kb);
                return acc;
            }, {});
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "space-y-2",
                        children: field.value && field.value.length > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "space-y-2",
                            children: field.value.map((kbId)=>{
                                const currentKb = knowledgeBases.find((base)=>base.uuid === kbId);
                                if (!currentKb) return null;
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between rounded-lg border p-3 hover:bg-accent",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex items-center gap-2 flex-1",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex-1 min-w-0",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "font-medium flex items-center gap-2",
                                                        children: [
                                                            currentKb.name,
                                                            currentKb.knowledge_engine?.name && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                className: "text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
                                                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(currentKb.knowledge_engine.name)
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 602,
                                                                columnNumber: 31
                                                            }, this)
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 599,
                                                        columnNumber: 27
                                                    }, this),
                                                    currentKb.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "text-sm text-muted-foreground",
                                                        children: currentKb.description
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 610,
                                                        columnNumber: 29
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 598,
                                                columnNumber: 25
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 597,
                                            columnNumber: 23
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            type: "button",
                                            variant: "ghost",
                                            size: "icon",
                                            onClick: ()=>{
                                                const newValue = field.value.filter((id)=>id !== kbId);
                                                field.onChange(newValue);
                                            },
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__["X"], {
                                                className: "h-4 w-4"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 627,
                                                columnNumber: 25
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 616,
                                            columnNumber: 23
                                        }, this)
                                    ]
                                }, kbId, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 593,
                                    columnNumber: 21
                                }, this);
                            })
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 585,
                            columnNumber: 15
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-sm text-muted-foreground",
                                children: t('knowledge.noKnowledgeBaseSelected')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 635,
                                columnNumber: 17
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 634,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 583,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                        type: "button",
                        onClick: ()=>{
                            setTempSelectedKBIds(field.value || []);
                            setKbDialogOpen(true);
                        },
                        variant: "outline",
                        className: "w-full",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__["Plus"], {
                                className: "mr-2 h-4 w-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 651,
                                columnNumber: 13
                            }, this),
                            t('knowledge.addKnowledgeBase')
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 642,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Dialog"], {
                        open: kbDialogOpen,
                        onOpenChange: setKbDialogOpen,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogContent"], {
                            className: "max-w-2xl max-h-[80vh] overflow-hidden flex flex-col",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogHeader"], {
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                        children: t('knowledge.selectKnowledgeBases')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 659,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 658,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex-1 overflow-y-auto space-y-4 pr-2",
                                    children: Object.entries(multiKbsByEngine).map(([engineName, kbs])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "space-y-2",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "text-sm font-semibold text-muted-foreground px-2",
                                                    children: engineName
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                    lineNumber: 664,
                                                    columnNumber: 21
                                                }, this),
                                                kbs.map((base)=>{
                                                    const isSelected = tempSelectedKBIds.includes(base.uuid ?? '');
                                                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer",
                                                        onClick: ()=>{
                                                            const kbId = base.uuid ?? '';
                                                            setTempSelectedKBIds((prev)=>prev.includes(kbId) ? prev.filter((id)=>id !== kbId) : [
                                                                    ...prev,
                                                                    kbId
                                                                ]);
                                                        },
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Checkbox"], {
                                                                checked: isSelected,
                                                                "aria-label": `Select ${base.name}`
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 684,
                                                                columnNumber: 27
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "flex-1",
                                                                children: [
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "font-medium",
                                                                        children: base.name
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                        lineNumber: 689,
                                                                        columnNumber: 29
                                                                    }, this),
                                                                    base.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "text-sm text-muted-foreground",
                                                                        children: base.description
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                        lineNumber: 691,
                                                                        columnNumber: 31
                                                                    }, this)
                                                                ]
                                                            }, void 0, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 688,
                                                                columnNumber: 27
                                                            }, this)
                                                        ]
                                                    }, base.uuid, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 672,
                                                        columnNumber: 25
                                                    }, this);
                                                })
                                            ]
                                        }, engineName, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 663,
                                            columnNumber: 19
                                        }, this))
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 661,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogFooter"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "outline",
                                            onClick: ()=>setKbDialogOpen(false),
                                            children: t('common.cancel')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 703,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            onClick: ()=>{
                                                field.onChange(tempSelectedKBIds);
                                                setKbDialogOpen(false);
                                            },
                                            children: t('common.confirm')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 709,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 702,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 657,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 656,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].BOT_SELECTOR:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('bots.selectBot')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 727,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 726,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                            children: bots.map((bot)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: bot.uuid ?? '',
                                    children: bot.name
                                }, bot.uuid, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 732,
                                    columnNumber: 17
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 730,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 729,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 725,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].PROMPT_EDITOR:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    field.value.map((item, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex gap-2 items-center",
                            children: [
                                index === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "w-[120px] px-3 py-2 border rounded bg-gray-50 dark:bg-[#2a292e] text-gray-500 dark:text-white dark:border-gray-600",
                                    children: "system"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 749,
                                    columnNumber: 19
                                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                                    value: item.role,
                                    onValueChange: (value)=>{
                                        const newValue = [
                                            ...field.value
                                        ];
                                        newValue[index] = {
                                            ...newValue[index],
                                            role: value
                                        };
                                        field.onChange(newValue);
                                    },
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                                            className: "w-[120px] bg-[#ffffff] dark:bg-[#2a2a2e]",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {}, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 762,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 761,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                        value: "user",
                                                        children: "user"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 766,
                                                        columnNumber: 25
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                        value: "assistant",
                                                        children: "assistant"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 767,
                                                        columnNumber: 25
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 765,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 764,
                                            columnNumber: 21
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 753,
                                    columnNumber: 19
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$textarea$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Textarea"], {
                                    className: "w-[300px]",
                                    value: item.content,
                                    onChange: (e)=>{
                                        const newValue = [
                                            ...field.value
                                        ];
                                        newValue[index] = {
                                            ...newValue[index],
                                            content: e.target.value
                                        };
                                        field.onChange(newValue);
                                    }
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 773,
                                    columnNumber: 17
                                }, this),
                                index !== 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    type: "button",
                                    className: "p-2 hover:bg-gray-100 rounded",
                                    onClick: ()=>{
                                        const newValue = field.value.filter(// eslint-disable-next-line @typescript-eslint/no-explicit-any
                                        (_, i)=>i !== index);
                                        field.onChange(newValue);
                                    },
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        className: "w-5 h-5 text-red-500",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 804,
                                            columnNumber: 23
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 798,
                                        columnNumber: 21
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 787,
                                    columnNumber: 19
                                }, this)
                            ]
                        }, index, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 746,
                            columnNumber: 15
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                        type: "button",
                        variant: "outline",
                        onClick: ()=>{
                            field.onChange([
                                ...field.value,
                                {
                                    role: 'user',
                                    content: ''
                                }
                            ]);
                        },
                        children: t('common.addRound')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 811,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 743,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].FILE:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: field.value && field.value.file_key ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Card"], {
                    className: "py-3 max-w-full overflow-hidden bg-gray-900",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardContent"], {
                        className: "flex items-center gap-3 p-0 px-4 min-w-0",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex-1 min-w-0 overflow-hidden",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-sm font-medium truncate",
                                        title: field.value.file_key,
                                        children: field.value.file_key
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 830,
                                        columnNumber: 19
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-xs text-muted-foreground truncate",
                                        children: field.value.mimetype
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 836,
                                        columnNumber: 19
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 829,
                                columnNumber: 17
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                type: "button",
                                variant: "ghost",
                                size: "sm",
                                className: "flex-shrink-0 h-8 w-8 p-0",
                                onClick: (e)=>{
                                    e.preventDefault();
                                    e.stopPropagation();
                                    field.onChange(null);
                                },
                                title: t('common.delete'),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                    xmlns: "http://www.w3.org/2000/svg",
                                    viewBox: "0 0 24 24",
                                    fill: "currentColor",
                                    className: "w-4 h-4 text-destructive",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                        d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 858,
                                        columnNumber: 21
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 852,
                                    columnNumber: 19
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 840,
                                columnNumber: 17
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 828,
                        columnNumber: 15
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                    lineNumber: 827,
                    columnNumber: 13
                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "relative",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                            type: "file",
                            accept: config.accept,
                            disabled: uploading,
                            onChange: async (e)=>{
                                const file = e.target.files?.[0];
                                if (file) {
                                    const fileConfig = await handleFileUpload(file);
                                    if (fileConfig) {
                                        field.onChange(fileConfig);
                                    }
                                }
                                e.target.value = '';
                            },
                            className: "hidden",
                            id: `file-input-${config.name}`
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 865,
                            columnNumber: 15
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                            type: "button",
                            variant: "outline",
                            size: "sm",
                            disabled: uploading,
                            onClick: ()=>document.getElementById(`file-input-${config.name}`)?.click(),
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                    className: "w-4 h-4 mr-2",
                                    xmlns: "http://www.w3.org/2000/svg",
                                    viewBox: "0 0 24 24",
                                    fill: "currentColor",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                        d: "M11 11V5H13V11H19V13H13V19H11V13H5V11H11Z"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 897,
                                        columnNumber: 19
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 891,
                                    columnNumber: 17
                                }, this),
                                uploading ? t('plugins.fileUpload.uploading') : t('plugins.fileUpload.chooseFile')
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 882,
                            columnNumber: 15
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                    lineNumber: 864,
                    columnNumber: 13
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 825,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DynamicFormItemType"].FILE_ARRAY:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    field.value?.map((fileConfig, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Card"], {
                            className: "py-3 max-w-full overflow-hidden bg-gray-900",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardContent"], {
                                className: "flex items-center gap-3 p-0 px-4 min-w-0",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex-1 min-w-0 overflow-hidden",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-sm font-medium truncate",
                                                title: fileConfig.file_key,
                                                children: fileConfig.file_key
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 919,
                                                columnNumber: 21
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-xs text-muted-foreground truncate",
                                                children: fileConfig.mimetype
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 925,
                                                columnNumber: 21
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 918,
                                        columnNumber: 19
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                        type: "button",
                                        variant: "ghost",
                                        size: "sm",
                                        className: "flex-shrink-0 h-8 w-8 p-0",
                                        onClick: (e)=>{
                                            e.preventDefault();
                                            e.stopPropagation();
                                            const newValue = field.value.filter((_, i)=>i !== index);
                                            field.onChange(newValue);
                                        },
                                        title: t('common.delete'),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            viewBox: "0 0 24 24",
                                            fill: "currentColor",
                                            className: "w-4 h-4 text-destructive",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 950,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 944,
                                            columnNumber: 21
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 929,
                                        columnNumber: 19
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 917,
                                columnNumber: 17
                            }, this)
                        }, index, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 913,
                            columnNumber: 15
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "relative",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                type: "file",
                                accept: config.accept,
                                disabled: uploading,
                                onChange: async (e)=>{
                                    const file = e.target.files?.[0];
                                    if (file) {
                                        const fileConfig = await handleFileUpload(file);
                                        if (fileConfig) {
                                            field.onChange([
                                                ...field.value || [],
                                                fileConfig
                                            ]);
                                        }
                                    }
                                    e.target.value = '';
                                },
                                className: "hidden",
                                id: `file-array-input-${config.name}`
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 958,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                type: "button",
                                variant: "outline",
                                size: "sm",
                                disabled: uploading,
                                onClick: ()=>document.getElementById(`file-array-input-${config.name}`)?.click(),
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        className: "w-4 h-4 mr-2",
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M11 11V5H13V11H19V13H13V19H11V13H5V11H11Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 992,
                                            columnNumber: 17
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 986,
                                        columnNumber: 15
                                    }, this),
                                    uploading ? t('plugins.fileUpload.uploading') : t('plugins.fileUpload.addFile')
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 975,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 957,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 910,
                columnNumber: 9
            }, this);
        default:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                ...field
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 1003,
                columnNumber: 14
            }, this);
    }
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>DynamicFormComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-hook-form/dist/index.esm.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@hookform/resolvers/zod/dist/zod.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/zod/v3/external.js [app-ssr] (ecmascript) <export * as z>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/form.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormItemComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
;
;
function DynamicFormComponent({ itemConfigList, onSubmit, initialValues, onFileUploaded, isEditing, externalDependentValues }) {
    const isInitialMount = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(true);
    const previousInitialValues = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(initialValues);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    // Normalize a form value according to its field type.
    // This ensures legacy/malformed data (e.g. a plain string for
    // model-fallback-selector) is coerced to the expected shape
    // so that downstream components never crash.
    const normalizeFieldValue = (item, value)=>{
        if (item.type === 'model-fallback-selector') {
            if (value != null && typeof value === 'object' && !Array.isArray(value)) {
                const obj = value;
                return {
                    primary: typeof obj.primary === 'string' ? obj.primary : '',
                    fallbacks: Array.isArray(obj.fallbacks) ? obj.fallbacks.filter((v)=>typeof v === 'string') : []
                };
            }
            // Legacy string format or any other unexpected type
            return {
                primary: typeof value === 'string' ? value : '',
                fallbacks: []
            };
        }
        return value;
    };
    // 根据 itemConfigList 动态生成 zod schema
    const formSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object(itemConfigList.reduce((acc, item)=>{
        let fieldSchema;
        switch(item.type){
            case 'integer':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number();
                break;
            case 'float':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number();
                break;
            case 'boolean':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].boolean();
                break;
            case 'string':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'array[string]':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string());
                break;
            case 'select':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'llm-model-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'embedding-model-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'knowledge-base-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'knowledge-base-multi-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string());
                break;
            case 'bot-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'model-fallback-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                    primary: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                    fallbacks: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string())
                });
                break;
            case 'prompt-editor':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                    content: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                    role: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
                }));
                break;
            default:
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
        }
        if (item.required && (fieldSchema instanceof __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodString || fieldSchema instanceof __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodArray)) {
            fieldSchema = fieldSchema.min(1, {
                message: t('common.fieldRequired')
            });
        }
        return {
            ...acc,
            [item.name]: fieldSchema
        };
    }, {}));
    const form = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useForm"])({
        resolver: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["zodResolver"])(formSchema),
        defaultValues: itemConfigList.reduce((acc, item)=>{
            // 优先使用 initialValues，如果没有则使用默认值
            const rawValue = initialValues?.[item.name] ?? item.default;
            return {
                ...acc,
                [item.name]: normalizeFieldValue(item, rawValue)
            };
        }, {})
    });
    // 当 initialValues 变化时更新表单值
    // 但要避免因为内部表单更新触发的 onSubmit 导致的 initialValues 变化而重新设置表单
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        // 首次挂载时，使用 initialValues 初始化表单
        if (isInitialMount.current) {
            isInitialMount.current = false;
            previousInitialValues.current = initialValues;
            return;
        }
        // 检查 initialValues 是否真的发生了实质性变化
        // 使用 JSON.stringify 进行深度比较
        const hasRealChange = JSON.stringify(previousInitialValues.current) !== JSON.stringify(initialValues);
        if (initialValues && hasRealChange) {
            // 合并默认值和初始值
            const mergedValues = itemConfigList.reduce((acc, item)=>{
                const rawValue = initialValues[item.name] ?? item.default;
                acc[item.name] = normalizeFieldValue(item, rawValue);
                return acc;
            }, {});
            Object.entries(mergedValues).forEach(([key, value])=>{
                form.setValue(key, value);
            });
            previousInitialValues.current = initialValues;
        }
    }, [
        initialValues,
        form,
        itemConfigList
    ]);
    // Get reactive form values for conditional rendering
    const watchedValues = form.watch();
    // Stable ref for onSubmit to avoid re-triggering the effect when the
    // parent passes a new closure on every render.
    const onSubmitRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(onSubmit);
    onSubmitRef.current = onSubmit;
    // 监听表单值变化
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        // Emit initial form values immediately so the parent always has a valid snapshot,
        // even if the user saves without modifying any field.
        // form.watch(callback) only fires on subsequent changes, not on mount.
        const formValues = form.getValues();
        const initialFinalValues = itemConfigList.reduce((acc, item)=>{
            acc[item.name] = formValues[item.name] ?? item.default;
            return acc;
        }, {});
        onSubmitRef.current?.(initialFinalValues);
        // Update previousInitialValues to the emitted snapshot so that if the
        // parent writes these values back as new initialValues, the deep
        // comparison in the initialValues-sync useEffect won't detect a change
        // and won't trigger an infinite update loop.
        previousInitialValues.current = initialFinalValues;
        const subscription = form.watch(()=>{
            const formValues = form.getValues();
            const finalValues = itemConfigList.reduce((acc, item)=>{
                acc[item.name] = formValues[item.name] ?? item.default;
                return acc;
            }, {});
            onSubmitRef.current?.(finalValues);
            previousInitialValues.current = finalValues;
        });
        return ()=>subscription.unsubscribe();
    }, [
        form,
        itemConfigList
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Form"], {
        ...form,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "space-y-4",
            children: itemConfigList.map((config)=>{
                if (config.show_if) {
                    const dependValue = watchedValues[config.show_if.field] !== undefined ? watchedValues[config.show_if.field] : externalDependentValues?.[config.show_if.field];
                    if (config.show_if.operator === 'eq' && dependValue !== config.show_if.value) {
                        return null;
                    }
                    if (config.show_if.operator === 'neq' && dependValue === config.show_if.value) {
                        return null;
                    }
                    if (config.show_if.operator === 'in' && Array.isArray(config.show_if.value) && !config.show_if.value.includes(dependValue)) {
                        return null;
                    }
                }
                // All fields are disabled when editing (creation_settings are immutable)
                const isFieldDisabled = !!isEditing;
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                    control: form.control,
                    name: config.name,
                    render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                    children: [
                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(config.label),
                                        ' ',
                                        config.required && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "text-red-500",
                                            children: "*"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                            lineNumber: 285,
                                            columnNumber: 41
                                        }, void 0)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 283,
                                    columnNumber: 19
                                }, void 0),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: isFieldDisabled ? 'pointer-events-none opacity-60' : '',
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormItemComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                                            config: config,
                                            field: field,
                                            onFileUploaded: onFileUploaded
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                            lineNumber: 293,
                                            columnNumber: 23
                                        }, void 0)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                        lineNumber: 288,
                                        columnNumber: 21
                                    }, void 0)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 287,
                                    columnNumber: 19
                                }, void 0),
                                config.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-muted-foreground",
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(config.description)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 301,
                                    columnNumber: 21
                                }, void 0),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 305,
                                    columnNumber: 19
                                }, void 0)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                            lineNumber: 282,
                            columnNumber: 17
                        }, void 0)
                }, config.id, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                    lineNumber: 277,
                    columnNumber: 13
                }, this);
            })
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
            lineNumber: 240,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
        lineNumber: 239,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginForm
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
;
;
function PluginForm({ pluginAuthor, pluginName, onFormSubmit, onFormCancel }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [pluginInfo, setPluginInfo] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])();
    const [pluginConfig, setPluginConfig] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])();
    const [isSaving, setIsLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const currentFormValues = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])({});
    const uploadedFileKeys = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(new Set());
    const initialFileKeys = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(new Set());
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        // 获取插件信息
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPlugin(pluginAuthor, pluginName).then((res)=>{
            setPluginInfo(res.plugin);
        });
        // 获取插件配置
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPluginConfig(pluginAuthor, pluginName).then((res)=>{
            setPluginConfig(res);
            // 提取初始配置中的所有文件 key
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const extractFileKeys = (obj)=>{
                const keys = [];
                if (obj && typeof obj === 'object') {
                    if ('file_key' in obj && typeof obj.file_key === 'string') {
                        keys.push(obj.file_key);
                    }
                    for (const value of Object.values(obj)){
                        if (Array.isArray(value)) {
                            value.forEach((item)=>keys.push(...extractFileKeys(item)));
                        } else if (typeof value === 'object' && value !== null) {
                            keys.push(...extractFileKeys(value));
                        }
                    }
                }
                return keys;
            };
            const fileKeys = extractFileKeys(res.config);
            initialFileKeys.current = new Set(fileKeys);
        });
    }, [
        pluginAuthor,
        pluginName
    ]);
    const handleSubmit = async ()=>{
        setIsLoading(true);
        try {
            // 保存配置
            await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].updatePluginConfig(pluginAuthor, pluginName, currentFormValues.current);
            // 提取最终保存的配置中的所有文件 key
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const extractFileKeys = (obj)=>{
                const keys = [];
                if (obj && typeof obj === 'object') {
                    if ('file_key' in obj && typeof obj.file_key === 'string') {
                        keys.push(obj.file_key);
                    }
                    for (const value of Object.values(obj)){
                        if (Array.isArray(value)) {
                            value.forEach((item)=>keys.push(...extractFileKeys(item)));
                        } else if (typeof value === 'object' && value !== null) {
                            keys.push(...extractFileKeys(value));
                        }
                    }
                }
                return keys;
            };
            const finalFileKeys = new Set(extractFileKeys(currentFormValues.current));
            // 计算需要删除的文件：
            // 1. 在编辑期间上传的，但最终未保存的文件
            // 2. 初始配置中有的，但最终配置中没有的文件（被删除的文件）
            const filesToDelete = [];
            // 上传了但未使用的文件
            uploadedFileKeys.current.forEach((key)=>{
                if (!finalFileKeys.has(key)) {
                    filesToDelete.push(key);
                }
            });
            // 初始有但最终没有的文件（被删除的）
            initialFileKeys.current.forEach((key)=>{
                if (!finalFileKeys.has(key)) {
                    filesToDelete.push(key);
                }
            });
            // 删除不需要的文件
            const deletePromises = filesToDelete.map((fileKey)=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].deletePluginConfigFile(fileKey).catch((err)=>{
                    console.warn(`Failed to delete file ${fileKey}:`, err);
                }));
            await Promise.all(deletePromises);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('plugins.saveConfigSuccessNormal'));
            onFormSubmit(1000);
        } catch (error) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.saveConfigError') + error.message);
        } finally{
            setIsLoading(false);
        }
    };
    if (!pluginInfo || !pluginConfig) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex items-center justify-center h-full mb-[2rem]",
            children: t('plugins.loading')
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
            lineNumber: 135,
            columnNumber: 7
        }, this);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-lg font-medium",
                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(pluginInfo.manifest.manifest.metadata.label)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                        lineNumber: 144,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-sm text-gray-500 pb-2",
                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(pluginInfo.manifest.manifest.metadata.description ?? {
                            en_US: '',
                            zh_Hans: ''
                        })
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                        lineNumber: 147,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "mb-4 flex flex-row items-center justify-start gap-[0.4rem]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                            components: (()=>{
                                const componentKindCount = {};
                                for (const component of pluginInfo.components){
                                    const kind = component.manifest.manifest.kind;
                                    if (componentKindCount[kind]) {
                                        componentKindCount[kind]++;
                                    } else {
                                        componentKindCount[kind] = 1;
                                    }
                                }
                                return componentKindCount;
                            })(),
                            showComponentName: true,
                            showTitle: false,
                            useBadge: true,
                            t: t
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                            lineNumber: 157,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                        lineNumber: 156,
                        columnNumber: 9
                    }, this),
                    pluginInfo.manifest.manifest.spec.config.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                        itemConfigList: pluginInfo.manifest.manifest.spec.config,
                        initialValues: pluginConfig.config,
                        onSubmit: (values)=>{
                            // 只保存表单值的引用,不触发状态更新
                            currentFormValues.current = values;
                        },
                        onFileUploaded: (fileKey)=>{
                            // 追踪上传的文件
                            uploadedFileKeys.current.add(fileKey);
                        }
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                        lineNumber: 178,
                        columnNumber: 11
                    }, this),
                    pluginInfo.manifest.manifest.spec.config.length === 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-sm text-gray-500",
                        children: t('plugins.pluginNoConfig')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                        lineNumber: 192,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                lineNumber: 143,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "sticky bottom-0 left-0 right-0 bg-background border-t p-4 mt-4",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex justify-end gap-2",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                            type: "submit",
                            onClick: ()=>handleSubmit(),
                            disabled: isSaving,
                            children: isSaving ? t('plugins.saving') : t('plugins.saveConfig')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                            lineNumber: 200,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                            type: "button",
                            variant: "outline",
                            onClick: onFormCancel,
                            children: t('plugins.cancel')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                            lineNumber: 207,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                    lineNumber: 199,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
                lineNumber: 198,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx",
        lineNumber: 142,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginReadme
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$markdown$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__Markdown__as__default$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-markdown/lib/index.js [app-ssr] (ecmascript) <export Markdown as default>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$remark$2d$gfm$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/remark-gfm/lib/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$raw$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-raw/lib/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$sanitize$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-sanitize/lib/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$highlight$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-highlight/lib/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$slug$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-slug/lib/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$autolink$2d$headings$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-autolink-headings/lib/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
;
;
;
;
;
;
function PluginReadme({ pluginAuthor, pluginName }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [readme, setReadme] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('');
    const [isLoadingReadme, setIsLoadingReadme] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const language = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getAPILanguageCode"])();
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        // Fetch plugin README
        setIsLoadingReadme(true);
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPluginReadme(pluginAuthor, pluginName, language).then((res)=>{
            setReadme(res.readme);
        }).catch(()=>{
            setReadme('');
        }).finally(()=>{
            setIsLoadingReadme(false);
        });
    }, [
        pluginAuthor,
        pluginName
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "w-full h-full overflow-auto",
        children: isLoadingReadme ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "p-6 text-sm text-gray-500 dark:text-gray-400",
            children: t('plugins.loadingReadme')
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
            lineNumber: 46,
            columnNumber: 9
        }, this) : readme ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "markdown-body p-6 max-w-none pt-0",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$markdown$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__Markdown__as__default$3e$__["default"], {
                remarkPlugins: [
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$remark$2d$gfm$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
                ],
                rehypePlugins: [
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$raw$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"],
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$sanitize$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"],
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$highlight$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"],
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$slug$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"],
                    [
                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$autolink$2d$headings$2f$lib$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"],
                        {
                            behavior: 'wrap',
                            properties: {
                                className: [
                                    'anchor'
                                ]
                            }
                        }
                    ]
                ],
                components: {
                    ul: ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("ul", {
                            className: "list-disc",
                            children: children
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
                            lineNumber: 69,
                            columnNumber: 37
                        }, void 0),
                    ol: ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("ol", {
                            className: "list-decimal",
                            children: children
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
                            lineNumber: 71,
                            columnNumber: 17
                        }, void 0),
                    li: ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                            className: "ml-4",
                            children: children
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
                            lineNumber: 73,
                            columnNumber: 37
                        }, void 0),
                    img: ({ src, alt, ...props })=>{
                        let imageSrc = src || '';
                        if (typeof imageSrc !== 'string') {
                            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                src: src,
                                alt: alt || '',
                                className: "max-w-full h-auto rounded-lg my-4",
                                ...props
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
                                lineNumber: 79,
                                columnNumber: 21
                            }, void 0);
                        }
                        if (imageSrc && !imageSrc.startsWith('http://') && !imageSrc.startsWith('https://') && !imageSrc.startsWith('data:')) {
                            imageSrc = imageSrc.replace(/^(\.\/|\/)+/, '');
                            if (!imageSrc.startsWith('assets/')) {
                                imageSrc = `assets/${imageSrc}`;
                            }
                            const assetPath = imageSrc.replace(/^assets\//, '');
                            imageSrc = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPluginAssetURL(pluginAuthor, pluginName, assetPath);
                        }
                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: imageSrc,
                            alt: alt || '',
                            className: "max-w-lg h-auto my-4",
                            ...props
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
                            lineNumber: 109,
                            columnNumber: 19
                        }, void 0);
                    }
                },
                children: readme
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
                lineNumber: 51,
                columnNumber: 11
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
            lineNumber: 50,
            columnNumber: 9
        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "p-6 text-sm text-gray-500 dark:text-gray-400",
            children: t('plugins.noReadme')
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
            lineNumber: 123,
            columnNumber: 9
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx",
        lineNumber: 44,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/plugins.module.css [app-ssr] (css module)", ((__turbopack_context__) => {

__turbopack_context__.v({
  "marketComponentBody": "plugins-module__lGF0uq__marketComponentBody",
  "pageContainer": "plugins-module__lGF0uq__pageContainer",
  "pluginListContainer": "plugins-module__lGF0uq__pluginListContainer",
});
}),
"[project]/coding/projects/LangBot/web/src/app/utils/versionCompare.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Compare two version strings and determine if the first is newer than the second.
 * Supports semantic versioning format (e.g., "1.2.3", "1.0.0-beta.1").
 *
 * @param version1 - The version to compare (potentially newer)
 * @param version2 - The version to compare against (base version)
 * @returns true if version1 is newer than version2, false otherwise
 */ __turbopack_context__.s([
    "isNewerVersion",
    ()=>isNewerVersion
]);
function isNewerVersion(version1, version2) {
    if (!version1 || !version2) {
        return false;
    }
    // Remove any leading 'v' prefix
    const v1 = version1.replace(/^v/, '');
    const v2 = version2.replace(/^v/, '');
    // Split into main version and pre-release parts
    const [main1, pre1] = v1.split('-');
    const [main2, pre2] = v2.split('-');
    // Split main version into numeric parts
    const parts1 = main1.split('.').map((p)=>parseInt(p, 10) || 0);
    const parts2 = main2.split('.').map((p)=>parseInt(p, 10) || 0);
    // Normalize length
    const maxLen = Math.max(parts1.length, parts2.length);
    while(parts1.length < maxLen)parts1.push(0);
    while(parts2.length < maxLen)parts2.push(0);
    // Compare main version parts
    for(let i = 0; i < maxLen; i++){
        if (parts1[i] > parts2[i]) return true;
        if (parts1[i] < parts2[i]) return false;
    }
    // Main versions are equal, compare pre-release
    // A version without pre-release is newer than one with pre-release
    if (!pre1 && pre2) return true;
    if (pre1 && !pre2) return false;
    if (!pre1 && !pre2) return false;
    // Both have pre-release, compare lexicographically
    return pre1 > pre2;
}
}),
"[project]/coding/projects/LangBot/web/src/hooks/useAsyncTask.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "AsyncTaskStatus",
    ()=>AsyncTaskStatus,
    "useAsyncTask",
    ()=>useAsyncTask
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
;
;
var AsyncTaskStatus = /*#__PURE__*/ function(AsyncTaskStatus) {
    AsyncTaskStatus["WAIT_INPUT"] = "WAIT_INPUT";
    AsyncTaskStatus["RUNNING"] = "RUNNING";
    AsyncTaskStatus["SUCCESS"] = "SUCCESS";
    AsyncTaskStatus["ERROR"] = "ERROR";
    return AsyncTaskStatus;
}({});
function useAsyncTask(options = {}) {
    const { onSuccess, onError, pollInterval = 1000 } = options;
    const [status, setStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])("WAIT_INPUT");
    const [error, setError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const intervalRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const alreadySuccessRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(false);
    const clearPollingInterval = ()=>{
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
    };
    const reset = ()=>{
        clearPollingInterval();
        setStatus("WAIT_INPUT");
        setError(null);
        alreadySuccessRef.current = false;
    };
    const startTask = (taskId)=>{
        setStatus("RUNNING");
        setError(null);
        alreadySuccessRef.current = false;
        const interval = setInterval(()=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getAsyncTask(taskId).then((res)=>{
                if (res.runtime.done) {
                    clearPollingInterval();
                    if (res.runtime.exception) {
                        setError(res.runtime.exception);
                        setStatus("ERROR");
                        onError?.(res.runtime.exception);
                    } else {
                        if (!alreadySuccessRef.current) {
                            alreadySuccessRef.current = true;
                            setStatus("SUCCESS");
                            onSuccess?.();
                        }
                    }
                }
            }).catch((error)=>{
                clearPollingInterval();
                const errorMessage = error.message || 'Unknown error';
                setError(errorMessage);
                setStatus("ERROR");
                onError?.(errorMessage);
            });
        }, pollInterval);
        intervalRef.current = interval;
    };
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        return ()=>{
            clearPollingInterval();
        };
    }, []);
    return {
        status,
        error,
        startTask,
        reset
    };
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginCardVO.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$plugin$2d$card$2f$PluginCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$plugin$2d$form$2f$PluginForm$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-form/PluginForm.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$plugin$2d$readme$2f$PluginReadme$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$plugins$2e$module$2e$css__$5b$app$2d$ssr$5d$__$28$css__module$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/plugins.module.css [app-ssr] (css module)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$utils$2f$versionCompare$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/utils/versionCompare.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/checkbox.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/hooks/useAsyncTask.ts [app-ssr] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
var PluginOperationType = /*#__PURE__*/ function(PluginOperationType) {
    PluginOperationType["DELETE"] = "DELETE";
    PluginOperationType["UPDATE"] = "UPDATE";
    return PluginOperationType;
}(PluginOperationType || {});
// eslint-disable-next-line react/display-name
const PluginInstalledComponent = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["forwardRef"])((props, ref)=>{
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [pluginList, setPluginList] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [detailModalOpen, setDetailModalOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [selectedPlugin, setSelectedPlugin] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [showOperationModal, setShowOperationModal] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [operationType, setOperationType] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])("DELETE");
    const [targetPlugin, setTargetPlugin] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [deleteData, setDeleteData] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const asyncTask = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useAsyncTask"])({
        onSuccess: ()=>{
            const successMessage = operationType === "DELETE" ? t('plugins.deleteSuccess') : t('plugins.updateSuccess');
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(successMessage);
            setShowOperationModal(false);
            getPluginList();
        },
        onError: ()=>{
        // Error is already handled in the hook state
        }
    });
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        initData();
    }, []);
    function initData() {
        getPluginList();
    }
    async function getPluginList() {
        try {
            // 获取已安装插件列表
            const installedPluginsResp = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPlugins();
            const installedPlugins = installedPluginsResp.plugins;
            // 获取市场插件列表
            const client = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])();
            const marketplaceResp = await client.getMarketplacePlugins(1, 100);
            const marketplacePlugins = marketplaceResp.plugins;
            // 创建市场插件映射，便于快速查找
            const marketplacePluginMap = new Map();
            marketplacePlugins.forEach((plugin)=>{
                const key = `${plugin.author}/${plugin.name}`;
                marketplacePluginMap.set(key, plugin);
            });
            // 转换并比较版本号
            const pluginCards = installedPlugins.map((plugin)=>{
                const cardVO = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PluginCardVO"]({
                    author: plugin.manifest.manifest.metadata.author ?? '',
                    label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.manifest.manifest.metadata.label),
                    description: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.manifest.manifest.metadata.description ?? {
                        en_US: '',
                        zh_Hans: ''
                    }),
                    debug: plugin.debug,
                    enabled: plugin.enabled,
                    name: plugin.manifest.manifest.metadata.name,
                    version: plugin.manifest.manifest.metadata.version ?? '',
                    status: plugin.status,
                    components: plugin.components,
                    priority: plugin.priority,
                    install_source: plugin.install_source,
                    install_info: plugin.install_info
                });
                // 检查是否来自市场且有更新
                if (cardVO.install_source === 'marketplace') {
                    const marketplaceKey = `${cardVO.author}/${cardVO.name}`;
                    const marketplacePlugin = marketplacePluginMap.get(marketplaceKey);
                    if (marketplacePlugin && marketplacePlugin.latest_version) {
                        cardVO.hasUpdate = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$utils$2f$versionCompare$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["isNewerVersion"])(marketplacePlugin.latest_version, cardVO.version);
                    }
                }
                return cardVO;
            });
            setPluginList(pluginCards);
        } catch (error) {
            console.error('获取插件列表失败:', error);
            // 失败时仍显示已安装插件，不影响用户体验
            const installedPluginsResp = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPlugins();
            setPluginList(installedPluginsResp.plugins.map((plugin)=>{
                return new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PluginCardVO"]({
                    author: plugin.manifest.manifest.metadata.author ?? '',
                    label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.manifest.manifest.metadata.label),
                    description: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.manifest.manifest.metadata.description ?? {
                        en_US: '',
                        zh_Hans: ''
                    }),
                    debug: plugin.debug,
                    enabled: plugin.enabled,
                    name: plugin.manifest.manifest.metadata.name,
                    version: plugin.manifest.manifest.metadata.version ?? '',
                    status: plugin.status,
                    components: plugin.components,
                    priority: plugin.priority,
                    install_source: plugin.install_source,
                    install_info: plugin.install_info
                });
            }));
        }
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useImperativeHandle"])(ref, ()=>({
            refreshPluginList: getPluginList
        }));
    function handlePluginClick(plugin) {
        setSelectedPlugin(plugin);
        setDetailModalOpen(true);
    }
    function handlePluginDelete(plugin) {
        setTargetPlugin(plugin);
        setOperationType("DELETE");
        setShowOperationModal(true);
        setDeleteData(false);
        asyncTask.reset();
    }
    function handlePluginUpdate(plugin) {
        setTargetPlugin(plugin);
        setOperationType("UPDATE");
        setShowOperationModal(true);
        asyncTask.reset();
    }
    function executeOperation() {
        if (!targetPlugin) return;
        const apiCall = operationType === "DELETE" ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].removePlugin(targetPlugin.author, targetPlugin.name, deleteData) : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].upgradePlugin(targetPlugin.author, targetPlugin.name);
        apiCall.then((res)=>{
            asyncTask.startTask(res.task_id);
        }).catch((error)=>{
            const errorMessage = operationType === "DELETE" ? t('plugins.deleteError') + error.message : t('plugins.updateError') + error.message;
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(errorMessage);
        });
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Dialog"], {
                open: showOperationModal,
                onOpenChange: (open)=>{
                    if (!open) {
                        setShowOperationModal(false);
                        setTargetPlugin(null);
                        asyncTask.reset();
                    }
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogContent"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                children: operationType === "DELETE" ? t('plugins.deleteConfirm') : t('plugins.updateConfirm')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                lineNumber: 224,
                                columnNumber: 15
                            }, ("TURBOPACK compile-time value", void 0))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                            lineNumber: 223,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogDescription"], {
                            children: [
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].WAIT_INPUT && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex flex-col gap-4",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            children: operationType === "DELETE" ? t('plugins.confirmDeletePlugin', {
                                                author: targetPlugin?.author ?? '',
                                                name: targetPlugin?.name ?? ''
                                            }) : t('plugins.confirmUpdatePlugin', {
                                                author: targetPlugin?.author ?? '',
                                                name: targetPlugin?.name ?? ''
                                            })
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                            lineNumber: 233,
                                            columnNumber: 19
                                        }, ("TURBOPACK compile-time value", void 0)),
                                        operationType === "DELETE" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex items-center space-x-2",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Checkbox"], {
                                                    id: "delete-data",
                                                    checked: deleteData,
                                                    onCheckedChange: (checked)=>setDeleteData(checked === true)
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                                    lineNumber: 246,
                                                    columnNumber: 23
                                                }, ("TURBOPACK compile-time value", void 0)),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                                    htmlFor: "delete-data",
                                                    className: "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer",
                                                    children: t('plugins.deleteDataCheckbox')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                                    lineNumber: 253,
                                                    columnNumber: 23
                                                }, ("TURBOPACK compile-time value", void 0))
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                            lineNumber: 245,
                                            columnNumber: 21
                                        }, ("TURBOPACK compile-time value", void 0))
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 232,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0)),
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].RUNNING && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    children: operationType === "DELETE" ? t('plugins.deleting') : t('plugins.updating')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 264,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0)),
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].ERROR && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    children: [
                                        operationType === "DELETE" ? t('plugins.deleteError') : t('plugins.updateError'),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "text-red-500",
                                            children: asyncTask.error
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                            lineNumber: 275,
                                            columnNumber: 19
                                        }, ("TURBOPACK compile-time value", void 0))
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 271,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                            lineNumber: 230,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogFooter"], {
                            children: [
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].WAIT_INPUT && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "outline",
                                    onClick: ()=>{
                                        setShowOperationModal(false);
                                        setTargetPlugin(null);
                                        asyncTask.reset();
                                    },
                                    children: t('plugins.cancel')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 281,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0)),
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].WAIT_INPUT && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: operationType === "DELETE" ? 'destructive' : 'default',
                                    onClick: ()=>{
                                        executeOperation();
                                    },
                                    children: operationType === "DELETE" ? t('plugins.confirmDelete') : t('plugins.confirmUpdate')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 293,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0)),
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].RUNNING && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: operationType === "DELETE" ? 'destructive' : 'default',
                                    disabled: true,
                                    children: operationType === "DELETE" ? t('plugins.deleting') : t('plugins.updating')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 309,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0)),
                                asyncTask.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$useAsyncTask$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["AsyncTaskStatus"].ERROR && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "default",
                                    onClick: ()=>{
                                        setShowOperationModal(false);
                                        asyncTask.reset();
                                    },
                                    children: t('plugins.close')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 323,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                            lineNumber: 279,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0))
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                    lineNumber: 222,
                    columnNumber: 11
                }, ("TURBOPACK compile-time value", void 0))
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                lineNumber: 212,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)),
            pluginList.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex flex-col items-center justify-center text-gray-500 min-h-[60vh] w-full gap-2",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                        className: "h-[3rem] w-[3rem]",
                        xmlns: "http://www.w3.org/2000/svg",
                        viewBox: "0 0 24 24",
                        fill: "currentColor",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                            d: "M7 5C7 2.79086 8.79086 1 11 1C13.2091 1 15 2.79086 15 5H20C20.5523 5 21 5.44772 21 6V10.1707C21 10.4953 20.8424 10.7997 20.5774 10.9872C20.3123 11.1746 19.9728 11.2217 19.6668 11.1135C19.4595 11.0403 19.2355 11 19 11C17.8954 11 17 11.8954 17 13C17 14.1046 17.8954 15 19 15C19.2355 15 19.4595 14.9597 19.6668 14.8865C19.9728 14.7783 20.3123 14.8254 20.5774 15.0128C20.8424 15.2003 21 15.5047 21 15.8293V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H7ZM11 3C9.89543 3 9 3.89543 9 5C9 5.23554 9.0403 5.45952 9.11355 5.66675C9.22172 5.97282 9.17461 6.31235 8.98718 6.57739C8.79974 6.84243 8.49532 7 8.17071 7H5V19H19V17C16.7909 17 15 15.2091 15 13C15 10.7909 16.7909 9 19 9V7H13.8293C13.5047 7 13.2003 6.84243 13.0128 6.57739C12.8254 6.31235 12.7783 5.97282 12.8865 5.66675C12.9597 5.45952 13 5.23555 13 5C13 3.89543 12.1046 3 11 3Z"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                            lineNumber: 345,
                            columnNumber: 15
                        }, ("TURBOPACK compile-time value", void 0))
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                        lineNumber: 339,
                        columnNumber: 13
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-lg mb-2",
                        children: t('plugins.noPluginInstalled')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                        lineNumber: 347,
                        columnNumber: 13
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                lineNumber: 338,
                columnNumber: 11
            }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$plugins$2e$module$2e$css__$5b$app$2d$ssr$5d$__$28$css__module$29$__["default"].pluginListContainer}`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Dialog"], {
                        open: detailModalOpen,
                        onOpenChange: setDetailModalOpen,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogContent"], {
                            className: "sm:max-w-[1100px] max-w-[95vw] max-h-[85vh] p-0 flex flex-col",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogHeader"], {
                                    className: "px-6 pt-6 pb-2 border-b",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                        children: selectedPlugin && `${selectedPlugin.author}/${selectedPlugin.name}`
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                        lineNumber: 354,
                                        columnNumber: 19
                                    }, ("TURBOPACK compile-time value", void 0))
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 353,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0)),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex-1 flex flex-row overflow-hidden min-h-0",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex-1 overflow-y-auto border-r min-w-0",
                                            children: selectedPlugin && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$plugin$2d$readme$2f$PluginReadme$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                                                pluginAuthor: selectedPlugin.author,
                                                pluginName: selectedPlugin.name
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                                lineNumber: 363,
                                                columnNumber: 23
                                            }, ("TURBOPACK compile-time value", void 0))
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                            lineNumber: 361,
                                            columnNumber: 19
                                        }, ("TURBOPACK compile-time value", void 0)),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "w-[380px] flex-shrink-0 overflow-y-auto px-4",
                                            children: selectedPlugin && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$plugin$2d$form$2f$PluginForm$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                                                pluginAuthor: selectedPlugin.author,
                                                pluginName: selectedPlugin.name,
                                                onFormSubmit: (timeout)=>{
                                                    setDetailModalOpen(false);
                                                    if (timeout) {
                                                        setTimeout(()=>{
                                                            getPluginList();
                                                        }, timeout);
                                                    } else {
                                                        getPluginList();
                                                    }
                                                },
                                                onFormCancel: ()=>{
                                                    setDetailModalOpen(false);
                                                }
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                                lineNumber: 372,
                                                columnNumber: 23
                                            }, ("TURBOPACK compile-time value", void 0))
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                            lineNumber: 370,
                                            columnNumber: 19
                                        }, ("TURBOPACK compile-time value", void 0))
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                    lineNumber: 359,
                                    columnNumber: 17
                                }, ("TURBOPACK compile-time value", void 0))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                            lineNumber: 352,
                            columnNumber: 15
                        }, ("TURBOPACK compile-time value", void 0))
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                        lineNumber: 351,
                        columnNumber: 13
                    }, ("TURBOPACK compile-time value", void 0)),
                    pluginList.map((vo, index)=>{
                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$plugin$2d$card$2f$PluginCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                                cardVO: vo,
                                onCardClick: ()=>handlePluginClick(vo),
                                onDeleteClick: ()=>handlePluginDelete(vo),
                                onUpgradeClick: ()=>handlePluginUpdate(vo)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                                lineNumber: 398,
                                columnNumber: 19
                            }, ("TURBOPACK compile-time value", void 0))
                        }, index, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                            lineNumber: 397,
                            columnNumber: 17
                        }, ("TURBOPACK compile-time value", void 0));
                    })
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx",
                lineNumber: 350,
                columnNumber: 11
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true);
});
const __TURBOPACK__default__export__ = PluginInstalledComponent;
}),
"[project]/coding/projects/LangBot/web/src/components/ui/toggle.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Toggle",
    ()=>Toggle,
    "toggleVariants",
    ()=>toggleVariants
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$toggle$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-toggle/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$class$2d$variance$2d$authority$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/class-variance-authority/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-ssr] (ecmascript)");
'use client';
;
;
;
;
const toggleVariants = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$class$2d$variance$2d$authority$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cva"])("inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium hover:bg-muted hover:text-muted-foreground disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-accent data-[state=on]:text-accent-foreground dark:data-[state=on]:bg-slate-700 dark:data-[state=on]:text-white [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] outline-none transition-[color,box-shadow] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive whitespace-nowrap", {
    variants: {
        variant: {
            default: 'bg-transparent',
            outline: 'border border-input bg-transparent shadow-xs hover:bg-accent hover:text-accent-foreground'
        },
        size: {
            default: 'h-9 px-2 min-w-9',
            sm: 'h-8 px-1.5 min-w-8',
            lg: 'h-10 px-2.5 min-w-10'
        }
    },
    defaultVariants: {
        variant: 'default',
        size: 'default'
    }
});
function Toggle({ className, variant, size, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$toggle$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Root"], {
        "data-slot": "toggle",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])(toggleVariants({
            variant,
            size,
            className
        })),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/toggle.tsx",
        lineNumber: 39,
        columnNumber: 5
    }, this);
}
;
}),
"[project]/coding/projects/LangBot/web/src/components/ui/toggle-group.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ToggleGroup",
    ()=>ToggleGroup,
    "ToggleGroupItem",
    ()=>ToggleGroupItem
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$toggle$2d$group$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-toggle-group/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/toggle.tsx [app-ssr] (ecmascript)");
'use client';
;
;
;
;
;
const ToggleGroupContext = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["createContext"]({
    size: 'default',
    variant: 'default',
    spacing: 0
});
function ToggleGroup({ className, variant, size, spacing = 0, children, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$toggle$2d$group$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Root"], {
        "data-slot": "toggle-group",
        "data-variant": variant,
        "data-size": size,
        "data-spacing": spacing,
        style: {
            '--gap': spacing
        },
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('group/toggle-group flex w-fit items-center gap-[--spacing(var(--gap))] rounded-md data-[spacing=default]:data-[variant=outline]:shadow-xs', className),
        ...props,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(ToggleGroupContext.Provider, {
            value: {
                variant,
                size,
                spacing
            },
            children: children
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/toggle-group.tsx",
            lineNumber: 44,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/toggle-group.tsx",
        lineNumber: 32,
        columnNumber: 5
    }, this);
}
function ToggleGroupItem({ className, children, variant, size, ...props }) {
    const context = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useContext"](ToggleGroupContext);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$toggle$2d$group$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Item"], {
        "data-slot": "toggle-group-item",
        "data-variant": context.variant || variant,
        "data-size": context.size || size,
        "data-spacing": context.spacing,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toggleVariants"])({
            variant: context.variant || variant,
            size: context.size || size
        }), 'w-auto min-w-0 shrink-0 px-3 focus:z-10 focus-visible:z-10', 'data-[spacing=0]:rounded-none data-[spacing=0]:shadow-none data-[spacing=0]:first:rounded-l-md data-[spacing=0]:last:rounded-r-md data-[spacing=0]:data-[variant=outline]:border-l-0 data-[spacing=0]:data-[variant=outline]:first:border-l', className),
        ...props,
        children: children
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/toggle-group.tsx",
        lineNumber: 62,
        columnNumber: 5
    }, this);
}
;
}),
"[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Tooltip",
    ()=>Tooltip,
    "TooltipContent",
    ()=>TooltipContent,
    "TooltipProvider",
    ()=>TooltipProvider,
    "TooltipTrigger",
    ()=>TooltipTrigger
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-tooltip/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-ssr] (ecmascript)");
'use client';
;
;
;
function TooltipProvider({ delayDuration = 0, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Provider"], {
        "data-slot": "tooltip-provider",
        delayDuration: delayDuration,
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
        lineNumber: 13,
        columnNumber: 5
    }, this);
}
function Tooltip({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(TooltipProvider, {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Root"], {
            "data-slot": "tooltip",
            ...props
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
            lineNumber: 26,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
        lineNumber: 25,
        columnNumber: 5
    }, this);
}
function TooltipTrigger({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Trigger"], {
        "data-slot": "tooltip-trigger",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
        lineNumber: 34,
        columnNumber: 10
    }, this);
}
function TooltipContent({ className, sideOffset = 0, children, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Portal"], {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Content"], {
            "data-slot": "tooltip-content",
            sideOffset: sideOffset,
            className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('bg-primary text-primary-foreground animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 w-fit origin-(--radix-tooltip-content-transform-origin) rounded-md px-3 py-1.5 text-xs text-balance', className),
            ...props,
            children: [
                children,
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Arrow"], {
                    className: "bg-primary fill-primary z-50 size-2.5 translate-y-[calc(-50%_-_2px)] rotate-45 rounded-[2px]"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
                    lineNumber: 55,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
            lineNumber: 45,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
        lineNumber: 44,
        columnNumber: 5
    }, this);
}
;
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginMarketCardComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-ssr] (ecmascript) <export default as Wrench>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/audio-waveform.js [app-ssr] (ecmascript) <export default as AudioWaveform>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/hash.js [app-ssr] (ecmascript) <export default as Hash>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$download$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Download$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/download.js [app-ssr] (ecmascript) <export default as Download>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$external$2d$link$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ExternalLink$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/external-link.js [app-ssr] (ecmascript) <export default as ExternalLink>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/book.js [app-ssr] (ecmascript) <export default as Book>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$file$2d$text$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__FileText$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/file-text.js [app-ssr] (ecmascript) <export default as FileText>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$info$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Info$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/info.js [app-ssr] (ecmascript) <export default as Info>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
function PluginMarketCardComponent({ cardVO, onInstall, tagNames = {} }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [isHovered, setIsHovered] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const bottomRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [visibleTags, setVisibleTags] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(2);
    // Measure how many tags fit in the bottom row
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const tags = cardVO.tags;
        if (!bottomRef.current || !tags || tags.length === 0) return;
        const measure = ()=>{
            const container = bottomRef.current;
            if (!container) return;
            const width = container.offsetWidth;
            const availableForTags = width - 140 - 80;
            if (availableForTags <= 0) {
                setVisibleTags(0);
                return;
            }
            const tagWidth = 80;
            const plusBadgeWidth = 40;
            const maxTags = Math.max(0, Math.floor((availableForTags - plusBadgeWidth) / tagWidth));
            if (maxTags >= tags.length) {
                setVisibleTags(tags.length);
            } else {
                setVisibleTags(Math.max(1, maxTags));
            }
        };
        measure();
        const observer = new ResizeObserver(measure);
        observer.observe(bottomRef.current);
        return ()=>observer.disconnect();
    }, [
        cardVO.tags
    ]);
    const remainingTags = cardVO.tags ? cardVO.tags.length - visibleTags : 0;
    function handleInstallClick(e) {
        e.stopPropagation();
        if (onInstall) {
            onInstall(cardVO.author, cardVO.pluginName);
        }
    }
    function handleViewDetailsClick(e) {
        e.stopPropagation();
        const detailUrl = `https://space.langbot.app/market/${cardVO.author}/${cardVO.pluginName}`;
        window.open(detailUrl, '_blank');
    }
    const kindIconMap = {
        Tool: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
            className: "w-4 h-4"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
            lineNumber: 86,
            columnNumber: 11
        }, this),
        EventListener: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__["AudioWaveform"], {
            className: "w-4 h-4"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
            lineNumber: 87,
            columnNumber: 20
        }, this),
        Command: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__["Hash"], {
            className: "w-4 h-4"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
            lineNumber: 88,
            columnNumber: 14
        }, this),
        KnowledgeEngine: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__["Book"], {
            className: "w-4 h-4"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
            lineNumber: 89,
            columnNumber: 22
        }, this),
        Parser: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$file$2d$text$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__FileText$3e$__["FileText"], {
            className: "w-4 h-4"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
            lineNumber: 90,
            columnNumber: 13
        }, this)
    };
    // Plugins that only contain KnowledgeRetriever components are deprecated
    const isDeprecated = (()=>{
        if (!cardVO.components) return false;
        const keys = Object.keys(cardVO.components);
        return keys.length > 0 && keys.every((k)=>k === 'KnowledgeRetriever');
    })();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "w-[100%] h-auto min-h-[8rem] sm:min-h-[9rem] bg-white rounded-[10px] shadow-[0px_0px_4px_0_rgba(0,0,0,0.2)] p-3 sm:p-[1rem] hover:shadow-[0px_3px_6px_0_rgba(0,0,0,0.12)] transition-all duration-200 hover:scale-[1.005] dark:bg-[#1f1f22] relative",
        onMouseEnter: ()=>setIsHovered(true),
        onMouseLeave: ()=>setIsHovered(false),
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "w-full h-full flex flex-col justify-between gap-3",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex flex-row items-start justify-start gap-2 sm:gap-[1.2rem] min-h-0",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                src: cardVO.iconURL,
                                alt: "plugin icon",
                                className: "w-12 h-12 sm:w-16 sm:h-16 flex-shrink-0 rounded-[8%]"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 109,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex-1 flex flex-col items-start justify-start gap-[0.4rem] sm:gap-[0.6rem] min-w-0 overflow-hidden",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex flex-col items-start justify-start w-full min-w-0",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-[0.65rem] sm:text-[0.7rem] text-[#666] dark:text-[#999] truncate w-full",
                                                children: cardVO.pluginId
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                lineNumber: 117,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex items-center gap-1.5 w-full min-w-0",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "text-base sm:text-[1.2rem] text-black dark:text-[#f0f0f0] truncate",
                                                        children: cardVO.label
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                        lineNumber: 121,
                                                        columnNumber: 17
                                                    }, this),
                                                    isDeprecated && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TooltipProvider"], {
                                                        delayDuration: 200,
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Tooltip"], {
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TooltipTrigger"], {
                                                                    asChild: true,
                                                                    onClick: (e)=>e.preventDefault(),
                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                                        variant: "outline",
                                                                        className: "text-[0.6rem] px-1.5 py-0 h-4 flex-shrink-0 border-red-400 text-red-500 dark:border-red-500 dark:text-red-400 gap-0.5 cursor-help",
                                                                        children: [
                                                                            t('market.deprecated'),
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$info$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Info$3e$__["Info"], {
                                                                                className: "w-2.5 h-2.5"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                                                lineNumber: 136,
                                                                                columnNumber: 27
                                                                            }, this)
                                                                        ]
                                                                    }, void 0, true, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                                        lineNumber: 131,
                                                                        columnNumber: 25
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                                    lineNumber: 127,
                                                                    columnNumber: 23
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TooltipContent"], {
                                                                    side: "top",
                                                                    className: "max-w-[240px] text-xs",
                                                                    children: t('market.deprecatedTooltip')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                                    lineNumber: 139,
                                                                    columnNumber: 23
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                            lineNumber: 126,
                                                            columnNumber: 21
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                        lineNumber: 125,
                                                        columnNumber: 19
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                lineNumber: 120,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                        lineNumber: 116,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-[0.7rem] sm:text-[0.8rem] text-[#666] dark:text-[#999] line-clamp-2 overflow-hidden",
                                        children: cardVO.description
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                        lineNumber: 151,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 115,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-start justify-center gap-[0.4rem] flex-shrink-0",
                                children: cardVO.githubURL && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                    className: "w-5 h-5 sm:w-[1.4rem] sm:h-[1.4rem] text-black cursor-pointer hover:text-gray-600 dark:text-[#f0f0f0] flex-shrink-0",
                                    xmlns: "http://www.w3.org/2000/svg",
                                    viewBox: "0 0 24 24",
                                    fill: "currentColor",
                                    onClick: (e)=>{
                                        e.stopPropagation();
                                        window.open(cardVO.githubURL, '_blank');
                                    },
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                        d: "M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                        lineNumber: 168,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                    lineNumber: 158,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 156,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                        lineNumber: 108,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        ref: bottomRef,
                        className: "w-full flex flex-row items-center justify-between gap-2 px-0 sm:px-[0.4rem] flex-shrink-0 overflow-hidden",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center justify-start gap-2 min-w-0 overflow-hidden",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex flex-row items-center gap-[0.3rem] sm:gap-[0.4rem] flex-shrink-0",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                className: "w-4 h-4 sm:w-[1.2rem] sm:h-[1.2rem] text-[#2563eb] dark:text-[#5b8def] flex-shrink-0",
                                                xmlns: "http://www.w3.org/2000/svg",
                                                viewBox: "0 0 24 24",
                                                fill: "none",
                                                stroke: "currentColor",
                                                strokeWidth: "2",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                        d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                        lineNumber: 190,
                                                        columnNumber: 17
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("polyline", {
                                                        points: "7,10 12,15 17,10"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                        lineNumber: 191,
                                                        columnNumber: 17
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("line", {
                                                        x1: "12",
                                                        y1: "15",
                                                        x2: "12",
                                                        y2: "3"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                        lineNumber: 192,
                                                        columnNumber: 17
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                lineNumber: 182,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-xs sm:text-sm text-[#2563eb] dark:text-[#5b8def] font-medium whitespace-nowrap",
                                                children: cardVO.installCount?.toLocaleString() ?? '0'
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                lineNumber: 194,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                        lineNumber: 181,
                                        columnNumber: 13
                                    }, this),
                                    cardVO.tags && cardVO.tags.length > 0 && visibleTags > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex flex-row items-center gap-1.5 overflow-hidden flex-shrink min-w-0",
                                        children: [
                                            cardVO.tags.slice(0, visibleTags).map((tag)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                    variant: "secondary",
                                                    className: "text-[0.65rem] sm:text-[0.7rem] px-2 py-0.5 h-5 flex items-center gap-1 flex-shrink-0 whitespace-nowrap",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                            className: "w-2.5 h-2.5 flex-shrink-0",
                                                            xmlns: "http://www.w3.org/2000/svg",
                                                            viewBox: "0 0 24 24",
                                                            fill: "none",
                                                            stroke: "currentColor",
                                                            strokeWidth: "2",
                                                            strokeLinecap: "round",
                                                            strokeLinejoin: "round",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                                    d: "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                                    lineNumber: 218,
                                                                    columnNumber: 23
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("line", {
                                                                    x1: "7",
                                                                    y1: "7",
                                                                    x2: "7.01",
                                                                    y2: "7"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                                    lineNumber: 219,
                                                                    columnNumber: 23
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                            lineNumber: 208,
                                                            columnNumber: 21
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: "truncate max-w-[5rem]",
                                                            children: tagNames[tag] || tag
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                            lineNumber: 221,
                                                            columnNumber: 21
                                                        }, this)
                                                    ]
                                                }, tag, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                    lineNumber: 203,
                                                    columnNumber: 19
                                                }, this)),
                                            remainingTags > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                                variant: "outline",
                                                className: "text-[0.65rem] sm:text-[0.7rem] px-1.5 py-0.5 h-5 flex items-center flex-shrink-0 whitespace-nowrap",
                                                children: [
                                                    "+",
                                                    remainingTags
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                lineNumber: 227,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                        lineNumber: 201,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 179,
                                columnNumber: 11
                            }, this),
                            cardVO.components && Object.keys(cardVO.components).length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center gap-1",
                                children: Object.entries(cardVO.components).map(([kind, count])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                        variant: "outline",
                                        className: "flex items-center gap-1",
                                        children: [
                                            kindIconMap[kind],
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "ml-1",
                                                children: count
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                                lineNumber: 248,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, kind, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                        lineNumber: 242,
                                        columnNumber: 17
                                    }, this))
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 240,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                        lineNumber: 175,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                lineNumber: 106,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `absolute inset-0 bg-gray-100/55 dark:bg-black/35 rounded-[10px] flex items-center justify-center gap-3 transition-all duration-200 ${isHovered ? 'opacity-100' : 'opacity-0 pointer-events-none'}`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                        onClick: handleInstallClick,
                        className: `bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 transition-all duration-200 ${isHovered ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'}`,
                        style: {
                            transitionDelay: isHovered ? '10ms' : '0ms'
                        },
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$download$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Download$3e$__["Download"], {
                                className: "w-4 h-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 269,
                                columnNumber: 11
                            }, this),
                            t('market.install')
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                        lineNumber: 262,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                        onClick: handleViewDetailsClick,
                        variant: "outline",
                        className: `bg-white hover:bg-gray-100 text-gray-900 dark:bg-white dark:hover:bg-gray-100 dark:text-gray-900 px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 transition-all duration-200 ${isHovered ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'}`,
                        style: {
                            transitionDelay: isHovered ? '20ms' : '0ms'
                        },
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$external$2d$link$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ExternalLink$3e$__["ExternalLink"], {
                                className: "w-4 h-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                                lineNumber: 280,
                                columnNumber: 11
                            }, this),
                            t('market.viewDetails')
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                        lineNumber: 272,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
                lineNumber: 257,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx",
        lineNumber: 101,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardVO.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PluginMarketCardVO",
    ()=>PluginMarketCardVO
]);
class PluginMarketCardVO {
    pluginId;
    description;
    label;
    author;
    pluginName;
    iconURL;
    githubURL;
    installCount;
    version;
    components;
    tags;
    constructor(prop){
        this.description = prop.description;
        this.label = prop.label;
        this.author = prop.author;
        this.pluginName = prop.pluginName;
        this.iconURL = prop.iconURL;
        this.githubURL = prop.githubURL;
        this.installCount = prop.installCount;
        this.pluginId = prop.pluginId;
        this.version = prop.version;
        this.components = prop.components;
        this.tags = prop.tags;
    }
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LoadingInline",
    ()=>LoadingInline,
    "LoadingPage",
    ()=>LoadingPage,
    "LoadingSpinner",
    ()=>LoadingSpinner
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/loader-circle.js [app-ssr] (ecmascript) <export default as Loader2>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-ssr] (ecmascript)");
;
;
;
const sizeMap = {
    sm: 'h-4 w-4',
    default: 'h-8 w-8',
    lg: 'h-12 w-12'
};
const textSizeMap = {
    sm: 'text-xs',
    default: 'text-sm',
    lg: 'text-base'
};
function LoadingSpinner({ size = 'default', className, text = '加载中...', fullPage = false }) {
    const spinner = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "flex flex-col items-center gap-4",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__["Loader2"], {
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('animate-spin text-primary', sizeMap[size], className)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
                lineNumber: 45,
                columnNumber: 7
            }, this),
            text && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["cn"])('text-muted-foreground', textSizeMap[size]),
                children: text
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
                lineNumber: 49,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 44,
        columnNumber: 5
    }, this);
    if (fullPage) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "fixed inset-0 flex items-center justify-center bg-background",
            children: spinner
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
            lineNumber: 56,
            columnNumber: 7
        }, this);
    }
    return spinner;
}
function LoadingPage({ text }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingSpinner, {
        fullPage: true,
        text: text
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 69,
        columnNumber: 10
    }, this);
}
function LoadingInline({ size, text }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingSpinner, {
        size: size,
        text: text
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 82,
        columnNumber: 10
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TagsFilter",
    ()=>TagsFilter
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/select.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/checkbox.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$label$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/label.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$tag$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Tag$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/tag.js [app-ssr] (ecmascript) <export default as Tag>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
function TagsFilter({ availableTags, selectedTags, onTagsChange }) {
    const { t, i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [open, setOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const handleTagToggle = (tag)=>{
        const newTags = selectedTags.includes(tag) ? selectedTags.filter((t)=>t !== tag) : [
            ...selectedTags,
            tag
        ];
        onTagsChange(newTags);
    };
    const handleClearAll = ()=>{
        onTagsChange([]);
    };
    const extractI18nObject = (obj)=>{
        const lang = i18n.language || 'en_US';
        return obj[lang] || obj.zh_Hans || obj.en_US || '';
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
        open: open,
        onOpenChange: setOpen,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                className: "w-[140px]",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex items-center gap-2 w-full",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$tag$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Tag$3e$__["Tag"], {
                            className: "h-4 w-4 flex-shrink-0"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                            lineNumber: 51,
                            columnNumber: 11
                        }, this),
                        selectedTags.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "text-muted-foreground truncate text-sm",
                            children: t('market.tags.filterByTags')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                            lineNumber: 53,
                            columnNumber: 13
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "text-sm truncate",
                            children: [
                                selectedTags.length,
                                " ",
                                t('market.tags.selected')
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                            lineNumber: 57,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                    lineNumber: 50,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                lineNumber: 49,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                className: "w-[240px]",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectGroup"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "px-2 py-1.5 flex items-center justify-between border-b",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "text-sm font-medium",
                                    children: t('market.tags.selectTags')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                                    lineNumber: 66,
                                    columnNumber: 13
                                }, this),
                                selectedTags.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "ghost",
                                    size: "sm",
                                    onClick: handleClearAll,
                                    className: "h-auto p-0 text-xs hover:bg-transparent hover:text-destructive",
                                    children: t('market.tags.clearAll')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                                    lineNumber: 70,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                            lineNumber: 65,
                            columnNumber: 11
                        }, this),
                        availableTags.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "px-2 py-6 text-center text-sm text-muted-foreground",
                            children: t('market.tags.noTags')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                            lineNumber: 82,
                            columnNumber: 13
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "max-h-[300px] overflow-y-auto",
                            children: availableTags.map((tag)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center space-x-2 px-2 py-2 hover:bg-accent cursor-pointer",
                                    onClick: (e)=>{
                                        e.preventDefault();
                                        handleTagToggle(tag.tag);
                                    },
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Checkbox"], {
                                            id: `tag-${tag.tag}`,
                                            checked: selectedTags.includes(tag.tag),
                                            onClick: (e)=>e.stopPropagation(),
                                            onCheckedChange: ()=>handleTagToggle(tag.tag)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                                            lineNumber: 96,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$label$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Label"], {
                                            htmlFor: `tag-${tag.tag}`,
                                            className: "text-sm font-normal cursor-pointer flex-1",
                                            onClick: (e)=>e.preventDefault(),
                                            children: extractI18nObject(tag.display_name)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                                            lineNumber: 102,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, tag.tag, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                                    lineNumber: 88,
                                    columnNumber: 17
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                            lineNumber: 86,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                    lineNumber: 64,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
                lineNumber: 63,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx",
        lineNumber: 48,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "RecommendationLists",
    ()=>RecommendationLists
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$left$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronLeft$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-left.js [app-ssr] (ecmascript) <export default as ChevronLeft>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-right.js [app-ssr] (ecmascript) <export default as ChevronRight>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$star$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Star$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/star.js [app-ssr] (ecmascript) <export default as Star>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardVO.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
;
// Match the main plugin grid: grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4
function pluginToVO(plugin, t) {
    return new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PluginMarketCardVO"]({
        pluginId: plugin.author + ' / ' + plugin.name,
        author: plugin.author,
        pluginName: plugin.name,
        label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.label),
        description: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.description) || t('market.noDescription'),
        installCount: plugin.install_count,
        iconURL: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().getPluginIconURL(plugin.author, plugin.name),
        githubURL: plugin.repository,
        version: plugin.latest_version,
        components: plugin.components,
        tags: plugin.tags || []
    });
}
function RecommendationListRow({ list, tagNames, onInstall, isLast }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [page, setPage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(0);
    const [perPage, setPerPage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(4);
    const gridRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const plugins = list.plugins || [];
    // Measure how many columns the CSS grid actually renders
    const measureCols = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        if (!gridRef.current) return;
        const style = window.getComputedStyle(gridRef.current);
        const cols = style.gridTemplateColumns.split(' ').length;
        setPerPage(cols);
    }, []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        measureCols();
        const observer = new ResizeObserver(measureCols);
        if (gridRef.current) observer.observe(gridRef.current);
        return ()=>observer.disconnect();
    }, [
        measureCols
    ]);
    // Auto-advance every 5 seconds
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (plugins.length <= perPage) return;
        const timer = setInterval(()=>{
            setPage((p)=>{
                const tp = Math.max(1, Math.ceil(plugins.length / perPage));
                return p >= tp - 1 ? 0 : p + 1;
            });
        }, 5000);
        return ()=>clearInterval(timer);
    }, [
        plugins.length,
        perPage
    ]);
    const totalPages = Math.max(1, Math.ceil(plugins.length / perPage));
    const safePage = Math.min(page, totalPages - 1);
    if (safePage !== page) setPage(safePage);
    const start = safePage * perPage;
    const visiblePlugins = plugins.slice(start, start + perPage);
    if (plugins.length === 0) return null;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "mb-6",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex items-center justify-between mb-3",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center gap-2",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$star$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Star$3e$__["Star"], {
                                className: "w-4 h-4 text-yellow-500"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                lineNumber: 104,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                className: "font-semibold text-base",
                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(list.label)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                lineNumber: 105,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                        lineNumber: 103,
                        columnNumber: 9
                    }, this),
                    totalPages > 1 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center gap-1",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                variant: "ghost",
                                size: "sm",
                                onClick: ()=>setPage((p)=>Math.max(0, p - 1)),
                                disabled: safePage === 0,
                                className: "h-7 w-7 p-0",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$left$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronLeft$3e$__["ChevronLeft"], {
                                    className: "w-4 h-4"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                    lineNumber: 118,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                lineNumber: 111,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "text-xs text-muted-foreground px-1",
                                children: [
                                    safePage + 1,
                                    " / ",
                                    totalPages
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                lineNumber: 120,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                variant: "ghost",
                                size: "sm",
                                onClick: ()=>setPage((p)=>Math.min(totalPages - 1, p + 1)),
                                disabled: safePage >= totalPages - 1,
                                className: "h-7 w-7 p-0",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__["ChevronRight"], {
                                    className: "w-4 h-4"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                    lineNumber: 130,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                                lineNumber: 123,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                        lineNumber: 110,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                lineNumber: 102,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                ref: gridRef,
                className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6",
                children: visiblePlugins.map((plugin)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                        cardVO: pluginToVO(plugin, t),
                        tagNames: tagNames,
                        onInstall: onInstall
                    }, plugin.author + ' / ' + plugin.name, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                        lineNumber: 140,
                        columnNumber: 11
                    }, this))
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                lineNumber: 135,
                columnNumber: 7
            }, this),
            totalPages > 1 && !isLast && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "border-b border-border mt-6"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                lineNumber: 149,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
        lineNumber: 101,
        columnNumber: 5
    }, this);
}
function RecommendationLists({ lists, tagNames, onInstall }) {
    if (!lists || lists.length === 0) return null;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "mt-6",
        children: [
            lists.map((list, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(RecommendationListRow, {
                    list: list,
                    tagNames: tagNames,
                    onInstall: onInstall,
                    isLast: index === lists.length - 1
                }, list.uuid, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                    lineNumber: 169,
                    columnNumber: 9
                }, this)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "border-b border-border mb-6"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
                lineNumber: 177,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx",
        lineNumber: 167,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>MarketPage
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/select.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/toggle-group.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$search$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Search$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/search.js [app-ssr] (ecmascript) <export default as Search>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-ssr] (ecmascript) <export default as Wrench>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/audio-waveform.js [app-ssr] (ecmascript) <export default as AudioWaveform>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/hash.js [app-ssr] (ecmascript) <export default as Hash>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/book.js [app-ssr] (ecmascript) <export default as Book>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$file$2d$text$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__FileText$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/file-text.js [app-ssr] (ecmascript) <export default as FileText>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardVO.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$TagsFilter$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/TagsFilter.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$RecommendationLists$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/RecommendationLists.tsx [app-ssr] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
// 内部组件，用于处理搜索参数
function MarketPageContent({ installPlugin }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [searchQuery, setSearchQuery] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('');
    const [componentFilter, setComponentFilter] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('all');
    const [selectedTags, setSelectedTags] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [availableTags, setAvailableTags] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [tagNames, setTagNames] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])({});
    const [plugins, setPlugins] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [isLoading, setIsLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [isLoadingMore, setIsLoadingMore] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [hasMore, setHasMore] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(true);
    const [currentPage, setCurrentPage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(1);
    const [total, setTotal] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(0);
    const [sortOption, setSortOption] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('install_count_desc');
    const [recommendationLists, setRecommendationLists] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const pageSize = 12; // 每页12个
    const searchTimeoutRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const scrollContainerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    // 排序选项
    const sortOptions = [
        {
            value: 'created_at_desc',
            label: t('market.sort.recentlyAdded'),
            sortBy: 'created_at',
            sortOrder: 'DESC'
        },
        {
            value: 'updated_at_desc',
            label: t('market.sort.recentlyUpdated'),
            sortBy: 'updated_at',
            sortOrder: 'DESC'
        },
        {
            value: 'install_count_desc',
            label: t('market.sort.mostDownloads'),
            sortBy: 'install_count',
            sortOrder: 'DESC'
        },
        {
            value: 'install_count_asc',
            label: t('market.sort.leastDownloads'),
            sortBy: 'install_count',
            sortOrder: 'ASC'
        }
    ];
    // 获取当前排序参数
    const getCurrentSort = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        const option = sortOptions.find((opt)=>opt.value === sortOption);
        return option ? {
            sortBy: option.sortBy,
            sortOrder: option.sortOrder
        } : {
            sortBy: 'install_count',
            sortOrder: 'DESC'
        };
    }, [
        sortOption
    ]);
    // 将API响应转换为VO对象
    const transformToVO = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((plugin)=>{
        return new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PluginMarketCardVO"]({
            pluginId: plugin.author + ' / ' + plugin.name,
            author: plugin.author,
            pluginName: plugin.name,
            label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.label),
            description: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(plugin.description) || t('market.noDescription'),
            installCount: plugin.install_count,
            iconURL: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().getPluginIconURL(plugin.author, plugin.name),
            githubURL: plugin.repository,
            version: plugin.latest_version,
            components: plugin.components,
            tags: plugin.tags || []
        });
    }, []);
    // 获取插件列表
    const fetchPlugins = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async (page, isSearch = false, reset = false)=>{
        if (page === 1) {
            setIsLoading(true);
        } else {
            setIsLoadingMore(true);
        }
        try {
            const { sortBy, sortOrder } = getCurrentSort();
            const filterValue = componentFilter === 'all' ? undefined : componentFilter;
            // Always use searchMarketplacePlugins to support component filtering and tags filtering
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().searchMarketplacePlugins(isSearch && searchQuery.trim() ? searchQuery.trim() : '', page, pageSize, sortBy, sortOrder, filterValue, selectedTags.length > 0 ? selectedTags : undefined);
            const data = response;
            const newPlugins = data.plugins.map(transformToVO);
            const total = data.total;
            if (reset || page === 1) {
                setPlugins(newPlugins);
            } else {
                setPlugins((prev)=>[
                        ...prev,
                        ...newPlugins
                    ]);
            }
            setTotal(total);
            setHasMore(data.plugins.length === pageSize && plugins.length + newPlugins.length < total);
        } catch (error) {
            console.error('Failed to fetch plugins:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('market.loadFailed'));
        } finally{
            setIsLoading(false);
            setIsLoadingMore(false);
        }
    }, [
        searchQuery,
        componentFilter,
        selectedTags,
        pageSize,
        transformToVO,
        plugins.length,
        getCurrentSort
    ]);
    // 初始加载
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        fetchPlugins(1, false, true);
        fetchAvailableTags();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    // 获取可用标签
    const fetchAvailableTags = async ()=>{
        try {
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().getAllTags();
            const tags = response.tags || [];
            setAvailableTags(tags);
            // Build tag names map for all components to use
            const nameMap = {};
            tags.forEach((tag)=>{
                const displayName = {
                    en_US: tag.display_name.en_US || tag.tag,
                    zh_Hans: tag.display_name.zh_Hans || tag.tag,
                    zh_Hant: tag.display_name.zh_Hant,
                    ja_JP: tag.display_name.ja_JP
                };
                nameMap[tag.tag] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["extractI18nObject"])(displayName);
            });
            setTagNames(nameMap);
        } catch (error) {
            console.error('Failed to fetch tags:', error);
        }
    };
    // Fetch recommendation lists
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        async function fetchRecommendationLists() {
            try {
                const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().getRecommendationLists();
                setRecommendationLists(response.lists || []);
            } catch (error) {
                console.error('Failed to fetch recommendation lists:', error);
            }
        }
        fetchRecommendationLists();
    }, []);
    // 搜索功能
    const handleSearch = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((query)=>{
        setSearchQuery(query);
        setCurrentPage(1);
        setPlugins([]);
        fetchPlugins(1, !!query.trim(), true);
    }, [
        fetchPlugins
    ]);
    // 防抖搜索
    const handleSearchInputChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((value)=>{
        setSearchQuery(value);
        // 清除之前的定时器
        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }
        // 设置新的定时器
        searchTimeoutRef.current = setTimeout(()=>{
            handleSearch(value);
        }, 300);
    }, [
        handleSearch
    ]);
    // 排序选项变化处理
    const handleSortChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((value)=>{
        setSortOption(value);
        setCurrentPage(1);
        setPlugins([]);
    // fetchPlugins will be called by useEffect when sortOption changes
    }, []);
    // 组件筛选变化处理
    const handleComponentFilterChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((value)=>{
        setComponentFilter(value);
        setCurrentPage(1);
        setPlugins([]);
    // fetchPlugins will be called by useEffect when componentFilter changes
    }, []);
    // 当排序选项或组件筛选变化时重新加载数据
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        fetchPlugins(1, !!searchQuery.trim(), true);
    }, [
        sortOption,
        componentFilter
    ]);
    // Tags 筛选变化时重新搜索
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (!isLoading) {
            setCurrentPage(1);
            fetchPlugins(1, searchQuery.trim() !== '', true);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        selectedTags
    ]);
    // 处理 tags 变化
    const handleTagsChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((tags)=>{
        setSelectedTags(tags);
    }, []);
    // 处理安装插件
    const handleInstallPlugin = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async (author, pluginName)=>{
        try {
            // Fetch full plugin details to get PluginV4 object
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCloudServiceClientSync"])().getPluginDetail(author, pluginName);
            const pluginV4 = response.plugin;
            // Call the install function passed from parent
            installPlugin(pluginV4);
        } catch (error) {
            console.error('Failed to install plugin:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('market.installFailed'));
        }
    }, [
        plugins,
        installPlugin,
        t
    ]);
    // 清理定时器
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        return ()=>{
            if (searchTimeoutRef.current) {
                clearTimeout(searchTimeoutRef.current);
            }
        };
    }, []);
    const visiblePlugins = plugins;
    // 加载更多
    const loadMore = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        if (!isLoadingMore && hasMore) {
            const nextPage = currentPage + 1;
            setCurrentPage(nextPage);
            fetchPlugins(nextPage, !!searchQuery.trim());
        }
    }, [
        currentPage,
        isLoadingMore,
        hasMore,
        fetchPlugins,
        searchQuery
    ]);
    // Check if content fills the viewport and load more if needed
    const checkAndLoadMore = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(()=>{
        const scrollContainer = scrollContainerRef.current;
        if (!scrollContainer || isLoading || isLoadingMore || !hasMore) return;
        const { scrollHeight, clientHeight } = scrollContainer;
        // If content doesn't fill the viewport (no scrollbar), load more
        if (scrollHeight <= clientHeight) {
            loadMore();
        }
    }, [
        loadMore,
        isLoading,
        isLoadingMore,
        hasMore
    ]);
    // Listen to scroll events on the scroll container
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const scrollContainer = scrollContainerRef.current;
        if (!scrollContainer) return;
        const handleScroll = ()=>{
            const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
            // Load more when scrolled to within 100px of the bottom
            if (scrollTop + clientHeight >= scrollHeight - 100) {
                loadMore();
            }
        };
        scrollContainer.addEventListener('scroll', handleScroll);
        return ()=>scrollContainer.removeEventListener('scroll', handleScroll);
    }, [
        loadMore
    ]);
    // Check if we need to load more after content changes or initial load
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        // Small delay to ensure DOM has updated
        const timer = setTimeout(()=>{
            checkAndLoadMore();
        }, 100);
        return ()=>clearTimeout(timer);
    }, [
        plugins,
        checkAndLoadMore
    ]);
    // Also check on window resize
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const handleResize = ()=>{
            checkAndLoadMore();
        };
        window.addEventListener('resize', handleResize);
        return ()=>window.removeEventListener('resize', handleResize);
    }, [
        checkAndLoadMore
    ]);
    // 安装插件
    // const handleInstallPlugin = (plugin: PluginV4) => {
    // };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "h-full flex flex-col",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex-shrink-0 space-y-4 px-3 sm:px-4 py-4 sm:py-6",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex flex-col sm:flex-row items-center justify-center gap-3",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "relative w-full max-w-2xl",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$search$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Search$3e$__["Search"], {
                                        className: "absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 396,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                        placeholder: t('market.searchPlaceholder'),
                                        value: searchQuery,
                                        onChange: (e)=>handleSearchInputChange(e.target.value),
                                        onKeyPress: (e)=>{
                                            if (e.key === 'Enter') {
                                                // Immediately search, clear debounce timer
                                                if (searchTimeoutRef.current) {
                                                    clearTimeout(searchTimeoutRef.current);
                                                }
                                                handleSearch(searchQuery);
                                            }
                                        },
                                        className: "pl-10 pr-4 text-sm sm:text-base"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 397,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 395,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$TagsFilter$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TagsFilter"], {
                                availableTags: availableTags,
                                selectedTags: selectedTags,
                                onTagsChange: handleTagsChange
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 415,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                        lineNumber: 394,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 px-3 sm:px-4",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-col sm:flex-row items-center gap-2",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "text-xs sm:text-sm text-muted-foreground whitespace-nowrap",
                                        children: [
                                            t('market.filterByComponent'),
                                            ":"
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 426,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroup"], {
                                        type: "single",
                                        spacing: 2,
                                        size: "sm",
                                        value: componentFilter,
                                        onValueChange: (value)=>{
                                            if (value) handleComponentFilterChange(value);
                                        },
                                        className: "justify-start",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroupItem"], {
                                                value: "all",
                                                "aria-label": "All components",
                                                className: "text-xs sm:text-sm cursor-pointer",
                                                children: t('market.allComponents')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 439,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroupItem"], {
                                                value: "Tool",
                                                "aria-label": "Tool",
                                                className: "text-xs sm:text-sm cursor-pointer",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                                        className: "h-4 w-4 mr-1"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                        lineNumber: 451,
                                                        columnNumber: 17
                                                    }, this),
                                                    t('plugins.componentName.Tool')
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 446,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroupItem"], {
                                                value: "Command",
                                                "aria-label": "Command",
                                                className: "text-xs sm:text-sm cursor-pointer",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__["Hash"], {
                                                        className: "h-4 w-4 mr-1"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                        lineNumber: 459,
                                                        columnNumber: 17
                                                    }, this),
                                                    t('plugins.componentName.Command')
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 454,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroupItem"], {
                                                value: "EventListener",
                                                "aria-label": "EventListener",
                                                className: "text-xs sm:text-sm cursor-pointer",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__["AudioWaveform"], {
                                                        className: "h-4 w-4 mr-1"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                        lineNumber: 467,
                                                        columnNumber: 17
                                                    }, this),
                                                    t('plugins.componentName.EventListener')
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 462,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroupItem"], {
                                                value: "KnowledgeEngine",
                                                "aria-label": "KnowledgeEngine",
                                                className: "text-xs sm:text-sm cursor-pointer",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__["Book"], {
                                                        className: "h-4 w-4 mr-1"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                        lineNumber: 475,
                                                        columnNumber: 17
                                                    }, this),
                                                    t('plugins.componentName.KnowledgeEngine')
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 470,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$toggle$2d$group$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ToggleGroupItem"], {
                                                value: "Parser",
                                                "aria-label": "Parser",
                                                className: "text-xs sm:text-sm cursor-pointer",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$file$2d$text$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__FileText$3e$__["FileText"], {
                                                        className: "h-4 w-4 mr-1"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                        lineNumber: 483,
                                                        columnNumber: 17
                                                    }, this),
                                                    t('plugins.componentName.Parser')
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 478,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 429,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 425,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center gap-2 sm:gap-3",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "text-xs sm:text-sm text-muted-foreground whitespace-nowrap",
                                        children: [
                                            t('market.sortBy'),
                                            ":"
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 491,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                                        value: sortOption,
                                        onValueChange: handleSortChange,
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                                                className: "w-40 sm:w-48 text-xs sm:text-sm",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {}, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                    lineNumber: 496,
                                                    columnNumber: 17
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 495,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                                                children: sortOptions.map((option)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                        value: option.value,
                                                        children: option.label
                                                    }, option.value, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                        lineNumber: 500,
                                                        columnNumber: 19
                                                    }, this))
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                                lineNumber: 498,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 494,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 490,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                        lineNumber: 423,
                        columnNumber: 9
                    }, this),
                    total > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-center text-muted-foreground text-sm",
                        children: searchQuery ? t('market.searchResults', {
                            count: total
                        }) : t('market.totalPlugins', {
                            count: total
                        })
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                        lineNumber: 511,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                lineNumber: 392,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                ref: scrollContainerRef,
                className: "flex-1 overflow-y-auto px-3 sm:px-4",
                children: [
                    !searchQuery && componentFilter === 'all' && selectedTags.length === 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "pt-4",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$RecommendationLists$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RecommendationLists"], {
                            lists: recommendationLists,
                            tagNames: tagNames,
                            onInstall: handleInstallPlugin
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                            lineNumber: 529,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                        lineNumber: 528,
                        columnNumber: 13
                    }, this),
                    isLoading ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center justify-center py-12",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                            text: t('market.loading')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                            lineNumber: 539,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                        lineNumber: 538,
                        columnNumber: 11
                    }, this) : plugins.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center justify-center py-12",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-muted-foreground",
                            children: searchQuery ? t('market.noResults') : t('market.noPlugins')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                            lineNumber: 543,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                        lineNumber: 542,
                        columnNumber: 11
                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6 pb-6 pt-4",
                                children: visiblePlugins.map((plugin)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$plugin$2d$market$2d$card$2f$PluginMarketCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                                        cardVO: plugin,
                                        onInstall: handleInstallPlugin,
                                        tagNames: tagNames
                                    }, plugin.pluginId, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 551,
                                        columnNumber: 17
                                    }, this))
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 549,
                                columnNumber: 13
                            }, this),
                            isLoadingMore && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center justify-center py-6",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                                    size: "sm",
                                    text: t('market.loadingMore')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                    lineNumber: 563,
                                    columnNumber: 17
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 562,
                                columnNumber: 15
                            }, this),
                            !hasMore && plugins.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-center text-muted-foreground py-6",
                                children: [
                                    t('market.allLoaded'),
                                    ' · ',
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                        href: "https://github.com/langbot-app/langbot-plugin-demo/issues/new?template=plugin-request.yml",
                                        target: "_blank",
                                        rel: "noopener noreferrer",
                                        className: "text-primary hover:underline",
                                        children: t('market.requestPlugin')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                        lineNumber: 572,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                                lineNumber: 569,
                                columnNumber: 15
                            }, this)
                        ]
                    }, void 0, true)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                lineNumber: 520,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
        lineNumber: 390,
        columnNumber: 5
    }, this);
}
function MarketPage({ installPlugin }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Suspense"], {
        fallback: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "container mx-auto px-4 py-6",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex items-center justify-center py-12",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                    text: "加载中..."
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                    lineNumber: 600,
                    columnNumber: 13
                }, void 0)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
                lineNumber: 599,
                columnNumber: 11
            }, void 0)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
            lineNumber: 598,
            columnNumber: 9
        }, void 0),
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(MarketPageContent, {
            installPlugin: installPlugin
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
            lineNumber: 605,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx",
        lineNumber: 596,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/entities/api/index.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MCPSessionStatus",
    ()=>MCPSessionStatus
]);
var MCPSessionStatus = /*#__PURE__*/ function(MCPSessionStatus) {
    MCPSessionStatus["CONNECTING"] = "connecting";
    MCPSessionStatus["CONNECTED"] = "connected";
    MCPSessionStatus["ERROR"] = "error";
    return MCPSessionStatus;
}({});
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>MCPCardComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/switch.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$refresh$2d$ccw$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__RefreshCcw$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/refresh-ccw.js [app-ssr] (ecmascript) <export default as RefreshCcw>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-ssr] (ecmascript) <export default as Wrench>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ban$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Ban$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/ban.js [app-ssr] (ecmascript) <export default as Ban>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2d$alert$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AlertCircle$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle-alert.js [app-ssr] (ecmascript) <export default as AlertCircle>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/loader-circle.js [app-ssr] (ecmascript) <export default as Loader2>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/entities/api/index.ts [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
;
;
;
function MCPCardComponent({ cardVO, onCardClick, onRefresh }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [enabled, setEnabled] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(cardVO.enable);
    const [switchEnable, setSwitchEnable] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(true);
    const [testing, setTesting] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [toolsCount, setToolsCount] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(cardVO.tools);
    const [status, setStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(cardVO.status);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        setStatus(cardVO.status);
        setToolsCount(cardVO.tools);
        setEnabled(cardVO.enable);
    }, [
        cardVO.status,
        cardVO.tools,
        cardVO.enable
    ]);
    function handleEnable(checked) {
        setSwitchEnable(false);
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].toggleMCPServer(cardVO.name, checked).then(()=>{
            setEnabled(checked);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('mcp.saveSuccess'));
            onRefresh();
            setSwitchEnable(true);
        }).catch((err)=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('mcp.modifyFailed') + err.msg);
            setSwitchEnable(true);
        });
    }
    function handleTest(e) {
        e.stopPropagation();
        setTesting(true);
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].testMCPServer(cardVO.name, {}).then((resp)=>{
            const taskId = resp.task_id;
            const interval = setInterval(()=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getAsyncTask(taskId).then((taskResp)=>{
                    if (taskResp.runtime.done) {
                        clearInterval(interval);
                        setTesting(false);
                        if (taskResp.runtime.exception) {
                            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('mcp.refreshFailed') + taskResp.runtime.exception);
                        } else {
                            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('mcp.refreshSuccess'));
                        }
                        // Refresh to get updated runtime_info
                        onRefresh();
                    }
                });
            }, 1000);
        }).catch((err)=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('mcp.refreshFailed') + err.msg);
            setTesting(false);
        });
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "w-[100%] h-[10rem] bg-white dark:bg-[#1f1f22] rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] dark:shadow-none p-[1.2rem] cursor-pointer transition-all duration-200 hover:shadow-[0px_2px_8px_0_rgba(0,0,0,0.1)] dark:hover:shadow-none",
        onClick: onCardClick,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "w-full h-full flex flex-row items-start justify-start gap-[1.2rem]",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                    xmlns: "http://www.w3.org/2000/svg",
                    viewBox: "0 0 24 24",
                    width: "64",
                    height: "64",
                    fill: "rgba(70,146,221,1)",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                        d: "M17.6567 14.8284L16.2425 13.4142L17.6567 12C19.2188 10.4379 19.2188 7.90524 17.6567 6.34314C16.0946 4.78105 13.5619 4.78105 11.9998 6.34314L10.5856 7.75736L9.17139 6.34314L10.5856 4.92893C12.9287 2.58578 16.7277 2.58578 19.0709 4.92893C21.414 7.27208 21.414 11.0711 19.0709 13.4142L17.6567 14.8284ZM14.8282 17.6569L13.414 19.0711C11.0709 21.4142 7.27189 21.4142 4.92875 19.0711C2.5856 16.7279 2.5856 12.9289 4.92875 10.5858L6.34296 9.17157L7.75717 10.5858L6.34296 12C4.78086 13.5621 4.78086 16.0948 6.34296 17.6569C7.90506 19.2189 10.4377 19.2189 11.9998 17.6569L13.414 16.2426L14.8282 17.6569ZM14.8282 7.75736L16.2425 9.17157L9.17139 16.2426L7.75717 14.8284L14.8282 7.75736Z"
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                        lineNumber: 98,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                    lineNumber: 91,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "w-full h-full flex flex-col items-start justify-between gap-[0.6rem]",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex flex-col items-start justify-start gap-[0.3rem]",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center gap-[0.5rem]",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-[1.2rem] text-black dark:text-[#f0f0f0] font-medium",
                                        children: cardVO.name
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 104,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Badge"], {
                                        variant: "secondary",
                                        className: "text-[0.65rem] px-1.5 py-0",
                                        children: cardVO.mode.toUpperCase()
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 107,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 103,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                            lineNumber: 102,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "w-full flex flex-row items-start justify-start gap-[0.6rem]",
                            children: !enabled ? // 未启用 - 橙色
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center gap-[0.4rem]",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ban$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Ban$3e$__["Ban"], {
                                        className: "w-4 h-4 text-orange-500 dark:text-orange-400"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 117,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-sm text-orange-500 dark:text-orange-400 font-medium",
                                        children: t('mcp.statusDisabled')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 118,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 116,
                                columnNumber: 15
                            }, this) : status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTED ? // 连接成功 - 显示工具数量
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex h-full flex-row items-center justify-center gap-[0.4rem]",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                        className: "w-5 h-5"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 125,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-base text-black dark:text-[#f0f0f0] font-medium",
                                        children: t('mcp.toolCount', {
                                            count: toolsCount
                                        })
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 126,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 124,
                                columnNumber: 15
                            }, this) : status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTING ? // 连接中 - 蓝色加载
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center gap-[0.4rem]",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__["Loader2"], {
                                        className: "w-4 h-4 text-blue-500 dark:text-blue-400 animate-spin"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 133,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-sm text-blue-500 dark:text-blue-400 font-medium",
                                        children: t('mcp.connecting')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 134,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 132,
                                columnNumber: 15
                            }, this) : // 连接失败 - 红色
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center gap-[0.4rem]",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2d$alert$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__AlertCircle$3e$__["AlertCircle"], {
                                        className: "w-4 h-4 text-red-500 dark:text-red-400"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 141,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-sm text-red-500 dark:text-red-400 font-medium",
                                        children: t('mcp.connectionFailedStatus')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                        lineNumber: 142,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 140,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                            lineNumber: 113,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                    lineNumber: 101,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex flex-col items-center justify-between h-full",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex items-center justify-center",
                            onClick: (e)=>e.stopPropagation(),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Switch"], {
                                className: "cursor-pointer",
                                checked: enabled,
                                onCheckedChange: handleEnable,
                                disabled: !switchEnable
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 155,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                            lineNumber: 151,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex items-center justify-center gap-[0.4rem]",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                variant: "ghost",
                                size: "sm",
                                className: "p-1 h-8 w-8",
                                onClick: (e)=>handleTest(e),
                                disabled: testing,
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$refresh$2d$ccw$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__RefreshCcw$3e$__["RefreshCcw"], {
                                    className: "w-4 h-4"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                    lineNumber: 171,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                                lineNumber: 164,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                            lineNumber: 163,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
                    lineNumber: 150,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
            lineNumber: 90,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx",
        lineNumber: 86,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPCardVO.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MCPCardVO",
    ()=>MCPCardVO
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/entities/api/index.ts [app-ssr] (ecmascript)");
;
class MCPCardVO {
    name;
    mode;
    enable;
    status;
    tools;
    error;
    constructor(data){
        this.name = data.name;
        this.mode = data.mode;
        this.enable = data.enable;
        // Determine status from runtime_info
        if (!data.runtime_info) {
            this.status = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].ERROR;
            this.tools = 0;
        } else if (data.runtime_info.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTED) {
            this.status = data.runtime_info.status;
            this.tools = data.runtime_info.tool_count || 0;
        } else {
            this.status = data.runtime_info.status;
            this.tools = 0;
            this.error = data.runtime_info.error_message;
        }
    }
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>MCPComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$mcp$2d$card$2f$MCPCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-card/MCPCardComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$MCPCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPCardVO.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/entities/api/index.ts [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
'use client';
;
;
;
;
;
;
;
function MCPComponent({ onEditServer }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [installedServers, setInstalledServers] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [loading, setLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const pollingIntervalRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        fetchInstalledServers();
        return ()=>{
            // Cleanup: clear polling interval when component unmounts
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, []);
    // Check if any enabled server is connecting and start/stop polling accordingly
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const hasConnecting = installedServers.some((server)=>server.enable && server.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTING);
        if (hasConnecting && !pollingIntervalRef.current) {
            // Start polling every 3 seconds
            pollingIntervalRef.current = setInterval(()=>{
                fetchInstalledServers();
            }, 3000);
        } else if (!hasConnecting && pollingIntervalRef.current) {
            // Stop polling when no enabled server is connecting
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
        return ()=>{
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
        };
    }, [
        installedServers
    ]);
    function fetchInstalledServers() {
        setLoading(true);
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getMCPServers().then((resp)=>{
            const servers = resp.servers.map((server)=>new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$MCPCardVO$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPCardVO"](server));
            setInstalledServers(servers);
            setLoading(false);
        }).catch((error)=>{
            console.error('Failed to fetch MCP servers:', error);
            setLoading(false);
        });
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "w-full h-full",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "w-full h-full px-[0.8rem] pt-[0rem]",
            children: loading ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex flex-col items-center justify-center text-gray-500 min-h-[60vh] w-full gap-2",
                children: t('mcp.loading')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                lineNumber: 79,
                columnNumber: 11
            }, this) : installedServers.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex flex-col items-center justify-center text-gray-500 min-h-[60vh] w-full gap-2",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                        className: "h-[3rem] w-[3rem]",
                        xmlns: "http://www.w3.org/2000/svg",
                        viewBox: "0 0 24 24",
                        fill: "currentColor",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                            d: "M4.5 7.65311V16.3469L12 20.689L19.5 16.3469V7.65311L12 3.311L4.5 7.65311ZM12 1L21.5 6.5V17.5L12 23L2.5 17.5V6.5L12 1ZM6.49896 9.97065L11 12.5765V17.625H13V12.5765L17.501 9.97066L16.499 8.2398L12 10.8445L7.50104 8.2398L6.49896 9.97065Z"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                            lineNumber: 90,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                        lineNumber: 84,
                        columnNumber: 13
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-lg mb-2",
                        children: t('mcp.noServerInstalled')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                        lineNumber: 92,
                        columnNumber: 13
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                lineNumber: 83,
                columnNumber: 11
            }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-[2rem] pb-6",
                children: installedServers.map((server, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$mcp$2d$card$2f$MCPCardComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                            cardVO: server,
                            onCardClick: ()=>{
                                if (onEditServer) {
                                    onEditServer(server.name);
                                }
                            },
                            onRefresh: fetchInstalledServers
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                            lineNumber: 98,
                            columnNumber: 17
                        }, this)
                    }, `${server.name}-${index}`, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                        lineNumber: 97,
                        columnNumber: 15
                    }, this))
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
                lineNumber: 95,
                columnNumber: 11
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
            lineNumber: 77,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx",
        lineNumber: 75,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>MCPFormDialog
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-hook-form/dist/index.esm.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@hookform/resolvers/zod/dist/zod.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/zod/v3/external.js [app-ssr] (ecmascript) <export * as z>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/card.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/form.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/select.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/entities/api/index.ts [app-ssr] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
// Status Display Component - 在测试中、连接中或连接失败时使用
function StatusDisplay({ testing, runtimeInfo, t }) {
    if (testing) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex items-center gap-2 text-blue-600",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                    className: "w-5 h-5 animate-spin",
                    xmlns: "http://www.w3.org/2000/svg",
                    fill: "none",
                    viewBox: "0 0 24 24",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                            className: "opacity-25",
                            cx: "12",
                            cy: "12",
                            r: "10",
                            stroke: "currentColor",
                            strokeWidth: "4"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 71,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                            className: "opacity-75",
                            fill: "currentColor",
                            d: "M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 79,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 65,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    className: "font-medium",
                    children: t('mcp.testing')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 85,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
            lineNumber: 64,
            columnNumber: 7
        }, this);
    }
    // 连接中
    if (runtimeInfo.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTING) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex items-center gap-2 text-blue-600",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                    className: "w-5 h-5 animate-spin",
                    xmlns: "http://www.w3.org/2000/svg",
                    fill: "none",
                    viewBox: "0 0 24 24",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                            className: "opacity-25",
                            cx: "12",
                            cy: "12",
                            r: "10",
                            stroke: "currentColor",
                            strokeWidth: "4"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 100,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                            className: "opacity-75",
                            fill: "currentColor",
                            d: "M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 108,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 94,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    className: "font-medium",
                    children: t('mcp.connecting')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 114,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
            lineNumber: 93,
            columnNumber: 7
        }, this);
    }
    // 连接失败
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "space-y-1",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex items-center gap-2 text-red-600",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                        className: "w-5 h-5",
                        xmlns: "http://www.w3.org/2000/svg",
                        fill: "none",
                        viewBox: "0 0 24 24",
                        stroke: "currentColor",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                            strokeLinecap: "round",
                            strokeLinejoin: "round",
                            strokeWidth: 2,
                            d: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 130,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                        lineNumber: 123,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "font-medium",
                        children: t('mcp.connectionFailed')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                        lineNumber: 137,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                lineNumber: 122,
                columnNumber: 7
            }, this),
            runtimeInfo.error_message && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "text-sm text-red-500 pl-7",
                children: runtimeInfo.error_message
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                lineNumber: 140,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
        lineNumber: 121,
        columnNumber: 5
    }, this);
}
// Tools List Component
function ToolsList({ tools }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "space-y-2 max-h-[300px] overflow-y-auto",
        children: tools.map((tool, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Card"], {
                className: "py-3 shadow-none",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardHeader"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardTitle"], {
                            className: "text-sm",
                            children: tool.name
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 155,
                            columnNumber: 13
                        }, this),
                        tool.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardDescription"], {
                            className: "text-xs",
                            children: tool.description
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 157,
                            columnNumber: 15
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 154,
                    columnNumber: 11
                }, this)
            }, index, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                lineNumber: 153,
                columnNumber: 9
            }, this))
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
        lineNumber: 151,
        columnNumber: 5
    }, this);
}
const getFormSchema = (t)=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        name: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string({
            required_error: t('mcp.nameRequired')
        }).min(1, {
            message: t('mcp.nameRequired')
        }),
        mode: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
            'sse',
            'stdio',
            'http'
        ]),
        timeout: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number({
            invalid_type_error: t('mcp.timeoutMustBeNumber')
        }).positive({
            message: t('mcp.timeoutMustBePositive')
        }).default(30),
        ssereadtimeout: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number({
            invalid_type_error: t('mcp.sseTimeoutMustBeNumber')
        }).positive({
            message: t('mcp.timeoutMustBePositive')
        }).default(300),
        url: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
        command: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
        args: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            value: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
        })).optional(),
        extra_args: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            key: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
                'string',
                'number',
                'boolean'
            ]),
            value: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
        })).optional()
    }).superRefine((data, ctx)=>{
        if (data.mode === 'sse' || data.mode === 'http') {
            if (!data.url || data.url.length === 0) {
                ctx.addIssue({
                    code: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodIssueCode.custom,
                    message: t('mcp.urlRequired'),
                    path: [
                        'url'
                    ]
                });
            }
        } else if (data.mode === 'stdio') {
            if (!data.command || data.command.length === 0) {
                ctx.addIssue({
                    code: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodIssueCode.custom,
                    message: t('mcp.commandRequired'),
                    path: [
                        'command'
                    ]
                });
            }
        }
    });
function MCPFormDialog({ open, onOpenChange, serverName, isEditMode = false, onSuccess, onDelete }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const formSchema = getFormSchema(t);
    const form = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useForm"])({
        resolver: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["zodResolver"])(formSchema),
        defaultValues: {
            name: '',
            mode: 'sse',
            url: '',
            command: '',
            args: [],
            timeout: 30,
            ssereadtimeout: 300,
            extra_args: []
        }
    });
    const [extraArgs, setExtraArgs] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [stdioArgs, setStdioArgs] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [mcpTesting, setMcpTesting] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [runtimeInfo, setRuntimeInfo] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const pollingIntervalRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const watchMode = form.watch('mode');
    // Load server data when editing
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (open && isEditMode && serverName) {
            loadServerForEdit(serverName);
        } else if (open && !isEditMode) {
            // Reset form when creating new server
            form.reset({
                name: '',
                mode: 'sse',
                url: '',
                command: '',
                args: [],
                timeout: 30,
                ssereadtimeout: 300,
                extra_args: []
            });
            setExtraArgs([]);
            setStdioArgs([]);
            setRuntimeInfo(null);
        }
        // Cleanup polling interval when dialog closes
        return ()=>{
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
        };
    }, [
        open,
        isEditMode,
        serverName
    ]);
    // Poll for updates when runtime_info status is CONNECTING
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (!open || !isEditMode || !serverName || !runtimeInfo || runtimeInfo.status !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTING) {
            // Stop polling if conditions are not met
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
            return;
        }
        // Start polling if not already running
        if (!pollingIntervalRef.current) {
            pollingIntervalRef.current = setInterval(()=>{
                loadServerForEdit(serverName);
            }, 3000);
        }
        return ()=>{
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
        };
    }, [
        open,
        isEditMode,
        serverName,
        runtimeInfo?.status
    ]);
    async function loadServerForEdit(serverName) {
        try {
            const resp = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getMCPServer(serverName);
            const server = resp.server ?? resp;
            form.setValue('name', server.name);
            form.setValue('mode', server.mode);
            if (server.mode === 'sse' || server.mode === 'http') {
                form.setValue('url', server.extra_args.url);
                form.setValue('timeout', server.extra_args.timeout);
                if (server.mode === 'sse') {
                    form.setValue('ssereadtimeout', server.extra_args.ssereadtimeout);
                }
                if (server.extra_args.headers) {
                    const headers = Object.entries(server.extra_args.headers).map(([key, value])=>({
                            key,
                            type: 'string',
                            value: String(value)
                        }));
                    setExtraArgs(headers);
                    form.setValue('extra_args', headers);
                }
            } else if (server.mode === 'stdio') {
                form.setValue('command', server.extra_args.command);
                const args = (server.extra_args.args || []).map((arg)=>({
                        value: arg
                    }));
                setStdioArgs(args);
                form.setValue('args', args);
                if (server.extra_args.env) {
                    const envs = Object.entries(server.extra_args.env).map(([key, value])=>({
                            key,
                            type: 'string',
                            value: String(value)
                        }));
                    setExtraArgs(envs);
                    form.setValue('extra_args', envs);
                }
            }
            if (server.runtime_info) {
                setRuntimeInfo(server.runtime_info);
            } else {
                setRuntimeInfo(null);
            }
        } catch (error) {
            console.error('Failed to load server:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('mcp.loadFailed'));
        }
    }
    async function handleFormSubmit(value) {
        try {
            let serverConfig;
            if (value.mode === 'sse' || value.mode === 'http') {
                const headers = {};
                value.extra_args?.forEach((arg)=>{
                    headers[arg.key] = String(arg.value);
                });
                if (value.mode === 'sse') {
                    serverConfig = {
                        name: value.name,
                        mode: 'sse',
                        enable: true,
                        extra_args: {
                            url: value.url,
                            headers: headers,
                            timeout: value.timeout,
                            ssereadtimeout: value.ssereadtimeout
                        }
                    };
                } else {
                    serverConfig = {
                        name: value.name,
                        mode: 'http',
                        enable: true,
                        extra_args: {
                            url: value.url,
                            headers: headers,
                            timeout: value.timeout
                        }
                    };
                }
            } else {
                // Convert extra_args to env
                const env = {};
                value.extra_args?.forEach((arg)=>{
                    env[arg.key] = String(arg.value);
                });
                // Convert args object array to string array
                const args = value.args?.map((arg)=>arg.value) || [];
                serverConfig = {
                    name: value.name,
                    mode: 'stdio',
                    enable: true,
                    extra_args: {
                        command: value.command,
                        args: args,
                        env: env
                    }
                };
            }
            if (isEditMode && serverName) {
                await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].updateMCPServer(serverName, serverConfig);
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('mcp.updateSuccess'));
            } else {
                await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].createMCPServer(serverConfig);
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('mcp.createSuccess'));
            }
            handleDialogClose(false);
            onSuccess?.();
        } catch (error) {
            console.error('Failed to save MCP server:', error);
            const errMsg = error.msg || '';
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error((isEditMode ? t('mcp.updateFailed') : t('mcp.createFailed')) + errMsg);
        }
    }
    async function testMcp() {
        setMcpTesting(true);
        try {
            const mode = form.getValues('mode');
            let extraArgsData;
            if (mode === 'sse') {
                extraArgsData = {
                    url: form.getValues('url'),
                    timeout: form.getValues('timeout'),
                    headers: Object.fromEntries(extraArgs.map((arg)=>[
                            arg.key,
                            arg.value
                        ])),
                    ssereadtimeout: form.getValues('ssereadtimeout')
                };
            } else if (mode === 'http') {
                extraArgsData = {
                    url: form.getValues('url'),
                    timeout: form.getValues('timeout'),
                    headers: Object.fromEntries(extraArgs.map((arg)=>[
                            arg.key,
                            arg.value
                        ]))
                };
            } else {
                extraArgsData = {
                    command: form.getValues('command'),
                    args: stdioArgs.map((arg)=>arg.value),
                    env: Object.fromEntries(extraArgs.map((arg)=>[
                            arg.key,
                            arg.value
                        ]))
                };
            }
            const { task_id } = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].testMCPServer('_', {
                name: form.getValues('name'),
                mode: mode,
                enable: true,
                extra_args: extraArgsData
            });
            if (!task_id) {
                throw new Error(t('mcp.noTaskId'));
            }
            const interval = setInterval(async ()=>{
                try {
                    const taskResp = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getAsyncTask(task_id);
                    if (taskResp.runtime?.done) {
                        clearInterval(interval);
                        setMcpTesting(false);
                        if (taskResp.runtime.exception) {
                            const errorMsg = taskResp.runtime.exception || t('mcp.unknownError');
                            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(`${t('mcp.testError')}: ${errorMsg}`);
                            setRuntimeInfo({
                                status: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].ERROR,
                                error_message: errorMsg,
                                tool_count: 0,
                                tools: []
                            });
                        } else {
                            if (isEditMode) {
                                await loadServerForEdit(form.getValues('name'));
                            }
                            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('mcp.testSuccess'));
                        }
                    }
                } catch (err) {
                    clearInterval(interval);
                    setMcpTesting(false);
                    const errorMsg = err.msg || t('mcp.getTaskFailed');
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(`${t('mcp.testError')}: ${errorMsg}`);
                }
            }, 1000);
        } catch (err) {
            setMcpTesting(false);
            const errorMsg = err.message || t('mcp.unknownError');
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(`${t('mcp.testError')}: ${errorMsg}`);
        }
    }
    const addExtraArg = ()=>{
        const newArgs = [
            ...extraArgs,
            {
                key: '',
                type: 'string',
                value: ''
            }
        ];
        setExtraArgs(newArgs);
        form.setValue('extra_args', newArgs);
    };
    const removeExtraArg = (index)=>{
        const newArgs = extraArgs.filter((_, i)=>i !== index);
        setExtraArgs(newArgs);
        form.setValue('extra_args', newArgs);
    };
    const updateExtraArg = (index, field, value)=>{
        const newArgs = [
            ...extraArgs
        ];
        newArgs[index] = {
            ...newArgs[index],
            [field]: value
        };
        setExtraArgs(newArgs);
        form.setValue('extra_args', newArgs);
    };
    const addStdioArg = ()=>{
        const newArgs = [
            ...stdioArgs,
            {
                value: ''
            }
        ];
        setStdioArgs(newArgs);
        form.setValue('args', newArgs);
    };
    const removeStdioArg = (index)=>{
        const newArgs = stdioArgs.filter((_, i)=>i !== index);
        setStdioArgs(newArgs);
        form.setValue('args', newArgs);
    };
    const updateStdioArg = (index, value)=>{
        const newArgs = [
            ...stdioArgs
        ];
        newArgs[index] = {
            value
        };
        setStdioArgs(newArgs);
        form.setValue('args', newArgs);
    };
    const handleDialogClose = (open)=>{
        onOpenChange(open);
        if (!open) {
            form.reset();
            setExtraArgs([]);
            setStdioArgs([]);
            setRuntimeInfo(null);
        }
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Dialog"], {
        open: open,
        onOpenChange: handleDialogClose,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogContent"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogHeader"], {
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogTitle"], {
                        children: isEditMode ? t('mcp.editServer') : t('mcp.createServer')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                        lineNumber: 608,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 607,
                    columnNumber: 9
                }, this),
                isEditMode && runtimeInfo && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "mb-0 space-y-3",
                    children: [
                        (mcpTesting || runtimeInfo.status !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTED) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "p-3 rounded-lg border",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(StatusDisplay, {
                                testing: mcpTesting,
                                runtimeInfo: runtimeInfo,
                                t: t
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                lineNumber: 619,
                                columnNumber: 17
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 618,
                            columnNumber: 15
                        }, this),
                        !mcpTesting && runtimeInfo.status === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$api$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["MCPSessionStatus"].CONNECTED && runtimeInfo.tools?.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "text-sm font-medium",
                                    children: t('mcp.toolCount', {
                                        count: runtimeInfo.tools?.length || 0
                                    })
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                    lineNumber: 632,
                                    columnNumber: 19
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(ToolsList, {
                                    tools: runtimeInfo.tools
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                    lineNumber: 637,
                                    columnNumber: 19
                                }, this)
                            ]
                        }, void 0, true)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 614,
                    columnNumber: 11
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Form"], {
                    ...form,
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                        onSubmit: form.handleSubmit(handleFormSubmit),
                        className: "space-y-4",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "space-y-4",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                                    control: form.control,
                                    name: "name",
                                    render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                    children: t('mcp.name')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 654,
                                                    columnNumber: 21
                                                }, void 0),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                        ...field
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                        lineNumber: 656,
                                                        columnNumber: 23
                                                    }, void 0)
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 655,
                                                    columnNumber: 21
                                                }, void 0),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 658,
                                                    columnNumber: 21
                                                }, void 0)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 653,
                                            columnNumber: 19
                                        }, void 0)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                    lineNumber: 649,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                                    control: form.control,
                                    name: "mode",
                                    render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                    children: t('mcp.serverMode')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 668,
                                                    columnNumber: 21
                                                }, void 0),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Select"], {
                                                    onValueChange: field.onChange,
                                                    defaultValue: field.value,
                                                    value: field.value,
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectValue"], {
                                                                    placeholder: t('mcp.selectMode')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                    lineNumber: 676,
                                                                    columnNumber: 27
                                                                }, void 0)
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 675,
                                                                columnNumber: 25
                                                            }, void 0)
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 674,
                                                            columnNumber: 23
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectContent"], {
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                                    value: "http",
                                                                    children: t('mcp.http')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                    lineNumber: 680,
                                                                    columnNumber: 25
                                                                }, void 0),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                                    value: "stdio",
                                                                    children: t('mcp.stdio')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                    lineNumber: 681,
                                                                    columnNumber: 25
                                                                }, void 0),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                                    value: "sse",
                                                                    children: t('mcp.sse')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                    lineNumber: 682,
                                                                    columnNumber: 25
                                                                }, void 0)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 679,
                                                            columnNumber: 23
                                                        }, void 0)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 669,
                                                    columnNumber: 21
                                                }, void 0),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 685,
                                                    columnNumber: 21
                                                }, void 0)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 667,
                                            columnNumber: 19
                                        }, void 0)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                    lineNumber: 663,
                                    columnNumber: 15
                                }, this),
                                (watchMode === 'sse' || watchMode === 'http') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                                            control: form.control,
                                            name: "url",
                                            render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                            children: t('mcp.url')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 697,
                                                            columnNumber: 25
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                ...field
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 699,
                                                                columnNumber: 27
                                                            }, void 0)
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 698,
                                                            columnNumber: 25
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 701,
                                                            columnNumber: 25
                                                        }, void 0)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 696,
                                                    columnNumber: 23
                                                }, void 0)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 692,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                                            control: form.control,
                                            name: "timeout",
                                            render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                            children: t('mcp.timeout')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 711,
                                                            columnNumber: 25
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                type: "number",
                                                                placeholder: t('mcp.timeout'),
                                                                ...field,
                                                                onChange: (e)=>field.onChange(Number(e.target.value))
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 713,
                                                                columnNumber: 27
                                                            }, void 0)
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 712,
                                                            columnNumber: 25
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 722,
                                                            columnNumber: 25
                                                        }, void 0)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 710,
                                                    columnNumber: 23
                                                }, void 0)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 706,
                                            columnNumber: 19
                                        }, this),
                                        watchMode === 'sse' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                                            control: form.control,
                                            name: "ssereadtimeout",
                                            render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                            children: t('mcp.sseTimeout')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 733,
                                                            columnNumber: 27
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                type: "number",
                                                                placeholder: t('mcp.sseTimeoutDescription'),
                                                                ...field,
                                                                onChange: (e)=>field.onChange(Number(e.target.value))
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 735,
                                                                columnNumber: 29
                                                            }, void 0)
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 734,
                                                            columnNumber: 27
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 744,
                                                            columnNumber: 27
                                                        }, void 0)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 732,
                                                    columnNumber: 25
                                                }, void 0)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 728,
                                            columnNumber: 21
                                        }, this)
                                    ]
                                }, void 0, true),
                                watchMode === 'stdio' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormField"], {
                                            control: form.control,
                                            name: "command",
                                            render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                            children: t('mcp.command')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 759,
                                                            columnNumber: 25
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormControl"], {
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                ...field
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 761,
                                                                columnNumber: 27
                                                            }, void 0)
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 760,
                                                            columnNumber: 25
                                                        }, void 0),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 763,
                                                            columnNumber: 25
                                                        }, void 0)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 758,
                                                    columnNumber: 23
                                                }, void 0)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 754,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                    children: t('mcp.args')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 769,
                                                    columnNumber: 21
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "space-y-2",
                                                    children: [
                                                        stdioArgs.map((arg, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "flex gap-2",
                                                                children: [
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                        placeholder: t('mcp.args'),
                                                                        value: arg.value,
                                                                        onChange: (e)=>updateStdioArg(index, e.target.value)
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                        lineNumber: 773,
                                                                        columnNumber: 27
                                                                    }, this),
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                        type: "button",
                                                                        className: "p-2 hover:bg-gray-100 rounded",
                                                                        onClick: ()=>removeStdioArg(index),
                                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                                            xmlns: "http://www.w3.org/2000/svg",
                                                                            viewBox: "0 0 24 24",
                                                                            fill: "currentColor",
                                                                            className: "w-5 h-5 text-red-500",
                                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                                                d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                                lineNumber: 791,
                                                                                columnNumber: 31
                                                                            }, this)
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                            lineNumber: 785,
                                                                            columnNumber: 29
                                                                        }, this)
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                        lineNumber: 780,
                                                                        columnNumber: 27
                                                                    }, this)
                                                                ]
                                                            }, index, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 772,
                                                                columnNumber: 25
                                                            }, this)),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                            type: "button",
                                                            variant: "outline",
                                                            onClick: addStdioArg,
                                                            children: t('mcp.addArgument')
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                            lineNumber: 796,
                                                            columnNumber: 23
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 770,
                                                    columnNumber: 21
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 768,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, void 0, true),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormItem"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormLabel"], {
                                            children: watchMode === 'sse' || watchMode === 'http' ? t('mcp.headers') : t('mcp.env')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 809,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "space-y-2",
                                            children: [
                                                extraArgs.map((arg, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "flex gap-2",
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                placeholder: t('models.keyName'),
                                                                value: arg.key,
                                                                onChange: (e)=>updateExtraArg(index, 'key', e.target.value)
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 817,
                                                                columnNumber: 23
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                placeholder: t('models.value'),
                                                                value: arg.value,
                                                                onChange: (e)=>updateExtraArg(index, 'value', e.target.value)
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 844,
                                                                columnNumber: 23
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                type: "button",
                                                                className: "p-2 hover:bg-gray-100 rounded",
                                                                onClick: ()=>removeExtraArg(index),
                                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                                    xmlns: "http://www.w3.org/2000/svg",
                                                                    viewBox: "0 0 24 24",
                                                                    fill: "currentColor",
                                                                    className: "w-5 h-5 text-red-500",
                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                                        d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                        lineNumber: 862,
                                                                        columnNumber: 27
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                    lineNumber: 856,
                                                                    columnNumber: 25
                                                                }, this)
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                                lineNumber: 851,
                                                                columnNumber: 23
                                                            }, this)
                                                        ]
                                                    }, index, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                        lineNumber: 816,
                                                        columnNumber: 21
                                                    }, this)),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                    type: "button",
                                                    variant: "outline",
                                                    onClick: addExtraArg,
                                                    children: watchMode === 'sse' || watchMode === 'http' ? t('mcp.addHeader') : t('mcp.addEnvVar')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                                    lineNumber: 867,
                                                    columnNumber: 19
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 814,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormDescription"], {
                                            children: t('mcp.extraParametersDescription')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 873,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 876,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                    lineNumber: 808,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogFooter"], {
                                    children: [
                                        isEditMode && onDelete && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            type: "button",
                                            variant: "destructive",
                                            onClick: onDelete,
                                            children: t('common.delete')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 881,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            type: "submit",
                                            children: isEditMode ? t('common.save') : t('common.submit')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 890,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            type: "button",
                                            variant: "outline",
                                            onClick: ()=>testMcp(),
                                            disabled: mcpTesting,
                                            children: t('common.test')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 894,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            type: "button",
                                            variant: "outline",
                                            onClick: ()=>handleDialogClose(false),
                                            children: t('common.cancel')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                            lineNumber: 903,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                                    lineNumber: 879,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                            lineNumber: 648,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                        lineNumber: 644,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
                    lineNumber: 643,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
            lineNumber: 606,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx",
        lineNumber: 605,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>MCPDeleteConfirmDialog
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
'use client';
;
;
;
;
;
;
function MCPDeleteConfirmDialog({ open, onOpenChange, serverName, onSuccess }) {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    async function handleDelete() {
        if (!serverName) return;
        try {
            await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].deleteMCPServer(serverName);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('mcp.deleteSuccess'));
            onOpenChange(false);
            if (onSuccess) {
                onSuccess();
            }
        } catch (error) {
            console.error('Failed to delete server:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('mcp.deleteFailed'));
        }
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Dialog"], {
        open: open,
        onOpenChange: onOpenChange,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogContent"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogHeader"], {
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogTitle"], {
                        children: t('mcp.confirmDeleteTitle')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
                        lineNumber: 54,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
                    lineNumber: 53,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogDescription"], {
                    children: t('mcp.confirmDeleteServer')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
                    lineNumber: 56,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogFooter"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                            variant: "outline",
                            onClick: ()=>onOpenChange(false),
                            children: t('common.cancel')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
                            lineNumber: 58,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                            variant: "destructive",
                            onClick: handleDelete,
                            children: t('common.confirm')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
                            lineNumber: 61,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
                    lineNumber: 57,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
            lineNumber: 52,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx",
        lineNumber: 51,
        columnNumber: 5
    }, this);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginConfigPage
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginInstalledComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$PluginMarketComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$MCPServerComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/MCPServerComponent.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$mcp$2d$form$2f$MCPFormDialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPFormDialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$mcp$2d$form$2f$MCPDeleteConfirmDialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$plugins$2e$module$2e$css__$5b$app$2d$ssr$5d$__$28$css__module$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/plugins.module.css [app-ssr] (css module)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/tabs.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/card.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__PlusIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/plus.js [app-ssr] (ecmascript) <export default as PlusIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$down$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronDownIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-down.js [app-ssr] (ecmascript) <export default as ChevronDownIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$upload$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__UploadIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/upload.js [app-ssr] (ecmascript) <export default as UploadIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$store$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__StoreIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/store.js [app-ssr] (ecmascript) <export default as StoreIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$download$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Download$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/download.js [app-ssr] (ecmascript) <export default as Download>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$power$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Power$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/power.js [app-ssr] (ecmascript) <export default as Power>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$github$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Github$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/github.js [app-ssr] (ecmascript) <export default as Github>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$left$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronLeft$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-left.js [app-ssr] (ecmascript) <export default as ChevronLeft>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$code$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Code$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/code.js [app-ssr] (ecmascript) <export default as Code>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$copy$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Copy$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/copy.js [app-ssr] (ecmascript) <export default as Copy>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$check$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Check$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/check.js [app-ssr] (ecmascript) <export default as Check>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$bug$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Bug$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/bug.js [app-ssr] (ecmascript) <export default as Bug>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dropdown-menu.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/popover.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-ssr] (ecmascript) <locals>");
'use client';
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
;
var PluginInstallStatus = /*#__PURE__*/ function(PluginInstallStatus) {
    PluginInstallStatus["WAIT_INPUT"] = "wait_input";
    PluginInstallStatus["SELECT_RELEASE"] = "select_release";
    PluginInstallStatus["SELECT_ASSET"] = "select_asset";
    PluginInstallStatus["ASK_CONFIRM"] = "ask_confirm";
    PluginInstallStatus["INSTALLING"] = "installing";
    PluginInstallStatus["ERROR"] = "error";
    return PluginInstallStatus;
}(PluginInstallStatus || {});
function PluginConfigPage() {
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [activeTab, setActiveTab] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('installed');
    const [modalOpen, setModalOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [installSource, setInstallSource] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('local');
    const [installInfo, setInstallInfo] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])({}); // eslint-disable-line @typescript-eslint/no-explicit-any
    const [mcpSSEModalOpen, setMcpSSEModalOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [pluginInstallStatus, setPluginInstallStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])("wait_input");
    const [installError, setInstallError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [githubURL, setGithubURL] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('');
    const [githubReleases, setGithubReleases] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [selectedRelease, setSelectedRelease] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [githubAssets, setGithubAssets] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [selectedAsset, setSelectedAsset] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [githubOwner, setGithubOwner] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('');
    const [githubRepo, setGithubRepo] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])('');
    const [fetchingReleases, setFetchingReleases] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [fetchingAssets, setFetchingAssets] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [isDragOver, setIsDragOver] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [pluginSystemStatus, setPluginSystemStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [statusLoading, setStatusLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(true);
    const fileInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [showDeleteConfirmModal, setShowDeleteConfirmModal] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [editingServerName, setEditingServerName] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [isEditMode, setIsEditMode] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [refreshKey, setRefreshKey] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(0);
    const [debugInfo, setDebugInfo] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(null);
    const [debugPopoverOpen, setDebugPopoverOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [copiedDebugUrl, setCopiedDebugUrl] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [copiedDebugKey, setCopiedDebugKey] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const fetchPluginSystemStatus = async ()=>{
            try {
                setStatusLoading(true);
                const status = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPluginSystemStatus();
                setPluginSystemStatus(status);
            } catch (error) {
                console.error('Failed to fetch plugin system status:', error);
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.failedToGetStatus'));
            } finally{
                setStatusLoading(false);
            }
        };
        fetchPluginSystemStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = [
            'Bytes',
            'KB',
            'MB',
            'GB'
        ];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
    function watchTask(taskId) {
        let alreadySuccess = false;
        const interval = setInterval(()=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getAsyncTask(taskId).then((resp)=>{
                if (resp.runtime.done) {
                    clearInterval(interval);
                    if (resp.runtime.exception) {
                        setInstallError(resp.runtime.exception);
                        setPluginInstallStatus("error");
                    } else {
                        if (!alreadySuccess) {
                            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].success(t('plugins.installSuccess'));
                            alreadySuccess = true;
                        }
                        resetGithubState();
                        setModalOpen(false);
                        pluginInstalledRef.current?.refreshPluginList();
                    }
                }
            });
        }, 1000);
    }
    const pluginInstalledRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    function resetGithubState() {
        setGithubURL('');
        setGithubReleases([]);
        setSelectedRelease(null);
        setGithubAssets([]);
        setSelectedAsset(null);
        setGithubOwner('');
        setGithubRepo('');
        setFetchingReleases(false);
        setFetchingAssets(false);
    }
    async function checkExtensionsLimit() {
        const maxExtensions = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].limitation?.max_extensions ?? -1;
        if (maxExtensions < 0) return true;
        try {
            const [pluginsResp, mcpResp] = await Promise.all([
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPlugins(),
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getMCPServers()
            ]);
            const total = (pluginsResp.plugins?.length ?? 0) + (mcpResp.servers?.length ?? 0);
            if (total >= maxExtensions) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('limitation.maxExtensionsReached', {
                    max: maxExtensions
                }));
                return false;
            }
        } catch  {
        // If we can't check, let backend handle it
        }
        return true;
    }
    async function fetchGithubReleases() {
        if (!githubURL.trim()) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.enterRepoUrl'));
            return;
        }
        setFetchingReleases(true);
        setInstallError(null);
        try {
            const result = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getGithubReleases(githubURL);
            setGithubReleases(result.releases);
            setGithubOwner(result.owner);
            setGithubRepo(result.repo);
            if (result.releases.length === 0) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].warning(t('plugins.noReleasesFound'));
            } else {
                setPluginInstallStatus("select_release");
            }
        } catch (error) {
            console.error('Failed to fetch GitHub releases:', error);
            const errorMessage = error instanceof Error ? error.message : String(error);
            setInstallError(errorMessage || t('plugins.fetchReleasesError'));
            setPluginInstallStatus("error");
        } finally{
            setFetchingReleases(false);
        }
    }
    async function handleReleaseSelect(release) {
        setSelectedRelease(release);
        setFetchingAssets(true);
        setInstallError(null);
        try {
            const result = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getGithubReleaseAssets(githubOwner, githubRepo, release.id);
            setGithubAssets(result.assets);
            if (result.assets.length === 0) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].warning(t('plugins.noAssetsFound'));
            } else {
                setPluginInstallStatus("select_asset");
            }
        } catch (error) {
            console.error('Failed to fetch GitHub release assets:', error);
            const errorMessage = error instanceof Error ? error.message : String(error);
            setInstallError(errorMessage || t('plugins.fetchAssetsError'));
            setPluginInstallStatus("error");
        } finally{
            setFetchingAssets(false);
        }
    }
    function handleAssetSelect(asset) {
        setSelectedAsset(asset);
        setPluginInstallStatus("ask_confirm");
    }
    function handleModalConfirm() {
        if (installSource === 'github' && selectedAsset && selectedRelease) {
            installPlugin('github', {
                asset_url: selectedAsset.download_url,
                owner: githubOwner,
                repo: githubRepo,
                release_tag: selectedRelease.tag_name
            });
        } else {
            installPlugin(installSource, installInfo); // eslint-disable-line @typescript-eslint/no-explicit-any
        }
    }
    function installPlugin(installSource, installInfo) {
        setPluginInstallStatus("installing");
        if (installSource === 'github') {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].installPluginFromGithub(installInfo.asset_url, installInfo.owner, installInfo.repo, installInfo.release_tag).then((resp)=>{
                const taskId = resp.task_id;
                watchTask(taskId);
            }).catch((err)=>{
                setInstallError(err.msg);
                setPluginInstallStatus("error");
            });
        } else if (installSource === 'local') {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].installPluginFromLocal(installInfo.file).then((resp)=>{
                const taskId = resp.task_id;
                watchTask(taskId);
            }).catch((err)=>{
                setInstallError(err.msg);
                setPluginInstallStatus("error");
            });
        } else if (installSource === 'marketplace') {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].installPluginFromMarketplace(installInfo.plugin_author, installInfo.plugin_name, installInfo.plugin_version).then((resp)=>{
                const taskId = resp.task_id;
                watchTask(taskId);
            });
        }
    }
    const validateFileType = (file)=>{
        const allowedExtensions = [
            '.lbpkg',
            '.zip'
        ];
        const fileName = file.name.toLowerCase();
        return allowedExtensions.some((ext)=>fileName.endsWith(ext));
    };
    const uploadPluginFile = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async (file)=>{
        if (!pluginSystemStatus?.is_enable || !pluginSystemStatus?.is_connected) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.pluginSystemNotReady'));
            return;
        }
        if (!validateFileType(file)) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.unsupportedFileType'));
            return;
        }
        if (!await checkExtensionsLimit()) return;
        setModalOpen(true);
        setPluginInstallStatus("installing");
        setInstallError(null);
        installPlugin('local', {
            file
        });
    }, [
        t,
        pluginSystemStatus,
        installPlugin
    ]);
    const handleFileSelect = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async ()=>{
        if (!await checkExtensionsLimit()) return;
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    }, []);
    const handleFileChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((event)=>{
        const file = event.target.files?.[0];
        if (file) {
            uploadPluginFile(file);
        }
        event.target.value = '';
    }, [
        uploadPluginFile
    ]);
    const isPluginSystemReady = pluginSystemStatus?.is_enable && pluginSystemStatus?.is_connected;
    const handleDragOver = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((event)=>{
        event.preventDefault();
        if (isPluginSystemReady) {
            setIsDragOver(true);
        }
    }, [
        isPluginSystemReady
    ]);
    const handleDragLeave = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((event)=>{
        event.preventDefault();
        setIsDragOver(false);
    }, []);
    const handleDrop = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((event)=>{
        event.preventDefault();
        setIsDragOver(false);
        if (!isPluginSystemReady) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.pluginSystemNotReady'));
            return;
        }
        const files = Array.from(event.dataTransfer.files);
        if (files.length > 0) {
            uploadPluginFile(files[0]);
        }
    }, [
        uploadPluginFile,
        isPluginSystemReady,
        t
    ]);
    const handleShowDebugInfo = async ()=>{
        try {
            const info = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPluginDebugInfo();
            setDebugInfo(info);
            setDebugPopoverOpen(true);
        } catch (error) {
            console.error('Failed to fetch debug info:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.failedToGetDebugInfo'));
        }
    };
    const handleCopyDebugInfo = (text, type)=>{
        try {
            navigator.clipboard.writeText(text);
            if (type === 'url') {
                setCopiedDebugUrl(true);
                setTimeout(()=>setCopiedDebugUrl(false), 2000);
            } else {
                setCopiedDebugKey(true);
                setTimeout(()=>setCopiedDebugKey(false), 2000);
            }
        } catch  {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.select();
            textArea.setSelectionRange(0, 99999);
            const success = document.execCommand('copy');
            document.body.removeChild(textArea);
            if (success) {
                setCopiedDebugUrl(true);
                setTimeout(()=>setCopiedDebugUrl(false), 2000);
            } else {
                setCopiedDebugKey(true);
                setTimeout(()=>setCopiedDebugKey(false), 2000);
            }
        }
    };
    const renderPluginDisabledState = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex flex-col items-center justify-center h-[60vh] text-center pt-[10vh]",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$power$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Power$3e$__["Power"], {
                    className: "w-16 h-16 text-gray-400 mb-4"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 462,
                    columnNumber: 7
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                    className: "text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2",
                    children: t('plugins.systemDisabled')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 463,
                    columnNumber: 7
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                    className: "text-gray-500 dark:text-gray-400 max-w-md",
                    children: t('plugins.systemDisabledDesc')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 466,
                    columnNumber: 7
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
            lineNumber: 461,
            columnNumber: 5
        }, this);
    const renderPluginConnectionErrorState = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex flex-col items-center justify-center h-[60vh] text-center pt-[10vh]",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                    xmlns: "http://www.w3.org/2000/svg",
                    viewBox: "0 0 24 24",
                    width: "72",
                    height: "72",
                    fill: "#BDBDBD",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                        d: "M17.657 14.8284L16.2428 13.4142L17.657 12C19.2191 10.4379 19.2191 7.90526 17.657 6.34316C16.0949 4.78106 13.5622 4.78106 12.0001 6.34316L10.5859 7.75737L9.17171 6.34316L10.5859 4.92895C12.9291 2.5858 16.7281 2.5858 19.0712 4.92895C21.4143 7.27209 21.4143 11.0711 19.0712 13.4142L17.657 14.8284ZM14.8286 17.6569L13.4143 19.0711C11.0712 21.4142 7.27221 21.4142 4.92907 19.0711C2.58592 16.7279 2.58592 12.9289 4.92907 10.5858L6.34328 9.17159L7.75749 10.5858L6.34328 12C4.78118 13.5621 4.78118 16.0948 6.34328 17.6569C7.90538 19.219 10.438 19.219 12.0001 17.6569L13.4143 16.2427L14.8286 17.6569ZM14.8286 7.75737L16.2428 9.17159L9.17171 16.2427L7.75749 14.8284L14.8286 7.75737ZM5.77539 2.29291L7.70724 1.77527L8.74252 5.63897L6.81067 6.15661L5.77539 2.29291ZM15.2578 18.3611L17.1896 17.8434L18.2249 21.7071L16.293 22.2248L15.2578 18.3611ZM2.29303 5.77527L6.15673 6.81054L5.63909 8.7424L1.77539 7.70712L2.29303 5.77527ZM18.3612 15.2576L22.2249 16.2929L21.7072 18.2248L17.8435 17.1895L18.3612 15.2576Z"
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                        lineNumber: 481,
                        columnNumber: 9
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 474,
                    columnNumber: 7
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                    className: "text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2",
                    children: t('plugins.connectionError')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 484,
                    columnNumber: 7
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                    className: "text-gray-500 dark:text-gray-400 max-w-md mb-4",
                    children: t('plugins.connectionErrorDesc')
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 487,
                    columnNumber: 7
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
            lineNumber: 473,
            columnNumber: 5
        }, this);
    const renderLoadingState = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex flex-col items-center justify-center h-[60vh] pt-[10vh]",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: "text-gray-500 dark:text-gray-400",
                children: t('plugins.loadingStatus')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 495,
                columnNumber: 7
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
            lineNumber: 494,
            columnNumber: 5
        }, this);
    if (statusLoading) {
        return renderLoadingState();
    }
    if (!pluginSystemStatus?.is_enable) {
        return renderPluginDisabledState();
    }
    if (!pluginSystemStatus?.is_connected) {
        return renderPluginConnectionErrorState();
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$plugins$2e$module$2e$css__$5b$app$2d$ssr$5d$__$28$css__module$29$__["default"].pageContainer} h-full flex flex-col ${isDragOver ? 'bg-blue-50' : ''}`,
        onDragOver: handleDragOver,
        onDragLeave: handleDragLeave,
        onDrop: handleDrop,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                ref: fileInputRef,
                type: "file",
                accept: ".lbpkg,.zip",
                onChange: handleFileChange,
                style: {
                    display: 'none'
                }
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 522,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Tabs"], {
                value: activeTab,
                onValueChange: setActiveTab,
                className: "w-full h-full flex flex-col",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex flex-row justify-between items-center px-[0.8rem] flex-shrink-0",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsList"], {
                                className: "shadow-md py-5 bg-[#f0f0f0] dark:bg-[#2a2a2e]",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                        value: "installed",
                                        className: "px-6 py-4 cursor-pointer",
                                        children: t('plugins.installed')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 536,
                                        columnNumber: 13
                                    }, this),
                                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].enable_marketplace && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                        value: "market",
                                        className: "px-6 py-4 cursor-pointer",
                                        children: t('plugins.marketplace')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 540,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                        value: "mcp-servers",
                                        className: "px-6 py-4 cursor-pointer",
                                        children: t('mcp.title')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 544,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 535,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row justify-end items-center gap-2",
                                children: [
                                    activeTab === 'installed' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Popover"], {
                                        open: debugPopoverOpen,
                                        onOpenChange: setDebugPopoverOpen,
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PopoverTrigger"], {
                                                asChild: true,
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                    variant: "outline",
                                                    className: "px-4 py-5 cursor-pointer",
                                                    onClick: handleShowDebugInfo,
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$code$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Code$3e$__["Code"], {
                                                            className: "w-4 h-4 mr-2"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 564,
                                                            columnNumber: 21
                                                        }, this),
                                                        t('plugins.debugInfo')
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 559,
                                                    columnNumber: 19
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                lineNumber: 558,
                                                columnNumber: 17
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PopoverContent"], {
                                                className: "w-[380px]",
                                                align: "end",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "space-y-3",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "flex items-center gap-2 pb-2 border-b",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$bug$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Bug$3e$__["Bug"], {
                                                                    className: "w-4 h-4"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 572,
                                                                    columnNumber: 23
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("h4", {
                                                                    className: "font-semibold text-sm",
                                                                    children: t('plugins.debugInfoTitle')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 573,
                                                                    columnNumber: 23
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 571,
                                                            columnNumber: 21
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "flex items-center gap-2",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                                                    className: "text-sm font-medium whitespace-nowrap min-w-[50px]",
                                                                    children: [
                                                                        t('plugins.debugUrl'),
                                                                        ":"
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 580,
                                                                    columnNumber: 23
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                    value: debugInfo?.debug_url || '',
                                                                    readOnly: true,
                                                                    className: "w-[220px] font-mono text-xs h-8"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 583,
                                                                    columnNumber: 23
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                                    variant: "ghost",
                                                                    size: "icon",
                                                                    className: "h-8 w-8 shrink-0",
                                                                    onClick: ()=>handleCopyDebugInfo(debugInfo?.debug_url || '', 'url'),
                                                                    children: copiedDebugUrl ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$check$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Check$3e$__["Check"], {
                                                                        className: "w-3.5 h-3.5 text-green-600"
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                        lineNumber: 597,
                                                                        columnNumber: 27
                                                                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$copy$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Copy$3e$__["Copy"], {
                                                                        className: "w-3.5 h-3.5"
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                        lineNumber: 599,
                                                                        columnNumber: 27
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 588,
                                                                    columnNumber: 23
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 579,
                                                            columnNumber: 21
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "space-y-1",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "flex items-center gap-2",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                                                            className: "text-sm font-medium whitespace-nowrap min-w-[50px]",
                                                                            children: [
                                                                                t('plugins.debugKey'),
                                                                                ":"
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                            lineNumber: 607,
                                                                            columnNumber: 25
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                                                            value: debugInfo?.plugin_debug_key || t('plugins.noDebugKey'),
                                                                            readOnly: true,
                                                                            className: "w-[220px] font-mono text-xs h-8"
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                            lineNumber: 610,
                                                                            columnNumber: 25
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                                            variant: "ghost",
                                                                            size: "icon",
                                                                            className: "h-8 w-8 shrink-0",
                                                                            onClick: ()=>handleCopyDebugInfo(debugInfo?.plugin_debug_key || '', 'key'),
                                                                            disabled: !debugInfo?.plugin_debug_key,
                                                                            children: copiedDebugKey ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$check$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Check$3e$__["Check"], {
                                                                                className: "w-3.5 h-3.5 text-green-600"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                                lineNumber: 631,
                                                                                columnNumber: 29
                                                                            }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$copy$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Copy$3e$__["Copy"], {
                                                                                className: "w-3.5 h-3.5"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                                lineNumber: 633,
                                                                                columnNumber: 29
                                                                            }, this)
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                            lineNumber: 618,
                                                                            columnNumber: 25
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 606,
                                                                    columnNumber: 23
                                                                }, this),
                                                                !debugInfo?.plugin_debug_key && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                                    className: "text-xs text-muted-foreground ml-[58px]",
                                                                    children: t('plugins.debugKeyDisabled')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 638,
                                                                    columnNumber: 25
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 605,
                                                            columnNumber: 21
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 569,
                                                    columnNumber: 19
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                lineNumber: 568,
                                                columnNumber: 17
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 554,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenu"], {
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuTrigger"], {
                                                asChild: true,
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                                    variant: "default",
                                                    className: "px-6 py-4 cursor-pointer",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__PlusIcon$3e$__["PlusIcon"], {
                                                            className: "w-4 h-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 650,
                                                            columnNumber: 19
                                                        }, this),
                                                        activeTab === 'mcp-servers' ? t('mcp.add') : t('plugins.install'),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$down$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronDownIcon$3e$__["ChevronDownIcon"], {
                                                            className: "ml-2 w-4 h-4"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 654,
                                                            columnNumber: 19
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 649,
                                                    columnNumber: 17
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                lineNumber: 648,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuContent"], {
                                                align: "end",
                                                children: activeTab === 'mcp-servers' ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                        onClick: async ()=>{
                                                            if (!await checkExtensionsLimit()) return;
                                                            setActiveTab('mcp-servers');
                                                            setIsEditMode(false);
                                                            setEditingServerName(null);
                                                            setMcpSSEModalOpen(true);
                                                        },
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__PlusIcon$3e$__["PlusIcon"], {
                                                                className: "w-4 h-4"
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                lineNumber: 669,
                                                                columnNumber: 23
                                                            }, this),
                                                            t('mcp.createServer')
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                        lineNumber: 660,
                                                        columnNumber: 21
                                                    }, this)
                                                }, void 0, false) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                                    children: [
                                                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].enable_marketplace && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                            onClick: ()=>{
                                                                setActiveTab('market');
                                                            },
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$store$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__StoreIcon$3e$__["StoreIcon"], {
                                                                    className: "w-4 h-4"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 681,
                                                                    columnNumber: 25
                                                                }, this),
                                                                t('plugins.marketplace')
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 676,
                                                            columnNumber: 23
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                            onClick: handleFileSelect,
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$upload$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__UploadIcon$3e$__["UploadIcon"], {
                                                                    className: "w-4 h-4"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 686,
                                                                    columnNumber: 23
                                                                }, this),
                                                                t('plugins.uploadLocal')
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 685,
                                                            columnNumber: 21
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dropdown$2d$menu$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DropdownMenuItem"], {
                                                            onClick: async ()=>{
                                                                if (!await checkExtensionsLimit()) return;
                                                                setInstallSource('github');
                                                                setPluginInstallStatus("wait_input");
                                                                setInstallError(null);
                                                                resetGithubState();
                                                                setModalOpen(true);
                                                            },
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$github$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Github$3e$__["Github"], {
                                                                    className: "w-4 h-4"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                    lineNumber: 699,
                                                                    columnNumber: 23
                                                                }, this),
                                                                t('plugins.installFromGithub')
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                            lineNumber: 689,
                                                            columnNumber: 21
                                                        }, this)
                                                    ]
                                                }, void 0, true)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                lineNumber: 657,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 647,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 552,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                        lineNumber: 534,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsContent"], {
                        value: "installed",
                        className: "flex-1 overflow-y-auto mt-0",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginInstalledComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                            ref: pluginInstalledRef
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 709,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                        lineNumber: 708,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsContent"], {
                        value: "market",
                        className: "flex-1 overflow-y-auto mt-0",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$market$2f$PluginMarketComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                            installPlugin: async (plugin)=>{
                                if (!await checkExtensionsLimit()) return;
                                setInstallSource('marketplace');
                                setInstallInfo({
                                    plugin_author: plugin.author,
                                    plugin_name: plugin.name,
                                    plugin_version: plugin.latest_version
                                });
                                setPluginInstallStatus("ask_confirm");
                                setModalOpen(true);
                            }
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 712,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                        lineNumber: 711,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["TabsContent"], {
                        value: "mcp-servers",
                        className: "flex-1 overflow-y-auto mt-0",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$MCPServerComponent$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                            onEditServer: (serverName)=>{
                                setEditingServerName(serverName);
                                setIsEditMode(true);
                                setMcpSSEModalOpen(true);
                            }
                        }, refreshKey, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 730,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                        lineNumber: 726,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 529,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Dialog"], {
                open: modalOpen,
                onOpenChange: (open)=>{
                    setModalOpen(open);
                    if (!open) {
                        resetGithubState();
                        setInstallError(null);
                    }
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogContent"], {
                    className: "w-[500px] max-h-[80vh] p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                className: "flex items-center gap-4",
                                children: [
                                    installSource === 'github' ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$github$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Github$3e$__["Github"], {
                                        className: "size-6"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 755,
                                        columnNumber: 17
                                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$download$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__Download$3e$__["Download"], {
                                        className: "size-6"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 757,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        children: t('plugins.installPlugin')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                        lineNumber: 759,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 753,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 752,
                            columnNumber: 11
                        }, this),
                        installSource === 'github' && pluginInstallStatus === "wait_input" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "mb-2",
                                    children: t('plugins.enterRepoUrl')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 767,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Input"], {
                                    placeholder: t('plugins.repoUrlPlaceholder'),
                                    value: githubURL,
                                    onChange: (e)=>setGithubURL(e.target.value),
                                    className: "mb-4"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 768,
                                    columnNumber: 17
                                }, this),
                                fetchingReleases && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-gray-500",
                                    children: t('plugins.fetchingReleases')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 775,
                                    columnNumber: 19
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 766,
                            columnNumber: 15
                        }, this),
                        installSource === 'github' && pluginInstallStatus === "select_release" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between mb-4",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            className: "font-medium",
                                            children: t('plugins.selectRelease')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 786,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "ghost",
                                            size: "sm",
                                            onClick: ()=>{
                                                setPluginInstallStatus("wait_input");
                                                setGithubReleases([]);
                                            },
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$left$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronLeft$3e$__["ChevronLeft"], {
                                                    className: "w-4 h-4 mr-1"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 795,
                                                    columnNumber: 21
                                                }, this),
                                                t('plugins.backToRepoUrl')
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 787,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 785,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "max-h-[400px] overflow-y-auto space-y-2 pb-2",
                                    children: githubReleases.map((release)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Card"], {
                                            className: "cursor-pointer hover:shadow-sm transition-shadow duration-200 shadow-none py-4",
                                            onClick: ()=>handleReleaseSelect(release),
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardHeader"], {
                                                className: "flex flex-row items-start justify-between px-3 space-y-0",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "flex-1",
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardTitle"], {
                                                                className: "text-sm",
                                                                children: release.name || release.tag_name
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                lineNumber: 808,
                                                                columnNumber: 27
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardDescription"], {
                                                                className: "text-xs mt-1",
                                                                children: [
                                                                    t('plugins.releaseTag', {
                                                                        tag: release.tag_name
                                                                    }),
                                                                    ' ',
                                                                    "•",
                                                                    ' ',
                                                                    t('plugins.publishedAt', {
                                                                        date: new Date(release.published_at).toLocaleDateString()
                                                                    })
                                                                ]
                                                            }, void 0, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                                lineNumber: 811,
                                                                columnNumber: 27
                                                            }, this)
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                        lineNumber: 807,
                                                        columnNumber: 25
                                                    }, this),
                                                    release.prerelease && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded ml-2 shrink-0",
                                                        children: t('plugins.prerelease')
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                        lineNumber: 822,
                                                        columnNumber: 27
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                lineNumber: 806,
                                                columnNumber: 23
                                            }, this)
                                        }, release.id, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 801,
                                            columnNumber: 21
                                        }, this))
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 799,
                                    columnNumber: 17
                                }, this),
                                fetchingAssets && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-gray-500 mt-4",
                                    children: t('plugins.loading')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 831,
                                    columnNumber: 19
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 784,
                            columnNumber: 15
                        }, this),
                        installSource === 'github' && pluginInstallStatus === "select_asset" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between mb-4",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            className: "font-medium",
                                            children: t('plugins.selectAsset')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 842,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "ghost",
                                            size: "sm",
                                            onClick: ()=>{
                                                setPluginInstallStatus("select_release");
                                                setGithubAssets([]);
                                                setSelectedAsset(null);
                                            },
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$left$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronLeft$3e$__["ChevronLeft"], {
                                                    className: "w-4 h-4 mr-1"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 854,
                                                    columnNumber: 21
                                                }, this),
                                                t('plugins.backToReleases')
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 843,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 841,
                                    columnNumber: 17
                                }, this),
                                selectedRelease && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "mb-4 p-2 bg-gray-50 dark:bg-gray-900 rounded",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "text-sm font-medium",
                                            children: selectedRelease.name || selectedRelease.tag_name
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 860,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "text-xs text-gray-500",
                                            children: selectedRelease.tag_name
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 863,
                                            columnNumber: 21
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 859,
                                    columnNumber: 19
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "max-h-[400px] overflow-y-auto space-y-2 pb-2",
                                    children: githubAssets.map((asset)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Card"], {
                                            className: "cursor-pointer hover:shadow-sm transition-shadow duration-200 shadow-none py-3",
                                            onClick: ()=>handleAssetSelect(asset),
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardHeader"], {
                                                className: "px-3",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardTitle"], {
                                                        className: "text-sm",
                                                        children: asset.name
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                        lineNumber: 876,
                                                        columnNumber: 25
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["CardDescription"], {
                                                        className: "text-xs",
                                                        children: t('plugins.assetSize', {
                                                            size: formatFileSize(asset.size)
                                                        })
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                        lineNumber: 877,
                                                        columnNumber: 25
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                lineNumber: 875,
                                                columnNumber: 23
                                            }, this)
                                        }, asset.id, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 870,
                                            columnNumber: 21
                                        }, this))
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 868,
                                    columnNumber: 17
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 840,
                            columnNumber: 15
                        }, this),
                        installSource === 'marketplace' && pluginInstallStatus === "ask_confirm" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "mb-2",
                                children: t('plugins.askConfirm', {
                                    name: installInfo.plugin_name,
                                    version: installInfo.plugin_version
                                })
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 893,
                                columnNumber: 17
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 892,
                            columnNumber: 15
                        }, this),
                        installSource === 'github' && pluginInstallStatus === "ask_confirm" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between mb-4",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            className: "font-medium",
                                            children: t('plugins.confirmInstall')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 907,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "ghost",
                                            size: "sm",
                                            onClick: ()=>{
                                                setPluginInstallStatus("select_asset");
                                                setSelectedAsset(null);
                                            },
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$left$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronLeft$3e$__["ChevronLeft"], {
                                                    className: "w-4 h-4 mr-1"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 916,
                                                    columnNumber: 21
                                                }, this),
                                                t('plugins.backToAssets')
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 908,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 906,
                                    columnNumber: 17
                                }, this),
                                selectedRelease && selectedAsset && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "p-3 bg-gray-50 dark:bg-gray-900 rounded space-y-2",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-sm font-medium",
                                                    children: "Repository: "
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 923,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-sm",
                                                    children: [
                                                        githubOwner,
                                                        "/",
                                                        githubRepo
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 924,
                                                    columnNumber: 23
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 922,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-sm font-medium",
                                                    children: "Release: "
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 929,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-sm",
                                                    children: selectedRelease.tag_name
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 930,
                                                    columnNumber: 23
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 928,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-sm font-medium",
                                                    children: "File: "
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 935,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-sm",
                                                    children: selectedAsset.name
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                                    lineNumber: 936,
                                                    columnNumber: 23
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 934,
                                            columnNumber: 21
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 921,
                                    columnNumber: 19
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 905,
                            columnNumber: 15
                        }, this),
                        pluginInstallStatus === "installing" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "mb-2",
                                children: t('plugins.installing')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 946,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 945,
                            columnNumber: 13
                        }, this),
                        pluginInstallStatus === "error" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "mt-4",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "mb-2",
                                    children: t('plugins.installFailed')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 953,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "mb-2 text-red-500",
                                    children: installError
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 954,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 952,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DialogFooter"], {
                            children: [
                                pluginInstallStatus === "wait_input" && installSource === 'github' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "outline",
                                            onClick: ()=>{
                                                setModalOpen(false);
                                                resetGithubState();
                                            },
                                            children: t('common.cancel')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 962,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            onClick: fetchGithubReleases,
                                            disabled: !githubURL.trim() || fetchingReleases,
                                            children: fetchingReleases ? t('plugins.loading') : t('common.confirm')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 971,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, void 0, true),
                                pluginInstallStatus === "ask_confirm" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "outline",
                                            onClick: ()=>setModalOpen(false),
                                            children: t('common.cancel')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 983,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                            onClick: ()=>handleModalConfirm(),
                                            children: t('common.confirm')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                            lineNumber: 986,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true),
                                pluginInstallStatus === "error" && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "default",
                                    onClick: ()=>setModalOpen(false),
                                    children: t('common.close')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                    lineNumber: 992,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                            lineNumber: 958,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 751,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 741,
                columnNumber: 7
            }, this),
            isDragOver && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "fixed inset-0 bg-gray-500 bg-opacity-50 flex items-center justify-center z-50 pointer-events-none",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "bg-white rounded-lg p-8 shadow-lg border-2 border-dashed border-gray-500",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "text-center",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$upload$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__default__as__UploadIcon$3e$__["UploadIcon"], {
                                className: "mx-auto h-12 w-12 text-gray-500 mb-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 1004,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-lg font-medium text-gray-700",
                                children: t('plugins.dragToUpload')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                                lineNumber: 1005,
                                columnNumber: 15
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                        lineNumber: 1003,
                        columnNumber: 13
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                    lineNumber: 1002,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 1001,
                columnNumber: 9
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$mcp$2d$form$2f$MCPFormDialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                open: mcpSSEModalOpen,
                onOpenChange: setMcpSSEModalOpen,
                serverName: editingServerName,
                isEditMode: isEditMode,
                onSuccess: ()=>{
                    setEditingServerName(null);
                    setIsEditMode(false);
                    setRefreshKey((prev)=>prev + 1);
                },
                onDelete: ()=>{
                    setShowDeleteConfirmModal(true);
                }
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 1013,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$mcp$2d$server$2f$mcp$2d$form$2f$MCPDeleteConfirmDialog$2e$tsx__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"], {
                open: showDeleteConfirmModal,
                onOpenChange: setShowDeleteConfirmModal,
                serverName: editingServerName,
                onSuccess: ()=>{
                    setMcpSSEModalOpen(false);
                    setEditingServerName(null);
                    setIsEditMode(false);
                    setRefreshKey((prev)=>prev + 1);
                }
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
                lineNumber: 1028,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/page.tsx",
        lineNumber: 514,
        columnNumber: 5
    }, this);
}
}),
];

//# sourceMappingURL=coding_projects_LangBot_web_src_4aa66669._.js.map