(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/panel-left.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>PanelLeft
]);
/**
 * @license lucide-react v0.507.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$createLucideIcon$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/createLucideIcon.js [app-client] (ecmascript)");
;
const __iconNode = [
    [
        "rect",
        {
            width: "18",
            height: "18",
            x: "3",
            y: "3",
            rx: "2",
            key: "afitv7"
        }
    ],
    [
        "path",
        {
            d: "M9 3v18",
            key: "fh3hqa"
        }
    ]
];
const PanelLeft = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$createLucideIcon$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])("panel-left", __iconNode);
;
 //# sourceMappingURL=panel-left.js.map
}),
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/panel-left.js [app-client] (ecmascript) <export default as PanelLeftIcon>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PanelLeftIcon",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$panel$2d$left$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$panel$2d$left$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/panel-left.js [app-client] (ecmascript)");
}),
"[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-tooltip/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Root",
    ()=>Slot,
    "Slot",
    ()=>Slot,
    "Slottable",
    ()=>Slottable,
    "createSlot",
    ()=>createSlot,
    "createSlottable",
    ()=>createSlottable
]);
// src/slot.tsx
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-compose-refs/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
;
;
;
// @__NO_SIDE_EFFECTS__
function createSlot(ownerName) {
    const SlotClone = /* @__PURE__ */ createSlotClone(ownerName);
    const Slot2 = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
        const { children, ...slotProps } = props;
        const childrenArray = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].toArray(children);
        const slottable = childrenArray.find(isSlottable);
        if (slottable) {
            const newElement = slottable.props.children;
            const newChildren = childrenArray.map((child)=>{
                if (child === slottable) {
                    if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].count(newElement) > 1) return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].only(null);
                    return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](newElement) ? newElement.props.children : null;
                } else {
                    return child;
                }
            });
            return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(SlotClone, {
                ...slotProps,
                ref: forwardedRef,
                children: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](newElement) ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"](newElement, void 0, newChildren) : null
            });
        }
        return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(SlotClone, {
            ...slotProps,
            ref: forwardedRef,
            children
        });
    });
    Slot2.displayName = `${ownerName}.Slot`;
    return Slot2;
}
var Slot = /* @__PURE__ */ createSlot("Slot");
// @__NO_SIDE_EFFECTS__
function createSlotClone(ownerName) {
    const SlotClone = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
        const { children, ...slotProps } = props;
        if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](children)) {
            const childrenRef = getElementRef(children);
            const props2 = mergeProps(slotProps, children.props);
            if (children.type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"]) {
                props2.ref = forwardedRef ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeRefs"])(forwardedRef, childrenRef) : childrenRef;
            }
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"](children, props2);
        }
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].count(children) > 1 ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].only(null) : null;
    });
    SlotClone.displayName = `${ownerName}.SlotClone`;
    return SlotClone;
}
var SLOTTABLE_IDENTIFIER = Symbol("radix.slottable");
// @__NO_SIDE_EFFECTS__
function createSlottable(ownerName) {
    const Slottable2 = ({ children })=>{
        return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children
        });
    };
    Slottable2.displayName = `${ownerName}.Slottable`;
    Slottable2.__radixId = SLOTTABLE_IDENTIFIER;
    return Slottable2;
}
var Slottable = /* @__PURE__ */ createSlottable("Slottable");
function isSlottable(child) {
    return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](child) && typeof child.type === "function" && "__radixId" in child.type && child.type.__radixId === SLOTTABLE_IDENTIFIER;
}
function mergeProps(slotProps, childProps) {
    const overrideProps = {
        ...childProps
    };
    for(const propName in childProps){
        const slotPropValue = slotProps[propName];
        const childPropValue = childProps[propName];
        const isHandler = /^on[A-Z]/.test(propName);
        if (isHandler) {
            if (slotPropValue && childPropValue) {
                overrideProps[propName] = (...args)=>{
                    const result = childPropValue(...args);
                    slotPropValue(...args);
                    return result;
                };
            } else if (slotPropValue) {
                overrideProps[propName] = slotPropValue;
            }
        } else if (propName === "style") {
            overrideProps[propName] = {
                ...slotPropValue,
                ...childPropValue
            };
        } else if (propName === "className") {
            overrideProps[propName] = [
                slotPropValue,
                childPropValue
            ].filter(Boolean).join(" ");
        }
    }
    return {
        ...slotProps,
        ...overrideProps
    };
}
function getElementRef(element) {
    let getter = Object.getOwnPropertyDescriptor(element.props, "ref")?.get;
    let mayWarn = getter && "isReactWarning" in getter && getter.isReactWarning;
    if (mayWarn) {
        return element.ref;
    }
    getter = Object.getOwnPropertyDescriptor(element, "ref")?.get;
    mayWarn = getter && "isReactWarning" in getter && getter.isReactWarning;
    if (mayWarn) {
        return element.props.ref;
    }
    return element.props.ref || element.ref;
}
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-tooltip/dist/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Arrow",
    ()=>Arrow2,
    "Content",
    ()=>Content2,
    "Portal",
    ()=>Portal,
    "Provider",
    ()=>Provider,
    "Root",
    ()=>Root3,
    "Tooltip",
    ()=>Tooltip,
    "TooltipArrow",
    ()=>TooltipArrow,
    "TooltipContent",
    ()=>TooltipContent,
    "TooltipPortal",
    ()=>TooltipPortal,
    "TooltipProvider",
    ()=>TooltipProvider,
    "TooltipTrigger",
    ()=>TooltipTrigger,
    "Trigger",
    ()=>Trigger,
    "createTooltipScope",
    ()=>createTooltipScope
]);
// src/tooltip.tsx
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-compose-refs/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-context/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dismissable$2d$layer$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-dismissable-layer/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-id/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-popper/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$portal$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-portal/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-presence/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-tooltip/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-use-controllable-state/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$visually$2d$hidden$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-visually-hidden/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
"use client";
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
var [createTooltipContext, createTooltipScope] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContextScope"])("Tooltip", [
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPopperScope"]
]);
var usePopperScope = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPopperScope"])();
var PROVIDER_NAME = "TooltipProvider";
var DEFAULT_DELAY_DURATION = 700;
var TOOLTIP_OPEN = "tooltip.open";
var [TooltipProviderContextProvider, useTooltipProviderContext] = createTooltipContext(PROVIDER_NAME);
var TooltipProvider = (props)=>{
    const { __scopeTooltip, delayDuration = DEFAULT_DELAY_DURATION, skipDelayDuration = 300, disableHoverableContent = false, children } = props;
    const isOpenDelayedRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](true);
    const isPointerInTransitRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const skipDelayTimerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipProvider.useEffect": ()=>{
            const skipDelayTimer = skipDelayTimerRef.current;
            return ({
                "TooltipProvider.useEffect": ()=>window.clearTimeout(skipDelayTimer)
            })["TooltipProvider.useEffect"];
        }
    }["TooltipProvider.useEffect"], []);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TooltipProviderContextProvider, {
        scope: __scopeTooltip,
        isOpenDelayedRef,
        delayDuration,
        onOpen: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "TooltipProvider.useCallback": ()=>{
                window.clearTimeout(skipDelayTimerRef.current);
                isOpenDelayedRef.current = false;
            }
        }["TooltipProvider.useCallback"], []),
        onClose: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "TooltipProvider.useCallback": ()=>{
                window.clearTimeout(skipDelayTimerRef.current);
                skipDelayTimerRef.current = window.setTimeout({
                    "TooltipProvider.useCallback": ()=>isOpenDelayedRef.current = true
                }["TooltipProvider.useCallback"], skipDelayDuration);
            }
        }["TooltipProvider.useCallback"], [
            skipDelayDuration
        ]),
        isPointerInTransitRef,
        onPointerInTransitChange: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "TooltipProvider.useCallback": (inTransit)=>{
                isPointerInTransitRef.current = inTransit;
            }
        }["TooltipProvider.useCallback"], []),
        disableHoverableContent,
        children
    });
};
TooltipProvider.displayName = PROVIDER_NAME;
var TOOLTIP_NAME = "Tooltip";
var [TooltipContextProvider, useTooltipContext] = createTooltipContext(TOOLTIP_NAME);
var Tooltip = (props)=>{
    const { __scopeTooltip, children, open: openProp, defaultOpen, onOpenChange, disableHoverableContent: disableHoverableContentProp, delayDuration: delayDurationProp } = props;
    const providerContext = useTooltipProviderContext(TOOLTIP_NAME, props.__scopeTooltip);
    const popperScope = usePopperScope(__scopeTooltip);
    const [trigger, setTrigger] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const contentId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])();
    const openTimerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    const disableHoverableContent = disableHoverableContentProp ?? providerContext.disableHoverableContent;
    const delayDuration = delayDurationProp ?? providerContext.delayDuration;
    const wasOpenDelayedRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const [open, setOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useControllableState"])({
        prop: openProp,
        defaultProp: defaultOpen ?? false,
        onChange: {
            "Tooltip.useControllableState": (open2)=>{
                if (open2) {
                    providerContext.onOpen();
                    document.dispatchEvent(new CustomEvent(TOOLTIP_OPEN));
                } else {
                    providerContext.onClose();
                }
                onOpenChange?.(open2);
            }
        }["Tooltip.useControllableState"],
        caller: TOOLTIP_NAME
    });
    const stateAttribute = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "Tooltip.useMemo[stateAttribute]": ()=>{
            return open ? wasOpenDelayedRef.current ? "delayed-open" : "instant-open" : "closed";
        }
    }["Tooltip.useMemo[stateAttribute]"], [
        open
    ]);
    const handleOpen = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "Tooltip.useCallback[handleOpen]": ()=>{
            window.clearTimeout(openTimerRef.current);
            openTimerRef.current = 0;
            wasOpenDelayedRef.current = false;
            setOpen(true);
        }
    }["Tooltip.useCallback[handleOpen]"], [
        setOpen
    ]);
    const handleClose = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "Tooltip.useCallback[handleClose]": ()=>{
            window.clearTimeout(openTimerRef.current);
            openTimerRef.current = 0;
            setOpen(false);
        }
    }["Tooltip.useCallback[handleClose]"], [
        setOpen
    ]);
    const handleDelayedOpen = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "Tooltip.useCallback[handleDelayedOpen]": ()=>{
            window.clearTimeout(openTimerRef.current);
            openTimerRef.current = window.setTimeout({
                "Tooltip.useCallback[handleDelayedOpen]": ()=>{
                    wasOpenDelayedRef.current = true;
                    setOpen(true);
                    openTimerRef.current = 0;
                }
            }["Tooltip.useCallback[handleDelayedOpen]"], delayDuration);
        }
    }["Tooltip.useCallback[handleDelayedOpen]"], [
        delayDuration,
        setOpen
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "Tooltip.useEffect": ()=>{
            return ({
                "Tooltip.useEffect": ()=>{
                    if (openTimerRef.current) {
                        window.clearTimeout(openTimerRef.current);
                        openTimerRef.current = 0;
                    }
                }
            })["Tooltip.useEffect"];
        }
    }["Tooltip.useEffect"], []);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
        ...popperScope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TooltipContextProvider, {
            scope: __scopeTooltip,
            contentId,
            open,
            stateAttribute,
            trigger,
            onTriggerChange: setTrigger,
            onTriggerEnter: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
                "Tooltip.useCallback": ()=>{
                    if (providerContext.isOpenDelayedRef.current) handleDelayedOpen();
                    else handleOpen();
                }
            }["Tooltip.useCallback"], [
                providerContext.isOpenDelayedRef,
                handleDelayedOpen,
                handleOpen
            ]),
            onTriggerLeave: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
                "Tooltip.useCallback": ()=>{
                    if (disableHoverableContent) {
                        handleClose();
                    } else {
                        window.clearTimeout(openTimerRef.current);
                        openTimerRef.current = 0;
                    }
                }
            }["Tooltip.useCallback"], [
                handleClose,
                disableHoverableContent
            ]),
            onOpen: handleOpen,
            onClose: handleClose,
            disableHoverableContent,
            children
        })
    });
};
Tooltip.displayName = TOOLTIP_NAME;
var TRIGGER_NAME = "TooltipTrigger";
var TooltipTrigger = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeTooltip, ...triggerProps } = props;
    const context = useTooltipContext(TRIGGER_NAME, __scopeTooltip);
    const providerContext = useTooltipProviderContext(TRIGGER_NAME, __scopeTooltip);
    const popperScope = usePopperScope(__scopeTooltip);
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref, context.onTriggerChange);
    const isPointerDownRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const hasPointerMoveOpenedRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const handlePointerUp = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "TooltipTrigger.useCallback[handlePointerUp]": ()=>isPointerDownRef.current = false
    }["TooltipTrigger.useCallback[handlePointerUp]"], []);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipTrigger.useEffect": ()=>{
            return ({
                "TooltipTrigger.useEffect": ()=>document.removeEventListener("pointerup", handlePointerUp)
            })["TooltipTrigger.useEffect"];
        }
    }["TooltipTrigger.useEffect"], [
        handlePointerUp
    ]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Anchor"], {
        asChild: true,
        ...popperScope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].button, {
            "aria-describedby": context.open ? context.contentId : void 0,
            "data-state": context.stateAttribute,
            ...triggerProps,
            ref: composedRefs,
            onPointerMove: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerMove, (event)=>{
                if (event.pointerType === "touch") return;
                if (!hasPointerMoveOpenedRef.current && !providerContext.isPointerInTransitRef.current) {
                    context.onTriggerEnter();
                    hasPointerMoveOpenedRef.current = true;
                }
            }),
            onPointerLeave: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerLeave, ()=>{
                context.onTriggerLeave();
                hasPointerMoveOpenedRef.current = false;
            }),
            onPointerDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerDown, ()=>{
                if (context.open) {
                    context.onClose();
                }
                isPointerDownRef.current = true;
                document.addEventListener("pointerup", handlePointerUp, {
                    once: true
                });
            }),
            onFocus: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onFocus, ()=>{
                if (!isPointerDownRef.current) context.onOpen();
            }),
            onBlur: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onBlur, context.onClose),
            onClick: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onClick, context.onClose)
        })
    });
});
TooltipTrigger.displayName = TRIGGER_NAME;
var PORTAL_NAME = "TooltipPortal";
var [PortalProvider, usePortalContext] = createTooltipContext(PORTAL_NAME, {
    forceMount: void 0
});
var TooltipPortal = (props)=>{
    const { __scopeTooltip, forceMount, children, container } = props;
    const context = useTooltipContext(PORTAL_NAME, __scopeTooltip);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(PortalProvider, {
        scope: __scopeTooltip,
        forceMount,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
            present: forceMount || context.open,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$portal$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Portal"], {
                asChild: true,
                container,
                children
            })
        })
    });
};
TooltipPortal.displayName = PORTAL_NAME;
var CONTENT_NAME = "TooltipContent";
var TooltipContent = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const portalContext = usePortalContext(CONTENT_NAME, props.__scopeTooltip);
    const { forceMount = portalContext.forceMount, side = "top", ...contentProps } = props;
    const context = useTooltipContext(CONTENT_NAME, props.__scopeTooltip);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
        present: forceMount || context.open,
        children: context.disableHoverableContent ? /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TooltipContentImpl, {
            side,
            ...contentProps,
            ref: forwardedRef
        }) : /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TooltipContentHoverable, {
            side,
            ...contentProps,
            ref: forwardedRef
        })
    });
});
var TooltipContentHoverable = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const context = useTooltipContext(CONTENT_NAME, props.__scopeTooltip);
    const providerContext = useTooltipProviderContext(CONTENT_NAME, props.__scopeTooltip);
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref);
    const [pointerGraceArea, setPointerGraceArea] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const { trigger, onClose } = context;
    const content = ref.current;
    const { onPointerInTransitChange } = providerContext;
    const handleRemoveGraceArea = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "TooltipContentHoverable.useCallback[handleRemoveGraceArea]": ()=>{
            setPointerGraceArea(null);
            onPointerInTransitChange(false);
        }
    }["TooltipContentHoverable.useCallback[handleRemoveGraceArea]"], [
        onPointerInTransitChange
    ]);
    const handleCreateGraceArea = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "TooltipContentHoverable.useCallback[handleCreateGraceArea]": (event, hoverTarget)=>{
            const currentTarget = event.currentTarget;
            const exitPoint = {
                x: event.clientX,
                y: event.clientY
            };
            const exitSide = getExitSideFromRect(exitPoint, currentTarget.getBoundingClientRect());
            const paddedExitPoints = getPaddedExitPoints(exitPoint, exitSide);
            const hoverTargetPoints = getPointsFromRect(hoverTarget.getBoundingClientRect());
            const graceArea = getHull([
                ...paddedExitPoints,
                ...hoverTargetPoints
            ]);
            setPointerGraceArea(graceArea);
            onPointerInTransitChange(true);
        }
    }["TooltipContentHoverable.useCallback[handleCreateGraceArea]"], [
        onPointerInTransitChange
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipContentHoverable.useEffect": ()=>{
            return ({
                "TooltipContentHoverable.useEffect": ()=>handleRemoveGraceArea()
            })["TooltipContentHoverable.useEffect"];
        }
    }["TooltipContentHoverable.useEffect"], [
        handleRemoveGraceArea
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipContentHoverable.useEffect": ()=>{
            if (trigger && content) {
                const handleTriggerLeave = {
                    "TooltipContentHoverable.useEffect.handleTriggerLeave": (event)=>handleCreateGraceArea(event, content)
                }["TooltipContentHoverable.useEffect.handleTriggerLeave"];
                const handleContentLeave = {
                    "TooltipContentHoverable.useEffect.handleContentLeave": (event)=>handleCreateGraceArea(event, trigger)
                }["TooltipContentHoverable.useEffect.handleContentLeave"];
                trigger.addEventListener("pointerleave", handleTriggerLeave);
                content.addEventListener("pointerleave", handleContentLeave);
                return ({
                    "TooltipContentHoverable.useEffect": ()=>{
                        trigger.removeEventListener("pointerleave", handleTriggerLeave);
                        content.removeEventListener("pointerleave", handleContentLeave);
                    }
                })["TooltipContentHoverable.useEffect"];
            }
        }
    }["TooltipContentHoverable.useEffect"], [
        trigger,
        content,
        handleCreateGraceArea,
        handleRemoveGraceArea
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipContentHoverable.useEffect": ()=>{
            if (pointerGraceArea) {
                const handleTrackPointerGrace = {
                    "TooltipContentHoverable.useEffect.handleTrackPointerGrace": (event)=>{
                        const target = event.target;
                        const pointerPosition = {
                            x: event.clientX,
                            y: event.clientY
                        };
                        const hasEnteredTarget = trigger?.contains(target) || content?.contains(target);
                        const isPointerOutsideGraceArea = !isPointInPolygon(pointerPosition, pointerGraceArea);
                        if (hasEnteredTarget) {
                            handleRemoveGraceArea();
                        } else if (isPointerOutsideGraceArea) {
                            handleRemoveGraceArea();
                            onClose();
                        }
                    }
                }["TooltipContentHoverable.useEffect.handleTrackPointerGrace"];
                document.addEventListener("pointermove", handleTrackPointerGrace);
                return ({
                    "TooltipContentHoverable.useEffect": ()=>document.removeEventListener("pointermove", handleTrackPointerGrace)
                })["TooltipContentHoverable.useEffect"];
            }
        }
    }["TooltipContentHoverable.useEffect"], [
        trigger,
        content,
        pointerGraceArea,
        onClose,
        handleRemoveGraceArea
    ]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TooltipContentImpl, {
        ...props,
        ref: composedRefs
    });
});
var [VisuallyHiddenContentContextProvider, useVisuallyHiddenContentContext] = createTooltipContext(TOOLTIP_NAME, {
    isInside: false
});
var Slottable = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createSlottable"])("TooltipContent");
var TooltipContentImpl = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeTooltip, children, "aria-label": ariaLabel, onEscapeKeyDown, onPointerDownOutside, ...contentProps } = props;
    const context = useTooltipContext(CONTENT_NAME, __scopeTooltip);
    const popperScope = usePopperScope(__scopeTooltip);
    const { onClose } = context;
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipContentImpl.useEffect": ()=>{
            document.addEventListener(TOOLTIP_OPEN, onClose);
            return ({
                "TooltipContentImpl.useEffect": ()=>document.removeEventListener(TOOLTIP_OPEN, onClose)
            })["TooltipContentImpl.useEffect"];
        }
    }["TooltipContentImpl.useEffect"], [
        onClose
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "TooltipContentImpl.useEffect": ()=>{
            if (context.trigger) {
                const handleScroll = {
                    "TooltipContentImpl.useEffect.handleScroll": (event)=>{
                        const target = event.target;
                        if (target?.contains(context.trigger)) onClose();
                    }
                }["TooltipContentImpl.useEffect.handleScroll"];
                window.addEventListener("scroll", handleScroll, {
                    capture: true
                });
                return ({
                    "TooltipContentImpl.useEffect": ()=>window.removeEventListener("scroll", handleScroll, {
                            capture: true
                        })
                })["TooltipContentImpl.useEffect"];
            }
        }
    }["TooltipContentImpl.useEffect"], [
        context.trigger,
        onClose
    ]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dismissable$2d$layer$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DismissableLayer"], {
        asChild: true,
        disableOutsidePointerEvents: false,
        onEscapeKeyDown,
        onPointerDownOutside,
        onFocusOutside: (event)=>event.preventDefault(),
        onDismiss: onClose,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Content"], {
            "data-state": context.stateAttribute,
            ...popperScope,
            ...contentProps,
            ref: forwardedRef,
            style: {
                ...contentProps.style,
                // re-namespace exposed content custom properties
                ...{
                    "--radix-tooltip-content-transform-origin": "var(--radix-popper-transform-origin)",
                    "--radix-tooltip-content-available-width": "var(--radix-popper-available-width)",
                    "--radix-tooltip-content-available-height": "var(--radix-popper-available-height)",
                    "--radix-tooltip-trigger-width": "var(--radix-popper-anchor-width)",
                    "--radix-tooltip-trigger-height": "var(--radix-popper-anchor-height)"
                }
            },
            children: [
                /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Slottable, {
                    children
                }),
                /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(VisuallyHiddenContentContextProvider, {
                    scope: __scopeTooltip,
                    isInside: true,
                    children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$visually$2d$hidden$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
                        id: context.contentId,
                        role: "tooltip",
                        children: ariaLabel || children
                    })
                })
            ]
        })
    });
});
TooltipContent.displayName = CONTENT_NAME;
var ARROW_NAME = "TooltipArrow";
var TooltipArrow = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeTooltip, ...arrowProps } = props;
    const popperScope = usePopperScope(__scopeTooltip);
    const visuallyHiddenContentContext = useVisuallyHiddenContentContext(ARROW_NAME, __scopeTooltip);
    return visuallyHiddenContentContext.isInside ? null : /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Arrow"], {
        ...popperScope,
        ...arrowProps,
        ref: forwardedRef
    });
});
TooltipArrow.displayName = ARROW_NAME;
function getExitSideFromRect(point, rect) {
    const top = Math.abs(rect.top - point.y);
    const bottom = Math.abs(rect.bottom - point.y);
    const right = Math.abs(rect.right - point.x);
    const left = Math.abs(rect.left - point.x);
    switch(Math.min(top, bottom, right, left)){
        case left:
            return "left";
        case right:
            return "right";
        case top:
            return "top";
        case bottom:
            return "bottom";
        default:
            throw new Error("unreachable");
    }
}
function getPaddedExitPoints(exitPoint, exitSide, padding = 5) {
    const paddedExitPoints = [];
    switch(exitSide){
        case "top":
            paddedExitPoints.push({
                x: exitPoint.x - padding,
                y: exitPoint.y + padding
            }, {
                x: exitPoint.x + padding,
                y: exitPoint.y + padding
            });
            break;
        case "bottom":
            paddedExitPoints.push({
                x: exitPoint.x - padding,
                y: exitPoint.y - padding
            }, {
                x: exitPoint.x + padding,
                y: exitPoint.y - padding
            });
            break;
        case "left":
            paddedExitPoints.push({
                x: exitPoint.x + padding,
                y: exitPoint.y - padding
            }, {
                x: exitPoint.x + padding,
                y: exitPoint.y + padding
            });
            break;
        case "right":
            paddedExitPoints.push({
                x: exitPoint.x - padding,
                y: exitPoint.y - padding
            }, {
                x: exitPoint.x - padding,
                y: exitPoint.y + padding
            });
            break;
    }
    return paddedExitPoints;
}
function getPointsFromRect(rect) {
    const { top, right, bottom, left } = rect;
    return [
        {
            x: left,
            y: top
        },
        {
            x: right,
            y: top
        },
        {
            x: right,
            y: bottom
        },
        {
            x: left,
            y: bottom
        }
    ];
}
function isPointInPolygon(point, polygon) {
    const { x, y } = point;
    let inside = false;
    for(let i = 0, j = polygon.length - 1; i < polygon.length; j = i++){
        const ii = polygon[i];
        const jj = polygon[j];
        const xi = ii.x;
        const yi = ii.y;
        const xj = jj.x;
        const yj = jj.y;
        const intersect = yi > y !== yj > y && x < (xj - xi) * (y - yi) / (yj - yi) + xi;
        if (intersect) inside = !inside;
    }
    return inside;
}
function getHull(points) {
    const newPoints = points.slice();
    newPoints.sort((a, b)=>{
        if (a.x < b.x) return -1;
        else if (a.x > b.x) return 1;
        else if (a.y < b.y) return -1;
        else if (a.y > b.y) return 1;
        else return 0;
    });
    return getHullPresorted(newPoints);
}
function getHullPresorted(points) {
    if (points.length <= 1) return points.slice();
    const upperHull = [];
    for(let i = 0; i < points.length; i++){
        const p = points[i];
        while(upperHull.length >= 2){
            const q = upperHull[upperHull.length - 1];
            const r = upperHull[upperHull.length - 2];
            if ((q.x - r.x) * (p.y - r.y) >= (q.y - r.y) * (p.x - r.x)) upperHull.pop();
            else break;
        }
        upperHull.push(p);
    }
    upperHull.pop();
    const lowerHull = [];
    for(let i = points.length - 1; i >= 0; i--){
        const p = points[i];
        while(lowerHull.length >= 2){
            const q = lowerHull[lowerHull.length - 1];
            const r = lowerHull[lowerHull.length - 2];
            if ((q.x - r.x) * (p.y - r.y) >= (q.y - r.y) * (p.x - r.x)) lowerHull.pop();
            else break;
        }
        lowerHull.push(p);
    }
    lowerHull.pop();
    if (upperHull.length === 1 && lowerHull.length === 1 && upperHull[0].x === lowerHull[0].x && upperHull[0].y === lowerHull[0].y) {
        return upperHull;
    } else {
        return upperHull.concat(lowerHull);
    }
}
var Provider = TooltipProvider;
var Root3 = Tooltip;
var Trigger = TooltipTrigger;
var Portal = TooltipPortal;
var Content2 = TooltipContent;
var Arrow2 = TooltipArrow;
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/ellipsis.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>Ellipsis
]);
/**
 * @license lucide-react v0.507.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$createLucideIcon$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/createLucideIcon.js [app-client] (ecmascript)");
;
const __iconNode = [
    [
        "circle",
        {
            cx: "12",
            cy: "12",
            r: "1",
            key: "41hilf"
        }
    ],
    [
        "circle",
        {
            cx: "19",
            cy: "12",
            r: "1",
            key: "1wjl8i"
        }
    ],
    [
        "circle",
        {
            cx: "5",
            cy: "12",
            r: "1",
            key: "1pcz8c"
        }
    ]
];
const Ellipsis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$createLucideIcon$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])("ellipsis", __iconNode);
;
 //# sourceMappingURL=ellipsis.js.map
}),
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/ellipsis.js [app-client] (ecmascript) <export default as MoreHorizontal>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MoreHorizontal",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ellipsis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ellipsis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/ellipsis.js [app-client] (ecmascript)");
}),
"[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-menu/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Root",
    ()=>Slot,
    "Slot",
    ()=>Slot,
    "Slottable",
    ()=>Slottable,
    "createSlot",
    ()=>createSlot,
    "createSlottable",
    ()=>createSlottable
]);
// src/slot.tsx
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-compose-refs/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
;
;
;
// @__NO_SIDE_EFFECTS__
function createSlot(ownerName) {
    const SlotClone = /* @__PURE__ */ createSlotClone(ownerName);
    const Slot2 = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
        const { children, ...slotProps } = props;
        const childrenArray = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].toArray(children);
        const slottable = childrenArray.find(isSlottable);
        if (slottable) {
            const newElement = slottable.props.children;
            const newChildren = childrenArray.map((child)=>{
                if (child === slottable) {
                    if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].count(newElement) > 1) return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].only(null);
                    return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](newElement) ? newElement.props.children : null;
                } else {
                    return child;
                }
            });
            return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(SlotClone, {
                ...slotProps,
                ref: forwardedRef,
                children: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](newElement) ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"](newElement, void 0, newChildren) : null
            });
        }
        return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(SlotClone, {
            ...slotProps,
            ref: forwardedRef,
            children
        });
    });
    Slot2.displayName = `${ownerName}.Slot`;
    return Slot2;
}
var Slot = /* @__PURE__ */ createSlot("Slot");
// @__NO_SIDE_EFFECTS__
function createSlotClone(ownerName) {
    const SlotClone = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
        const { children, ...slotProps } = props;
        if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](children)) {
            const childrenRef = getElementRef(children);
            const props2 = mergeProps(slotProps, children.props);
            if (children.type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"]) {
                props2.ref = forwardedRef ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeRefs"])(forwardedRef, childrenRef) : childrenRef;
            }
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"](children, props2);
        }
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].count(children) > 1 ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].only(null) : null;
    });
    SlotClone.displayName = `${ownerName}.SlotClone`;
    return SlotClone;
}
var SLOTTABLE_IDENTIFIER = Symbol("radix.slottable");
// @__NO_SIDE_EFFECTS__
function createSlottable(ownerName) {
    const Slottable2 = ({ children })=>{
        return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children
        });
    };
    Slottable2.displayName = `${ownerName}.Slottable`;
    Slottable2.__radixId = SLOTTABLE_IDENTIFIER;
    return Slottable2;
}
var Slottable = /* @__PURE__ */ createSlottable("Slottable");
function isSlottable(child) {
    return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"](child) && typeof child.type === "function" && "__radixId" in child.type && child.type.__radixId === SLOTTABLE_IDENTIFIER;
}
function mergeProps(slotProps, childProps) {
    const overrideProps = {
        ...childProps
    };
    for(const propName in childProps){
        const slotPropValue = slotProps[propName];
        const childPropValue = childProps[propName];
        const isHandler = /^on[A-Z]/.test(propName);
        if (isHandler) {
            if (slotPropValue && childPropValue) {
                overrideProps[propName] = (...args)=>{
                    const result = childPropValue(...args);
                    slotPropValue(...args);
                    return result;
                };
            } else if (slotPropValue) {
                overrideProps[propName] = slotPropValue;
            }
        } else if (propName === "style") {
            overrideProps[propName] = {
                ...slotPropValue,
                ...childPropValue
            };
        } else if (propName === "className") {
            overrideProps[propName] = [
                slotPropValue,
                childPropValue
            ].filter(Boolean).join(" ");
        }
    }
    return {
        ...slotProps,
        ...overrideProps
    };
}
function getElementRef(element) {
    let getter = Object.getOwnPropertyDescriptor(element.props, "ref")?.get;
    let mayWarn = getter && "isReactWarning" in getter && getter.isReactWarning;
    if (mayWarn) {
        return element.ref;
    }
    getter = Object.getOwnPropertyDescriptor(element, "ref")?.get;
    mayWarn = getter && "isReactWarning" in getter && getter.isReactWarning;
    if (mayWarn) {
        return element.props.ref;
    }
    return element.props.ref || element.ref;
}
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-menu/dist/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Anchor",
    ()=>Anchor2,
    "Arrow",
    ()=>Arrow2,
    "CheckboxItem",
    ()=>CheckboxItem,
    "Content",
    ()=>Content2,
    "Group",
    ()=>Group,
    "Item",
    ()=>Item2,
    "ItemIndicator",
    ()=>ItemIndicator,
    "Label",
    ()=>Label,
    "Menu",
    ()=>Menu,
    "MenuAnchor",
    ()=>MenuAnchor,
    "MenuArrow",
    ()=>MenuArrow,
    "MenuCheckboxItem",
    ()=>MenuCheckboxItem,
    "MenuContent",
    ()=>MenuContent,
    "MenuGroup",
    ()=>MenuGroup,
    "MenuItem",
    ()=>MenuItem,
    "MenuItemIndicator",
    ()=>MenuItemIndicator,
    "MenuLabel",
    ()=>MenuLabel,
    "MenuPortal",
    ()=>MenuPortal,
    "MenuRadioGroup",
    ()=>MenuRadioGroup,
    "MenuRadioItem",
    ()=>MenuRadioItem,
    "MenuSeparator",
    ()=>MenuSeparator,
    "MenuSub",
    ()=>MenuSub,
    "MenuSubContent",
    ()=>MenuSubContent,
    "MenuSubTrigger",
    ()=>MenuSubTrigger,
    "Portal",
    ()=>Portal,
    "RadioGroup",
    ()=>RadioGroup,
    "RadioItem",
    ()=>RadioItem,
    "Root",
    ()=>Root3,
    "Separator",
    ()=>Separator,
    "Sub",
    ()=>Sub,
    "SubContent",
    ()=>SubContent,
    "SubTrigger",
    ()=>SubTrigger,
    "createMenuScope",
    ()=>createMenuScope
]);
// src/menu.tsx
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$collection$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-collection/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-compose-refs/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-context/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$direction$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-direction/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dismissable$2d$layer$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-dismissable-layer/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$focus$2d$guards$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-focus-guards/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$focus$2d$scope$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-focus-scope/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-id/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-popper/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$portal$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-portal/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-presence/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$roving$2d$focus$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-roving-focus/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-menu/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$callback$2d$ref$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-use-callback-ref/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$aria$2d$hidden$2f$dist$2f$es2015$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/aria-hidden/dist/es2015/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$remove$2d$scroll$2f$dist$2f$es2015$2f$Combination$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__RemoveScroll$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-remove-scroll/dist/es2015/Combination.js [app-client] (ecmascript) <export default as RemoveScroll>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
"use client";
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
;
;
var SELECTION_KEYS = [
    "Enter",
    " "
];
var FIRST_KEYS = [
    "ArrowDown",
    "PageUp",
    "Home"
];
var LAST_KEYS = [
    "ArrowUp",
    "PageDown",
    "End"
];
var FIRST_LAST_KEYS = [
    ...FIRST_KEYS,
    ...LAST_KEYS
];
var SUB_OPEN_KEYS = {
    ltr: [
        ...SELECTION_KEYS,
        "ArrowRight"
    ],
    rtl: [
        ...SELECTION_KEYS,
        "ArrowLeft"
    ]
};
var SUB_CLOSE_KEYS = {
    ltr: [
        "ArrowLeft"
    ],
    rtl: [
        "ArrowRight"
    ]
};
var MENU_NAME = "Menu";
var [Collection, useCollection, createCollectionScope] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$collection$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCollection"])(MENU_NAME);
var [createMenuContext, createMenuScope] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContextScope"])(MENU_NAME, [
    createCollectionScope,
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPopperScope"],
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$roving$2d$focus$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createRovingFocusGroupScope"]
]);
var usePopperScope = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPopperScope"])();
var useRovingFocusGroupScope = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$roving$2d$focus$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createRovingFocusGroupScope"])();
var [MenuProvider, useMenuContext] = createMenuContext(MENU_NAME);
var [MenuRootProvider, useMenuRootContext] = createMenuContext(MENU_NAME);
var Menu = (props)=>{
    const { __scopeMenu, open = false, children, dir, onOpenChange, modal = true } = props;
    const popperScope = usePopperScope(__scopeMenu);
    const [content, setContent] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const isUsingKeyboardRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const handleOpenChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$callback$2d$ref$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallbackRef"])(onOpenChange);
    const direction = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$direction$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDirection"])(dir);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "Menu.useEffect": ()=>{
            const handleKeyDown = {
                "Menu.useEffect.handleKeyDown": ()=>{
                    isUsingKeyboardRef.current = true;
                    document.addEventListener("pointerdown", handlePointer, {
                        capture: true,
                        once: true
                    });
                    document.addEventListener("pointermove", handlePointer, {
                        capture: true,
                        once: true
                    });
                }
            }["Menu.useEffect.handleKeyDown"];
            const handlePointer = {
                "Menu.useEffect.handlePointer": ()=>isUsingKeyboardRef.current = false
            }["Menu.useEffect.handlePointer"];
            document.addEventListener("keydown", handleKeyDown, {
                capture: true
            });
            return ({
                "Menu.useEffect": ()=>{
                    document.removeEventListener("keydown", handleKeyDown, {
                        capture: true
                    });
                    document.removeEventListener("pointerdown", handlePointer, {
                        capture: true
                    });
                    document.removeEventListener("pointermove", handlePointer, {
                        capture: true
                    });
                }
            })["Menu.useEffect"];
        }
    }["Menu.useEffect"], []);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
        ...popperScope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuProvider, {
            scope: __scopeMenu,
            open,
            onOpenChange: handleOpenChange,
            content,
            onContentChange: setContent,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuRootProvider, {
                scope: __scopeMenu,
                onClose: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
                    "Menu.useCallback": ()=>handleOpenChange(false)
                }["Menu.useCallback"], [
                    handleOpenChange
                ]),
                isUsingKeyboardRef,
                dir: direction,
                modal,
                children
            })
        })
    });
};
Menu.displayName = MENU_NAME;
var ANCHOR_NAME = "MenuAnchor";
var MenuAnchor = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, ...anchorProps } = props;
    const popperScope = usePopperScope(__scopeMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Anchor"], {
        ...popperScope,
        ...anchorProps,
        ref: forwardedRef
    });
});
MenuAnchor.displayName = ANCHOR_NAME;
var PORTAL_NAME = "MenuPortal";
var [PortalProvider, usePortalContext] = createMenuContext(PORTAL_NAME, {
    forceMount: void 0
});
var MenuPortal = (props)=>{
    const { __scopeMenu, forceMount, children, container } = props;
    const context = useMenuContext(PORTAL_NAME, __scopeMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(PortalProvider, {
        scope: __scopeMenu,
        forceMount,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
            present: forceMount || context.open,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$portal$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Portal"], {
                asChild: true,
                container,
                children
            })
        })
    });
};
MenuPortal.displayName = PORTAL_NAME;
var CONTENT_NAME = "MenuContent";
var [MenuContentProvider, useMenuContentContext] = createMenuContext(CONTENT_NAME);
var MenuContent = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const portalContext = usePortalContext(CONTENT_NAME, props.__scopeMenu);
    const { forceMount = portalContext.forceMount, ...contentProps } = props;
    const context = useMenuContext(CONTENT_NAME, props.__scopeMenu);
    const rootContext = useMenuRootContext(CONTENT_NAME, props.__scopeMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Collection.Provider, {
        scope: props.__scopeMenu,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
            present: forceMount || context.open,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Collection.Slot, {
                scope: props.__scopeMenu,
                children: rootContext.modal ? /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuRootContentModal, {
                    ...contentProps,
                    ref: forwardedRef
                }) : /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuRootContentNonModal, {
                    ...contentProps,
                    ref: forwardedRef
                })
            })
        })
    });
});
var MenuRootContentModal = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const context = useMenuContext(CONTENT_NAME, props.__scopeMenu);
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "MenuRootContentModal.useEffect": ()=>{
            const content = ref.current;
            if (content) return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$aria$2d$hidden$2f$dist$2f$es2015$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["hideOthers"])(content);
        }
    }["MenuRootContentModal.useEffect"], []);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuContentImpl, {
        ...props,
        ref: composedRefs,
        trapFocus: context.open,
        disableOutsidePointerEvents: context.open,
        disableOutsideScroll: true,
        onFocusOutside: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onFocusOutside, (event)=>event.preventDefault(), {
            checkForDefaultPrevented: false
        }),
        onDismiss: ()=>context.onOpenChange(false)
    });
});
var MenuRootContentNonModal = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const context = useMenuContext(CONTENT_NAME, props.__scopeMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuContentImpl, {
        ...props,
        ref: forwardedRef,
        trapFocus: false,
        disableOutsidePointerEvents: false,
        disableOutsideScroll: false,
        onDismiss: ()=>context.onOpenChange(false)
    });
});
var Slot = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createSlot"])("MenuContent.ScrollLock");
var MenuContentImpl = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, loop = false, trapFocus, onOpenAutoFocus, onCloseAutoFocus, disableOutsidePointerEvents, onEntryFocus, onEscapeKeyDown, onPointerDownOutside, onFocusOutside, onInteractOutside, onDismiss, disableOutsideScroll, ...contentProps } = props;
    const context = useMenuContext(CONTENT_NAME, __scopeMenu);
    const rootContext = useMenuRootContext(CONTENT_NAME, __scopeMenu);
    const popperScope = usePopperScope(__scopeMenu);
    const rovingFocusGroupScope = useRovingFocusGroupScope(__scopeMenu);
    const getItems = useCollection(__scopeMenu);
    const [currentItemId, setCurrentItemId] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const contentRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, contentRef, context.onContentChange);
    const timerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    const searchRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"]("");
    const pointerGraceTimerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    const pointerGraceIntentRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const pointerDirRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"]("right");
    const lastPointerXRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    const ScrollLockWrapper = disableOutsideScroll ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$remove$2d$scroll$2f$dist$2f$es2015$2f$Combination$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__RemoveScroll$3e$__["RemoveScroll"] : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"];
    const scrollLockWrapperProps = disableOutsideScroll ? {
        as: Slot,
        allowPinchZoom: true
    } : void 0;
    const handleTypeaheadSearch = (key)=>{
        const search = searchRef.current + key;
        const items = getItems().filter((item)=>!item.disabled);
        const currentItem = document.activeElement;
        const currentMatch = items.find((item)=>item.ref.current === currentItem)?.textValue;
        const values = items.map((item)=>item.textValue);
        const nextMatch = getNextMatch(values, search, currentMatch);
        const newItem = items.find((item)=>item.textValue === nextMatch)?.ref.current;
        (function updateSearch(value) {
            searchRef.current = value;
            window.clearTimeout(timerRef.current);
            if (value !== "") timerRef.current = window.setTimeout(()=>updateSearch(""), 1e3);
        })(search);
        if (newItem) {
            setTimeout(()=>newItem.focus());
        }
    };
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "MenuContentImpl.useEffect": ()=>{
            return ({
                "MenuContentImpl.useEffect": ()=>window.clearTimeout(timerRef.current)
            })["MenuContentImpl.useEffect"];
        }
    }["MenuContentImpl.useEffect"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$focus$2d$guards$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useFocusGuards"])();
    const isPointerMovingToSubmenu = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "MenuContentImpl.useCallback[isPointerMovingToSubmenu]": (event)=>{
            const isMovingTowards = pointerDirRef.current === pointerGraceIntentRef.current?.side;
            return isMovingTowards && isPointerInGraceArea(event, pointerGraceIntentRef.current?.area);
        }
    }["MenuContentImpl.useCallback[isPointerMovingToSubmenu]"], []);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuContentProvider, {
        scope: __scopeMenu,
        searchRef,
        onItemEnter: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "MenuContentImpl.useCallback": (event)=>{
                if (isPointerMovingToSubmenu(event)) event.preventDefault();
            }
        }["MenuContentImpl.useCallback"], [
            isPointerMovingToSubmenu
        ]),
        onItemLeave: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "MenuContentImpl.useCallback": (event)=>{
                if (isPointerMovingToSubmenu(event)) return;
                contentRef.current?.focus();
                setCurrentItemId(null);
            }
        }["MenuContentImpl.useCallback"], [
            isPointerMovingToSubmenu
        ]),
        onTriggerLeave: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "MenuContentImpl.useCallback": (event)=>{
                if (isPointerMovingToSubmenu(event)) event.preventDefault();
            }
        }["MenuContentImpl.useCallback"], [
            isPointerMovingToSubmenu
        ]),
        pointerGraceTimerRef,
        onPointerGraceIntentChange: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "MenuContentImpl.useCallback": (intent)=>{
                pointerGraceIntentRef.current = intent;
            }
        }["MenuContentImpl.useCallback"], []),
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ScrollLockWrapper, {
            ...scrollLockWrapperProps,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$focus$2d$scope$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FocusScope"], {
                asChild: true,
                trapped: trapFocus,
                onMountAutoFocus: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(onOpenAutoFocus, (event)=>{
                    event.preventDefault();
                    contentRef.current?.focus({
                        preventScroll: true
                    });
                }),
                onUnmountAutoFocus: onCloseAutoFocus,
                children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dismissable$2d$layer$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DismissableLayer"], {
                    asChild: true,
                    disableOutsidePointerEvents,
                    onEscapeKeyDown,
                    onPointerDownOutside,
                    onFocusOutside,
                    onInteractOutside,
                    onDismiss,
                    children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$roving$2d$focus$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
                        asChild: true,
                        ...rovingFocusGroupScope,
                        dir: rootContext.dir,
                        orientation: "vertical",
                        loop,
                        currentTabStopId: currentItemId,
                        onCurrentTabStopIdChange: setCurrentItemId,
                        onEntryFocus: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(onEntryFocus, (event)=>{
                            if (!rootContext.isUsingKeyboardRef.current) event.preventDefault();
                        }),
                        preventScrollOnEntryFocus: true,
                        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Content"], {
                            role: "menu",
                            "aria-orientation": "vertical",
                            "data-state": getOpenState(context.open),
                            "data-radix-menu-content": "",
                            dir: rootContext.dir,
                            ...popperScope,
                            ...contentProps,
                            ref: composedRefs,
                            style: {
                                outline: "none",
                                ...contentProps.style
                            },
                            onKeyDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(contentProps.onKeyDown, (event)=>{
                                const target = event.target;
                                const isKeyDownInside = target.closest("[data-radix-menu-content]") === event.currentTarget;
                                const isModifierKey = event.ctrlKey || event.altKey || event.metaKey;
                                const isCharacterKey = event.key.length === 1;
                                if (isKeyDownInside) {
                                    if (event.key === "Tab") event.preventDefault();
                                    if (!isModifierKey && isCharacterKey) handleTypeaheadSearch(event.key);
                                }
                                const content = contentRef.current;
                                if (event.target !== content) return;
                                if (!FIRST_LAST_KEYS.includes(event.key)) return;
                                event.preventDefault();
                                const items = getItems().filter((item)=>!item.disabled);
                                const candidateNodes = items.map((item)=>item.ref.current);
                                if (LAST_KEYS.includes(event.key)) candidateNodes.reverse();
                                focusFirst(candidateNodes);
                            }),
                            onBlur: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onBlur, (event)=>{
                                if (!event.currentTarget.contains(event.target)) {
                                    window.clearTimeout(timerRef.current);
                                    searchRef.current = "";
                                }
                            }),
                            onPointerMove: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerMove, whenMouse((event)=>{
                                const target = event.target;
                                const pointerXHasChanged = lastPointerXRef.current !== event.clientX;
                                if (event.currentTarget.contains(target) && pointerXHasChanged) {
                                    const newDir = event.clientX > lastPointerXRef.current ? "right" : "left";
                                    pointerDirRef.current = newDir;
                                    lastPointerXRef.current = event.clientX;
                                }
                            }))
                        })
                    })
                })
            })
        })
    });
});
MenuContent.displayName = CONTENT_NAME;
var GROUP_NAME = "MenuGroup";
var MenuGroup = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, ...groupProps } = props;
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].div, {
        role: "group",
        ...groupProps,
        ref: forwardedRef
    });
});
MenuGroup.displayName = GROUP_NAME;
var LABEL_NAME = "MenuLabel";
var MenuLabel = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, ...labelProps } = props;
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].div, {
        ...labelProps,
        ref: forwardedRef
    });
});
MenuLabel.displayName = LABEL_NAME;
var ITEM_NAME = "MenuItem";
var ITEM_SELECT = "menu.itemSelect";
var MenuItem = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { disabled = false, onSelect, ...itemProps } = props;
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const rootContext = useMenuRootContext(ITEM_NAME, props.__scopeMenu);
    const contentContext = useMenuContentContext(ITEM_NAME, props.__scopeMenu);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref);
    const isPointerDownRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const handleSelect = ()=>{
        const menuItem = ref.current;
        if (!disabled && menuItem) {
            const itemSelectEvent = new CustomEvent(ITEM_SELECT, {
                bubbles: true,
                cancelable: true
            });
            menuItem.addEventListener(ITEM_SELECT, (event)=>onSelect?.(event), {
                once: true
            });
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["dispatchDiscreteCustomEvent"])(menuItem, itemSelectEvent);
            if (itemSelectEvent.defaultPrevented) {
                isPointerDownRef.current = false;
            } else {
                rootContext.onClose();
            }
        }
    };
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuItemImpl, {
        ...itemProps,
        ref: composedRefs,
        disabled,
        onClick: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onClick, handleSelect),
        onPointerDown: (event)=>{
            props.onPointerDown?.(event);
            isPointerDownRef.current = true;
        },
        onPointerUp: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerUp, (event)=>{
            if (!isPointerDownRef.current) event.currentTarget?.click();
        }),
        onKeyDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onKeyDown, (event)=>{
            const isTypingAhead = contentContext.searchRef.current !== "";
            if (disabled || isTypingAhead && event.key === " ") return;
            if (SELECTION_KEYS.includes(event.key)) {
                event.currentTarget.click();
                event.preventDefault();
            }
        })
    });
});
MenuItem.displayName = ITEM_NAME;
var MenuItemImpl = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, disabled = false, textValue, ...itemProps } = props;
    const contentContext = useMenuContentContext(ITEM_NAME, __scopeMenu);
    const rovingFocusGroupScope = useRovingFocusGroupScope(__scopeMenu);
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref);
    const [isFocused, setIsFocused] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](false);
    const [textContent, setTextContent] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"]("");
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "MenuItemImpl.useEffect": ()=>{
            const menuItem = ref.current;
            if (menuItem) {
                setTextContent((menuItem.textContent ?? "").trim());
            }
        }
    }["MenuItemImpl.useEffect"], [
        itemProps.children
    ]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Collection.ItemSlot, {
        scope: __scopeMenu,
        disabled,
        textValue: textValue ?? textContent,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$roving$2d$focus$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Item"], {
            asChild: true,
            ...rovingFocusGroupScope,
            focusable: !disabled,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].div, {
                role: "menuitem",
                "data-highlighted": isFocused ? "" : void 0,
                "aria-disabled": disabled || void 0,
                "data-disabled": disabled ? "" : void 0,
                ...itemProps,
                ref: composedRefs,
                onPointerMove: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerMove, whenMouse((event)=>{
                    if (disabled) {
                        contentContext.onItemLeave(event);
                    } else {
                        contentContext.onItemEnter(event);
                        if (!event.defaultPrevented) {
                            const item = event.currentTarget;
                            item.focus({
                                preventScroll: true
                            });
                        }
                    }
                })),
                onPointerLeave: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerLeave, whenMouse((event)=>contentContext.onItemLeave(event))),
                onFocus: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onFocus, ()=>setIsFocused(true)),
                onBlur: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onBlur, ()=>setIsFocused(false))
            })
        })
    });
});
var CHECKBOX_ITEM_NAME = "MenuCheckboxItem";
var MenuCheckboxItem = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { checked = false, onCheckedChange, ...checkboxItemProps } = props;
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ItemIndicatorProvider, {
        scope: props.__scopeMenu,
        checked,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuItem, {
            role: "menuitemcheckbox",
            "aria-checked": isIndeterminate(checked) ? "mixed" : checked,
            ...checkboxItemProps,
            ref: forwardedRef,
            "data-state": getCheckedState(checked),
            onSelect: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(checkboxItemProps.onSelect, ()=>onCheckedChange?.(isIndeterminate(checked) ? true : !checked), {
                checkForDefaultPrevented: false
            })
        })
    });
});
MenuCheckboxItem.displayName = CHECKBOX_ITEM_NAME;
var RADIO_GROUP_NAME = "MenuRadioGroup";
var [RadioGroupProvider, useRadioGroupContext] = createMenuContext(RADIO_GROUP_NAME, {
    value: void 0,
    onValueChange: ()=>{}
});
var MenuRadioGroup = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { value, onValueChange, ...groupProps } = props;
    const handleValueChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$callback$2d$ref$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallbackRef"])(onValueChange);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(RadioGroupProvider, {
        scope: props.__scopeMenu,
        value,
        onValueChange: handleValueChange,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuGroup, {
            ...groupProps,
            ref: forwardedRef
        })
    });
});
MenuRadioGroup.displayName = RADIO_GROUP_NAME;
var RADIO_ITEM_NAME = "MenuRadioItem";
var MenuRadioItem = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { value, ...radioItemProps } = props;
    const context = useRadioGroupContext(RADIO_ITEM_NAME, props.__scopeMenu);
    const checked = value === context.value;
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ItemIndicatorProvider, {
        scope: props.__scopeMenu,
        checked,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuItem, {
            role: "menuitemradio",
            "aria-checked": checked,
            ...radioItemProps,
            ref: forwardedRef,
            "data-state": getCheckedState(checked),
            onSelect: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(radioItemProps.onSelect, ()=>context.onValueChange?.(value), {
                checkForDefaultPrevented: false
            })
        })
    });
});
MenuRadioItem.displayName = RADIO_ITEM_NAME;
var ITEM_INDICATOR_NAME = "MenuItemIndicator";
var [ItemIndicatorProvider, useItemIndicatorContext] = createMenuContext(ITEM_INDICATOR_NAME, {
    checked: false
});
var MenuItemIndicator = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, forceMount, ...itemIndicatorProps } = props;
    const indicatorContext = useItemIndicatorContext(ITEM_INDICATOR_NAME, __scopeMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
        present: forceMount || isIndeterminate(indicatorContext.checked) || indicatorContext.checked === true,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].span, {
            ...itemIndicatorProps,
            ref: forwardedRef,
            "data-state": getCheckedState(indicatorContext.checked)
        })
    });
});
MenuItemIndicator.displayName = ITEM_INDICATOR_NAME;
var SEPARATOR_NAME = "MenuSeparator";
var MenuSeparator = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, ...separatorProps } = props;
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].div, {
        role: "separator",
        "aria-orientation": "horizontal",
        ...separatorProps,
        ref: forwardedRef
    });
});
MenuSeparator.displayName = SEPARATOR_NAME;
var ARROW_NAME = "MenuArrow";
var MenuArrow = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeMenu, ...arrowProps } = props;
    const popperScope = usePopperScope(__scopeMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Arrow"], {
        ...popperScope,
        ...arrowProps,
        ref: forwardedRef
    });
});
MenuArrow.displayName = ARROW_NAME;
var SUB_NAME = "MenuSub";
var [MenuSubProvider, useMenuSubContext] = createMenuContext(SUB_NAME);
var MenuSub = (props)=>{
    const { __scopeMenu, children, open = false, onOpenChange } = props;
    const parentMenuContext = useMenuContext(SUB_NAME, __scopeMenu);
    const popperScope = usePopperScope(__scopeMenu);
    const [trigger, setTrigger] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const [content, setContent] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const handleOpenChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$callback$2d$ref$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallbackRef"])(onOpenChange);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "MenuSub.useEffect": ()=>{
            if (parentMenuContext.open === false) handleOpenChange(false);
            return ({
                "MenuSub.useEffect": ()=>handleOpenChange(false)
            })["MenuSub.useEffect"];
        }
    }["MenuSub.useEffect"], [
        parentMenuContext.open,
        handleOpenChange
    ]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
        ...popperScope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuProvider, {
            scope: __scopeMenu,
            open,
            onOpenChange: handleOpenChange,
            content,
            onContentChange: setContent,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuSubProvider, {
                scope: __scopeMenu,
                contentId: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])(),
                triggerId: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])(),
                trigger,
                onTriggerChange: setTrigger,
                children
            })
        })
    });
};
MenuSub.displayName = SUB_NAME;
var SUB_TRIGGER_NAME = "MenuSubTrigger";
var MenuSubTrigger = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const context = useMenuContext(SUB_TRIGGER_NAME, props.__scopeMenu);
    const rootContext = useMenuRootContext(SUB_TRIGGER_NAME, props.__scopeMenu);
    const subContext = useMenuSubContext(SUB_TRIGGER_NAME, props.__scopeMenu);
    const contentContext = useMenuContentContext(SUB_TRIGGER_NAME, props.__scopeMenu);
    const openTimerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const { pointerGraceTimerRef, onPointerGraceIntentChange } = contentContext;
    const scope = {
        __scopeMenu: props.__scopeMenu
    };
    const clearOpenTimer = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "MenuSubTrigger.useCallback[clearOpenTimer]": ()=>{
            if (openTimerRef.current) window.clearTimeout(openTimerRef.current);
            openTimerRef.current = null;
        }
    }["MenuSubTrigger.useCallback[clearOpenTimer]"], []);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "MenuSubTrigger.useEffect": ()=>clearOpenTimer
    }["MenuSubTrigger.useEffect"], [
        clearOpenTimer
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "MenuSubTrigger.useEffect": ()=>{
            const pointerGraceTimer = pointerGraceTimerRef.current;
            return ({
                "MenuSubTrigger.useEffect": ()=>{
                    window.clearTimeout(pointerGraceTimer);
                    onPointerGraceIntentChange(null);
                }
            })["MenuSubTrigger.useEffect"];
        }
    }["MenuSubTrigger.useEffect"], [
        pointerGraceTimerRef,
        onPointerGraceIntentChange
    ]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuAnchor, {
        asChild: true,
        ...scope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuItemImpl, {
            id: subContext.triggerId,
            "aria-haspopup": "menu",
            "aria-expanded": context.open,
            "aria-controls": subContext.contentId,
            "data-state": getOpenState(context.open),
            ...props,
            ref: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeRefs"])(forwardedRef, subContext.onTriggerChange),
            onClick: (event)=>{
                props.onClick?.(event);
                if (props.disabled || event.defaultPrevented) return;
                event.currentTarget.focus();
                if (!context.open) context.onOpenChange(true);
            },
            onPointerMove: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerMove, whenMouse((event)=>{
                contentContext.onItemEnter(event);
                if (event.defaultPrevented) return;
                if (!props.disabled && !context.open && !openTimerRef.current) {
                    contentContext.onPointerGraceIntentChange(null);
                    openTimerRef.current = window.setTimeout(()=>{
                        context.onOpenChange(true);
                        clearOpenTimer();
                    }, 100);
                }
            })),
            onPointerLeave: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerLeave, whenMouse((event)=>{
                clearOpenTimer();
                const contentRect = context.content?.getBoundingClientRect();
                if (contentRect) {
                    const side = context.content?.dataset.side;
                    const rightSide = side === "right";
                    const bleed = rightSide ? -5 : 5;
                    const contentNearEdge = contentRect[rightSide ? "left" : "right"];
                    const contentFarEdge = contentRect[rightSide ? "right" : "left"];
                    contentContext.onPointerGraceIntentChange({
                        area: [
                            // Apply a bleed on clientX to ensure that our exit point is
                            // consistently within polygon bounds
                            {
                                x: event.clientX + bleed,
                                y: event.clientY
                            },
                            {
                                x: contentNearEdge,
                                y: contentRect.top
                            },
                            {
                                x: contentFarEdge,
                                y: contentRect.top
                            },
                            {
                                x: contentFarEdge,
                                y: contentRect.bottom
                            },
                            {
                                x: contentNearEdge,
                                y: contentRect.bottom
                            }
                        ],
                        side
                    });
                    window.clearTimeout(pointerGraceTimerRef.current);
                    pointerGraceTimerRef.current = window.setTimeout(()=>contentContext.onPointerGraceIntentChange(null), 300);
                } else {
                    contentContext.onTriggerLeave(event);
                    if (event.defaultPrevented) return;
                    contentContext.onPointerGraceIntentChange(null);
                }
            })),
            onKeyDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onKeyDown, (event)=>{
                const isTypingAhead = contentContext.searchRef.current !== "";
                if (props.disabled || isTypingAhead && event.key === " ") return;
                if (SUB_OPEN_KEYS[rootContext.dir].includes(event.key)) {
                    context.onOpenChange(true);
                    context.content?.focus();
                    event.preventDefault();
                }
            })
        })
    });
});
MenuSubTrigger.displayName = SUB_TRIGGER_NAME;
var SUB_CONTENT_NAME = "MenuSubContent";
var MenuSubContent = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const portalContext = usePortalContext(CONTENT_NAME, props.__scopeMenu);
    const { forceMount = portalContext.forceMount, ...subContentProps } = props;
    const context = useMenuContext(CONTENT_NAME, props.__scopeMenu);
    const rootContext = useMenuRootContext(CONTENT_NAME, props.__scopeMenu);
    const subContext = useMenuSubContext(SUB_CONTENT_NAME, props.__scopeMenu);
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Collection.Provider, {
        scope: props.__scopeMenu,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
            present: forceMount || context.open,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Collection.Slot, {
                scope: props.__scopeMenu,
                children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(MenuContentImpl, {
                    id: subContext.contentId,
                    "aria-labelledby": subContext.triggerId,
                    ...subContentProps,
                    ref: composedRefs,
                    align: "start",
                    side: rootContext.dir === "rtl" ? "left" : "right",
                    disableOutsidePointerEvents: false,
                    disableOutsideScroll: false,
                    trapFocus: false,
                    onOpenAutoFocus: (event)=>{
                        if (rootContext.isUsingKeyboardRef.current) ref.current?.focus();
                        event.preventDefault();
                    },
                    onCloseAutoFocus: (event)=>event.preventDefault(),
                    onFocusOutside: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onFocusOutside, (event)=>{
                        if (event.target !== subContext.trigger) context.onOpenChange(false);
                    }),
                    onEscapeKeyDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onEscapeKeyDown, (event)=>{
                        rootContext.onClose();
                        event.preventDefault();
                    }),
                    onKeyDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onKeyDown, (event)=>{
                        const isKeyDownInside = event.currentTarget.contains(event.target);
                        const isCloseKey = SUB_CLOSE_KEYS[rootContext.dir].includes(event.key);
                        if (isKeyDownInside && isCloseKey) {
                            context.onOpenChange(false);
                            subContext.trigger?.focus();
                            event.preventDefault();
                        }
                    })
                })
            })
        })
    });
});
MenuSubContent.displayName = SUB_CONTENT_NAME;
function getOpenState(open) {
    return open ? "open" : "closed";
}
function isIndeterminate(checked) {
    return checked === "indeterminate";
}
function getCheckedState(checked) {
    return isIndeterminate(checked) ? "indeterminate" : checked ? "checked" : "unchecked";
}
function focusFirst(candidates) {
    const PREVIOUSLY_FOCUSED_ELEMENT = document.activeElement;
    for (const candidate of candidates){
        if (candidate === PREVIOUSLY_FOCUSED_ELEMENT) return;
        candidate.focus();
        if (document.activeElement !== PREVIOUSLY_FOCUSED_ELEMENT) return;
    }
}
function wrapArray(array, startIndex) {
    return array.map((_, index)=>array[(startIndex + index) % array.length]);
}
function getNextMatch(values, search, currentMatch) {
    const isRepeated = search.length > 1 && Array.from(search).every((char)=>char === search[0]);
    const normalizedSearch = isRepeated ? search[0] : search;
    const currentMatchIndex = currentMatch ? values.indexOf(currentMatch) : -1;
    let wrappedValues = wrapArray(values, Math.max(currentMatchIndex, 0));
    const excludeCurrentMatch = normalizedSearch.length === 1;
    if (excludeCurrentMatch) wrappedValues = wrappedValues.filter((v)=>v !== currentMatch);
    const nextMatch = wrappedValues.find((value)=>value.toLowerCase().startsWith(normalizedSearch.toLowerCase()));
    return nextMatch !== currentMatch ? nextMatch : void 0;
}
function isPointInPolygon(point, polygon) {
    const { x, y } = point;
    let inside = false;
    for(let i = 0, j = polygon.length - 1; i < polygon.length; j = i++){
        const ii = polygon[i];
        const jj = polygon[j];
        const xi = ii.x;
        const yi = ii.y;
        const xj = jj.x;
        const yj = jj.y;
        const intersect = yi > y !== yj > y && x < (xj - xi) * (y - yi) / (yj - yi) + xi;
        if (intersect) inside = !inside;
    }
    return inside;
}
function isPointerInGraceArea(event, area) {
    if (!area) return false;
    const cursorPos = {
        x: event.clientX,
        y: event.clientY
    };
    return isPointInPolygon(cursorPos, area);
}
function whenMouse(handler) {
    return (event)=>event.pointerType === "mouse" ? handler(event) : void 0;
}
var Root3 = Menu;
var Anchor2 = MenuAnchor;
var Portal = MenuPortal;
var Content2 = MenuContent;
var Group = MenuGroup;
var Label = MenuLabel;
var Item2 = MenuItem;
var CheckboxItem = MenuCheckboxItem;
var RadioGroup = MenuRadioGroup;
var RadioItem = MenuRadioItem;
var ItemIndicator = MenuItemIndicator;
var Separator = MenuSeparator;
var Arrow2 = MenuArrow;
var Sub = MenuSub;
var SubTrigger = MenuSubTrigger;
var SubContent = MenuSubContent;
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-dropdown-menu/dist/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Arrow",
    ()=>Arrow2,
    "CheckboxItem",
    ()=>CheckboxItem2,
    "Content",
    ()=>Content2,
    "DropdownMenu",
    ()=>DropdownMenu,
    "DropdownMenuArrow",
    ()=>DropdownMenuArrow,
    "DropdownMenuCheckboxItem",
    ()=>DropdownMenuCheckboxItem,
    "DropdownMenuContent",
    ()=>DropdownMenuContent,
    "DropdownMenuGroup",
    ()=>DropdownMenuGroup,
    "DropdownMenuItem",
    ()=>DropdownMenuItem,
    "DropdownMenuItemIndicator",
    ()=>DropdownMenuItemIndicator,
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
    "DropdownMenuSub",
    ()=>DropdownMenuSub,
    "DropdownMenuSubContent",
    ()=>DropdownMenuSubContent,
    "DropdownMenuSubTrigger",
    ()=>DropdownMenuSubTrigger,
    "DropdownMenuTrigger",
    ()=>DropdownMenuTrigger,
    "Group",
    ()=>Group2,
    "Item",
    ()=>Item2,
    "ItemIndicator",
    ()=>ItemIndicator2,
    "Label",
    ()=>Label2,
    "Portal",
    ()=>Portal2,
    "RadioGroup",
    ()=>RadioGroup2,
    "RadioItem",
    ()=>RadioItem2,
    "Root",
    ()=>Root2,
    "Separator",
    ()=>Separator2,
    "Sub",
    ()=>Sub2,
    "SubContent",
    ()=>SubContent2,
    "SubTrigger",
    ()=>SubTrigger2,
    "Trigger",
    ()=>Trigger,
    "createDropdownMenuScope",
    ()=>createDropdownMenuScope
]);
// src/dropdown-menu.tsx
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-compose-refs/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-context/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-use-controllable-state/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-menu/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-id/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
"use client";
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
var DROPDOWN_MENU_NAME = "DropdownMenu";
var [createDropdownMenuContext, createDropdownMenuScope] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContextScope"])(DROPDOWN_MENU_NAME, [
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createMenuScope"]
]);
var useMenuScope = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createMenuScope"])();
var [DropdownMenuProvider, useDropdownMenuContext] = createDropdownMenuContext(DROPDOWN_MENU_NAME);
var DropdownMenu = (props)=>{
    const { __scopeDropdownMenu, children, dir, open: openProp, defaultOpen, onOpenChange, modal = true } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    const triggerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const [open, setOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useControllableState"])({
        prop: openProp,
        defaultProp: defaultOpen ?? false,
        onChange: onOpenChange,
        caller: DROPDOWN_MENU_NAME
    });
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DropdownMenuProvider, {
        scope: __scopeDropdownMenu,
        triggerId: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])(),
        triggerRef,
        contentId: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$id$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])(),
        open,
        onOpenChange: setOpen,
        onOpenToggle: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
            "DropdownMenu.useCallback": ()=>setOpen({
                    "DropdownMenu.useCallback": (prevOpen)=>!prevOpen
                }["DropdownMenu.useCallback"])
        }["DropdownMenu.useCallback"], [
            setOpen
        ]),
        modal,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
            ...menuScope,
            open,
            onOpenChange: setOpen,
            dir,
            modal,
            children
        })
    });
};
DropdownMenu.displayName = DROPDOWN_MENU_NAME;
var TRIGGER_NAME = "DropdownMenuTrigger";
var DropdownMenuTrigger = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, disabled = false, ...triggerProps } = props;
    const context = useDropdownMenuContext(TRIGGER_NAME, __scopeDropdownMenu);
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Anchor"], {
        asChild: true,
        ...menuScope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].button, {
            type: "button",
            id: context.triggerId,
            "aria-haspopup": "menu",
            "aria-expanded": context.open,
            "aria-controls": context.open ? context.contentId : void 0,
            "data-state": context.open ? "open" : "closed",
            "data-disabled": disabled ? "" : void 0,
            disabled,
            ...triggerProps,
            ref: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeRefs"])(forwardedRef, context.triggerRef),
            onPointerDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerDown, (event)=>{
                if (!disabled && event.button === 0 && event.ctrlKey === false) {
                    context.onOpenToggle();
                    if (!context.open) event.preventDefault();
                }
            }),
            onKeyDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onKeyDown, (event)=>{
                if (disabled) return;
                if ([
                    "Enter",
                    " "
                ].includes(event.key)) context.onOpenToggle();
                if (event.key === "ArrowDown") context.onOpenChange(true);
                if ([
                    "Enter",
                    " ",
                    "ArrowDown"
                ].includes(event.key)) event.preventDefault();
            })
        })
    });
});
DropdownMenuTrigger.displayName = TRIGGER_NAME;
var PORTAL_NAME = "DropdownMenuPortal";
var DropdownMenuPortal = (props)=>{
    const { __scopeDropdownMenu, ...portalProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Portal"], {
        ...menuScope,
        ...portalProps
    });
};
DropdownMenuPortal.displayName = PORTAL_NAME;
var CONTENT_NAME = "DropdownMenuContent";
var DropdownMenuContent = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...contentProps } = props;
    const context = useDropdownMenuContext(CONTENT_NAME, __scopeDropdownMenu);
    const menuScope = useMenuScope(__scopeDropdownMenu);
    const hasInteractedOutsideRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Content"], {
        id: context.contentId,
        "aria-labelledby": context.triggerId,
        ...menuScope,
        ...contentProps,
        ref: forwardedRef,
        onCloseAutoFocus: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onCloseAutoFocus, (event)=>{
            if (!hasInteractedOutsideRef.current) context.triggerRef.current?.focus();
            hasInteractedOutsideRef.current = false;
            event.preventDefault();
        }),
        onInteractOutside: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onInteractOutside, (event)=>{
            const originalEvent = event.detail.originalEvent;
            const ctrlLeftClick = originalEvent.button === 0 && originalEvent.ctrlKey === true;
            const isRightClick = originalEvent.button === 2 || ctrlLeftClick;
            if (!context.modal || isRightClick) hasInteractedOutsideRef.current = true;
        }),
        style: {
            ...props.style,
            // re-namespace exposed content custom properties
            ...{
                "--radix-dropdown-menu-content-transform-origin": "var(--radix-popper-transform-origin)",
                "--radix-dropdown-menu-content-available-width": "var(--radix-popper-available-width)",
                "--radix-dropdown-menu-content-available-height": "var(--radix-popper-available-height)",
                "--radix-dropdown-menu-trigger-width": "var(--radix-popper-anchor-width)",
                "--radix-dropdown-menu-trigger-height": "var(--radix-popper-anchor-height)"
            }
        }
    });
});
DropdownMenuContent.displayName = CONTENT_NAME;
var GROUP_NAME = "DropdownMenuGroup";
var DropdownMenuGroup = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...groupProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Group"], {
        ...menuScope,
        ...groupProps,
        ref: forwardedRef
    });
});
DropdownMenuGroup.displayName = GROUP_NAME;
var LABEL_NAME = "DropdownMenuLabel";
var DropdownMenuLabel = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...labelProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"], {
        ...menuScope,
        ...labelProps,
        ref: forwardedRef
    });
});
DropdownMenuLabel.displayName = LABEL_NAME;
var ITEM_NAME = "DropdownMenuItem";
var DropdownMenuItem = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...itemProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Item"], {
        ...menuScope,
        ...itemProps,
        ref: forwardedRef
    });
});
DropdownMenuItem.displayName = ITEM_NAME;
var CHECKBOX_ITEM_NAME = "DropdownMenuCheckboxItem";
var DropdownMenuCheckboxItem = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...checkboxItemProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CheckboxItem"], {
        ...menuScope,
        ...checkboxItemProps,
        ref: forwardedRef
    });
});
DropdownMenuCheckboxItem.displayName = CHECKBOX_ITEM_NAME;
var RADIO_GROUP_NAME = "DropdownMenuRadioGroup";
var DropdownMenuRadioGroup = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...radioGroupProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RadioGroup"], {
        ...menuScope,
        ...radioGroupProps,
        ref: forwardedRef
    });
});
DropdownMenuRadioGroup.displayName = RADIO_GROUP_NAME;
var RADIO_ITEM_NAME = "DropdownMenuRadioItem";
var DropdownMenuRadioItem = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...radioItemProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RadioItem"], {
        ...menuScope,
        ...radioItemProps,
        ref: forwardedRef
    });
});
DropdownMenuRadioItem.displayName = RADIO_ITEM_NAME;
var INDICATOR_NAME = "DropdownMenuItemIndicator";
var DropdownMenuItemIndicator = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...itemIndicatorProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ItemIndicator"], {
        ...menuScope,
        ...itemIndicatorProps,
        ref: forwardedRef
    });
});
DropdownMenuItemIndicator.displayName = INDICATOR_NAME;
var SEPARATOR_NAME = "DropdownMenuSeparator";
var DropdownMenuSeparator = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...separatorProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Separator"], {
        ...menuScope,
        ...separatorProps,
        ref: forwardedRef
    });
});
DropdownMenuSeparator.displayName = SEPARATOR_NAME;
var ARROW_NAME = "DropdownMenuArrow";
var DropdownMenuArrow = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...arrowProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Arrow"], {
        ...menuScope,
        ...arrowProps,
        ref: forwardedRef
    });
});
DropdownMenuArrow.displayName = ARROW_NAME;
var DropdownMenuSub = (props)=>{
    const { __scopeDropdownMenu, children, open: openProp, onOpenChange, defaultOpen } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    const [open, setOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useControllableState"])({
        prop: openProp,
        defaultProp: defaultOpen ?? false,
        onChange: onOpenChange,
        caller: "DropdownMenuSub"
    });
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Sub"], {
        ...menuScope,
        open,
        onOpenChange: setOpen,
        children
    });
};
var SUB_TRIGGER_NAME = "DropdownMenuSubTrigger";
var DropdownMenuSubTrigger = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...subTriggerProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SubTrigger"], {
        ...menuScope,
        ...subTriggerProps,
        ref: forwardedRef
    });
});
DropdownMenuSubTrigger.displayName = SUB_TRIGGER_NAME;
var SUB_CONTENT_NAME = "DropdownMenuSubContent";
var DropdownMenuSubContent = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeDropdownMenu, ...subContentProps } = props;
    const menuScope = useMenuScope(__scopeDropdownMenu);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$menu$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SubContent"], {
        ...menuScope,
        ...subContentProps,
        ref: forwardedRef,
        style: {
            ...props.style,
            // re-namespace exposed content custom properties
            ...{
                "--radix-dropdown-menu-content-transform-origin": "var(--radix-popper-transform-origin)",
                "--radix-dropdown-menu-content-available-width": "var(--radix-popper-available-width)",
                "--radix-dropdown-menu-content-available-height": "var(--radix-popper-available-height)",
                "--radix-dropdown-menu-trigger-width": "var(--radix-popper-anchor-width)",
                "--radix-dropdown-menu-trigger-height": "var(--radix-popper-anchor-height)"
            }
        }
    });
});
DropdownMenuSubContent.displayName = SUB_CONTENT_NAME;
var Root2 = DropdownMenu;
var Trigger = DropdownMenuTrigger;
var Portal2 = DropdownMenuPortal;
var Content2 = DropdownMenuContent;
var Group2 = DropdownMenuGroup;
var Label2 = DropdownMenuLabel;
var Item2 = DropdownMenuItem;
var CheckboxItem2 = DropdownMenuCheckboxItem;
var RadioGroup2 = DropdownMenuRadioGroup;
var RadioItem2 = DropdownMenuRadioItem;
var ItemIndicator2 = DropdownMenuItemIndicator;
var Separator2 = DropdownMenuSeparator;
var Arrow2 = DropdownMenuArrow;
var Sub2 = DropdownMenuSub;
var SubTrigger2 = DropdownMenuSubTrigger;
var SubContent2 = DropdownMenuSubContent;
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-right.js [app-client] (ecmascript) <export default as ChevronRightIcon>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ChevronRightIcon",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-right.js [app-client] (ecmascript)");
}),
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>Circle
]);
/**
 * @license lucide-react v0.507.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$createLucideIcon$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/createLucideIcon.js [app-client] (ecmascript)");
;
const __iconNode = [
    [
        "circle",
        {
            cx: "12",
            cy: "12",
            r: "10",
            key: "1mglay"
        }
    ]
];
const Circle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$createLucideIcon$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])("circle", __iconNode);
;
 //# sourceMappingURL=circle.js.map
}),
"[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle.js [app-client] (ecmascript) <export default as CircleIcon>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CircleIcon",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle.js [app-client] (ecmascript)");
}),
"[project]/coding/projects/LangBot/web/node_modules/@tanstack/table-core/build/lib/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ColumnFaceting",
    ()=>ColumnFaceting,
    "ColumnFiltering",
    ()=>ColumnFiltering,
    "ColumnGrouping",
    ()=>ColumnGrouping,
    "ColumnOrdering",
    ()=>ColumnOrdering,
    "ColumnPinning",
    ()=>ColumnPinning,
    "ColumnSizing",
    ()=>ColumnSizing,
    "ColumnVisibility",
    ()=>ColumnVisibility,
    "GlobalFaceting",
    ()=>GlobalFaceting,
    "GlobalFiltering",
    ()=>GlobalFiltering,
    "Headers",
    ()=>Headers,
    "RowExpanding",
    ()=>RowExpanding,
    "RowPagination",
    ()=>RowPagination,
    "RowPinning",
    ()=>RowPinning,
    "RowSelection",
    ()=>RowSelection,
    "RowSorting",
    ()=>RowSorting,
    "_getVisibleLeafColumns",
    ()=>_getVisibleLeafColumns,
    "aggregationFns",
    ()=>aggregationFns,
    "buildHeaderGroups",
    ()=>buildHeaderGroups,
    "createCell",
    ()=>createCell,
    "createColumn",
    ()=>createColumn,
    "createColumnHelper",
    ()=>createColumnHelper,
    "createRow",
    ()=>createRow,
    "createTable",
    ()=>createTable,
    "defaultColumnSizing",
    ()=>defaultColumnSizing,
    "expandRows",
    ()=>expandRows,
    "filterFns",
    ()=>filterFns,
    "flattenBy",
    ()=>flattenBy,
    "functionalUpdate",
    ()=>functionalUpdate,
    "getCoreRowModel",
    ()=>getCoreRowModel,
    "getExpandedRowModel",
    ()=>getExpandedRowModel,
    "getFacetedMinMaxValues",
    ()=>getFacetedMinMaxValues,
    "getFacetedRowModel",
    ()=>getFacetedRowModel,
    "getFacetedUniqueValues",
    ()=>getFacetedUniqueValues,
    "getFilteredRowModel",
    ()=>getFilteredRowModel,
    "getGroupedRowModel",
    ()=>getGroupedRowModel,
    "getMemoOptions",
    ()=>getMemoOptions,
    "getPaginationRowModel",
    ()=>getPaginationRowModel,
    "getSortedRowModel",
    ()=>getSortedRowModel,
    "isFunction",
    ()=>isFunction,
    "isNumberArray",
    ()=>isNumberArray,
    "isRowSelected",
    ()=>isRowSelected,
    "isSubRowSelected",
    ()=>isSubRowSelected,
    "makeStateUpdater",
    ()=>makeStateUpdater,
    "memo",
    ()=>memo,
    "noop",
    ()=>noop,
    "orderColumns",
    ()=>orderColumns,
    "passiveEventSupported",
    ()=>passiveEventSupported,
    "reSplitAlphaNumeric",
    ()=>reSplitAlphaNumeric,
    "selectRowsFn",
    ()=>selectRowsFn,
    "shouldAutoRemoveFilter",
    ()=>shouldAutoRemoveFilter,
    "sortingFns",
    ()=>sortingFns
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
   * table-core
   *
   * Copyright (c) TanStack
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE.md file in the root directory of this source tree.
   *
   * @license MIT
   */ // type Person = {
