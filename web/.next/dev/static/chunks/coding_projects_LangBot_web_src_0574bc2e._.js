(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/coding/projects/LangBot/web/src/app/infra/basic-component/create-card-component/createCartComponent.module.css [app-client] (css module)", ((__turbopack_context__) => {

__turbopack_context__.v({
  "cardContainer": "createCartComponent-module__mFGHBq__cardContainer",
  "createCardContainer": "createCartComponent-module__mFGHBq__createCardContainer",
});
}),
"[project]/coding/projects/LangBot/web/src/app/infra/basic-component/create-card-component/CreateCardComponent.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>CreateCardComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$basic$2d$component$2f$create$2d$card$2d$component$2f$createCartComponent$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/basic-component/create-card-component/createCartComponent.module.css [app-client] (css module)");
;
;
function CreateCardComponent({ height, plusSize, onClick, width = '100%' }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$basic$2d$component$2f$create$2d$card$2d$component$2f$createCartComponent$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].cardContainer} ${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$basic$2d$component$2f$create$2d$card$2d$component$2f$createCartComponent$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].createCardContainer} `,
        style: {
            width: `${width}`,
            height: `${height}`,
            fontSize: `${plusSize}px`
        },
        onClick: onClick,
        children: "+"
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/infra/basic-component/create-card-component/CreateCardComponent.tsx",
        lineNumber: 15,
        columnNumber: 5
    }, this);
}
_c = CreateCardComponent;
var _c;
__turbopack_context__.k.register(_c, "CreateCardComponent");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCardVO.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PipelineCardVO",
    ()=>PipelineCardVO
]);
class PipelineCardVO {
    id;
    description;
    name;
    lastUpdatedTimeAgo;
    isDefault;
    emoji;
    constructor(props){
        this.id = props.id;
        this.name = props.name;
        this.description = props.description;
        this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
        this.isDefault = props.isDefault;
        this.emoji = props.emoji;
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/pipelineCard.module.css [app-client] (css module)", ((__turbopack_context__) => {

__turbopack_context__.v({
  "basicInfoContainer": "pipelineCard-module__GUxC_G__basicInfoContainer",
  "basicInfoDescriptionText": "pipelineCard-module__GUxC_G__basicInfoDescriptionText",
  "basicInfoLastUpdatedTimeContainer": "pipelineCard-module__GUxC_G__basicInfoLastUpdatedTimeContainer",
  "basicInfoNameContainer": "pipelineCard-module__GUxC_G__basicInfoNameContainer",
  "basicInfoNameText": "pipelineCard-module__GUxC_G__basicInfoNameText",
  "basicInfoUpdateTimeIcon": "pipelineCard-module__GUxC_G__basicInfoUpdateTimeIcon",
  "basicInfoUpdateTimeText": "pipelineCard-module__GUxC_G__basicInfoUpdateTimeText",
  "bigText": "pipelineCard-module__GUxC_G__bigText",
  "cardContainer": "pipelineCard-module__GUxC_G__cardContainer",
  "debugButtonIcon": "pipelineCard-module__GUxC_G__debugButtonIcon",
  "iconBasicInfoContainer": "pipelineCard-module__GUxC_G__iconBasicInfoContainer",
  "iconEmoji": "pipelineCard-module__GUxC_G__iconEmoji",
  "operationContainer": "pipelineCard-module__GUxC_G__operationContainer",
  "operationDefaultBadge": "pipelineCard-module__GUxC_G__operationDefaultBadge",
  "operationDefaultBadgeIcon": "pipelineCard-module__GUxC_G__operationDefaultBadgeIcon",
  "operationDefaultBadgeText": "pipelineCard-module__GUxC_G__operationDefaultBadgeText",
});
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PipelineCard
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/pipelineCard.module.css [app-client] (css module)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
function PipelineCard({ cardVO }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].cardContainer}`,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoContainer}`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].iconBasicInfoContainer}`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].iconEmoji}`,
                                children: cardVO.emoji || '⚙️'
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                lineNumber: 12,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoNameContainer}`,
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoNameText}  ${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].bigText}`,
                                        children: cardVO.name
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                        lineNumber: 14,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoDescriptionText}`,
                                        children: cardVO.description
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                        lineNumber: 17,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                lineNumber: 13,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                        lineNumber: 11,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoLastUpdatedTimeContainer}`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoUpdateTimeIcon}`,
                                xmlns: "http://www.w3.org/2000/svg",
                                viewBox: "0 0 24 24",
                                fill: "currentColor",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM13 12H17V14H11V7H13V12Z"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                    lineNumber: 30,
                                    columnNumber: 13
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                lineNumber: 24,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `${__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].basicInfoUpdateTimeText}`,
                                children: [
                                    t('pipelines.updateTime'),
                                    cardVO.lastUpdatedTimeAgo
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                lineNumber: 32,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                        lineNumber: 23,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                lineNumber: 10,
                columnNumber: 7
            }, this),
            cardVO.isDefault && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].operationContainer,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].operationDefaultBadge,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                            className: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].operationDefaultBadgeIcon,
                            xmlns: "http://www.w3.org/2000/svg",
                            viewBox: "0 0 24 24",
                            fill: "currentColor",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                d: "M12.0006 18.26L4.94715 22.2082L6.52248 14.2799L0.587891 8.7918L8.61493 7.84006L12.0006 0.5L15.3862 7.84006L23.4132 8.7918L17.4787 14.2799L19.054 22.2082L12.0006 18.26Z"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                                lineNumber: 48,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                            lineNumber: 42,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$pipelineCard$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].operationDefaultBadgeText,
                            children: t('pipelines.defaultBadge')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                            lineNumber: 50,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                    lineNumber: 41,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
                lineNumber: 40,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx",
        lineNumber: 9,
        columnNumber: 5
    }, this);
}
_s(PipelineCard, "zlIdU9EjM2llFt74AbE2KsUJXyM=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"]
    ];
});
_c = PipelineCard;
var _c;
__turbopack_context__.k.register(_c, "PipelineCard");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/pipelineConfig.module.css [app-client] (css module)", ((__turbopack_context__) => {