//   firstName: string
//   lastName: string
//   age: number
//   visits: number
//   status: string
//   progress: number
//   createdAt: Date
//   nested: {
//     foo: [
//       {
//         bar: 'bar'
//       }
//     ]
//     bar: { subBar: boolean }[]
//     baz: {
//       foo: 'foo'
//       bar: {
//         baz: 'baz'
//       }
//     }
//   }
// }
// const test: DeepKeys<Person> = 'nested.foo.0.bar'
// const test2: DeepKeys<Person> = 'nested.bar'
// const helper = createColumnHelper<Person>()
// helper.accessor('nested.foo', {
//   cell: info => info.getValue(),
// })
// helper.accessor('nested.foo.0.bar', {
//   cell: info => info.getValue(),
// })
// helper.accessor('nested.bar', {
//   cell: info => info.getValue(),
// })
function createColumnHelper() {
    return {
        accessor: (accessor, column)=>{
            return typeof accessor === 'function' ? {
                ...column,
                accessorFn: accessor
            } : {
                ...column,
                accessorKey: accessor
            };
        },
        display: (column)=>column,
        group: (column)=>column
    };
}
// Is this type a tuple?
// If this type is a tuple, what indices are allowed?
///
function functionalUpdate(updater, input) {
    return typeof updater === 'function' ? updater(input) : updater;
}
function noop() {
//
}
function makeStateUpdater(key, instance) {
    return (updater)=>{
        instance.setState((old)=>{
            return {
                ...old,
                [key]: functionalUpdate(updater, old[key])
            };
        });
    };
}
function isFunction(d) {
    return d instanceof Function;
}
function isNumberArray(d) {
    return Array.isArray(d) && d.every((val)=>typeof val === 'number');
}
function flattenBy(arr, getChildren) {
    const flat = [];
    const recurse = (subArr)=>{
        subArr.forEach((item)=>{
            flat.push(item);
            const children = getChildren(item);
            if (children != null && children.length) {
                recurse(children);
            }
        });
    };
    recurse(arr);
    return flat;
}
function memo(getDeps, fn, opts) {
    let deps = [];
    let result;
    return (depArgs)=>{
        let depTime;
        if (opts.key && opts.debug) depTime = Date.now();
        const newDeps = getDeps(depArgs);
        const depsChanged = newDeps.length !== deps.length || newDeps.some((dep, index)=>deps[index] !== dep);
        if (!depsChanged) {
            return result;
        }
        deps = newDeps;
        let resultTime;
        if (opts.key && opts.debug) resultTime = Date.now();
        result = fn(...newDeps);
        opts == null || opts.onChange == null || opts.onChange(result);
        if (opts.key && opts.debug) {
            if (opts != null && opts.debug()) {
                const depEndTime = Math.round((Date.now() - depTime) * 100) / 100;
                const resultEndTime = Math.round((Date.now() - resultTime) * 100) / 100;
                const resultFpsPercentage = resultEndTime / 16;
                const pad = (str, num)=>{
                    str = String(str);
                    while(str.length < num){
                        str = ' ' + str;
                    }
                    return str;
                };
                console.info(`%c⏱ ${pad(resultEndTime, 5)} /${pad(depEndTime, 5)} ms`, `
            font-size: .6rem;
            font-weight: bold;
            color: hsl(${Math.max(0, Math.min(120 - 120 * resultFpsPercentage, 120))}deg 100% 31%);`, opts == null ? void 0 : opts.key);
            }
        }
        return result;
    };
}
function getMemoOptions(tableOptions, debugLevel, key, onChange) {
    return {
        debug: ()=>{
            var _tableOptions$debugAl;
            return (_tableOptions$debugAl = tableOptions == null ? void 0 : tableOptions.debugAll) != null ? _tableOptions$debugAl : tableOptions[debugLevel];
        },
        key: ("TURBOPACK compile-time value", "development") === 'development' && key,
        onChange
    };
}
function createCell(table, row, column, columnId) {
    const getRenderValue = ()=>{
        var _cell$getValue;
        return (_cell$getValue = cell.getValue()) != null ? _cell$getValue : table.options.renderFallbackValue;
    };
    const cell = {
        id: `${row.id}_${column.id}`,
        row,
        column,
        getValue: ()=>row.getValue(columnId),
        renderValue: getRenderValue,
        getContext: memo(()=>[
                table,
                column,
                row,
                cell
            ], (table, column, row, cell)=>({
                table,
                column,
                row,
                cell: cell,
                getValue: cell.getValue,
                renderValue: cell.renderValue
            }), getMemoOptions(table.options, 'debugCells', 'cell.getContext'))
    };
    table._features.forEach((feature)=>{
        feature.createCell == null || feature.createCell(cell, column, row, table);
    }, {});
    return cell;
}
function createColumn(table, columnDef, depth, parent) {
    var _ref, _resolvedColumnDef$id;
    const defaultColumn = table._getDefaultColumnDef();
    const resolvedColumnDef = {
        ...defaultColumn,
        ...columnDef
    };
    const accessorKey = resolvedColumnDef.accessorKey;
    let id = (_ref = (_resolvedColumnDef$id = resolvedColumnDef.id) != null ? _resolvedColumnDef$id : accessorKey ? typeof String.prototype.replaceAll === 'function' ? accessorKey.replaceAll('.', '_') : accessorKey.replace(/\./g, '_') : undefined) != null ? _ref : typeof resolvedColumnDef.header === 'string' ? resolvedColumnDef.header : undefined;
    let accessorFn;
    if (resolvedColumnDef.accessorFn) {
        accessorFn = resolvedColumnDef.accessorFn;
    } else if (accessorKey) {
        // Support deep accessor keys
        if (accessorKey.includes('.')) {
            accessorFn = (originalRow)=>{
                let result = originalRow;
                for (const key of accessorKey.split('.')){
                    var _result;
                    result = (_result = result) == null ? void 0 : _result[key];
                    if (("TURBOPACK compile-time value", "development") !== 'production' && result === undefined) {
                        console.warn(`"${key}" in deeply nested key "${accessorKey}" returned undefined.`);
                    }
                }
                return result;
            };
        } else {
            accessorFn = (originalRow)=>originalRow[resolvedColumnDef.accessorKey];
        }
    }
    if (!id) {
        if ("TURBOPACK compile-time truthy", 1) {
            throw new Error(resolvedColumnDef.accessorFn ? `Columns require an id when using an accessorFn` : `Columns require an id when using a non-string header`);
        }
        throw new Error();
    }
    let column = {
        id: `${String(id)}`,
        accessorFn,
        parent: parent,
        depth,
        columnDef: resolvedColumnDef,
        columns: [],
        getFlatColumns: memo(()=>[
                true
            ], ()=>{
            var _column$columns;
            return [
                column,
                ...(_column$columns = column.columns) == null ? void 0 : _column$columns.flatMap((d)=>d.getFlatColumns())
            ];
        }, getMemoOptions(table.options, 'debugColumns', 'column.getFlatColumns')),
        getLeafColumns: memo(()=>[
                table._getOrderColumnsFn()
            ], (orderColumns)=>{
            var _column$columns2;
            if ((_column$columns2 = column.columns) != null && _column$columns2.length) {
                let leafColumns = column.columns.flatMap((column)=>column.getLeafColumns());
                return orderColumns(leafColumns);
            }
            return [
                column
            ];
        }, getMemoOptions(table.options, 'debugColumns', 'column.getLeafColumns'))
    };
    for (const feature of table._features){
        feature.createColumn == null || feature.createColumn(column, table);
    }
    // Yes, we have to convert table to unknown, because we know more than the compiler here.
    return column;
}
const debug = 'debugHeaders';
//
function createHeader(table, column, options) {
    var _options$id;
    const id = (_options$id = options.id) != null ? _options$id : column.id;
    let header = {
        id,
        column,
        index: options.index,
        isPlaceholder: !!options.isPlaceholder,
        placeholderId: options.placeholderId,
        depth: options.depth,
        subHeaders: [],
        colSpan: 0,
        rowSpan: 0,
        headerGroup: null,
        getLeafHeaders: ()=>{
            const leafHeaders = [];
            const recurseHeader = (h)=>{
                if (h.subHeaders && h.subHeaders.length) {
                    h.subHeaders.map(recurseHeader);
                }
                leafHeaders.push(h);
            };
            recurseHeader(header);
            return leafHeaders;
        },
        getContext: ()=>({
                table,
                header: header,
                column
            })
    };
    table._features.forEach((feature)=>{
        feature.createHeader == null || feature.createHeader(header, table);
    });
    return header;
}
const Headers = {
    createTable: (table)=>{
        // Header Groups
        table.getHeaderGroups = memo(()=>[
                table.getAllColumns(),
                table.getVisibleLeafColumns(),
                table.getState().columnPinning.left,
                table.getState().columnPinning.right
            ], (allColumns, leafColumns, left, right)=>{
            var _left$map$filter, _right$map$filter;
            const leftColumns = (_left$map$filter = left == null ? void 0 : left.map((columnId)=>leafColumns.find((d)=>d.id === columnId)).filter(Boolean)) != null ? _left$map$filter : [];
            const rightColumns = (_right$map$filter = right == null ? void 0 : right.map((columnId)=>leafColumns.find((d)=>d.id === columnId)).filter(Boolean)) != null ? _right$map$filter : [];
            const centerColumns = leafColumns.filter((column)=>!(left != null && left.includes(column.id)) && !(right != null && right.includes(column.id)));
            const headerGroups = buildHeaderGroups(allColumns, [
                ...leftColumns,
                ...centerColumns,
                ...rightColumns
            ], table);
            return headerGroups;
        }, getMemoOptions(table.options, debug, 'getHeaderGroups'));
        table.getCenterHeaderGroups = memo(()=>[
                table.getAllColumns(),
                table.getVisibleLeafColumns(),
                table.getState().columnPinning.left,
                table.getState().columnPinning.right
            ], (allColumns, leafColumns, left, right)=>{
            leafColumns = leafColumns.filter((column)=>!(left != null && left.includes(column.id)) && !(right != null && right.includes(column.id)));
            return buildHeaderGroups(allColumns, leafColumns, table, 'center');
        }, getMemoOptions(table.options, debug, 'getCenterHeaderGroups'));
        table.getLeftHeaderGroups = memo(()=>[
                table.getAllColumns(),
                table.getVisibleLeafColumns(),
                table.getState().columnPinning.left
            ], (allColumns, leafColumns, left)=>{
            var _left$map$filter2;
            const orderedLeafColumns = (_left$map$filter2 = left == null ? void 0 : left.map((columnId)=>leafColumns.find((d)=>d.id === columnId)).filter(Boolean)) != null ? _left$map$filter2 : [];
            return buildHeaderGroups(allColumns, orderedLeafColumns, table, 'left');
        }, getMemoOptions(table.options, debug, 'getLeftHeaderGroups'));
        table.getRightHeaderGroups = memo(()=>[
                table.getAllColumns(),
                table.getVisibleLeafColumns(),
                table.getState().columnPinning.right
            ], (allColumns, leafColumns, right)=>{
            var _right$map$filter2;
            const orderedLeafColumns = (_right$map$filter2 = right == null ? void 0 : right.map((columnId)=>leafColumns.find((d)=>d.id === columnId)).filter(Boolean)) != null ? _right$map$filter2 : [];
            return buildHeaderGroups(allColumns, orderedLeafColumns, table, 'right');
        }, getMemoOptions(table.options, debug, 'getRightHeaderGroups'));
        // Footer Groups
        table.getFooterGroups = memo(()=>[
                table.getHeaderGroups()
            ], (headerGroups)=>{
            return [
                ...headerGroups
            ].reverse();
        }, getMemoOptions(table.options, debug, 'getFooterGroups'));
        table.getLeftFooterGroups = memo(()=>[
                table.getLeftHeaderGroups()
            ], (headerGroups)=>{
            return [
                ...headerGroups
            ].reverse();
        }, getMemoOptions(table.options, debug, 'getLeftFooterGroups'));
        table.getCenterFooterGroups = memo(()=>[
                table.getCenterHeaderGroups()
            ], (headerGroups)=>{
            return [
                ...headerGroups
            ].reverse();
        }, getMemoOptions(table.options, debug, 'getCenterFooterGroups'));
        table.getRightFooterGroups = memo(()=>[
                table.getRightHeaderGroups()
            ], (headerGroups)=>{
            return [
                ...headerGroups
            ].reverse();
        }, getMemoOptions(table.options, debug, 'getRightFooterGroups'));
        // Flat Headers
        table.getFlatHeaders = memo(()=>[
                table.getHeaderGroups()
            ], (headerGroups)=>{
            return headerGroups.map((headerGroup)=>{
                return headerGroup.headers;
            }).flat();
        }, getMemoOptions(table.options, debug, 'getFlatHeaders'));
        table.getLeftFlatHeaders = memo(()=>[
                table.getLeftHeaderGroups()
            ], (left)=>{
            return left.map((headerGroup)=>{
                return headerGroup.headers;
            }).flat();
        }, getMemoOptions(table.options, debug, 'getLeftFlatHeaders'));
        table.getCenterFlatHeaders = memo(()=>[
                table.getCenterHeaderGroups()
            ], (left)=>{
            return left.map((headerGroup)=>{
                return headerGroup.headers;
            }).flat();
        }, getMemoOptions(table.options, debug, 'getCenterFlatHeaders'));
        table.getRightFlatHeaders = memo(()=>[
                table.getRightHeaderGroups()
            ], (left)=>{
            return left.map((headerGroup)=>{
                return headerGroup.headers;
            }).flat();
        }, getMemoOptions(table.options, debug, 'getRightFlatHeaders'));
        // Leaf Headers
        table.getCenterLeafHeaders = memo(()=>[
                table.getCenterFlatHeaders()
            ], (flatHeaders)=>{
            return flatHeaders.filter((header)=>{
                var _header$subHeaders;
                return !((_header$subHeaders = header.subHeaders) != null && _header$subHeaders.length);
            });
        }, getMemoOptions(table.options, debug, 'getCenterLeafHeaders'));
        table.getLeftLeafHeaders = memo(()=>[
                table.getLeftFlatHeaders()
            ], (flatHeaders)=>{
            return flatHeaders.filter((header)=>{
                var _header$subHeaders2;
                return !((_header$subHeaders2 = header.subHeaders) != null && _header$subHeaders2.length);
            });
        }, getMemoOptions(table.options, debug, 'getLeftLeafHeaders'));
        table.getRightLeafHeaders = memo(()=>[
                table.getRightFlatHeaders()
            ], (flatHeaders)=>{
            return flatHeaders.filter((header)=>{
                var _header$subHeaders3;
                return !((_header$subHeaders3 = header.subHeaders) != null && _header$subHeaders3.length);
            });
        }, getMemoOptions(table.options, debug, 'getRightLeafHeaders'));
        table.getLeafHeaders = memo(()=>[
                table.getLeftHeaderGroups(),
                table.getCenterHeaderGroups(),
                table.getRightHeaderGroups()
            ], (left, center, right)=>{
            var _left$0$headers, _left$, _center$0$headers, _center$, _right$0$headers, _right$;
            return [
                ...(_left$0$headers = (_left$ = left[0]) == null ? void 0 : _left$.headers) != null ? _left$0$headers : [],
                ...(_center$0$headers = (_center$ = center[0]) == null ? void 0 : _center$.headers) != null ? _center$0$headers : [],
                ...(_right$0$headers = (_right$ = right[0]) == null ? void 0 : _right$.headers) != null ? _right$0$headers : []
            ].map((header)=>{
                return header.getLeafHeaders();
            }).flat();
        }, getMemoOptions(table.options, debug, 'getLeafHeaders'));
    }
};
function buildHeaderGroups(allColumns, columnsToGroup, table, headerFamily) {
    var _headerGroups$0$heade, _headerGroups$;
    // Find the max depth of the columns:
    // build the leaf column row
    // build each buffer row going up
    //    placeholder for non-existent level
    //    real column for existing level
    let maxDepth = 0;
    const findMaxDepth = function(columns, depth) {
        if (depth === void 0) {
            depth = 1;
        }
        maxDepth = Math.max(maxDepth, depth);
        columns.filter((column)=>column.getIsVisible()).forEach((column)=>{
            var _column$columns;
            if ((_column$columns = column.columns) != null && _column$columns.length) {
                findMaxDepth(column.columns, depth + 1);
            }
        }, 0);
    };
    findMaxDepth(allColumns);
    let headerGroups = [];
    const createHeaderGroup = (headersToGroup, depth)=>{
        // The header group we are creating
        const headerGroup = {
            depth,
            id: [
                headerFamily,
                `${depth}`
            ].filter(Boolean).join('_'),
            headers: []
        };
        // The parent columns we're going to scan next
        const pendingParentHeaders = [];
        // Scan each column for parents
        headersToGroup.forEach((headerToGroup)=>{
            // What is the latest (last) parent column?
            const latestPendingParentHeader = [
                ...pendingParentHeaders
            ].reverse()[0];
            const isLeafHeader = headerToGroup.column.depth === headerGroup.depth;
            let column;
            let isPlaceholder = false;
            if (isLeafHeader && headerToGroup.column.parent) {
                // The parent header is new
                column = headerToGroup.column.parent;
            } else {
                // The parent header is repeated
                column = headerToGroup.column;
                isPlaceholder = true;
            }
            if (latestPendingParentHeader && (latestPendingParentHeader == null ? void 0 : latestPendingParentHeader.column) === column) {
                // This column is repeated. Add it as a sub header to the next batch
                latestPendingParentHeader.subHeaders.push(headerToGroup);
            } else {
                // This is a new header. Let's create it
                const header = createHeader(table, column, {
                    id: [
                        headerFamily,
                        depth,
                        column.id,
                        headerToGroup == null ? void 0 : headerToGroup.id
                    ].filter(Boolean).join('_'),
                    isPlaceholder,
                    placeholderId: isPlaceholder ? `${pendingParentHeaders.filter((d)=>d.column === column).length}` : undefined,
                    depth,
                    index: pendingParentHeaders.length
                });
                // Add the headerToGroup as a subHeader of the new header
                header.subHeaders.push(headerToGroup);
                // Add the new header to the pendingParentHeaders to get grouped
                // in the next batch
                pendingParentHeaders.push(header);
            }
            headerGroup.headers.push(headerToGroup);
            headerToGroup.headerGroup = headerGroup;
        });
        headerGroups.push(headerGroup);
        if (depth > 0) {
            createHeaderGroup(pendingParentHeaders, depth - 1);
        }
    };
    const bottomHeaders = columnsToGroup.map((column, index)=>createHeader(table, column, {
            depth: maxDepth,
            index
        }));
    createHeaderGroup(bottomHeaders, maxDepth - 1);
    headerGroups.reverse();
    // headerGroups = headerGroups.filter(headerGroup => {
    //   return !headerGroup.headers.every(header => header.isPlaceholder)
    // })
    const recurseHeadersForSpans = (headers)=>{
        const filteredHeaders = headers.filter((header)=>header.column.getIsVisible());
        return filteredHeaders.map((header)=>{
            let colSpan = 0;
            let rowSpan = 0;
            let childRowSpans = [
                0
            ];
            if (header.subHeaders && header.subHeaders.length) {
                childRowSpans = [];
                recurseHeadersForSpans(header.subHeaders).forEach((_ref)=>{
                    let { colSpan: childColSpan, rowSpan: childRowSpan } = _ref;
                    colSpan += childColSpan;
                    childRowSpans.push(childRowSpan);
                });
            } else {
                colSpan = 1;
            }
            const minChildRowSpan = Math.min(...childRowSpans);
            rowSpan = rowSpan + minChildRowSpan;
            header.colSpan = colSpan;
            header.rowSpan = rowSpan;
            return {
                colSpan,
                rowSpan
            };
        });
    };
    recurseHeadersForSpans((_headerGroups$0$heade = (_headerGroups$ = headerGroups[0]) == null ? void 0 : _headerGroups$.headers) != null ? _headerGroups$0$heade : []);
    return headerGroups;
}
const createRow = (table, id, original, rowIndex, depth, subRows, parentId)=>{
    let row = {
        id,
        index: rowIndex,
        original,
        depth,
        parentId,
        _valuesCache: {},
        _uniqueValuesCache: {},
        getValue: (columnId)=>{
            if (row._valuesCache.hasOwnProperty(columnId)) {
                return row._valuesCache[columnId];
            }
            const column = table.getColumn(columnId);
            if (!(column != null && column.accessorFn)) {
                return undefined;
            }
            row._valuesCache[columnId] = column.accessorFn(row.original, rowIndex);
            return row._valuesCache[columnId];
        },
        getUniqueValues: (columnId)=>{
            if (row._uniqueValuesCache.hasOwnProperty(columnId)) {
                return row._uniqueValuesCache[columnId];
            }
            const column = table.getColumn(columnId);
            if (!(column != null && column.accessorFn)) {
                return undefined;
            }
            if (!column.columnDef.getUniqueValues) {
                row._uniqueValuesCache[columnId] = [
                    row.getValue(columnId)
                ];
                return row._uniqueValuesCache[columnId];
            }
            row._uniqueValuesCache[columnId] = column.columnDef.getUniqueValues(row.original, rowIndex);
            return row._uniqueValuesCache[columnId];
        },
        renderValue: (columnId)=>{
            var _row$getValue;
            return (_row$getValue = row.getValue(columnId)) != null ? _row$getValue : table.options.renderFallbackValue;
        },
        subRows: subRows != null ? subRows : [],
        getLeafRows: ()=>flattenBy(row.subRows, (d)=>d.subRows),
        getParentRow: ()=>row.parentId ? table.getRow(row.parentId, true) : undefined,
        getParentRows: ()=>{
            let parentRows = [];
            let currentRow = row;
            while(true){
                const parentRow = currentRow.getParentRow();
                if (!parentRow) break;
                parentRows.push(parentRow);
                currentRow = parentRow;
            }
            return parentRows.reverse();
        },
        getAllCells: memo(()=>[
                table.getAllLeafColumns()
            ], (leafColumns)=>{
            return leafColumns.map((column)=>{
                return createCell(table, row, column, column.id);
            });
        }, getMemoOptions(table.options, 'debugRows', 'getAllCells')),
        _getAllCellsByColumnId: memo(()=>[
                row.getAllCells()
            ], (allCells)=>{
            return allCells.reduce((acc, cell)=>{
                acc[cell.column.id] = cell;
                return acc;
            }, {});
        }, getMemoOptions(table.options, 'debugRows', 'getAllCellsByColumnId'))
    };
    for(let i = 0; i < table._features.length; i++){
        const feature = table._features[i];
        feature == null || feature.createRow == null || feature.createRow(row, table);
    }
    return row;
};
//
const ColumnFaceting = {
    createColumn: (column, table)=>{
        column._getFacetedRowModel = table.options.getFacetedRowModel && table.options.getFacetedRowModel(table, column.id);
        column.getFacetedRowModel = ()=>{
            if (!column._getFacetedRowModel) {
                return table.getPreFilteredRowModel();
            }
            return column._getFacetedRowModel();
        };
        column._getFacetedUniqueValues = table.options.getFacetedUniqueValues && table.options.getFacetedUniqueValues(table, column.id);
        column.getFacetedUniqueValues = ()=>{
            if (!column._getFacetedUniqueValues) {
                return new Map();
            }
            return column._getFacetedUniqueValues();
        };
        column._getFacetedMinMaxValues = table.options.getFacetedMinMaxValues && table.options.getFacetedMinMaxValues(table, column.id);
        column.getFacetedMinMaxValues = ()=>{
            if (!column._getFacetedMinMaxValues) {
                return undefined;
            }
            return column._getFacetedMinMaxValues();
        };
    }
};
const includesString = (row, columnId, filterValue)=>{
    var _filterValue$toString, _row$getValue;
    const search = filterValue == null || (_filterValue$toString = filterValue.toString()) == null ? void 0 : _filterValue$toString.toLowerCase();
    return Boolean((_row$getValue = row.getValue(columnId)) == null || (_row$getValue = _row$getValue.toString()) == null || (_row$getValue = _row$getValue.toLowerCase()) == null ? void 0 : _row$getValue.includes(search));
};
includesString.autoRemove = (val)=>testFalsey(val);
const includesStringSensitive = (row, columnId, filterValue)=>{
    var _row$getValue2;
    return Boolean((_row$getValue2 = row.getValue(columnId)) == null || (_row$getValue2 = _row$getValue2.toString()) == null ? void 0 : _row$getValue2.includes(filterValue));
};
includesStringSensitive.autoRemove = (val)=>testFalsey(val);
const equalsString = (row, columnId, filterValue)=>{
    var _row$getValue3;
    return ((_row$getValue3 = row.getValue(columnId)) == null || (_row$getValue3 = _row$getValue3.toString()) == null ? void 0 : _row$getValue3.toLowerCase()) === (filterValue == null ? void 0 : filterValue.toLowerCase());
};
equalsString.autoRemove = (val)=>testFalsey(val);
const arrIncludes = (row, columnId, filterValue)=>{
    var _row$getValue4;
    return (_row$getValue4 = row.getValue(columnId)) == null ? void 0 : _row$getValue4.includes(filterValue);
};
arrIncludes.autoRemove = (val)=>testFalsey(val);
const arrIncludesAll = (row, columnId, filterValue)=>{
    return !filterValue.some((val)=>{
        var _row$getValue5;
        return !((_row$getValue5 = row.getValue(columnId)) != null && _row$getValue5.includes(val));
    });
};
arrIncludesAll.autoRemove = (val)=>testFalsey(val) || !(val != null && val.length);
const arrIncludesSome = (row, columnId, filterValue)=>{
    return filterValue.some((val)=>{
        var _row$getValue6;
        return (_row$getValue6 = row.getValue(columnId)) == null ? void 0 : _row$getValue6.includes(val);
    });
};
arrIncludesSome.autoRemove = (val)=>testFalsey(val) || !(val != null && val.length);
const equals = (row, columnId, filterValue)=>{
    return row.getValue(columnId) === filterValue;
};
equals.autoRemove = (val)=>testFalsey(val);
const weakEquals = (row, columnId, filterValue)=>{
    return row.getValue(columnId) == filterValue;
};
weakEquals.autoRemove = (val)=>testFalsey(val);
const inNumberRange = (row, columnId, filterValue)=>{
    let [min, max] = filterValue;
    const rowValue = row.getValue(columnId);
    return rowValue >= min && rowValue <= max;
};
inNumberRange.resolveFilterValue = (val)=>{
    let [unsafeMin, unsafeMax] = val;
    let parsedMin = typeof unsafeMin !== 'number' ? parseFloat(unsafeMin) : unsafeMin;
    let parsedMax = typeof unsafeMax !== 'number' ? parseFloat(unsafeMax) : unsafeMax;
    let min = unsafeMin === null || Number.isNaN(parsedMin) ? -Infinity : parsedMin;
    let max = unsafeMax === null || Number.isNaN(parsedMax) ? Infinity : parsedMax;
    if (min > max) {
        const temp = min;
        min = max;
        max = temp;
    }
    return [
        min,
        max
    ];
};
inNumberRange.autoRemove = (val)=>testFalsey(val) || testFalsey(val[0]) && testFalsey(val[1]);
// Export
const filterFns = {
    includesString,
    includesStringSensitive,
    equalsString,
    arrIncludes,
    arrIncludesAll,
    arrIncludesSome,
    equals,
    weakEquals,
    inNumberRange
};
// Utils
function testFalsey(val) {
    return val === undefined || val === null || val === '';
}
//
const ColumnFiltering = {
    getDefaultColumnDef: ()=>{
        return {
            filterFn: 'auto'
        };
    },
    getInitialState: (state)=>{
        return {
            columnFilters: [],
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onColumnFiltersChange: makeStateUpdater('columnFilters', table),
            filterFromLeafRows: false,
            maxLeafRowFilterDepth: 100
        };
    },
    createColumn: (column, table)=>{
        column.getAutoFilterFn = ()=>{
            const firstRow = table.getCoreRowModel().flatRows[0];
            const value = firstRow == null ? void 0 : firstRow.getValue(column.id);
            if (typeof value === 'string') {
                return filterFns.includesString;
            }
            if (typeof value === 'number') {
                return filterFns.inNumberRange;
            }
            if (typeof value === 'boolean') {
                return filterFns.equals;
            }
            if (value !== null && typeof value === 'object') {
                return filterFns.equals;
            }
            if (Array.isArray(value)) {
                return filterFns.arrIncludes;
            }
            return filterFns.weakEquals;
        };
        column.getFilterFn = ()=>{
            var _table$options$filter, _table$options$filter2;
            return isFunction(column.columnDef.filterFn) ? column.columnDef.filterFn : column.columnDef.filterFn === 'auto' ? column.getAutoFilterFn() : (_table$options$filter = (_table$options$filter2 = table.options.filterFns) == null ? void 0 : _table$options$filter2[column.columnDef.filterFn]) != null ? _table$options$filter : filterFns[column.columnDef.filterFn];
        };
        column.getCanFilter = ()=>{
            var _column$columnDef$ena, _table$options$enable, _table$options$enable2;
            return ((_column$columnDef$ena = column.columnDef.enableColumnFilter) != null ? _column$columnDef$ena : true) && ((_table$options$enable = table.options.enableColumnFilters) != null ? _table$options$enable : true) && ((_table$options$enable2 = table.options.enableFilters) != null ? _table$options$enable2 : true) && !!column.accessorFn;
        };
        column.getIsFiltered = ()=>column.getFilterIndex() > -1;
        column.getFilterValue = ()=>{
            var _table$getState$colum;
            return (_table$getState$colum = table.getState().columnFilters) == null || (_table$getState$colum = _table$getState$colum.find((d)=>d.id === column.id)) == null ? void 0 : _table$getState$colum.value;
        };
        column.getFilterIndex = ()=>{
            var _table$getState$colum2, _table$getState$colum3;
            return (_table$getState$colum2 = (_table$getState$colum3 = table.getState().columnFilters) == null ? void 0 : _table$getState$colum3.findIndex((d)=>d.id === column.id)) != null ? _table$getState$colum2 : -1;
        };
        column.setFilterValue = (value)=>{
            table.setColumnFilters((old)=>{
                const filterFn = column.getFilterFn();
                const previousFilter = old == null ? void 0 : old.find((d)=>d.id === column.id);
                const newFilter = functionalUpdate(value, previousFilter ? previousFilter.value : undefined);
                //
                if (shouldAutoRemoveFilter(filterFn, newFilter, column)) {
                    var _old$filter;
                    return (_old$filter = old == null ? void 0 : old.filter((d)=>d.id !== column.id)) != null ? _old$filter : [];
                }
                const newFilterObj = {
                    id: column.id,
                    value: newFilter
                };
                if (previousFilter) {
                    var _old$map;
                    return (_old$map = old == null ? void 0 : old.map((d)=>{
                        if (d.id === column.id) {
                            return newFilterObj;
                        }
                        return d;
                    })) != null ? _old$map : [];
                }
                if (old != null && old.length) {
                    return [
                        ...old,
                        newFilterObj
                    ];
                }
                return [
                    newFilterObj
                ];
            });
        };
    },
    createRow: (row, _table)=>{
        row.columnFilters = {};
        row.columnFiltersMeta = {};
    },
    createTable: (table)=>{
        table.setColumnFilters = (updater)=>{
            const leafColumns = table.getAllLeafColumns();
            const updateFn = (old)=>{
                var _functionalUpdate;
                return (_functionalUpdate = functionalUpdate(updater, old)) == null ? void 0 : _functionalUpdate.filter((filter)=>{
                    const column = leafColumns.find((d)=>d.id === filter.id);
                    if (column) {
                        const filterFn = column.getFilterFn();
                        if (shouldAutoRemoveFilter(filterFn, filter.value, column)) {
                            return false;
                        }
                    }
                    return true;
                });
            };
            table.options.onColumnFiltersChange == null || table.options.onColumnFiltersChange(updateFn);
        };
        table.resetColumnFilters = (defaultState)=>{
            var _table$initialState$c, _table$initialState;
            table.setColumnFilters(defaultState ? [] : (_table$initialState$c = (_table$initialState = table.initialState) == null ? void 0 : _table$initialState.columnFilters) != null ? _table$initialState$c : []);
        };
        table.getPreFilteredRowModel = ()=>table.getCoreRowModel();
        table.getFilteredRowModel = ()=>{
            if (!table._getFilteredRowModel && table.options.getFilteredRowModel) {
                table._getFilteredRowModel = table.options.getFilteredRowModel(table);
            }
            if (table.options.manualFiltering || !table._getFilteredRowModel) {
                return table.getPreFilteredRowModel();
            }
            return table._getFilteredRowModel();
        };
    }
};
function shouldAutoRemoveFilter(filterFn, value, column) {
    return (filterFn && filterFn.autoRemove ? filterFn.autoRemove(value, column) : false) || typeof value === 'undefined' || typeof value === 'string' && !value;
}
const sum = (columnId, _leafRows, childRows)=>{
    // It's faster to just add the aggregations together instead of
    // process leaf nodes individually
    return childRows.reduce((sum, next)=>{
        const nextValue = next.getValue(columnId);
        return sum + (typeof nextValue === 'number' ? nextValue : 0);
    }, 0);
};
const min = (columnId, _leafRows, childRows)=>{
    let min;
    childRows.forEach((row)=>{
        const value = row.getValue(columnId);
        if (value != null && (min > value || min === undefined && value >= value)) {
            min = value;
        }
    });
    return min;
};
const max = (columnId, _leafRows, childRows)=>{
    let max;
    childRows.forEach((row)=>{
        const value = row.getValue(columnId);
        if (value != null && (max < value || max === undefined && value >= value)) {
            max = value;
        }
    });
    return max;
};
const extent = (columnId, _leafRows, childRows)=>{
    let min;
    let max;
    childRows.forEach((row)=>{
        const value = row.getValue(columnId);
        if (value != null) {
            if (min === undefined) {
                if (value >= value) min = max = value;
            } else {
                if (min > value) min = value;
                if (max < value) max = value;
            }
        }
    });
    return [
        min,
        max
    ];
};
const mean = (columnId, leafRows)=>{
    let count = 0;
    let sum = 0;
    leafRows.forEach((row)=>{
        let value = row.getValue(columnId);
        if (value != null && (value = +value) >= value) {
            ++count, sum += value;
        }
    });
    if (count) return sum / count;
    return;
};
const median = (columnId, leafRows)=>{
    if (!leafRows.length) {
        return;
    }
    const values = leafRows.map((row)=>row.getValue(columnId));
    if (!isNumberArray(values)) {
        return;
    }
    if (values.length === 1) {
        return values[0];
    }
    const mid = Math.floor(values.length / 2);
    const nums = values.sort((a, b)=>a - b);
    return values.length % 2 !== 0 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
};
const unique = (columnId, leafRows)=>{
    return Array.from(new Set(leafRows.map((d)=>d.getValue(columnId))).values());
};
const uniqueCount = (columnId, leafRows)=>{
    return new Set(leafRows.map((d)=>d.getValue(columnId))).size;
};
const count = (_columnId, leafRows)=>{
    return leafRows.length;
};
const aggregationFns = {
    sum,
    min,
    max,
    extent,
    mean,
    median,
    unique,
    uniqueCount,
    count
};
//
const ColumnGrouping = {
    getDefaultColumnDef: ()=>{
        return {
            aggregatedCell: (props)=>{
                var _toString, _props$getValue;
                return (_toString = (_props$getValue = props.getValue()) == null || _props$getValue.toString == null ? void 0 : _props$getValue.toString()) != null ? _toString : null;
            },
            aggregationFn: 'auto'
        };
    },
    getInitialState: (state)=>{
        return {
            grouping: [],
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onGroupingChange: makeStateUpdater('grouping', table),
            groupedColumnMode: 'reorder'
        };
    },
    createColumn: (column, table)=>{
        column.toggleGrouping = ()=>{
            table.setGrouping((old)=>{
                // Find any existing grouping for this column
                if (old != null && old.includes(column.id)) {
                    return old.filter((d)=>d !== column.id);
                }
                return [
                    ...old != null ? old : [],
                    column.id
                ];
            });
        };
        column.getCanGroup = ()=>{
            var _column$columnDef$ena, _table$options$enable;
            return ((_column$columnDef$ena = column.columnDef.enableGrouping) != null ? _column$columnDef$ena : true) && ((_table$options$enable = table.options.enableGrouping) != null ? _table$options$enable : true) && (!!column.accessorFn || !!column.columnDef.getGroupingValue);
        };
        column.getIsGrouped = ()=>{
            var _table$getState$group;
            return (_table$getState$group = table.getState().grouping) == null ? void 0 : _table$getState$group.includes(column.id);
        };
        column.getGroupedIndex = ()=>{
            var _table$getState$group2;
            return (_table$getState$group2 = table.getState().grouping) == null ? void 0 : _table$getState$group2.indexOf(column.id);
        };
        column.getToggleGroupingHandler = ()=>{
            const canGroup = column.getCanGroup();
            return ()=>{
                if (!canGroup) return;
                column.toggleGrouping();
            };
        };
        column.getAutoAggregationFn = ()=>{
            const firstRow = table.getCoreRowModel().flatRows[0];
            const value = firstRow == null ? void 0 : firstRow.getValue(column.id);
            if (typeof value === 'number') {
                return aggregationFns.sum;
            }
            if (Object.prototype.toString.call(value) === '[object Date]') {
                return aggregationFns.extent;
            }
        };
        column.getAggregationFn = ()=>{
            var _table$options$aggreg, _table$options$aggreg2;
            if (!column) {
                throw new Error();
            }
            return isFunction(column.columnDef.aggregationFn) ? column.columnDef.aggregationFn : column.columnDef.aggregationFn === 'auto' ? column.getAutoAggregationFn() : (_table$options$aggreg = (_table$options$aggreg2 = table.options.aggregationFns) == null ? void 0 : _table$options$aggreg2[column.columnDef.aggregationFn]) != null ? _table$options$aggreg : aggregationFns[column.columnDef.aggregationFn];
        };
    },
    createTable: (table)=>{
        table.setGrouping = (updater)=>table.options.onGroupingChange == null ? void 0 : table.options.onGroupingChange(updater);
        table.resetGrouping = (defaultState)=>{
            var _table$initialState$g, _table$initialState;
            table.setGrouping(defaultState ? [] : (_table$initialState$g = (_table$initialState = table.initialState) == null ? void 0 : _table$initialState.grouping) != null ? _table$initialState$g : []);
        };
        table.getPreGroupedRowModel = ()=>table.getFilteredRowModel();
        table.getGroupedRowModel = ()=>{
            if (!table._getGroupedRowModel && table.options.getGroupedRowModel) {
                table._getGroupedRowModel = table.options.getGroupedRowModel(table);
            }
            if (table.options.manualGrouping || !table._getGroupedRowModel) {
                return table.getPreGroupedRowModel();
            }
            return table._getGroupedRowModel();
        };
    },
    createRow: (row, table)=>{
        row.getIsGrouped = ()=>!!row.groupingColumnId;
        row.getGroupingValue = (columnId)=>{
            if (row._groupingValuesCache.hasOwnProperty(columnId)) {
                return row._groupingValuesCache[columnId];
            }
            const column = table.getColumn(columnId);
            if (!(column != null && column.columnDef.getGroupingValue)) {
                return row.getValue(columnId);
            }
            row._groupingValuesCache[columnId] = column.columnDef.getGroupingValue(row.original);
            return row._groupingValuesCache[columnId];
        };
        row._groupingValuesCache = {};
    },
    createCell: (cell, column, row, table)=>{
        cell.getIsGrouped = ()=>column.getIsGrouped() && column.id === row.groupingColumnId;
        cell.getIsPlaceholder = ()=>!cell.getIsGrouped() && column.getIsGrouped();
        cell.getIsAggregated = ()=>{
            var _row$subRows;
            return !cell.getIsGrouped() && !cell.getIsPlaceholder() && !!((_row$subRows = row.subRows) != null && _row$subRows.length);
        };
    }
};
function orderColumns(leafColumns, grouping, groupedColumnMode) {
    if (!(grouping != null && grouping.length) || !groupedColumnMode) {
        return leafColumns;
    }
    const nonGroupingColumns = leafColumns.filter((col)=>!grouping.includes(col.id));
    if (groupedColumnMode === 'remove') {
        return nonGroupingColumns;
    }
    const groupingColumns = grouping.map((g)=>leafColumns.find((col)=>col.id === g)).filter(Boolean);
    return [
        ...groupingColumns,
        ...nonGroupingColumns
    ];
}
//
const ColumnOrdering = {
    getInitialState: (state)=>{
        return {
            columnOrder: [],
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onColumnOrderChange: makeStateUpdater('columnOrder', table)
        };
    },
    createColumn: (column, table)=>{
        column.getIndex = memo((position)=>[
                _getVisibleLeafColumns(table, position)
            ], (columns)=>columns.findIndex((d)=>d.id === column.id), getMemoOptions(table.options, 'debugColumns', 'getIndex'));
        column.getIsFirstColumn = (position)=>{
            var _columns$;
            const columns = _getVisibleLeafColumns(table, position);
            return ((_columns$ = columns[0]) == null ? void 0 : _columns$.id) === column.id;
        };
        column.getIsLastColumn = (position)=>{
            var _columns;
            const columns = _getVisibleLeafColumns(table, position);
            return ((_columns = columns[columns.length - 1]) == null ? void 0 : _columns.id) === column.id;
        };
    },
    createTable: (table)=>{
        table.setColumnOrder = (updater)=>table.options.onColumnOrderChange == null ? void 0 : table.options.onColumnOrderChange(updater);
        table.resetColumnOrder = (defaultState)=>{
            var _table$initialState$c;
            table.setColumnOrder(defaultState ? [] : (_table$initialState$c = table.initialState.columnOrder) != null ? _table$initialState$c : []);
        };
        table._getOrderColumnsFn = memo(()=>[
                table.getState().columnOrder,
                table.getState().grouping,
                table.options.groupedColumnMode
            ], (columnOrder, grouping, groupedColumnMode)=>(columns)=>{
                // Sort grouped columns to the start of the column list
                // before the headers are built
                let orderedColumns = [];
                // If there is no order, return the normal columns
                if (!(columnOrder != null && columnOrder.length)) {
                    orderedColumns = columns;
                } else {
                    const columnOrderCopy = [
                        ...columnOrder
                    ];
                    // If there is an order, make a copy of the columns
                    const columnsCopy = [
                        ...columns
                    ];
                    // And make a new ordered array of the columns
                    // Loop over the columns and place them in order into the new array
                    while(columnsCopy.length && columnOrderCopy.length){
                        const targetColumnId = columnOrderCopy.shift();
                        const foundIndex = columnsCopy.findIndex((d)=>d.id === targetColumnId);
                        if (foundIndex > -1) {
                            orderedColumns.push(columnsCopy.splice(foundIndex, 1)[0]);
                        }
                    }
                    // If there are any columns left, add them to the end
                    orderedColumns = [
                        ...orderedColumns,
                        ...columnsCopy
                    ];
                }
                return orderColumns(orderedColumns, grouping, groupedColumnMode);
            }, getMemoOptions(table.options, 'debugTable', '_getOrderColumnsFn'));
    }
};
//
const getDefaultColumnPinningState = ()=>({
        left: [],
        right: []
    });