__turbopack_context__.v({
  "configPageContainer": "pipelineConfig-module__W2iQ7G__configPageContainer",
  "pipelineListContainer": "pipelineConfig-module__W2iQ7G__pipelineListContainer",
});
}),
"[project]/coding/projects/LangBot/web/src/hooks/use-mobile.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useIsMobile",
    ()=>useIsMobile
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var _s = __turbopack_context__.k.signature();
;
const MOBILE_BREAKPOINT = 768;
function useIsMobile() {
    _s();
    const [isMobile, setIsMobile] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](undefined);
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "useIsMobile.useEffect": ()=>{
            const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
            const onChange = {
                "useIsMobile.useEffect.onChange": ()=>{
                    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
                }
            }["useIsMobile.useEffect.onChange"];
            mql.addEventListener('change', onChange);
            setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
            return ({
                "useIsMobile.useEffect": ()=>mql.removeEventListener('change', onChange)
            })["useIsMobile.useEffect"];
        }
    }["useIsMobile.useEffect"], []);
    return !!isMobile;
}
_s(useIsMobile, "D6B2cPXNCaIbeOx+abFr1uxLRM0=");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Sheet",
    ()=>Sheet,
    "SheetClose",
    ()=>SheetClose,
    "SheetContent",
    ()=>SheetContent,
    "SheetDescription",
    ()=>SheetDescription,
    "SheetFooter",
    ()=>SheetFooter,
    "SheetHeader",
    ()=>SheetHeader,
    "SheetTitle",
    ()=>SheetTitle,
    "SheetTrigger",
    ()=>SheetTrigger
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-dialog/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__XIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/x.js [app-client] (ecmascript) <export default as XIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
'use client';
;
;
;
;
function Sheet({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
        "data-slot": "sheet",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 10,
        columnNumber: 10
    }, this);
}
_c = Sheet;
function SheetTrigger({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Trigger"], {
        "data-slot": "sheet-trigger",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 16,
        columnNumber: 10
    }, this);
}
_c1 = SheetTrigger;
function SheetClose({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Close"], {
        "data-slot": "sheet-close",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 22,
        columnNumber: 10
    }, this);
}
_c2 = SheetClose;
function SheetPortal({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Portal"], {
        "data-slot": "sheet-portal",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 28,
        columnNumber: 10
    }, this);
}
_c3 = SheetPortal;
function SheetOverlay({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Overlay"], {
        "data-slot": "sheet-overlay",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 36,
        columnNumber: 5
    }, this);
}
_c4 = SheetOverlay;
function SheetContent({ className, children, side = 'right', ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(SheetPortal, {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(SheetOverlay, {}, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
                lineNumber: 57,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Content"], {
                "data-slot": "sheet-content",
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-background data-[state=open]:animate-in data-[state=closed]:animate-out fixed z-50 flex flex-col gap-4 shadow-lg transition ease-in-out data-[state=closed]:duration-300 data-[state=open]:duration-500', side === 'right' && 'data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm', side === 'left' && 'data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm', side === 'top' && 'data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top inset-x-0 top-0 h-auto border-b', side === 'bottom' && 'data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom inset-x-0 bottom-0 h-auto border-t', className),
                ...props,
                children: [
                    children,
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Close"], {
                        className: "ring-offset-background focus:ring-ring data-[state=open]:bg-secondary absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__XIcon$3e$__["XIcon"], {
                                className: "size-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
                                lineNumber: 76,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "sr-only",
                                children: "Close"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
                                lineNumber: 77,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
                        lineNumber: 75,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
                lineNumber: 58,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 56,
        columnNumber: 5
    }, this);
}
_c5 = SheetContent;
function SheetHeader({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sheet-header",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex flex-col gap-1.5 p-4', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 86,
        columnNumber: 5
    }, this);
}
_c6 = SheetHeader;
function SheetFooter({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sheet-footer",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('mt-auto flex flex-col gap-2 p-4', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 96,
        columnNumber: 5
    }, this);
}
_c7 = SheetFooter;
function SheetTitle({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Title"], {
        "data-slot": "sheet-title",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-foreground font-semibold', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 109,
        columnNumber: 5
    }, this);
}
_c8 = SheetTitle;
function SheetDescription({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$dialog$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Description"], {
        "data-slot": "sheet-description",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-muted-foreground text-sm', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx",
        lineNumber: 122,
        columnNumber: 5
    }, this);
}
_c9 = SheetDescription;
;
var _c, _c1, _c2, _c3, _c4, _c5, _c6, _c7, _c8, _c9;
__turbopack_context__.k.register(_c, "Sheet");
__turbopack_context__.k.register(_c1, "SheetTrigger");
__turbopack_context__.k.register(_c2, "SheetClose");
__turbopack_context__.k.register(_c3, "SheetPortal");
__turbopack_context__.k.register(_c4, "SheetOverlay");
__turbopack_context__.k.register(_c5, "SheetContent");
__turbopack_context__.k.register(_c6, "SheetHeader");
__turbopack_context__.k.register(_c7, "SheetFooter");
__turbopack_context__.k.register(_c8, "SheetTitle");
__turbopack_context__.k.register(_c9, "SheetDescription");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/skeleton.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Skeleton",
    ()=>Skeleton
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
;
;
function Skeleton({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "skeleton",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-accent animate-pulse rounded-md', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/skeleton.tsx",
        lineNumber: 5,
        columnNumber: 5
    }, this);
}
_c = Skeleton;
;
var _c;
__turbopack_context__.k.register(_c, "Skeleton");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
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
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-tooltip/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
'use client';
;
;
;
function TooltipProvider({ delayDuration = 0, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Provider"], {
        "data-slot": "tooltip-provider",
        delayDuration: delayDuration,
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
        lineNumber: 13,
        columnNumber: 5
    }, this);
}
_c = TooltipProvider;
function Tooltip({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TooltipProvider, {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
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
_c1 = Tooltip;
function TooltipTrigger({ ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Trigger"], {
        "data-slot": "tooltip-trigger",
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx",
        lineNumber: 34,
        columnNumber: 10
    }, this);
}
_c2 = TooltipTrigger;
function TooltipContent({ className, sideOffset = 0, children, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Portal"], {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Content"], {
            "data-slot": "tooltip-content",
            sideOffset: sideOffset,
            className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-primary text-primary-foreground animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 w-fit origin-(--radix-tooltip-content-transform-origin) rounded-md px-3 py-1.5 text-xs text-balance', className),
            ...props,
            children: [
                children,
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$tooltip$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Arrow"], {
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
_c3 = TooltipContent;
;
var _c, _c1, _c2, _c3;
__turbopack_context__.k.register(_c, "TooltipProvider");
__turbopack_context__.k.register(_c1, "Tooltip");
__turbopack_context__.k.register(_c2, "TooltipTrigger");
__turbopack_context__.k.register(_c3, "TooltipContent");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Sidebar",
    ()=>Sidebar,
    "SidebarContent",
    ()=>SidebarContent,
    "SidebarFooter",
    ()=>SidebarFooter,
    "SidebarGroup",
    ()=>SidebarGroup,
    "SidebarGroupAction",
    ()=>SidebarGroupAction,
    "SidebarGroupContent",
    ()=>SidebarGroupContent,
    "SidebarGroupLabel",
    ()=>SidebarGroupLabel,
    "SidebarHeader",
    ()=>SidebarHeader,
    "SidebarInput",
    ()=>SidebarInput,
    "SidebarInset",
    ()=>SidebarInset,
    "SidebarMenu",
    ()=>SidebarMenu,
    "SidebarMenuAction",
    ()=>SidebarMenuAction,
    "SidebarMenuBadge",
    ()=>SidebarMenuBadge,
    "SidebarMenuButton",
    ()=>SidebarMenuButton,
    "SidebarMenuItem",
    ()=>SidebarMenuItem,
    "SidebarMenuSkeleton",
    ()=>SidebarMenuSkeleton,
    "SidebarMenuSub",
    ()=>SidebarMenuSub,
    "SidebarMenuSubButton",
    ()=>SidebarMenuSubButton,
    "SidebarMenuSubItem",
    ()=>SidebarMenuSubItem,
    "SidebarProvider",
    ()=>SidebarProvider,
    "SidebarRail",
    ()=>SidebarRail,
    "SidebarSeparator",
    ()=>SidebarSeparator,
    "SidebarTrigger",
    ()=>SidebarTrigger,
    "useSidebar",
    ()=>useSidebar
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$class$2d$variance$2d$authority$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/class-variance-authority/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$panel$2d$left$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__PanelLeftIcon$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/panel-left.js [app-client] (ecmascript) <export default as PanelLeftIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$use$2d$mobile$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/hooks/use-mobile.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$separator$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/separator.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sheet$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/sheet.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/skeleton.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/tooltip.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature(), _s1 = __turbopack_context__.k.signature(), _s2 = __turbopack_context__.k.signature(), _s3 = __turbopack_context__.k.signature(), _s4 = __turbopack_context__.k.signature(), _s5 = __turbopack_context__.k.signature(), _s6 = __turbopack_context__.k.signature();
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
const SIDEBAR_COOKIE_NAME = 'sidebar_state';
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
const SIDEBAR_WIDTH = '16rem';
const SIDEBAR_WIDTH_MOBILE = '18rem';
const SIDEBAR_WIDTH_ICON = '3rem';
const SIDEBAR_KEYBOARD_SHORTCUT = 'b';
const SidebarContext = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"](null);
function useSidebar() {
    _s();
    const context = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"](SidebarContext);
    if (!context) {
        throw new Error('useSidebar must be used within a SidebarProvider.');
    }
    return context;
}
_s(useSidebar, "b9L3QQ+jgeyIrH0NfHrJ8nn7VMU=");
function SidebarProvider({ defaultOpen = true, open: openProp, onOpenChange: setOpenProp, className, style, children, ...props }) {
    _s1();
    const isMobile = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$use$2d$mobile$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useIsMobile"])();
    const [openMobile, setOpenMobile] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](false);
    // This is the internal state of the sidebar.
    // We use openProp and setOpenProp for control from outside the component.
    const [_open, _setOpen] = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](defaultOpen);
    const open = openProp ?? _open;
    const setOpen = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "SidebarProvider.useCallback[setOpen]": (value)=>{
            const openState = typeof value === 'function' ? value(open) : value;
            if (setOpenProp) {
                setOpenProp(openState);
            } else {
                _setOpen(openState);
            }
            // This sets the cookie to keep the sidebar state.
            document.cookie = `${SIDEBAR_COOKIE_NAME}=${openState}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
        }
    }["SidebarProvider.useCallback[setOpen]"], [
        setOpenProp,
        open
    ]);
    // Helper to toggle the sidebar.
    const toggleSidebar = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "SidebarProvider.useCallback[toggleSidebar]": ()=>{
            return isMobile ? setOpenMobile({
                "SidebarProvider.useCallback[toggleSidebar]": (open)=>!open
            }["SidebarProvider.useCallback[toggleSidebar]"]) : setOpen({
                "SidebarProvider.useCallback[toggleSidebar]": (open)=>!open
            }["SidebarProvider.useCallback[toggleSidebar]"]);
        }
    }["SidebarProvider.useCallback[toggleSidebar]"], [
        isMobile,
        setOpen,
        setOpenMobile
    ]);
    // Adds a keyboard shortcut to toggle the sidebar.
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"]({
        "SidebarProvider.useEffect": ()=>{
            const handleKeyDown = {
                "SidebarProvider.useEffect.handleKeyDown": (event)=>{
                    if (event.key === SIDEBAR_KEYBOARD_SHORTCUT && (event.metaKey || event.ctrlKey)) {
                        event.preventDefault();
                        toggleSidebar();
                    }
                }
            }["SidebarProvider.useEffect.handleKeyDown"];
            window.addEventListener('keydown', handleKeyDown);
            return ({
                "SidebarProvider.useEffect": ()=>window.removeEventListener('keydown', handleKeyDown)
            })["SidebarProvider.useEffect"];
        }
    }["SidebarProvider.useEffect"], [
        toggleSidebar
    ]);
    // We add a state so that we can do data-state="expanded" or "collapsed".
    // This makes it easier to style the sidebar with Tailwind classes.
    const state = open ? 'expanded' : 'collapsed';
    const contextValue = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "SidebarProvider.useMemo[contextValue]": ()=>({
                state,
                open,
                setOpen,
                isMobile,
                openMobile,
                setOpenMobile,
                toggleSidebar
            })
    }["SidebarProvider.useMemo[contextValue]"], [
        state,
        open,
        setOpen,
        isMobile,
        openMobile,
        setOpenMobile,
        toggleSidebar
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(SidebarContext.Provider, {
        value: contextValue,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TooltipProvider"], {
            delayDuration: 0,
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                "data-slot": "sidebar-wrapper",
                style: {
                    '--sidebar-width': SIDEBAR_WIDTH,
                    '--sidebar-width-icon': SIDEBAR_WIDTH_ICON,
                    ...style
                },
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('group/sidebar-wrapper has-data-[variant=inset]:bg-sidebar flex min-h-svh w-full', className),
                ...props,
                children: children
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 132,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
            lineNumber: 131,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 130,
        columnNumber: 5
    }, this);
}
_s1(SidebarProvider, "QSOkjq1AvKFJW5+zwiK52jPX7zI=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$hooks$2f$use$2d$mobile$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useIsMobile"]
    ];
});
_c = SidebarProvider;
function Sidebar({ side = 'left', variant = 'sidebar', collapsible = 'offcanvas', className, children, ...props }) {
    _s2();
    const { isMobile, state, openMobile, setOpenMobile } = useSidebar();
    if (collapsible === 'none') {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            "data-slot": "sidebar",
            className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-sidebar text-sidebar-foreground flex h-full w-(--sidebar-width) flex-col', className),
            ...props,
            children: children
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
            lineNumber: 170,
            columnNumber: 7
        }, this);
    }
    if (isMobile) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sheet$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Sheet"], {
            open: openMobile,
            onOpenChange: setOpenMobile,
            ...props,
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sheet$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SheetContent"], {
                "data-sidebar": "sidebar",
                "data-slot": "sidebar",
                "data-mobile": "true",
                className: "bg-sidebar text-sidebar-foreground w-(--sidebar-width) p-0 [&>button]:hidden",
                style: {
                    '--sidebar-width': SIDEBAR_WIDTH_MOBILE
                },
                side: side,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sheet$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SheetHeader"], {
                        className: "sr-only",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sheet$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SheetTitle"], {
                                children: "Sidebar"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                                lineNumber: 199,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sheet$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SheetDescription"], {
                                children: "Displays the mobile sidebar."
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                                lineNumber: 200,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                        lineNumber: 198,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex h-full w-full flex-col",
                        children: children
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                        lineNumber: 202,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 186,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
            lineNumber: 185,
            columnNumber: 7
        }, this);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "group peer text-sidebar-foreground hidden md:block",
        "data-state": state,
        "data-collapsible": state === 'collapsed' ? collapsible : '',
        "data-variant": variant,
        "data-side": side,
        "data-slot": "sidebar",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                "data-slot": "sidebar-gap",
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('relative w-(--sidebar-width) bg-transparent transition-[width] duration-200 ease-linear', 'group-data-[collapsible=offcanvas]:w-0', 'group-data-[side=right]:rotate-180', variant === 'floating' || variant === 'inset' ? 'group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4)))]' : 'group-data-[collapsible=icon]:w-(--sidebar-width-icon)')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 218,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                "data-slot": "sidebar-container",
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('fixed inset-y-0 z-10 hidden h-svh w-(--sidebar-width) transition-[left,right,width] duration-200 ease-linear md:flex', side === 'left' ? 'left-0 group-data-[collapsible=offcanvas]:left-[calc(var(--sidebar-width)*-1)]' : 'right-0 group-data-[collapsible=offcanvas]:right-[calc(var(--sidebar-width)*-1)]', // Adjust the padding for floating and inset variants.
                variant === 'floating' || variant === 'inset' ? 'p-2 group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4))+2px)]' : 'group-data-[collapsible=icon]:w-(--sidebar-width-icon) group-data-[side=left]:border-r group-data-[side=right]:border-l', className),
                ...props,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    "data-sidebar": "sidebar",
                    "data-slot": "sidebar-inner",
                    className: "bg-sidebar group-data-[variant=floating]:border-sidebar-border flex h-full w-full flex-col group-data-[variant=floating]:rounded-lg group-data-[variant=floating]:border group-data-[variant=floating]:shadow-sm",
                    children: children
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                    lineNumber: 244,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 229,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 209,
        columnNumber: 5
    }, this);
}
_s2(Sidebar, "hAL3+uRFwO9tnbDK50BUE5wZ71s=", false, function() {
    return [
        useSidebar
    ];
});
_c1 = Sidebar;
function SidebarTrigger({ className, onClick, ...props }) {
    _s3();
    const { toggleSidebar } = useSidebar();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
        "data-sidebar": "trigger",
        "data-slot": "sidebar-trigger",
        variant: "ghost",
        size: "icon",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('size-7', className),
        onClick: (event)=>{
            onClick?.(event);
            toggleSidebar();
        },
        ...props,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$panel$2d$left$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__PanelLeftIcon$3e$__["PanelLeftIcon"], {}, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 276,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                className: "sr-only",
                children: "Toggle Sidebar"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 277,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 264,
        columnNumber: 5
    }, this);
}
_s3(SidebarTrigger, "dRnjPhQbCChcVGr4xvQkpNxnqyg=", false, function() {
    return [
        useSidebar
    ];
});
_c2 = SidebarTrigger;
function SidebarRail({ className, ...props }) {
    _s4();
    const { toggleSidebar } = useSidebar();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
        "data-sidebar": "rail",
        "data-slot": "sidebar-rail",
        "aria-label": "Toggle Sidebar",
        tabIndex: -1,
        onClick: toggleSidebar,
        title: "Toggle Sidebar",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('hover:after:bg-sidebar-border absolute inset-y-0 z-20 hidden w-4 -translate-x-1/2 transition-all ease-linear group-data-[side=left]:-right-4 group-data-[side=right]:left-0 after:absolute after:inset-y-0 after:left-1/2 after:w-[2px] sm:flex', 'in-data-[side=left]:cursor-w-resize in-data-[side=right]:cursor-e-resize', '[[data-side=left][data-state=collapsed]_&]:cursor-e-resize [[data-side=right][data-state=collapsed]_&]:cursor-w-resize', 'hover:group-data-[collapsible=offcanvas]:bg-sidebar group-data-[collapsible=offcanvas]:translate-x-0 group-data-[collapsible=offcanvas]:after:left-full', '[[data-side=left][data-collapsible=offcanvas]_&]:-right-2', '[[data-side=right][data-collapsible=offcanvas]_&]:-left-2', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 286,
        columnNumber: 5
    }, this);
}
_s4(SidebarRail, "dRnjPhQbCChcVGr4xvQkpNxnqyg=", false, function() {
    return [
        useSidebar
    ];
});
_c3 = SidebarRail;
function SidebarInset({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("main", {
        "data-slot": "sidebar-inset",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-background relative flex w-full flex-1 flex-col', 'md:peer-data-[variant=inset]:m-2 md:peer-data-[variant=inset]:ml-0 md:peer-data-[variant=inset]:rounded-xl md:peer-data-[variant=inset]:shadow-sm md:peer-data-[variant=inset]:peer-data-[state=collapsed]:ml-2', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 309,
        columnNumber: 5
    }, this);
}
_c4 = SidebarInset;
function SidebarInput({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
        "data-slot": "sidebar-input",
        "data-sidebar": "input",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-background h-8 w-full shadow-none', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 326,
        columnNumber: 5
    }, this);
}
_c5 = SidebarInput;
function SidebarHeader({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-header",
        "data-sidebar": "header",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex flex-col gap-2 p-2', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 337,
        columnNumber: 5
    }, this);
}
_c6 = SidebarHeader;
function SidebarFooter({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-footer",
        "data-sidebar": "footer",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex flex-col gap-2 p-2', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 348,
        columnNumber: 5
    }, this);
}
_c7 = SidebarFooter;
function SidebarSeparator({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$separator$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Separator"], {
        "data-slot": "sidebar-separator",
        "data-sidebar": "separator",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-sidebar-border mx-2 w-auto', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 362,
        columnNumber: 5
    }, this);
}
_c8 = SidebarSeparator;
function SidebarContent({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-content",
        "data-sidebar": "content",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex min-h-0 flex-1 flex-col gap-2 overflow-auto group-data-[collapsible=icon]:overflow-hidden', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 373,
        columnNumber: 5
    }, this);
}
_c9 = SidebarContent;
function SidebarGroup({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-group",
        "data-sidebar": "group",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('relative flex w-full min-w-0 flex-col p-2', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 387,
        columnNumber: 5
    }, this);
}
_c10 = SidebarGroup;
function SidebarGroupLabel({ className, asChild = false, ...props }) {
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : 'div';
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
        "data-slot": "sidebar-group-label",
        "data-sidebar": "group-label",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-sidebar-foreground/70 ring-sidebar-ring flex h-8 shrink-0 items-center rounded-md px-2 text-xs font-medium outline-hidden transition-[margin,opacity] duration-200 ease-linear focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0', 'group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 404,
        columnNumber: 5
    }, this);
}
_c11 = SidebarGroupLabel;
function SidebarGroupAction({ className, asChild = false, ...props }) {
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : 'button';
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
        "data-slot": "sidebar-group-action",
        "data-sidebar": "group-action",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground absolute top-3.5 right-3 flex aspect-square w-5 items-center justify-center rounded-md p-0 outline-hidden transition-transform focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0', // Increases the hit area of the button on mobile.
        'after:absolute after:-inset-2 md:after:hidden', 'group-data-[collapsible=icon]:hidden', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 425,
        columnNumber: 5
    }, this);
}
_c12 = SidebarGroupAction;
function SidebarGroupContent({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-group-content",
        "data-sidebar": "group-content",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('w-full text-sm', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 445,
        columnNumber: 5
    }, this);
}
_c13 = SidebarGroupContent;
function SidebarMenu({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("ul", {
        "data-slot": "sidebar-menu",
        "data-sidebar": "menu",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex w-full min-w-0 flex-col gap-1', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 456,
        columnNumber: 5
    }, this);
}
_c14 = SidebarMenu;
function SidebarMenuItem({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
        "data-slot": "sidebar-menu-item",
        "data-sidebar": "menu-item",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('group/menu-item relative', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 467,
        columnNumber: 5
    }, this);
}
_c15 = SidebarMenuItem;
const sidebarMenuButtonVariants = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$class$2d$variance$2d$authority$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cva"])('peer/menu-button flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left text-sm outline-hidden ring-sidebar-ring transition-[width,height,padding] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 group-has-data-[sidebar=menu-action]/menu-item:pr-8 aria-disabled:pointer-events-none aria-disabled:opacity-50 data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground data-[state=open]:hover:bg-sidebar-accent data-[state=open]:hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-2! [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0', {
    variants: {
        variant: {
            default: 'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            outline: 'bg-background shadow-[0_0_0_1px_hsl(var(--sidebar-border))] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:shadow-[0_0_0_1px_hsl(var(--sidebar-accent))]'
        },
        size: {
            default: 'h-8 text-sm',
            sm: 'h-7 text-xs',
            lg: 'h-12 text-sm group-data-[collapsible=icon]:p-0!'
        }
    },
    defaultVariants: {
        variant: 'default',
        size: 'default'
    }
});
function SidebarMenuButton({ asChild = false, isActive = false, variant = 'default', size = 'default', tooltip, className, ...props }) {
    _s5();
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : 'button';
    const { isMobile, state } = useSidebar();
    const button = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
        "data-slot": "sidebar-menu-button",
        "data-sidebar": "menu-button",
        "data-size": size,
        "data-active": isActive,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])(sidebarMenuButtonVariants({
            variant,
            size
        }), className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 515,
        columnNumber: 5
    }, this);
    if (!tooltip) {
        return button;
    }
    if (typeof tooltip === 'string') {
        tooltip = {
            children: tooltip
        };
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TooltipTrigger"], {
                asChild: true,
                children: button
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 537,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tooltip$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TooltipContent"], {
                side: "right",
                align: "center",
                hidden: state !== 'collapsed' || isMobile,
                ...tooltip
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 538,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 536,
        columnNumber: 5
    }, this);
}
_s5(SidebarMenuButton, "DSCdbs8JtpmKVxCYgM7sPAZNgB0=", false, function() {
    return [
        useSidebar
    ];
});
_c16 = SidebarMenuButton;
function SidebarMenuAction({ className, asChild = false, showOnHover = false, ...props }) {
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : 'button';
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
        "data-slot": "sidebar-menu-action",
        "data-sidebar": "menu-action",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground peer-hover/menu-button:text-sidebar-accent-foreground absolute top-1.5 right-1 flex aspect-square w-5 items-center justify-center rounded-md p-0 outline-hidden transition-transform focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0', // Increases the hit area of the button on mobile.
        'after:absolute after:-inset-2 md:after:hidden', 'peer-data-[size=sm]/menu-button:top-1', 'peer-data-[size=default]/menu-button:top-1.5', 'peer-data-[size=lg]/menu-button:top-2.5', 'group-data-[collapsible=icon]:hidden', showOnHover && 'peer-data-[active=true]/menu-button:text-sidebar-accent-foreground group-focus-within/menu-item:opacity-100 group-hover/menu-item:opacity-100 data-[state=open]:opacity-100 md:opacity-0', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 560,
        columnNumber: 5
    }, this);
}
_c17 = SidebarMenuAction;
function SidebarMenuBadge({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-menu-badge",
        "data-sidebar": "menu-badge",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-sidebar-foreground pointer-events-none absolute right-1 flex h-5 min-w-5 items-center justify-center rounded-md px-1 text-xs font-medium tabular-nums select-none', 'peer-hover/menu-button:text-sidebar-accent-foreground peer-data-[active=true]/menu-button:text-sidebar-accent-foreground', 'peer-data-[size=sm]/menu-button:top-1', 'peer-data-[size=default]/menu-button:top-1.5', 'peer-data-[size=lg]/menu-button:top-2.5', 'group-data-[collapsible=icon]:hidden', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 585,
        columnNumber: 5
    }, this);
}
_c18 = SidebarMenuBadge;
function SidebarMenuSkeleton({ className, showIcon = false, ...props }) {
    _s6();
    // Random width between 50 to 90%.
    const width = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "SidebarMenuSkeleton.useMemo[width]": ()=>{
            return `${Math.floor(Math.random() * 40) + 50}%`;
        }
    }["SidebarMenuSkeleton.useMemo[width]"], []);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "sidebar-menu-skeleton",
        "data-sidebar": "menu-skeleton",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex h-8 items-center gap-2 rounded-md px-2', className),
        ...props,
        children: [
            showIcon && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Skeleton"], {
                className: "size-4 rounded-md",
                "data-sidebar": "menu-skeleton-icon"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 622,
                columnNumber: 9
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Skeleton"], {
                className: "h-4 max-w-(--skeleton-width) flex-1",
                "data-sidebar": "menu-skeleton-text",
                style: {
                    '--skeleton-width': width
                }
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
                lineNumber: 627,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 615,
        columnNumber: 5
    }, this);
}
_s6(SidebarMenuSkeleton, "nKFjX4dxbYo91VAj5VdWQ1XUe3I=");
_c19 = SidebarMenuSkeleton;
function SidebarMenuSub({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("ul", {
        "data-slot": "sidebar-menu-sub",
        "data-sidebar": "menu-sub",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('border-sidebar-border mx-3.5 flex min-w-0 translate-x-px flex-col gap-1 border-l px-2.5 py-0.5', 'group-data-[collapsible=icon]:hidden', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 642,
        columnNumber: 5
    }, this);
}
_c20 = SidebarMenuSub;
function SidebarMenuSubItem({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
        "data-slot": "sidebar-menu-sub-item",
        "data-sidebar": "menu-sub-item",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('group/menu-sub-item relative', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 660,
        columnNumber: 5
    }, this);
}
_c21 = SidebarMenuSubItem;
function SidebarMenuSubButton({ asChild = false, size = 'md', isActive = false, className, ...props }) {
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : 'a';
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
        "data-slot": "sidebar-menu-sub-button",
        "data-sidebar": "menu-sub-button",
        "data-size": size,
        "data-active": isActive,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground active:bg-sidebar-accent active:text-sidebar-accent-foreground [&>svg]:text-sidebar-accent-foreground flex h-7 min-w-0 -translate-x-px items-center gap-2 overflow-hidden rounded-md px-2 outline-hidden focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0', 'data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground', size === 'sm' && 'text-xs', size === 'md' && 'text-sm', 'group-data-[collapsible=icon]:hidden', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx",
        lineNumber: 683,
        columnNumber: 5
    }, this);
}
_c22 = SidebarMenuSubButton;
;
var _c, _c1, _c2, _c3, _c4, _c5, _c6, _c7, _c8, _c9, _c10, _c11, _c12, _c13, _c14, _c15, _c16, _c17, _c18, _c19, _c20, _c21, _c22;
__turbopack_context__.k.register(_c, "SidebarProvider");
__turbopack_context__.k.register(_c1, "Sidebar");
__turbopack_context__.k.register(_c2, "SidebarTrigger");
__turbopack_context__.k.register(_c3, "SidebarRail");
__turbopack_context__.k.register(_c4, "SidebarInset");
__turbopack_context__.k.register(_c5, "SidebarInput");
__turbopack_context__.k.register(_c6, "SidebarHeader");
__turbopack_context__.k.register(_c7, "SidebarFooter");
__turbopack_context__.k.register(_c8, "SidebarSeparator");
__turbopack_context__.k.register(_c9, "SidebarContent");
__turbopack_context__.k.register(_c10, "SidebarGroup");
__turbopack_context__.k.register(_c11, "SidebarGroupLabel");
__turbopack_context__.k.register(_c12, "SidebarGroupAction");
__turbopack_context__.k.register(_c13, "SidebarGroupContent");
__turbopack_context__.k.register(_c14, "SidebarMenu");
__turbopack_context__.k.register(_c15, "SidebarMenuItem");
__turbopack_context__.k.register(_c16, "SidebarMenuButton");
__turbopack_context__.k.register(_c17, "SidebarMenuAction");
__turbopack_context__.k.register(_c18, "SidebarMenuBadge");
__turbopack_context__.k.register(_c19, "SidebarMenuSkeleton");
__turbopack_context__.k.register(_c20, "SidebarMenuSub");
__turbopack_context__.k.register(_c21, "SidebarMenuSubItem");
__turbopack_context__.k.register(_c22, "SidebarMenuSubButton");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/entities/form/dynamic.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
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
    DynamicFormItemType["PROMPT_EDITOR"] = "prompt-editor";
    DynamicFormItemType["UNKNOWN"] = "unknown";
    DynamicFormItemType["KNOWLEDGE_BASE_SELECTOR"] = "knowledge-base-selector";
    DynamicFormItemType["KNOWLEDGE_BASE_MULTI_SELECTOR"] = "knowledge-base-multi-selector";
    DynamicFormItemType["PLUGIN_SELECTOR"] = "plugin-selector";
    DynamicFormItemType["BOT_SELECTOR"] = "bot-selector";
    return DynamicFormItemType;
}({});
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/textarea.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Textarea",
    ()=>Textarea
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
;
;
function Textarea({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("textarea", {
        "data-slot": "textarea",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30 flex field-sizing-content min-h-16 w-full rounded-md border bg-transparent px-3 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/textarea.tsx",
        lineNumber: 7,
        columnNumber: 5
    }, this);
}
_c = Textarea;
;
var _c;
__turbopack_context__.k.register(_c, "Textarea");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>DynamicFormItemComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/entities/form/dynamic.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/select.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/switch.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$textarea$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/textarea.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/card.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/checkbox.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/plus.js [app-client] (ecmascript) <export default as Plus>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/x.js [app-client] (ecmascript) <export default as X>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$eye$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Eye$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/eye.js [app-client] (ecmascript) <export default as Eye>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-client] (ecmascript) <export default as Wrench>");
;
var _s = __turbopack_context__.k.signature();
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
    _s();
    const [llmModels, setLlmModels] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [knowledgeBases, setKnowledgeBases] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [externalKnowledgeBases, setExternalKnowledgeBases] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [bots, setBots] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [uploading, setUploading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [kbDialogOpen, setKbDialogOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [tempSelectedKBIds, setTempSelectedKBIds] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [pluginSystemStatus, setPluginSystemStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const handleFileUpload = async (file)=>{
        const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
        if (file.size > MAX_FILE_SIZE) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.fileUpload.tooLarge'));
            return null;
        }
        try {
            setUploading(true);
            const response = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].uploadPluginConfigFile(file);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('plugins.fileUpload.success'));
            // 通知父组件文件已上传
            onFileUploaded?.(response.file_key);
            return {
                file_key: response.file_key,
                mimetype: file.type
            };
        } catch (error) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('plugins.fileUpload.failed') + ': ' + error.message);
            return null;
        } finally{
            setUploading(false);
        }
    };
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DynamicFormItemComponent.useEffect": ()=>{
            if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].LLM_MODEL_SELECTOR) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getProviderLLMModels().then({
                    "DynamicFormItemComponent.useEffect": (resp)=>{
                        let models = resp.models;
                        // Filter out space-chat-completions models when not logged in with space account or when models service is disabled
                        if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].disable_models_service || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["userInfo"]?.account_type !== 'space') {
                            models = models.filter({
                                "DynamicFormItemComponent.useEffect": (m)=>m.provider?.requester !== 'space-chat-completions'
                            }["DynamicFormItemComponent.useEffect"]);
                        }
                        setLlmModels(models);
                    }
                }["DynamicFormItemComponent.useEffect"]).catch({
                    "DynamicFormItemComponent.useEffect": (err)=>{
                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error('Failed to get LLM model list: ' + err.msg);
                    }
                }["DynamicFormItemComponent.useEffect"]);
            }
        }
    }["DynamicFormItemComponent.useEffect"], [
        config.type
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DynamicFormItemComponent.useEffect": ()=>{
            if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_SELECTOR || config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_MULTI_SELECTOR) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getKnowledgeBases().then({
                    "DynamicFormItemComponent.useEffect": (resp)=>{
                        setKnowledgeBases(resp.bases);
                    }
                }["DynamicFormItemComponent.useEffect"]).catch({
                    "DynamicFormItemComponent.useEffect": (err)=>{
                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error('Failed to get knowledge base list: ' + err.msg);
                    }
                }["DynamicFormItemComponent.useEffect"]);
                // Fetch plugin system status
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getPluginSystemStatus().then({
                    "DynamicFormItemComponent.useEffect": (status)=>{
                        setPluginSystemStatus(status);
                    }
                }["DynamicFormItemComponent.useEffect"]).catch({
                    "DynamicFormItemComponent.useEffect": (err)=>{
                        console.error('Failed to get plugin system status:', err);
                    }
                }["DynamicFormItemComponent.useEffect"]);
            }
        }
    }["DynamicFormItemComponent.useEffect"], [
        config.type
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DynamicFormItemComponent.useEffect": ()=>{
            if ((config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_SELECTOR || config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_MULTI_SELECTOR) && pluginSystemStatus?.is_enable && pluginSystemStatus?.is_connected) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getExternalKnowledgeBases().then({
                    "DynamicFormItemComponent.useEffect": (resp)=>{
                        setExternalKnowledgeBases(resp.bases);
                    }
                }["DynamicFormItemComponent.useEffect"]).catch({
                    "DynamicFormItemComponent.useEffect": (err)=>{
                        console.error('Failed to get external knowledge base list:', err);
                    }
                }["DynamicFormItemComponent.useEffect"]);
            }
        }
    }["DynamicFormItemComponent.useEffect"], [
        config.type,
        pluginSystemStatus
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DynamicFormItemComponent.useEffect": ()=>{
            if (config.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].BOT_SELECTOR) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getBots().then({
                    "DynamicFormItemComponent.useEffect": (resp)=>{
                        setBots(resp.bots);
                    }
                }["DynamicFormItemComponent.useEffect"]).catch({
                    "DynamicFormItemComponent.useEffect": (err)=>{
                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error('Failed to get bot list: ' + err.msg);
                    }
                }["DynamicFormItemComponent.useEffect"]);
            }
        }
    }["DynamicFormItemComponent.useEffect"], [
        config.type
    ]);
    switch(config.type){
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].INT:
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].FLOAT:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
                type: "number",
                ...field,
                onChange: (e)=>field.onChange(Number(e.target.value))
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 180,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].STRING:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
                ...field
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 188,
                columnNumber: 14
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].TEXT:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$textarea$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Textarea"], {
                ...field,
                className: "min-h-[120px]"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 191,
                columnNumber: 14
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].BOOLEAN:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Switch"], {
                checked: field.value,
                onCheckedChange: field.onChange
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 194,
                columnNumber: 14
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].STRING_ARRAY:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    field.value.map((item, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex gap-2 items-center",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
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
                                    lineNumber: 201,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    type: "button",
                                    className: "p-2 hover:bg-gray-100 rounded",
                                    onClick: ()=>{
                                        const newValue = field.value.filter((_, i)=>i !== index);
                                        field.onChange(newValue);
                                    },
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        className: "w-5 h-5 text-red-500",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 226,
                                            columnNumber: 19
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 220,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 210,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, index, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 200,
                            columnNumber: 13
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
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
                        lineNumber: 231,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 198,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].SELECT:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('common.select')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 247,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 246,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                            children: config.options?.map((option)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: option.name,
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(option.label)
                                }, option.name, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 252,
                                    columnNumber: 17
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 250,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 249,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 245,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].LLM_MODEL_SELECTOR:
            // Group models by provider
            const groupedModels = llmModels.reduce((acc, model)=>{
                const providerName = model.provider?.name || model.provider?.requester || 'Unknown';
                if (!acc[providerName]) acc[providerName] = [];
                acc[providerName].push(model);
                return acc;
            }, {});
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('models.selectModel')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 277,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 276,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: Object.entries(groupedModels).map(([providerName, models])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                        children: providerName
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 282,
                                        columnNumber: 17
                                    }, this),
                                    models.map((model)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                            value: model.uuid,
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "inline-flex items-center gap-1",
                                                children: [
                                                    model.name,
                                                    model.abilities?.includes('vision') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$eye$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Eye$3e$__["Eye"], {
                                                        className: "h-3 w-3 text-muted-foreground"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 288,
                                                        columnNumber: 25
                                                    }, this),
                                                    model.abilities?.includes('func_call') && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                                        className: "h-3 w-3 text-muted-foreground"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 291,
                                                        columnNumber: 25
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 285,
                                                columnNumber: 21
                                            }, this)
                                        }, model.uuid, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 284,
                                            columnNumber: 19
                                        }, this))
                                ]
                            }, providerName, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 281,
                                columnNumber: 15
                            }, this))
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 279,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 275,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_SELECTOR:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('knowledge.selectKnowledgeBase')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 306,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 305,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: "__none__",
                                    children: t('knowledge.empty')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 310,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 309,
                                columnNumber: 13
                            }, this),
                            knowledgeBases.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                        children: t('knowledge.builtIn')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 315,
                                        columnNumber: 17
                                    }, this),
                                    knowledgeBases.map((base)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                            value: base.uuid ?? '',
                                            children: base.name
                                        }, base.uuid, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 317,
                                            columnNumber: 19
                                        }, this))
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 314,
                                columnNumber: 15
                            }, this),
                            externalKnowledgeBases.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectLabel"], {
                                        children: t('knowledge.external')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 326,
                                        columnNumber: 17
                                    }, this),
                                    externalKnowledgeBases.map((base)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                            value: base.uuid ?? '',
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "flex items-center gap-2",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                                        src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getPluginIconURL(base.plugin_author, base.plugin_name),
                                                        alt: "plugin icon",
                                                        className: "w-4 h-4 rounded-[8%] flex-shrink-0"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 330,
                                                        columnNumber: 23
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        children: base.name
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 338,
                                                        columnNumber: 23
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 329,
                                                columnNumber: 21
                                            }, this)
                                        }, base.uuid, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 328,
                                            columnNumber: 19
                                        }, this))
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 325,
                                columnNumber: 15
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 308,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 304,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].KNOWLEDGE_BASE_MULTI_SELECTOR:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "space-y-2",
                        children: field.value && field.value.length > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "space-y-2",
                            children: field.value.map((kbId)=>{
                                const kb = knowledgeBases.find((base)=>base.uuid === kbId);
                                const externalKb = externalKnowledgeBases.find((base)=>base.uuid === kbId);
                                const currentKb = kb || externalKb;
                                if (!currentKb) return null;
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between rounded-lg border p-3 hover:bg-accent",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex items-center gap-2 flex-1",
                                            children: [
                                                externalKb && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                                    src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getPluginIconURL(externalKb.plugin_author, externalKb.plugin_name),
                                                    alt: "plugin icon",
                                                    className: "w-8 h-8 rounded-[8%] flex-shrink-0"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                    lineNumber: 369,
                                                    columnNumber: 27
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "flex-1 min-w-0",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "font-medium",
                                                            children: currentKb.name
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                            lineNumber: 379,
                                                            columnNumber: 27
                                                        }, this),
                                                        currentKb.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "text-sm text-muted-foreground",
                                                            children: currentKb.description
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                            lineNumber: 381,
                                                            columnNumber: 29
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                    lineNumber: 378,
                                                    columnNumber: 25
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 367,
                                            columnNumber: 23
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            type: "button",
                                            variant: "ghost",
                                            size: "icon",
                                            onClick: ()=>{
                                                const newValue = field.value.filter((id)=>id !== kbId);
                                                field.onChange(newValue);
                                            },
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__["X"], {
                                                className: "h-4 w-4"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 398,
                                                columnNumber: 25
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 387,
                                            columnNumber: 23
                                        }, this)
                                    ]
                                }, kbId, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 363,
                                    columnNumber: 21
                                }, this);
                            })
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 353,
                            columnNumber: 15
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-sm text-muted-foreground",
                                children: t('knowledge.noKnowledgeBaseSelected')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 406,
                                columnNumber: 17
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 405,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 351,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                        type: "button",
                        onClick: ()=>{
                            setTempSelectedKBIds(field.value || []);
                            setKbDialogOpen(true);
                        },
                        variant: "outline",
                        className: "w-full",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__["Plus"], {
                                className: "mr-2 h-4 w-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 422,
                                columnNumber: 13
                            }, this),
                            t('knowledge.addKnowledgeBase')
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 413,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
                        open: kbDialogOpen,
                        onOpenChange: setKbDialogOpen,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                            className: "max-w-2xl max-h-[80vh] overflow-hidden flex flex-col",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                        children: t('knowledge.selectKnowledgeBases')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 430,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 429,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex-1 overflow-y-auto space-y-4 pr-2",
                                    children: [
                                        knowledgeBases.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "space-y-2",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "text-sm font-semibold text-muted-foreground px-2",
                                                    children: t('knowledge.builtIn')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                    lineNumber: 436,
                                                    columnNumber: 21
                                                }, this),
                                                knowledgeBases.map((base)=>{
                                                    const isSelected = tempSelectedKBIds.includes(base.uuid ?? '');
                                                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer",
                                                        onClick: ()=>{
                                                            const kbId = base.uuid ?? '';
                                                            setTempSelectedKBIds((prev)=>prev.includes(kbId) ? prev.filter((id)=>id !== kbId) : [
                                                                    ...prev,
                                                                    kbId
                                                                ]);
                                                        },
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Checkbox"], {
                                                                checked: isSelected,
                                                                "aria-label": `Select ${base.name}`
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 456,
                                                                columnNumber: 27
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "flex-1",
                                                                children: [
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "font-medium",
                                                                        children: base.name
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                        lineNumber: 461,
                                                                        columnNumber: 29
                                                                    }, this),
                                                                    base.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "text-sm text-muted-foreground",
                                                                        children: base.description
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                        lineNumber: 463,
                                                                        columnNumber: 31
                                                                    }, this)
                                                                ]
                                                            }, void 0, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 460,
                                                                columnNumber: 27
                                                            }, this)
                                                        ]
                                                    }, base.uuid, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 444,
                                                        columnNumber: 25
                                                    }, this);
                                                })
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 435,
                                            columnNumber: 19
                                        }, this),
                                        externalKnowledgeBases.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "space-y-2",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "text-sm font-semibold text-muted-foreground px-2",
                                                    children: t('knowledge.external')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                    lineNumber: 477,
                                                    columnNumber: 21
                                                }, this),
                                                externalKnowledgeBases.map((base)=>{
                                                    const isSelected = tempSelectedKBIds.includes(base.uuid ?? '');
                                                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer",
                                                        onClick: ()=>{
                                                            const kbId = base.uuid ?? '';
                                                            setTempSelectedKBIds((prev)=>prev.includes(kbId) ? prev.filter((id)=>id !== kbId) : [
                                                                    ...prev,
                                                                    kbId
                                                                ]);
                                                        },
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Checkbox"], {
                                                                checked: isSelected,
                                                                "aria-label": `Select ${base.name}`
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 497,
                                                                columnNumber: 27
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                                                src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["httpClient"].getPluginIconURL(base.plugin_author, base.plugin_name),
                                                                alt: "plugin icon",
                                                                className: "w-8 h-8 rounded-[8%] flex-shrink-0"
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 501,
                                                                columnNumber: 27
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "flex-1",
                                                                children: [
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "font-medium",
                                                                        children: base.name
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                        lineNumber: 510,
                                                                        columnNumber: 29
                                                                    }, this),
                                                                    base.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "text-sm text-muted-foreground",
                                                                        children: base.description
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                        lineNumber: 512,
                                                                        columnNumber: 31
                                                                    }, this)
                                                                ]
                                                            }, void 0, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                                lineNumber: 509,
                                                                columnNumber: 27
                                                            }, this)
                                                        ]
                                                    }, base.uuid, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 485,
                                                        columnNumber: 25
                                                    }, this);
                                                })
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 476,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 432,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogFooter"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "outline",
                                            onClick: ()=>setKbDialogOpen(false),
                                            children: t('common.cancel')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 524,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            onClick: ()=>{
                                                field.onChange(tempSelectedKBIds);
                                                setKbDialogOpen(false);
                                            },
                                            children: t('common.confirm')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 530,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 523,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 428,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 427,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].BOT_SELECTOR:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Select"], {
                value: field.value,
                onValueChange: field.onChange,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                        className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectValue"], {
                            placeholder: t('bots.selectBot')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 548,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 547,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectContent"], {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                            children: bots.map((bot)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: bot.uuid ?? '',
                                    children: bot.name
                                }, bot.uuid, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 553,
                                    columnNumber: 17
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 551,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 550,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 546,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].PROMPT_EDITOR:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    field.value.map((item, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex gap-2 items-center",
                            children: [
                                index === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "w-[120px] px-3 py-2 border rounded bg-gray-50 dark:bg-[#2a292e] text-gray-500 dark:text-white dark:border-gray-600",
                                    children: "system"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 570,
                                    columnNumber: 19
                                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Select"], {
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
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                                            className: "w-[120px] bg-[#ffffff] dark:bg-[#2a2a2e]",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectValue"], {}, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 583,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 582,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectContent"], {
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectGroup"], {
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                        value: "user",
                                                        children: "user"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 587,
                                                        columnNumber: 25
                                                    }, this),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                                        value: "assistant",
                                                        children: "assistant"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                        lineNumber: 588,
                                                        columnNumber: 25
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 586,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 585,
                                            columnNumber: 21
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 574,
                                    columnNumber: 19
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$textarea$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Textarea"], {
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
                                    lineNumber: 594,
                                    columnNumber: 17
                                }, this),
                                index !== 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    type: "button",
                                    className: "p-2 hover:bg-gray-100 rounded",
                                    onClick: ()=>{
                                        const newValue = field.value.filter(// eslint-disable-next-line @typescript-eslint/no-explicit-any
                                        (_, i)=>i !== index);
                                        field.onChange(newValue);
                                    },
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        className: "w-5 h-5 text-red-500",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 625,
                                            columnNumber: 23
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 619,
                                        columnNumber: 21
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 608,
                                    columnNumber: 19
                                }, this)
                            ]
                        }, index, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 567,
                            columnNumber: 15
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
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
                        lineNumber: 632,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 564,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].FILE:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: field.value && field.value.file_key ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Card"], {
                    className: "py-3 max-w-full overflow-hidden bg-gray-900",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardContent"], {
                        className: "flex items-center gap-3 p-0 px-4 min-w-0",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex-1 min-w-0 overflow-hidden",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-sm font-medium truncate",
                                        title: field.value.file_key,
                                        children: field.value.file_key
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 651,
                                        columnNumber: 19
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-xs text-muted-foreground truncate",
                                        children: field.value.mimetype
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 657,
                                        columnNumber: 19
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 650,
                                columnNumber: 17
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
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
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                    xmlns: "http://www.w3.org/2000/svg",
                                    viewBox: "0 0 24 24",
                                    fill: "currentColor",
                                    className: "w-4 h-4 text-destructive",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                        d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 679,
                                        columnNumber: 21
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 673,
                                    columnNumber: 19
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 661,
                                columnNumber: 17
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 649,
                        columnNumber: 15
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                    lineNumber: 648,
                    columnNumber: 13
                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "relative",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
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
                            lineNumber: 686,
                            columnNumber: 15
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                            type: "button",
                            variant: "outline",
                            size: "sm",
                            disabled: uploading,
                            onClick: ()=>document.getElementById(`file-input-${config.name}`)?.click(),
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                    className: "w-4 h-4 mr-2",
                                    xmlns: "http://www.w3.org/2000/svg",
                                    viewBox: "0 0 24 24",
                                    fill: "currentColor",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                        d: "M11 11V5H13V11H19V13H13V19H11V13H5V11H11Z"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 718,
                                        columnNumber: 19
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                    lineNumber: 712,
                                    columnNumber: 17
                                }, this),
                                uploading ? t('plugins.fileUpload.uploading') : t('plugins.fileUpload.chooseFile')
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 703,
                            columnNumber: 15
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                    lineNumber: 685,
                    columnNumber: 13
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 646,
                columnNumber: 9
            }, this);
        case __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$entities$2f$form$2f$dynamic$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DynamicFormItemType"].FILE_ARRAY:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-2",
                children: [
                    field.value?.map((fileConfig, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Card"], {
                            className: "py-3 max-w-full overflow-hidden bg-gray-900",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardContent"], {
                                className: "flex items-center gap-3 p-0 px-4 min-w-0",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex-1 min-w-0 overflow-hidden",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-sm font-medium truncate",
                                                title: fileConfig.file_key,
                                                children: fileConfig.file_key
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 740,
                                                columnNumber: 21
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-xs text-muted-foreground truncate",
                                                children: fileConfig.mimetype
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 746,
                                                columnNumber: 21
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 739,
                                        columnNumber: 19
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
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
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            viewBox: "0 0 24 24",
                                            fill: "currentColor",
                                            className: "w-4 h-4 text-destructive",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                d: "M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                                lineNumber: 771,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 765,
                                            columnNumber: 21
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 750,
                                        columnNumber: 19
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 738,
                                columnNumber: 17
                            }, this)
                        }, index, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                            lineNumber: 734,
                            columnNumber: 15
                        }, this)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "relative",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
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
                                lineNumber: 779,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                type: "button",
                                variant: "outline",
                                size: "sm",
                                disabled: uploading,
                                onClick: ()=>document.getElementById(`file-array-input-${config.name}`)?.click(),
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        className: "w-4 h-4 mr-2",
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M11 11V5H13V11H19V13H13V19H11V13H5V11H11Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                            lineNumber: 813,
                                            columnNumber: 17
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                        lineNumber: 807,
                                        columnNumber: 15
                                    }, this),
                                    uploading ? t('plugins.fileUpload.uploading') : t('plugins.fileUpload.addFile')
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                                lineNumber: 796,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                        lineNumber: 778,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 731,
                columnNumber: 9
            }, this);
        default:
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
                ...field
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx",
                lineNumber: 824,
                columnNumber: 14
            }, this);
    }
}
_s(DynamicFormItemComponent, "XMiUSmN9JR00iVa/lojk5pwhTh8=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"]
    ];
});
_c = DynamicFormItemComponent;
var _c;
__turbopack_context__.k.register(_c, "DynamicFormItemComponent");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>DynamicFormComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-hook-form/dist/index.esm.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@hookform/resolvers/zod/dist/zod.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/zod/v3/external.js [app-client] (ecmascript) <export * as z>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/form.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormItemComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
;
;
;
;
;
function DynamicFormComponent({ itemConfigList, onSubmit, initialValues, onFileUploaded }) {
    _s();
    const isInitialMount = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(true);
    const previousInitialValues = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(initialValues);
    // 根据 itemConfigList 动态生成 zod schema
    const formSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object(itemConfigList.reduce((acc, item)=>{
        let fieldSchema;
        switch(item.type){
            case 'integer':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number();
                break;
            case 'float':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number();
                break;
            case 'boolean':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].boolean();
                break;
            case 'string':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'array[string]':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string());
                break;
            case 'select':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'llm-model-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'knowledge-base-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'knowledge-base-multi-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string());
                break;
            case 'bot-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'prompt-editor':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                    content: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                    role: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
                }));
                break;
            default:
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
        }
        if (item.required && (fieldSchema instanceof __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodString || fieldSchema instanceof __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodArray)) {
            fieldSchema = fieldSchema.min(1, {
                message: '此字段为必填项'
            });
        }
        return {
            ...acc,
            [item.name]: fieldSchema
        };
    }, {}));
    const form = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useForm"])({
        resolver: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["zodResolver"])(formSchema),
        defaultValues: itemConfigList.reduce({
            "DynamicFormComponent.useForm[form]": (acc, item)=>{
                // 优先使用 initialValues，如果没有则使用默认值
                const value = initialValues?.[item.name] ?? item.default;
                return {
                    ...acc,
                    [item.name]: value
                };
            }
        }["DynamicFormComponent.useForm[form]"], {})
    });
    // 当 initialValues 变化时更新表单值
    // 但要避免因为内部表单更新触发的 onSubmit 导致的 initialValues 变化而重新设置表单
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DynamicFormComponent.useEffect": ()=>{
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
                const mergedValues = itemConfigList.reduce({
                    "DynamicFormComponent.useEffect.mergedValues": (acc, item)=>{
                        acc[item.name] = initialValues[item.name] ?? item.default;
                        return acc;
                    }
                }["DynamicFormComponent.useEffect.mergedValues"], {});
                Object.entries(mergedValues).forEach({
                    "DynamicFormComponent.useEffect": ([key, value])=>{
                        form.setValue(key, value);
                    }
                }["DynamicFormComponent.useEffect"]);
                previousInitialValues.current = initialValues;
            }
        }
    }["DynamicFormComponent.useEffect"], [
        initialValues,
        form,
        itemConfigList
    ]);
    // Stable ref for onSubmit to avoid re-triggering the effect when the
    // parent passes a new closure on every render.
    const onSubmitRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(onSubmit);
    onSubmitRef.current = onSubmit;
    // 监听表单值变化
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DynamicFormComponent.useEffect": ()=>{
            // Emit initial form values immediately so the parent always has a valid snapshot,
            // even if the user saves without modifying any field.
            // form.watch(callback) only fires on subsequent changes, not on mount.
            const formValues = form.getValues();
            const initialFinalValues = itemConfigList.reduce({
                "DynamicFormComponent.useEffect.initialFinalValues": (acc, item)=>{
                    acc[item.name] = formValues[item.name] ?? item.default;
                    return acc;
                }
            }["DynamicFormComponent.useEffect.initialFinalValues"], {});
            onSubmitRef.current?.(initialFinalValues);
            const subscription = form.watch({
                "DynamicFormComponent.useEffect.subscription": ()=>{
                    const formValues = form.getValues();
                    const finalValues = itemConfigList.reduce({
                        "DynamicFormComponent.useEffect.subscription.finalValues": (acc, item)=>{
                            acc[item.name] = formValues[item.name] ?? item.default;
                            return acc;
                        }
                    }["DynamicFormComponent.useEffect.subscription.finalValues"], {});
                    onSubmitRef.current?.(finalValues);
                }
            }["DynamicFormComponent.useEffect.subscription"]);
            return ({
                "DynamicFormComponent.useEffect": ()=>subscription.unsubscribe()
            })["DynamicFormComponent.useEffect"];
        }
    }["DynamicFormComponent.useEffect"], [
        form,
        itemConfigList
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Form"], {
        ...form,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "space-y-4",
            children: itemConfigList.map((config)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormField"], {
                    control: form.control,
                    name: config.name,
                    render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormItem"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormLabel"], {
                                    children: [
                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(config.label),
                                        ' ',
                                        config.required && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "text-red-500",
                                            children: "*"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                            lineNumber: 190,
                                            columnNumber: 39
                                        }, void 0)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 188,
                                    columnNumber: 17
                                }, void 0),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormControl"], {
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormItemComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                        config: config,
                                        field: field,
                                        onFileUploaded: onFileUploaded
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                        lineNumber: 193,
                                        columnNumber: 19
                                    }, void 0)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 192,
                                    columnNumber: 17
                                }, void 0),
                                config.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-muted-foreground",
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(config.description)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 200,
                                    columnNumber: 19
                                }, void 0),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                                    lineNumber: 204,
                                    columnNumber: 17
                                }, void 0)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                            lineNumber: 187,
                            columnNumber: 15
                        }, void 0)
                }, config.id, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
                    lineNumber: 182,
                    columnNumber: 11
                }, this))
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
            lineNumber: 180,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx",
        lineNumber: 179,
        columnNumber: 5
    }, this);
}
_s(DynamicFormComponent, "kuXhsumfe/Dl8+iDlBp4X2i5dpw=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useForm"]
    ];
});
_c = DynamicFormComponent;
var _c;
__turbopack_context__.k.register(_c, "DynamicFormComponent");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>N8nAuthFormComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-hook-form/dist/index.esm.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@hookform/resolvers/zod/dist/zod.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/zod/v3/external.js [app-client] (ecmascript) <export * as z>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/form.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormItemComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
;
;
;
;
;
function N8nAuthFormComponent({ itemConfigList, onSubmit, initialValues }) {
    _s();
    // 当前选择的认证类型
    const [authType, setAuthType] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(initialValues?.['auth-type'] || 'none');
    // 根据 itemConfigList 动态生成 zod schema
    const formSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object(itemConfigList.reduce((acc, item)=>{
        let fieldSchema;
        switch(item.type){
            case 'integer':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number();
                break;
            case 'float':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number();
                break;
            case 'boolean':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].boolean();
                break;
            case 'string':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'array[string]':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string());
                break;
            case 'select':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'llm-model-selector':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
                break;
            case 'prompt-editor':
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                    content: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                    role: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
                }));
                break;
            default:
                fieldSchema = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string();
        }
        if (item.required && (fieldSchema instanceof __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodString || fieldSchema instanceof __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].ZodArray)) {
            fieldSchema = fieldSchema.min(1, {
                message: '此字段为必填项'
            });
        }
        return {
            ...acc,
            [item.name]: fieldSchema
        };
    }, {}));
    const form = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useForm"])({
        resolver: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["zodResolver"])(formSchema),
        defaultValues: itemConfigList.reduce({
            "N8nAuthFormComponent.useForm[form]": (acc, item)=>{
                // 优先使用 initialValues，如果没有则使用默认值
                const value = initialValues?.[item.name] ?? item.default;
                return {
                    ...acc,
                    [item.name]: value
                };
            }
        }["N8nAuthFormComponent.useForm[form]"], {})
    });
    // 当 initialValues 变化时更新表单值
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "N8nAuthFormComponent.useEffect": ()=>{
            if (initialValues) {
                // 合并默认值和初始值
                const mergedValues = itemConfigList.reduce({
                    "N8nAuthFormComponent.useEffect.mergedValues": (acc, item)=>{
                        acc[item.name] = initialValues[item.name] ?? item.default;
                        return acc;
                    }
                }["N8nAuthFormComponent.useEffect.mergedValues"], {});
                Object.entries(mergedValues).forEach({
                    "N8nAuthFormComponent.useEffect": ([key, value])=>{
                        form.setValue(key, value);
                    }
                }["N8nAuthFormComponent.useEffect"]);
                // 更新认证类型
                setAuthType(mergedValues['auth-type'] || 'none');
            }
        }
    }["N8nAuthFormComponent.useEffect"], [
        initialValues,
        form,
        itemConfigList
    ]);
    // 监听表单值变化
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "N8nAuthFormComponent.useEffect": ()=>{
            const subscription = form.watch({
                "N8nAuthFormComponent.useEffect.subscription": (value, { name })=>{
                    // 如果认证类型变化，更新状态
                    if (name === 'auth-type') {
                        setAuthType(value['auth-type']);
                    }
                    // 获取完整的表单值，确保包含所有默认值
                    const formValues = form.getValues();
                    const finalValues = itemConfigList.reduce({
                        "N8nAuthFormComponent.useEffect.subscription.finalValues": (acc, item)=>{
                            acc[item.name] = formValues[item.name] ?? item.default;
                            return acc;
                        }
                    }["N8nAuthFormComponent.useEffect.subscription.finalValues"], {});
                    onSubmit?.(finalValues);
                }
            }["N8nAuthFormComponent.useEffect.subscription"]);
            return ({
                "N8nAuthFormComponent.useEffect": ()=>subscription.unsubscribe()
            })["N8nAuthFormComponent.useEffect"];
        }
    }["N8nAuthFormComponent.useEffect"], [
        form,
        onSubmit,
        itemConfigList
    ]);
    // 根据认证类型过滤表单项
    const filteredConfigList = itemConfigList.filter((config)=>{
        // 始终显示webhook-url、auth-type、timeout和output-key
        if ([
            'webhook-url',
            'auth-type',
            'timeout',
            'output-key'
        ].includes(config.name)) {
            return true;
        }
        // 根据认证类型显示相应的表单项
        if (authType === 'basic' && config.name.startsWith('basic-')) {
            return true;
        }
        if (authType === 'jwt' && config.name.startsWith('jwt-')) {
            return true;
        }
        if (authType === 'header' && config.name.startsWith('header-')) {
            return true;
        }
        return false;
    });
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Form"], {
        ...form,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "space-y-4",
            children: filteredConfigList.map((config)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormField"], {
                    control: form.control,
                    name: config.name,
                    render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormItem"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormLabel"], {
                                    children: [
                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(config.label),
                                        ' ',
                                        config.required && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "text-red-500",
                                            children: "*"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                                            lineNumber: 186,
                                            columnNumber: 39
                                        }, void 0)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                                    lineNumber: 184,
                                    columnNumber: 17
                                }, void 0),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormControl"], {
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormItemComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                        config: config,
                                        field: field
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                                        lineNumber: 189,
                                        columnNumber: 19
                                    }, void 0)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                                    lineNumber: 188,
                                    columnNumber: 17
                                }, void 0),
                                config.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-muted-foreground",
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(config.description)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                                    lineNumber: 192,
                                    columnNumber: 19
                                }, void 0),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                                    lineNumber: 196,
                                    columnNumber: 17
                                }, void 0)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                            lineNumber: 183,
                            columnNumber: 15
                        }, void 0)
                }, config.id, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
                    lineNumber: 178,
                    columnNumber: 11
                }, this))
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
            lineNumber: 176,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx",
        lineNumber: 175,
        columnNumber: 5
    }, this);
}
_s(N8nAuthFormComponent, "OBkKlHlRcmYtv12lrXdxPUZq3gI=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useForm"]
    ];
});
_c = N8nAuthFormComponent;
var _c;
__turbopack_context__.k.register(_c, "N8nAuthFormComponent");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>EmojiPicker
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/popover.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
;
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
        '🎭'
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
        '🗳️'
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
        '🔹'
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
        '🌻'
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
        '🎈'
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
        '💽'
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
        '🧫'
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
        '🏭'
    ]
};
const CATEGORY_LABELS = {
    common: '常用',
    objects: '物品',
    symbols: '符号',
    nature: '自然',
    faces: '表情',
    tech: '科技',
    science: '科学',
    business: '商业'
};
// 每个分类的代表性 emoji（用于分页按钮）
const CATEGORY_ICONS = {
    common: '⭐',
    objects: '📦',
    symbols: '🔴',
    nature: '🌟',
    faces: '😀',
    tech: '💻',
    science: '🔬',
    business: '💼'
};
function EmojiPicker({ value, onChange, disabled }) {
    _s();
    const [open, setOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [activeCategory, setActiveCategory] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('common');
    const handleEmojiSelect = (emoji)=>{
        onChange(emoji);
        setOpen(false);
    };
    const currentEmojis = EMOJI_CATEGORIES[activeCategory];
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Popover"], {
        open: open,
        onOpenChange: setOpen,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PopoverTrigger"], {
                asChild: true,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                    variant: "outline",
                    disabled: disabled,
                    className: "w-16 h-16 text-3xl p-0 hover:bg-gray-100 dark:hover:bg-gray-800",
                    type: "button",
                    children: value || '😀'
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                    lineNumber: 197,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                lineNumber: 196,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$popover$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PopoverContent"], {
                className: "w-80 p-4",
                align: "start",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "space-y-3",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                            className: "text-sm font-medium text-gray-700 dark:text-gray-300",
                            children: CATEGORY_LABELS[activeCategory]
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                            lineNumber: 209,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "grid grid-cols-6 gap-1",
                            children: currentEmojis.map((emoji, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    type: "button",
                                    onClick: ()=>handleEmojiSelect(emoji),
                                    className: `w-10 h-10 text-xl rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center justify-center ${value === emoji ? 'bg-gray-200 dark:bg-gray-700' : ''}`,
                                    children: emoji
                                }, `${activeCategory}-${index}`, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                                    lineNumber: 216,
                                    columnNumber: 15
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                            lineNumber: 214,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "pt-2 border-t border-gray-200 dark:border-gray-700",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex justify-center gap-1",
                                children: Object.keys(EMOJI_CATEGORIES).map((category)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        type: "button",
                                        onClick: ()=>setActiveCategory(category),
                                        className: `w-7 h-7 text-base rounded transition-colors flex items-center justify-center ${activeCategory === category ? 'bg-gray-200 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`,
                                        title: CATEGORY_LABELS[category],
                                        children: CATEGORY_ICONS[category]
                                    }, category, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                                        lineNumber: 233,
                                        columnNumber: 17
                                    }, this))
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                                lineNumber: 231,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                            lineNumber: 230,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                    lineNumber: 207,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
                lineNumber: 206,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx",
        lineNumber: 195,
        columnNumber: 5
    }, this);
}
_s(EmojiPicker, "YOzijlB835QGtM1WxY50T7DBtYQ=");
_c = EmojiPicker;
var _c;
__turbopack_context__.k.register(_c, "EmojiPicker");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PipelineFormComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/tabs.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/DynamicFormComponent.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$N8nAuthFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/components/dynamic-form/N8nAuthFormComponent.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-hook-form/dist/index.esm.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@hookform/resolvers/zod/dist/zod.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/zod/v3/external.js [app-client] (ecmascript) <export * as z>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$emoji$2d$picker$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/emoji-picker.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/form.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/i18n/I18nProvider.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
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
function PipelineFormComponent({ onFinish, onNewPipelineCreated, isEditMode, pipelineId, showButtons = true, onDeletePipeline, onCancel }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [showDeleteConfirm, setShowDeleteConfirm] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [showCopyConfirm, setShowCopyConfirm] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [isDefaultPipeline, setIsDefaultPipeline] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const formSchema = isEditMode ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        basic: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            name: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().min(1, {
                message: t('pipelines.nameRequired')
            }),
            description: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().min(1, {
                message: t('pipelines.descriptionRequired')
            }),
            emoji: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
        }),
        ai: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()),
        trigger: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()),
        safety: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()),
        output: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any())
    }) : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        basic: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            name: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().min(1, {
                message: t('pipelines.nameRequired')
            }),
            description: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().min(1, {
                message: t('pipelines.descriptionRequired')
            }),
            emoji: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
        }),
        ai: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()).optional(),
        trigger: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()).optional(),
        safety: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()).optional(),
        output: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()).optional()
    });
    // 这里不好，可以改成enum等
    const formLabelList = isEditMode ? [
        {
            label: t('pipelines.basicInfo'),
            name: 'basic'
        },
        {
            label: t('pipelines.aiCapabilities'),
            name: 'ai'
        },
        {
            label: t('pipelines.triggerConditions'),
            name: 'trigger'
        },
        {
            label: t('pipelines.safetyControls'),
            name: 'safety'
        },
        {
            label: t('pipelines.outputProcessing'),
            name: 'output'
        }
    ] : [
        {
            label: t('pipelines.basicInfo'),
            name: 'basic'
        }
    ];
    const [aiConfigTabSchema, setAIConfigTabSchema] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const [triggerConfigTabSchema, setTriggerConfigTabSchema] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const [safetyConfigTabSchema, setSafetyConfigTabSchema] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const [outputConfigTabSchema, setOutputConfigTabSchema] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const form = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useForm"])({
        resolver: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$hookform$2f$resolvers$2f$zod$2f$dist$2f$zod$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["zodResolver"])(formSchema),
        defaultValues: {
            basic: {
                emoji: '⚙️'
            },
            ai: {},
            trigger: {},
            safety: {},
            output: {}
        }
    });
    // Track unsaved changes by comparing current form values against a saved snapshot
    const savedSnapshotRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])('');
    const watchedValues = form.watch();
    const hasUnsavedChanges = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "PipelineFormComponent.useMemo[hasUnsavedChanges]": ()=>{
            if (!isEditMode || !savedSnapshotRef.current) return false;
            return JSON.stringify(watchedValues) !== savedSnapshotRef.current;
        }
    }["PipelineFormComponent.useMemo[hasUnsavedChanges]"], [
        isEditMode,
        watchedValues
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PipelineFormComponent.useEffect": ()=>{
            // get config schema from metadata
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getGeneralPipelineMetadata().then({
                "PipelineFormComponent.useEffect": (resp)=>{
                    for (const config of resp.configs){
                        if (config.name === 'ai') {
                            setAIConfigTabSchema(config);
                        } else if (config.name === 'trigger') {
                            setTriggerConfigTabSchema(config);
                        } else if (config.name === 'safety') {
                            setSafetyConfigTabSchema(config);
                        } else if (config.name === 'output') {
                            setOutputConfigTabSchema(config);
                        }
                    }
                }
            }["PipelineFormComponent.useEffect"]);
            if (isEditMode) {
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPipeline(pipelineId || '').then({
                    "PipelineFormComponent.useEffect": (resp)=>{
                        setIsDefaultPipeline(resp.pipeline.is_default ?? false);
                        const loadedValues = {
                            basic: {
                                name: resp.pipeline.name,
                                description: resp.pipeline.description,
                                emoji: resp.pipeline.emoji || '⚙️'
                            },
                            ai: resp.pipeline.config.ai,
                            trigger: resp.pipeline.config.trigger,
                            safety: resp.pipeline.config.safety,
                            output: resp.pipeline.config.output
                        };
                        form.reset(loadedValues);
                        savedSnapshotRef.current = JSON.stringify(loadedValues);
                    }
                }["PipelineFormComponent.useEffect"]);
            }
        }
    }["PipelineFormComponent.useEffect"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PipelineFormComponent.useEffect": ()=>{
            if (!isEditMode) {
                form.reset({
                    basic: {
                        name: '',
                        description: '',
                        emoji: '⚙️'
                    }
                });
            }
        }
    }["PipelineFormComponent.useEffect"], [
        form,
        isEditMode
    ]);
    function handleFormSubmit(values) {
        if (isEditMode) {
            handleModify(values);
        } else {
            handleCreate(values);
        }
    }
    function handleCreate(values) {
        const pipeline = {
            config: {},
            description: values.basic.description,
            name: values.basic.name,
            emoji: values.basic.emoji
        };
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].createPipeline(pipeline).then((resp)=>{
            onFinish();
            onNewPipelineCreated(resp.uuid);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('pipelines.createSuccess'));
        }).catch((err)=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.createError') + err.msg);
        });
    }
    function handleModify(values) {
        const realConfig = {
            ai: values.ai,
            trigger: values.trigger,
            safety: values.safety,
            output: values.output
        };
        const pipeline = {
            config: realConfig,
            // created_at: '',
            description: values.basic.description,
            // for_version: '',
            name: values.basic.name,
            emoji: values.basic.emoji
        };
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].updatePipeline(pipelineId || '', pipeline).then(()=>{
            savedSnapshotRef.current = JSON.stringify(form.getValues());
            onFinish();
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('pipelines.saveSuccess'));
        }).catch((err)=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.saveError') + err.msg);
        });
    }
    function renderDynamicForms(stage, formName) {
        // 如果是 AI 配置，需要特殊处理
        if (formName === 'ai') {
            // 获取当前选择的 runner
            const currentRunner = form.watch('ai.runner.runner');
            // 如果是 runner 配置项，直接渲染
            if (stage.name === 'runner') {
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "space-y-4 mb-6",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-lg font-medium",
                            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(stage.label)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 251,
                            columnNumber: 13
                        }, this),
                        stage.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-sm text-gray-500",
                            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(stage.description)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 255,
                            columnNumber: 15
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                            itemConfigList: stage.config,
                            initialValues: // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            form.watch(formName)?.[stage.name] || {},
                            onSubmit: (values)=>{
                                const currentValues = // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                form.getValues(formName) || {};
                                form.setValue(formName, {
                                    ...currentValues,
                                    [stage.name]: values
                                });
                            }
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 259,
                            columnNumber: 13
                        }, this)
                    ]
                }, stage.name, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 250,
                    columnNumber: 11
                }, this);
            }
            // 如果不是当前选择的 runner 对应的配置项，则不渲染
            if (stage.name !== currentRunner) {
                return null;
            }
            // 对于n8n-service-api配置，使用N8nAuthFormComponent处理表单联动
            if (stage.name === 'n8n-service-api') {
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "space-y-4 mb-6",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-lg font-medium",
                            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(stage.label)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 289,
                            columnNumber: 13
                        }, this),
                        stage.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-sm text-gray-500",
                            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(stage.description)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 293,
                            columnNumber: 15
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$N8nAuthFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                            itemConfigList: stage.config,
                            initialValues: // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            form.watch(formName)?.[stage.name] || {},
                            onSubmit: (values)=>{
                                const currentValues = // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                form.getValues(formName) || {};
                                form.setValue(formName, {
                                    ...currentValues,
                                    [stage.name]: values
                                });
                            }
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 297,
                            columnNumber: 13
                        }, this)
                    ]
                }, stage.name, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 288,
                    columnNumber: 11
                }, this);
            }
        }
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "space-y-4 mb-6",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "text-lg font-medium",
                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(stage.label)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 321,
                    columnNumber: 9
                }, this),
                stage.description && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "text-sm text-gray-500",
                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$i18n$2f$I18nProvider$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractI18nObject"])(stage.description)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 325,
                    columnNumber: 11
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$components$2f$dynamic$2d$form$2f$DynamicFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                    itemConfigList: stage.config,
                    initialValues: // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    form.watch(formName)?.[stage.name] || {},
                    onSubmit: (values)=>{
                        const currentValues = // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        form.getValues(formName) || {};
                        form.setValue(formName, {
                            ...currentValues,
                            [stage.name]: values
                        });
                    }
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 329,
                    columnNumber: 9
                }, this)
            ]
        }, stage.name, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
            lineNumber: 320,
            columnNumber: 7
        }, this);
    }
    const handleDelete = ()=>{
        setShowDeleteConfirm(true);
    };
    const confirmDelete = ()=>{
        if (pipelineId) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].deletePipeline(pipelineId).then(()=>{
                onDeletePipeline();
                setShowDeleteConfirm(false);
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('pipelines.deleteSuccess'));
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.deleteError') + err.msg);
            });
        }
    };
    const handleCopy = ()=>{
        setShowCopyConfirm(true);
    };
    const confirmCopy = ()=>{
        if (pipelineId) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].copyPipeline(pipelineId).then(()=>{
                onFinish();
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('common.copySuccess'));
                setShowCopyConfirm(false);
                onCancel();
            }).catch((err)=>{
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.createError') + err.msg);
            });
        }
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "!max-w-[70vw] max-w-6xl h-full p-0 flex flex-col bg-white dark:bg-black",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Form"], {
                    ...form,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                            id: "pipeline-form",
                            onSubmit: form.handleSubmit(handleFormSubmit),
                            className: "h-full flex flex-col flex-1 min-h-0 mb-2",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex-1 flex flex-col min-h-0",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tabs"], {
                                    defaultValue: formLabelList[0].name,
                                    className: "h-full flex flex-col flex-1 min-h-0",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsList"], {
                                            children: formLabelList.map((formLabel)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                                    value: formLabel.name,
                                                    children: formLabel.label
                                                }, formLabel.name, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                    lineNumber: 404,
                                                    columnNumber: 21
                                                }, this))
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                            lineNumber: 402,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            id: "pipeline-form-content",
                                            className: "flex-1 overflow-y-auto min-h-0",
                                            children: formLabelList.map((formLabel)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsContent"], {
                                                    value: formLabel.name,
                                                    className: "overflow-y-auto max-h-full",
                                                    children: [
                                                        formLabel.name === 'basic' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "space-y-6",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "flex gap-4 items-start",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormField"], {
                                                                            control: form.control,
                                                                            name: "basic.name",
                                                                            render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormItem"], {
                                                                                    className: "flex-1",
                                                                                    children: [
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                                                            children: [
                                                                                                t('common.name'),
                                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                                    className: "text-red-500",
                                                                                                    children: "*"
                                                                                                }, void 0, false, {
                                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                                    lineNumber: 431,
                                                                                                    columnNumber: 37
                                                                                                }, void 0)
                                                                                            ]
                                                                                        }, void 0, true, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 429,
                                                                                            columnNumber: 35
                                                                                        }, void 0),
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormControl"], {
                                                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
                                                                                                ...field
                                                                                            }, void 0, false, {
                                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                                lineNumber: 434,
                                                                                                columnNumber: 37
                                                                                            }, void 0)
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 433,
                                                                                            columnNumber: 35
                                                                                        }, void 0),
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 436,
                                                                                            columnNumber: 35
                                                                                        }, void 0)
                                                                                    ]
                                                                                }, void 0, true, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                    lineNumber: 428,
                                                                                    columnNumber: 33
                                                                                }, void 0)
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                            lineNumber: 424,
                                                                            columnNumber: 29
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormField"], {
                                                                            control: form.control,
                                                                            name: "basic.emoji",
                                                                            render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormItem"], {
                                                                                    children: [
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                                                            children: t('common.icon')
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 445,
                                                                                            columnNumber: 35
                                                                                        }, void 0),
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormControl"], {
                                                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$emoji$2d$picker$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                                                                                value: field.value,
                                                                                                onChange: field.onChange
                                                                                            }, void 0, false, {
                                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                                lineNumber: 447,
                                                                                                columnNumber: 37
                                                                                            }, void 0)
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 446,
                                                                                            columnNumber: 35
                                                                                        }, void 0),
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 452,
                                                                                            columnNumber: 35
                                                                                        }, void 0)
                                                                                    ]
                                                                                }, void 0, true, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                    lineNumber: 444,
                                                                                    columnNumber: 33
                                                                                }, void 0)
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                            lineNumber: 440,
                                                                            columnNumber: 29
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                    lineNumber: 423,
                                                                    columnNumber: 27
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormField"], {
                                                                    control: form.control,
                                                                    name: "basic.description",
                                                                    render: ({ field })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormItem"], {
                                                                            children: [
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormLabel"], {
                                                                                    children: [
                                                                                        t('common.description'),
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                            className: "text-red-500",
                                                                                            children: "*"
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                            lineNumber: 465,
                                                                                            columnNumber: 35
                                                                                        }, void 0)
                                                                                    ]
                                                                                }, void 0, true, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                    lineNumber: 463,
                                                                                    columnNumber: 33
                                                                                }, void 0),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormControl"], {
                                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
                                                                                        ...field
                                                                                    }, void 0, false, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                        lineNumber: 468,
                                                                                        columnNumber: 35
                                                                                    }, void 0)
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                    lineNumber: 467,
                                                                                    columnNumber: 33
                                                                                }, void 0),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$form$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormMessage"], {}, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                                    lineNumber: 470,
                                                                                    columnNumber: 33
                                                                                }, void 0)
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                            lineNumber: 462,
                                                                            columnNumber: 31
                                                                        }, void 0)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                    lineNumber: 458,
                                                                    columnNumber: 27
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                            lineNumber: 421,
                                                            columnNumber: 25
                                                        }, this),
                                                        isEditMode && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                                            children: [
                                                                formLabel.name === 'ai' && aiConfigTabSchema && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "space-y-6",
                                                                    children: aiConfigTabSchema.stages.map((stage)=>renderDynamicForms(stage, 'ai'))
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                    lineNumber: 480,
                                                                    columnNumber: 29
                                                                }, this),
                                                                formLabel.name === 'trigger' && triggerConfigTabSchema && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "space-y-6",
                                                                    children: triggerConfigTabSchema.stages.map((stage)=>renderDynamicForms(stage, 'trigger'))
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                    lineNumber: 489,
                                                                    columnNumber: 31
                                                                }, this),
                                                                formLabel.name === 'safety' && safetyConfigTabSchema && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "space-y-6",
                                                                    children: safetyConfigTabSchema.stages.map((stage)=>renderDynamicForms(stage, 'safety'))
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                    lineNumber: 498,
                                                                    columnNumber: 31
                                                                }, this),
                                                                formLabel.name === 'output' && outputConfigTabSchema && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "space-y-6",
                                                                    children: outputConfigTabSchema.stages.map((stage)=>renderDynamicForms(stage, 'output'))
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                                    lineNumber: 507,
                                                                    columnNumber: 31
                                                                }, this)
                                                            ]
                                                        }, void 0, true)
                                                    ]
                                                }, formLabel.name, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                                    lineNumber: 415,
                                                    columnNumber: 21
                                                }, this))
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                            lineNumber: 410,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 398,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                lineNumber: 397,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 392,
                            columnNumber: 11
                        }, this),
                        showButtons && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex justify-end items-center gap-2 pt-4 border-t mb-0 bg-white dark:bg-black sticky bottom-0 z-10",
                            children: [
                                isEditMode && hasUnsavedChanges && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "text-amber-600 dark:text-amber-400 text-sm flex items-center gap-1.5 mr-auto",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "inline-block w-1.5 h-1.5 rounded-full bg-amber-500"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                            lineNumber: 526,
                                            columnNumber: 19
                                        }, this),
                                        t('pipelines.unsavedChanges')
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 525,
                                    columnNumber: 17
                                }, this),
                                isEditMode && !isDefaultPipeline && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    type: "button",
                                    variant: "destructive",
                                    onClick: handleDelete,
                                    children: t('common.delete')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 532,
                                    columnNumber: 17
                                }, this),
                                isEditMode && isDefaultPipeline && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "text-gray-500 text-sm h-full flex items-center mr-2",
                                    children: t('pipelines.defaultPipelineCannotDelete')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 542,
                                    columnNumber: 17
                                }, this),
                                isEditMode && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    type: "button",
                                    variant: "default",
                                    onClick: handleCopy,
                                    className: "bg-green-600 hover:bg-green-700 text-white",
                                    children: t('common.copy')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 548,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    type: "submit",
                                    form: "pipeline-form",
                                    children: isEditMode ? t('common.save') : t('common.submit')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 558,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    type: "button",
                                    variant: "outline",
                                    onClick: onCancel,
                                    children: t('common.cancel')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 561,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 523,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 391,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                lineNumber: 390,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
                open: showDeleteConfirm,
                onOpenChange: setShowDeleteConfirm,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                children: t('common.confirmDelete')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                lineNumber: 573,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 572,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "py-4",
                            children: t('pipelines.deleteConfirmation')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 575,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogFooter"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "outline",
                                    onClick: ()=>setShowDeleteConfirm(false),
                                    children: t('common.cancel')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 577,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "destructive",
                                    onClick: confirmDelete,
                                    children: t('common.confirmDelete')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 583,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 576,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 571,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                lineNumber: 570,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
                open: showCopyConfirm,
                onOpenChange: setShowCopyConfirm,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                children: t('pipelines.copyConfirmTitle')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                lineNumber: 594,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 593,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "py-4",
                            children: t('pipelines.copyConfirmation')
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 596,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogFooter"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "outline",
                                    onClick: ()=>setShowCopyConfirm(false),
                                    children: t('common.cancel')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 598,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    onClick: confirmCopy,
                                    children: t('common.confirm')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                                    lineNumber: 601,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                            lineNumber: 597,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                    lineNumber: 592,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx",
                lineNumber: 591,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true);
}
_s(PipelineFormComponent, "11+QuOIlEY7smLPv24uYCud+7NY=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"],
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$hook$2d$form$2f$dist$2f$index$2e$esm$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useForm"]
    ];
});
_c = PipelineFormComponent;
var _c;
__turbopack_context__.k.register(_c, "PipelineFormComponent");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ScrollArea",
    ()=>ScrollArea,
    "ScrollBar",
    ()=>ScrollBar
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$scroll$2d$area$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-scroll-area/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
'use client';
;
;
;
function ScrollArea({ className, children, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$scroll$2d$area$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Root"], {
        "data-slot": "scroll-area",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('relative', className),
        ...props,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$scroll$2d$area$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Viewport"], {
                "data-slot": "scroll-area-viewport",
                className: "focus-visible:ring-ring/50 size-full rounded-[inherit] transition-[color,box-shadow] outline-none focus-visible:ring-[3px] focus-visible:outline-1",
                children: children
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx",
                lineNumber: 19,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(ScrollBar, {}, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx",
                lineNumber: 25,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$scroll$2d$area$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Corner"], {}, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx",
                lineNumber: 26,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx",
        lineNumber: 14,
        columnNumber: 5
    }, this);
}
_c = ScrollArea;
function ScrollBar({ className, orientation = 'vertical', ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$scroll$2d$area$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ScrollAreaScrollbar"], {
        "data-slot": "scroll-area-scrollbar",
        orientation: orientation,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex touch-none p-px transition-colors select-none', orientation === 'vertical' && 'h-full w-2.5 border-l border-l-transparent', orientation === 'horizontal' && 'h-2.5 flex-col border-t border-t-transparent', className),
        ...props,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$scroll$2d$area$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ScrollAreaThumb"], {
            "data-slot": "scroll-area-thumb",
            className: "bg-border relative flex-1 rounded-full"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx",
            lineNumber: 50,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx",
        lineNumber: 37,
        columnNumber: 5
    }, this);
}
_c1 = ScrollBar;
;
var _c, _c1;
__turbopack_context__.k.register(_c, "ScrollArea");
__turbopack_context__.k.register(_c1, "ScrollBar");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/AtBadge.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>AtBadge
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/x.js [app-client] (ecmascript) <export default as X>");
;
;
;
function AtBadge({ targetName, readonly = false, onRemove }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
        variant: "secondary",
        className: "flex items-center gap-1 px-2 py-1 text-sm bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/60",
        children: [
            "@",
            targetName,
            !readonly && onRemove && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                onClick: onRemove,
                className: "ml-1 hover:text-blue-800 dark:hover:text-blue-200 focus:outline-none",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__["X"], {
                    className: "h-3 w-3"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/AtBadge.tsx",
                    lineNumber: 26,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/AtBadge.tsx",
                lineNumber: 22,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/AtBadge.tsx",
        lineNumber: 16,
        columnNumber: 5
    }, this);
}
_c = AtBadge;
var _c;
__turbopack_context__.k.register(_c, "AtBadge");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/websocket/WebSocketClient.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * WebSocket客户端类
 * 用于管理WebSocket连接和消息处理
 */ __turbopack_context__.s([
    "WebSocketClient",
    ()=>WebSocketClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
class WebSocketClient {
    pipelineId;
    sessionType;
    token;
    ws;
    connectionId;
    reconnectAttempts;
    maxReconnectAttempts;
    reconnectDelay;
    heartbeatInterval;
    heartbeatIntervalMs;
    isConnecting;
    // 事件回调
    onConnectedCallback;
    onMessageCallback;
    onErrorCallback;
    onCloseCallback;
    onBroadcastCallback;
    constructor(pipelineId, sessionType = 'person', token){
        this.pipelineId = pipelineId;
        this.sessionType = sessionType;
        this.token = token;
        this.ws = null;
        this.connectionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000; // 3秒重连间隔
        this.heartbeatInterval = null;
        this.heartbeatIntervalMs = 30000; // 30秒
        this.isConnecting = false; // 防止重复连接
    }
    /**
   * 连接到WebSocket服务器
   */ connect() {
        return new Promise((resolve, reject)=>{
            try {
                // 防止重复连接
                if (this.isConnecting || this.ws && this.ws.readyState === WebSocket.CONNECTING) {
                    console.warn('WebSocket正在连接中，忽略重复连接请求');
                    reject(new Error('Connection already in progress'));
                    return;
                }
                // 如果已经连接，直接返回
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    console.warn('WebSocket已连接，忽略重复连接请求');
                    resolve(this.connectionId || '');
                    return;
                }
                this.isConnecting = true;
                // 构建WebSocket URL
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                // extract host from process.env.NEXT_PUBLIC_API_BASE_URL
                // 如果环境变量未定义,使用当前页面的 host (适配生产环境)
                const host = ("TURBOPACK compile-time value", "http://us-ca-cloudcone-03.rockchin.top:5300")?.split('://')[1] || window.location.host;
                const url = `${protocol}//${host}/api/v1/pipelines/${this.pipelineId}/ws/connect?session_type=${this.sessionType}`;
                this.ws = new WebSocket(url);
                // 连接打开
                this.ws.onopen = ()=>{
                    this.reconnectAttempts = 0;
                    this.isConnecting = false;
                    this.startHeartbeat();
                };
                // 接收消息
                this.ws.onmessage = (event)=>{
                    try {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                        // 第一次连接成功
                        if (data.type === 'connected' && data.connection_id) {
                            this.connectionId = data.connection_id;
                            resolve(data.connection_id);
                        }
                    } catch (error) {
                        console.error('解析WebSocket消息失败:', error);
                        this.onErrorCallback?.(error);
                    }
                };
                // 连接关闭
                this.ws.onclose = ()=>{
                    this.isConnecting = false;
                    this.stopHeartbeat();
                    this.onCloseCallback?.();
                    // 自动重连
                    if (this.reconnectAttempts < this.maxReconnectAttempts) {
                        this.reconnectAttempts++;
                        setTimeout(()=>{
                            this.connect().catch(console.error);
                        }, this.reconnectDelay * this.reconnectAttempts);
                    }
                };
                // 连接错误
                this.ws.onerror = (event)=>{
                    console.error('WebSocket错误:', event);
                    this.isConnecting = false;
                    const error = new Error('WebSocket连接失败');
                    this.onErrorCallback?.(error);
                    reject(error);
                };
            } catch (error) {
                this.isConnecting = false;
                reject(error);
            }
        });
    }
    /**
   * 处理接收到的消息
   */ handleMessage(data) {
        switch(data.type){
            case 'connected':
                this.onConnectedCallback?.(data);
                break;
            case 'response':
                // 检查 session_type 是否匹配 - 如果消息没有 session_type 或者不匹配当前session，都忽略
                if (!data.session_type || data.session_type !== this.sessionType) {
                    // 忽略不匹配的 session_type 消息
                    console.debug(`忽略不匹配的消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`);
                    break;
                }
                if (data.data) {
                    this.onMessageCallback?.(data.data);
                }
                break;
            case 'user_message':
                // 检查 session_type 是否匹配 - 如果消息没有 session_type 或者不匹配当前session，都忽略
                if (!data.session_type || data.session_type !== this.sessionType) {
                    // 忽略不匹配的 session_type 消息
                    console.debug(`忽略不匹配的用户消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`);
                    break;
                }
                // 用户消息广播（包括自己发送的消息）
                if (data.data) {
                    this.onMessageCallback?.(data.data);
                }
                break;
            case 'pong':
                break;
            case 'broadcast':
                if (data.message) {
                    this.onBroadcastCallback?.(data.message);
                }
                break;
            case 'error':
                const error = new Error(data.message || '未知错误');
                this.onErrorCallback?.(error);
                break;
            default:
                console.warn('未知消息类型:', data);
        }
    }
    /**
   * 发送消息
   */ sendMessage(messageChain, stream = true) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket未连接');
        }
        const message = {
            type: 'message',
            message: messageChain,
            stream: stream
        };
        this.ws.send(JSON.stringify(message));
    }
    /**
   * 发送心跳
   */ sendHeartbeat() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            return;
        }
        this.ws.send(JSON.stringify({
            type: 'ping'
        }));
    }
    /**
   * 启动心跳
   */ startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatInterval = setInterval(()=>{
            this.sendHeartbeat();
        }, this.heartbeatIntervalMs);
    }
    /**
   * 停止心跳
   */ stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    /**
   * 断开连接
   */ disconnect() {
        if (this.ws) {
            this.stopHeartbeat();
            // 停止自动重连
            this.reconnectAttempts = this.maxReconnectAttempts;
            // 发送断开消息
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'disconnect'
                }));
            }
            this.ws.close();
            this.ws = null;
            this.connectionId = null;
            this.isConnecting = false;
        }
    }
    /**
   * 获取连接ID
   */ getConnectionId() {
        return this.connectionId;
    }
    /**
   * 获取连接状态
   */ isConnected() {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }
    // ===== 事件回调设置 =====
    onConnected(callback) {
        this.onConnectedCallback = callback;
        return this;
    }
    onMessage(callback) {
        this.onMessageCallback = callback;
        return this;
    }
    onError(callback) {
        this.onErrorCallback = callback;
        return this;
    }
    onClose(callback) {
        this.onCloseCallback = callback;
        return this;
    }
    onBroadcast(callback) {
        this.onBroadcastCallback = callback;
        return this;
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>ImagePreviewDialog
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
;
function ImagePreviewDialog({ open, imageUrl, onClose }) {
    if (!open) return null;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "fixed inset-0 z-[100] flex items-center justify-center p-8 animate-in fade-in duration-200",
        onClick: onClose,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "absolute inset-0 bg-black/20 "
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
                lineNumber: 22,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "relative z-10 flex flex-col items-center gap-2",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        onClick: onClose,
                        className: "self-end w-9 h-9 rounded-full bg-white hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-100 shadow-lg transition-all hover:scale-105 flex items-center justify-center",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                            className: "w-4 h-4",
                            fill: "none",
                            viewBox: "0 0 24 24",
                            stroke: "currentColor",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                strokeLinecap: "round",
                                strokeLinejoin: "round",
                                strokeWidth: 2,
                                d: "M6 18L18 6M6 6l12 12"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
                                lineNumber: 37,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
                            lineNumber: 31,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
                        lineNumber: 27,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                        src: imageUrl,
                        alt: "Preview",
                        className: "max-w-[50vw] max-h-[50vh] object-contain rounded-lg shadow-2xl bg-white",
                        onClick: (e)=>e.stopPropagation()
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
                        lineNumber: 47,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
                lineNumber: 25,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx",
        lineNumber: 17,
        columnNumber: 5
    }, this);
}
_c = ImagePreviewDialog;
var _c;
__turbopack_context__.k.register(_c, "ImagePreviewDialog");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>DebugDialog
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/input.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$scroll$2d$area$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/scroll-area.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/switch.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$AtBadge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/AtBadge.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$websocket$2f$WebSocketClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/websocket/WebSocketClient.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$ImagePreviewDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$markdown$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__Markdown__as__default$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-markdown/lib/index.js [app-client] (ecmascript) <export Markdown as default>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$remark$2d$gfm$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/remark-gfm/lib/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$highlight$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-highlight/lib/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$raw$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-raw/lib/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$slug$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-slug/lib/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$autolink$2d$headings$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/rehype-autolink-headings/lib/index.js [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
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
function DebugDialog({ open, pipelineId, isEmbedded = false, onConnectionStatusChange }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [selectedPipelineId, setSelectedPipelineId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(pipelineId);
    const [sessionType, setSessionType] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('person');
    const [messages, setMessages] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [inputValue, setInputValue] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const [showAtPopover, setShowAtPopover] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [hasAt, setHasAt] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [isHovering, setIsHovering] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [isConnected, setIsConnected] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [selectedImages, setSelectedImages] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [isUploading, setIsUploading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [previewImageUrl, setPreviewImageUrl] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const [showImagePreview, setShowImagePreview] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [quotedMessage, setQuotedMessage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [rawModeMessages, setRawModeMessages] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(new Set());
    const [streamOutput, setStreamOutput] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(true);
    const messagesEndRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const inputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const popoverRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const fileInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const wsClientRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const isInitializingRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(false);
    const scrollToBottom = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "DebugDialog.useCallback[scrollToBottom]": ()=>{
            // 使用setTimeout确保在DOM更新后执行滚动
            setTimeout({
                "DebugDialog.useCallback[scrollToBottom]": ()=>{
                    const scrollArea = document.querySelector('.scroll-area');
                    if (scrollArea) {
                        scrollArea.scrollTo({
                            top: scrollArea.scrollHeight,
                            behavior: 'smooth'
                        });
                    }
                    // 同时确保messagesEndRef也滚动到视图
                    messagesEndRef.current?.scrollIntoView({
                        behavior: 'smooth'
                    });
                }
            }["DebugDialog.useCallback[scrollToBottom]"], 0);
        }
    }["DebugDialog.useCallback[scrollToBottom]"], []);
    const loadMessages = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "DebugDialog.useCallback[loadMessages]": async (pipelineId)=>{
            try {
                const response = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getWebSocketHistoryMessages(pipelineId, sessionType);
                setMessages(response.messages);
            } catch (error) {
                console.error('Failed to load messages:', error);
            }
        }
    }["DebugDialog.useCallback[loadMessages]"], [
        sessionType
    ]);
    // 初始化WebSocket连接
    const initWebSocket = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "DebugDialog.useCallback[initWebSocket]": async (pipelineId)=>{
            // 防止重复初始化
            if (isInitializingRef.current) {
                return;
            }
            try {
                isInitializingRef.current = true;
                // 断开旧连接
                if (wsClientRef.current) {
                    wsClientRef.current.disconnect();
                    wsClientRef.current = null;
                }
                // 创建新连接
                const wsClient = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$websocket$2f$WebSocketClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["WebSocketClient"](pipelineId, sessionType);
                wsClient.onConnected({
                    "DebugDialog.useCallback[initWebSocket]": ()=>{
                        setIsConnected(true);
                        isInitializingRef.current = false;
                    }
                }["DebugDialog.useCallback[initWebSocket]"]).onMessage({
                    "DebugDialog.useCallback[initWebSocket]": (wsMessage)=>{
                        // 将 WebSocketMessage 转换为 Message 类型
                        const message = {
                            ...wsMessage,
                            message_chain: wsMessage.message_chain
                        };
                        setMessages({
                            "DebugDialog.useCallback[initWebSocket]": (prevMessages)=>{
                                // 查找是否已存在相同ID的消息
                                const existingIndex = prevMessages.findIndex({
                                    "DebugDialog.useCallback[initWebSocket].existingIndex": (m)=>m.id === message.id
                                }["DebugDialog.useCallback[initWebSocket].existingIndex"]);
                                if (existingIndex >= 0) {
                                    // 更新已存在的消息（流式输出）
                                    const newMessages = [
                                        ...prevMessages
                                    ];
                                    newMessages[existingIndex] = message;
                                    return newMessages;
                                } else {
                                    // 添加新消息
                                    return [
                                        ...prevMessages,
                                        message
                                    ];
                                }
                            }
                        }["DebugDialog.useCallback[initWebSocket]"]);
                    }
                }["DebugDialog.useCallback[initWebSocket]"]).onError({
                    "DebugDialog.useCallback[initWebSocket]": (error)=>{
                        console.error('WebSocket错误:', error);
                        setIsConnected(false);
                        isInitializingRef.current = false;
                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.debugDialog.connectionError'));
                    }
                }["DebugDialog.useCallback[initWebSocket]"]).onClose({
                    "DebugDialog.useCallback[initWebSocket]": ()=>{
                        setIsConnected(false);
                        isInitializingRef.current = false;
                    }
                }["DebugDialog.useCallback[initWebSocket]"]).onBroadcast({
                    "DebugDialog.useCallback[initWebSocket]": (message)=>{
                        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].info(message);
                    }
                }["DebugDialog.useCallback[initWebSocket]"]);
                await wsClient.connect();
                wsClientRef.current = wsClient;
            } catch (error) {
                console.error('WebSocket连接失败:', error);
                setIsConnected(false);
                isInitializingRef.current = false;
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.debugDialog.connectionFailed'));
            }
        }
    }["DebugDialog.useCallback[initWebSocket]"], [
        sessionType,
        t
    ]);
    // 在useEffect中监听messages变化时滚动
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DebugDialog.useEffect": ()=>{
            scrollToBottom();
        }
    }["DebugDialog.useEffect"], [
        messages,
        scrollToBottom
    ]);
    // 监听 open 和 pipelineId 变化，进入时连接，离开时断开
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DebugDialog.useEffect": ()=>{
            if (open) {
                setSelectedPipelineId(pipelineId);
            } else {
                // 关闭对话框时立即断开WebSocket
                if (wsClientRef.current) {
                    wsClientRef.current.disconnect();
                    wsClientRef.current = null;
                    setIsConnected(false);
                    isInitializingRef.current = false;
                }
            }
            return ({
                "DebugDialog.useEffect": ()=>{
                    // 组件卸载时断开WebSocket
                    if (wsClientRef.current) {
                        wsClientRef.current.disconnect();
                        wsClientRef.current = null;
                        isInitializingRef.current = false;
                    }
                }
            })["DebugDialog.useEffect"];
        }
    }["DebugDialog.useEffect"], [
        open,
        pipelineId
    ]);
    // 监听 sessionType 和 selectedPipelineId 变化，重新加载消息和连接
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DebugDialog.useEffect": ()=>{
            if (open) {
                // 清空当前消息，避免显示旧的消息
                setMessages([]);
                loadMessages(selectedPipelineId);
                initWebSocket(selectedPipelineId);
            }
        }
    }["DebugDialog.useEffect"], [
        sessionType,
        selectedPipelineId,
        open,
        loadMessages,
        initWebSocket
    ]);
    // 通知父组件连接状态变化
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DebugDialog.useEffect": ()=>{
            onConnectionStatusChange?.(isConnected);
        }
    }["DebugDialog.useEffect"], [
        isConnected,
        onConnectionStatusChange
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DebugDialog.useEffect": ()=>{
            const handleClickOutside = {
                "DebugDialog.useEffect.handleClickOutside": (event)=>{
                    if (popoverRef.current && !popoverRef.current.contains(event.target) && !inputRef.current?.contains(event.target)) {
                        setShowAtPopover(false);
                    }
                }
            }["DebugDialog.useEffect.handleClickOutside"];
            document.addEventListener('mousedown', handleClickOutside);
            return ({
                "DebugDialog.useEffect": ()=>{
                    document.removeEventListener('mousedown', handleClickOutside);
                }
            })["DebugDialog.useEffect"];
        }
    }["DebugDialog.useEffect"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "DebugDialog.useEffect": ()=>{
            if (showAtPopover) {
                setIsHovering(true);
            }
        }
    }["DebugDialog.useEffect"], [
        showAtPopover
    ]);
    const handleInputChange = (e)=>{
        const value = e.target.value;
        if (sessionType === 'group') {
            if (value.endsWith('@')) {
                setShowAtPopover(true);
            } else if (showAtPopover && (!value.includes('@') || value.length > 1)) {
                setShowAtPopover(false);
            }
        }
        setInputValue(value);
    };
    const handleAtSelect = ()=>{
        setHasAt(true);
        setShowAtPopover(false);
        setInputValue(inputValue.slice(0, -1));
    };
    const handleAtRemove = ()=>{
        setHasAt(false);
    };
    const handleKeyPress = (e)=>{
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (showAtPopover) {
                handleAtSelect();
            } else {
                sendMessage();
            }
        } else if (e.key === 'Backspace' && hasAt && inputValue === '') {
            handleAtRemove();
        }
    };
    const handleImageSelect = async (e)=>{
        const files = e.target.files;
        if (!files || files.length === 0) return;
        const newImages = [];
        for(let i = 0; i < files.length; i++){
            const file = files[i];
            if (file.type.startsWith('image/')) {
                const preview = URL.createObjectURL(file);
                newImages.push({
                    file,
                    preview
                });
            }
        }
        setSelectedImages((prev)=>[
                ...prev,
                ...newImages
            ]);
    };
    const handleRemoveImage = (index)=>{
        setSelectedImages((prev)=>{
            const newImages = [
                ...prev
            ];
            URL.revokeObjectURL(newImages[index].preview);
            newImages.splice(index, 1);
            return newImages;
        });
    };
    const sendMessage = async ()=>{
        if (!inputValue.trim() && !hasAt && selectedImages.length === 0 && !quotedMessage) return;
        if (!isConnected || !wsClientRef.current) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.debugDialog.notConnected'));
            return;
        }
        try {
            setIsUploading(true);
            const messageChain = [];
            // 添加引用消息(如果有)
            if (quotedMessage) {
                // 获取被引用消息的Source组件以获取message_id
                const sourceComponent = quotedMessage.message_chain.find((c)=>c.type === 'Source');
                const messageId = sourceComponent ? sourceComponent.id : quotedMessage.id;
                messageChain.push({
                    type: 'Quote',
                    id: messageId,
                    origin: quotedMessage.message_chain.filter((c)=>c.type !== 'Source')
                });
            }
            let text_content = inputValue.trim();
            if (hasAt) {
                text_content = ' ' + text_content;
            }
            if (hasAt) {
                messageChain.push({
                    type: 'At',
                    target: 'websocketbot',
                    display: 'websocketbot'
                });
            }
            // 添加文本
            if (text_content) {
                messageChain.push({
                    type: 'Plain',
                    text: text_content
                });
            }
            // 上传图片并添加到消息链
            for (const image of selectedImages){
                try {
                    const result = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].uploadWebSocketImage(selectedPipelineId, image.file);
                    messageChain.push({
                        type: 'Image',
                        path: result.file_key
                    });
                } catch (error) {
                    console.error('图片上传失败:', error);
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.debugDialog.imageUploadFailed'));
                }
            }
            // 清空输入框、图片和引用消息
            setInputValue('');
            setHasAt(false);
            setQuotedMessage(null);
            selectedImages.forEach((img)=>URL.revokeObjectURL(img.preview));
            setSelectedImages([]);
            // 通过WebSocket发送消息
            // 不在本地添加消息，等待后端广播回来（带有正确的ID）
            wsClientRef.current.sendMessage(messageChain, streamOutput);
        } catch (error) {
            console.error('Failed to send message:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.debugDialog.sendFailed'));
        } finally{
            setIsUploading(false);
            inputRef.current?.focus();
        }
    };
    const renderMessageComponent = (component, index)=>{
        switch(component.type){
            case 'Plain':
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    children: component.text
                }, index, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 405,
                    columnNumber: 16
                }, this);
            case 'At':
                {
                    const atComponent = component;
                    // 优先使用 display，如果没有则使用 target
                    const displayName = atComponent.display || atComponent.target?.toString() || '';
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "inline-flex align-middle mx-1",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$AtBadge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                            targetName: displayName,
                            readonly: true
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 414,
                            columnNumber: 13
                        }, this)
                    }, index, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 413,
                        columnNumber: 11
                    }, this);
                }
            case 'AtAll':
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    className: "inline-flex align-middle mx-1",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$AtBadge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                        targetName: "全体成员",
                        readonly: true
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 422,
                        columnNumber: 13
                    }, this)
                }, index, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 421,
                    columnNumber: 11
                }, this);
            case 'Image':
                {
                    const img = component;
                    const imageUrl = img.url || (img.base64 ? img.base64 : '');
                    if (!imageUrl) return null;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "my-2",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: imageUrl,
                            alt: "Image",
                            className: "max-w-full max-h-96 rounded-lg cursor-pointer hover:opacity-90 transition-opacity",
                            onClick: ()=>{
                                setPreviewImageUrl(imageUrl);
                                setShowImagePreview(true);
                            }
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 434,
                            columnNumber: 13
                        }, this)
                    }, index, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 433,
                        columnNumber: 11
                    }, this);
                }
            case 'File':
                {
                    const file = component;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "my-2 flex items-center gap-2 text-sm",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                className: "w-4 h-4",
                                fill: "currentColor",
                                viewBox: "0 0 20 20",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 452,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 451,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: [
                                    "[文件] ",
                                    file.name || 'Unknown'
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 454,
                                columnNumber: 13
                            }, this)
                        ]
                    }, index, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 450,
                        columnNumber: 11
                    }, this);
                }
            case 'Voice':
                {
                    const voice = component;
                    const voiceUrl = voice.url || (voice.base64 ? voice.base64 : '');
                    if (!voiceUrl) {
                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            children: "[语音]"
                        }, index, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 464,
                            columnNumber: 18
                        }, this);
                    }
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "my-2 flex items-center gap-2",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                    className: "w-5 h-5",
                                    fill: "currentColor",
                                    viewBox: "0 0 20 20",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                        d: "M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 471,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 470,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("audio", {
                                    controls: true,
                                    src: voiceUrl,
                                    className: "h-8",
                                    style: {
                                        maxWidth: '200px'
                                    },
                                    children: "Your browser does not support the audio element."
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 473,
                                    columnNumber: 15
                                }, this),
                                voice.length && voice.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "text-xs text-gray-500 dark:text-gray-400",
                                    children: [
                                        voice.length,
                                        "s"
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 482,
                                    columnNumber: 17
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 469,
                            columnNumber: 13
                        }, this)
                    }, index, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 468,
                        columnNumber: 11
                    }, this);
                }
            case 'Quote':
                {
                    const quote = component;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "mb-2 pl-3 border-l-2 border-gray-400 dark:border-gray-500",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "text-sm opacity-75",
                            children: quote.origin?.map((comp, idx)=>renderMessageComponent(comp, idx))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 498,
                            columnNumber: 13
                        }, this)
                    }, index, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 494,
                        columnNumber: 11
                    }, this);
                }
            case 'Source':
                // Source 不显示
                return null;
            default:
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    children: [
                        "[",
                        component.type,
                        "]"
                    ]
                }, index, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 512,
                    columnNumber: 16
                }, this);
        }
    };
    const getMessageTimestamp = (message)=>{
        // 首先尝试从message_chain中的Source组件获取时间戳
        const sourceComponent = message.message_chain.find((c)=>c.type === 'Source');
        if (sourceComponent && sourceComponent.timestamp) {
            return sourceComponent.timestamp;
        }
        // 如果没有Source组件，使用message.timestamp
        // 假设timestamp是ISO字符串，转换为Unix时间戳（秒）
        if (message.timestamp) {
            return Math.floor(new Date(message.timestamp).getTime() / 1000);
        }
        return 0;
    };
    const formatTimestamp = (timestamp)=>{
        if (!timestamp) return '';
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        // 判断是否是今天
        const isToday = now.toDateString() === date.toDateString();
        if (isToday) {
            return `${hours}:${minutes}`;
        }
        // 判断是否是昨天
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        const isYesterday = yesterday.toDateString() === date.toDateString();
        if (isYesterday) {
            return `${t('bots.yesterday')} ${hours}:${minutes}`;
        }
        // 判断是否是今年
        const isThisYear = now.getFullYear() === date.getFullYear();
        if (isThisYear) {
            const month = date.getMonth() + 1;
            const day = date.getDate();
            return t('bots.dateFormat', {
                month,
                day
            });
        }
        // 更早的日期
        return t('bots.earlier');
    };
    // Generate a unique key for a message
    const getMessageKey = (message)=>{
        return `${message.id}-${message.timestamp}`;
    };
    // Toggle raw mode for a message (by default, messages are in markdown mode)
    const toggleRawMode = (message)=>{
        const key = getMessageKey(message);
        setRawModeMessages((prev)=>{
            const newSet = new Set(prev);
            if (newSet.has(key)) {
                newSet.delete(key);
            } else {
                newSet.add(key);
            }
            return newSet;
        });
    };
    // Check if message has any Plain text content
    const hasPlainText = (message)=>{
        return message.message_chain.some((c)=>c.type === 'Plain');
    };
    // Extract plain text from message chain
    const getPlainText = (message)=>{
        return message.message_chain.filter((c)=>c.type === 'Plain').map((c)=>c.text).join('');
    };
    const renderMessageContent = (message)=>{
        const key = getMessageKey(message);
        const isRawMode = rawModeMessages.has(key);
        // By default, render with markdown if there's plain text (unless raw mode is enabled)
        if (!isRawMode && hasPlainText(message)) {
            const plainText = getPlainText(message);
            const nonPlainComponents = message.message_chain.filter((c)=>c.type !== 'Plain' && c.type !== 'Source');
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "text-base leading-relaxed align-middle",
                children: [
                    nonPlainComponents.map((component, index)=>renderMessageComponent(component, index)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "markdown-body",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$markdown$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__Markdown__as__default$3e$__["default"], {
                            remarkPlugins: [
                                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$remark$2d$gfm$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
                            ],
                            rehypePlugins: [
                                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$raw$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"],
                                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$highlight$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"],
                                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$slug$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"],
                                [
                                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$rehype$2d$autolink$2d$headings$2f$lib$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"],
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
                                ul: ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("ul", {
                                        className: "list-disc",
                                        children: children
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 638,
                                        columnNumber: 39
                                    }, void 0),
                                ol: ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("ol", {
                                        className: "list-decimal",
                                        children: children
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 640,
                                        columnNumber: 19
                                    }, void 0),
                                li: ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                                        className: "ml-4",
                                        children: children
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 642,
                                        columnNumber: 39
                                    }, void 0),
                                img: ({ src, alt, ...props })=>{
                                    const imageSrc = src || '';
                                    if (typeof imageSrc !== 'string') {
                                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                            src: src,
                                            alt: alt || '',
                                            className: "max-w-full h-auto rounded-lg my-4",
                                            ...props
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 648,
                                            columnNumber: 23
                                        }, void 0);
                                    }
                                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                        src: imageSrc,
                                        alt: alt || '',
                                        className: "max-w-lg h-auto my-4",
                                        ...props
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 658,
                                        columnNumber: 21
                                    }, void 0);
                                }
                            },
                            children: plainText
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 621,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 620,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                lineNumber: 614,
                columnNumber: 9
            }, this);
        }
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "text-base leading-relaxed align-middle whitespace-pre-wrap",
            children: message.message_chain.map((component, index)=>renderMessageComponent(component, index))
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
            lineNumber: 676,
            columnNumber: 7
        }, this);
    };
    const renderContent = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "flex flex-1 h-full min-h-0",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "w-14 bg-white dark:bg-black p-2 pl-0  flex-shrink-0 flex flex-col justify-start gap-2",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                            variant: "ghost",
                            size: "icon",
                            className: `w-10 h-10 justify-center rounded-md transition-none ${sessionType === 'person' ? 'bg-[#2288ee] text-white hover:bg-[#2288ee] hover:text-white' : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'} border-0 shadow-none`,
                            onClick: ()=>setSessionType('person'),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                xmlns: "http://www.w3.org/2000/svg",
                                viewBox: "0 0 24 24",
                                fill: "currentColor",
                                className: "w-6 h-6",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M4 22C4 17.5817 7.58172 14 12 14C16.4183 14 20 17.5817 20 22H18C18 18.6863 15.3137 16 12 16C8.68629 16 6 18.6863 6 22H4ZM12 13C8.685 13 6 10.315 6 7C6 3.685 8.685 1 12 1C15.315 1 18 3.685 18 7C18 10.315 15.315 13 12 13ZM12 11C14.21 11 16 9.21 16 7C16 4.79 14.21 3 12 3C9.79 3 8 4.79 8 7C8 9.21 9.79 11 12 11Z"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 703,
                                    columnNumber: 13
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 697,
                                columnNumber: 11
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 687,
                            columnNumber: 9
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                            variant: "ghost",
                            size: "icon",
                            className: `w-10 h-10 justify-center rounded-md transition-none ${sessionType === 'group' ? 'bg-[#2288ee] text-white hover:bg-[#2288ee] hover:text-white' : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'} border-0 shadow-none`,
                            onClick: ()=>setSessionType('group'),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                xmlns: "http://www.w3.org/2000/svg",
                                viewBox: "0 0 24 24",
                                fill: "currentColor",
                                className: "w-6 h-6",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M2 22C2 17.5817 5.58172 14 10 14C14.4183 14 18 17.5817 18 22H16C16 18.6863 13.3137 16 10 16C6.68629 16 4 18.6863 4 22H2ZM10 13C6.685 13 4 10.315 4 7C4 3.685 6.685 1 10 1C13.315 1 16 3.685 16 7C16 10.315 13.315 13 10 13ZM10 11C12.21 11 14 9.21 14 7C14 4.79 12.21 3 10 3C7.79 3 6 4.79 6 7C6 9.21 7.79 11 10 11ZM18.2837 14.7028C21.0644 15.9561 23 18.752 23 22H21C21 19.564 19.5483 17.4671 17.4628 16.5271L18.2837 14.7028ZM17.5962 3.41321C19.5944 4.23703 21 6.20361 21 8.5C21 11.3702 18.8042 13.7252 16 13.9776V11.9646C17.6967 11.7222 19 10.264 19 8.5C19 7.11935 18.2016 5.92603 17.041 5.35635L17.5962 3.41321Z"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 722,
                                    columnNumber: 13
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 716,
                                columnNumber: 11
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 706,
                            columnNumber: 9
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 686,
                    columnNumber: 7
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex-1 flex flex-col w-[10rem] h-full min-h-0",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$scroll$2d$area$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ScrollArea"], {
                            className: "flex-1 p-6 overflow-y-auto min-h-0 bg-white dark:bg-black scroll-area",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "space-y-6",
                                children: [
                                    messages.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-center text-muted-foreground py-12 text-lg",
                                        children: t('pipelines.debugDialog.noMessages')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 731,
                                        columnNumber: 15
                                    }, this) : messages.map((message)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex', message.role === 'user' ? 'justify-end' : 'justify-start'),
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('max-w-3xl px-5 py-3 rounded-2xl', message.role === 'user' ? 'user-message-bubble bg-blue-100 dark:bg-blue-900 text-gray-900 dark:text-gray-100 rounded-br-none' : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-none'),
                                                children: [
                                                    renderMessageContent(message),
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-xs mt-2 flex items-center justify-between gap-2', message.role === 'user' ? 'text-gray-600 dark:text-gray-300' : 'text-gray-500 dark:text-gray-400'),
                                                        children: [
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "flex items-center gap-2",
                                                                children: [
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                        children: message.role === 'user' ? t('pipelines.debugDialog.userMessage') : t('pipelines.debugDialog.botMessage')
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                        lineNumber: 761,
                                                                        columnNumber: 25
                                                                    }, this),
                                                                    hasPlainText(message) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                        onClick: ()=>toggleRawMode(message),
                                                                        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('px-1.5 py-0.5 rounded text-[10px] transition-colors', message.role === 'user' ? 'hover:bg-blue-200 dark:hover:bg-blue-800' : 'hover:bg-gray-200 dark:hover:bg-gray-700'),
                                                                        title: rawModeMessages.has(getMessageKey(message)) ? t('pipelines.debugDialog.showMarkdown') : t('pipelines.debugDialog.showRaw'),
                                                                        children: rawModeMessages.has(getMessageKey(message)) ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                            className: "flex items-center gap-0.5",
                                                                            children: [
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                                                    className: "w-3 h-3",
                                                                                    viewBox: "0 0 16 16",
                                                                                    fill: "currentColor",
                                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                                                        d: "M14.85 3H1.15C.52 3 0 3.52 0 4.15v7.69C0 12.48.52 13 1.15 13h13.69c.64 0 1.15-.52 1.15-1.15v-7.7C16 3.52 15.48 3 14.85 3zM9 11H7V8L5.5 9.92 4 8v3H2V5h2l1.5 2L7 5h2v6zm2.99.5L9.5 8H11V5h2v3h1.5l-2.51 3.5z"
                                                                                    }, void 0, false, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                                        lineNumber: 788,
                                                                                        columnNumber: 35
                                                                                    }, this)
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                                    lineNumber: 783,
                                                                                    columnNumber: 33
                                                                                }, this),
                                                                                "MD"
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                            lineNumber: 782,
                                                                            columnNumber: 31
                                                                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                            className: "flex items-center gap-0.5",
                                                                            children: [
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                                                    className: "w-3 h-3",
                                                                                    fill: "none",
                                                                                    viewBox: "0 0 24 24",
                                                                                    stroke: "currentColor",
                                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                                                        strokeLinecap: "round",
                                                                                        strokeLinejoin: "round",
                                                                                        strokeWidth: 2,
                                                                                        d: "M4 6h16M4 12h16M4 18h7"
                                                                                    }, void 0, false, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                                        lineNumber: 800,
                                                                                        columnNumber: 35
                                                                                    }, this)
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                                    lineNumber: 794,
                                                                                    columnNumber: 33
                                                                                }, this),
                                                                                t('pipelines.debugDialog.showRaw')
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                            lineNumber: 793,
                                                                            columnNumber: 31
                                                                        }, this)
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                        lineNumber: 767,
                                                                        columnNumber: 27
                                                                    }, this),
                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                        onClick: ()=>setQuotedMessage(message),
                                                                        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('px-1.5 py-0.5 rounded text-[10px] transition-colors flex items-center gap-0.5', message.role === 'user' ? 'hover:bg-blue-200 dark:hover:bg-blue-800' : 'hover:bg-gray-200 dark:hover:bg-gray-700'),
                                                                        title: t('pipelines.debugDialog.reply'),
                                                                        children: [
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                                                className: "w-3 h-3",
                                                                                fill: "none",
                                                                                viewBox: "0 0 24 24",
                                                                                stroke: "currentColor",
                                                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                                                    strokeLinecap: "round",
                                                                                    strokeLinejoin: "round",
                                                                                    strokeWidth: 2,
                                                                                    d: "M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                                    lineNumber: 828,
                                                                                    columnNumber: 29
                                                                                }, this)
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                                lineNumber: 822,
                                                                                columnNumber: 27
                                                                            }, this),
                                                                            t('pipelines.debugDialog.reply')
                                                                        ]
                                                                    }, void 0, true, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                        lineNumber: 812,
                                                                        columnNumber: 25
                                                                    }, this)
                                                                ]
                                                            }, void 0, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                lineNumber: 760,
                                                                columnNumber: 23
                                                            }, this),
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                className: "text-[10px]",
                                                                children: formatTimestamp(getMessageTimestamp(message))
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                                lineNumber: 838,
                                                                columnNumber: 23
                                                            }, this)
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                        lineNumber: 752,
                                                        columnNumber: 21
                                                    }, this)
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                lineNumber: 743,
                                                columnNumber: 19
                                            }, this)
                                        }, message.id + message.timestamp, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 736,
                                            columnNumber: 17
                                        }, this)),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        ref: messagesEndRef
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 846,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 729,
                                columnNumber: 11
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 728,
                            columnNumber: 9
                        }, this),
                        quotedMessage && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "px-4 py-2 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-start gap-2",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex-1 pl-3 border-l-2 border-[#2288ee]",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-xs text-gray-500 dark:text-gray-400 mb-1",
                                                children: [
                                                    t('pipelines.debugDialog.replyTo'),
                                                    ' ',
                                                    quotedMessage.role === 'user' ? t('pipelines.debugDialog.userMessage') : t('pipelines.debugDialog.botMessage')
                                                ]
                                            }, void 0, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                lineNumber: 855,
                                                columnNumber: 17
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "text-sm text-gray-700 dark:text-gray-300 line-clamp-2",
                                                children: quotedMessage.message_chain.filter((c)=>c.type === 'Plain').map((c)=>c.text).join('')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                lineNumber: 861,
                                                columnNumber: 17
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 854,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        onClick: ()=>setQuotedMessage(null),
                                        className: "w-5 h-5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300",
                                        children: "×"
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 868,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 853,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 852,
                            columnNumber: 11
                        }, this),
                        selectedImages.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "px-4 pb-2 bg-white dark:bg-black",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex gap-2 flex-wrap",
                                children: selectedImages.map((image, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "relative group",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                                src: image.preview,
                                                alt: `preview-${index}`,
                                                className: "w-20 h-20 object-cover rounded-lg border border-gray-300 dark:border-gray-600"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                lineNumber: 884,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                onClick: ()=>handleRemoveImage(index),
                                                className: "absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity",
                                                children: "×"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                lineNumber: 889,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, index, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                        lineNumber: 883,
                                        columnNumber: 17
                                    }, this))
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                lineNumber: 881,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 880,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "p-4 pb-0 bg-white dark:bg-black flex gap-2",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex gap-2 items-center",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex items-center gap-1",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "text-xs text-gray-500 dark:text-gray-400",
                                                    children: t('pipelines.debugDialog.streamOutput')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                    lineNumber: 904,
                                                    columnNumber: 15
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Switch"], {
                                                    checked: streamOutput,
                                                    onCheckedChange: setStreamOutput,
                                                    disabled: !isConnected,
                                                    className: "data-[state=checked]:bg-[#2288ee]"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                    lineNumber: 907,
                                                    columnNumber: 15
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 903,
                                            columnNumber: 13
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                            ref: fileInputRef,
                                            type: "file",
                                            accept: "image/*",
                                            multiple: true,
                                            onChange: handleImageSelect,
                                            className: "hidden"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 914,
                                            columnNumber: 13
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "ghost",
                                            size: "icon",
                                            onClick: ()=>fileInputRef.current?.click(),
                                            disabled: !isConnected || isUploading,
                                            className: "w-10 h-10 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700",
                                            title: "上传图片",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                className: "w-5 h-5",
                                                fill: "none",
                                                viewBox: "0 0 24 24",
                                                stroke: "currentColor",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                    strokeLinecap: "round",
                                                    strokeLinejoin: "round",
                                                    strokeWidth: 2,
                                                    d: "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                    lineNumber: 936,
                                                    columnNumber: 17
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                lineNumber: 930,
                                                columnNumber: 15
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 922,
                                            columnNumber: 13
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 902,
                                    columnNumber: 11
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex-1 flex items-center gap-2",
                                    children: [
                                        hasAt && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$AtBadge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                            targetName: "websocketbot",
                                            onRemove: handleAtRemove
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 947,
                                            columnNumber: 15
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "relative flex-1",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$input$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Input"], {
                                                    ref: inputRef,
                                                    value: inputValue,
                                                    onChange: handleInputChange,
                                                    onKeyPress: handleKeyPress,
                                                    placeholder: t('pipelines.debugDialog.inputPlaceholder', {
                                                        type: sessionType === 'person' ? t('pipelines.debugDialog.privateChat') : t('pipelines.debugDialog.groupChat')
                                                    }),
                                                    disabled: !isConnected || isUploading,
                                                    className: "flex-1 rounded-md px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 focus:border-[#2288ee] transition-none text-base disabled:opacity-50"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                    lineNumber: 950,
                                                    columnNumber: 15
                                                }, this),
                                                showAtPopover && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    ref: popoverRef,
                                                    className: "absolute bottom-full left-0 mb-2 w-auto rounded-md border bg-white dark:bg-gray-800 dark:border-gray-600 shadow-lg",
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex items-center gap-2 px-4 py-1.5 rounded cursor-pointer', isHovering ? 'bg-gray-100 dark:bg-gray-700' : 'bg-white dark:bg-gray-800'),
                                                        onClick: handleAtSelect,
                                                        onMouseEnter: ()=>setIsHovering(true),
                                                        onMouseLeave: ()=>setIsHovering(false),
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: "text-gray-800 dark:text-gray-200",
                                                            children: [
                                                                "@websocketbot - ",
                                                                t('pipelines.debugDialog.atTips')
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                            lineNumber: 980,
                                                            columnNumber: 21
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                        lineNumber: 969,
                                                        columnNumber: 19
                                                    }, this)
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                                    lineNumber: 965,
                                                    columnNumber: 17
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                            lineNumber: 949,
                                            columnNumber: 13
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 945,
                                    columnNumber: 11
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    onClick: sendMessage,
                                    disabled: !inputValue.trim() && !hasAt && selectedImages.length === 0 && !quotedMessage || !isConnected || isUploading,
                                    className: "rounded-md bg-[#2288ee] hover:bg-[#2288ee] w-20 text-white px-6 py-2 text-base font-medium transition-none flex items-center gap-2 shadow-none disabled:opacity-50",
                                    children: isUploading ? '上传中...' : t('pipelines.debugDialog.send')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                                    lineNumber: 988,
                                    columnNumber: 11
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                            lineNumber: 901,
                            columnNumber: 9
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 727,
                    columnNumber: 7
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
            lineNumber: 685,
            columnNumber: 5
        }, this);
    // 如果是嵌入模式，直接返回内容
    if (isEmbedded) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "flex flex-col h-full min-h-0",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex-1 min-h-0 flex flex-col",
                        children: renderContent()
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                        lineNumber: 1012,
                        columnNumber: 11
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 1011,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$ImagePreviewDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                    open: showImagePreview,
                    imageUrl: previewImageUrl,
                    onClose: ()=>setShowImagePreview(false)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                    lineNumber: 1014,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true);
    }
    // 原有的Dialog包装
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                className: "!max-w-[70vw] max-w-6xl h-[70vh] p-6 flex flex-col rounded-2xl shadow-2xl bg-white dark:bg-black",
                children: renderContent()
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                lineNumber: 1026,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$ImagePreviewDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                open: showImagePreview,
                imageUrl: previewImageUrl,
                onClose: ()=>setShowImagePreview(false)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx",
                lineNumber: 1029,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true);
}
_s(DebugDialog, "SzSEIkK5IKpkbFk1VmKwHvPvQFU=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"]
    ];
});
_c = DebugDialog;
var _c;
__turbopack_context__.k.register(_c, "DebugDialog");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginComponentList
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-client] (ecmascript) <export default as Wrench>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/audio-waveform.js [app-client] (ecmascript) <export default as AudioWaveform>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/hash.js [app-client] (ecmascript) <export default as Hash>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/book.js [app-client] (ecmascript) <export default as Book>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-client] (ecmascript)");
;
;
;
function PluginComponentList({ components, showComponentName, showTitle, useBadge, t, responsive = false }) {
    const kindIconMap = {
        Tool: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 21,
            columnNumber: 11
        }, this),
        EventListener: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$audio$2d$waveform$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__AudioWaveform$3e$__["AudioWaveform"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 22,
            columnNumber: 20
        }, this),
        Command: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$hash$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Hash$3e$__["Hash"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 23,
            columnNumber: 14
        }, this),
        KnowledgeRetriever: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$book$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Book$3e$__["Book"], {
            className: "w-5 h-5"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
            lineNumber: 24,
            columnNumber: 25
        }, this)
    };
    const componentKindList = Object.keys(components || {});
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            showTitle && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                children: t('plugins.componentsList')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                lineNumber: 31,
                columnNumber: 21
            }, this),
            componentKindList.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                children: componentKindList.map((kind)=>{
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                        children: [
                            useBadge && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                variant: "outline",
                                className: "flex items-center gap-1",
                                children: [
                                    kindIconMap[kind],
                                    responsive ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "hidden md:inline",
                                        children: t('plugins.componentName.' + kind)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                        lineNumber: 46,
                                        columnNumber: 23
                                    }, this) : showComponentName && t('plugins.componentName.' + kind),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "ml-1",
                                        children: components[kind]
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                        lineNumber: 52,
                                        columnNumber: 21
                                    }, this)
                                ]
                            }, kind, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                lineNumber: 38,
                                columnNumber: 19
                            }, this),
                            !useBadge && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex flex-row items-center justify-start gap-[0.2rem]",
                                children: [
                                    kindIconMap[kind],
                                    responsive ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "hidden md:inline",
                                        children: t('plugins.componentName.' + kind)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                        lineNumber: 64,
                                        columnNumber: 23
                                    }, this) : showComponentName && t('plugins.componentName.' + kind),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "ml-1",
                                        children: components[kind]
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                        lineNumber: 70,
                                        columnNumber: 21
                                    }, this)
                                ]
                            }, kind, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                                lineNumber: 57,
                                columnNumber: 19
                            }, this)
                        ]
                    }, void 0, true);
                })
            }, void 0, false),
            componentKindList.length === 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                children: t('plugins.noComponents')
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx",
                lineNumber: 79,
                columnNumber: 42
            }, this)
        ]
    }, void 0, true);
}
_c = PluginComponentList;
var _c;
__turbopack_context__.k.register(_c, "PluginComponentList");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PipelineExtension
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/skeleton.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/checkbox.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/plus.js [app-client] (ecmascript) <export default as Plus>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/x.js [app-client] (ecmascript) <export default as X>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$server$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Server$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/server.js [app-client] (ecmascript) <export default as Server>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/wrench.js [app-client] (ecmascript) <export default as Wrench>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/badge.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/switch.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$label$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/label.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/plugins/components/plugin-installed/PluginComponentList.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
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
function PipelineExtension({ pipelineId }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [loading, setLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(true);
    const [enableAllPlugins, setEnableAllPlugins] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(true);
    const [enableAllMCPServers, setEnableAllMCPServers] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(true);
    const [selectedPlugins, setSelectedPlugins] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [allPlugins, setAllPlugins] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [selectedMCPServers, setSelectedMCPServers] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [allMCPServers, setAllMCPServers] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [pluginDialogOpen, setPluginDialogOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [mcpDialogOpen, setMcpDialogOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [tempSelectedPluginIds, setTempSelectedPluginIds] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [tempSelectedMCPIds, setTempSelectedMCPIds] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PipelineExtension.useEffect": ()=>{
            loadExtensions();
        }
    }["PipelineExtension.useEffect"], [
        pipelineId
    ]);
    const getPluginId = (plugin)=>{
        const author = plugin.manifest.manifest.metadata.author;
        const name = plugin.manifest.manifest.metadata.name;
        return `${author}/${name}`;
    };
    const loadExtensions = async ()=>{
        try {
            setLoading(true);
            const data = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["backendClient"].getPipelineExtensions(pipelineId);
            setEnableAllPlugins(data.enable_all_plugins ?? true);
            setEnableAllMCPServers(data.enable_all_mcp_servers ?? true);
            const boundPluginIds = new Set(data.bound_plugins.map((p)=>`${p.author}/${p.name}`));
            const selected = data.available_plugins.filter((plugin)=>boundPluginIds.has(getPluginId(plugin)));
            setSelectedPlugins(selected);
            setAllPlugins(data.available_plugins);
            // Load MCP servers
            const boundMCPServerIds = new Set(data.bound_mcp_servers || []);
            const selectedMCP = data.available_mcp_servers.filter((server)=>boundMCPServerIds.has(server.uuid || ''));
            setSelectedMCPServers(selectedMCP);
            setAllMCPServers(data.available_mcp_servers);
        } catch (error) {
            console.error('Failed to load extensions:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.extensions.loadError'));
        } finally{
            setLoading(false);
        }
    };
    const saveToBackend = async (plugins, mcpServers, newEnableAllPlugins, newEnableAllMCPServers)=>{
        try {
            const boundPluginsArray = plugins.map((plugin)=>{
                const metadata = plugin.manifest.manifest.metadata;
                return {
                    author: metadata.author || '',
                    name: metadata.name
                };
            });
            const boundMCPServerIds = mcpServers.map((server)=>server.uuid || '');
            await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["backendClient"].updatePipelineExtensions(pipelineId, boundPluginsArray, boundMCPServerIds, newEnableAllPlugins ?? enableAllPlugins, newEnableAllMCPServers ?? enableAllMCPServers);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('pipelines.extensions.saveSuccess'));
        } catch (error) {
            console.error('Failed to save extensions:', error);
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.extensions.saveError'));
            // Reload on error to restore correct state
            loadExtensions();
        }
    };
    const handleRemovePlugin = async (pluginId)=>{
        const newPlugins = selectedPlugins.filter((p)=>getPluginId(p) !== pluginId);
        setSelectedPlugins(newPlugins);
        await saveToBackend(newPlugins, selectedMCPServers);
    };
    const handleRemoveMCPServer = async (serverUuid)=>{
        const newServers = selectedMCPServers.filter((s)=>s.uuid !== serverUuid);
        setSelectedMCPServers(newServers);
        await saveToBackend(selectedPlugins, newServers);
    };
    const handleOpenPluginDialog = ()=>{
        setTempSelectedPluginIds(selectedPlugins.map((p)=>getPluginId(p)));
        setPluginDialogOpen(true);
    };
    const handleOpenMCPDialog = ()=>{
        setTempSelectedMCPIds(selectedMCPServers.map((s)=>s.uuid || ''));
        setMcpDialogOpen(true);
    };
    const handleTogglePlugin = (pluginId)=>{
        setTempSelectedPluginIds((prev)=>prev.includes(pluginId) ? prev.filter((id)=>id !== pluginId) : [
                ...prev,
                pluginId
            ]);
    };
    const handleToggleMCPServer = (serverUuid)=>{
        setTempSelectedMCPIds((prev)=>prev.includes(serverUuid) ? prev.filter((id)=>id !== serverUuid) : [
                ...prev,
                serverUuid
            ]);
    };
    const handleToggleAllPlugins = ()=>{
        if (tempSelectedPluginIds.length === allPlugins.length) {
            // Deselect all
            setTempSelectedPluginIds([]);
        } else {
            // Select all
            setTempSelectedPluginIds(allPlugins.map((p)=>getPluginId(p)));
        }
    };
    const handleToggleAllMCPServers = ()=>{
        if (tempSelectedMCPIds.length === allMCPServers.length) {
            // Deselect all
            setTempSelectedMCPIds([]);
        } else {
            // Select all
            setTempSelectedMCPIds(allMCPServers.map((s)=>s.uuid || ''));
        }
    };
    const handleConfirmPluginSelection = async ()=>{
        const newSelected = allPlugins.filter((p)=>tempSelectedPluginIds.includes(getPluginId(p)));
        setSelectedPlugins(newSelected);
        setPluginDialogOpen(false);
        await saveToBackend(newSelected, selectedMCPServers);
    };
    const handleConfirmMCPSelection = async ()=>{
        const newSelected = allMCPServers.filter((s)=>tempSelectedMCPIds.includes(s.uuid || ''));
        setSelectedMCPServers(newSelected);
        setMcpDialogOpen(false);
        await saveToBackend(selectedPlugins, newSelected);
    };
    const handleToggleEnableAllPlugins = async (checked)=>{
        setEnableAllPlugins(checked);
        await saveToBackend(selectedPlugins, selectedMCPServers, checked, undefined);
    };
    const handleToggleEnableAllMCPServers = async (checked)=>{
        setEnableAllMCPServers(checked);
        await saveToBackend(selectedPlugins, selectedMCPServers, undefined, checked);
    };
    if (loading) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "space-y-4",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Skeleton"], {
                    className: "h-20 w-full"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                    lineNumber: 224,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Skeleton"], {
                    className: "h-20 w-full"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                    lineNumber: 225,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$skeleton$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Skeleton"], {
                    className: "h-20 w-full"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                    lineNumber: 226,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
            lineNumber: 223,
            columnNumber: 7
        }, this);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "space-y-6",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-3",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center justify-between",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                className: "text-sm font-semibold text-foreground",
                                children: t('pipelines.extensions.pluginsTitle')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 236,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center gap-2",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$label$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"], {
                                        htmlFor: "enable-all-plugins",
                                        className: "text-sm font-normal cursor-pointer",
                                        children: t('pipelines.extensions.enableAllPlugins')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                        lineNumber: 240,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Switch"], {
                                        id: "enable-all-plugins",
                                        checked: enableAllPlugins,
                                        onCheckedChange: handleToggleEnableAllPlugins
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                        lineNumber: 246,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 239,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                        lineNumber: 235,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "space-y-2",
                        children: enableAllPlugins ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/30",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-sm text-muted-foreground",
                                children: t('pipelines.extensions.allPluginsEnabled')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 256,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 255,
                            columnNumber: 13
                        }, this) : selectedPlugins.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-sm text-muted-foreground",
                                children: t('pipelines.extensions.noPluginsSelected')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 262,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 261,
                            columnNumber: 13
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "space-y-2",
                            children: selectedPlugins.map((plugin)=>{
                                const pluginId = getPluginId(plugin);
                                const metadata = plugin.manifest.manifest.metadata;
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between rounded-lg border p-3 hover:bg-accent",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex-1 flex items-center gap-3",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                                    src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["backendClient"].getPluginIconURL(metadata.author || '', metadata.name),
                                                    alt: metadata.name,
                                                    className: "w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 277,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "flex-1",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "font-medium",
                                                            children: metadata.name
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 286,
                                                            columnNumber: 25
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "text-sm text-muted-foreground",
                                                            children: [
                                                                metadata.author,
                                                                " • v",
                                                                metadata.version
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 287,
                                                            columnNumber: 25
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "flex gap-1 mt-1",
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                                                components: (()=>{
                                                                    const componentKindCount = {};
                                                                    for (const component of plugin.components){
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
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                                lineNumber: 291,
                                                                columnNumber: 27
                                                            }, this)
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 290,
                                                            columnNumber: 25
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 285,
                                                    columnNumber: 23
                                                }, this),
                                                !plugin.enabled && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                                    variant: "secondary",
                                                    children: t('pipelines.extensions.disabled')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 313,
                                                    columnNumber: 25
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 276,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "ghost",
                                            size: "icon",
                                            onClick: ()=>handleRemovePlugin(pluginId),
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__["X"], {
                                                className: "h-4 w-4"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                lineNumber: 323,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 318,
                                            columnNumber: 21
                                        }, this)
                                    ]
                                }, pluginId, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 272,
                                    columnNumber: 19
                                }, this);
                            })
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 267,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                        lineNumber: 253,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                        onClick: handleOpenPluginDialog,
                        variant: "outline",
                        className: "w-full",
                        disabled: enableAllPlugins,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__["Plus"], {
                                className: "mr-2 h-4 w-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 338,
                                columnNumber: 11
                            }, this),
                            t('pipelines.extensions.addPlugin')
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                        lineNumber: 332,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                lineNumber: 234,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "space-y-3",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center justify-between",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                className: "text-sm font-semibold text-foreground",
                                children: t('pipelines.extensions.mcpServersTitle')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 346,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center gap-2",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$label$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"], {
                                        htmlFor: "enable-all-mcp-servers",
                                        className: "text-sm font-normal cursor-pointer",
                                        children: t('pipelines.extensions.enableAllMCPServers')
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                        lineNumber: 350,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$switch$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Switch"], {
                                        id: "enable-all-mcp-servers",
                                        checked: enableAllMCPServers,
                                        onCheckedChange: handleToggleEnableAllMCPServers
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                        lineNumber: 356,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 349,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                        lineNumber: 345,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "space-y-2",
                        children: enableAllMCPServers ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/30",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-sm text-muted-foreground",
                                children: t('pipelines.extensions.allMCPServersEnabled')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 366,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 365,
                            columnNumber: 13
                        }, this) : selectedMCPServers.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "text-sm text-muted-foreground",
                                children: t('pipelines.extensions.noMCPServersSelected')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 372,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 371,
                            columnNumber: 13
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "space-y-2",
                            children: selectedMCPServers.map((server)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center justify-between rounded-lg border p-3 hover:bg-accent",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex-1 flex items-center gap-3",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0",
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$server$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Server$3e$__["Server"], {
                                                        className: "h-5 w-5 text-muted-foreground"
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                        lineNumber: 385,
                                                        columnNumber: 23
                                                    }, this)
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 384,
                                                    columnNumber: 21
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "flex-1",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "font-medium",
                                                            children: server.name
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 388,
                                                            columnNumber: 23
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "text-sm text-muted-foreground",
                                                            children: server.mode
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 389,
                                                            columnNumber: 23
                                                        }, this),
                                                        server.runtime_info && server.runtime_info.status === 'connected' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                                            variant: "outline",
                                                            className: "flex items-center gap-1 mt-1",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                                                    className: "h-3 w-3 text-black dark:text-white"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                                    lineNumber: 398,
                                                                    columnNumber: 29
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    className: "text-xs text-black dark:text-white",
                                                                    children: t('pipelines.extensions.toolCount', {
                                                                        count: server.runtime_info.tool_count || 0
                                                                    })
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                                    lineNumber: 399,
                                                                    columnNumber: 29
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 394,
                                                            columnNumber: 27
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 387,
                                                    columnNumber: 21
                                                }, this),
                                                !server.enable && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                                    variant: "secondary",
                                                    children: t('pipelines.extensions.disabled')
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 408,
                                                    columnNumber: 23
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 383,
                                            columnNumber: 19
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "ghost",
                                            size: "icon",
                                            onClick: ()=>handleRemoveMCPServer(server.uuid || ''),
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$x$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__X$3e$__["X"], {
                                                className: "h-4 w-4"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                lineNumber: 418,
                                                columnNumber: 21
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 413,
                                            columnNumber: 19
                                        }, this)
                                    ]
                                }, server.uuid, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 379,
                                    columnNumber: 17
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 377,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                        lineNumber: 363,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                        onClick: handleOpenMCPDialog,
                        variant: "outline",
                        className: "w-full",
                        disabled: enableAllMCPServers,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$plus$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Plus$3e$__["Plus"], {
                                className: "mr-2 h-4 w-4"
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 432,
                                columnNumber: 11
                            }, this),
                            t('pipelines.extensions.addMCPServer')
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                        lineNumber: 426,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                lineNumber: 344,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
                open: pluginDialogOpen,
                onOpenChange: setPluginDialogOpen,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                    className: "max-w-2xl max-h-[80vh] overflow-hidden flex flex-col",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                children: t('pipelines.extensions.selectPlugins')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 441,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 440,
                            columnNumber: 11
                        }, this),
                        allPlugins.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex items-center gap-3 px-1 py-2 border-b cursor-pointer",
                            onClick: handleToggleAllPlugins,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Checkbox"], {
                                    checked: tempSelectedPluginIds.length === allPlugins.length && allPlugins.length > 0,
                                    onCheckedChange: handleToggleAllPlugins
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 448,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "text-sm font-medium",
                                    children: t('pipelines.extensions.selectAll')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 455,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 444,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex-1 overflow-y-auto space-y-2 pr-2",
                            children: allPlugins.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex h-full items-center justify-center",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-muted-foreground",
                                    children: t('pipelines.extensions.noPluginsInstalled')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 463,
                                    columnNumber: 17
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 462,
                                columnNumber: 15
                            }, this) : allPlugins.map((plugin)=>{
                                const pluginId = getPluginId(plugin);
                                const metadata = plugin.manifest.manifest.metadata;
                                const isSelected = tempSelectedPluginIds.includes(pluginId);
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer",
                                    onClick: ()=>handleTogglePlugin(pluginId),
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Checkbox"], {
                                            checked: isSelected
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 478,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                            src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["backendClient"].getPluginIconURL(metadata.author || '', metadata.name),
                                            alt: metadata.name,
                                            className: "w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 479,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex-1",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "font-medium",
                                                    children: metadata.name
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 488,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "text-sm text-muted-foreground",
                                                    children: [
                                                        metadata.author,
                                                        " • v",
                                                        metadata.version
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 489,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "flex gap-1 mt-1",
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$plugins$2f$components$2f$plugin$2d$installed$2f$PluginComponentList$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                                        components: (()=>{
                                                            const componentKindCount = {};
                                                            for (const component of plugin.components){
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
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                        lineNumber: 493,
                                                        columnNumber: 25
                                                    }, this)
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 492,
                                                    columnNumber: 23
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 487,
                                            columnNumber: 21
                                        }, this),
                                        !plugin.enabled && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                            variant: "secondary",
                                            children: t('pipelines.extensions.disabled')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 515,
                                            columnNumber: 23
                                        }, this)
                                    ]
                                }, pluginId, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 473,
                                    columnNumber: 19
                                }, this);
                            })
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 460,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogFooter"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "outline",
                                    onClick: ()=>setPluginDialogOpen(false),
                                    children: t('common.cancel')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 525,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    onClick: handleConfirmPluginSelection,
                                    children: t('common.confirm')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 531,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 524,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                    lineNumber: 439,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                lineNumber: 438,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
                open: mcpDialogOpen,
                onOpenChange: setMcpDialogOpen,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                    className: "max-w-2xl max-h-[80vh] overflow-hidden flex flex-col",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                children: t('pipelines.extensions.selectMCPServers')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 542,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 541,
                            columnNumber: 11
                        }, this),
                        allMCPServers.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex items-center gap-3 px-1 py-2 border-b cursor-pointer",
                            onClick: handleToggleAllMCPServers,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Checkbox"], {
                                    checked: tempSelectedMCPIds.length === allMCPServers.length && allMCPServers.length > 0,
                                    onCheckedChange: handleToggleAllMCPServers
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 551,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "text-sm font-medium",
                                    children: t('pipelines.extensions.selectAll')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 558,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 547,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex-1 overflow-y-auto space-y-2 pr-2",
                            children: allMCPServers.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex h-full items-center justify-center",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-muted-foreground",
                                    children: t('pipelines.extensions.noMCPServersConfigured')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 566,
                                    columnNumber: 17
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                lineNumber: 565,
                                columnNumber: 15
                            }, this) : allMCPServers.map((server)=>{
                                const isSelected = tempSelectedMCPIds.includes(server.uuid || '');
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer",
                                    onClick: ()=>handleToggleMCPServer(server.uuid || ''),
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$checkbox$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Checkbox"], {
                                            checked: isSelected
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 581,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$server$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Server$3e$__["Server"], {
                                                className: "h-5 w-5 text-muted-foreground"
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                lineNumber: 583,
                                                columnNumber: 23
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 582,
                                            columnNumber: 21
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "flex-1",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "font-medium",
                                                    children: server.name
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 586,
                                                    columnNumber: 23
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "text-sm text-muted-foreground",
                                                    children: server.mode
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 587,
                                                    columnNumber: 23
                                                }, this),
                                                server.runtime_info && server.runtime_info.status === 'connected' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                                    variant: "outline",
                                                    className: "flex items-center gap-1 mt-1",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$wrench$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Wrench$3e$__["Wrench"], {
                                                            className: "h-3 w-3 text-black dark:text-white"
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 596,
                                                            columnNumber: 29
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: "text-xs text-black dark:text-white",
                                                            children: t('pipelines.extensions.toolCount', {
                                                                count: server.runtime_info.tool_count || 0
                                                            })
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                            lineNumber: 597,
                                                            columnNumber: 29
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                                    lineNumber: 592,
                                                    columnNumber: 27
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 585,
                                            columnNumber: 21
                                        }, this),
                                        !server.enable && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$badge$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Badge"], {
                                            variant: "secondary",
                                            children: t('pipelines.extensions.disabled')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                            lineNumber: 606,
                                            columnNumber: 23
                                        }, this)
                                    ]
                                }, server.uuid, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 576,
                                    columnNumber: 19
                                }, this);
                            })
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 563,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogFooter"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    variant: "outline",
                                    onClick: ()=>setMcpDialogOpen(false),
                                    children: t('common.cancel')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 616,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    onClick: handleConfirmMCPSelection,
                                    children: t('common.confirm')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                                    lineNumber: 619,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                            lineNumber: 615,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                    lineNumber: 540,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
                lineNumber: 539,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx",
        lineNumber: 232,
        columnNumber: 5
    }, this);
}
_s(PipelineExtension, "JXlVgpNuidh8aRX1y2s73p8LN/E=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"]
    ];
});
_c = PipelineExtension;
var _c;
__turbopack_context__.k.register(_c, "PipelineExtension");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/monitoring/hooks/useMonitoringData.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useMonitoringData",
    ()=>useMonitoringData
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>");
var _s = __turbopack_context__.k.signature();
;
;
function useMonitoringData(filterState) {
    _s();
    const [data, setData] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [loading, setLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [error, setError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    // Memoize filter parameters to prevent unnecessary re-renders
    const selectedBotsStr = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useMonitoringData.useMemo[selectedBotsStr]": ()=>JSON.stringify(filterState.selectedBots)
    }["useMonitoringData.useMemo[selectedBotsStr]"], [
        filterState.selectedBots
    ]);
    const selectedPipelinesStr = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useMonitoringData.useMemo[selectedPipelinesStr]": ()=>JSON.stringify(filterState.selectedPipelines)
    }["useMonitoringData.useMemo[selectedPipelinesStr]"], [
        filterState.selectedPipelines
    ]);
    const customDateRangeStr = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useMonitoringData.useMemo[customDateRangeStr]": ()=>JSON.stringify(filterState.customDateRange)
    }["useMonitoringData.useMemo[customDateRangeStr]"], [
        filterState.customDateRange
    ]);
    // Convert time range to datetime strings
    const getTimeRange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useMonitoringData.useCallback[getTimeRange]": ()=>{
            const now = new Date();
            let startTime = null;
            switch(filterState.timeRange){
                case 'lastHour':
                    startTime = new Date(now.getTime() - 60 * 60 * 1000);
                    break;
                case 'last6Hours':
                    startTime = new Date(now.getTime() - 6 * 60 * 60 * 1000);
                    break;
                case 'last24Hours':
                    startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                    break;
                case 'last7Days':
                    startTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    break;
                case 'last30Days':
                    startTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                    break;
                case 'custom':
                    if (filterState.customDateRange) {
                        startTime = filterState.customDateRange.from;
                    }
                    break;
            }
            const endTime = filterState.timeRange === 'custom' && filterState.customDateRange ? filterState.customDateRange.to : now;
            return {
                startTime: startTime?.toISOString(),
                endTime: endTime.toISOString()
            };
        }
    }["useMonitoringData.useCallback[getTimeRange]"], [
        filterState.timeRange,
        filterState.customDateRange
    ]);
    // Fetch data based on filters
    const fetchData = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useMonitoringData.useCallback[fetchData]": async ()=>{
            setLoading(true);
            setError(null);
            try {
                const { startTime, endTime } = getTimeRange();
                const response = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["backendClient"].getMonitoringData({
                    botId: filterState.selectedBots.length > 0 ? filterState.selectedBots : undefined,
                    pipelineId: filterState.selectedPipelines.length > 0 ? filterState.selectedPipelines : undefined,
                    startTime,
                    endTime,
                    limit: 50
                });
                // Transform the response to match MonitoringData interface
                const transformedData = {
                    overview: {
                        totalMessages: response.overview.total_messages,
                        llmCalls: response.overview.llm_calls,
                        embeddingCalls: response.overview.embedding_calls || 0,
                        modelCalls: response.overview.model_calls || response.overview.llm_calls,
                        successRate: response.overview.success_rate,
                        activeSessions: response.overview.active_sessions
                    },
                    messages: response.messages.map({
                        "useMonitoringData.useCallback[fetchData]": (msg)=>({
                                id: msg.id,
                                timestamp: new Date(msg.timestamp),
                                botId: msg.bot_id,
                                botName: msg.bot_name,
                                pipelineId: msg.pipeline_id,
                                pipelineName: msg.pipeline_name,
                                messageContent: msg.message_content,
                                sessionId: msg.session_id,
                                status: msg.status,
                                level: msg.level,
                                platform: msg.platform,
                                userId: msg.user_id,
                                runnerName: msg.runner_name,
                                variables: msg.variables
                            })
                    }["useMonitoringData.useCallback[fetchData]"]),
                    llmCalls: response.llmCalls.map({
                        "useMonitoringData.useCallback[fetchData]": (call)=>({
                                id: call.id,
                                timestamp: new Date(call.timestamp),
                                modelName: call.model_name,
                                tokens: {
                                    input: call.input_tokens,
                                    output: call.output_tokens,
                                    total: call.total_tokens
                                },
                                duration: call.duration,
                                cost: call.cost,
                                status: call.status,
                                botId: call.bot_id,
                                botName: call.bot_name,
                                pipelineId: call.pipeline_id,
                                pipelineName: call.pipeline_name,
                                errorMessage: call.error_message,
                                messageId: call.message_id
                            })
                    }["useMonitoringData.useCallback[fetchData]"]),
                    embeddingCalls: (response.embeddingCalls || []).map({
                        "useMonitoringData.useCallback[fetchData]": (call)=>({
                                id: call.id,
                                timestamp: new Date(call.timestamp),
                                modelName: call.model_name,
                                promptTokens: call.prompt_tokens,
                                totalTokens: call.total_tokens,
                                duration: call.duration,
                                inputCount: call.input_count,
                                status: call.status,
                                errorMessage: call.error_message,
                                knowledgeBaseId: call.knowledge_base_id,
                                queryText: call.query_text,
                                sessionId: call.session_id,
                                messageId: call.message_id,
                                callType: call.call_type
                            })
                    }["useMonitoringData.useCallback[fetchData]"]),
                    // Create merged modelCalls array from llmCalls and embeddingCalls
                    modelCalls: [],
                    sessions: response.sessions.map({
                        "useMonitoringData.useCallback[fetchData]": (session)=>({
                                sessionId: session.session_id,
                                botId: session.bot_id,
                                botName: session.bot_name,
                                pipelineId: session.pipeline_id,
                                pipelineName: session.pipeline_name,
                                messageCount: session.message_count,
                                duration: new Date(session.last_activity).getTime() - new Date(session.start_time).getTime(),
                                lastActivity: new Date(session.last_activity),
                                startTime: new Date(session.start_time),
                                platform: session.platform,
                                userId: session.user_id
                            })
                    }["useMonitoringData.useCallback[fetchData]"]),
                    errors: response.errors.map({
                        "useMonitoringData.useCallback[fetchData]": (error)=>({
                                id: error.id,
                                timestamp: new Date(error.timestamp),
                                errorType: error.error_type,
                                errorMessage: error.error_message,
                                botId: error.bot_id,
                                botName: error.bot_name,
                                pipelineId: error.pipeline_id,
                                pipelineName: error.pipeline_name,
                                sessionId: error.session_id,
                                stackTrace: error.stack_trace,
                                messageId: error.message_id
                            })
                    }["useMonitoringData.useCallback[fetchData]"]),
                    totalCount: {
                        messages: response.totalCount.messages,
                        llmCalls: response.totalCount.llmCalls,
                        embeddingCalls: response.totalCount.embeddingCalls || 0,
                        sessions: response.totalCount.sessions,
                        errors: response.totalCount.errors
                    }
                };
                // Merge LLM calls and embedding calls into modelCalls
                const llmModelCalls = transformedData.llmCalls.map({
                    "useMonitoringData.useCallback[fetchData].llmModelCalls": (call)=>({
                            id: call.id,
                            timestamp: call.timestamp,
                            modelName: call.modelName,
                            modelType: 'llm',
                            status: call.status,
                            duration: call.duration,
                            errorMessage: call.errorMessage,
                            messageId: call.messageId,
                            tokens: call.tokens,
                            cost: call.cost,
                            botId: call.botId,
                            botName: call.botName,
                            pipelineId: call.pipelineId,
                            pipelineName: call.pipelineName
                        })
                }["useMonitoringData.useCallback[fetchData].llmModelCalls"]);
                const embeddingModelCalls = transformedData.embeddingCalls.map({
                    "useMonitoringData.useCallback[fetchData].embeddingModelCalls": (call)=>({
                            id: call.id,
                            timestamp: call.timestamp,
                            modelName: call.modelName,
                            modelType: 'embedding',
                            status: call.status,
                            duration: call.duration,
                            errorMessage: call.errorMessage,
                            messageId: call.messageId,
                            callType: call.callType,
                            promptTokens: call.promptTokens,
                            totalTokens: call.totalTokens,
                            inputCount: call.inputCount,
                            knowledgeBaseId: call.knowledgeBaseId,
                            queryText: call.queryText,
                            sessionId: call.sessionId
                        })
                }["useMonitoringData.useCallback[fetchData].embeddingModelCalls"]);
                // Combine and sort by timestamp (newest first)
                transformedData.modelCalls = [
                    ...llmModelCalls,
                    ...embeddingModelCalls
                ].sort({
                    "useMonitoringData.useCallback[fetchData]": (a, b)=>b.timestamp.getTime() - a.timestamp.getTime()
                }["useMonitoringData.useCallback[fetchData]"]);
                setData(transformedData);
            } catch (err) {
                setError(err);
                console.error('Failed to fetch monitoring data:', err);
            } finally{
                setLoading(false);
            }
        }
    }["useMonitoringData.useCallback[fetchData]"], [
        getTimeRange,
        filterState.selectedBots,
        filterState.selectedPipelines
    ]);
    // Fetch data when filter state changes
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "useMonitoringData.useEffect": ()=>{
            fetchData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
        }
    }["useMonitoringData.useEffect"], [
        selectedBotsStr,
        selectedPipelinesStr,
        filterState.timeRange,
        customDateRangeStr
    ]);
    // Manual refetch function
    const refetch = ()=>{
        fetchData();
    };
    return {
        data,
        loading,
        error,
        refetch
    };
}
_s(useMonitoringData, "06+KasuZFicr542NOGrLzqmOJss=");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MessageContentRenderer",
    ()=>MessageContentRenderer
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$ImagePreviewDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/ImagePreviewDialog.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
'use client';
;
;
function MessageContentRenderer({ content, maxLines = 3 }) {
    _s();
    const [previewImageUrl, setPreviewImageUrl] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const [showImagePreview, setShowImagePreview] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    // Try to parse content as message_chain JSON
    const parseContent = (content)=>{
        try {
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].type) {
                return parsed;
            }
            return null;
        } catch  {
            return null;
        }
    };
    const renderMessageComponent = (component, index)=>{
        switch(component.type){
            case 'Plain':
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    children: component.text
                }, index, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                    lineNumber: 45,
                    columnNumber: 16
                }, this);
            case 'At':
                {
                    const atComponent = component;
                    const displayName = atComponent.display || atComponent.target?.toString() || '';
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm",
                        children: [
                            "@",
                            displayName
                        ]
                    }, index, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                        lineNumber: 52,
                        columnNumber: 11
                    }, this);
                }
            case 'AtAll':
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm",
                    children: "@All"
                }, index, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                    lineNumber: 63,
                    columnNumber: 11
                }, this);
            case 'Image':
                {
                    const img = component;
                    const imageUrl = img.url || (img.base64 ? img.base64 : '');
                    if (!imageUrl) {
                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm",
                            children: "[Image]"
                        }, index, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                            lineNumber: 77,
                            columnNumber: 13
                        }, this);
                    }
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "inline-block align-middle mx-1",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: imageUrl,
                            alt: "Image",
                            className: "w-20 h-20 object-cover rounded cursor-pointer hover:opacity-80 transition-opacity border border-gray-200 dark:border-gray-700",
                            onClick: (e)=>{
                                e.stopPropagation();
                                setPreviewImageUrl(imageUrl);
                                setShowImagePreview(true);
                            }
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                            lineNumber: 88,
                            columnNumber: 13
                        }, this)
                    }, index, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                        lineNumber: 87,
                        columnNumber: 11
                    }, this);
                }
            case 'File':
                {
                    const file = component;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                className: "w-3.5 h-3.5 mr-1",
                                fill: "currentColor",
                                viewBox: "0 0 20 20",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                                    lineNumber: 114,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                                lineNumber: 109,
                                columnNumber: 13
                            }, this),
                            file.name || 'File'
                        ]
                    }, index, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                        lineNumber: 105,
                        columnNumber: 11
                    }, this);
                }
            case 'Voice':
                {
                    const voice = component;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                className: "w-3.5 h-3.5 mr-1",
                                fill: "currentColor",
                                viewBox: "0 0 20 20",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                    d: "M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                                    lineNumber: 133,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                                lineNumber: 128,
                                columnNumber: 13
                            }, this),
                            "Voice",
                            voice.length ? ` ${voice.length}s` : ''
                        ]
                    }, index, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                        lineNumber: 124,
                        columnNumber: 11
                    }, this);
                }
            case 'Quote':
                {
                    const quote = component;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-sm border-l-2 border-gray-400",
                        children: quote.origin?.filter((c)=>c.type === 'Plain').map((c)=>c.text).join('') || '[Quote]'
                    }, index, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                        lineNumber: 143,
                        columnNumber: 11
                    }, this);
                }
            case 'Source':
                return null;
            default:
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                    className: "inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm",
                    children: [
                        "[",
                        component.type,
                        "]"
                    ]
                }, index, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                    lineNumber: 160,
                    columnNumber: 11
                }, this);
        }
    };
    const messageChain = parseContent(content);
    // Determine line clamp class
    const lineClampClass = maxLines === 2 ? 'line-clamp-2' : maxLines === 3 ? 'line-clamp-3' : maxLines === 4 ? 'line-clamp-4' : '';
    if (messageChain) {
        // Filter out Source components as they render to null
        const visibleComponents = messageChain.filter((component)=>component.type !== 'Source');
        // If no visible components, show placeholder
        if (visibleComponents.length === 0) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                className: "text-gray-400 dark:text-gray-500 italic",
                children: "[Empty message]"
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                lineNumber: 191,
                columnNumber: 9
            }, this);
        }
        // Render as message chain
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: `${lineClampClass}`,
                    children: messageChain.map((component, index)=>renderMessageComponent(component, index))
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                    lineNumber: 200,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$ImagePreviewDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                    open: showImagePreview,
                    imageUrl: previewImageUrl,
                    onClose: ()=>setShowImagePreview(false)
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
                    lineNumber: 205,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true);
    }
    // Handle empty plain text
    if (!content || content.trim() === '' || content === '[]' || content === '""') {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
            className: "text-gray-400 dark:text-gray-500 italic",
            children: "[Empty message]"
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
            lineNumber: 222,
            columnNumber: 7
        }, this);
    }
    // Render as plain text
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
        className: lineClampClass,
        children: content
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx",
        lineNumber: 229,
        columnNumber: 10
    }, this);
}
_s(MessageContentRenderer, "r72SLNEiIVZk5XnUmoZ10EOfpCM=");
_c = MessageContentRenderer;
var _c;
__turbopack_context__.k.register(_c, "MessageContentRenderer");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LoadingInline",
    ()=>LoadingInline,
    "LoadingPage",
    ()=>LoadingPage,
    "LoadingSpinner",
    ()=>LoadingSpinner
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/loader-circle.js [app-client] (ecmascript) <export default as Loader2>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
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
    const spinner = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "flex flex-col items-center gap-4",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__["Loader2"], {
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('animate-spin text-primary', sizeMap[size], className)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
                lineNumber: 45,
                columnNumber: 7
            }, this),
            text && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-muted-foreground', textSizeMap[size]),
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
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
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
_c = LoadingSpinner;
function LoadingPage({ text }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingSpinner, {
        fullPage: true,
        text: text
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 69,
        columnNumber: 10
    }, this);
}
_c1 = LoadingPage;
function LoadingInline({ size, text }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingSpinner, {
        size: size,
        text: text
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 82,
        columnNumber: 10
    }, this);
}
_c2 = LoadingInline;
var _c, _c1, _c2;
__turbopack_context__.k.register(_c, "LoadingSpinner");
__turbopack_context__.k.register(_c1, "LoadingPage");
__turbopack_context__.k.register(_c2, "LoadingInline");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PipelineMonitoringTab
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/tabs.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-right.js [app-client] (ecmascript) <export default as ChevronRight>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$down$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronDown$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/chevron-down.js [app-client] (ecmascript) <export default as ChevronDown>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$external$2d$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ExternalLink$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/external-link.js [app-client] (ecmascript) <export default as ExternalLink>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$monitoring$2f$hooks$2f$useMonitoringData$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/monitoring/hooks/useMonitoringData.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$monitoring$2f$components$2f$MessageContentRenderer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/monitoring/components/MessageContentRenderer.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals> <export backendClient as httpClient>");
;
var _s = __turbopack_context__.k.signature();
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
function PipelineMonitoringTab({ pipelineId, onNavigateToMonitoring }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    // Filter state - only show data for this pipeline, last 24 hours
    const filterState = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "PipelineMonitoringTab.useMemo[filterState]": ()=>({
                selectedBots: [],
                selectedPipelines: [
                    pipelineId
                ],
                timeRange: 'last24Hours',
                customDateRange: null
            })
    }["PipelineMonitoringTab.useMemo[filterState]"], [
        pipelineId
    ]);
    const { data, loading, refetch } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$monitoring$2f$hooks$2f$useMonitoringData$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMonitoringData"])(filterState);
    const [expandedMessageId, setExpandedMessageId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [messageDetails, setMessageDetails] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({});
    const [loadingDetails, setLoadingDetails] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({});
    const [expandedErrorId, setExpandedErrorId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [activeTab, setActiveTab] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('messages');
    const toggleMessageExpand = async (messageId)=>{
        if (expandedMessageId === messageId) {
            setExpandedMessageId(null);
        } else {
            setExpandedMessageId(messageId);
            if (!messageDetails[messageId]) {
                setLoadingDetails((prev)=>({
                        ...prev,
                        [messageId]: true
                    }));
                try {
                    const result = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].get(`/api/v1/monitoring/messages/${messageId}/details`);
                    if (result) {
                        setMessageDetails((prev)=>({
                                ...prev,
                                [messageId]: {
                                    messageId: result.message_id,
                                    found: result.found,
                                    message: result.message ? {
                                        id: result.message.id,
                                        timestamp: new Date(result.message.timestamp),
                                        botId: result.message.bot_id,
                                        botName: result.message.bot_name,
                                        pipelineId: result.message.pipeline_id,
                                        pipelineName: result.message.pipeline_name,
                                        messageContent: result.message.message_content,
                                        sessionId: result.message.session_id,
                                        status: result.message.status,
                                        level: result.message.level,
                                        platform: result.message.platform,
                                        userId: result.message.user_id,
                                        runnerName: result.message.runner_name,
                                        variables: result.message.variables
                                    } : undefined,
                                    llmCalls: result.llm_calls.map((call)=>({
                                            id: call.id,
                                            timestamp: new Date(call.timestamp),
                                            modelName: call.model_name,
                                            status: call.status,
                                            duration: call.duration,
                                            errorMessage: call.error_message,
                                            tokens: {
                                                input: call.input_tokens || 0,
                                                output: call.output_tokens || 0,
                                                total: call.total_tokens || 0
                                            }
                                        })),
                                    errors: result.errors.map((error)=>({
                                            id: error.id,
                                            timestamp: new Date(error.timestamp),
                                            errorType: error.error_type,
                                            errorMessage: error.error_message,
                                            stackTrace: error.stack_trace
                                        })),
                                    llmStats: {
                                        totalCalls: result.llm_stats.total_calls,
                                        totalInputTokens: result.llm_stats.total_input_tokens,
                                        totalOutputTokens: result.llm_stats.total_output_tokens,
                                        totalTokens: result.llm_stats.total_tokens,
                                        totalDurationMs: result.llm_stats.total_duration_ms,
                                        averageDurationMs: result.llm_stats.average_duration_ms
                                    }
                                }
                            }));
                    }
                } catch (error) {
                    console.error('Failed to fetch message details:', error);
                } finally{
                    setLoadingDetails((prev)=>({
                            ...prev,
                            [messageId]: false
                        }));
                }
            }
        }
    };
    const toggleErrorExpand = (errorId)=>{
        if (expandedErrorId === errorId) {
            setExpandedErrorId(null);
        } else {
            setExpandedErrorId(errorId);
        }
    };
    const jumpToMessage = async (messageId)=>{
        setActiveTab('messages');
        // Small delay to ensure tab transition completes before expanding
        setTimeout(()=>{
            toggleMessageExpand(messageId);
        }, 100);
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "w-full h-full flex flex-col",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex items-center justify-between mb-4 pb-4 border-b border-gray-200 dark:border-gray-700",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "text-sm text-gray-500 dark:text-gray-400",
                        children: t('pipelines.monitoring.description')
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 198,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex items-center gap-2",
                        children: [
                            onNavigateToMonitoring && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                variant: "outline",
                                size: "sm",
                                onClick: onNavigateToMonitoring,
                                className: "bg-white dark:bg-[#2a2a2e] hover:bg-gray-50 dark:hover:bg-gray-800 border-gray-300 dark:border-gray-600",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        className: "w-4 h-4 mr-2",
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M10 6V8H5V19H16V14H18V20C18 20.5523 17.5523 21 17 21H4C3.44772 21 3 20.5523 3 20V7C3 6.44772 3.44772 6 4 6H10ZM21 3V11H19V6.413L11.2071 14.2071L9.79289 12.7929L17.585 5H13V3H21Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                            lineNumber: 215,
                                            columnNumber: 17
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 209,
                                        columnNumber: 15
                                    }, this),
                                    t('pipelines.monitoring.detailedLogs')
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 203,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                variant: "outline",
                                size: "sm",
                                onClick: refetch,
                                className: "bg-white dark:bg-[#2a2a2e] hover:bg-gray-50 dark:hover:bg-gray-800 border-gray-300 dark:border-gray-600",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                        className: "w-4 h-4 mr-2",
                                        xmlns: "http://www.w3.org/2000/svg",
                                        viewBox: "0 0 24 24",
                                        fill: "currentColor",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                            d: "M5.46257 4.43262C7.21556 2.91688 9.5007 2 12 2C17.5228 2 22 6.47715 22 12C22 14.1361 21.3302 16.1158 20.1892 17.7406L17 12H20C20 7.58172 16.4183 4 12 4C9.84982 4 7.89777 4.84827 6.46023 6.22842L5.46257 4.43262ZM18.5374 19.5674C16.7844 21.0831 14.4993 22 12 22C6.47715 22 2 17.5228 2 12C2 9.86386 2.66979 7.88416 3.8108 6.25944L7 12H4C4 16.4183 7.58172 20 12 20C14.1502 20 16.1022 19.1517 17.5398 17.7716L18.5374 19.5674Z"
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                            lineNumber: 232,
                                            columnNumber: 15
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 226,
                                        columnNumber: 13
                                    }, this),
                                    t('monitoring.refreshData')
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 220,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 201,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                lineNumber: 197,
                columnNumber: 7
            }, this),
            data && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "grid grid-cols-3 gap-4 mb-6",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-4",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-sm text-gray-500 dark:text-gray-400",
                                children: t('monitoring.totalMessages')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 243,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1",
                                children: data.overview.totalMessages
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 246,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 242,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-4",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-sm text-gray-500 dark:text-gray-400",
                                children: t('monitoring.successRate')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 251,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1",
                                children: [
                                    data.overview.successRate.toFixed(1),
                                    "%"
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 254,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 250,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-4",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-sm text-gray-500 dark:text-gray-400",
                                children: t('monitoring.tabs.errors')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 259,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "text-2xl font-bold text-red-600 dark:text-red-400 mt-1",
                                children: data.errors.length
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 262,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 258,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                lineNumber: 241,
                columnNumber: 9
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tabs"], {
                value: activeTab,
                onValueChange: setActiveTab,
                className: "flex-1 flex flex-col min-h-0",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsList"], {
                        className: "bg-gray-100 dark:bg-[#1a1a1e] h-10 p-1 mb-4",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                value: "messages",
                                className: "px-4 py-1.5 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm",
                                children: t('monitoring.tabs.messages')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 276,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                value: "errors",
                                className: "px-4 py-1.5 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm",
                                children: t('monitoring.tabs.errors')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 282,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsTrigger"], {
                                value: "llmCalls",
                                className: "px-4 py-1.5 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm",
                                children: t('monitoring.tabs.modelCalls')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 288,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 275,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "flex-1 overflow-y-auto min-h-0",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsContent"], {
                                value: "messages",
                                className: "m-0 h-full",
                                children: [
                                    loading && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "py-12 flex justify-center",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                                            text: t('monitoring.messageList.loading')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                            lineNumber: 301,
                                            columnNumber: 17
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 300,
                                        columnNumber: 15
                                    }, this),
                                    !loading && data && data.messages && data.messages.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "space-y-3",
                                        children: data.messages.filter((msg)=>{
                                            const content = msg.messageContent?.trim();
                                            return content && content !== '[]' && content !== '""';
                                        }).map((msg)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden hover:shadow-md transition-all duration-200",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors",
                                                        onClick: ()=>toggleMessageExpand(msg.id),
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "flex items-start justify-between",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "flex items-start flex-1",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            className: "mr-2 mt-0.5",
                                                                            children: expandedMessageId === msg.id ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$down$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronDown$3e$__["ChevronDown"], {
                                                                                className: "w-4 h-4 text-gray-500"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 325,
                                                                                columnNumber: 33
                                                                            }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__["ChevronRight"], {
                                                                                className: "w-4 h-4 text-gray-500"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 327,
                                                                                columnNumber: 33
                                                                            }, this)
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 323,
                                                                            columnNumber: 29
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            className: "flex-1",
                                                                            children: [
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                    className: "flex items-center gap-2 mb-1",
                                                                                    children: [
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                            className: `text-xs px-2 py-0.5 rounded ${msg.status === 'success' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : msg.status === 'error' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'}`,
                                                                                            children: msg.status
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                            lineNumber: 332,
                                                                                            columnNumber: 33
                                                                                        }, this),
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                            className: "text-xs text-gray-500 dark:text-gray-400",
                                                                                            children: msg.botName
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                            lineNumber: 343,
                                                                                            columnNumber: 33
                                                                                        }, this)
                                                                                    ]
                                                                                }, void 0, true, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                    lineNumber: 331,
                                                                                    columnNumber: 31
                                                                                }, this),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                    className: "text-sm text-gray-700 dark:text-gray-300 line-clamp-2",
                                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$monitoring$2f$components$2f$MessageContentRenderer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["MessageContentRenderer"], {
                                                                                        content: msg.messageContent
                                                                                    }, void 0, false, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                        lineNumber: 348,
                                                                                        columnNumber: 33
                                                                                    }, this)
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                    lineNumber: 347,
                                                                                    columnNumber: 31
                                                                                }, this)
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 330,
                                                                            columnNumber: 29
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 322,
                                                                    columnNumber: 27
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    className: "text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4",
                                                                    children: msg.timestamp.toLocaleString()
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 354,
                                                                    columnNumber: 27
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                            lineNumber: 321,
                                                            columnNumber: 25
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                        lineNumber: 317,
                                                        columnNumber: 23
                                                    }, this),
                                                    expandedMessageId === msg.id && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-900",
                                                        children: [
                                                            loadingDetails[msg.id] && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "flex justify-center py-8",
                                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                                                                    text: t('monitoring.messageList.loading')
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 364,
                                                                    columnNumber: 31
                                                                }, this)
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                lineNumber: 363,
                                                                columnNumber: 29
                                                            }, this),
                                                            !loadingDetails[msg.id] && messageDetails[msg.id] && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                className: "space-y-4",
                                                                children: [
                                                                    messageDetails[msg.id].errors.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "bg-red-50 dark:bg-red-900/20 rounded-lg p-3",
                                                                        children: [
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h4", {
                                                                                className: "text-sm font-semibold text-red-700 dark:text-red-400 mb-2",
                                                                                children: t('monitoring.errors.errorMessage')
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 375,
                                                                                columnNumber: 37
                                                                            }, this),
                                                                            messageDetails[msg.id].errors.map((error)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                    className: "text-sm space-y-2",
                                                                                    children: [
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                            className: "text-red-600 dark:text-red-400",
                                                                                            children: [
                                                                                                error.errorType,
                                                                                                ":",
                                                                                                ' ',
                                                                                                error.errorMessage
                                                                                            ]
                                                                                        }, void 0, true, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                            lineNumber: 384,
                                                                                            columnNumber: 43
                                                                                        }, this),
                                                                                        error.stackTrace && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("pre", {
                                                                                            className: "text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-40 bg-white dark:bg-gray-900 p-2 rounded whitespace-pre-wrap break-words",
                                                                                            children: error.stackTrace
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                            lineNumber: 389,
                                                                                            columnNumber: 45
                                                                                        }, this)
                                                                                    ]
                                                                                }, error.id, true, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                    lineNumber: 380,
                                                                                    columnNumber: 41
                                                                                }, this))
                                                                        ]
                                                                    }, void 0, true, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                        lineNumber: 374,
                                                                        columnNumber: 35
                                                                    }, this),
                                                                    messageDetails[msg.id].llmCalls.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3",
                                                                        children: [
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h4", {
                                                                                className: "text-sm font-semibold text-blue-700 dark:text-blue-400 mb-2",
                                                                                children: [
                                                                                    t('monitoring.tabs.modelCalls'),
                                                                                    " (",
                                                                                    messageDetails[msg.id].llmCalls.length,
                                                                                    ")"
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 401,
                                                                                columnNumber: 37
                                                                            }, this),
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                className: "text-xs text-gray-600 dark:text-gray-400 space-y-1",
                                                                                children: [
                                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                        children: [
                                                                                            t('monitoring.llmCalls.totalTokens'),
                                                                                            ":",
                                                                                            ' ',
                                                                                            messageDetails[msg.id].llmStats.totalTokens
                                                                                        ]
                                                                                    }, void 0, true, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                        lineNumber: 406,
                                                                                        columnNumber: 39
                                                                                    }, this),
                                                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                        children: [
                                                                                            t('monitoring.llmCalls.duration'),
                                                                                            ":",
                                                                                            ' ',
                                                                                            messageDetails[msg.id].llmStats.totalDurationMs.toFixed(0),
                                                                                            "ms"
                                                                                        ]
                                                                                    }, void 0, true, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                        lineNumber: 413,
                                                                                        columnNumber: 39
                                                                                    }, this)
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 405,
                                                                                columnNumber: 37
                                                                            }, this)
                                                                        ]
                                                                    }, void 0, true, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                        lineNumber: 400,
                                                                        columnNumber: 35
                                                                    }, this)
                                                                ]
                                                            }, void 0, true, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                lineNumber: 372,
                                                                columnNumber: 31
                                                            }, this)
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                        lineNumber: 361,
                                                        columnNumber: 25
                                                    }, this)
                                                ]
                                            }, msg.id, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 313,
                                                columnNumber: 21
                                            }, this))
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 306,
                                        columnNumber: 15
                                    }, this),
                                    !loading && (!data || !data.messages || data.messages.length === 0) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-center text-gray-500 dark:text-gray-400 py-16",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                className: "w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600",
                                                fill: "none",
                                                viewBox: "0 0 24 24",
                                                stroke: "currentColor",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                    strokeLinecap: "round",
                                                    strokeLinejoin: "round",
                                                    strokeWidth: 1.5,
                                                    d: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                    lineNumber: 441,
                                                    columnNumber: 21
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 435,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                className: "text-base font-medium",
                                                children: t('monitoring.messageList.noMessages')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 448,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 434,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 298,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsContent"], {
                                value: "errors",
                                className: "m-0 h-full",
                                children: [
                                    loading && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "py-12 flex justify-center",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                                            text: t('common.loading')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                            lineNumber: 459,
                                            columnNumber: 17
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 458,
                                        columnNumber: 15
                                    }, this),
                                    !loading && data && data.errors && data.errors.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "space-y-3",
                                        children: data.errors.map((error)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "border border-red-200 dark:border-red-900 rounded-lg overflow-hidden hover:shadow-md transition-all duration-200",
                                                children: [
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "p-4 cursor-pointer hover:bg-red-50 dark:hover:bg-red-950/50 transition-colors bg-red-50/50 dark:bg-red-950/30",
                                                        onClick: ()=>toggleErrorExpand(error.id),
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "flex items-start justify-between",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "flex items-start flex-1",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            className: "mr-2 mt-0.5",
                                                                            children: expandedErrorId === error.id ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$down$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronDown$3e$__["ChevronDown"], {
                                                                                className: "w-4 h-4 text-red-500"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 478,
                                                                                columnNumber: 31
                                                                            }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__["ChevronRight"], {
                                                                                className: "w-4 h-4 text-red-500"
                                                                            }, void 0, false, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 480,
                                                                                columnNumber: 31
                                                                            }, this)
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 476,
                                                                            columnNumber: 27
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            className: "flex-1",
                                                                            children: [
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                    className: "flex items-center gap-2 mb-1",
                                                                                    children: error.messageId && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                                                                        variant: "ghost",
                                                                                        size: "sm",
                                                                                        className: "h-5 px-1.5 text-xs",
                                                                                        onClick: (e)=>{
                                                                                            e.stopPropagation();
                                                                                            jumpToMessage(error.messageId);
                                                                                        },
                                                                                        children: [
                                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$external$2d$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ExternalLink$3e$__["ExternalLink"], {
                                                                                                className: "w-3 h-3 mr-1"
                                                                                            }, void 0, false, {
                                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                                lineNumber: 495,
                                                                                                columnNumber: 35
                                                                                            }, this),
                                                                                            t('monitoring.messageList.viewConversation')
                                                                                        ]
                                                                                    }, void 0, true, {
                                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                        lineNumber: 486,
                                                                                        columnNumber: 33
                                                                                    }, this)
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                    lineNumber: 484,
                                                                                    columnNumber: 29
                                                                                }, this),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                                    className: "font-medium text-sm text-red-700 dark:text-red-300 mb-1",
                                                                                    children: error.errorType
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                    lineNumber: 500,
                                                                                    columnNumber: 29
                                                                                }, this),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                                                    className: "text-sm text-red-600 dark:text-red-400 line-clamp-2",
                                                                                    children: error.errorMessage
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                    lineNumber: 503,
                                                                                    columnNumber: 29
                                                                                }, this)
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 483,
                                                                            columnNumber: 27
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 475,
                                                                    columnNumber: 25
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    className: "text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4",
                                                                    children: error.timestamp.toLocaleString()
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 508,
                                                                    columnNumber: 25
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                            lineNumber: 474,
                                                            columnNumber: 23
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                        lineNumber: 470,
                                                        columnNumber: 21
                                                    }, this),
                                                    expandedErrorId === error.id && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                        className: "border-t border-red-200 dark:border-red-900 p-4 bg-white dark:bg-gray-900",
                                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "space-y-3",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "bg-red-50 dark:bg-red-900/20 rounded-lg p-3",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h4", {
                                                                            className: "text-sm font-semibold text-red-700 dark:text-red-400 mb-2",
                                                                            children: t('monitoring.errors.errorMessage')
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 518,
                                                                            columnNumber: 29
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            className: "text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap break-words",
                                                                            children: error.errorMessage
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 521,
                                                                            columnNumber: 29
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 517,
                                                                    columnNumber: 27
                                                                }, this),
                                                                error.stackTrace && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "bg-gray-50 dark:bg-gray-800 rounded-lg p-3",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h4", {
                                                                            className: "text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2",
                                                                            children: t('monitoring.errors.stackTrace')
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 528,
                                                                            columnNumber: 31
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("pre", {
                                                                            className: "text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-60 bg-white dark:bg-gray-900 p-2 rounded whitespace-pre-wrap break-words",
                                                                            children: error.stackTrace
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                            lineNumber: 531,
                                                                            columnNumber: 31
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 527,
                                                                    columnNumber: 29
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                            lineNumber: 516,
                                                            columnNumber: 25
                                                        }, this)
                                                    }, void 0, false, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                        lineNumber: 515,
                                                        columnNumber: 23
                                                    }, this)
                                                ]
                                            }, error.id, true, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 466,
                                                columnNumber: 19
                                            }, this))
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 464,
                                        columnNumber: 15
                                    }, this),
                                    !loading && (!data || !data.errors || data.errors.length === 0) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-center text-gray-500 dark:text-gray-400 py-16",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                className: "w-16 h-16 mx-auto mb-4 text-green-300 dark:text-green-600",
                                                fill: "none",
                                                viewBox: "0 0 24 24",
                                                stroke: "currentColor",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                    strokeLinecap: "round",
                                                    strokeLinejoin: "round",
                                                    strokeWidth: 1.5,
                                                    d: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                    lineNumber: 553,
                                                    columnNumber: 21
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 547,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                className: "text-base font-medium text-green-600 dark:text-green-400",
                                                children: t('monitoring.errors.noErrors')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 560,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 546,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 456,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$tabs$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TabsContent"], {
                                value: "llmCalls",
                                className: "m-0 h-full",
                                children: [
                                    loading && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "py-12 flex justify-center",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                                            text: t('common.loading')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                            lineNumber: 571,
                                            columnNumber: 17
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 570,
                                        columnNumber: 15
                                    }, this),
                                    !loading && data && data.llmCalls && data.llmCalls.length > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "space-y-3",
                                        children: data.llmCalls.map((call)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: "border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-all duration-200",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "flex items-start justify-between",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "flex-1",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "flex items-center gap-2 mb-2",
                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                        className: `text-xs px-2 py-0.5 rounded ${call.status === 'success' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'}`,
                                                                        children: call.status
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                        lineNumber: 585,
                                                                        columnNumber: 27
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 584,
                                                                    columnNumber: 25
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "font-medium text-sm text-gray-700 dark:text-gray-300 mb-2",
                                                                    children: call.modelName
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 595,
                                                                    columnNumber: 25
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "text-xs text-gray-600 dark:text-gray-400 space-y-1",
                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                        className: "flex flex-wrap gap-4",
                                                                        children: [
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                children: [
                                                                                    t('monitoring.llmCalls.inputTokens'),
                                                                                    ":",
                                                                                    ' ',
                                                                                    call.tokens.input
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 600,
                                                                                columnNumber: 29
                                                                            }, this),
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                children: [
                                                                                    t('monitoring.llmCalls.outputTokens'),
                                                                                    ":",
                                                                                    ' ',
                                                                                    call.tokens.output
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 604,
                                                                                columnNumber: 29
                                                                            }, this),
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                children: [
                                                                                    t('monitoring.llmCalls.totalTokens'),
                                                                                    ":",
                                                                                    ' ',
                                                                                    call.tokens.total
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 608,
                                                                                columnNumber: 29
                                                                            }, this),
                                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                children: [
                                                                                    t('monitoring.llmCalls.duration'),
                                                                                    ":",
                                                                                    ' ',
                                                                                    call.duration,
                                                                                    "ms"
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 612,
                                                                                columnNumber: 29
                                                                            }, this),
                                                                            call.cost && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                                children: [
                                                                                    t('monitoring.llmCalls.cost'),
                                                                                    ": $",
                                                                                    call.cost.toFixed(4)
                                                                                ]
                                                                            }, void 0, true, {
                                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                                lineNumber: 617,
                                                                                columnNumber: 31
                                                                            }, this)
                                                                        ]
                                                                    }, void 0, true, {
                                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                        lineNumber: 599,
                                                                        columnNumber: 27
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 598,
                                                                    columnNumber: 25
                                                                }, this),
                                                                call.errorMessage && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "mt-2 text-xs text-red-600 dark:text-red-400",
                                                                    children: [
                                                                        "Error: ",
                                                                        call.errorMessage
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                                    lineNumber: 625,
                                                                    columnNumber: 27
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                            lineNumber: 583,
                                                            columnNumber: 23
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: "text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4",
                                                            children: call.timestamp.toLocaleString()
                                                        }, void 0, false, {
                                                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                            lineNumber: 630,
                                                            columnNumber: 23
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                    lineNumber: 582,
                                                    columnNumber: 21
                                                }, this)
                                            }, call.id, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 578,
                                                columnNumber: 19
                                            }, this))
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 576,
                                        columnNumber: 15
                                    }, this),
                                    !loading && (!data || !data.llmCalls || data.llmCalls.length === 0) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "text-center text-gray-500 dark:text-gray-400 py-16",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                                                className: "w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600",
                                                fill: "none",
                                                viewBox: "0 0 24 24",
                                                stroke: "currentColor",
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                                    strokeLinecap: "round",
                                                    strokeLinejoin: "round",
                                                    strokeWidth: 1.5,
                                                    d: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                    lineNumber: 648,
                                                    columnNumber: 21
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 642,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                className: "text-base font-medium",
                                                children: t('monitoring.llmCalls.noData')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                                lineNumber: 655,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                        lineNumber: 641,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                                lineNumber: 568,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                        lineNumber: 296,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
                lineNumber: 270,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx",
        lineNumber: 195,
        columnNumber: 5
    }, this);
}
_s(PipelineMonitoringTab, "p2KmChUscg9dXcFLmUj1Hv5LzpA=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"],
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$monitoring$2f$hooks$2f$useMonitoringData$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMonitoringData"]
    ];
});
_c = PipelineMonitoringTab;
var _c;
__turbopack_context__.k.register(_c, "PipelineMonitoringTab");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PipelineDialog
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/dialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/sidebar.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$form$2f$PipelineFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$DebugDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$extensions$2f$PipelineExtension$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-extensions/PipelineExtension.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$monitoring$2d$tab$2f$PipelineMonitoringTab$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
;
;
;
;
;
;
;
;
;
function PipelineDialog({ open, onOpenChange, pipelineId: propPipelineId, isEditMode = false, onFinish, onNewPipelineCreated, onDeletePipeline, onCancel }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const [pipelineId, setPipelineId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(propPipelineId);
    const [currentMode, setCurrentMode] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('config');
    const [isWebSocketConnected, setIsWebSocketConnected] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PipelineDialog.useEffect": ()=>{
            setPipelineId(propPipelineId);
            setCurrentMode('config');
        }
    }["PipelineDialog.useEffect"], [
        propPipelineId,
        open
    ]);
    const handleFinish = ()=>{
        onFinish();
    };
    const handleNewPipelineCreated = (newPipelineId)=>{
        setPipelineId(newPipelineId);
        setCurrentMode('config');
        if (onNewPipelineCreated) {
            onNewPipelineCreated(newPipelineId);
        }
    };
    const menu = [
        {
            key: 'config',
            label: t('pipelines.configuration'),
            icon: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                xmlns: "http://www.w3.org/2000/svg",
                viewBox: "0 0 24 24",
                fill: "currentColor",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M5 7C5 6.17157 5.67157 5.5 6.5 5.5C7.32843 5.5 8 6.17157 8 7C8 7.82843 7.32843 8.5 6.5 8.5C5.67157 8.5 5 7.82843 5 7ZM6.5 3.5C4.567 3.5 3 5.067 3 7C3 8.933 4.567 10.5 6.5 10.5C8.433 10.5 10 8.933 10 7C10 5.067 8.433 3.5 6.5 3.5ZM12 8H20V6H12V8ZM16 17C16 16.1716 16.6716 15.5 17.5 15.5C18.3284 15.5 19 16.1716 19 17C19 17.8284 18.3284 18.5 17.5 18.5C16.6716 18.5 16 17.8284 16 17ZM17.5 13.5C15.567 13.5 14 15.067 14 17C14 18.933 15.567 20.5 17.5 20.5C19.433 20.5 21 18.933 21 17C21 15.067 19.433 13.5 17.5 13.5ZM4 16V18H12V16H4Z"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                    lineNumber: 84,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                lineNumber: 79,
                columnNumber: 9
            }, this)
        },
        {
            key: 'extensions',
            label: t('pipelines.extensions.title'),
            icon: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                xmlns: "http://www.w3.org/2000/svg",
                viewBox: "0 0 24 24",
                fill: "currentColor",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M7 5C7 2.79086 8.79086 1 11 1C13.2091 1 15 2.79086 15 5H18C18.5523 5 19 5.44772 19 6V9C21.2091 9 23 10.7909 23 13C23 15.2091 21.2091 17 19 17V20C19 20.5523 18.5523 21 18 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H7ZM11 3C9.89543 3 9 3.89543 9 5C9 5.23554 9.0403 5.45952 9.11355 5.66675C9.22172 5.97282 9.17461 6.31235 8.98718 6.57739C8.79974 6.84243 8.49532 7 8.17071 7H5V19H17V15.8293C17 15.5047 17.1576 15.2003 17.4226 15.0128C17.6877 14.8254 18.0272 14.7783 18.3332 14.8865C18.5405 14.9597 18.7645 15 19 15C20.1046 15 21 14.1046 21 13C21 11.8954 20.1046 11 19 11C18.7645 11 18.5405 11.0403 18.3332 11.1135C18.0272 11.2217 17.6877 11.1746 17.4226 10.9872C17.1576 10.7997 17 10.4953 17 10.1707V7H13.8293C13.5047 7 13.2003 6.84243 13.0128 6.57739C12.8254 6.31235 12.7783 5.97282 12.8865 5.66675C12.9597 5.45952 13 5.23555 13 5C13 3.89543 12.1046 3 11 3Z"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                    lineNumber: 97,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                lineNumber: 92,
                columnNumber: 9
            }, this)
        },
        {
            key: 'debug',
            label: t('pipelines.debugChat'),
            icon: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                xmlns: "http://www.w3.org/2000/svg",
                viewBox: "0 0 24 24",
                fill: "currentColor",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M13 19.9C15.2822 19.4367 17 17.419 17 15V12C17 11.299 16.8564 10.6219 16.5846 10H7.41538C7.14358 10.6219 7 11.299 7 12V15C7 17.419 8.71776 19.4367 11 19.9V14H13V19.9ZM5.5358 17.6907C5.19061 16.8623 5 15.9534 5 15H2V13H5V12C5 11.3573 5.08661 10.7348 5.2488 10.1436L3.0359 8.86602L4.0359 7.13397L6.05636 8.30049C6.11995 8.19854 6.18609 8.09835 6.25469 8H17.7453C17.8139 8.09835 17.88 8.19854 17.9436 8.30049L19.9641 7.13397L20.9641 8.86602L18.7512 10.1436C18.9134 10.7348 19 11.3573 19 12V13H22V15H19C19 15.9534 18.8094 16.8623 18.4642 17.6907L20.9641 19.134L19.9641 20.866L17.4383 19.4077C16.1549 20.9893 14.1955 22 12 22C9.80453 22 7.84512 20.9893 6.56171 19.4077L4.0359 20.866L3.0359 19.134L5.5358 17.6907ZM8 6C8 3.79086 9.79086 2 12 2C14.2091 2 16 3.79086 16 6H8Z"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                    lineNumber: 110,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                lineNumber: 105,
                columnNumber: 9
            }, this)
        },
        {
            key: 'monitoring',
            label: t('pipelines.monitoring.title'),
            icon: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                xmlns: "http://www.w3.org/2000/svg",
                viewBox: "0 0 24 24",
                fill: "currentColor",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M2 3.9934C2 3.44476 2.45531 3 2.9918 3H21.0082C21.556 3 22 3.44495 22 3.9934V20.0066C22 20.5552 21.5447 21 21.0082 21H2.9918C2.44405 21 2 20.5551 2 20.0066V3.9934ZM4 5V19H20V5H4ZM6 7H18V9H6V7ZM6 11H18V13H6V11ZM6 15H12V17H6V15Z"
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                    lineNumber: 123,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                lineNumber: 118,
                columnNumber: 9
            }, this)
        }
    ];
    const getDialogTitle = ()=>{
        if (currentMode === 'config') {
            return isEditMode ? t('pipelines.editPipeline') : t('pipelines.createPipeline');
        }
        if (currentMode === 'extensions') {
            return t('pipelines.extensions.title');
        }
        if (currentMode === 'monitoring') {
            return t('pipelines.monitoring.title');
        }
        return t('pipelines.debugDialog.title');
    };
    // 创建新流水线时的对话框
    if (!isEditMode) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
            open: open,
            onOpenChange: onOpenChange,
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
                className: "overflow-hidden p-0 !max-w-[40vw] max-h-[70vh] flex",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("main", {
                    className: "flex flex-1 flex-col h-[70vh]",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                            className: "px-6 pt-6 pb-4 shrink-0",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                children: t('pipelines.createPipeline')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                lineNumber: 151,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                            lineNumber: 150,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "flex-1 overflow-y-auto px-6 pb-6",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$form$2f$PipelineFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                onFinish: handleFinish,
                                onNewPipelineCreated: handleNewPipelineCreated,
                                isEditMode: isEditMode,
                                pipelineId: pipelineId,
                                disableForm: false,
                                showButtons: true,
                                onDeletePipeline: onDeletePipeline,
                                onCancel: ()=>{
                                    onCancel();
                                }
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                lineNumber: 154,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                            lineNumber: 153,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                    lineNumber: 149,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                lineNumber: 148,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
            lineNumber: 147,
            columnNumber: 7
        }, this);
    }
    // 编辑流水线时的对话框
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dialog"], {
        open: open,
        onOpenChange: onOpenChange,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogContent"], {
            className: "overflow-hidden p-0 !max-w-[80vw] h-[75vh] flex",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarProvider"], {
                className: "items-start w-full flex h-full min-h-0",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Sidebar"], {
                        collapsible: "none",
                        className: "hidden md:flex h-full min-h-0 w-40 border-r bg-white dark:bg-black",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarContent"], {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarGroup"], {
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarGroupContent"], {
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarMenu"], {
                                        children: menu.map((item)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarMenuItem"], {
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$sidebar$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SidebarMenuButton"], {
                                                    asChild: true,
                                                    isActive: currentMode === item.key,
                                                    onClick: ()=>setCurrentMode(item.key),
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                                        href: "#",
                                                        children: [
                                                            item.icon,
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                children: item.label
                                                            }, void 0, false, {
                                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                                                lineNumber: 195,
                                                                columnNumber: 29
                                                            }, this)
                                                        ]
                                                    }, void 0, true, {
                                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                                        lineNumber: 193,
                                                        columnNumber: 27
                                                    }, this)
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                                    lineNumber: 188,
                                                    columnNumber: 25
                                                }, this)
                                            }, item.key, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                                lineNumber: 187,
                                                columnNumber: 23
                                            }, this))
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 185,
                                        columnNumber: 19
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                    lineNumber: 184,
                                    columnNumber: 17
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                lineNumber: 183,
                                columnNumber: 15
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                            lineNumber: 182,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                        lineNumber: 178,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("main", {
                        className: "flex flex-1 flex-col h-full min-h-0",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogHeader"], {
                                className: "px-6 pt-6 pb-4 shrink-0 flex flex-row items-center justify-start",
                                style: {
                                    height: '4rem'
                                },
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$dialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DialogTitle"], {
                                        children: getDialogTitle()
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 210,
                                        columnNumber: 15
                                    }, this),
                                    currentMode === 'debug' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "flex items-center gap-2 ml-2",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                className: `w-2.5 h-2.5 rounded-full ${isWebSocketConnected ? 'bg-green-500' : 'bg-red-500'}`,
                                                title: isWebSocketConnected ? t('pipelines.debugDialog.connected') : t('pipelines.debugDialog.disconnected')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                                lineNumber: 213,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "text-sm text-gray-600 dark:text-gray-400",
                                                children: isWebSocketConnected ? t('pipelines.debugDialog.connected') : t('pipelines.debugDialog.disconnected')
                                            }, void 0, false, {
                                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                                lineNumber: 223,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 212,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                lineNumber: 206,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex-1 overflow-y-auto px-6 pb-4 w-full",
                                style: {
                                    height: 'calc(100% - 4rem)'
                                },
                                children: [
                                    currentMode === 'config' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$form$2f$PipelineFormComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                        onFinish: handleFinish,
                                        onNewPipelineCreated: handleNewPipelineCreated,
                                        isEditMode: isEditMode,
                                        pipelineId: pipelineId,
                                        disableForm: false,
                                        showButtons: true,
                                        onDeletePipeline: onDeletePipeline,
                                        onCancel: ()=>{
                                            onCancel();
                                        }
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 236,
                                        columnNumber: 17
                                    }, this),
                                    currentMode === 'extensions' && pipelineId && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$extensions$2f$PipelineExtension$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                        pipelineId: pipelineId
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 251,
                                        columnNumber: 17
                                    }, this),
                                    currentMode === 'debug' && pipelineId && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$debug$2d$dialog$2f$DebugDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                        open: true,
                                        pipelineId: pipelineId,
                                        isEmbedded: true,
                                        onConnectionStatusChange: setIsWebSocketConnected
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 255,
                                        columnNumber: 17
                                    }, this),
                                    currentMode === 'monitoring' && pipelineId && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$monitoring$2d$tab$2f$PipelineMonitoringTab$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                        pipelineId: pipelineId,
                                        onNavigateToMonitoring: ()=>{
                                            router.push(`/home/monitoring?pipelineId=${pipelineId}`);
                                            onOpenChange(false);
                                        }
                                    }, void 0, false, {
                                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                        lineNumber: 264,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                                lineNumber: 231,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                        lineNumber: 205,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
                lineNumber: 177,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
            lineNumber: 176,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx",
        lineNumber: 175,
        columnNumber: 5
    }, this);
}
_s(PipelineDialog, "9X2cbBOokDhE7c1qdVPbehMutTw=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"],
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"]
    ];
});
_c = PipelineDialog;
var _c;
__turbopack_context__.k.register(_c, "PipelineDialog");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>PluginConfigPage
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$basic$2d$component$2f$create$2d$card$2d$component$2f$CreateCardComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/basic-component/create-card-component/CreateCardComponent.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$PipelineCardVO$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCardVO.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$PipelineCard$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/components/pipeline-card/PipelineCard.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$pipelineConfig$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/pipelineConfig.module.css [app-client] (css module)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$PipelineDetailDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/home/pipelines/PipelineDetailDialog.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/select.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>");
;
var _s = __turbopack_context__.k.signature();
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
function PluginConfigPage() {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [dialogOpen, setDialogOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [isEditForm, setIsEditForm] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [pipelineList, setPipelineList] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const [selectedPipelineId, setSelectedPipelineId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const [sortByValue, setSortByValue] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('created_at');
    const [sortOrderValue, setSortOrderValue] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('DESC');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PluginConfigPage.useEffect": ()=>{
            // Load sort preference from localStorage
            const savedSortBy = localStorage.getItem('pipeline_sort_by');
            const savedSortOrder = localStorage.getItem('pipeline_sort_order');
            if (savedSortBy && savedSortOrder) {
                setSortByValue(savedSortBy);
                setSortOrderValue(savedSortOrder);
                getPipelines(savedSortBy, savedSortOrder);
            } else {
                getPipelines();
            }
        }
    }["PluginConfigPage.useEffect"], []);
    function getPipelines(sortBy = sortByValue, sortOrder = sortOrderValue) {
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].getPipelines(sortBy, sortOrder).then((value)=>{
            const currentTime = new Date();
            const pipelineList = value.pipelines.map((pipeline)=>{
                const lastUpdatedTimeAgo = Math.floor((currentTime.getTime() - new Date(pipeline.updated_at ?? currentTime.getTime()).getTime()) / 1000 / 60 / 60 / 24);
                const lastUpdatedTimeAgoText = lastUpdatedTimeAgo > 0 ? ` ${lastUpdatedTimeAgo} ${t('pipelines.daysAgo')}` : t('pipelines.today');
                return new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$PipelineCardVO$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PipelineCardVO"]({
                    lastUpdatedTimeAgo: lastUpdatedTimeAgoText,
                    description: pipeline.description,
                    id: pipeline.uuid ?? '',
                    name: pipeline.name,
                    emoji: pipeline.emoji,
                    isDefault: pipeline.is_default ?? false
                });
            });
            setPipelineList(pipelineList);
        }).catch((error)=>{
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('pipelines.getPipelineListError') + error.message);
        });
    }
    const handlePipelineClick = (pipelineId)=>{
        setSelectedPipelineId(pipelineId);
        setIsEditForm(true);
        setDialogOpen(true);
    };
    const handleCreateNew = ()=>{
        const maxPipelines = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["systemInfo"].limitation?.max_pipelines ?? -1;
        if (maxPipelines >= 0 && pipelineList.length >= maxPipelines) {
            __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].error(t('limitation.maxPipelinesReached', {
                max: maxPipelines
            }));
            return;
        }
        setIsEditForm(false);
        setSelectedPipelineId('');
        setDialogOpen(true);
    };
    function handleSortChange(value) {
        const [newSortBy, newSortOrder] = value.split(',').map((s)=>s.trim());
        setSortByValue(newSortBy);
        setSortOrderValue(newSortOrder);
        // Save sort preference to localStorage
        localStorage.setItem('pipeline_sort_by', newSortBy);
        localStorage.setItem('pipeline_sort_order', newSortOrder);
        getPipelines(newSortBy, newSortOrder);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$pipelineConfig$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].configPageContainer,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$PipelineDetailDialog$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                open: dialogOpen,
                onOpenChange: setDialogOpen,
                pipelineId: selectedPipelineId || undefined,
                isEditMode: isEditForm,
                onFinish: ()=>{
                    getPipelines();
                },
                onNewPipelineCreated: (pipelineId)=>{
                    getPipelines();
                    setSelectedPipelineId(pipelineId);
                    setIsEditForm(true);
                    setDialogOpen(true);
                },
                onDeletePipeline: ()=>{
                    getPipelines();
                    setDialogOpen(false);
                },
                onCancel: ()=>{
                    setDialogOpen(false);
                }
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                lineNumber: 115,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "flex flex-row justify-between items-center mb-4 px-[0.8rem]",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Select"], {
                    value: `${sortByValue},${sortOrderValue}`,
                    onValueChange: handleSortChange,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectTrigger"], {
                            className: "w-[180px] cursor-pointer bg-[#ffffff] dark:bg-[#2a2a2e]",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectValue"], {
                                placeholder: t('pipelines.sortBy')
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                                lineNumber: 144,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                            lineNumber: 143,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectContent"], {
                            className: "bg-[#ffffff] dark:bg-[#2a2a2e]",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: "created_at,DESC",
                                    className: "text-gray-900 dark:text-gray-100",
                                    children: t('pipelines.newestCreated')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                                    lineNumber: 147,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: "created_at,ASC",
                                    className: "text-gray-900 dark:text-gray-100",
                                    children: t('pipelines.earliestCreated')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                                    lineNumber: 153,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: "updated_at,DESC",
                                    className: "text-gray-900 dark:text-gray-100",
                                    children: t('pipelines.recentlyEdited')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                                    lineNumber: 159,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$select$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SelectItem"], {
                                    value: "updated_at,ASC",
                                    className: "text-gray-900 dark:text-gray-100",
                                    children: t('pipelines.earliestEdited')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                                    lineNumber: 165,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                            lineNumber: 146,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                    lineNumber: 139,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                lineNumber: 138,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$pipelineConfig$2e$module$2e$css__$5b$app$2d$client$5d$__$28$css__module$29$__["default"].pipelineListContainer,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$basic$2d$component$2f$create$2d$card$2d$component$2f$CreateCardComponent$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                        width: '100%',
                        height: '10rem',
                        plusSize: '90px',
                        onClick: handleCreateNew
                    }, void 0, false, {
                        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                        lineNumber: 175,
                        columnNumber: 9
                    }, this),
                    pipelineList.map((pipeline)=>{
                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            onClick: ()=>handlePipelineClick(pipeline.id),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$home$2f$pipelines$2f$components$2f$pipeline$2d$card$2f$PipelineCard$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                cardVO: pipeline
                            }, void 0, false, {
                                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                                lineNumber: 188,
                                columnNumber: 15
                            }, this)
                        }, pipeline.id, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                            lineNumber: 184,
                            columnNumber: 13
                        }, this);
                    })
                ]
            }, void 0, true, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
                lineNumber: 174,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/home/pipelines/page.tsx",
        lineNumber: 114,
        columnNumber: 5
    }, this);
}
_s(PluginConfigPage, "fXzaZbwEyfChopm5sk91/I7cTYU=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"]
    ];
});
_c = PluginConfigPage;
var _c;
__turbopack_context__.k.register(_c, "PluginConfigPage");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
]);

//# sourceMappingURL=coding_projects_LangBot_web_src_0574bc2e._.js.map