const ColumnPinning = {
    getInitialState: (state)=>{
        return {
            columnPinning: getDefaultColumnPinningState(),
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onColumnPinningChange: makeStateUpdater('columnPinning', table)
        };
    },
    createColumn: (column, table)=>{
        column.pin = (position)=>{
            const columnIds = column.getLeafColumns().map((d)=>d.id).filter(Boolean);
            table.setColumnPinning((old)=>{
                var _old$left3, _old$right3;
                if (position === 'right') {
                    var _old$left, _old$right;
                    return {
                        left: ((_old$left = old == null ? void 0 : old.left) != null ? _old$left : []).filter((d)=>!(columnIds != null && columnIds.includes(d))),
                        right: [
                            ...((_old$right = old == null ? void 0 : old.right) != null ? _old$right : []).filter((d)=>!(columnIds != null && columnIds.includes(d))),
                            ...columnIds
                        ]
                    };
                }
                if (position === 'left') {
                    var _old$left2, _old$right2;
                    return {
                        left: [
                            ...((_old$left2 = old == null ? void 0 : old.left) != null ? _old$left2 : []).filter((d)=>!(columnIds != null && columnIds.includes(d))),
                            ...columnIds
                        ],
                        right: ((_old$right2 = old == null ? void 0 : old.right) != null ? _old$right2 : []).filter((d)=>!(columnIds != null && columnIds.includes(d)))
                    };
                }
                return {
                    left: ((_old$left3 = old == null ? void 0 : old.left) != null ? _old$left3 : []).filter((d)=>!(columnIds != null && columnIds.includes(d))),
                    right: ((_old$right3 = old == null ? void 0 : old.right) != null ? _old$right3 : []).filter((d)=>!(columnIds != null && columnIds.includes(d)))
                };
            });
        };
        column.getCanPin = ()=>{
            const leafColumns = column.getLeafColumns();
            return leafColumns.some((d)=>{
                var _d$columnDef$enablePi, _ref, _table$options$enable;
                return ((_d$columnDef$enablePi = d.columnDef.enablePinning) != null ? _d$columnDef$enablePi : true) && ((_ref = (_table$options$enable = table.options.enableColumnPinning) != null ? _table$options$enable : table.options.enablePinning) != null ? _ref : true);
            });
        };
        column.getIsPinned = ()=>{
            const leafColumnIds = column.getLeafColumns().map((d)=>d.id);
            const { left, right } = table.getState().columnPinning;
            const isLeft = leafColumnIds.some((d)=>left == null ? void 0 : left.includes(d));
            const isRight = leafColumnIds.some((d)=>right == null ? void 0 : right.includes(d));
            return isLeft ? 'left' : isRight ? 'right' : false;
        };
        column.getPinnedIndex = ()=>{
            var _table$getState$colum, _table$getState$colum2;
            const position = column.getIsPinned();
            return position ? (_table$getState$colum = (_table$getState$colum2 = table.getState().columnPinning) == null || (_table$getState$colum2 = _table$getState$colum2[position]) == null ? void 0 : _table$getState$colum2.indexOf(column.id)) != null ? _table$getState$colum : -1 : 0;
        };
    },
    createRow: (row, table)=>{
        row.getCenterVisibleCells = memo(()=>[
                row._getAllVisibleCells(),
                table.getState().columnPinning.left,
                table.getState().columnPinning.right
            ], (allCells, left, right)=>{
            const leftAndRight = [
                ...left != null ? left : [],
                ...right != null ? right : []
            ];
            return allCells.filter((d)=>!leftAndRight.includes(d.column.id));
        }, getMemoOptions(table.options, 'debugRows', 'getCenterVisibleCells'));
        row.getLeftVisibleCells = memo(()=>[
                row._getAllVisibleCells(),
                table.getState().columnPinning.left
            ], (allCells, left)=>{
            const cells = (left != null ? left : []).map((columnId)=>allCells.find((cell)=>cell.column.id === columnId)).filter(Boolean).map((d)=>({
                    ...d,
                    position: 'left'
                }));
            return cells;
        }, getMemoOptions(table.options, 'debugRows', 'getLeftVisibleCells'));
        row.getRightVisibleCells = memo(()=>[
                row._getAllVisibleCells(),
                table.getState().columnPinning.right
            ], (allCells, right)=>{
            const cells = (right != null ? right : []).map((columnId)=>allCells.find((cell)=>cell.column.id === columnId)).filter(Boolean).map((d)=>({
                    ...d,
                    position: 'right'
                }));
            return cells;
        }, getMemoOptions(table.options, 'debugRows', 'getRightVisibleCells'));
    },
    createTable: (table)=>{
        table.setColumnPinning = (updater)=>table.options.onColumnPinningChange == null ? void 0 : table.options.onColumnPinningChange(updater);
        table.resetColumnPinning = (defaultState)=>{
            var _table$initialState$c, _table$initialState;
            return table.setColumnPinning(defaultState ? getDefaultColumnPinningState() : (_table$initialState$c = (_table$initialState = table.initialState) == null ? void 0 : _table$initialState.columnPinning) != null ? _table$initialState$c : getDefaultColumnPinningState());
        };
        table.getIsSomeColumnsPinned = (position)=>{
            var _pinningState$positio;
            const pinningState = table.getState().columnPinning;
            if (!position) {
                var _pinningState$left, _pinningState$right;
                return Boolean(((_pinningState$left = pinningState.left) == null ? void 0 : _pinningState$left.length) || ((_pinningState$right = pinningState.right) == null ? void 0 : _pinningState$right.length));
            }
            return Boolean((_pinningState$positio = pinningState[position]) == null ? void 0 : _pinningState$positio.length);
        };
        table.getLeftLeafColumns = memo(()=>[
                table.getAllLeafColumns(),
                table.getState().columnPinning.left
            ], (allColumns, left)=>{
            return (left != null ? left : []).map((columnId)=>allColumns.find((column)=>column.id === columnId)).filter(Boolean);
        }, getMemoOptions(table.options, 'debugColumns', 'getLeftLeafColumns'));
        table.getRightLeafColumns = memo(()=>[
                table.getAllLeafColumns(),
                table.getState().columnPinning.right
            ], (allColumns, right)=>{
            return (right != null ? right : []).map((columnId)=>allColumns.find((column)=>column.id === columnId)).filter(Boolean);
        }, getMemoOptions(table.options, 'debugColumns', 'getRightLeafColumns'));
        table.getCenterLeafColumns = memo(()=>[
                table.getAllLeafColumns(),
                table.getState().columnPinning.left,
                table.getState().columnPinning.right
            ], (allColumns, left, right)=>{
            const leftAndRight = [
                ...left != null ? left : [],
                ...right != null ? right : []
            ];
            return allColumns.filter((d)=>!leftAndRight.includes(d.id));
        }, getMemoOptions(table.options, 'debugColumns', 'getCenterLeafColumns'));
    }
};
function safelyAccessDocument(_document) {
    return _document || (typeof document !== 'undefined' ? document : null);
}
//
//
const defaultColumnSizing = {
    size: 150,
    minSize: 20,
    maxSize: Number.MAX_SAFE_INTEGER
};
const getDefaultColumnSizingInfoState = ()=>({
        startOffset: null,
        startSize: null,
        deltaOffset: null,
        deltaPercentage: null,
        isResizingColumn: false,
        columnSizingStart: []
    });
const ColumnSizing = {
    getDefaultColumnDef: ()=>{
        return defaultColumnSizing;
    },
    getInitialState: (state)=>{
        return {
            columnSizing: {},
            columnSizingInfo: getDefaultColumnSizingInfoState(),
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            columnResizeMode: 'onEnd',
            columnResizeDirection: 'ltr',
            onColumnSizingChange: makeStateUpdater('columnSizing', table),
            onColumnSizingInfoChange: makeStateUpdater('columnSizingInfo', table)
        };
    },
    createColumn: (column, table)=>{
        column.getSize = ()=>{
            var _column$columnDef$min, _ref, _column$columnDef$max;
            const columnSize = table.getState().columnSizing[column.id];
            return Math.min(Math.max((_column$columnDef$min = column.columnDef.minSize) != null ? _column$columnDef$min : defaultColumnSizing.minSize, (_ref = columnSize != null ? columnSize : column.columnDef.size) != null ? _ref : defaultColumnSizing.size), (_column$columnDef$max = column.columnDef.maxSize) != null ? _column$columnDef$max : defaultColumnSizing.maxSize);
        };
        column.getStart = memo((position)=>[
                position,
                _getVisibleLeafColumns(table, position),
                table.getState().columnSizing
            ], (position, columns)=>columns.slice(0, column.getIndex(position)).reduce((sum, column)=>sum + column.getSize(), 0), getMemoOptions(table.options, 'debugColumns', 'getStart'));
        column.getAfter = memo((position)=>[
                position,
                _getVisibleLeafColumns(table, position),
                table.getState().columnSizing
            ], (position, columns)=>columns.slice(column.getIndex(position) + 1).reduce((sum, column)=>sum + column.getSize(), 0), getMemoOptions(table.options, 'debugColumns', 'getAfter'));
        column.resetSize = ()=>{
            table.setColumnSizing((_ref2)=>{
                let { [column.id]: _, ...rest } = _ref2;
                return rest;
            });
        };
        column.getCanResize = ()=>{
            var _column$columnDef$ena, _table$options$enable;
            return ((_column$columnDef$ena = column.columnDef.enableResizing) != null ? _column$columnDef$ena : true) && ((_table$options$enable = table.options.enableColumnResizing) != null ? _table$options$enable : true);
        };
        column.getIsResizing = ()=>{
            return table.getState().columnSizingInfo.isResizingColumn === column.id;
        };
    },
    createHeader: (header, table)=>{
        header.getSize = ()=>{
            let sum = 0;
            const recurse = (header)=>{
                if (header.subHeaders.length) {
                    header.subHeaders.forEach(recurse);
                } else {
                    var _header$column$getSiz;
                    sum += (_header$column$getSiz = header.column.getSize()) != null ? _header$column$getSiz : 0;
                }
            };
            recurse(header);
            return sum;
        };
        header.getStart = ()=>{
            if (header.index > 0) {
                const prevSiblingHeader = header.headerGroup.headers[header.index - 1];
                return prevSiblingHeader.getStart() + prevSiblingHeader.getSize();
            }
            return 0;
        };
        header.getResizeHandler = (_contextDocument)=>{
            const column = table.getColumn(header.column.id);
            const canResize = column == null ? void 0 : column.getCanResize();
            return (e)=>{
                if (!column || !canResize) {
                    return;
                }
                e.persist == null || e.persist();
                if (isTouchStartEvent(e)) {
                    // lets not respond to multiple touches (e.g. 2 or 3 fingers)
                    if (e.touches && e.touches.length > 1) {
                        return;
                    }
                }
                const startSize = header.getSize();
                const columnSizingStart = header ? header.getLeafHeaders().map((d)=>[
                        d.column.id,
                        d.column.getSize()
                    ]) : [
                    [
                        column.id,
                        column.getSize()
                    ]
                ];
                const clientX = isTouchStartEvent(e) ? Math.round(e.touches[0].clientX) : e.clientX;
                const newColumnSizing = {};
                const updateOffset = (eventType, clientXPos)=>{
                    if (typeof clientXPos !== 'number') {
                        return;
                    }
                    table.setColumnSizingInfo((old)=>{
                        var _old$startOffset, _old$startSize;
                        const deltaDirection = table.options.columnResizeDirection === 'rtl' ? -1 : 1;
                        const deltaOffset = (clientXPos - ((_old$startOffset = old == null ? void 0 : old.startOffset) != null ? _old$startOffset : 0)) * deltaDirection;
                        const deltaPercentage = Math.max(deltaOffset / ((_old$startSize = old == null ? void 0 : old.startSize) != null ? _old$startSize : 0), -0.999999);
                        old.columnSizingStart.forEach((_ref3)=>{
                            let [columnId, headerSize] = _ref3;
                            newColumnSizing[columnId] = Math.round(Math.max(headerSize + headerSize * deltaPercentage, 0) * 100) / 100;
                        });
                        return {
                            ...old,
                            deltaOffset,
                            deltaPercentage
                        };
                    });
                    if (table.options.columnResizeMode === 'onChange' || eventType === 'end') {
                        table.setColumnSizing((old)=>({
                                ...old,
                                ...newColumnSizing
                            }));
                    }
                };
                const onMove = (clientXPos)=>updateOffset('move', clientXPos);
                const onEnd = (clientXPos)=>{
                    updateOffset('end', clientXPos);
                    table.setColumnSizingInfo((old)=>({
                            ...old,
                            isResizingColumn: false,
                            startOffset: null,
                            startSize: null,
                            deltaOffset: null,
                            deltaPercentage: null,
                            columnSizingStart: []
                        }));
                };
                const contextDocument = safelyAccessDocument(_contextDocument);
                const mouseEvents = {
                    moveHandler: (e)=>onMove(e.clientX),
                    upHandler: (e)=>{
                        contextDocument == null || contextDocument.removeEventListener('mousemove', mouseEvents.moveHandler);
                        contextDocument == null || contextDocument.removeEventListener('mouseup', mouseEvents.upHandler);
                        onEnd(e.clientX);
                    }
                };
                const touchEvents = {
                    moveHandler: (e)=>{
                        if (e.cancelable) {
                            e.preventDefault();
                            e.stopPropagation();
                        }
                        onMove(e.touches[0].clientX);
                        return false;
                    },
                    upHandler: (e)=>{
                        var _e$touches$;
                        contextDocument == null || contextDocument.removeEventListener('touchmove', touchEvents.moveHandler);
                        contextDocument == null || contextDocument.removeEventListener('touchend', touchEvents.upHandler);
                        if (e.cancelable) {
                            e.preventDefault();
                            e.stopPropagation();
                        }
                        onEnd((_e$touches$ = e.touches[0]) == null ? void 0 : _e$touches$.clientX);
                    }
                };
                const passiveIfSupported = passiveEventSupported() ? {
                    passive: false
                } : false;
                if (isTouchStartEvent(e)) {
                    contextDocument == null || contextDocument.addEventListener('touchmove', touchEvents.moveHandler, passiveIfSupported);
                    contextDocument == null || contextDocument.addEventListener('touchend', touchEvents.upHandler, passiveIfSupported);
                } else {
                    contextDocument == null || contextDocument.addEventListener('mousemove', mouseEvents.moveHandler, passiveIfSupported);
                    contextDocument == null || contextDocument.addEventListener('mouseup', mouseEvents.upHandler, passiveIfSupported);
                }
                table.setColumnSizingInfo((old)=>({
                        ...old,
                        startOffset: clientX,
                        startSize,
                        deltaOffset: 0,
                        deltaPercentage: 0,
                        columnSizingStart,
                        isResizingColumn: column.id
                    }));
            };
        };
    },
    createTable: (table)=>{
        table.setColumnSizing = (updater)=>table.options.onColumnSizingChange == null ? void 0 : table.options.onColumnSizingChange(updater);
        table.setColumnSizingInfo = (updater)=>table.options.onColumnSizingInfoChange == null ? void 0 : table.options.onColumnSizingInfoChange(updater);
        table.resetColumnSizing = (defaultState)=>{
            var _table$initialState$c;
            table.setColumnSizing(defaultState ? {} : (_table$initialState$c = table.initialState.columnSizing) != null ? _table$initialState$c : {});
        };
        table.resetHeaderSizeInfo = (defaultState)=>{
            var _table$initialState$c2;
            table.setColumnSizingInfo(defaultState ? getDefaultColumnSizingInfoState() : (_table$initialState$c2 = table.initialState.columnSizingInfo) != null ? _table$initialState$c2 : getDefaultColumnSizingInfoState());
        };
        table.getTotalSize = ()=>{
            var _table$getHeaderGroup, _table$getHeaderGroup2;
            return (_table$getHeaderGroup = (_table$getHeaderGroup2 = table.getHeaderGroups()[0]) == null ? void 0 : _table$getHeaderGroup2.headers.reduce((sum, header)=>{
                return sum + header.getSize();
            }, 0)) != null ? _table$getHeaderGroup : 0;
        };
        table.getLeftTotalSize = ()=>{
            var _table$getLeftHeaderG, _table$getLeftHeaderG2;
            return (_table$getLeftHeaderG = (_table$getLeftHeaderG2 = table.getLeftHeaderGroups()[0]) == null ? void 0 : _table$getLeftHeaderG2.headers.reduce((sum, header)=>{
                return sum + header.getSize();
            }, 0)) != null ? _table$getLeftHeaderG : 0;
        };
        table.getCenterTotalSize = ()=>{
            var _table$getCenterHeade, _table$getCenterHeade2;
            return (_table$getCenterHeade = (_table$getCenterHeade2 = table.getCenterHeaderGroups()[0]) == null ? void 0 : _table$getCenterHeade2.headers.reduce((sum, header)=>{
                return sum + header.getSize();
            }, 0)) != null ? _table$getCenterHeade : 0;
        };
        table.getRightTotalSize = ()=>{
            var _table$getRightHeader, _table$getRightHeader2;
            return (_table$getRightHeader = (_table$getRightHeader2 = table.getRightHeaderGroups()[0]) == null ? void 0 : _table$getRightHeader2.headers.reduce((sum, header)=>{
                return sum + header.getSize();
            }, 0)) != null ? _table$getRightHeader : 0;
        };
    }
};
let passiveSupported = null;
function passiveEventSupported() {
    if (typeof passiveSupported === 'boolean') return passiveSupported;
    let supported = false;
    try {
        const options = {
            get passive () {
                supported = true;
                return false;
            }
        };
        const noop = ()=>{};
        window.addEventListener('test', noop, options);
        window.removeEventListener('test', noop);
    } catch (err) {
        supported = false;
    }
    passiveSupported = supported;
    return passiveSupported;
}
function isTouchStartEvent(e) {
    return e.type === 'touchstart';
}
//
const ColumnVisibility = {
    getInitialState: (state)=>{
        return {
            columnVisibility: {},
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onColumnVisibilityChange: makeStateUpdater('columnVisibility', table)
        };
    },
    createColumn: (column, table)=>{
        column.toggleVisibility = (value)=>{
            if (column.getCanHide()) {
                table.setColumnVisibility((old)=>({
                        ...old,
                        [column.id]: value != null ? value : !column.getIsVisible()
                    }));
            }
        };
        column.getIsVisible = ()=>{
            var _ref, _table$getState$colum;
            const childColumns = column.columns;
            return (_ref = childColumns.length ? childColumns.some((c)=>c.getIsVisible()) : (_table$getState$colum = table.getState().columnVisibility) == null ? void 0 : _table$getState$colum[column.id]) != null ? _ref : true;
        };
        column.getCanHide = ()=>{
            var _column$columnDef$ena, _table$options$enable;
            return ((_column$columnDef$ena = column.columnDef.enableHiding) != null ? _column$columnDef$ena : true) && ((_table$options$enable = table.options.enableHiding) != null ? _table$options$enable : true);
        };
        column.getToggleVisibilityHandler = ()=>{
            return (e)=>{
                column.toggleVisibility == null || column.toggleVisibility(e.target.checked);
            };
        };
    },
    createRow: (row, table)=>{
        row._getAllVisibleCells = memo(()=>[
                row.getAllCells(),
                table.getState().columnVisibility
            ], (cells)=>{
            return cells.filter((cell)=>cell.column.getIsVisible());
        }, getMemoOptions(table.options, 'debugRows', '_getAllVisibleCells'));
        row.getVisibleCells = memo(()=>[
                row.getLeftVisibleCells(),
                row.getCenterVisibleCells(),
                row.getRightVisibleCells()
            ], (left, center, right)=>[
                ...left,
                ...center,
                ...right
            ], getMemoOptions(table.options, 'debugRows', 'getVisibleCells'));
    },
    createTable: (table)=>{
        const makeVisibleColumnsMethod = (key, getColumns)=>{
            return memo(()=>[
                    getColumns(),
                    getColumns().filter((d)=>d.getIsVisible()).map((d)=>d.id).join('_')
                ], (columns)=>{
                return columns.filter((d)=>d.getIsVisible == null ? void 0 : d.getIsVisible());
            }, getMemoOptions(table.options, 'debugColumns', key));
        };
        table.getVisibleFlatColumns = makeVisibleColumnsMethod('getVisibleFlatColumns', ()=>table.getAllFlatColumns());
        table.getVisibleLeafColumns = makeVisibleColumnsMethod('getVisibleLeafColumns', ()=>table.getAllLeafColumns());
        table.getLeftVisibleLeafColumns = makeVisibleColumnsMethod('getLeftVisibleLeafColumns', ()=>table.getLeftLeafColumns());
        table.getRightVisibleLeafColumns = makeVisibleColumnsMethod('getRightVisibleLeafColumns', ()=>table.getRightLeafColumns());
        table.getCenterVisibleLeafColumns = makeVisibleColumnsMethod('getCenterVisibleLeafColumns', ()=>table.getCenterLeafColumns());
        table.setColumnVisibility = (updater)=>table.options.onColumnVisibilityChange == null ? void 0 : table.options.onColumnVisibilityChange(updater);
        table.resetColumnVisibility = (defaultState)=>{
            var _table$initialState$c;
            table.setColumnVisibility(defaultState ? {} : (_table$initialState$c = table.initialState.columnVisibility) != null ? _table$initialState$c : {});
        };
        table.toggleAllColumnsVisible = (value)=>{
            var _value;
            value = (_value = value) != null ? _value : !table.getIsAllColumnsVisible();
            table.setColumnVisibility(table.getAllLeafColumns().reduce((obj, column)=>({
                    ...obj,
                    [column.id]: !value ? !(column.getCanHide != null && column.getCanHide()) : value
                }), {}));
        };
        table.getIsAllColumnsVisible = ()=>!table.getAllLeafColumns().some((column)=>!(column.getIsVisible != null && column.getIsVisible()));
        table.getIsSomeColumnsVisible = ()=>table.getAllLeafColumns().some((column)=>column.getIsVisible == null ? void 0 : column.getIsVisible());
        table.getToggleAllColumnsVisibilityHandler = ()=>{
            return (e)=>{
                var _target;
                table.toggleAllColumnsVisible((_target = e.target) == null ? void 0 : _target.checked);
            };
        };
    }
};
function _getVisibleLeafColumns(table, position) {
    return !position ? table.getVisibleLeafColumns() : position === 'center' ? table.getCenterVisibleLeafColumns() : position === 'left' ? table.getLeftVisibleLeafColumns() : table.getRightVisibleLeafColumns();
}
//
const GlobalFaceting = {
    createTable: (table)=>{
        table._getGlobalFacetedRowModel = table.options.getFacetedRowModel && table.options.getFacetedRowModel(table, '__global__');
        table.getGlobalFacetedRowModel = ()=>{
            if (table.options.manualFiltering || !table._getGlobalFacetedRowModel) {
                return table.getPreFilteredRowModel();
            }
            return table._getGlobalFacetedRowModel();
        };
        table._getGlobalFacetedUniqueValues = table.options.getFacetedUniqueValues && table.options.getFacetedUniqueValues(table, '__global__');
        table.getGlobalFacetedUniqueValues = ()=>{
            if (!table._getGlobalFacetedUniqueValues) {
                return new Map();
            }
            return table._getGlobalFacetedUniqueValues();
        };
        table._getGlobalFacetedMinMaxValues = table.options.getFacetedMinMaxValues && table.options.getFacetedMinMaxValues(table, '__global__');
        table.getGlobalFacetedMinMaxValues = ()=>{
            if (!table._getGlobalFacetedMinMaxValues) {
                return;
            }
            return table._getGlobalFacetedMinMaxValues();
        };
    }
};
//
const GlobalFiltering = {
    getInitialState: (state)=>{
        return {
            globalFilter: undefined,
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onGlobalFilterChange: makeStateUpdater('globalFilter', table),
            globalFilterFn: 'auto',
            getColumnCanGlobalFilter: (column)=>{
                var _table$getCoreRowMode;
                const value = (_table$getCoreRowMode = table.getCoreRowModel().flatRows[0]) == null || (_table$getCoreRowMode = _table$getCoreRowMode._getAllCellsByColumnId()[column.id]) == null ? void 0 : _table$getCoreRowMode.getValue();
                return typeof value === 'string' || typeof value === 'number';
            }
        };
    },
    createColumn: (column, table)=>{
        column.getCanGlobalFilter = ()=>{
            var _column$columnDef$ena, _table$options$enable, _table$options$enable2, _table$options$getCol;
            return ((_column$columnDef$ena = column.columnDef.enableGlobalFilter) != null ? _column$columnDef$ena : true) && ((_table$options$enable = table.options.enableGlobalFilter) != null ? _table$options$enable : true) && ((_table$options$enable2 = table.options.enableFilters) != null ? _table$options$enable2 : true) && ((_table$options$getCol = table.options.getColumnCanGlobalFilter == null ? void 0 : table.options.getColumnCanGlobalFilter(column)) != null ? _table$options$getCol : true) && !!column.accessorFn;
        };
    },
    createTable: (table)=>{
        table.getGlobalAutoFilterFn = ()=>{
            return filterFns.includesString;
        };
        table.getGlobalFilterFn = ()=>{
            var _table$options$filter, _table$options$filter2;
            const { globalFilterFn: globalFilterFn } = table.options;
            return isFunction(globalFilterFn) ? globalFilterFn : globalFilterFn === 'auto' ? table.getGlobalAutoFilterFn() : (_table$options$filter = (_table$options$filter2 = table.options.filterFns) == null ? void 0 : _table$options$filter2[globalFilterFn]) != null ? _table$options$filter : filterFns[globalFilterFn];
        };
        table.setGlobalFilter = (updater)=>{
            table.options.onGlobalFilterChange == null || table.options.onGlobalFilterChange(updater);
        };
        table.resetGlobalFilter = (defaultState)=>{
            table.setGlobalFilter(defaultState ? undefined : table.initialState.globalFilter);
        };
    }
};
//
const RowExpanding = {
    getInitialState: (state)=>{
        return {
            expanded: {},
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onExpandedChange: makeStateUpdater('expanded', table),
            paginateExpandedRows: true
        };
    },
    createTable: (table)=>{
        let registered = false;
        let queued = false;
        table._autoResetExpanded = ()=>{
            var _ref, _table$options$autoRe;
            if (!registered) {
                table._queue(()=>{
                    registered = true;
                });
                return;
            }
            if ((_ref = (_table$options$autoRe = table.options.autoResetAll) != null ? _table$options$autoRe : table.options.autoResetExpanded) != null ? _ref : !table.options.manualExpanding) {
                if (queued) return;
                queued = true;
                table._queue(()=>{
                    table.resetExpanded();
                    queued = false;
                });
            }
        };
        table.setExpanded = (updater)=>table.options.onExpandedChange == null ? void 0 : table.options.onExpandedChange(updater);
        table.toggleAllRowsExpanded = (expanded)=>{
            if (expanded != null ? expanded : !table.getIsAllRowsExpanded()) {
                table.setExpanded(true);
            } else {
                table.setExpanded({});
            }
        };
        table.resetExpanded = (defaultState)=>{
            var _table$initialState$e, _table$initialState;
            table.setExpanded(defaultState ? {} : (_table$initialState$e = (_table$initialState = table.initialState) == null ? void 0 : _table$initialState.expanded) != null ? _table$initialState$e : {});
        };
        table.getCanSomeRowsExpand = ()=>{
            return table.getPrePaginationRowModel().flatRows.some((row)=>row.getCanExpand());
        };
        table.getToggleAllRowsExpandedHandler = ()=>{
            return (e)=>{
                e.persist == null || e.persist();
                table.toggleAllRowsExpanded();
            };
        };
        table.getIsSomeRowsExpanded = ()=>{
            const expanded = table.getState().expanded;
            return expanded === true || Object.values(expanded).some(Boolean);
        };
        table.getIsAllRowsExpanded = ()=>{
            const expanded = table.getState().expanded;
            // If expanded is true, save some cycles and return true
            if (typeof expanded === 'boolean') {
                return expanded === true;
            }
            if (!Object.keys(expanded).length) {
                return false;
            }
            // If any row is not expanded, return false
            if (table.getRowModel().flatRows.some((row)=>!row.getIsExpanded())) {
                return false;
            }
            // They must all be expanded :shrug:
            return true;
        };
        table.getExpandedDepth = ()=>{
            let maxDepth = 0;
            const rowIds = table.getState().expanded === true ? Object.keys(table.getRowModel().rowsById) : Object.keys(table.getState().expanded);
            rowIds.forEach((id)=>{
                const splitId = id.split('.');
                maxDepth = Math.max(maxDepth, splitId.length);
            });
            return maxDepth;
        };
        table.getPreExpandedRowModel = ()=>table.getSortedRowModel();
        table.getExpandedRowModel = ()=>{
            if (!table._getExpandedRowModel && table.options.getExpandedRowModel) {
                table._getExpandedRowModel = table.options.getExpandedRowModel(table);
            }
            if (table.options.manualExpanding || !table._getExpandedRowModel) {
                return table.getPreExpandedRowModel();
            }
            return table._getExpandedRowModel();
        };
    },
    createRow: (row, table)=>{
        row.toggleExpanded = (expanded)=>{
            table.setExpanded((old)=>{
                var _expanded;
                const exists = old === true ? true : !!(old != null && old[row.id]);
                let oldExpanded = {};
                if (old === true) {
                    Object.keys(table.getRowModel().rowsById).forEach((rowId)=>{
                        oldExpanded[rowId] = true;
                    });
                } else {
                    oldExpanded = old;
                }
                expanded = (_expanded = expanded) != null ? _expanded : !exists;
                if (!exists && expanded) {
                    return {
                        ...oldExpanded,
                        [row.id]: true
                    };
                }
                if (exists && !expanded) {
                    const { [row.id]: _, ...rest } = oldExpanded;
                    return rest;
                }
                return old;
            });
        };
        row.getIsExpanded = ()=>{
            var _table$options$getIsR;
            const expanded = table.getState().expanded;
            return !!((_table$options$getIsR = table.options.getIsRowExpanded == null ? void 0 : table.options.getIsRowExpanded(row)) != null ? _table$options$getIsR : expanded === true || (expanded == null ? void 0 : expanded[row.id]));
        };
        row.getCanExpand = ()=>{
            var _table$options$getRow, _table$options$enable, _row$subRows;
            return (_table$options$getRow = table.options.getRowCanExpand == null ? void 0 : table.options.getRowCanExpand(row)) != null ? _table$options$getRow : ((_table$options$enable = table.options.enableExpanding) != null ? _table$options$enable : true) && !!((_row$subRows = row.subRows) != null && _row$subRows.length);
        };
        row.getIsAllParentsExpanded = ()=>{
            let isFullyExpanded = true;
            let currentRow = row;
            while(isFullyExpanded && currentRow.parentId){
                currentRow = table.getRow(currentRow.parentId, true);
                isFullyExpanded = currentRow.getIsExpanded();
            }
            return isFullyExpanded;
        };
        row.getToggleExpandedHandler = ()=>{
            const canExpand = row.getCanExpand();
            return ()=>{
                if (!canExpand) return;
                row.toggleExpanded();
            };
        };
    }
};
//
const defaultPageIndex = 0;
const defaultPageSize = 10;
const getDefaultPaginationState = ()=>({
        pageIndex: defaultPageIndex,
        pageSize: defaultPageSize
    });
const RowPagination = {
    getInitialState: (state)=>{
        return {
            ...state,
            pagination: {
                ...getDefaultPaginationState(),
                ...state == null ? void 0 : state.pagination
            }
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onPaginationChange: makeStateUpdater('pagination', table)
        };
    },
    createTable: (table)=>{
        let registered = false;
        let queued = false;
        table._autoResetPageIndex = ()=>{
            var _ref, _table$options$autoRe;
            if (!registered) {
                table._queue(()=>{
                    registered = true;
                });
                return;
            }
            if ((_ref = (_table$options$autoRe = table.options.autoResetAll) != null ? _table$options$autoRe : table.options.autoResetPageIndex) != null ? _ref : !table.options.manualPagination) {
                if (queued) return;
                queued = true;
                table._queue(()=>{
                    table.resetPageIndex();
                    queued = false;
                });
            }
        };
        table.setPagination = (updater)=>{
            const safeUpdater = (old)=>{
                let newState = functionalUpdate(updater, old);
                return newState;
            };
            return table.options.onPaginationChange == null ? void 0 : table.options.onPaginationChange(safeUpdater);
        };
        table.resetPagination = (defaultState)=>{
            var _table$initialState$p;
            table.setPagination(defaultState ? getDefaultPaginationState() : (_table$initialState$p = table.initialState.pagination) != null ? _table$initialState$p : getDefaultPaginationState());
        };
        table.setPageIndex = (updater)=>{
            table.setPagination((old)=>{
                let pageIndex = functionalUpdate(updater, old.pageIndex);
                const maxPageIndex = typeof table.options.pageCount === 'undefined' || table.options.pageCount === -1 ? Number.MAX_SAFE_INTEGER : table.options.pageCount - 1;
                pageIndex = Math.max(0, Math.min(pageIndex, maxPageIndex));
                return {
                    ...old,
                    pageIndex
                };
            });
        };
        table.resetPageIndex = (defaultState)=>{
            var _table$initialState$p2, _table$initialState;
            table.setPageIndex(defaultState ? defaultPageIndex : (_table$initialState$p2 = (_table$initialState = table.initialState) == null || (_table$initialState = _table$initialState.pagination) == null ? void 0 : _table$initialState.pageIndex) != null ? _table$initialState$p2 : defaultPageIndex);
        };
        table.resetPageSize = (defaultState)=>{
            var _table$initialState$p3, _table$initialState2;
            table.setPageSize(defaultState ? defaultPageSize : (_table$initialState$p3 = (_table$initialState2 = table.initialState) == null || (_table$initialState2 = _table$initialState2.pagination) == null ? void 0 : _table$initialState2.pageSize) != null ? _table$initialState$p3 : defaultPageSize);
        };
        table.setPageSize = (updater)=>{
            table.setPagination((old)=>{
                const pageSize = Math.max(1, functionalUpdate(updater, old.pageSize));
                const topRowIndex = old.pageSize * old.pageIndex;
                const pageIndex = Math.floor(topRowIndex / pageSize);
                return {
                    ...old,
                    pageIndex,
                    pageSize
                };
            });
        };
        //deprecated
        table.setPageCount = (updater)=>table.setPagination((old)=>{
                var _table$options$pageCo;
                let newPageCount = functionalUpdate(updater, (_table$options$pageCo = table.options.pageCount) != null ? _table$options$pageCo : -1);
                if (typeof newPageCount === 'number') {
                    newPageCount = Math.max(-1, newPageCount);
                }
                return {
                    ...old,
                    pageCount: newPageCount
                };
            });
        table.getPageOptions = memo(()=>[
                table.getPageCount()
            ], (pageCount)=>{
            let pageOptions = [];
            if (pageCount && pageCount > 0) {
                pageOptions = [
                    ...new Array(pageCount)
                ].fill(null).map((_, i)=>i);
            }
            return pageOptions;
        }, getMemoOptions(table.options, 'debugTable', 'getPageOptions'));
        table.getCanPreviousPage = ()=>table.getState().pagination.pageIndex > 0;
        table.getCanNextPage = ()=>{
            const { pageIndex } = table.getState().pagination;
            const pageCount = table.getPageCount();
            if (pageCount === -1) {
                return true;
            }
            if (pageCount === 0) {
                return false;
            }
            return pageIndex < pageCount - 1;
        };
        table.previousPage = ()=>{
            return table.setPageIndex((old)=>old - 1);
        };
        table.nextPage = ()=>{
            return table.setPageIndex((old)=>{
                return old + 1;
            });
        };
        table.firstPage = ()=>{
            return table.setPageIndex(0);
        };
        table.lastPage = ()=>{
            return table.setPageIndex(table.getPageCount() - 1);
        };
        table.getPrePaginationRowModel = ()=>table.getExpandedRowModel();
        table.getPaginationRowModel = ()=>{
            if (!table._getPaginationRowModel && table.options.getPaginationRowModel) {
                table._getPaginationRowModel = table.options.getPaginationRowModel(table);
            }
            if (table.options.manualPagination || !table._getPaginationRowModel) {
                return table.getPrePaginationRowModel();
            }
            return table._getPaginationRowModel();
        };
        table.getPageCount = ()=>{
            var _table$options$pageCo2;
            return (_table$options$pageCo2 = table.options.pageCount) != null ? _table$options$pageCo2 : Math.ceil(table.getRowCount() / table.getState().pagination.pageSize);
        };
        table.getRowCount = ()=>{
            var _table$options$rowCou;
            return (_table$options$rowCou = table.options.rowCount) != null ? _table$options$rowCou : table.getPrePaginationRowModel().rows.length;
        };
    }
};
//
const getDefaultRowPinningState = ()=>({
        top: [],
        bottom: []
    });
const RowPinning = {
    getInitialState: (state)=>{
        return {
            rowPinning: getDefaultRowPinningState(),
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onRowPinningChange: makeStateUpdater('rowPinning', table)
        };
    },
    createRow: (row, table)=>{
        row.pin = (position, includeLeafRows, includeParentRows)=>{
            const leafRowIds = includeLeafRows ? row.getLeafRows().map((_ref)=>{
                let { id } = _ref;
                return id;
            }) : [];
            const parentRowIds = includeParentRows ? row.getParentRows().map((_ref2)=>{
                let { id } = _ref2;
                return id;
            }) : [];
            const rowIds = new Set([
                ...parentRowIds,
                row.id,
                ...leafRowIds
            ]);
            table.setRowPinning((old)=>{
                var _old$top3, _old$bottom3;
                if (position === 'bottom') {
                    var _old$top, _old$bottom;
                    return {
                        top: ((_old$top = old == null ? void 0 : old.top) != null ? _old$top : []).filter((d)=>!(rowIds != null && rowIds.has(d))),
                        bottom: [
                            ...((_old$bottom = old == null ? void 0 : old.bottom) != null ? _old$bottom : []).filter((d)=>!(rowIds != null && rowIds.has(d))),
                            ...Array.from(rowIds)
                        ]
                    };
                }
                if (position === 'top') {
                    var _old$top2, _old$bottom2;
                    return {
                        top: [
                            ...((_old$top2 = old == null ? void 0 : old.top) != null ? _old$top2 : []).filter((d)=>!(rowIds != null && rowIds.has(d))),
                            ...Array.from(rowIds)
                        ],
                        bottom: ((_old$bottom2 = old == null ? void 0 : old.bottom) != null ? _old$bottom2 : []).filter((d)=>!(rowIds != null && rowIds.has(d)))
                    };
                }
                return {
                    top: ((_old$top3 = old == null ? void 0 : old.top) != null ? _old$top3 : []).filter((d)=>!(rowIds != null && rowIds.has(d))),
                    bottom: ((_old$bottom3 = old == null ? void 0 : old.bottom) != null ? _old$bottom3 : []).filter((d)=>!(rowIds != null && rowIds.has(d)))
                };
            });
        };
        row.getCanPin = ()=>{
            var _ref3;
            const { enableRowPinning, enablePinning } = table.options;
            if (typeof enableRowPinning === 'function') {
                return enableRowPinning(row);
            }
            return (_ref3 = enableRowPinning != null ? enableRowPinning : enablePinning) != null ? _ref3 : true;
        };
        row.getIsPinned = ()=>{
            const rowIds = [
                row.id
            ];
            const { top, bottom } = table.getState().rowPinning;
            const isTop = rowIds.some((d)=>top == null ? void 0 : top.includes(d));
            const isBottom = rowIds.some((d)=>bottom == null ? void 0 : bottom.includes(d));
            return isTop ? 'top' : isBottom ? 'bottom' : false;
        };
        row.getPinnedIndex = ()=>{
            var _ref4, _visiblePinnedRowIds$;
            const position = row.getIsPinned();
            if (!position) return -1;
            const visiblePinnedRowIds = (_ref4 = position === 'top' ? table.getTopRows() : table.getBottomRows()) == null ? void 0 : _ref4.map((_ref5)=>{
                let { id } = _ref5;
                return id;
            });
            return (_visiblePinnedRowIds$ = visiblePinnedRowIds == null ? void 0 : visiblePinnedRowIds.indexOf(row.id)) != null ? _visiblePinnedRowIds$ : -1;
        };
    },
    createTable: (table)=>{
        table.setRowPinning = (updater)=>table.options.onRowPinningChange == null ? void 0 : table.options.onRowPinningChange(updater);
        table.resetRowPinning = (defaultState)=>{
            var _table$initialState$r, _table$initialState;
            return table.setRowPinning(defaultState ? getDefaultRowPinningState() : (_table$initialState$r = (_table$initialState = table.initialState) == null ? void 0 : _table$initialState.rowPinning) != null ? _table$initialState$r : getDefaultRowPinningState());
        };
        table.getIsSomeRowsPinned = (position)=>{
            var _pinningState$positio;
            const pinningState = table.getState().rowPinning;
            if (!position) {
                var _pinningState$top, _pinningState$bottom;
                return Boolean(((_pinningState$top = pinningState.top) == null ? void 0 : _pinningState$top.length) || ((_pinningState$bottom = pinningState.bottom) == null ? void 0 : _pinningState$bottom.length));
            }
            return Boolean((_pinningState$positio = pinningState[position]) == null ? void 0 : _pinningState$positio.length);
        };
        table._getPinnedRows = (visibleRows, pinnedRowIds, position)=>{
            var _table$options$keepPi;
            const rows = ((_table$options$keepPi = table.options.keepPinnedRows) != null ? _table$options$keepPi : true) ? //get all rows that are pinned even if they would not be otherwise visible
            //account for expanded parent rows, but not pagination or filtering
            (pinnedRowIds != null ? pinnedRowIds : []).map((rowId)=>{
                const row = table.getRow(rowId, true);
                return row.getIsAllParentsExpanded() ? row : null;
            }) : //else get only visible rows that are pinned
            (pinnedRowIds != null ? pinnedRowIds : []).map((rowId)=>visibleRows.find((row)=>row.id === rowId));
            return rows.filter(Boolean).map((d)=>({
                    ...d,
                    position
                }));
        };
        table.getTopRows = memo(()=>[
                table.getRowModel().rows,
                table.getState().rowPinning.top
            ], (allRows, topPinnedRowIds)=>table._getPinnedRows(allRows, topPinnedRowIds, 'top'), getMemoOptions(table.options, 'debugRows', 'getTopRows'));
        table.getBottomRows = memo(()=>[
                table.getRowModel().rows,
                table.getState().rowPinning.bottom
            ], (allRows, bottomPinnedRowIds)=>table._getPinnedRows(allRows, bottomPinnedRowIds, 'bottom'), getMemoOptions(table.options, 'debugRows', 'getBottomRows'));
        table.getCenterRows = memo(()=>[
                table.getRowModel().rows,
                table.getState().rowPinning.top,
                table.getState().rowPinning.bottom
            ], (allRows, top, bottom)=>{
            const topAndBottom = new Set([
                ...top != null ? top : [],
                ...bottom != null ? bottom : []
            ]);
            return allRows.filter((d)=>!topAndBottom.has(d.id));
        }, getMemoOptions(table.options, 'debugRows', 'getCenterRows'));
    }
};
//
const RowSelection = {
    getInitialState: (state)=>{
        return {
            rowSelection: {},
            ...state
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onRowSelectionChange: makeStateUpdater('rowSelection', table),
            enableRowSelection: true,
            enableMultiRowSelection: true,
            enableSubRowSelection: true
        };
    },
    createTable: (table)=>{
        table.setRowSelection = (updater)=>table.options.onRowSelectionChange == null ? void 0 : table.options.onRowSelectionChange(updater);
        table.resetRowSelection = (defaultState)=>{
            var _table$initialState$r;
            return table.setRowSelection(defaultState ? {} : (_table$initialState$r = table.initialState.rowSelection) != null ? _table$initialState$r : {});
        };
        table.toggleAllRowsSelected = (value)=>{
            table.setRowSelection((old)=>{
                value = typeof value !== 'undefined' ? value : !table.getIsAllRowsSelected();
                const rowSelection = {
                    ...old
                };
                const preGroupedFlatRows = table.getPreGroupedRowModel().flatRows;
                // We don't use `mutateRowIsSelected` here for performance reasons.
                // All of the rows are flat already, so it wouldn't be worth it
                if (value) {
                    preGroupedFlatRows.forEach((row)=>{
                        if (!row.getCanSelect()) {
                            return;
                        }
                        rowSelection[row.id] = true;
                    });
                } else {
                    preGroupedFlatRows.forEach((row)=>{
                        delete rowSelection[row.id];
                    });
                }
                return rowSelection;
            });
        };
        table.toggleAllPageRowsSelected = (value)=>table.setRowSelection((old)=>{
                const resolvedValue = typeof value !== 'undefined' ? value : !table.getIsAllPageRowsSelected();
                const rowSelection = {
                    ...old
                };
                table.getRowModel().rows.forEach((row)=>{
                    mutateRowIsSelected(rowSelection, row.id, resolvedValue, true, table);
                });
                return rowSelection;
            });
        // addRowSelectionRange: rowId => {
        //   const {
        //     rows,
        //     rowsById,
        //     options: { selectGroupingRows, selectSubRows },
        //   } = table
        //   const findSelectedRow = (rows: Row[]) => {
        //     let found
        //     rows.find(d => {
        //       if (d.getIsSelected()) {
        //         found = d
        //         return true
        //       }
        //       const subFound = findSelectedRow(d.subRows || [])
        //       if (subFound) {
        //         found = subFound
        //         return true
        //       }
        //       return false
        //     })
        //     return found
        //   }
        //   const firstRow = findSelectedRow(rows) || rows[0]
        //   const lastRow = rowsById[rowId]
        //   let include = false
        //   const selectedRowIds = {}
        //   const addRow = (row: Row) => {
        //     mutateRowIsSelected(selectedRowIds, row.id, true, {
        //       rowsById,
        //       selectGroupingRows: selectGroupingRows!,
        //       selectSubRows: selectSubRows!,
        //     })
        //   }
        //   table.rows.forEach(row => {
        //     const isFirstRow = row.id === firstRow.id
        //     const isLastRow = row.id === lastRow.id
        //     if (isFirstRow || isLastRow) {
        //       if (!include) {
        //         include = true
        //       } else if (include) {
        //         addRow(row)
        //         include = false
        //       }
        //     }
        //     if (include) {
        //       addRow(row)
        //     }
        //   })
        //   table.setRowSelection(selectedRowIds)
        // },
        table.getPreSelectedRowModel = ()=>table.getCoreRowModel();
        table.getSelectedRowModel = memo(()=>[
                table.getState().rowSelection,
                table.getCoreRowModel()
            ], (rowSelection, rowModel)=>{
            if (!Object.keys(rowSelection).length) {
                return {
                    rows: [],
                    flatRows: [],
                    rowsById: {}
                };
            }
            return selectRowsFn(table, rowModel);
        }, getMemoOptions(table.options, 'debugTable', 'getSelectedRowModel'));
        table.getFilteredSelectedRowModel = memo(()=>[
                table.getState().rowSelection,
                table.getFilteredRowModel()
            ], (rowSelection, rowModel)=>{
            if (!Object.keys(rowSelection).length) {
                return {
                    rows: [],
                    flatRows: [],
                    rowsById: {}
                };
            }
            return selectRowsFn(table, rowModel);
        }, getMemoOptions(table.options, 'debugTable', 'getFilteredSelectedRowModel'));
        table.getGroupedSelectedRowModel = memo(()=>[
                table.getState().rowSelection,
                table.getSortedRowModel()
            ], (rowSelection, rowModel)=>{
            if (!Object.keys(rowSelection).length) {
                return {
                    rows: [],
                    flatRows: [],
                    rowsById: {}
                };
            }
            return selectRowsFn(table, rowModel);
        }, getMemoOptions(table.options, 'debugTable', 'getGroupedSelectedRowModel'));
        ///
        // getGroupingRowCanSelect: rowId => {
        //   const row = table.getRow(rowId)
        //   if (!row) {
        //     throw new Error()
        //   }
        //   if (typeof table.options.enableGroupingRowSelection === 'function') {
        //     return table.options.enableGroupingRowSelection(row)
        //   }
        //   return table.options.enableGroupingRowSelection ?? false
        // },
        table.getIsAllRowsSelected = ()=>{
            const preGroupedFlatRows = table.getFilteredRowModel().flatRows;
            const { rowSelection } = table.getState();
            let isAllRowsSelected = Boolean(preGroupedFlatRows.length && Object.keys(rowSelection).length);
            if (isAllRowsSelected) {
                if (preGroupedFlatRows.some((row)=>row.getCanSelect() && !rowSelection[row.id])) {
                    isAllRowsSelected = false;
                }
            }
            return isAllRowsSelected;
        };
        table.getIsAllPageRowsSelected = ()=>{
            const paginationFlatRows = table.getPaginationRowModel().flatRows.filter((row)=>row.getCanSelect());
            const { rowSelection } = table.getState();
            let isAllPageRowsSelected = !!paginationFlatRows.length;
            if (isAllPageRowsSelected && paginationFlatRows.some((row)=>!rowSelection[row.id])) {
                isAllPageRowsSelected = false;
            }
            return isAllPageRowsSelected;
        };
        table.getIsSomeRowsSelected = ()=>{
            var _table$getState$rowSe;
            const totalSelected = Object.keys((_table$getState$rowSe = table.getState().rowSelection) != null ? _table$getState$rowSe : {}).length;
            return totalSelected > 0 && totalSelected < table.getFilteredRowModel().flatRows.length;
        };
        table.getIsSomePageRowsSelected = ()=>{
            const paginationFlatRows = table.getPaginationRowModel().flatRows;
            return table.getIsAllPageRowsSelected() ? false : paginationFlatRows.filter((row)=>row.getCanSelect()).some((d)=>d.getIsSelected() || d.getIsSomeSelected());
        };
        table.getToggleAllRowsSelectedHandler = ()=>{
            return (e)=>{
                table.toggleAllRowsSelected(e.target.checked);
            };
        };
        table.getToggleAllPageRowsSelectedHandler = ()=>{
            return (e)=>{
                table.toggleAllPageRowsSelected(e.target.checked);
            };
        };
    },
    createRow: (row, table)=>{
        row.toggleSelected = (value, opts)=>{
            const isSelected = row.getIsSelected();
            table.setRowSelection((old)=>{
                var _opts$selectChildren;
                value = typeof value !== 'undefined' ? value : !isSelected;
                if (row.getCanSelect() && isSelected === value) {
                    return old;
                }
                const selectedRowIds = {
                    ...old
                };
                mutateRowIsSelected(selectedRowIds, row.id, value, (_opts$selectChildren = opts == null ? void 0 : opts.selectChildren) != null ? _opts$selectChildren : true, table);
                return selectedRowIds;
            });
        };
        row.getIsSelected = ()=>{
            const { rowSelection } = table.getState();
            return isRowSelected(row, rowSelection);
        };
        row.getIsSomeSelected = ()=>{
            const { rowSelection } = table.getState();
            return isSubRowSelected(row, rowSelection) === 'some';
        };
        row.getIsAllSubRowsSelected = ()=>{
            const { rowSelection } = table.getState();
            return isSubRowSelected(row, rowSelection) === 'all';
        };
        row.getCanSelect = ()=>{
            var _table$options$enable;
            if (typeof table.options.enableRowSelection === 'function') {
                return table.options.enableRowSelection(row);
            }
            return (_table$options$enable = table.options.enableRowSelection) != null ? _table$options$enable : true;
        };
        row.getCanSelectSubRows = ()=>{
            var _table$options$enable2;
            if (typeof table.options.enableSubRowSelection === 'function') {
                return table.options.enableSubRowSelection(row);
            }
            return (_table$options$enable2 = table.options.enableSubRowSelection) != null ? _table$options$enable2 : true;
        };
        row.getCanMultiSelect = ()=>{
            var _table$options$enable3;
            if (typeof table.options.enableMultiRowSelection === 'function') {
                return table.options.enableMultiRowSelection(row);
            }
            return (_table$options$enable3 = table.options.enableMultiRowSelection) != null ? _table$options$enable3 : true;
        };
        row.getToggleSelectedHandler = ()=>{
            const canSelect = row.getCanSelect();
            return (e)=>{
                var _target;
                if (!canSelect) return;
                row.toggleSelected((_target = e.target) == null ? void 0 : _target.checked);
            };
        };
    }
};
const mutateRowIsSelected = (selectedRowIds, id, value, includeChildren, table)=>{
    var _row$subRows;
    const row = table.getRow(id, true);
    // const isGrouped = row.getIsGrouped()
    // if ( // TODO: enforce grouping row selection rules
    //   !isGrouped ||
    //   (isGrouped && table.options.enableGroupingRowSelection)
    // ) {
    if (value) {
        if (!row.getCanMultiSelect()) {
            Object.keys(selectedRowIds).forEach((key)=>delete selectedRowIds[key]);
        }
        if (row.getCanSelect()) {
            selectedRowIds[id] = true;
        }
    } else {
        delete selectedRowIds[id];
    }
    // }
    if (includeChildren && (_row$subRows = row.subRows) != null && _row$subRows.length && row.getCanSelectSubRows()) {
        row.subRows.forEach((row)=>mutateRowIsSelected(selectedRowIds, row.id, value, includeChildren, table));
    }
};
function selectRowsFn(table, rowModel) {
    const rowSelection = table.getState().rowSelection;
    const newSelectedFlatRows = [];
    const newSelectedRowsById = {};
    // Filters top level and nested rows
    const recurseRows = function(rows, depth) {
        return rows.map((row)=>{
            var _row$subRows2;
            const isSelected = isRowSelected(row, rowSelection);
            if (isSelected) {
                newSelectedFlatRows.push(row);
                newSelectedRowsById[row.id] = row;
            }
            if ((_row$subRows2 = row.subRows) != null && _row$subRows2.length) {
                row = {
                    ...row,
                    subRows: recurseRows(row.subRows)
                };
            }
            if (isSelected) {
                return row;
            }
        }).filter(Boolean);
    };
    return {
        rows: recurseRows(rowModel.rows),
        flatRows: newSelectedFlatRows,
        rowsById: newSelectedRowsById
    };
}
function isRowSelected(row, selection) {
    var _selection$row$id;
    return (_selection$row$id = selection[row.id]) != null ? _selection$row$id : false;
}
function isSubRowSelected(row, selection, table) {
    var _row$subRows3;
    if (!((_row$subRows3 = row.subRows) != null && _row$subRows3.length)) return false;
    let allChildrenSelected = true;
    let someSelected = false;
    row.subRows.forEach((subRow)=>{
        // Bail out early if we know both of these
        if (someSelected && !allChildrenSelected) {
            return;
        }
        if (subRow.getCanSelect()) {
            if (isRowSelected(subRow, selection)) {
                someSelected = true;
            } else {
                allChildrenSelected = false;
            }
        }
        // Check row selection of nested subrows
        if (subRow.subRows && subRow.subRows.length) {
            const subRowChildrenSelected = isSubRowSelected(subRow, selection);
            if (subRowChildrenSelected === 'all') {
                someSelected = true;
            } else if (subRowChildrenSelected === 'some') {
                someSelected = true;
                allChildrenSelected = false;
            } else {
                allChildrenSelected = false;
            }
        }
    });
    return allChildrenSelected ? 'all' : someSelected ? 'some' : false;
}
const reSplitAlphaNumeric = /([0-9]+)/gm;
const alphanumeric = (rowA, rowB, columnId)=>{
    return compareAlphanumeric(toString(rowA.getValue(columnId)).toLowerCase(), toString(rowB.getValue(columnId)).toLowerCase());
};
const alphanumericCaseSensitive = (rowA, rowB, columnId)=>{
    return compareAlphanumeric(toString(rowA.getValue(columnId)), toString(rowB.getValue(columnId)));
};
// The text filter is more basic (less numeric support)
// but is much faster
const text = (rowA, rowB, columnId)=>{
    return compareBasic(toString(rowA.getValue(columnId)).toLowerCase(), toString(rowB.getValue(columnId)).toLowerCase());
};
// The text filter is more basic (less numeric support)
// but is much faster
const textCaseSensitive = (rowA, rowB, columnId)=>{
    return compareBasic(toString(rowA.getValue(columnId)), toString(rowB.getValue(columnId)));
};
const datetime = (rowA, rowB, columnId)=>{
    const a = rowA.getValue(columnId);
    const b = rowB.getValue(columnId);
    // Can handle nullish values
    // Use > and < because == (and ===) doesn't work with
    // Date objects (would require calling getTime()).
    return a > b ? 1 : a < b ? -1 : 0;
};
const basic = (rowA, rowB, columnId)=>{
    return compareBasic(rowA.getValue(columnId), rowB.getValue(columnId));
};
// Utils
function compareBasic(a, b) {
    return a === b ? 0 : a > b ? 1 : -1;
}
function toString(a) {
    if (typeof a === 'number') {
        if (isNaN(a) || a === Infinity || a === -Infinity) {
            return '';
        }
        return String(a);
    }
    if (typeof a === 'string') {
        return a;
    }
    return '';
}
// Mixed sorting is slow, but very inclusive of many edge cases.
// It handles numbers, mixed alphanumeric combinations, and even
// null, undefined, and Infinity
function compareAlphanumeric(aStr, bStr) {
    // Split on number groups, but keep the delimiter
    // Then remove falsey split values
    const a = aStr.split(reSplitAlphaNumeric).filter(Boolean);
    const b = bStr.split(reSplitAlphaNumeric).filter(Boolean);
    // While
    while(a.length && b.length){
        const aa = a.shift();
        const bb = b.shift();
        const an = parseInt(aa, 10);
        const bn = parseInt(bb, 10);
        const combo = [
            an,
            bn
        ].sort();
        // Both are string
        if (isNaN(combo[0])) {
            if (aa > bb) {
                return 1;
            }
            if (bb > aa) {
                return -1;
            }
            continue;
        }
        // One is a string, one is a number
        if (isNaN(combo[1])) {
            return isNaN(an) ? -1 : 1;
        }
        // Both are numbers
        if (an > bn) {
            return 1;
        }
        if (bn > an) {
            return -1;
        }
    }
    return a.length - b.length;
}
// Exports
const sortingFns = {
    alphanumeric,
    alphanumericCaseSensitive,
    text,
    textCaseSensitive,
    datetime,
    basic
};
//
const RowSorting = {
    getInitialState: (state)=>{
        return {
            sorting: [],
            ...state
        };
    },
    getDefaultColumnDef: ()=>{
        return {
            sortingFn: 'auto',
            sortUndefined: 1
        };
    },
    getDefaultOptions: (table)=>{
        return {
            onSortingChange: makeStateUpdater('sorting', table),
            isMultiSortEvent: (e)=>{
                return e.shiftKey;
            }
        };
    },
    createColumn: (column, table)=>{
        column.getAutoSortingFn = ()=>{
            const firstRows = table.getFilteredRowModel().flatRows.slice(10);
            let isString = false;
            for (const row of firstRows){
                const value = row == null ? void 0 : row.getValue(column.id);
                if (Object.prototype.toString.call(value) === '[object Date]') {
                    return sortingFns.datetime;
                }
                if (typeof value === 'string') {
                    isString = true;
                    if (value.split(reSplitAlphaNumeric).length > 1) {
                        return sortingFns.alphanumeric;
                    }
                }
            }
            if (isString) {
                return sortingFns.text;
            }
            return sortingFns.basic;
        };
        column.getAutoSortDir = ()=>{
            const firstRow = table.getFilteredRowModel().flatRows[0];
            const value = firstRow == null ? void 0 : firstRow.getValue(column.id);
            if (typeof value === 'string') {
                return 'asc';
            }
            return 'desc';
        };
        column.getSortingFn = ()=>{
            var _table$options$sortin, _table$options$sortin2;
            if (!column) {
                throw new Error();
            }
            return isFunction(column.columnDef.sortingFn) ? column.columnDef.sortingFn : column.columnDef.sortingFn === 'auto' ? column.getAutoSortingFn() : (_table$options$sortin = (_table$options$sortin2 = table.options.sortingFns) == null ? void 0 : _table$options$sortin2[column.columnDef.sortingFn]) != null ? _table$options$sortin : sortingFns[column.columnDef.sortingFn];
        };
        column.toggleSorting = (desc, multi)=>{
            // if (column.columns.length) {
            //   column.columns.forEach((c, i) => {
            //     if (c.id) {
            //       table.toggleColumnSorting(c.id, undefined, multi || !!i)
            //     }
            //   })
            //   return
            // }
            // this needs to be outside of table.setSorting to be in sync with rerender
            const nextSortingOrder = column.getNextSortingOrder();
            const hasManualValue = typeof desc !== 'undefined' && desc !== null;
            table.setSorting((old)=>{
                // Find any existing sorting for this column
                const existingSorting = old == null ? void 0 : old.find((d)=>d.id === column.id);
                const existingIndex = old == null ? void 0 : old.findIndex((d)=>d.id === column.id);
                let newSorting = [];
                // What should we do with this sort action?
                let sortAction;
                let nextDesc = hasManualValue ? desc : nextSortingOrder === 'desc';
                // Multi-mode
                if (old != null && old.length && column.getCanMultiSort() && multi) {
                    if (existingSorting) {
                        sortAction = 'toggle';
                    } else {
                        sortAction = 'add';
                    }
                } else {
                    // Normal mode
                    if (old != null && old.length && existingIndex !== old.length - 1) {
                        sortAction = 'replace';
                    } else if (existingSorting) {
                        sortAction = 'toggle';
                    } else {
                        sortAction = 'replace';
                    }
                }
                // Handle toggle states that will remove the sorting
                if (sortAction === 'toggle') {
                    // If we are "actually" toggling (not a manual set value), should we remove the sorting?
                    if (!hasManualValue) {
                        // Is our intention to remove?
                        if (!nextSortingOrder) {
                            sortAction = 'remove';
                        }
                    }
                }
                if (sortAction === 'add') {
                    var _table$options$maxMul;
                    newSorting = [
                        ...old,
                        {
                            id: column.id,
                            desc: nextDesc
                        }
                    ];
                    // Take latest n columns
                    newSorting.splice(0, newSorting.length - ((_table$options$maxMul = table.options.maxMultiSortColCount) != null ? _table$options$maxMul : Number.MAX_SAFE_INTEGER));
                } else if (sortAction === 'toggle') {
                    // This flips (or sets) the
                    newSorting = old.map((d)=>{
                        if (d.id === column.id) {
                            return {
                                ...d,
                                desc: nextDesc
                            };
                        }
                        return d;
                    });
                } else if (sortAction === 'remove') {
                    newSorting = old.filter((d)=>d.id !== column.id);
                } else {
                    newSorting = [
                        {
                            id: column.id,
                            desc: nextDesc
                        }
                    ];
                }
                return newSorting;
            });
        };
        column.getFirstSortDir = ()=>{
            var _ref, _column$columnDef$sor;
            const sortDescFirst = (_ref = (_column$columnDef$sor = column.columnDef.sortDescFirst) != null ? _column$columnDef$sor : table.options.sortDescFirst) != null ? _ref : column.getAutoSortDir() === 'desc';
            return sortDescFirst ? 'desc' : 'asc';
        };
        column.getNextSortingOrder = (multi)=>{
            var _table$options$enable, _table$options$enable2;
            const firstSortDirection = column.getFirstSortDir();
            const isSorted = column.getIsSorted();
            if (!isSorted) {
                return firstSortDirection;
            }
            if (isSorted !== firstSortDirection && ((_table$options$enable = table.options.enableSortingRemoval) != null ? _table$options$enable : true) && (// If enableSortRemove, enable in general
            multi ? (_table$options$enable2 = table.options.enableMultiRemove) != null ? _table$options$enable2 : true : true) // If multi, don't allow if enableMultiRemove))
            ) {
                return false;
            }
            return isSorted === 'desc' ? 'asc' : 'desc';
        };
        column.getCanSort = ()=>{
            var _column$columnDef$ena, _table$options$enable3;
            return ((_column$columnDef$ena = column.columnDef.enableSorting) != null ? _column$columnDef$ena : true) && ((_table$options$enable3 = table.options.enableSorting) != null ? _table$options$enable3 : true) && !!column.accessorFn;
        };
        column.getCanMultiSort = ()=>{
            var _ref2, _column$columnDef$ena2;
            return (_ref2 = (_column$columnDef$ena2 = column.columnDef.enableMultiSort) != null ? _column$columnDef$ena2 : table.options.enableMultiSort) != null ? _ref2 : !!column.accessorFn;
        };
        column.getIsSorted = ()=>{
            var _table$getState$sorti;
            const columnSort = (_table$getState$sorti = table.getState().sorting) == null ? void 0 : _table$getState$sorti.find((d)=>d.id === column.id);
            return !columnSort ? false : columnSort.desc ? 'desc' : 'asc';
        };
        column.getSortIndex = ()=>{
            var _table$getState$sorti2, _table$getState$sorti3;
            return (_table$getState$sorti2 = (_table$getState$sorti3 = table.getState().sorting) == null ? void 0 : _table$getState$sorti3.findIndex((d)=>d.id === column.id)) != null ? _table$getState$sorti2 : -1;
        };
        column.clearSorting = ()=>{
            //clear sorting for just 1 column
            table.setSorting((old)=>old != null && old.length ? old.filter((d)=>d.id !== column.id) : []);
        };
        column.getToggleSortingHandler = ()=>{
            const canSort = column.getCanSort();
            return (e)=>{
                if (!canSort) return;
                e.persist == null || e.persist();
                column.toggleSorting == null || column.toggleSorting(undefined, column.getCanMultiSort() ? table.options.isMultiSortEvent == null ? void 0 : table.options.isMultiSortEvent(e) : false);
            };
        };
    },
    createTable: (table)=>{
        table.setSorting = (updater)=>table.options.onSortingChange == null ? void 0 : table.options.onSortingChange(updater);
        table.resetSorting = (defaultState)=>{
            var _table$initialState$s, _table$initialState;
            table.setSorting(defaultState ? [] : (_table$initialState$s = (_table$initialState = table.initialState) == null ? void 0 : _table$initialState.sorting) != null ? _table$initialState$s : []);
        };
        table.getPreSortedRowModel = ()=>table.getGroupedRowModel();
        table.getSortedRowModel = ()=>{
            if (!table._getSortedRowModel && table.options.getSortedRowModel) {
                table._getSortedRowModel = table.options.getSortedRowModel(table);
            }
            if (table.options.manualSorting || !table._getSortedRowModel) {
                return table.getPreSortedRowModel();
            }
            return table._getSortedRowModel();
        };
    }
};
const builtInFeatures = [
    Headers,
    ColumnVisibility,
    ColumnOrdering,
    ColumnPinning,
    ColumnFaceting,
    ColumnFiltering,
    GlobalFaceting,
    //depends on ColumnFaceting
    GlobalFiltering,
    //depends on ColumnFiltering
    RowSorting,
    ColumnGrouping,
    //depends on RowSorting
    RowExpanding,
    RowPagination,
    RowPinning,
    RowSelection,
    ColumnSizing
];
//
function createTable(options) {
    var _options$_features, _options$initialState;
    if (("TURBOPACK compile-time value", "development") !== 'production' && (options.debugAll || options.debugTable)) {
        console.info('Creating Table Instance...');
    }
    const _features = [
        ...builtInFeatures,
        ...(_options$_features = options._features) != null ? _options$_features : []
    ];
    let table = {
        _features
    };
    const defaultOptions = table._features.reduce((obj, feature)=>{
        return Object.assign(obj, feature.getDefaultOptions == null ? void 0 : feature.getDefaultOptions(table));
    }, {});
    const mergeOptions = (options)=>{
        if (table.options.mergeOptions) {
            return table.options.mergeOptions(defaultOptions, options);
        }
        return {
            ...defaultOptions,
            ...options
        };
    };
    const coreInitialState = {};
    let initialState = {
        ...coreInitialState,
        ...(_options$initialState = options.initialState) != null ? _options$initialState : {}
    };
    table._features.forEach((feature)=>{
        var _feature$getInitialSt;
        initialState = (_feature$getInitialSt = feature.getInitialState == null ? void 0 : feature.getInitialState(initialState)) != null ? _feature$getInitialSt : initialState;
    });
    const queued = [];
    let queuedTimeout = false;
    const coreInstance = {
        _features,
        options: {
            ...defaultOptions,
            ...options
        },
        initialState,
        _queue: (cb)=>{
            queued.push(cb);
            if (!queuedTimeout) {
                queuedTimeout = true;
                // Schedule a microtask to run the queued callbacks after
                // the current call stack (render, etc) has finished.
                Promise.resolve().then(()=>{
                    while(queued.length){
                        queued.shift()();
                    }
                    queuedTimeout = false;
                }).catch((error)=>setTimeout(()=>{
                        throw error;
                    }));
            }
        },
        reset: ()=>{
            table.setState(table.initialState);
        },
        setOptions: (updater)=>{
            const newOptions = functionalUpdate(updater, table.options);
            table.options = mergeOptions(newOptions);
        },
        getState: ()=>{
            return table.options.state;
        },
        setState: (updater)=>{
            table.options.onStateChange == null || table.options.onStateChange(updater);
        },
        _getRowId: (row, index, parent)=>{
            var _table$options$getRow;
            return (_table$options$getRow = table.options.getRowId == null ? void 0 : table.options.getRowId(row, index, parent)) != null ? _table$options$getRow : `${parent ? [
                parent.id,
                index
            ].join('.') : index}`;
        },
        getCoreRowModel: ()=>{
            if (!table._getCoreRowModel) {
                table._getCoreRowModel = table.options.getCoreRowModel(table);
            }
            return table._getCoreRowModel();
        },
        // The final calls start at the bottom of the model,
        // expanded rows, which then work their way up
        getRowModel: ()=>{
            return table.getPaginationRowModel();
        },
        //in next version, we should just pass in the row model as the optional 2nd arg
        getRow: (id, searchAll)=>{
            let row = (searchAll ? table.getPrePaginationRowModel() : table.getRowModel()).rowsById[id];
            if (!row) {
                row = table.getCoreRowModel().rowsById[id];
                if (!row) {
                    if ("TURBOPACK compile-time truthy", 1) {
                        throw new Error(`getRow could not find row with ID: ${id}`);
                    }
                    throw new Error();
                }
            }
            return row;
        },
        _getDefaultColumnDef: memo(()=>[
                table.options.defaultColumn
            ], (defaultColumn)=>{
            var _defaultColumn;
            defaultColumn = (_defaultColumn = defaultColumn) != null ? _defaultColumn : {};
            return {
                header: (props)=>{
                    const resolvedColumnDef = props.header.column.columnDef;
                    if (resolvedColumnDef.accessorKey) {
                        return resolvedColumnDef.accessorKey;
                    }
                    if (resolvedColumnDef.accessorFn) {
                        return resolvedColumnDef.id;
                    }
                    return null;
                },
                // footer: props => props.header.column.id,
                cell: (props)=>{
                    var _props$renderValue$to, _props$renderValue;
                    return (_props$renderValue$to = (_props$renderValue = props.renderValue()) == null || _props$renderValue.toString == null ? void 0 : _props$renderValue.toString()) != null ? _props$renderValue$to : null;
                },
                ...table._features.reduce((obj, feature)=>{
                    return Object.assign(obj, feature.getDefaultColumnDef == null ? void 0 : feature.getDefaultColumnDef());
                }, {}),
                ...defaultColumn
            };
        }, getMemoOptions(options, 'debugColumns', '_getDefaultColumnDef')),
        _getColumnDefs: ()=>table.options.columns,
        getAllColumns: memo(()=>[
                table._getColumnDefs()
            ], (columnDefs)=>{
            const recurseColumns = function(columnDefs, parent, depth) {
                if (depth === void 0) {
                    depth = 0;
                }
                return columnDefs.map((columnDef)=>{
                    const column = createColumn(table, columnDef, depth, parent);
                    const groupingColumnDef = columnDef;
                    column.columns = groupingColumnDef.columns ? recurseColumns(groupingColumnDef.columns, column, depth + 1) : [];
                    return column;
                });
            };
            return recurseColumns(columnDefs);
        }, getMemoOptions(options, 'debugColumns', 'getAllColumns')),
        getAllFlatColumns: memo(()=>[
                table.getAllColumns()
            ], (allColumns)=>{
            return allColumns.flatMap((column)=>{
                return column.getFlatColumns();
            });
        }, getMemoOptions(options, 'debugColumns', 'getAllFlatColumns')),
        _getAllFlatColumnsById: memo(()=>[
                table.getAllFlatColumns()
            ], (flatColumns)=>{
            return flatColumns.reduce((acc, column)=>{
                acc[column.id] = column;
                return acc;
            }, {});
        }, getMemoOptions(options, 'debugColumns', 'getAllFlatColumnsById')),
        getAllLeafColumns: memo(()=>[
                table.getAllColumns(),
                table._getOrderColumnsFn()
            ], (allColumns, orderColumns)=>{
            let leafColumns = allColumns.flatMap((column)=>column.getLeafColumns());
            return orderColumns(leafColumns);
        }, getMemoOptions(options, 'debugColumns', 'getAllLeafColumns')),
        getColumn: (columnId)=>{
            const column = table._getAllFlatColumnsById()[columnId];
            if (("TURBOPACK compile-time value", "development") !== 'production' && !column) {
                console.error(`[Table] Column with id '${columnId}' does not exist.`);
            }
            return column;
        }
    };
    Object.assign(table, coreInstance);
    for(let index = 0; index < table._features.length; index++){
        const feature = table._features[index];
        feature == null || feature.createTable == null || feature.createTable(table);
    }
    return table;
}
function getCoreRowModel() {
    return (table)=>memo(()=>[
                table.options.data
            ], (data)=>{
            const rowModel = {
                rows: [],
                flatRows: [],
                rowsById: {}
            };
            const accessRows = function(originalRows, depth, parentRow) {
                if (depth === void 0) {
                    depth = 0;
                }
                const rows = [];
                for(let i = 0; i < originalRows.length; i++){
                    // This could be an expensive check at scale, so we should move it somewhere else, but where?
                    // if (!id) {
                    //   if (process.env.NODE_ENV !== 'production') {
                    //     throw new Error(`getRowId expected an ID, but got ${id}`)
                    //   }
                    // }
                    // Make the row
                    const row = createRow(table, table._getRowId(originalRows[i], i, parentRow), originalRows[i], i, depth, undefined, parentRow == null ? void 0 : parentRow.id);
                    // Keep track of every row in a flat array
                    rowModel.flatRows.push(row);
                    // Also keep track of every row by its ID
                    rowModel.rowsById[row.id] = row;
                    // Push table row into parent
                    rows.push(row);
                    // Get the original subrows
                    if (table.options.getSubRows) {
                        var _row$originalSubRows;
                        row.originalSubRows = table.options.getSubRows(originalRows[i], i);
                        // Then recursively access them
                        if ((_row$originalSubRows = row.originalSubRows) != null && _row$originalSubRows.length) {
                            row.subRows = accessRows(row.originalSubRows, depth + 1, row);
                        }
                    }
                }
                return rows;
            };
            rowModel.rows = accessRows(data);
            return rowModel;
        }, getMemoOptions(table.options, 'debugTable', 'getRowModel', ()=>table._autoResetPageIndex()));
}
function getExpandedRowModel() {
    return (table)=>memo(()=>[
                table.getState().expanded,
                table.getPreExpandedRowModel(),
                table.options.paginateExpandedRows
            ], (expanded, rowModel, paginateExpandedRows)=>{
            if (!rowModel.rows.length || expanded !== true && !Object.keys(expanded != null ? expanded : {}).length) {
                return rowModel;
            }
            if (!paginateExpandedRows) {
                // Only expand rows at this point if they are being paginated
                return rowModel;
            }
            return expandRows(rowModel);
        }, getMemoOptions(table.options, 'debugTable', 'getExpandedRowModel'));
}
function expandRows(rowModel) {
    const expandedRows = [];
    const handleRow = (row)=>{
        var _row$subRows;
        expandedRows.push(row);
        if ((_row$subRows = row.subRows) != null && _row$subRows.length && row.getIsExpanded()) {
            row.subRows.forEach(handleRow);
        }
    };
    rowModel.rows.forEach(handleRow);
    return {
        rows: expandedRows,
        flatRows: rowModel.flatRows,
        rowsById: rowModel.rowsById
    };
}
function getFacetedMinMaxValues() {
    return (table, columnId)=>memo(()=>{
            var _table$getColumn;
            return [
                (_table$getColumn = table.getColumn(columnId)) == null ? void 0 : _table$getColumn.getFacetedRowModel()
            ];
        }, (facetedRowModel)=>{
            if (!facetedRowModel) return undefined;
            const uniqueValues = facetedRowModel.flatRows.flatMap((flatRow)=>{
                var _flatRow$getUniqueVal;
                return (_flatRow$getUniqueVal = flatRow.getUniqueValues(columnId)) != null ? _flatRow$getUniqueVal : [];
            }).map(Number).filter((value)=>!Number.isNaN(value));
            if (!uniqueValues.length) return;
            let facetedMinValue = uniqueValues[0];
            let facetedMaxValue = uniqueValues[uniqueValues.length - 1];
            for (const value of uniqueValues){
                if (value < facetedMinValue) facetedMinValue = value;
                else if (value > facetedMaxValue) facetedMaxValue = value;
            }
            return [
                facetedMinValue,
                facetedMaxValue
            ];
        }, getMemoOptions(table.options, 'debugTable', 'getFacetedMinMaxValues'));
}
function filterRows(rows, filterRowImpl, table) {
    if (table.options.filterFromLeafRows) {
        return filterRowModelFromLeafs(rows, filterRowImpl, table);
    }
    return filterRowModelFromRoot(rows, filterRowImpl, table);
}
function filterRowModelFromLeafs(rowsToFilter, filterRow, table) {
    var _table$options$maxLea;
    const newFilteredFlatRows = [];
    const newFilteredRowsById = {};
    const maxDepth = (_table$options$maxLea = table.options.maxLeafRowFilterDepth) != null ? _table$options$maxLea : 100;
    const recurseFilterRows = function(rowsToFilter, depth) {
        if (depth === void 0) {
            depth = 0;
        }
        const rows = [];
        // Filter from children up first
        for(let i = 0; i < rowsToFilter.length; i++){
            var _row$subRows;
            let row = rowsToFilter[i];
            const newRow = createRow(table, row.id, row.original, row.index, row.depth, undefined, row.parentId);
            newRow.columnFilters = row.columnFilters;
            if ((_row$subRows = row.subRows) != null && _row$subRows.length && depth < maxDepth) {
                newRow.subRows = recurseFilterRows(row.subRows, depth + 1);
                row = newRow;
                if (filterRow(row) && !newRow.subRows.length) {
                    rows.push(row);
                    newFilteredRowsById[row.id] = row;
                    newFilteredFlatRows.push(row);
                    continue;
                }
                if (filterRow(row) || newRow.subRows.length) {
                    rows.push(row);
                    newFilteredRowsById[row.id] = row;
                    newFilteredFlatRows.push(row);
                    continue;
                }
            } else {
                row = newRow;
                if (filterRow(row)) {
                    rows.push(row);
                    newFilteredRowsById[row.id] = row;
                    newFilteredFlatRows.push(row);
                }
            }
        }
        return rows;
    };
    return {
        rows: recurseFilterRows(rowsToFilter),
        flatRows: newFilteredFlatRows,
        rowsById: newFilteredRowsById
    };
}
function filterRowModelFromRoot(rowsToFilter, filterRow, table) {
    var _table$options$maxLea2;
    const newFilteredFlatRows = [];
    const newFilteredRowsById = {};
    const maxDepth = (_table$options$maxLea2 = table.options.maxLeafRowFilterDepth) != null ? _table$options$maxLea2 : 100;
    // Filters top level and nested rows
    const recurseFilterRows = function(rowsToFilter, depth) {
        if (depth === void 0) {
            depth = 0;
        }
        // Filter from parents downward first
        const rows = [];
        // Apply the filter to any subRows
        for(let i = 0; i < rowsToFilter.length; i++){
            let row = rowsToFilter[i];
            const pass = filterRow(row);
            if (pass) {
                var _row$subRows2;
                if ((_row$subRows2 = row.subRows) != null && _row$subRows2.length && depth < maxDepth) {
                    const newRow = createRow(table, row.id, row.original, row.index, row.depth, undefined, row.parentId);
                    newRow.subRows = recurseFilterRows(row.subRows, depth + 1);
                    row = newRow;
                }
                rows.push(row);
                newFilteredFlatRows.push(row);
                newFilteredRowsById[row.id] = row;
            }
        }
        return rows;
    };
    return {
        rows: recurseFilterRows(rowsToFilter),
        flatRows: newFilteredFlatRows,
        rowsById: newFilteredRowsById
    };
}
function getFacetedRowModel() {
    return (table, columnId)=>memo(()=>[
                table.getPreFilteredRowModel(),
                table.getState().columnFilters,
                table.getState().globalFilter,
                table.getFilteredRowModel()
            ], (preRowModel, columnFilters, globalFilter)=>{
            if (!preRowModel.rows.length || !(columnFilters != null && columnFilters.length) && !globalFilter) {
                return preRowModel;
            }
            const filterableIds = [
                ...columnFilters.map((d)=>d.id).filter((d)=>d !== columnId),
                globalFilter ? '__global__' : undefined
            ].filter(Boolean);
            const filterRowsImpl = (row)=>{
                // Horizontally filter rows through each column
                for(let i = 0; i < filterableIds.length; i++){
                    if (row.columnFilters[filterableIds[i]] === false) {
                        return false;
                    }
                }
                return true;
            };
            return filterRows(preRowModel.rows, filterRowsImpl, table);
        }, getMemoOptions(table.options, 'debugTable', 'getFacetedRowModel'));
}
function getFacetedUniqueValues() {
    return (table, columnId)=>memo(()=>{
            var _table$getColumn;
            return [
                (_table$getColumn = table.getColumn(columnId)) == null ? void 0 : _table$getColumn.getFacetedRowModel()
            ];
        }, (facetedRowModel)=>{
            if (!facetedRowModel) return new Map();
            let facetedUniqueValues = new Map();
            for(let i = 0; i < facetedRowModel.flatRows.length; i++){
                const values = facetedRowModel.flatRows[i].getUniqueValues(columnId);
                for(let j = 0; j < values.length; j++){
                    const value = values[j];
                    if (facetedUniqueValues.has(value)) {
                        var _facetedUniqueValues$;
                        facetedUniqueValues.set(value, ((_facetedUniqueValues$ = facetedUniqueValues.get(value)) != null ? _facetedUniqueValues$ : 0) + 1);
                    } else {
                        facetedUniqueValues.set(value, 1);
                    }
                }
            }
            return facetedUniqueValues;
        }, getMemoOptions(table.options, 'debugTable', `getFacetedUniqueValues_${columnId}`));
}
function getFilteredRowModel() {
    return (table)=>memo(()=>[
                table.getPreFilteredRowModel(),
                table.getState().columnFilters,
                table.getState().globalFilter
            ], (rowModel, columnFilters, globalFilter)=>{
            if (!rowModel.rows.length || !(columnFilters != null && columnFilters.length) && !globalFilter) {
                for(let i = 0; i < rowModel.flatRows.length; i++){
                    rowModel.flatRows[i].columnFilters = {};
                    rowModel.flatRows[i].columnFiltersMeta = {};
                }
                return rowModel;
            }
            const resolvedColumnFilters = [];
            const resolvedGlobalFilters = [];
            (columnFilters != null ? columnFilters : []).forEach((d)=>{
                var _filterFn$resolveFilt;
                const column = table.getColumn(d.id);
                if (!column) {
                    return;
                }
                const filterFn = column.getFilterFn();
                if (!filterFn) {
                    if ("TURBOPACK compile-time truthy", 1) {
                        console.warn(`Could not find a valid 'column.filterFn' for column with the ID: ${column.id}.`);
                    }
                    return;
                }
                resolvedColumnFilters.push({
                    id: d.id,
                    filterFn,
                    resolvedValue: (_filterFn$resolveFilt = filterFn.resolveFilterValue == null ? void 0 : filterFn.resolveFilterValue(d.value)) != null ? _filterFn$resolveFilt : d.value
                });
            });
            const filterableIds = (columnFilters != null ? columnFilters : []).map((d)=>d.id);
            const globalFilterFn = table.getGlobalFilterFn();
            const globallyFilterableColumns = table.getAllLeafColumns().filter((column)=>column.getCanGlobalFilter());
            if (globalFilter && globalFilterFn && globallyFilterableColumns.length) {
                filterableIds.push('__global__');
                globallyFilterableColumns.forEach((column)=>{
                    var _globalFilterFn$resol;
                    resolvedGlobalFilters.push({
                        id: column.id,
                        filterFn: globalFilterFn,
                        resolvedValue: (_globalFilterFn$resol = globalFilterFn.resolveFilterValue == null ? void 0 : globalFilterFn.resolveFilterValue(globalFilter)) != null ? _globalFilterFn$resol : globalFilter
                    });
                });
            }
            let currentColumnFilter;
            let currentGlobalFilter;
            // Flag the prefiltered row model with each filter state
            for(let j = 0; j < rowModel.flatRows.length; j++){
                const row = rowModel.flatRows[j];
                row.columnFilters = {};
                if (resolvedColumnFilters.length) {
                    for(let i = 0; i < resolvedColumnFilters.length; i++){
                        currentColumnFilter = resolvedColumnFilters[i];
                        const id = currentColumnFilter.id;
                        // Tag the row with the column filter state
                        row.columnFilters[id] = currentColumnFilter.filterFn(row, id, currentColumnFilter.resolvedValue, (filterMeta)=>{
                            row.columnFiltersMeta[id] = filterMeta;
                        });
                    }
                }
                if (resolvedGlobalFilters.length) {
                    for(let i = 0; i < resolvedGlobalFilters.length; i++){
                        currentGlobalFilter = resolvedGlobalFilters[i];
                        const id = currentGlobalFilter.id;
                        // Tag the row with the first truthy global filter state
                        if (currentGlobalFilter.filterFn(row, id, currentGlobalFilter.resolvedValue, (filterMeta)=>{
                            row.columnFiltersMeta[id] = filterMeta;
                        })) {
                            row.columnFilters.__global__ = true;
                            break;
                        }
                    }
                    if (row.columnFilters.__global__ !== true) {
                        row.columnFilters.__global__ = false;
                    }
                }
            }
            const filterRowsImpl = (row)=>{
                // Horizontally filter rows through each column
                for(let i = 0; i < filterableIds.length; i++){
                    if (row.columnFilters[filterableIds[i]] === false) {
                        return false;
                    }
                }
                return true;
            };
            // Filter final rows using all of the active filters
            return filterRows(rowModel.rows, filterRowsImpl, table);
        }, getMemoOptions(table.options, 'debugTable', 'getFilteredRowModel', ()=>table._autoResetPageIndex()));
}
function getGroupedRowModel() {
    return (table)=>memo(()=>[
                table.getState().grouping,
                table.getPreGroupedRowModel()
            ], (grouping, rowModel)=>{
            if (!rowModel.rows.length || !grouping.length) {
                rowModel.rows.forEach((row)=>{
                    row.depth = 0;
                    row.parentId = undefined;
                });
                return rowModel;
            }
            // Filter the grouping list down to columns that exist
            const existingGrouping = grouping.filter((columnId)=>table.getColumn(columnId));
            const groupedFlatRows = [];
            const groupedRowsById = {};
            // const onlyGroupedFlatRows: Row[] = [];
            // const onlyGroupedRowsById: Record<RowId, Row> = {};
            // const nonGroupedFlatRows: Row[] = [];
            // const nonGroupedRowsById: Record<RowId, Row> = {};
            // Recursively group the data
            const groupUpRecursively = function(rows, depth, parentId) {
                if (depth === void 0) {
                    depth = 0;
                }
                // Grouping depth has been been met
                // Stop grouping and simply rewrite thd depth and row relationships
                if (depth >= existingGrouping.length) {
                    return rows.map((row)=>{
                        row.depth = depth;
                        groupedFlatRows.push(row);
                        groupedRowsById[row.id] = row;
                        if (row.subRows) {
                            row.subRows = groupUpRecursively(row.subRows, depth + 1, row.id);
                        }
                        return row;
                    });
                }
                const columnId = existingGrouping[depth];
                // Group the rows together for this level
                const rowGroupsMap = groupBy(rows, columnId);
                // Perform aggregations for each group
                const aggregatedGroupedRows = Array.from(rowGroupsMap.entries()).map((_ref, index)=>{
                    let [groupingValue, groupedRows] = _ref;
                    let id = `${columnId}:${groupingValue}`;
                    id = parentId ? `${parentId}>${id}` : id;
                    // First, Recurse to group sub rows before aggregation
                    const subRows = groupUpRecursively(groupedRows, depth + 1, id);
                    subRows.forEach((subRow)=>{
                        subRow.parentId = id;
                    });
                    // Flatten the leaf rows of the rows in this group
                    const leafRows = depth ? flattenBy(groupedRows, (row)=>row.subRows) : groupedRows;
                    const row = createRow(table, id, leafRows[0].original, index, depth, undefined, parentId);
                    Object.assign(row, {
                        groupingColumnId: columnId,
                        groupingValue,
                        subRows,
                        leafRows,
                        getValue: (columnId)=>{
                            // Don't aggregate columns that are in the grouping
                            if (existingGrouping.includes(columnId)) {
                                if (row._valuesCache.hasOwnProperty(columnId)) {
                                    return row._valuesCache[columnId];
                                }
                                if (groupedRows[0]) {
                                    var _groupedRows$0$getVal;
                                    row._valuesCache[columnId] = (_groupedRows$0$getVal = groupedRows[0].getValue(columnId)) != null ? _groupedRows$0$getVal : undefined;
                                }
                                return row._valuesCache[columnId];
                            }
                            if (row._groupingValuesCache.hasOwnProperty(columnId)) {
                                return row._groupingValuesCache[columnId];
                            }
                            // Aggregate the values
                            const column = table.getColumn(columnId);
                            const aggregateFn = column == null ? void 0 : column.getAggregationFn();
                            if (aggregateFn) {
                                row._groupingValuesCache[columnId] = aggregateFn(columnId, leafRows, groupedRows);
                                return row._groupingValuesCache[columnId];
                            }
                        }
                    });
                    subRows.forEach((subRow)=>{
                        groupedFlatRows.push(subRow);
                        groupedRowsById[subRow.id] = subRow;
                    // if (subRow.getIsGrouped?.()) {
                    //   onlyGroupedFlatRows.push(subRow);
                    //   onlyGroupedRowsById[subRow.id] = subRow;
                    // } else {
                    //   nonGroupedFlatRows.push(subRow);
                    //   nonGroupedRowsById[subRow.id] = subRow;
                    // }
                    });
                    return row;
                });
                return aggregatedGroupedRows;
            };
            const groupedRows = groupUpRecursively(rowModel.rows, 0);
            groupedRows.forEach((subRow)=>{
                groupedFlatRows.push(subRow);
                groupedRowsById[subRow.id] = subRow;
            // if (subRow.getIsGrouped?.()) {
            //   onlyGroupedFlatRows.push(subRow);
            //   onlyGroupedRowsById[subRow.id] = subRow;
            // } else {
            //   nonGroupedFlatRows.push(subRow);
            //   nonGroupedRowsById[subRow.id] = subRow;
            // }
            });
            return {
                rows: groupedRows,
                flatRows: groupedFlatRows,
                rowsById: groupedRowsById
            };
        }, getMemoOptions(table.options, 'debugTable', 'getGroupedRowModel', ()=>{
            table._queue(()=>{
                table._autoResetExpanded();
                table._autoResetPageIndex();
            });
        }));
}
function groupBy(rows, columnId) {
    const groupMap = new Map();
    return rows.reduce((map, row)=>{
        const resKey = `${row.getGroupingValue(columnId)}`;
        const previous = map.get(resKey);
        if (!previous) {
            map.set(resKey, [
                row
            ]);
        } else {
            previous.push(row);
        }
        return map;
    }, groupMap);
}
function getPaginationRowModel(opts) {
    return (table)=>memo(()=>[
                table.getState().pagination,
                table.getPrePaginationRowModel(),
                table.options.paginateExpandedRows ? undefined : table.getState().expanded
            ], (pagination, rowModel)=>{
            if (!rowModel.rows.length) {
                return rowModel;
            }
            const { pageSize, pageIndex } = pagination;
            let { rows, flatRows, rowsById } = rowModel;
            const pageStart = pageSize * pageIndex;
            const pageEnd = pageStart + pageSize;
            rows = rows.slice(pageStart, pageEnd);
            let paginatedRowModel;
            if (!table.options.paginateExpandedRows) {
                paginatedRowModel = expandRows({
                    rows,
                    flatRows,
                    rowsById
                });
            } else {
                paginatedRowModel = {
                    rows,
                    flatRows,
                    rowsById
                };
            }
            paginatedRowModel.flatRows = [];
            const handleRow = (row)=>{
                paginatedRowModel.flatRows.push(row);
                if (row.subRows.length) {
                    row.subRows.forEach(handleRow);
                }
            };
            paginatedRowModel.rows.forEach(handleRow);
            return paginatedRowModel;
        }, getMemoOptions(table.options, 'debugTable', 'getPaginationRowModel'));
}
function getSortedRowModel() {
    return (table)=>memo(()=>[
                table.getState().sorting,
                table.getPreSortedRowModel()
            ], (sorting, rowModel)=>{
            if (!rowModel.rows.length || !(sorting != null && sorting.length)) {
                return rowModel;
            }
            const sortingState = table.getState().sorting;
            const sortedFlatRows = [];
            // Filter out sortings that correspond to non existing columns
            const availableSorting = sortingState.filter((sort)=>{
                var _table$getColumn;
                return (_table$getColumn = table.getColumn(sort.id)) == null ? void 0 : _table$getColumn.getCanSort();
            });
            const columnInfoById = {};
            availableSorting.forEach((sortEntry)=>{
                const column = table.getColumn(sortEntry.id);
                if (!column) return;
                columnInfoById[sortEntry.id] = {
                    sortUndefined: column.columnDef.sortUndefined,
                    invertSorting: column.columnDef.invertSorting,
                    sortingFn: column.getSortingFn()
                };
            });
            const sortData = (rows)=>{
                // This will also perform a stable sorting using the row index
                // if needed.
                const sortedData = rows.map((row)=>({
                        ...row
                    }));
                sortedData.sort((rowA, rowB)=>{
                    for(let i = 0; i < availableSorting.length; i += 1){
                        var _sortEntry$desc;
                        const sortEntry = availableSorting[i];
                        const columnInfo = columnInfoById[sortEntry.id];
                        const sortUndefined = columnInfo.sortUndefined;
                        const isDesc = (_sortEntry$desc = sortEntry == null ? void 0 : sortEntry.desc) != null ? _sortEntry$desc : false;
                        let sortInt = 0;
                        // All sorting ints should always return in ascending order
                        if (sortUndefined) {
                            const aValue = rowA.getValue(sortEntry.id);
                            const bValue = rowB.getValue(sortEntry.id);
                            const aUndefined = aValue === undefined;
                            const bUndefined = bValue === undefined;
                            if (aUndefined || bUndefined) {
                                if (sortUndefined === 'first') return aUndefined ? -1 : 1;
                                if (sortUndefined === 'last') return aUndefined ? 1 : -1;
                                sortInt = aUndefined && bUndefined ? 0 : aUndefined ? sortUndefined : -sortUndefined;
                            }
                        }
                        if (sortInt === 0) {
                            sortInt = columnInfo.sortingFn(rowA, rowB, sortEntry.id);
                        }
                        // If sorting is non-zero, take care of desc and inversion
                        if (sortInt !== 0) {
                            if (isDesc) {
                                sortInt *= -1;
                            }
                            if (columnInfo.invertSorting) {
                                sortInt *= -1;
                            }
                            return sortInt;
                        }
                    }
                    return rowA.index - rowB.index;
                });
                // If there are sub-rows, sort them
                sortedData.forEach((row)=>{
                    var _row$subRows;
                    sortedFlatRows.push(row);
                    if ((_row$subRows = row.subRows) != null && _row$subRows.length) {
                        row.subRows = sortData(row.subRows);
                    }
                });
                return sortedData;
            };
            return {
                rows: sortData(rowModel.rows),
                flatRows: sortedFlatRows,
                rowsById: rowModel.rowsById
            };
        }, getMemoOptions(table.options, 'debugTable', 'getSortedRowModel', ()=>table._autoResetPageIndex()));
}
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/@tanstack/react-table/build/lib/index.mjs [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "flexRender",
    ()=>flexRender,
    "useReactTable",
    ()=>useReactTable
]);
/**
   * react-table
   *
   * Copyright (c) TanStack
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE.md file in the root directory of this source tree.
   *
   * @license MIT
   */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$tanstack$2f$table$2d$core$2f$build$2f$lib$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@tanstack/table-core/build/lib/index.mjs [app-client] (ecmascript)");
;
;
;
//
/**
 * If rendering headers, cells, or footers with custom markup, use flexRender instead of `cell.getValue()` or `cell.renderValue()`.
 */ function flexRender(Comp, props) {
    return !Comp ? null : isReactComponent(Comp) ? /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"](Comp, props) : Comp;
}
function isReactComponent(component) {
    return isClassComponent(component) || typeof component === 'function' || isExoticComponent(component);
}
function isClassComponent(component) {
    return typeof component === 'function' && (()=>{
        const proto = Object.getPrototypeOf(component);
        return proto.prototype && proto.prototype.isReactComponent;
    })();
}
function isExoticComponent(component) {
    return typeof component === 'object' && typeof component.$$typeof === 'symbol' && [
        'react.memo',
        'react.forward_ref'
    ].includes(component.$$typeof.description);
}
function useReactTable(options) {
    // Compose in the generic options to the user options
    const resolvedOptions = {
        state: {},
        // Dummy state
        onStateChange: ()=>{},
        // noop
        renderFallbackValue: null,
        ...options
    };
    // Create a new table and store it in state
    const [tableRef] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"]({
        "useReactTable.useState": ()=>({
                current: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$tanstack$2f$table$2d$core$2f$build$2f$lib$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createTable"])(resolvedOptions)
            })
    }["useReactTable.useState"]);
    // By default, manage table state here using the table's initial state
    const [state, setState] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"]({
        "useReactTable.useState": ()=>tableRef.current.initialState
    }["useReactTable.useState"]);
    // Compose the default state above with any user state. This will allow the user
    // to only control a subset of the state if desired.
    tableRef.current.setOptions((prev)=>({
            ...prev,
            ...options,
            state: {
                ...state,
                ...options.state
            },
            // Similarly, we'll maintain both our internal state and any user-provided
            // state.
            onStateChange: (updater)=>{
                setState(updater);
                options.onStateChange == null || options.onStateChange(updater);
            }
        }));
    return tableRef.current;
}
;
 //# sourceMappingURL=index.mjs.map
}),
"[project]/coding/projects/LangBot/web/node_modules/uuidjs/dist/uuid.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "UUID",
    ()=>UUID
]);
/**
 * UUID.js - RFC-compliant UUID Generator for JavaScript
 *
 * @author  LiosK
 * @version v5.1.0
 * @license Apache License 2.0: Copyright (c) 2010-2024 LiosK
 * @packageDocumentation
 */ var _a;
class UUID {
    // Core Component {{{
    /**
     * Generates a UUIDv4 as a hexadecimal string.
     * @returns The hexadecimal UUID string.
     */ static generate() {
        var rand = _a._getRandomInt, hex = _a._hexAligner;
        return hex(rand(32), 8) + // time_low
        "-" + hex(rand(16), 4) + // time_mid
        "-" + hex(0x4000 | rand(12), 4) + // time_hi_and_version
        "-" + hex(0x8000 | rand(14), 4) + // clock_seq_hi_and_reserved clock_seq_low
        "-" + hex(rand(48), 12) // node
        ;
    }
    /**
     * Returns an unsigned `x`-bit random integer.
     * @param x - An unsigned integer ranging from 0 to 53, inclusive.
     * @returns An unsigned `x`-bit random integer (`0 <= f(x) < 2^x`).
     */ static _getRandomInt(x) {
        if (x < 0 || x > 53) {
            return NaN;
        }
        var n = 0 | Math.random() * 0x40000000; // 1 << 30
        return x > 30 ? n + (0 | Math.random() * (1 << x - 30)) * 0x40000000 : n >>> 30 - x;
    }
    /**
     * Converts an integer to a zero-filled hexadecimal string.
     */ static _hexAligner(num, length) {
        var str = num.toString(16), i = length - str.length, z = "0";
        for(; i > 0; i >>>= 1, z += z){
            if (i & 1) {
                str = z + str;
            }
        }
        return str;
    }
    /**
     * Enables Math.random()-based pseudorandom number generator instead of cryptographically safer options.
     * @since v3.5.0
     * @deprecated This method is provided only to work around performance drawbacks of the safer algorithms.
     */ static useMathRandom() {
        _a._getRandomInt = _a._mathPRNG;
    }
    /**
     * Creates a UUIDv4 object.
     * @returns A UUIDv4 object.
     * @since 3.0
     */ static genV4() {
        var rand = _a._getRandomInt;
        return new _a(rand(32), rand(16), 0x4000 | rand(12), 0x80 | rand(6), rand(8), rand(48));
    }
    /**
     * Converts a hexadecimal UUID string to a UUID object.
     * @param strId - A hexadecimal UUID string ("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").
     * @returns The UUID object or `null`.
     * @since 3.0
     */ static parse(strId) {
        var r, p = /^\s*(urn:uuid:|\{)?([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{2})([0-9a-f]{2})-([0-9a-f]{12})(\})?\s*$/i;
        if (r = p.exec(strId)) {
            var l = r[1] || "", t = r[8] || "";
            if (l + t === "" || l === "{" && t === "}" || l.toLowerCase() === "urn:uuid:" && t === "") {
                return new _a(parseInt(r[2], 16), parseInt(r[3], 16), parseInt(r[4], 16), parseInt(r[5], 16), parseInt(r[6], 16), parseInt(r[7], 16));
            }
        }
        return null;
    }
    /**
     * Initializes the UUID object.
     * @param _timeLow - The time_low field (octet 0-3, uint32).
     * @param _timeMid - The time_mid field (octet 4-5, uint16).
     * @param _timeHiAndVersion - The time_hi_and_version field (octet 6-7, uint16).
     * @param _clockSeqHiAndReserved - The clock_seq_hi_and_reserved field (octet 8, uint8).
     * @param _clockSeqLow - The clock_seq_low field (octet 9, uint8).
     * @param _node - The node field (octet 10-15, uint48).
     */ constructor(_timeLow, _timeMid, _timeHiAndVersion, _clockSeqHiAndReserved, _clockSeqLow, _node){
        var names = _a.FIELD_NAMES, sizes = _a.FIELD_SIZES;
        var bin = _a._binAligner, hex = _a._hexAligner;
        // @ts-ignore
        this.intFields = new Array(6);
        // @ts-ignore
        this.bitFields = new Array(6);
        // @ts-ignore
        this.hexFields = new Array(6);
        for(var i = 0; i < 6; i++){
            var intValue = parseInt(arguments[i] || 0);
            // @ts-ignore
            this.intFields[i] = this.intFields[names[i]] = intValue;
            // @ts-ignore
            this.bitFields[i] = this.bitFields[names[i]] = bin(intValue, sizes[i]);
            // @ts-ignore
            this.hexFields[i] = this.hexFields[names[i]] = hex(intValue, sizes[i] >>> 2);
        }
        this.version = this.intFields.timeHiAndVersion >>> 12 & 0xf;
        this.bitString = this.bitFields.join("");
        this.hexNoDelim = this.hexFields.join("");
        this.hexString = this.hexFields[0] + "-" + this.hexFields[1] + "-" + this.hexFields[2] + "-" + this.hexFields[3] + this.hexFields[4] + "-" + this.hexFields[5];
        this.urn = "urn:uuid:" + this.hexString;
    }
    /**
     * Converts an integer to a zero-filled binary string.
     */ static _binAligner(num, length) {
        var str = num.toString(2), i = length - str.length, z = "0";
        for(; i > 0; i >>>= 1, z += z){
            if (i & 1) {
                str = z + str;
            }
        }
        return str;
    }
    /**
     * Returns the hexadecimal string representation.
     * @returns {@link UUID#hexString}.
     */ toString() {
        return this.hexString;
    }
    /**
     * Tests if two UUID objects are equal.
     * @returns `true` if two UUID objects are equal.
     */ equals(uuid) {
        if (!(uuid instanceof _a)) {
            return false;
        }
        for(var i = 0; i < 6; i++){
            if (this.intFields[i] !== uuid.intFields[i]) {
                return false;
            }
        }
        return true;
    }
    // }}}
    // UUIDv1 Component (1 of 2) {{{
    /**
     * Creates a UUIDv1 object.
     * @returns A UUIDv1 object.
     * @since 3.0
     */ static genV1() {
        if (_a._state == null) {
            _a._state = new UUIDState();
        }
        var now = new Date().getTime(), st = _a._state;
        if (now != st.timestamp) {
            if (now < st.timestamp) {
                st.sequence++;
            }
            st.timestamp = now;
            st.tick = _a._getRandomInt(12); // up to 4095, allowing 5904 tick per msec
        } else if (st.tick < 9992) {
            // advance sub-millisecond fraction up to 9999 100-nanoseconds
            st.tick += 1 + _a._getRandomInt(3);
        } else {
            // advance seq if tick overflows in remote chance
            st.sequence++;
        }
        // format time fields
        var tf = _a._getTimeFieldValues(st.timestamp);
        var tl = tf.low + st.tick;
        var thav = tf.hi & 0xfff | 0x1000; // set version '0001'
        // format clock sequence
        st.sequence &= 0x3fff;
        var cshar = st.sequence >>> 8 | 0x80; // set variant '10'
        var csl = st.sequence & 0xff;
        return new _a(tl, tf.mid, thav, cshar, csl, st.node);
    }
    /**
     * Re-initializes the internal state for UUIDv1 and UUIDv6 creation.
     * @since 3.0
     */ static resetState() {
        _a._state = new UUIDState();
    }
    /**
     * @param time - The number of milliseconds elapsed since 1970-01-01.
     */ static _getTimeFieldValues(time) {
        var ts = time - Date.UTC(1582, 9, 15);
        var hm = ts / 0x100000000 * 10000 & 0xfffffff;
        return {
            low: (ts & 0xfffffff) * 10000 % 0x100000000,
            mid: hm & 0xffff,
            hi: hm >>> 16,
            timestamp: ts
        };
    }
    // }}}
    // UUIDv6 Component {{{
    /**
     * Creates a UUIDv6 object.
     * @returns A UUIDv6 object.
     * @since v4.2.13
     */ static genV6() {
        if (_a._state == null) {
            _a._state = new UUIDState();
        }
        var now = new Date().getTime(), st = _a._state;
        if (now != st.timestamp) {
            if (now < st.timestamp) {
                st.sequence++;
            }
            st.timestamp = now;
            st.tick = _a._getRandomInt(12); // up to 4095, allowing 5904 tick per msec
        } else if (st.tick < 9992) {
            // advance sub-millisecond fraction up to 9999 100-nanoseconds
            st.tick += 1 + _a._getRandomInt(3);
        } else {
            // advance seq if tick overflows in remote chance
            st.sequence++;
        }
        // format time fields
        var ts = st.timestamp - Date.UTC(1582, 9, 15);
        var th = Math.floor(ts / 0x10000000 * 10000) % 0x100000000;
        var midlow = ((ts & 0xfffffff) * 10000 & 0xfffffff) + st.tick;
        var tm = midlow >>> 12;
        var tlav = midlow & 0xfff | 0x6000; // set version '0110'
        // format clock sequence
        st.sequence &= 0x3fff;
        var cshar = st.sequence >>> 8 | 0x80; // set variant '10'
        var csl = st.sequence & 0xff;
        return new _a(th, tm, tlav, cshar, csl, st.node);
    }
}
_a = UUID;
// }}}
// Advanced Random Number Generator Component {{{
UUID._mathPRNG = _a._getRandomInt;
(()=>{
    if (typeof crypto !== "undefined" && crypto.getRandomValues) {
        // Web Cryptography API
        _a._getRandomInt = (x)=>{
            if (x < 0 || x > 53) {
                return NaN;
            }
            var ns = new Uint32Array(x > 32 ? 2 : 1);
            crypto.getRandomValues(ns);
            return x > 32 ? ns[0] + (ns[1] >>> 64 - x) * 0x100000000 : ns[0] >>> 32 - x;
        };
    }
})();
// }}}
// UUID Object Component {{{
/**
 * The names of UUID internal fields.
 *
 * Note that these internal fields from the obsolete RFC 4122 are no longer
 * used in the current RFC 9562.
 * @since 3.0
 */ UUID.FIELD_NAMES = [
    "timeLow",
    "timeMid",
    "timeHiAndVersion",
    "clockSeqHiAndReserved",
    "clockSeqLow",
    "node"
];
/**
 * The sizes of UUID internal fields.
 *
 * Note that these internal fields from the obsolete RFC 4122 are no longer
 * used in the current RFC 9562.
 * @since 3.0
 */ UUID.FIELD_SIZES = [
    32,
    16,
    16,
    8,
    8,
    48
];
/**
 * A nil UUID object.
 * @since v3.4.0
 */ UUID.NIL = new _a(0, 0, 0, 0, 0, 0);
/**
 * The persistent internal state for UUIDv1 and UUIDv6 creation.
 */ UUID._state = null;
// UUIDv1 Component (2 of 2) {{{
class UUIDState {
    constructor(){
        // @ts-ignore
        var rand = UUID._getRandomInt;
        this.timestamp = 0;
        this.tick = 0; // timestamp fraction smaller than a millisecond
        this.sequence = rand(14);
        this.node = (rand(8) | 1) * 0x10000000000 + rand(40); // set multicast bit '1'
    }
} // }}}
 // vim: fdm=marker fmr&
}),
"[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-hover-card/dist/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Arrow",
    ()=>Arrow2,
    "Content",
    ()=>Content2,
    "HoverCard",
    ()=>HoverCard,
    "HoverCardArrow",
    ()=>HoverCardArrow,
    "HoverCardContent",
    ()=>HoverCardContent,
    "HoverCardPortal",
    ()=>HoverCardPortal,
    "HoverCardTrigger",
    ()=>HoverCardTrigger,
    "Portal",
    ()=>Portal,
    "Root",
    ()=>Root2,
    "Trigger",
    ()=>Trigger,
    "createHoverCardScope",
    ()=>createHoverCardScope
]);
// src/hover-card.tsx
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-context/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-use-controllable-state/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-compose-refs/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-popper/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$portal$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-portal/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-presence/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-primitive/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dismissable$2d$layer$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-dismissable-layer/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
"use client";
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
var originalBodyUserSelect;
var HOVERCARD_NAME = "HoverCard";
var [createHoverCardContext, createHoverCardScope] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$context$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContextScope"])(HOVERCARD_NAME, [
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPopperScope"]
]);
var usePopperScope = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPopperScope"])();
var [HoverCardProvider, useHoverCardContext] = createHoverCardContext(HOVERCARD_NAME);
var HoverCard = (props)=>{
    const { __scopeHoverCard, children, open: openProp, defaultOpen, onOpenChange, openDelay = 700, closeDelay = 300 } = props;
    const popperScope = usePopperScope(__scopeHoverCard);
    const openTimerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    const closeTimerRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](0);
    const hasSelectionRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const isPointerDownOnContentRef = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    const [open, setOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$use$2d$controllable$2d$state$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useControllableState"])({
        prop: openProp,
        defaultProp: defaultOpen ?? false,
        onChange: onOpenChange,
        caller: HOVERCARD_NAME
    });
    const handleOpen = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "HoverCard.useCallback[handleOpen]": ()=>{
            clearTimeout(closeTimerRef.current);
            openTimerRef.current = window.setTimeout({
                "HoverCard.useCallback[handleOpen]": ()=>setOpen(true)
            }["HoverCard.useCallback[handleOpen]"], openDelay);
        }
    }["HoverCard.useCallback[handleOpen]"], [
        openDelay,
        setOpen
    ]);
    const handleClose = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "HoverCard.useCallback[handleClose]": ()=>{
            clearTimeout(openTimerRef.current);
            if (!hasSelectionRef.current && !isPointerDownOnContentRef.current) {
                closeTimerRef.current = window.setTimeout({
                    "HoverCard.useCallback[handleClose]": ()=>setOpen(false)
                }["HoverCard.useCallback[handleClose]"], closeDelay);
            }
        }
    }["HoverCard.useCallback[handleClose]"], [
        closeDelay,
        setOpen
    ]);
    const handleDismiss = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "HoverCard.useCallback[handleDismiss]": ()=>setOpen(false)
    }["HoverCard.useCallback[handleDismiss]"], [
        setOpen
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "HoverCard.useEffect": ()=>{
            return ({
                "HoverCard.useEffect": ()=>{
                    clearTimeout(openTimerRef.current);
                    clearTimeout(closeTimerRef.current);
                }
            })["HoverCard.useEffect"];
        }
    }["HoverCard.useEffect"], []);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(HoverCardProvider, {
        scope: __scopeHoverCard,
        open,
        onOpenChange: setOpen,
        onOpen: handleOpen,
        onClose: handleClose,
        onDismiss: handleDismiss,
        hasSelectionRef,
        isPointerDownOnContentRef,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
            ...popperScope,
            children
        })
    });
};
HoverCard.displayName = HOVERCARD_NAME;
var TRIGGER_NAME = "HoverCardTrigger";
var HoverCardTrigger = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeHoverCard, ...triggerProps } = props;
    const context = useHoverCardContext(TRIGGER_NAME, __scopeHoverCard);
    const popperScope = usePopperScope(__scopeHoverCard);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Anchor"], {
        asChild: true,
        ...popperScope,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Primitive"].a, {
            "data-state": context.open ? "open" : "closed",
            ...triggerProps,
            ref: forwardedRef,
            onPointerEnter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerEnter, excludeTouch(context.onOpen)),
            onPointerLeave: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerLeave, excludeTouch(context.onClose)),
            onFocus: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onFocus, context.onOpen),
            onBlur: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onBlur, context.onClose),
            onTouchStart: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onTouchStart, (event)=>event.preventDefault())
        })
    });
});
HoverCardTrigger.displayName = TRIGGER_NAME;
var PORTAL_NAME = "HoverCardPortal";
var [PortalProvider, usePortalContext] = createHoverCardContext(PORTAL_NAME, {
    forceMount: void 0
});
var HoverCardPortal = (props)=>{
    const { __scopeHoverCard, forceMount, children, container } = props;
    const context = useHoverCardContext(PORTAL_NAME, __scopeHoverCard);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(PortalProvider, {
        scope: __scopeHoverCard,
        forceMount,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
            present: forceMount || context.open,
            children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$portal$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Portal"], {
                asChild: true,
                container,
                children
            })
        })
    });
};
HoverCardPortal.displayName = PORTAL_NAME;
var CONTENT_NAME = "HoverCardContent";
var HoverCardContent = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const portalContext = usePortalContext(CONTENT_NAME, props.__scopeHoverCard);
    const { forceMount = portalContext.forceMount, ...contentProps } = props;
    const context = useHoverCardContext(CONTENT_NAME, props.__scopeHoverCard);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$presence$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Presence"], {
        present: forceMount || context.open,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(HoverCardContentImpl, {
            "data-state": context.open ? "open" : "closed",
            ...contentProps,
            onPointerEnter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerEnter, excludeTouch(context.onOpen)),
            onPointerLeave: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(props.onPointerLeave, excludeTouch(context.onClose)),
            ref: forwardedRef
        })
    });
});
HoverCardContent.displayName = CONTENT_NAME;
var HoverCardContentImpl = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeHoverCard, onEscapeKeyDown, onPointerDownOutside, onFocusOutside, onInteractOutside, ...contentProps } = props;
    const context = useHoverCardContext(CONTENT_NAME, __scopeHoverCard);
    const popperScope = usePopperScope(__scopeHoverCard);
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const composedRefs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$compose$2d$refs$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useComposedRefs"])(forwardedRef, ref);
    const [containSelection, setContainSelection] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](false);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "HoverCardContentImpl.useEffect": ()=>{
            if (containSelection) {
                const body = document.body;
                originalBodyUserSelect = body.style.userSelect || body.style.webkitUserSelect;
                body.style.userSelect = "none";
                body.style.webkitUserSelect = "none";
                return ({
                    "HoverCardContentImpl.useEffect": ()=>{
                        body.style.userSelect = originalBodyUserSelect;
                        body.style.webkitUserSelect = originalBodyUserSelect;
                    }
                })["HoverCardContentImpl.useEffect"];
            }
        }
    }["HoverCardContentImpl.useEffect"], [
        containSelection
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "HoverCardContentImpl.useEffect": ()=>{
            if (ref.current) {
                const handlePointerUp = {
                    "HoverCardContentImpl.useEffect.handlePointerUp": ()=>{
                        setContainSelection(false);
                        context.isPointerDownOnContentRef.current = false;
                        setTimeout({
                            "HoverCardContentImpl.useEffect.handlePointerUp": ()=>{
                                const hasSelection = document.getSelection()?.toString() !== "";
                                if (hasSelection) context.hasSelectionRef.current = true;
                            }
                        }["HoverCardContentImpl.useEffect.handlePointerUp"]);
                    }
                }["HoverCardContentImpl.useEffect.handlePointerUp"];
                document.addEventListener("pointerup", handlePointerUp);
                return ({
                    "HoverCardContentImpl.useEffect": ()=>{
                        document.removeEventListener("pointerup", handlePointerUp);
                        context.hasSelectionRef.current = false;
                        context.isPointerDownOnContentRef.current = false;
                    }
                })["HoverCardContentImpl.useEffect"];
            }
        }
    }["HoverCardContentImpl.useEffect"], [
        context.isPointerDownOnContentRef,
        context.hasSelectionRef
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "HoverCardContentImpl.useEffect": ()=>{
            if (ref.current) {
                const tabbables = getTabbableNodes(ref.current);
                tabbables.forEach({
                    "HoverCardContentImpl.useEffect": (tabbable)=>tabbable.setAttribute("tabindex", "-1")
                }["HoverCardContentImpl.useEffect"]);
            }
        }
    }["HoverCardContentImpl.useEffect"]);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dismissable$2d$layer$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DismissableLayer"], {
        asChild: true,
        disableOutsidePointerEvents: false,
        onInteractOutside,
        onEscapeKeyDown,
        onPointerDownOutside,
        onFocusOutside: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(onFocusOutside, (event)=>{
            event.preventDefault();
        }),
        onDismiss: context.onDismiss,
        children: /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Content"], {
            ...popperScope,
            ...contentProps,
            onPointerDown: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$primitive$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["composeEventHandlers"])(contentProps.onPointerDown, (event)=>{
                if (event.currentTarget.contains(event.target)) {
                    setContainSelection(true);
                }
                context.hasSelectionRef.current = false;
                context.isPointerDownOnContentRef.current = true;
            }),
            ref: composedRefs,
            style: {
                ...contentProps.style,
                userSelect: containSelection ? "text" : void 0,
                // Safari requires prefix
                WebkitUserSelect: containSelection ? "text" : void 0,
                // re-namespace exposed content custom properties
                ...{
                    "--radix-hover-card-content-transform-origin": "var(--radix-popper-transform-origin)",
                    "--radix-hover-card-content-available-width": "var(--radix-popper-available-width)",
                    "--radix-hover-card-content-available-height": "var(--radix-popper-available-height)",
                    "--radix-hover-card-trigger-width": "var(--radix-popper-anchor-width)",
                    "--radix-hover-card-trigger-height": "var(--radix-popper-anchor-height)"
                }
            }
        })
    });
});
var ARROW_NAME = "HoverCardArrow";
var HoverCardArrow = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"]((props, forwardedRef)=>{
    const { __scopeHoverCard, ...arrowProps } = props;
    const popperScope = usePopperScope(__scopeHoverCard);
    return /* @__PURE__ */ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$popper$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Arrow"], {
        ...popperScope,
        ...arrowProps,
        ref: forwardedRef
    });
});
HoverCardArrow.displayName = ARROW_NAME;
function excludeTouch(eventHandler) {
    return (event)=>event.pointerType === "touch" ? void 0 : eventHandler();
}
function getTabbableNodes(container) {
    const nodes = [];
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_ELEMENT, {
        acceptNode: (node)=>{
            return node.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
        }
    });
    while(walker.nextNode())nodes.push(walker.currentNode);
    return nodes;
}
var Root2 = HoverCard;
var Trigger = HoverCardTrigger;
var Portal = HoverCardPortal;
var Content2 = HoverCardContent;
var Arrow2 = HoverCardArrow;
;
 //# sourceMappingURL=index.mjs.map
}),
]);

//# sourceMappingURL=a2e30_0a0c9653._.js.map