(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "compareValues",
    ()=>compareValues,
    "findEntryInArray",
    ()=>findEntryInArray,
    "getAnyElementOfObject",
    ()=>getAnyElementOfObject,
    "getLinearRegression",
    ()=>getLinearRegression,
    "getPercentValue",
    ()=>getPercentValue,
    "hasDuplicate",
    ()=>hasDuplicate,
    "interpolateNumber",
    ()=>interpolateNumber,
    "isNullish",
    ()=>isNullish,
    "isNumOrStr",
    ()=>isNumOrStr,
    "isNumber",
    ()=>isNumber,
    "isPercent",
    ()=>isPercent,
    "mathSign",
    ()=>mathSign,
    "uniqueId",
    ()=>uniqueId
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isString.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNaN.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNumber$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNumber.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
;
;
;
;
;
var mathSign = function mathSign(value) {
    if (value === 0) {
        return 0;
    }
    if (value > 0) {
        return 1;
    }
    return -1;
};
var isPercent = function isPercent(value) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value) && value.indexOf('%') === value.length - 1;
};
var isNumber = function isNumber(value) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNumber$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value);
};
var isNullish = function isNullish(value) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value);
};
var isNumOrStr = function isNumOrStr(value) {
    return isNumber(value) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value);
};
var idCounter = 0;
var uniqueId = function uniqueId(prefix) {
    var id = ++idCounter;
    return "".concat(prefix || '').concat(id);
};
var getPercentValue = function getPercentValue(percent, totalValue) {
    var defaultValue = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 0;
    var validate = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : false;
    if (!isNumber(percent) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(percent)) {
        return defaultValue;
    }
    var value;
    if (isPercent(percent)) {
        var index = percent.indexOf('%');
        value = totalValue * parseFloat(percent.slice(0, index)) / 100;
    } else {
        value = +percent;
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value)) {
        value = defaultValue;
    }
    if (validate && value > totalValue) {
        value = totalValue;
    }
    return value;
};
var getAnyElementOfObject = function getAnyElementOfObject(obj) {
    if (!obj) {
        return null;
    }
    var keys = Object.keys(obj);
    if (keys && keys.length) {
        return obj[keys[0]];
    }
    return null;
};
var hasDuplicate = function hasDuplicate(ary) {
    if (!Array.isArray(ary)) {
        return false;
    }
    var len = ary.length;
    var cache = {};
    for(var i = 0; i < len; i++){
        if (!cache[ary[i]]) {
            cache[ary[i]] = true;
        } else {
            return true;
        }
    }
    return false;
};
var interpolateNumber = function interpolateNumber(numberA, numberB) {
    if (isNumber(numberA) && isNumber(numberB)) {
        return function(t) {
            return numberA + t * (numberB - numberA);
        };
    }
    return function() {
        return numberB;
    };
};
function findEntryInArray(ary, specifiedKey, specifiedValue) {
    if (!ary || !ary.length) {
        return null;
    }
    return ary.find(function(entry) {
        return entry && (typeof specifiedKey === 'function' ? specifiedKey(entry) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry, specifiedKey)) === specifiedValue;
    });
}
var getLinearRegression = function getLinearRegression(data) {
    if (!data || !data.length) {
        return null;
    }
    var len = data.length;
    var xsum = 0;
    var ysum = 0;
    var xysum = 0;
    var xxsum = 0;
    var xmin = Infinity;
    var xmax = -Infinity;
    var xcurrent = 0;
    var ycurrent = 0;
    for(var i = 0; i < len; i++){
        xcurrent = data[i].cx || 0;
        ycurrent = data[i].cy || 0;
        xsum += xcurrent;
        ysum += ycurrent;
        xysum += xcurrent * ycurrent;
        xxsum += xcurrent * xcurrent;
        xmin = Math.min(xmin, xcurrent);
        xmax = Math.max(xmax, xcurrent);
    }
    var a = len * xxsum !== xsum * xsum ? (len * xysum - xsum * ysum) / (len * xxsum - xsum * xsum) : 0;
    return {
        xmin: xmin,
        xmax: xmax,
        a: a,
        b: (ysum - a * xsum) / len
    };
};
var compareValues = function compareValues(a, b) {
    if (isNumber(a) && isNumber(b)) {
        return a - b;
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(a) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(b)) {
        return a.localeCompare(b);
    }
    if (a instanceof Date && b instanceof Date) {
        return a.getTime() - b.getTime();
    }
    return String(a).localeCompare(String(b));
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ShallowEqual.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "shallowEqual",
    ()=>shallowEqual
]);
function shallowEqual(a, b) {
    /* eslint-disable no-restricted-syntax */ for(var key in a){
        if (({}).hasOwnProperty.call(a, key) && (!({}).hasOwnProperty.call(b, key) || a[key] !== b[key])) {
            return false;
        }
    }
    for(var _key in b){
        if (({}).hasOwnProperty.call(b, _key) && !({}).hasOwnProperty.call(a, _key)) {
            return false;
        }
    }
    return true;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "EventKeys",
    ()=>EventKeys,
    "FilteredElementKeyMap",
    ()=>FilteredElementKeyMap,
    "SVGElementPropKeys",
    ()=>SVGElementPropKeys,
    "adaptEventHandlers",
    ()=>adaptEventHandlers,
    "adaptEventsOfChild",
    ()=>adaptEventsOfChild
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
;
;
/**
 * Determines how values are stacked:
 *
 * - `none` is the default, it adds values on top of each other. No smarts. Negative values will overlap.
 * - `expand` make it so that the values always add up to 1 - so the chart will look like a rectangle.
 * - `wiggle` and `silhouette` tries to keep the chart centered.
 * - `sign` stacks positive values above zero and negative values below zero. Similar to `none` but handles negatives.
 * - `positive` ignores all negative values, and then behaves like \`none\`.
 *
 * Also see https://d3js.org/d3-shape/stack#stack-offsets
 * (note that the `diverging` offset in d3 is named `sign` in recharts)
 */ //
// Event Handler Types -- Copied from @types/react/index.d.ts and adapted for Props.
//
var SVGContainerPropKeys = [
    'viewBox',
    'children'
];
var SVGElementPropKeys = [
    'aria-activedescendant',
    'aria-atomic',
    'aria-autocomplete',
    'aria-busy',
    'aria-checked',
    'aria-colcount',
    'aria-colindex',
    'aria-colspan',
    'aria-controls',
    'aria-current',
    'aria-describedby',
    'aria-details',
    'aria-disabled',
    'aria-errormessage',
    'aria-expanded',
    'aria-flowto',
    'aria-haspopup',
    'aria-hidden',
    'aria-invalid',
    'aria-keyshortcuts',
    'aria-label',
    'aria-labelledby',
    'aria-level',
    'aria-live',
    'aria-modal',
    'aria-multiline',
    'aria-multiselectable',
    'aria-orientation',
    'aria-owns',
    'aria-placeholder',
    'aria-posinset',
    'aria-pressed',
    'aria-readonly',
    'aria-relevant',
    'aria-required',
    'aria-roledescription',
    'aria-rowcount',
    'aria-rowindex',
    'aria-rowspan',
    'aria-selected',
    'aria-setsize',
    'aria-sort',
    'aria-valuemax',
    'aria-valuemin',
    'aria-valuenow',
    'aria-valuetext',
    'className',
    'color',
    'height',
    'id',
    'lang',
    'max',
    'media',
    'method',
    'min',
    'name',
    'style',
    /*
 * removed 'type' SVGElementPropKey because we do not currently use any SVG elements
 * that can use it and it conflicts with the recharts prop 'type'
 * https://github.com/recharts/recharts/pull/3327
 * https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/type
 */ // 'type',
    'target',
    'width',
    'role',
    'tabIndex',
    'accentHeight',
    'accumulate',
    'additive',
    'alignmentBaseline',
    'allowReorder',
    'alphabetic',
    'amplitude',
    'arabicForm',
    'ascent',
    'attributeName',
    'attributeType',
    'autoReverse',
    'azimuth',
    'baseFrequency',
    'baselineShift',
    'baseProfile',
    'bbox',
    'begin',
    'bias',
    'by',
    'calcMode',
    'capHeight',
    'clip',
    'clipPath',
    'clipPathUnits',
    'clipRule',
    'colorInterpolation',
    'colorInterpolationFilters',
    'colorProfile',
    'colorRendering',
    'contentScriptType',
    'contentStyleType',
    'cursor',
    'cx',
    'cy',
    'd',
    'decelerate',
    'descent',
    'diffuseConstant',
    'direction',
    'display',
    'divisor',
    'dominantBaseline',
    'dur',
    'dx',
    'dy',
    'edgeMode',
    'elevation',
    'enableBackground',
    'end',
    'exponent',
    'externalResourcesRequired',
    'fill',
    'fillOpacity',
    'fillRule',
    'filter',
    'filterRes',
    'filterUnits',
    'floodColor',
    'floodOpacity',
    'focusable',
    'fontFamily',
    'fontSize',
    'fontSizeAdjust',
    'fontStretch',
    'fontStyle',
    'fontVariant',
    'fontWeight',
    'format',
    'from',
    'fx',
    'fy',
    'g1',
    'g2',
    'glyphName',
    'glyphOrientationHorizontal',
    'glyphOrientationVertical',
    'glyphRef',
    'gradientTransform',
    'gradientUnits',
    'hanging',
    'horizAdvX',
    'horizOriginX',
    'href',
    'ideographic',
    'imageRendering',
    'in2',
    'in',
    'intercept',
    'k1',
    'k2',
    'k3',
    'k4',
    'k',
    'kernelMatrix',
    'kernelUnitLength',
    'kerning',
    'keyPoints',
    'keySplines',
    'keyTimes',
    'lengthAdjust',
    'letterSpacing',
    'lightingColor',
    'limitingConeAngle',
    'local',
    'markerEnd',
    'markerHeight',
    'markerMid',
    'markerStart',
    'markerUnits',
    'markerWidth',
    'mask',
    'maskContentUnits',
    'maskUnits',
    'mathematical',
    'mode',
    'numOctaves',
    'offset',
    'opacity',
    'operator',
    'order',
    'orient',
    'orientation',
    'origin',
    'overflow',
    'overlinePosition',
    'overlineThickness',
    'paintOrder',
    'panose1',
    'pathLength',
    'patternContentUnits',
    'patternTransform',
    'patternUnits',
    'pointerEvents',
    'pointsAtX',
    'pointsAtY',
    'pointsAtZ',
    'preserveAlpha',
    'preserveAspectRatio',
    'primitiveUnits',
    'r',
    'radius',
    'refX',
    'refY',
    'renderingIntent',
    'repeatCount',
    'repeatDur',
    'requiredExtensions',
    'requiredFeatures',
    'restart',
    'result',
    'rotate',
    'rx',
    'ry',
    'seed',
    'shapeRendering',
    'slope',
    'spacing',
    'specularConstant',
    'specularExponent',
    'speed',
    'spreadMethod',
    'startOffset',
    'stdDeviation',
    'stemh',
    'stemv',
    'stitchTiles',
    'stopColor',
    'stopOpacity',
    'strikethroughPosition',
    'strikethroughThickness',
    'string',
    'stroke',
    'strokeDasharray',
    'strokeDashoffset',
    'strokeLinecap',
    'strokeLinejoin',
    'strokeMiterlimit',
    'strokeOpacity',
    'strokeWidth',
    'surfaceScale',
    'systemLanguage',
    'tableValues',
    'targetX',
    'targetY',
    'textAnchor',
    'textDecoration',
    'textLength',
    'textRendering',
    'to',
    'transform',
    'u1',
    'u2',
    'underlinePosition',
    'underlineThickness',
    'unicode',
    'unicodeBidi',
    'unicodeRange',
    'unitsPerEm',
    'vAlphabetic',
    'values',
    'vectorEffect',
    'version',
    'vertAdvY',
    'vertOriginX',
    'vertOriginY',
    'vHanging',
    'vIdeographic',
    'viewTarget',
    'visibility',
    'vMathematical',
    'widths',
    'wordSpacing',
    'writingMode',
    'x1',
    'x2',
    'x',
    'xChannelSelector',
    'xHeight',
    'xlinkActuate',
    'xlinkArcrole',
    'xlinkHref',
    'xlinkRole',
    'xlinkShow',
    'xlinkTitle',
    'xlinkType',
    'xmlBase',
    'xmlLang',
    'xmlns',
    'xmlnsXlink',
    'xmlSpace',
    'y1',
    'y2',
    'y',
    'yChannelSelector',
    'z',
    'zoomAndPan',
    'ref',
    'key',
    'angle'
];
var PolyElementKeys = [
    'points',
    'pathLength'
];
var FilteredElementKeyMap = {
    svg: SVGContainerPropKeys,
    polygon: PolyElementKeys,
    polyline: PolyElementKeys
};
var EventKeys = [
    'dangerouslySetInnerHTML',
    'onCopy',
    'onCopyCapture',
    'onCut',
    'onCutCapture',
    'onPaste',
    'onPasteCapture',
    'onCompositionEnd',
    'onCompositionEndCapture',
    'onCompositionStart',
    'onCompositionStartCapture',
    'onCompositionUpdate',
    'onCompositionUpdateCapture',
    'onFocus',
    'onFocusCapture',
    'onBlur',
    'onBlurCapture',
    'onChange',
    'onChangeCapture',
    'onBeforeInput',
    'onBeforeInputCapture',
    'onInput',
    'onInputCapture',
    'onReset',
    'onResetCapture',
    'onSubmit',
    'onSubmitCapture',
    'onInvalid',
    'onInvalidCapture',
    'onLoad',
    'onLoadCapture',
    'onError',
    'onErrorCapture',
    'onKeyDown',
    'onKeyDownCapture',
    'onKeyPress',
    'onKeyPressCapture',
    'onKeyUp',
    'onKeyUpCapture',
    'onAbort',
    'onAbortCapture',
    'onCanPlay',
    'onCanPlayCapture',
    'onCanPlayThrough',
    'onCanPlayThroughCapture',
    'onDurationChange',
    'onDurationChangeCapture',
    'onEmptied',
    'onEmptiedCapture',
    'onEncrypted',
    'onEncryptedCapture',
    'onEnded',
    'onEndedCapture',
    'onLoadedData',
    'onLoadedDataCapture',
    'onLoadedMetadata',
    'onLoadedMetadataCapture',
    'onLoadStart',
    'onLoadStartCapture',
    'onPause',
    'onPauseCapture',
    'onPlay',
    'onPlayCapture',
    'onPlaying',
    'onPlayingCapture',
    'onProgress',
    'onProgressCapture',
    'onRateChange',
    'onRateChangeCapture',
    'onSeeked',
    'onSeekedCapture',
    'onSeeking',
    'onSeekingCapture',
    'onStalled',
    'onStalledCapture',
    'onSuspend',
    'onSuspendCapture',
    'onTimeUpdate',
    'onTimeUpdateCapture',
    'onVolumeChange',
    'onVolumeChangeCapture',
    'onWaiting',
    'onWaitingCapture',
    'onAuxClick',
    'onAuxClickCapture',
    'onClick',
    'onClickCapture',
    'onContextMenu',
    'onContextMenuCapture',
    'onDoubleClick',
    'onDoubleClickCapture',
    'onDrag',
    'onDragCapture',
    'onDragEnd',
    'onDragEndCapture',
    'onDragEnter',
    'onDragEnterCapture',
    'onDragExit',
    'onDragExitCapture',
    'onDragLeave',
    'onDragLeaveCapture',
    'onDragOver',
    'onDragOverCapture',
    'onDragStart',
    'onDragStartCapture',
    'onDrop',
    'onDropCapture',
    'onMouseDown',
    'onMouseDownCapture',
    'onMouseEnter',
    'onMouseLeave',
    'onMouseMove',
    'onMouseMoveCapture',
    'onMouseOut',
    'onMouseOutCapture',
    'onMouseOver',
    'onMouseOverCapture',
    'onMouseUp',
    'onMouseUpCapture',
    'onSelect',
    'onSelectCapture',
    'onTouchCancel',
    'onTouchCancelCapture',
    'onTouchEnd',
    'onTouchEndCapture',
    'onTouchMove',
    'onTouchMoveCapture',
    'onTouchStart',
    'onTouchStartCapture',
    'onPointerDown',
    'onPointerDownCapture',
    'onPointerMove',
    'onPointerMoveCapture',
    'onPointerUp',
    'onPointerUpCapture',
    'onPointerCancel',
    'onPointerCancelCapture',
    'onPointerEnter',
    'onPointerEnterCapture',
    'onPointerLeave',
    'onPointerLeaveCapture',
    'onPointerOver',
    'onPointerOverCapture',
    'onPointerOut',
    'onPointerOutCapture',
    'onGotPointerCapture',
    'onGotPointerCaptureCapture',
    'onLostPointerCapture',
    'onLostPointerCaptureCapture',
    'onScroll',
    'onScrollCapture',
    'onWheel',
    'onWheelCapture',
    'onAnimationStart',
    'onAnimationStartCapture',
    'onAnimationEnd',
    'onAnimationEndCapture',
    'onAnimationIteration',
    'onAnimationIterationCapture',
    'onTransitionEnd',
    'onTransitionEndCapture'
];
var adaptEventHandlers = function adaptEventHandlers(props, newHandler) {
    if (!props || typeof props === 'function' || typeof props === 'boolean') {
        return null;
    }
    var inputProps = props;
    if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(props)) {
        inputProps = props.props;
    }
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(inputProps)) {
        return null;
    }
    var out = {};
    Object.keys(inputProps).forEach(function(key) {
        if (EventKeys.includes(key)) {
            out[key] = newHandler || function(e) {
                return inputProps[key](inputProps, e);
            };
        }
    });
    return out;
};
var getEventHandlerOfChild = function getEventHandlerOfChild(originalHandler, data, index) {
    return function(e) {
        originalHandler(data, index, e);
        return null;
    };
};
var adaptEventsOfChild = function adaptEventsOfChild(props, data, index) {
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(props) || _typeof(props) !== 'object') {
        return null;
    }
    var out = null;
    Object.keys(props).forEach(function(key) {
        var item = props[key];
        if (EventKeys.includes(key) && typeof item === 'function') {
            if (!out) out = {};
            out[key] = getEventHandlerOfChild(item, data, index);
        }
    });
    return out;
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LEGEND_TYPES",
    ()=>LEGEND_TYPES,
    "SCALE_TYPES",
    ()=>SCALE_TYPES,
    "TOOLTIP_TYPES",
    ()=>TOOLTIP_TYPES,
    "filterProps",
    ()=>filterProps,
    "filterSvgElements",
    ()=>filterSvgElements,
    "findAllByType",
    ()=>findAllByType,
    "findChildByType",
    ()=>findChildByType,
    "getDisplayName",
    ()=>getDisplayName,
    "getReactEventByType",
    ()=>getReactEventByType,
    "hasClipDot",
    ()=>hasClipDot,
    "isChildrenEqual",
    ()=>isChildrenEqual,
    "isSingleChildEqual",
    ()=>isSingleChildEqual,
    "isValidSpreadableProp",
    ()=>isValidSpreadableProp,
    "parseChildIndex",
    ()=>parseChildIndex,
    "renderByOrder",
    ()=>renderByOrder,
    "toArray",
    ()=>toArray,
    "validateWidthHeight",
    ()=>validateWidthHeight,
    "withoutType",
    ()=>withoutType
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isString.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$node_modules$2f$react$2d$is$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/node_modules/react-is/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ShallowEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
var _excluded = [
    "children"
], _excluded2 = [
    "children"
];
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
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
var REACT_BROWSER_EVENT_MAP = {
    click: 'onClick',
    mousedown: 'onMouseDown',
    mouseup: 'onMouseUp',
    mouseover: 'onMouseOver',
    mousemove: 'onMouseMove',
    mouseout: 'onMouseOut',
    mouseenter: 'onMouseEnter',
    mouseleave: 'onMouseLeave',
    touchcancel: 'onTouchCancel',
    touchend: 'onTouchEnd',
    touchmove: 'onTouchMove',
    touchstart: 'onTouchStart',
    contextmenu: 'onContextMenu',
    dblclick: 'onDoubleClick'
};
var SCALE_TYPES = [
    'auto',
    'linear',
    'pow',
    'sqrt',
    'log',
    'identity',
    'time',
    'band',
    'point',
    'ordinal',
    'quantile',
    'quantize',
    'utc',
    'sequential',
    'threshold'
];
var LEGEND_TYPES = [
    'plainline',
    'line',
    'square',
    'rect',
    'circle',
    'cross',
    'diamond',
    'star',
    'triangle',
    'wye',
    'none'
];
var TOOLTIP_TYPES = [
    'none'
];
var getDisplayName = function getDisplayName(Comp) {
    if (typeof Comp === 'string') {
        return Comp;
    }
    if (!Comp) {
        return '';
    }
    return Comp.displayName || Comp.name || 'Component';
};
// `toArray` gets called multiple times during the render
// so we can memoize last invocation (since reference to `children` is the same)
var lastChildren = null;
var lastResult = null;
var toArray = function toArray(children) {
    if (children === lastChildren && Array.isArray(lastResult)) {
        return lastResult;
    }
    var result = [];
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].forEach(children, function(child) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(child)) return;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$node_modules$2f$react$2d$is$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isFragment"])(child)) {
            result = result.concat(toArray(child.props.children));
        } else {
            // @ts-expect-error this could still be Iterable<ReactNode> and TS does not like that
            result.push(child);
        }
    });
    lastResult = result;
    lastChildren = children;
    return result;
};
function findAllByType(children, type) {
    var result = [];
    var types = [];
    if (Array.isArray(type)) {
        types = type.map(function(t) {
            return getDisplayName(t);
        });
    } else {
        types = [
            getDisplayName(type)
        ];
    }
    toArray(children).forEach(function(child) {
        var childType = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(child, 'type.displayName') || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(child, 'type.name');
        if (types.indexOf(childType) !== -1) {
            result.push(child);
        }
    });
    return result;
}
function findChildByType(children, type) {
    var result = findAllByType(children, type);
    return result && result[0];
}
var withoutType = function withoutType(children, type) {
    var newChildren = [];
    var types;
    if (Array.isArray(type)) {
        types = type.map(function(t) {
            return getDisplayName(t);
        });
    } else {
        types = [
            getDisplayName(type)
        ];
    }
    toArray(children).forEach(function(child) {
        var displayName = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(child, 'type.displayName');
        if (displayName && types.indexOf(displayName) !== -1) {
            return;
        }
        newChildren.push(child);
    });
    return newChildren;
};
var validateWidthHeight = function validateWidthHeight(el) {
    if (!el || !el.props) {
        return false;
    }
    var _el$props = el.props, width = _el$props.width, height = _el$props.height;
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(width) || width <= 0 || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(height) || height <= 0) {
        return false;
    }
    return true;
};
var SVG_TAGS = [
    'a',
    'altGlyph',
    'altGlyphDef',
    'altGlyphItem',
    'animate',
    'animateColor',
    'animateMotion',
    'animateTransform',
    'circle',
    'clipPath',
    'color-profile',
    'cursor',
    'defs',
    'desc',
    'ellipse',
    'feBlend',
    'feColormatrix',
    'feComponentTransfer',
    'feComposite',
    'feConvolveMatrix',
    'feDiffuseLighting',
    'feDisplacementMap',
    'feDistantLight',
    'feFlood',
    'feFuncA',
    'feFuncB',
    'feFuncG',
    'feFuncR',
    'feGaussianBlur',
    'feImage',
    'feMerge',
    'feMergeNode',
    'feMorphology',
    'feOffset',
    'fePointLight',
    'feSpecularLighting',
    'feSpotLight',
    'feTile',
    'feTurbulence',
    'filter',
    'font',
    'font-face',
    'font-face-format',
    'font-face-name',
    'font-face-url',
    'foreignObject',
    'g',
    'glyph',
    'glyphRef',
    'hkern',
    'image',
    'line',
    'lineGradient',
    'marker',
    'mask',
    'metadata',
    'missing-glyph',
    'mpath',
    'path',
    'pattern',
    'polygon',
    'polyline',
    'radialGradient',
    'rect',
    'script',
    'set',
    'stop',
    'style',
    'svg',
    'switch',
    'symbol',
    'text',
    'textPath',
    'title',
    'tref',
    'tspan',
    'use',
    'view',
    'vkern'
];
var isSvgElement = function isSvgElement(child) {
    return child && child.type && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(child.type) && SVG_TAGS.indexOf(child.type) >= 0;
};
var hasClipDot = function hasClipDot(dot) {
    return dot && _typeof(dot) === 'object' && 'clipDot' in dot;
};
var isValidSpreadableProp = function isValidSpreadableProp(property, key, includeEvents, svgElementType) {
    var _FilteredElementKeyMa;
    /**
   * If the svg element type is explicitly included, check against the filtered element key map
   * to determine if there are attributes that should only exist on that element type.
   * @todo Add an internal cjs version of https://github.com/wooorm/svg-element-attributes for full coverage.
   */ var matchingElementTypeKeys = (_FilteredElementKeyMa = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FilteredElementKeyMap"] === null || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FilteredElementKeyMap"] === void 0 ? void 0 : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FilteredElementKeyMap"][svgElementType]) !== null && _FilteredElementKeyMa !== void 0 ? _FilteredElementKeyMa : [];
    return key.startsWith('data-') || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(property) && (svgElementType && matchingElementTypeKeys.includes(key) || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SVGElementPropKeys"].includes(key)) || includeEvents && __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["EventKeys"].includes(key);
};
var filterSvgElements = function filterSvgElements(children) {
    var svgElements = [];
    toArray(children).forEach(function(entry) {
        if (isSvgElement(entry)) {
            svgElements.push(entry);
        }
    });
    return svgElements;
};
var filterProps = function filterProps(props, includeEvents, svgElementType) {
    if (!props || typeof props === 'function' || typeof props === 'boolean') {
        return null;
    }
    var inputProps = props;
    if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(props)) {
        inputProps = props.props;
    }
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(inputProps)) {
        return null;
    }
    var out = {};
    /**
   * Props are blindly spread onto SVG elements. This loop filters out properties that we don't want to spread.
   * Items filtered out are as follows:
   *   - functions in properties that are SVG attributes (functions are included when includeEvents is true)
   *   - props that are SVG attributes but don't matched the passed svgElementType
   *   - any prop that is not in SVGElementPropKeys (or in EventKeys if includeEvents is true)
   */ Object.keys(inputProps).forEach(function(key) {
        var _inputProps;
        if (isValidSpreadableProp((_inputProps = inputProps) === null || _inputProps === void 0 ? void 0 : _inputProps[key], key, includeEvents, svgElementType)) {
            out[key] = inputProps[key];
        }
    });
    return out;
};
var isChildrenEqual = function isChildrenEqual(nextChildren, prevChildren) {
    if (nextChildren === prevChildren) {
        return true;
    }
    var count = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].count(nextChildren);
    if (count !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].count(prevChildren)) {
        return false;
    }
    if (count === 0) {
        return true;
    }
    if (count === 1) {
        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        return isSingleChildEqual(Array.isArray(nextChildren) ? nextChildren[0] : nextChildren, Array.isArray(prevChildren) ? prevChildren[0] : prevChildren);
    }
    for(var i = 0; i < count; i++){
        var nextChild = nextChildren[i];
        var prevChild = prevChildren[i];
        if (Array.isArray(nextChild) || Array.isArray(prevChild)) {
            if (!isChildrenEqual(nextChild, prevChild)) {
                return false;
            }
        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        } else if (!isSingleChildEqual(nextChild, prevChild)) {
            return false;
        }
    }
    return true;
};
var isSingleChildEqual = function isSingleChildEqual(nextChild, prevChild) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(nextChild) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(prevChild)) {
        return true;
    }
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(nextChild) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(prevChild)) {
        var _ref = nextChild.props || {}, nextChildren = _ref.children, nextProps = _objectWithoutProperties(_ref, _excluded);
        var _ref2 = prevChild.props || {}, prevChildren = _ref2.children, prevProps = _objectWithoutProperties(_ref2, _excluded2);
        if (nextChildren && prevChildren) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["shallowEqual"])(nextProps, prevProps) && isChildrenEqual(nextChildren, prevChildren);
        }
        if (!nextChildren && !prevChildren) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["shallowEqual"])(nextProps, prevProps);
        }
        return false;
    }
    return false;
};
var renderByOrder = function renderByOrder(children, renderMap) {
    var elements = [];
    var record = {};
    toArray(children).forEach(function(child, index) {
        if (isSvgElement(child)) {
            elements.push(child);
        } else if (child) {
            var displayName = getDisplayName(child.type);
            var _ref3 = renderMap[displayName] || {}, handler = _ref3.handler, once = _ref3.once;
            if (handler && (!once || !record[displayName])) {
                var results = handler(child, displayName, index);
                elements.push(results);
                record[displayName] = true;
            }
        }
    });
    return elements;
};
var getReactEventByType = function getReactEventByType(e) {
    var type = e && e.type;
    if (type && REACT_BROWSER_EVENT_MAP[type]) {
        return REACT_BROWSER_EVENT_MAP[type];
    }
    return null;
};
var parseChildIndex = function parseChildIndex(child, children) {
    return toArray(children).indexOf(child);
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Surface.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Surface",
    ()=>Surface
]);
/**
 * @fileOverview Surface
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var _excluded = [
    "children",
    "width",
    "height",
    "viewBox",
    "className",
    "style",
    "title",
    "desc"
];
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
function Surface(props) {
    var children = props.children, width = props.width, height = props.height, viewBox = props.viewBox, className = props.className, style = props.style, title = props.title, desc = props.desc, others = _objectWithoutProperties(props, _excluded);
    var svgView = viewBox || {
        width: width,
        height: height,
        x: 0,
        y: 0
    };
    var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-surface', className);
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("svg", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(others, true, 'svg'), {
        className: layerClass,
        width: width,
        height: height,
        style: style,
        viewBox: "".concat(svgView.x, " ").concat(svgView.y, " ").concat(svgView.width, " ").concat(svgView.height)
    }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("title", null, title), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("desc", null, desc), children);
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Layer",
    ()=>Layer
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var _excluded = [
    "children",
    "className"
];
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
var Layer = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].forwardRef(function(props, ref) {
    var children = props.children, className = props.className, others = _objectWithoutProperties(props, _excluded);
    var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-layer', className);
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", _extends({
        className: layerClass
    }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(others, true), {
        ref: ref
    }), children);
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/DefaultTooltipContent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DefaultTooltipContent",
    ()=>DefaultTooltipContent
]);
/**
 * @fileOverview Default Tooltip Content
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$sortBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/sortBy.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
function defaultFormatter(value) {
    return Array.isArray(value) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(value[0]) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(value[1]) ? value.join(' ~ ') : value;
}
var DefaultTooltipContent = function DefaultTooltipContent(props) {
    var _props$separator = props.separator, separator = _props$separator === void 0 ? ' : ' : _props$separator, _props$contentStyle = props.contentStyle, contentStyle = _props$contentStyle === void 0 ? {} : _props$contentStyle, _props$itemStyle = props.itemStyle, itemStyle = _props$itemStyle === void 0 ? {} : _props$itemStyle, _props$labelStyle = props.labelStyle, labelStyle = _props$labelStyle === void 0 ? {} : _props$labelStyle, payload = props.payload, formatter = props.formatter, itemSorter = props.itemSorter, wrapperClassName = props.wrapperClassName, labelClassName = props.labelClassName, label = props.label, labelFormatter = props.labelFormatter, _props$accessibilityL = props.accessibilityLayer, accessibilityLayer = _props$accessibilityL === void 0 ? false : _props$accessibilityL;
    var renderContent = function renderContent() {
        if (payload && payload.length) {
            var listStyle = {
                padding: 0,
                margin: 0
            };
            var items = (itemSorter ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$sortBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(payload, itemSorter) : payload).map(function(entry, i) {
                if (entry.type === 'none') {
                    return null;
                }
                var finalItemStyle = _objectSpread({
                    display: 'block',
                    paddingTop: 4,
                    paddingBottom: 4,
                    color: entry.color || '#000'
                }, itemStyle);
                var finalFormatter = entry.formatter || formatter || defaultFormatter;
                var value = entry.value, name = entry.name;
                var finalValue = value;
                var finalName = name;
                if (finalFormatter && finalValue != null && finalName != null) {
                    var formatted = finalFormatter(value, name, entry, i, payload);
                    if (Array.isArray(formatted)) {
                        var _formatted = _slicedToArray(formatted, 2);
                        finalValue = _formatted[0];
                        finalName = _formatted[1];
                    } else {
                        finalValue = formatted;
                    }
                }
                return(/*#__PURE__*/ // eslint-disable-next-line react/no-array-index-key
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("li", {
                    className: "recharts-tooltip-item",
                    key: "tooltip-item-".concat(i),
                    style: finalItemStyle
                }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(finalName) ? /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("span", {
                    className: "recharts-tooltip-item-name"
                }, finalName) : null, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(finalName) ? /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("span", {
                    className: "recharts-tooltip-item-separator"
                }, separator) : null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("span", {
                    className: "recharts-tooltip-item-value"
                }, finalValue), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("span", {
                    className: "recharts-tooltip-item-unit"
                }, entry.unit || '')));
            });
            return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("ul", {
                className: "recharts-tooltip-item-list",
                style: listStyle
            }, items);
        }
        return null;
    };
    var finalStyle = _objectSpread({
        margin: 0,
        padding: 10,
        backgroundColor: '#fff',
        border: '1px solid #ccc',
        whiteSpace: 'nowrap'
    }, contentStyle);
    var finalLabelStyle = _objectSpread({
        margin: 0
    }, labelStyle);
    var hasLabel = !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(label);
    var finalLabel = hasLabel ? label : '';
    var wrapperCN = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-default-tooltip', wrapperClassName);
    var labelCN = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-tooltip-label', labelClassName);
    if (hasLabel && labelFormatter && payload !== undefined && payload !== null) {
        finalLabel = labelFormatter(label, payload);
    }
    var accessibilityAttributes = accessibilityLayer ? {
        role: 'status',
        'aria-live': 'assertive'
    } : {};
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", _extends({
        className: wrapperCN,
        style: finalStyle
    }, accessibilityAttributes), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("p", {
        className: labelCN,
        style: finalLabelStyle
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(finalLabel) ? finalLabel : "".concat(finalLabel)), renderContent());
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/tooltip/translate.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getTooltipCSSClassName",
    ()=>getTooltipCSSClassName,
    "getTooltipTranslate",
    ()=>getTooltipTranslate,
    "getTooltipTranslateXY",
    ()=>getTooltipTranslateXY,
    "getTransformStyle",
    ()=>getTransformStyle
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
var CSS_CLASS_PREFIX = 'recharts-tooltip-wrapper';
var TOOLTIP_HIDDEN = {
    visibility: 'hidden'
};
function getTooltipCSSClassName(_ref) {
    var coordinate = _ref.coordinate, translateX = _ref.translateX, translateY = _ref.translateY;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(CSS_CLASS_PREFIX, _defineProperty(_defineProperty(_defineProperty(_defineProperty({}, "".concat(CSS_CLASS_PREFIX, "-right"), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(translateX) && coordinate && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(coordinate.x) && translateX >= coordinate.x), "".concat(CSS_CLASS_PREFIX, "-left"), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(translateX) && coordinate && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(coordinate.x) && translateX < coordinate.x), "".concat(CSS_CLASS_PREFIX, "-bottom"), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(translateY) && coordinate && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(coordinate.y) && translateY >= coordinate.y), "".concat(CSS_CLASS_PREFIX, "-top"), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(translateY) && coordinate && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(coordinate.y) && translateY < coordinate.y));
}
function getTooltipTranslateXY(_ref2) {
    var allowEscapeViewBox = _ref2.allowEscapeViewBox, coordinate = _ref2.coordinate, key = _ref2.key, offsetTopLeft = _ref2.offsetTopLeft, position = _ref2.position, reverseDirection = _ref2.reverseDirection, tooltipDimension = _ref2.tooltipDimension, viewBox = _ref2.viewBox, viewBoxDimension = _ref2.viewBoxDimension;
    if (position && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(position[key])) {
        return position[key];
    }
    var negative = coordinate[key] - tooltipDimension - offsetTopLeft;
    var positive = coordinate[key] + offsetTopLeft;
    if (allowEscapeViewBox[key]) {
        return reverseDirection[key] ? negative : positive;
    }
    if (reverseDirection[key]) {
        var _tooltipBoundary = negative;
        var _viewBoxBoundary = viewBox[key];
        if (_tooltipBoundary < _viewBoxBoundary) {
            return Math.max(positive, viewBox[key]);
        }
        return Math.max(negative, viewBox[key]);
    }
    var tooltipBoundary = positive + tooltipDimension;
    var viewBoxBoundary = viewBox[key] + viewBoxDimension;
    if (tooltipBoundary > viewBoxBoundary) {
        return Math.max(negative, viewBox[key]);
    }
    return Math.max(positive, viewBox[key]);
}
function getTransformStyle(_ref3) {
    var translateX = _ref3.translateX, translateY = _ref3.translateY, useTranslate3d = _ref3.useTranslate3d;
    return {
        transform: useTranslate3d ? "translate3d(".concat(translateX, "px, ").concat(translateY, "px, 0)") : "translate(".concat(translateX, "px, ").concat(translateY, "px)")
    };
}
function getTooltipTranslate(_ref4) {
    var allowEscapeViewBox = _ref4.allowEscapeViewBox, coordinate = _ref4.coordinate, offsetTopLeft = _ref4.offsetTopLeft, position = _ref4.position, reverseDirection = _ref4.reverseDirection, tooltipBox = _ref4.tooltipBox, useTranslate3d = _ref4.useTranslate3d, viewBox = _ref4.viewBox;
    var cssProperties, translateX, translateY;
    if (tooltipBox.height > 0 && tooltipBox.width > 0 && coordinate) {
        translateX = getTooltipTranslateXY({
            allowEscapeViewBox: allowEscapeViewBox,
            coordinate: coordinate,
            key: 'x',
            offsetTopLeft: offsetTopLeft,
            position: position,
            reverseDirection: reverseDirection,
            tooltipDimension: tooltipBox.width,
            viewBox: viewBox,
            viewBoxDimension: viewBox.width
        });
        translateY = getTooltipTranslateXY({
            allowEscapeViewBox: allowEscapeViewBox,
            coordinate: coordinate,
            key: 'y',
            offsetTopLeft: offsetTopLeft,
            position: position,
            reverseDirection: reverseDirection,
            tooltipDimension: tooltipBox.height,
            viewBox: viewBox,
            viewBoxDimension: viewBox.height
        });
        cssProperties = getTransformStyle({
            translateX: translateX,
            translateY: translateY,
            useTranslate3d: useTranslate3d
        });
    } else {
        cssProperties = TOOLTIP_HIDDEN;
    }
    return {
        cssProperties: cssProperties,
        cssClasses: getTooltipCSSClassName({
            translateX: translateX,
            translateY: translateY,
            coordinate: coordinate
        })
    };
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/TooltipBoundingBox.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TooltipBoundingBox",
    ()=>TooltipBoundingBox
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$tooltip$2f$translate$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/tooltip/translate.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
var EPSILON = 1;
var TooltipBoundingBox = /*#__PURE__*/ function(_PureComponent) {
    function TooltipBoundingBox() {
        var _this;
        _classCallCheck(this, TooltipBoundingBox);
        for(var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++){
            args[_key] = arguments[_key];
        }
        _this = _callSuper(this, TooltipBoundingBox, [].concat(args));
        _defineProperty(_this, "state", {
            dismissed: false,
            dismissedAtCoordinate: {
                x: 0,
                y: 0
            },
            lastBoundingBox: {
                width: -1,
                height: -1
            }
        });
        _defineProperty(_this, "handleKeyDown", function(event) {
            if (event.key === 'Escape') {
                var _this$props$coordinat, _this$props$coordinat2, _this$props$coordinat3, _this$props$coordinat4;
                _this.setState({
                    dismissed: true,
                    dismissedAtCoordinate: {
                        x: (_this$props$coordinat = (_this$props$coordinat2 = _this.props.coordinate) === null || _this$props$coordinat2 === void 0 ? void 0 : _this$props$coordinat2.x) !== null && _this$props$coordinat !== void 0 ? _this$props$coordinat : 0,
                        y: (_this$props$coordinat3 = (_this$props$coordinat4 = _this.props.coordinate) === null || _this$props$coordinat4 === void 0 ? void 0 : _this$props$coordinat4.y) !== null && _this$props$coordinat3 !== void 0 ? _this$props$coordinat3 : 0
                    }
                });
            }
        });
        return _this;
    }
    _inherits(TooltipBoundingBox, _PureComponent);
    return _createClass(TooltipBoundingBox, [
        {
            key: "updateBBox",
            value: function updateBBox() {
                if (this.wrapperNode && this.wrapperNode.getBoundingClientRect) {
                    var box = this.wrapperNode.getBoundingClientRect();
                    if (Math.abs(box.width - this.state.lastBoundingBox.width) > EPSILON || Math.abs(box.height - this.state.lastBoundingBox.height) > EPSILON) {
                        this.setState({
                            lastBoundingBox: {
                                width: box.width,
                                height: box.height
                            }
                        });
                    }
                } else if (this.state.lastBoundingBox.width !== -1 || this.state.lastBoundingBox.height !== -1) {
                    this.setState({
                        lastBoundingBox: {
                            width: -1,
                            height: -1
                        }
                    });
                }
            }
        },
        {
            key: "componentDidMount",
            value: function componentDidMount() {
                document.addEventListener('keydown', this.handleKeyDown);
                this.updateBBox();
            }
        },
        {
            key: "componentWillUnmount",
            value: function componentWillUnmount() {
                document.removeEventListener('keydown', this.handleKeyDown);
            }
        },
        {
            key: "componentDidUpdate",
            value: function componentDidUpdate() {
                var _this$props$coordinat5, _this$props$coordinat6;
                if (this.props.active) {
                    this.updateBBox();
                }
                if (!this.state.dismissed) {
                    return;
                }
                if (((_this$props$coordinat5 = this.props.coordinate) === null || _this$props$coordinat5 === void 0 ? void 0 : _this$props$coordinat5.x) !== this.state.dismissedAtCoordinate.x || ((_this$props$coordinat6 = this.props.coordinate) === null || _this$props$coordinat6 === void 0 ? void 0 : _this$props$coordinat6.y) !== this.state.dismissedAtCoordinate.y) {
                    this.state.dismissed = false;
                }
            }
        },
        {
            key: "render",
            value: function render() {
                var _this2 = this;
                var _this$props = this.props, active = _this$props.active, allowEscapeViewBox = _this$props.allowEscapeViewBox, animationDuration = _this$props.animationDuration, animationEasing = _this$props.animationEasing, children = _this$props.children, coordinate = _this$props.coordinate, hasPayload = _this$props.hasPayload, isAnimationActive = _this$props.isAnimationActive, offset = _this$props.offset, position = _this$props.position, reverseDirection = _this$props.reverseDirection, useTranslate3d = _this$props.useTranslate3d, viewBox = _this$props.viewBox, wrapperStyle = _this$props.wrapperStyle;
                var _getTooltipTranslate = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$tooltip$2f$translate$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTooltipTranslate"])({
                    allowEscapeViewBox: allowEscapeViewBox,
                    coordinate: coordinate,
                    offsetTopLeft: offset,
                    position: position,
                    reverseDirection: reverseDirection,
                    tooltipBox: this.state.lastBoundingBox,
                    useTranslate3d: useTranslate3d,
                    viewBox: viewBox
                }), cssClasses = _getTooltipTranslate.cssClasses, cssProperties = _getTooltipTranslate.cssProperties;
                var outerStyle = _objectSpread(_objectSpread({
                    transition: isAnimationActive && active ? "transform ".concat(animationDuration, "ms ").concat(animationEasing) : undefined
                }, cssProperties), {}, {
                    pointerEvents: 'none',
                    visibility: !this.state.dismissed && active && hasPayload ? 'visible' : 'hidden',
                    position: 'absolute',
                    top: 0,
                    left: 0
                }, wrapperStyle);
                return(/*#__PURE__*/ // This element allow listening to the `Escape` key.
                // See https://github.com/recharts/recharts/pull/2925
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", {
                    tabIndex: -1,
                    className: cssClasses,
                    style: outerStyle,
                    ref: function ref(node) {
                        _this2.wrapperNode = node;
                    }
                }, children));
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Global",
    ()=>Global
]);
var parseIsSsrByDefault = function parseIsSsrByDefault() {
    return !(typeof window !== 'undefined' && window.document && window.document.createElement && window.setTimeout);
};
var Global = {
    isSsr: parseIsSsrByDefault(),
    get: function get(key) {
        return Global[key];
    },
    set: function set(key, value) {
        if (typeof key === 'string') {
            Global[key] = value;
        } else {
            var keys = Object.keys(key);
            if (keys && keys.length) {
                keys.forEach(function(k) {
                    Global[k] = key[k];
                });
            }
        }
    }
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/payload/getUniqPayload.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getUniqPayload",
    ()=>getUniqPayload
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$uniqBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/uniqBy.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
;
;
function getUniqPayload(payload, option, defaultUniqBy) {
    if (option === true) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$uniqBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(payload, defaultUniqBy);
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$uniqBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(payload, option);
    }
    return payload;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Tooltip.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Tooltip",
    ()=>Tooltip
]);
/**
 * @fileOverview Tooltip
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$DefaultTooltipContent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/DefaultTooltipContent.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$TooltipBoundingBox$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/TooltipBoundingBox.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$payload$2f$getUniqPayload$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/payload/getUniqPayload.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
function defaultUniqBy(entry) {
    return entry.dataKey;
}
function renderContent(content, props) {
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(content)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(content, props);
    }
    if (typeof content === 'function') {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(content, props);
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$DefaultTooltipContent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DefaultTooltipContent"], props);
}
var Tooltip = /*#__PURE__*/ function(_PureComponent) {
    function Tooltip() {
        _classCallCheck(this, Tooltip);
        return _callSuper(this, Tooltip, arguments);
    }
    _inherits(Tooltip, _PureComponent);
    return _createClass(Tooltip, [
        {
            key: "render",
            value: function render() {
                var _this = this;
                var _this$props = this.props, active = _this$props.active, allowEscapeViewBox = _this$props.allowEscapeViewBox, animationDuration = _this$props.animationDuration, animationEasing = _this$props.animationEasing, content = _this$props.content, coordinate = _this$props.coordinate, filterNull = _this$props.filterNull, isAnimationActive = _this$props.isAnimationActive, offset = _this$props.offset, payload = _this$props.payload, payloadUniqBy = _this$props.payloadUniqBy, position = _this$props.position, reverseDirection = _this$props.reverseDirection, useTranslate3d = _this$props.useTranslate3d, viewBox = _this$props.viewBox, wrapperStyle = _this$props.wrapperStyle;
                var finalPayload = payload !== null && payload !== void 0 ? payload : [];
                if (filterNull && finalPayload.length) {
                    finalPayload = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$payload$2f$getUniqPayload$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getUniqPayload"])(payload.filter(function(entry) {
                        return entry.value != null && (entry.hide !== true || _this.props.includeHidden);
                    }), payloadUniqBy, defaultUniqBy);
                }
                var hasPayload = finalPayload.length > 0;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$TooltipBoundingBox$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TooltipBoundingBox"], {
                    allowEscapeViewBox: allowEscapeViewBox,
                    animationDuration: animationDuration,
                    animationEasing: animationEasing,
                    isAnimationActive: isAnimationActive,
                    active: active,
                    coordinate: coordinate,
                    hasPayload: hasPayload,
                    offset: offset,
                    position: position,
                    reverseDirection: reverseDirection,
                    useTranslate3d: useTranslate3d,
                    viewBox: viewBox,
                    wrapperStyle: wrapperStyle
                }, renderContent(content, _objectSpread(_objectSpread({}, this.props), {}, {
                    payload: finalPayload
                })));
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
_defineProperty(Tooltip, "displayName", 'Tooltip');
_defineProperty(Tooltip, "defaultProps", {
    accessibilityLayer: false,
    allowEscapeViewBox: {
        x: false,
        y: false
    },
    animationDuration: 400,
    animationEasing: 'ease',
    contentStyle: {},
    coordinate: {
        x: 0,
        y: 0
    },
    cursor: true,
    cursorStyle: {},
    filterNull: true,
    isAnimationActive: !__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Global"].isSsr,
    itemStyle: {},
    labelStyle: {},
    offset: 10,
    reverseDirection: {
        x: false,
        y: false
    },
    separator: ' : ',
    trigger: 'hover',
    useTranslate3d: false,
    viewBox: {
        x: 0,
        y: 0,
        height: 0,
        width: 0
    },
    wrapperStyle: {}
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "warn",
    ()=>warn
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/* eslint no-console: 0 */ var isDev = ("TURBOPACK compile-time value", "development") !== 'production';
var warn = function warn(condition, format) {
    for(var _len = arguments.length, args = new Array(_len > 2 ? _len - 2 : 0), _key = 2; _key < _len; _key++){
        args[_key - 2] = arguments[_key];
    }
    if (isDev && typeof console !== 'undefined' && console.warn) {
        if (format === undefined) {
            console.warn('LogUtils requires an error message argument');
        }
        if (!condition) {
            if (format === undefined) {
                console.warn('Minified exception occurred; use the non-minified dev environment ' + 'for the full error message and additional helpful warnings.');
            } else {
                var argIndex = 0;
                console.warn(format.replace(/%s/g, function() {
                    return args[argIndex++];
                }));
            }
        }
    }
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Symbols.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Symbols",
    ()=>Symbols
]);
/**
 * @fileOverview Curve
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/upperFirst.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$shape$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/victory-vendor/es/d3-shape.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbol$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol.js [app-client] (ecmascript) <export default as symbol>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolCircle$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/circle.js [app-client] (ecmascript) <export default as symbolCircle>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$cross$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolCross$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/cross.js [app-client] (ecmascript) <export default as symbolCross>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$diamond$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolDiamond$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/diamond.js [app-client] (ecmascript) <export default as symbolDiamond>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$square$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolSquare$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/square.js [app-client] (ecmascript) <export default as symbolSquare>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$star$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolStar$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/star.js [app-client] (ecmascript) <export default as symbolStar>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$triangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolTriangle$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/triangle.js [app-client] (ecmascript) <export default as symbolTriangle>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$wye$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolWye$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/symbol/wye.js [app-client] (ecmascript) <export default as symbolWye>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
var _excluded = [
    "type",
    "size",
    "sizeType"
];
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
;
;
var symbolFactories = {
    symbolCircle: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolCircle$3e$__["symbolCircle"],
    symbolCross: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$cross$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolCross$3e$__["symbolCross"],
    symbolDiamond: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$diamond$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolDiamond$3e$__["symbolDiamond"],
    symbolSquare: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$square$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolSquare$3e$__["symbolSquare"],
    symbolStar: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$star$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolStar$3e$__["symbolStar"],
    symbolTriangle: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$triangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolTriangle$3e$__["symbolTriangle"],
    symbolWye: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$wye$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolWye$3e$__["symbolWye"]
};
var RADIAN = Math.PI / 180;
var getSymbolFactory = function getSymbolFactory(type) {
    var name = "symbol".concat((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(type));
    return symbolFactories[name] || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2f$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbolCircle$3e$__["symbolCircle"];
};
var calculateAreaSize = function calculateAreaSize(size, sizeType, type) {
    if (sizeType === 'area') {
        return size;
    }
    switch(type){
        case 'cross':
            return 5 * size * size / 9;
        case 'diamond':
            return 0.5 * size * size / Math.sqrt(3);
        case 'square':
            return size * size;
        case 'star':
            {
                var angle = 18 * RADIAN;
                return 1.25 * size * size * (Math.tan(angle) - Math.tan(angle * 2) * Math.pow(Math.tan(angle), 2));
            }
        case 'triangle':
            return Math.sqrt(3) * size * size / 4;
        case 'wye':
            return (21 - 10 * Math.sqrt(3)) * size * size / 8;
        default:
            return Math.PI * size * size / 4;
    }
};
var registerSymbol = function registerSymbol(key, factory) {
    symbolFactories["symbol".concat((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(key))] = factory;
};
var Symbols = function Symbols(_ref) {
    var _ref$type = _ref.type, type = _ref$type === void 0 ? 'circle' : _ref$type, _ref$size = _ref.size, size = _ref$size === void 0 ? 64 : _ref$size, _ref$sizeType = _ref.sizeType, sizeType = _ref$sizeType === void 0 ? 'area' : _ref$sizeType, rest = _objectWithoutProperties(_ref, _excluded);
    var props = _objectSpread(_objectSpread({}, rest), {}, {
        type: type,
        size: size,
        sizeType: sizeType
    });
    /**
   * Calculate the path of curve
   * @return {String} path
   */ var getPath = function getPath() {
        var symbolFactory = getSymbolFactory(type);
        var symbol = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$symbol$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__symbol$3e$__["symbol"])().type(symbolFactory).size(calculateAreaSize(size, sizeType, type));
        return symbol();
    };
    var className = props.className, cx = props.cx, cy = props.cy;
    var filteredProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true);
    if (cx === +cx && cy === +cy && size === +size) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, filteredProps, {
            className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-symbols', className),
            transform: "translate(".concat(cx, ", ").concat(cy, ")"),
            d: getPath()
        }));
    }
    return null;
};
Symbols.registerSymbol = registerSymbol;
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/DefaultLegendContent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DefaultLegendContent",
    ()=>DefaultLegendContent
]);
/**
 * @fileOverview Default Legend Content
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Surface$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Surface.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Symbols$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Symbols.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
;
;
var SIZE = 32;
var DefaultLegendContent = /*#__PURE__*/ function(_PureComponent) {
    function DefaultLegendContent() {
        _classCallCheck(this, DefaultLegendContent);
        return _callSuper(this, DefaultLegendContent, arguments);
    }
    _inherits(DefaultLegendContent, _PureComponent);
    return _createClass(DefaultLegendContent, [
        {
            key: "renderIcon",
            value: /**
     * Render the path of icon
     * @param {Object} data Data of each legend item
     * @return {String} Path element
     */ function renderIcon(data) {
                var inactiveColor = this.props.inactiveColor;
                var halfSize = SIZE / 2;
                var sixthSize = SIZE / 6;
                var thirdSize = SIZE / 3;
                var color = data.inactive ? inactiveColor : data.color;
                if (data.type === 'plainline') {
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", {
                        strokeWidth: 4,
                        fill: "none",
                        stroke: color,
                        strokeDasharray: data.payload.strokeDasharray,
                        x1: 0,
                        y1: halfSize,
                        x2: SIZE,
                        y2: halfSize,
                        className: "recharts-legend-icon"
                    });
                }
                if (data.type === 'line') {
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", {
                        strokeWidth: 4,
                        fill: "none",
                        stroke: color,
                        d: "M0,".concat(halfSize, "h").concat(thirdSize, "\n            A").concat(sixthSize, ",").concat(sixthSize, ",0,1,1,").concat(2 * thirdSize, ",").concat(halfSize, "\n            H").concat(SIZE, "M").concat(2 * thirdSize, ",").concat(halfSize, "\n            A").concat(sixthSize, ",").concat(sixthSize, ",0,1,1,").concat(thirdSize, ",").concat(halfSize),
                        className: "recharts-legend-icon"
                    });
                }
                if (data.type === 'rect') {
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", {
                        stroke: "none",
                        fill: color,
                        d: "M0,".concat(SIZE / 8, "h").concat(SIZE, "v").concat(SIZE * 3 / 4, "h").concat(-SIZE, "z"),
                        className: "recharts-legend-icon"
                    });
                }
                if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(data.legendIcon)) {
                    var iconProps = _objectSpread({}, data);
                    delete iconProps.legendIcon;
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(data.legendIcon, iconProps);
                }
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Symbols$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Symbols"], {
                    fill: color,
                    cx: halfSize,
                    cy: halfSize,
                    size: SIZE,
                    sizeType: "diameter",
                    type: data.type
                });
            }
        },
        {
            key: "renderItems",
            value: function renderItems() {
                var _this = this;
                var _this$props = this.props, payload = _this$props.payload, iconSize = _this$props.iconSize, layout = _this$props.layout, formatter = _this$props.formatter, inactiveColor = _this$props.inactiveColor;
                var viewBox = {
                    x: 0,
                    y: 0,
                    width: SIZE,
                    height: SIZE
                };
                var itemStyle = {
                    display: layout === 'horizontal' ? 'inline-block' : 'block',
                    marginRight: 10
                };
                var svgStyle = {
                    display: 'inline-block',
                    verticalAlign: 'middle',
                    marginRight: 4
                };
                return payload.map(function(entry, i) {
                    var finalFormatter = entry.formatter || formatter;
                    var className = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_defineProperty(_defineProperty({
                        'recharts-legend-item': true
                    }, "legend-item-".concat(i), true), "inactive", entry.inactive));
                    if (entry.type === 'none') {
                        return null;
                    }
                    // Do not render entry.value as functions. Always require static string properties.
                    var entryValue = !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry.value) ? entry.value : null;
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry.value), "The name property is also required when using a function for the dataKey of a chart's cartesian components. Ex: <Bar name=\"Name of my Data\"/>" // eslint-disable-line max-len
                    );
                    var color = entry.inactive ? inactiveColor : entry.color;
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("li", _extends({
                        className: className,
                        style: itemStyle,
                        key: "legend-item-".concat(i)
                    }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventsOfChild"])(_this.props, entry, i)), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Surface$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Surface"], {
                        width: iconSize,
                        height: iconSize,
                        viewBox: viewBox,
                        style: svgStyle
                    }, _this.renderIcon(entry)), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("span", {
                        className: "recharts-legend-item-text",
                        style: {
                            color: color
                        }
                    }, finalFormatter ? finalFormatter(entryValue, entry, i) : entryValue));
                });
            }
        },
        {
            key: "render",
            value: function render() {
                var _this$props2 = this.props, payload = _this$props2.payload, layout = _this$props2.layout, align = _this$props2.align;
                if (!payload || !payload.length) {
                    return null;
                }
                var finalStyle = {
                    padding: 0,
                    margin: 0,
                    textAlign: layout === 'horizontal' ? align : 'left'
                };
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("ul", {
                    className: "recharts-default-legend",
                    style: finalStyle
                }, this.renderItems());
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
_defineProperty(DefaultLegendContent, "displayName", 'Legend');
_defineProperty(DefaultLegendContent, "defaultProps", {
    iconSize: 14,
    layout: 'horizontal',
    align: 'center',
    verticalAlign: 'middle',
    inactiveColor: '#ccc'
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Legend.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Legend",
    ()=>Legend
]);
/**
 * @fileOverview Legend
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$DefaultLegendContent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/DefaultLegendContent.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$payload$2f$getUniqPayload$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/payload/getUniqPayload.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
var _excluded = [
    "ref"
];
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
;
function defaultUniqBy(entry) {
    return entry.value;
}
function renderContent(content, props) {
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(content)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(content, props);
    }
    if (typeof content === 'function') {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(content, props);
    }
    var ref = props.ref, otherProps = _objectWithoutProperties(props, _excluded);
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$DefaultLegendContent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DefaultLegendContent"], otherProps);
}
var EPS = 1;
var Legend = /*#__PURE__*/ function(_PureComponent) {
    function Legend() {
        var _this;
        _classCallCheck(this, Legend);
        for(var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++){
            args[_key] = arguments[_key];
        }
        _this = _callSuper(this, Legend, [].concat(args));
        _defineProperty(_this, "lastBoundingBox", {
            width: -1,
            height: -1
        });
        return _this;
    }
    _inherits(Legend, _PureComponent);
    return _createClass(Legend, [
        {
            key: "componentDidMount",
            value: function componentDidMount() {
                this.updateBBox();
            }
        },
        {
            key: "componentDidUpdate",
            value: function componentDidUpdate() {
                this.updateBBox();
            }
        },
        {
            key: "getBBox",
            value: function getBBox() {
                if (this.wrapperNode && this.wrapperNode.getBoundingClientRect) {
                    var box = this.wrapperNode.getBoundingClientRect();
                    box.height = this.wrapperNode.offsetHeight;
                    box.width = this.wrapperNode.offsetWidth;
                    return box;
                }
                return null;
            }
        },
        {
            key: "updateBBox",
            value: function updateBBox() {
                var onBBoxUpdate = this.props.onBBoxUpdate;
                var box = this.getBBox();
                if (box) {
                    if (Math.abs(box.width - this.lastBoundingBox.width) > EPS || Math.abs(box.height - this.lastBoundingBox.height) > EPS) {
                        this.lastBoundingBox.width = box.width;
                        this.lastBoundingBox.height = box.height;
                        if (onBBoxUpdate) {
                            onBBoxUpdate(box);
                        }
                    }
                } else if (this.lastBoundingBox.width !== -1 || this.lastBoundingBox.height !== -1) {
                    this.lastBoundingBox.width = -1;
                    this.lastBoundingBox.height = -1;
                    if (onBBoxUpdate) {
                        onBBoxUpdate(null);
                    }
                }
            }
        },
        {
            key: "getBBoxSnapshot",
            value: function getBBoxSnapshot() {
                if (this.lastBoundingBox.width >= 0 && this.lastBoundingBox.height >= 0) {
                    return _objectSpread({}, this.lastBoundingBox);
                }
                return {
                    width: 0,
                    height: 0
                };
            }
        },
        {
            key: "getDefaultPosition",
            value: function getDefaultPosition(style) {
                var _this$props = this.props, layout = _this$props.layout, align = _this$props.align, verticalAlign = _this$props.verticalAlign, margin = _this$props.margin, chartWidth = _this$props.chartWidth, chartHeight = _this$props.chartHeight;
                var hPos, vPos;
                if (!style || (style.left === undefined || style.left === null) && (style.right === undefined || style.right === null)) {
                    if (align === 'center' && layout === 'vertical') {
                        var box = this.getBBoxSnapshot();
                        hPos = {
                            left: ((chartWidth || 0) - box.width) / 2
                        };
                    } else {
                        hPos = align === 'right' ? {
                            right: margin && margin.right || 0
                        } : {
                            left: margin && margin.left || 0
                        };
                    }
                }
                if (!style || (style.top === undefined || style.top === null) && (style.bottom === undefined || style.bottom === null)) {
                    if (verticalAlign === 'middle') {
                        var _box = this.getBBoxSnapshot();
                        vPos = {
                            top: ((chartHeight || 0) - _box.height) / 2
                        };
                    } else {
                        vPos = verticalAlign === 'bottom' ? {
                            bottom: margin && margin.bottom || 0
                        } : {
                            top: margin && margin.top || 0
                        };
                    }
                }
                return _objectSpread(_objectSpread({}, hPos), vPos);
            }
        },
        {
            key: "render",
            value: function render() {
                var _this2 = this;
                var _this$props2 = this.props, content = _this$props2.content, width = _this$props2.width, height = _this$props2.height, wrapperStyle = _this$props2.wrapperStyle, payloadUniqBy = _this$props2.payloadUniqBy, payload = _this$props2.payload;
                var outerStyle = _objectSpread(_objectSpread({
                    position: 'absolute',
                    width: width || 'auto',
                    height: height || 'auto'
                }, this.getDefaultPosition(wrapperStyle)), wrapperStyle);
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", {
                    className: "recharts-legend-wrapper",
                    style: outerStyle,
                    ref: function ref(node) {
                        _this2.wrapperNode = node;
                    }
                }, renderContent(content, _objectSpread(_objectSpread({}, this.props), {}, {
                    payload: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$payload$2f$getUniqPayload$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getUniqPayload"])(payload, payloadUniqBy, defaultUniqBy)
                })));
            }
        }
    ], [
        {
            key: "getWithHeight",
            value: function getWithHeight(item, chartWidth) {
                var _this$defaultProps$it = _objectSpread(_objectSpread({}, this.defaultProps), item.props), layout = _this$defaultProps$it.layout;
                if (layout === 'vertical' && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(item.props.height)) {
                    return {
                        height: item.props.height
                    };
                }
                if (layout === 'horizontal') {
                    return {
                        width: item.props.width || chartWidth
                    };
                }
                return null;
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
_defineProperty(Legend, "displayName", 'Legend');
_defineProperty(Legend, "defaultProps", {
    iconSize: 14,
    layout: 'horizontal',
    align: 'center',
    verticalAlign: 'bottom'
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Dot.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Dot",
    ()=>Dot
]);
/**
 * @fileOverview Dot
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
;
;
;
;
var Dot = function Dot(props) {
    var cx = props.cx, cy = props.cy, r = props.r, className = props.className;
    var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-dot', className);
    if (cx === +cx && cy === +cy && r === +r) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"]("circle", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, false), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventHandlers"])(props), {
            className: layerClass,
            cx: cx,
            cy: cy,
            r: r
        }));
    }
    return null;
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Rectangle.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Rectangle",
    ()=>Rectangle,
    "isInRectangle",
    ()=>isInRectangle
]);
/**
 * @fileOverview Rectangle
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-smooth/es6/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
var getRectanglePath = function getRectanglePath(x, y, width, height, radius) {
    var maxRadius = Math.min(Math.abs(width) / 2, Math.abs(height) / 2);
    var ySign = height >= 0 ? 1 : -1;
    var xSign = width >= 0 ? 1 : -1;
    var clockWise = height >= 0 && width >= 0 || height < 0 && width < 0 ? 1 : 0;
    var path;
    if (maxRadius > 0 && radius instanceof Array) {
        var newRadius = [
            0,
            0,
            0,
            0
        ];
        for(var i = 0, len = 4; i < len; i++){
            newRadius[i] = radius[i] > maxRadius ? maxRadius : radius[i];
        }
        path = "M".concat(x, ",").concat(y + ySign * newRadius[0]);
        if (newRadius[0] > 0) {
            path += "A ".concat(newRadius[0], ",").concat(newRadius[0], ",0,0,").concat(clockWise, ",").concat(x + xSign * newRadius[0], ",").concat(y);
        }
        path += "L ".concat(x + width - xSign * newRadius[1], ",").concat(y);
        if (newRadius[1] > 0) {
            path += "A ".concat(newRadius[1], ",").concat(newRadius[1], ",0,0,").concat(clockWise, ",\n        ").concat(x + width, ",").concat(y + ySign * newRadius[1]);
        }
        path += "L ".concat(x + width, ",").concat(y + height - ySign * newRadius[2]);
        if (newRadius[2] > 0) {
            path += "A ".concat(newRadius[2], ",").concat(newRadius[2], ",0,0,").concat(clockWise, ",\n        ").concat(x + width - xSign * newRadius[2], ",").concat(y + height);
        }
        path += "L ".concat(x + xSign * newRadius[3], ",").concat(y + height);
        if (newRadius[3] > 0) {
            path += "A ".concat(newRadius[3], ",").concat(newRadius[3], ",0,0,").concat(clockWise, ",\n        ").concat(x, ",").concat(y + height - ySign * newRadius[3]);
        }
        path += 'Z';
    } else if (maxRadius > 0 && radius === +radius && radius > 0) {
        var _newRadius = Math.min(maxRadius, radius);
        path = "M ".concat(x, ",").concat(y + ySign * _newRadius, "\n            A ").concat(_newRadius, ",").concat(_newRadius, ",0,0,").concat(clockWise, ",").concat(x + xSign * _newRadius, ",").concat(y, "\n            L ").concat(x + width - xSign * _newRadius, ",").concat(y, "\n            A ").concat(_newRadius, ",").concat(_newRadius, ",0,0,").concat(clockWise, ",").concat(x + width, ",").concat(y + ySign * _newRadius, "\n            L ").concat(x + width, ",").concat(y + height - ySign * _newRadius, "\n            A ").concat(_newRadius, ",").concat(_newRadius, ",0,0,").concat(clockWise, ",").concat(x + width - xSign * _newRadius, ",").concat(y + height, "\n            L ").concat(x + xSign * _newRadius, ",").concat(y + height, "\n            A ").concat(_newRadius, ",").concat(_newRadius, ",0,0,").concat(clockWise, ",").concat(x, ",").concat(y + height - ySign * _newRadius, " Z");
    } else {
        path = "M ".concat(x, ",").concat(y, " h ").concat(width, " v ").concat(height, " h ").concat(-width, " Z");
    }
    return path;
};
var isInRectangle = function isInRectangle(point, rect) {
    if (!point || !rect) {
        return false;
    }
    var px = point.x, py = point.y;
    var x = rect.x, y = rect.y, width = rect.width, height = rect.height;
    if (Math.abs(width) > 0 && Math.abs(height) > 0) {
        var minX = Math.min(x, x + width);
        var maxX = Math.max(x, x + width);
        var minY = Math.min(y, y + height);
        var maxY = Math.max(y, y + height);
        return px >= minX && px <= maxX && py >= minY && py <= maxY;
    }
    return false;
};
var defaultProps = {
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    // The radius of border
    // The radius of four corners when radius is a number
    // The radius of left-top, right-top, right-bottom, left-bottom when radius is an array
    radius: 0,
    isAnimationActive: false,
    isUpdateAnimationActive: false,
    animationBegin: 0,
    animationDuration: 1500,
    animationEasing: 'ease'
};
var Rectangle = function Rectangle(rectangleProps) {
    var props = _objectSpread(_objectSpread({}, defaultProps), rectangleProps);
    var pathRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])();
    var _useState = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(-1), _useState2 = _slicedToArray(_useState, 2), totalLength = _useState2[0], setTotalLength = _useState2[1];
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Rectangle.useEffect": function() {
            if (pathRef.current && pathRef.current.getTotalLength) {
                try {
                    var pathTotalLength = pathRef.current.getTotalLength();
                    if (pathTotalLength) {
                        setTotalLength(pathTotalLength);
                    }
                } catch (err) {
                // calculate total length error
                }
            }
        }
    }["Rectangle.useEffect"], []);
    var x = props.x, y = props.y, width = props.width, height = props.height, radius = props.radius, className = props.className;
    var animationEasing = props.animationEasing, animationDuration = props.animationDuration, animationBegin = props.animationBegin, isAnimationActive = props.isAnimationActive, isUpdateAnimationActive = props.isUpdateAnimationActive;
    if (x !== +x || y !== +y || width !== +width || height !== +height || width === 0 || height === 0) {
        return null;
    }
    var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-rectangle', className);
    if (!isUpdateAnimationActive) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true), {
            className: layerClass,
            d: getRectanglePath(x, y, width, height, radius)
        }));
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"], {
        canBegin: totalLength > 0,
        from: {
            width: width,
            height: height,
            x: x,
            y: y
        },
        to: {
            width: width,
            height: height,
            x: x,
            y: y
        },
        duration: animationDuration,
        animationEasing: animationEasing,
        isActive: isUpdateAnimationActive
    }, function(_ref) {
        var currWidth = _ref.width, currHeight = _ref.height, currX = _ref.x, currY = _ref.y;
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"], {
            canBegin: totalLength > 0,
            from: "0px ".concat(totalLength === -1 ? 1 : totalLength, "px"),
            to: "".concat(totalLength, "px 0px"),
            attributeName: "strokeDasharray",
            begin: animationBegin,
            duration: animationDuration,
            isActive: isAnimationActive,
            easing: animationEasing
        }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true), {
            className: layerClass,
            d: getRectanglePath(currX, currY, currWidth, currHeight, radius),
            ref: pathRef
        })));
    });
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DOMUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getOffset",
    ()=>getOffset,
    "getStringSize",
    ()=>getStringSize,
    "getStyleString",
    ()=>getStyleString
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread();
}
function _nonIterableSpread() {
    throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _iterableToArray(iter) {
    if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter);
}
function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) return _arrayLikeToArray(arr);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
;
var stringCache = {
    widthCache: {},
    cacheCount: 0
};
var MAX_CACHE_NUM = 2000;
var SPAN_STYLE = {
    position: 'absolute',
    top: '-20000px',
    left: 0,
    padding: 0,
    margin: 0,
    border: 'none',
    whiteSpace: 'pre'
};
var STYLE_LIST = [
    'minWidth',
    'maxWidth',
    'width',
    'minHeight',
    'maxHeight',
    'height',
    'top',
    'left',
    'fontSize',
    'lineHeight',
    'padding',
    'margin',
    'paddingLeft',
    'paddingRight',
    'paddingTop',
    'paddingBottom',
    'marginLeft',
    'marginRight',
    'marginTop',
    'marginBottom'
];
var MEASUREMENT_SPAN_ID = 'recharts_measurement_span';
function autoCompleteStyle(name, value) {
    if (STYLE_LIST.indexOf(name) >= 0 && value === +value) {
        return "".concat(value, "px");
    }
    return value;
}
function camelToMiddleLine(text) {
    var strs = text.split('');
    var formatStrs = strs.reduce(function(result, entry) {
        if (entry === entry.toUpperCase()) {
            return [].concat(_toConsumableArray(result), [
                '-',
                entry.toLowerCase()
            ]);
        }
        return [].concat(_toConsumableArray(result), [
            entry
        ]);
    }, []);
    return formatStrs.join('');
}
var getStyleString = function getStyleString(style) {
    return Object.keys(style).reduce(function(result, s) {
        return "".concat(result).concat(camelToMiddleLine(s), ":").concat(autoCompleteStyle(s, style[s]), ";");
    }, '');
};
function removeInvalidKeys(obj) {
    var copyObj = _objectSpread({}, obj);
    Object.keys(copyObj).forEach(function(key) {
        if (!copyObj[key]) {
            delete copyObj[key];
        }
    });
    return copyObj;
}
var getStringSize = function getStringSize(text) {
    var style = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
    if (text === undefined || text === null || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Global"].isSsr) {
        return {
            width: 0,
            height: 0
        };
    }
    var copyStyle = removeInvalidKeys(style);
    var cacheKey = JSON.stringify({
        text: text,
        copyStyle: copyStyle
    });
    if (stringCache.widthCache[cacheKey]) {
        return stringCache.widthCache[cacheKey];
    }
    try {
        var measurementSpan = document.getElementById(MEASUREMENT_SPAN_ID);
        if (!measurementSpan) {
            measurementSpan = document.createElement('span');
            measurementSpan.setAttribute('id', MEASUREMENT_SPAN_ID);
            measurementSpan.setAttribute('aria-hidden', 'true');
            document.body.appendChild(measurementSpan);
        }
        // Need to use CSS Object Model (CSSOM) to be able to comply with Content Security Policy (CSP)
        // https://en.wikipedia.org/wiki/Content_Security_Policy
        var measurementSpanStyle = _objectSpread(_objectSpread({}, SPAN_STYLE), copyStyle);
        Object.assign(measurementSpan.style, measurementSpanStyle);
        measurementSpan.textContent = "".concat(text);
        var rect = measurementSpan.getBoundingClientRect();
        var result = {
            width: rect.width,
            height: rect.height
        };
        stringCache.widthCache[cacheKey] = result;
        if (++stringCache.cacheCount > MAX_CACHE_NUM) {
            stringCache.cacheCount = 0;
            stringCache.widthCache = {};
        }
        return result;
    } catch (e) {
        return {
            width: 0,
            height: 0
        };
    }
};
var getOffset = function getOffset(rect) {
    return {
        top: rect.top + window.scrollY - document.documentElement.clientTop,
        left: rect.left + window.scrollX - document.documentElement.clientLeft
    };
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReduceCSSCalc.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "reduceCSSCalc",
    ()=>reduceCSSCalc,
    "safeEvaluateExpression",
    ()=>safeEvaluateExpression
]);
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
var MULTIPLY_OR_DIVIDE_REGEX = /(-?\d+(?:\.\d+)?[a-zA-Z%]*)([*/])(-?\d+(?:\.\d+)?[a-zA-Z%]*)/;
var ADD_OR_SUBTRACT_REGEX = /(-?\d+(?:\.\d+)?[a-zA-Z%]*)([+-])(-?\d+(?:\.\d+)?[a-zA-Z%]*)/;
var CSS_LENGTH_UNIT_REGEX = /^px|cm|vh|vw|em|rem|%|mm|in|pt|pc|ex|ch|vmin|vmax|Q$/;
var NUM_SPLIT_REGEX = /(-?\d+(?:\.\d+)?)([a-zA-Z%]+)?/;
var CONVERSION_RATES = {
    cm: 96 / 2.54,
    mm: 96 / 25.4,
    pt: 96 / 72,
    pc: 96 / 6,
    "in": 96,
    Q: 96 / (2.54 * 40),
    px: 1
};
var FIXED_CSS_LENGTH_UNITS = Object.keys(CONVERSION_RATES);
var STR_NAN = 'NaN';
function convertToPx(value, unit) {
    return value * CONVERSION_RATES[unit];
}
var DecimalCSS = /*#__PURE__*/ function() {
    function DecimalCSS(num, unit) {
        _classCallCheck(this, DecimalCSS);
        this.num = num;
        this.unit = unit;
        this.num = num;
        this.unit = unit;
        if (Number.isNaN(num)) {
            this.unit = '';
        }
        if (unit !== '' && !CSS_LENGTH_UNIT_REGEX.test(unit)) {
            this.num = NaN;
            this.unit = '';
        }
        if (FIXED_CSS_LENGTH_UNITS.includes(unit)) {
            this.num = convertToPx(num, unit);
            this.unit = 'px';
        }
    }
    return _createClass(DecimalCSS, [
        {
            key: "add",
            value: function add(other) {
                if (this.unit !== other.unit) {
                    return new DecimalCSS(NaN, '');
                }
                return new DecimalCSS(this.num + other.num, this.unit);
            }
        },
        {
            key: "subtract",
            value: function subtract(other) {
                if (this.unit !== other.unit) {
                    return new DecimalCSS(NaN, '');
                }
                return new DecimalCSS(this.num - other.num, this.unit);
            }
        },
        {
            key: "multiply",
            value: function multiply(other) {
                if (this.unit !== '' && other.unit !== '' && this.unit !== other.unit) {
                    return new DecimalCSS(NaN, '');
                }
                return new DecimalCSS(this.num * other.num, this.unit || other.unit);
            }
        },
        {
            key: "divide",
            value: function divide(other) {
                if (this.unit !== '' && other.unit !== '' && this.unit !== other.unit) {
                    return new DecimalCSS(NaN, '');
                }
                return new DecimalCSS(this.num / other.num, this.unit || other.unit);
            }
        },
        {
            key: "toString",
            value: function toString() {
                return "".concat(this.num).concat(this.unit);
            }
        },
        {
            key: "isNaN",
            value: function isNaN() {
                return Number.isNaN(this.num);
            }
        }
    ], [
        {
            key: "parse",
            value: function parse(str) {
                var _NUM_SPLIT_REGEX$exec;
                var _ref = (_NUM_SPLIT_REGEX$exec = NUM_SPLIT_REGEX.exec(str)) !== null && _NUM_SPLIT_REGEX$exec !== void 0 ? _NUM_SPLIT_REGEX$exec : [], _ref2 = _slicedToArray(_ref, 3), numStr = _ref2[1], unit = _ref2[2];
                return new DecimalCSS(parseFloat(numStr), unit !== null && unit !== void 0 ? unit : '');
            }
        }
    ]);
}();
function calculateArithmetic(expr) {
    if (expr.includes(STR_NAN)) {
        return STR_NAN;
    }
    var newExpr = expr;
    while(newExpr.includes('*') || newExpr.includes('/')){
        var _MULTIPLY_OR_DIVIDE_R;
        var _ref3 = (_MULTIPLY_OR_DIVIDE_R = MULTIPLY_OR_DIVIDE_REGEX.exec(newExpr)) !== null && _MULTIPLY_OR_DIVIDE_R !== void 0 ? _MULTIPLY_OR_DIVIDE_R : [], _ref4 = _slicedToArray(_ref3, 4), leftOperand = _ref4[1], operator = _ref4[2], rightOperand = _ref4[3];
        var lTs = DecimalCSS.parse(leftOperand !== null && leftOperand !== void 0 ? leftOperand : '');
        var rTs = DecimalCSS.parse(rightOperand !== null && rightOperand !== void 0 ? rightOperand : '');
        var result = operator === '*' ? lTs.multiply(rTs) : lTs.divide(rTs);
        if (result.isNaN()) {
            return STR_NAN;
        }
        newExpr = newExpr.replace(MULTIPLY_OR_DIVIDE_REGEX, result.toString());
    }
    while(newExpr.includes('+') || /.-\d+(?:\.\d+)?/.test(newExpr)){
        var _ADD_OR_SUBTRACT_REGE;
        var _ref5 = (_ADD_OR_SUBTRACT_REGE = ADD_OR_SUBTRACT_REGEX.exec(newExpr)) !== null && _ADD_OR_SUBTRACT_REGE !== void 0 ? _ADD_OR_SUBTRACT_REGE : [], _ref6 = _slicedToArray(_ref5, 4), _leftOperand = _ref6[1], _operator = _ref6[2], _rightOperand = _ref6[3];
        var _lTs = DecimalCSS.parse(_leftOperand !== null && _leftOperand !== void 0 ? _leftOperand : '');
        var _rTs = DecimalCSS.parse(_rightOperand !== null && _rightOperand !== void 0 ? _rightOperand : '');
        var _result = _operator === '+' ? _lTs.add(_rTs) : _lTs.subtract(_rTs);
        if (_result.isNaN()) {
            return STR_NAN;
        }
        newExpr = newExpr.replace(ADD_OR_SUBTRACT_REGEX, _result.toString());
    }
    return newExpr;
}
var PARENTHESES_REGEX = /\(([^()]*)\)/;
function calculateParentheses(expr) {
    var newExpr = expr;
    while(newExpr.includes('(')){
        var _PARENTHESES_REGEX$ex = PARENTHESES_REGEX.exec(newExpr), _PARENTHESES_REGEX$ex2 = _slicedToArray(_PARENTHESES_REGEX$ex, 2), parentheticalExpression = _PARENTHESES_REGEX$ex2[1];
        newExpr = newExpr.replace(PARENTHESES_REGEX, calculateArithmetic(parentheticalExpression));
    }
    return newExpr;
}
function evaluateExpression(expression) {
    var newExpr = expression.replace(/\s+/g, '');
    newExpr = calculateParentheses(newExpr);
    newExpr = calculateArithmetic(newExpr);
    return newExpr;
}
function safeEvaluateExpression(expression) {
    try {
        return evaluateExpression(expression);
    } catch (e) {
        /* istanbul ignore next */ return STR_NAN;
    }
}
function reduceCSSCalc(expression) {
    var result = safeEvaluateExpression(expression.slice(5, -1));
    if (result === STR_NAN) {
        // notify the user
        return '';
    }
    return result;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Text.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Text",
    ()=>Text
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DOMUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReduceCSSCalc$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReduceCSSCalc.js [app-client] (ecmascript)");
var _excluded = [
    "x",
    "y",
    "lineHeight",
    "capHeight",
    "scaleToFit",
    "textAnchor",
    "verticalAnchor",
    "fill"
], _excluded2 = [
    "dx",
    "dy",
    "angle",
    "className",
    "breakAll"
];
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
;
;
;
;
;
;
;
;
var BREAKING_SPACES = /[ \f\n\r\t\v\u2028\u2029]+/;
var calculateWordWidths = function calculateWordWidths(_ref) {
    var children = _ref.children, breakAll = _ref.breakAll, style = _ref.style;
    try {
        var words = [];
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(children)) {
            if (breakAll) {
                words = children.toString().split('');
            } else {
                words = children.toString().split(BREAKING_SPACES);
            }
        }
        var wordsWithComputedWidth = words.map(function(word) {
            return {
                word: word,
                width: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getStringSize"])(word, style).width
            };
        });
        var spaceWidth = breakAll ? 0 : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getStringSize"])("\xA0", style).width;
        return {
            wordsWithComputedWidth: wordsWithComputedWidth,
            spaceWidth: spaceWidth
        };
    } catch (e) {
        return null;
    }
};
var calculateWordsByLines = function calculateWordsByLines(_ref2, initialWordsWithComputedWith, spaceWidth, lineWidth, scaleToFit) {
    var maxLines = _ref2.maxLines, children = _ref2.children, style = _ref2.style, breakAll = _ref2.breakAll;
    var shouldLimitLines = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(maxLines);
    var text = children;
    var calculate = function calculate() {
        var words = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : [];
        return words.reduce(function(result, _ref3) {
            var word = _ref3.word, width = _ref3.width;
            var currentLine = result[result.length - 1];
            if (currentLine && (lineWidth == null || scaleToFit || currentLine.width + width + spaceWidth < Number(lineWidth))) {
                // Word can be added to an existing line
                currentLine.words.push(word);
                currentLine.width += width + spaceWidth;
            } else {
                // Add first word to line or word is too long to scaleToFit on existing line
                var newLine = {
                    words: [
                        word
                    ],
                    width: width
                };
                result.push(newLine);
            }
            return result;
        }, []);
    };
    var originalResult = calculate(initialWordsWithComputedWith);
    var findLongestLine = function findLongestLine(words) {
        return words.reduce(function(a, b) {
            return a.width > b.width ? a : b;
        });
    };
    if (!shouldLimitLines) {
        return originalResult;
    }
    var suffix = '…';
    var checkOverflow = function checkOverflow(index) {
        var tempText = text.slice(0, index);
        var words = calculateWordWidths({
            breakAll: breakAll,
            style: style,
            children: tempText + suffix
        }).wordsWithComputedWidth;
        var result = calculate(words);
        var doesOverflow = result.length > maxLines || findLongestLine(result).width > Number(lineWidth);
        return [
            doesOverflow,
            result
        ];
    };
    var start = 0;
    var end = text.length - 1;
    var iterations = 0;
    var trimmedResult;
    while(start <= end && iterations <= text.length - 1){
        var middle = Math.floor((start + end) / 2);
        var prev = middle - 1;
        var _checkOverflow = checkOverflow(prev), _checkOverflow2 = _slicedToArray(_checkOverflow, 2), doesPrevOverflow = _checkOverflow2[0], result = _checkOverflow2[1];
        var _checkOverflow3 = checkOverflow(middle), _checkOverflow4 = _slicedToArray(_checkOverflow3, 1), doesMiddleOverflow = _checkOverflow4[0];
        if (!doesPrevOverflow && !doesMiddleOverflow) {
            start = middle + 1;
        }
        if (doesPrevOverflow && doesMiddleOverflow) {
            end = middle - 1;
        }
        if (!doesPrevOverflow && doesMiddleOverflow) {
            trimmedResult = result;
            break;
        }
        iterations++;
    }
    // Fallback to originalResult (result without trimming) if we cannot find the
    // where to trim.  This should not happen :tm:
    return trimmedResult || originalResult;
};
var getWordsWithoutCalculate = function getWordsWithoutCalculate(children) {
    var words = !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(children) ? children.toString().split(BREAKING_SPACES) : [];
    return [
        {
            words: words
        }
    ];
};
var getWordsByLines = function getWordsByLines(_ref4) {
    var width = _ref4.width, scaleToFit = _ref4.scaleToFit, children = _ref4.children, style = _ref4.style, breakAll = _ref4.breakAll, maxLines = _ref4.maxLines;
    // Only perform calculations if using features that require them (multiline, scaleToFit)
    if ((width || scaleToFit) && !__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Global"].isSsr) {
        var wordsWithComputedWidth, spaceWidth;
        var wordWidths = calculateWordWidths({
            breakAll: breakAll,
            children: children,
            style: style
        });
        if (wordWidths) {
            var wcw = wordWidths.wordsWithComputedWidth, sw = wordWidths.spaceWidth;
            wordsWithComputedWidth = wcw;
            spaceWidth = sw;
        } else {
            return getWordsWithoutCalculate(children);
        }
        return calculateWordsByLines({
            breakAll: breakAll,
            children: children,
            maxLines: maxLines,
            style: style
        }, wordsWithComputedWidth, spaceWidth, width, scaleToFit);
    }
    return getWordsWithoutCalculate(children);
};
var DEFAULT_FILL = '#808080';
var Text = function Text(_ref5) {
    var _ref5$x = _ref5.x, propsX = _ref5$x === void 0 ? 0 : _ref5$x, _ref5$y = _ref5.y, propsY = _ref5$y === void 0 ? 0 : _ref5$y, _ref5$lineHeight = _ref5.lineHeight, lineHeight = _ref5$lineHeight === void 0 ? '1em' : _ref5$lineHeight, _ref5$capHeight = _ref5.capHeight, capHeight = _ref5$capHeight === void 0 ? '0.71em' : _ref5$capHeight, _ref5$scaleToFit = _ref5.scaleToFit, scaleToFit = _ref5$scaleToFit === void 0 ? false : _ref5$scaleToFit, _ref5$textAnchor = _ref5.textAnchor, textAnchor = _ref5$textAnchor === void 0 ? 'start' : _ref5$textAnchor, _ref5$verticalAnchor = _ref5.verticalAnchor, verticalAnchor = _ref5$verticalAnchor === void 0 ? 'end' : _ref5$verticalAnchor, _ref5$fill = _ref5.fill, fill = _ref5$fill === void 0 ? DEFAULT_FILL : _ref5$fill, props = _objectWithoutProperties(_ref5, _excluded);
    var wordsByLines = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "Text.useMemo[wordsByLines]": function() {
            return getWordsByLines({
                breakAll: props.breakAll,
                children: props.children,
                maxLines: props.maxLines,
                scaleToFit: scaleToFit,
                style: props.style,
                width: props.width
            });
        }
    }["Text.useMemo[wordsByLines]"], [
        props.breakAll,
        props.children,
        props.maxLines,
        scaleToFit,
        props.style,
        props.width
    ]);
    var dx = props.dx, dy = props.dy, angle = props.angle, className = props.className, breakAll = props.breakAll, textProps = _objectWithoutProperties(props, _excluded2);
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(propsX) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(propsY)) {
        return null;
    }
    var x = propsX + ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(dx) ? dx : 0);
    var y = propsY + ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(dy) ? dy : 0);
    var startDy;
    switch(verticalAnchor){
        case 'start':
            startDy = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReduceCSSCalc$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["reduceCSSCalc"])("calc(".concat(capHeight, ")"));
            break;
        case 'middle':
            startDy = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReduceCSSCalc$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["reduceCSSCalc"])("calc(".concat((wordsByLines.length - 1) / 2, " * -").concat(lineHeight, " + (").concat(capHeight, " / 2))"));
            break;
        default:
            startDy = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReduceCSSCalc$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["reduceCSSCalc"])("calc(".concat(wordsByLines.length - 1, " * -").concat(lineHeight, ")"));
            break;
    }
    var transforms = [];
    if (scaleToFit) {
        var lineWidth = wordsByLines[0].width;
        var width = props.width;
        transforms.push("scale(".concat(((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(width) ? width / lineWidth : 1) / lineWidth, ")"));
    }
    if (angle) {
        transforms.push("rotate(".concat(angle, ", ").concat(x, ", ").concat(y, ")"));
    }
    if (transforms.length) {
        textProps.transform = transforms.join(' ');
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("text", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(textProps, true), {
        x: x,
        y: y,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-text', className),
        textAnchor: textAnchor,
        fill: fill.includes('url') ? DEFAULT_FILL : fill
    }), wordsByLines.map(function(line, index) {
        var words = line.words.join(breakAll ? '' : ' ');
        return(/*#__PURE__*/ // duplicate words will cause duplicate keys
        // eslint-disable-next-line react/no-array-index-key
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("tspan", {
            x: x,
            dy: index === 0 ? startDy : lineHeight,
            key: "".concat(words, "-").concat(index)
        }, words));
    }));
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ErrorBar.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ErrorBar",
    ()=>ErrorBar
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * @fileOverview Render a group of error bar
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/tiny-invariant/dist/esm/tiny-invariant.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var _excluded = [
    "offset",
    "layout",
    "width",
    "dataKey",
    "data",
    "dataPointFormatter",
    "xAxis",
    "yAxis"
];
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
var ErrorBar = /*#__PURE__*/ function(_React$Component) {
    function ErrorBar() {
        _classCallCheck(this, ErrorBar);
        return _callSuper(this, ErrorBar, arguments);
    }
    _inherits(ErrorBar, _React$Component);
    return _createClass(ErrorBar, [
        {
            key: "render",
            value: function render() {
                var _this$props = this.props, offset = _this$props.offset, layout = _this$props.layout, width = _this$props.width, dataKey = _this$props.dataKey, data = _this$props.data, dataPointFormatter = _this$props.dataPointFormatter, xAxis = _this$props.xAxis, yAxis = _this$props.yAxis, others = _objectWithoutProperties(_this$props, _excluded);
                var svgProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(others, false);
                !!(this.props.direction === 'x' && xAxis.type !== 'number') ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, 'ErrorBar requires Axis type property to be "number".') : "TURBOPACK unreachable" : void 0;
                var errorBars = data.map(function(entry) {
                    var _dataPointFormatter = dataPointFormatter(entry, dataKey), x = _dataPointFormatter.x, y = _dataPointFormatter.y, value = _dataPointFormatter.value, errorVal = _dataPointFormatter.errorVal;
                    if (!errorVal) {
                        return null;
                    }
                    var lineCoordinates = [];
                    var lowBound, highBound;
                    if (Array.isArray(errorVal)) {
                        var _errorVal = _slicedToArray(errorVal, 2);
                        lowBound = _errorVal[0];
                        highBound = _errorVal[1];
                    } else {
                        lowBound = highBound = errorVal;
                    }
                    if (layout === 'vertical') {
                        // error bar for horizontal charts, the y is fixed, x is a range value
                        var scale = xAxis.scale;
                        var yMid = y + offset;
                        var yMin = yMid + width;
                        var yMax = yMid - width;
                        var xMin = scale(value - lowBound);
                        var xMax = scale(value + highBound);
                        // the right line of |--|
                        lineCoordinates.push({
                            x1: xMax,
                            y1: yMin,
                            x2: xMax,
                            y2: yMax
                        });
                        // the middle line of |--|
                        lineCoordinates.push({
                            x1: xMin,
                            y1: yMid,
                            x2: xMax,
                            y2: yMid
                        });
                        // the left line of |--|
                        lineCoordinates.push({
                            x1: xMin,
                            y1: yMin,
                            x2: xMin,
                            y2: yMax
                        });
                    } else if (layout === 'horizontal') {
                        // error bar for horizontal charts, the x is fixed, y is a range value
                        var _scale = yAxis.scale;
                        var xMid = x + offset;
                        var _xMin = xMid - width;
                        var _xMax = xMid + width;
                        var _yMin = _scale(value - lowBound);
                        var _yMax = _scale(value + highBound);
                        // the top line
                        lineCoordinates.push({
                            x1: _xMin,
                            y1: _yMax,
                            x2: _xMax,
                            y2: _yMax
                        });
                        // the middle line
                        lineCoordinates.push({
                            x1: xMid,
                            y1: _yMin,
                            x2: xMid,
                            y2: _yMax
                        });
                        // the bottom line
                        lineCoordinates.push({
                            x1: _xMin,
                            y1: _yMin,
                            x2: _xMax,
                            y2: _yMin
                        });
                    }
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], _extends({
                        className: "recharts-errorBar",
                        key: "bar-".concat(lineCoordinates.map(function(c) {
                            return "".concat(c.x1, "-").concat(c.x2, "-").concat(c.y1, "-").concat(c.y2);
                        }))
                    }, svgProps), lineCoordinates.map(function(coordinates) {
                        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", _extends({}, coordinates, {
                            key: "line-".concat(coordinates.x1, "-").concat(coordinates.x2, "-").concat(coordinates.y1, "-").concat(coordinates.y2)
                        }));
                    }));
                });
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: "recharts-errorBars"
                }, errorBars);
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Component);
_defineProperty(ErrorBar, "defaultProps", {
    stroke: 'black',
    strokeWidth: 1.5,
    width: 5,
    offset: 0,
    layout: 'horizontal'
});
_defineProperty(ErrorBar, "displayName", 'ErrorBar');
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/getLegendProps.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getLegendProps",
    ()=>getLegendProps
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Legend$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Legend.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
var getLegendProps = function getLegendProps(_ref) {
    var children = _ref.children, formattedGraphicalItems = _ref.formattedGraphicalItems, legendWidth = _ref.legendWidth, legendContent = _ref.legendContent;
    var legendItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Legend$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Legend"]);
    if (!legendItem) {
        return null;
    }
    var legendDefaultProps = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Legend$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Legend"].defaultProps;
    var legendProps = legendDefaultProps !== undefined ? _objectSpread(_objectSpread({}, legendDefaultProps), legendItem.props) : {};
    var legendData;
    if (legendItem.props && legendItem.props.payload) {
        legendData = legendItem.props && legendItem.props.payload;
    } else if (legendContent === 'children') {
        legendData = (formattedGraphicalItems || []).reduce(function(result, _ref2) {
            var item = _ref2.item, props = _ref2.props;
            var data = props.sectors || props.data || [];
            return result.concat(data.map(function(entry) {
                return {
                    type: legendItem.props.iconType || item.props.legendType,
                    value: entry.name,
                    color: entry.fill,
                    payload: entry
                };
            }));
        }, []);
    } else {
        legendData = (formattedGraphicalItems || []).map(function(_ref3) {
            var item = _ref3.item;
            var itemDefaultProps = item.type.defaultProps;
            var itemProps = itemDefaultProps !== undefined ? _objectSpread(_objectSpread({}, itemDefaultProps), item.props) : {};
            var dataKey = itemProps.dataKey, name = itemProps.name, legendType = itemProps.legendType, hide = itemProps.hide;
            return {
                inactive: hide,
                dataKey: dataKey,
                type: legendProps.iconType || legendType || 'square',
                color: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getMainColorOfGraphicItem"])(item),
                value: name || dataKey,
                // @ts-expect-error property strokeDasharray is required in Payload but optional in props
                payload: itemProps
            };
        });
    }
    return _objectSpread(_objectSpread(_objectSpread({}, legendProps), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Legend$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Legend"].getWithHeight(legendItem, legendWidth)), {}, {
        payload: legendData,
        item: legendItem
    });
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MAX_VALUE_REG",
    ()=>MAX_VALUE_REG,
    "MIN_VALUE_REG",
    ()=>MIN_VALUE_REG,
    "appendOffsetOfLegend",
    ()=>appendOffsetOfLegend,
    "calculateActiveTickIndex",
    ()=>calculateActiveTickIndex,
    "checkDomainOfScale",
    ()=>checkDomainOfScale,
    "combineEventHandlers",
    ()=>combineEventHandlers,
    "findPositionOfBar",
    ()=>findPositionOfBar,
    "getBandSizeOfAxis",
    ()=>getBandSizeOfAxis,
    "getBarPosition",
    ()=>getBarPosition,
    "getBarSizeList",
    ()=>getBarSizeList,
    "getBaseValueOfBar",
    ()=>getBaseValueOfBar,
    "getCateCoordinateOfBar",
    ()=>getCateCoordinateOfBar,
    "getCateCoordinateOfLine",
    ()=>getCateCoordinateOfLine,
    "getCoordinatesOfGrid",
    ()=>getCoordinatesOfGrid,
    "getDomainOfDataByKey",
    ()=>getDomainOfDataByKey,
    "getDomainOfErrorBars",
    ()=>getDomainOfErrorBars,
    "getDomainOfItemsWithSameAxis",
    ()=>getDomainOfItemsWithSameAxis,
    "getDomainOfStackGroups",
    ()=>getDomainOfStackGroups,
    "getMainColorOfGraphicItem",
    ()=>getMainColorOfGraphicItem,
    "getStackGroupsByAxisId",
    ()=>getStackGroupsByAxisId,
    "getStackedData",
    ()=>getStackedData,
    "getStackedDataOfItem",
    ()=>getStackedDataOfItem,
    "getTicksOfAxis",
    ()=>getTicksOfAxis,
    "getTicksOfScale",
    ()=>getTicksOfScale,
    "getTooltipItem",
    ()=>getTooltipItem,
    "getValueByDataKey",
    ()=>getValueByDataKey,
    "isCategoricalAxis",
    ()=>isCategoricalAxis,
    "offsetPositive",
    ()=>offsetPositive,
    "offsetSign",
    ()=>offsetSign,
    "parseDomainOfCategoryAxis",
    ()=>parseDomainOfCategoryAxis,
    "parseErrorBarsOfAxis",
    ()=>parseErrorBarsOfAxis,
    "parseScale",
    ()=>parseScale,
    "parseSpecifiedDomain",
    ()=>parseSpecifiedDomain,
    "truncateByDomain",
    ()=>truncateByDomain
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/victory-vendor/es/d3-scale.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/victory-vendor/es/d3-scale.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$shape$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/victory-vendor/es/d3-shape.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$stack$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stack$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/stack.js [app-client] (ecmascript) <export default as stack>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$expand$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetExpand$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/offset/expand.js [app-client] (ecmascript) <export default as stackOffsetExpand>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$none$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetNone$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/offset/none.js [app-client] (ecmascript) <export default as stackOffsetNone>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$silhouette$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetSilhouette$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/offset/silhouette.js [app-client] (ecmascript) <export default as stackOffsetSilhouette>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$wiggle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetWiggle$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/offset/wiggle.js [app-client] (ecmascript) <export default as stackOffsetWiggle>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$order$2f$none$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOrderNone$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/order/none.js [app-client] (ecmascript) <export default as stackOrderNone>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/max.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$min$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/min.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isString.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$flatMap$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/flatMap.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNaN.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/upperFirst.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$sortBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/sortBy.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2d$scale$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts-scale/es6/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2d$scale$2f$es6$2f$getNiceTickValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts-scale/es6/getNiceTickValues.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ErrorBar$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ErrorBar.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
// TODO: Cause of circular dependency. Needs refactor.
// import { RadiusAxisProps, AngleAxisProps } from '../polar/types';
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getLegendProps$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/getLegendProps.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread();
}
function _nonIterableSpread() {
    throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _iterableToArray(iter) {
    if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter);
}
function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) return _arrayLikeToArray(arr);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
function getValueByDataKey(obj, dataKey, defaultValue) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(obj) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(dataKey)) {
        return defaultValue;
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(dataKey)) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(obj, dataKey, defaultValue);
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(dataKey)) {
        return dataKey(obj);
    }
    return defaultValue;
}
function getDomainOfDataByKey(data, key, type, filterNil) {
    var flattenData = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$flatMap$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(data, function(entry) {
        return getValueByDataKey(entry, key);
    });
    if (type === 'number') {
        // @ts-expect-error parseFloat type only accepts strings
        var domain = flattenData.filter(function(entry) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(entry) || parseFloat(entry);
        });
        return domain.length ? [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$min$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(domain),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(domain)
        ] : [
            Infinity,
            -Infinity
        ];
    }
    var validateData = filterNil ? flattenData.filter(function(entry) {
        return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry);
    }) : flattenData;
    // Supports x-axis of Date type
    return validateData.map(function(entry) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(entry) || entry instanceof Date ? entry : '';
    });
}
var calculateActiveTickIndex = function calculateActiveTickIndex(coordinate) {
    var _ticks$length;
    var ticks = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : [];
    var unsortedTicks = arguments.length > 2 ? arguments[2] : undefined;
    var axis = arguments.length > 3 ? arguments[3] : undefined;
    var index = -1;
    var len = (_ticks$length = ticks === null || ticks === void 0 ? void 0 : ticks.length) !== null && _ticks$length !== void 0 ? _ticks$length : 0;
    // if there are 1 or less ticks ticks then the active tick is at index 0
    if (len <= 1) {
        return 0;
    }
    if (axis && axis.axisType === 'angleAxis' && Math.abs(Math.abs(axis.range[1] - axis.range[0]) - 360) <= 1e-6) {
        var range = axis.range;
        // ticks are distributed in a circle
        for(var i = 0; i < len; i++){
            var before = i > 0 ? unsortedTicks[i - 1].coordinate : unsortedTicks[len - 1].coordinate;
            var cur = unsortedTicks[i].coordinate;
            var after = i >= len - 1 ? unsortedTicks[0].coordinate : unsortedTicks[i + 1].coordinate;
            var sameDirectionCoord = void 0;
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(cur - before) !== (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(after - cur)) {
                var diffInterval = [];
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(after - cur) === (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(range[1] - range[0])) {
                    sameDirectionCoord = after;
                    var curInRange = cur + range[1] - range[0];
                    diffInterval[0] = Math.min(curInRange, (curInRange + before) / 2);
                    diffInterval[1] = Math.max(curInRange, (curInRange + before) / 2);
                } else {
                    sameDirectionCoord = before;
                    var afterInRange = after + range[1] - range[0];
                    diffInterval[0] = Math.min(cur, (afterInRange + cur) / 2);
                    diffInterval[1] = Math.max(cur, (afterInRange + cur) / 2);
                }
                var sameInterval = [
                    Math.min(cur, (sameDirectionCoord + cur) / 2),
                    Math.max(cur, (sameDirectionCoord + cur) / 2)
                ];
                if (coordinate > sameInterval[0] && coordinate <= sameInterval[1] || coordinate >= diffInterval[0] && coordinate <= diffInterval[1]) {
                    index = unsortedTicks[i].index;
                    break;
                }
            } else {
                var minValue = Math.min(before, after);
                var maxValue = Math.max(before, after);
                if (coordinate > (minValue + cur) / 2 && coordinate <= (maxValue + cur) / 2) {
                    index = unsortedTicks[i].index;
                    break;
                }
            }
        }
    } else {
        // ticks are distributed in a single direction
        for(var _i = 0; _i < len; _i++){
            if (_i === 0 && coordinate <= (ticks[_i].coordinate + ticks[_i + 1].coordinate) / 2 || _i > 0 && _i < len - 1 && coordinate > (ticks[_i].coordinate + ticks[_i - 1].coordinate) / 2 && coordinate <= (ticks[_i].coordinate + ticks[_i + 1].coordinate) / 2 || _i === len - 1 && coordinate > (ticks[_i].coordinate + ticks[_i - 1].coordinate) / 2) {
                index = ticks[_i].index;
                break;
            }
        }
    }
    return index;
};
var getMainColorOfGraphicItem = function getMainColorOfGraphicItem(item) {
    var _item$type;
    var _ref = item, displayName = _ref.type.displayName; // TODO: check if displayName is valid.
    var defaultedProps = (_item$type = item.type) !== null && _item$type !== void 0 && _item$type.defaultProps ? _objectSpread(_objectSpread({}, item.type.defaultProps), item.props) : item.props;
    var stroke = defaultedProps.stroke, fill = defaultedProps.fill;
    var result;
    switch(displayName){
        case 'Line':
            result = stroke;
            break;
        case 'Area':
        case 'Radar':
            result = stroke && stroke !== 'none' ? stroke : fill;
            break;
        default:
            result = fill;
            break;
    }
    return result;
};
var getBarSizeList = function getBarSizeList(_ref2) {
    var globalSize = _ref2.barSize, totalSize = _ref2.totalSize, _ref2$stackGroups = _ref2.stackGroups, stackGroups = _ref2$stackGroups === void 0 ? {} : _ref2$stackGroups;
    if (!stackGroups) {
        return {};
    }
    var result = {};
    var numericAxisIds = Object.keys(stackGroups);
    for(var i = 0, len = numericAxisIds.length; i < len; i++){
        var sgs = stackGroups[numericAxisIds[i]].stackGroups;
        var stackIds = Object.keys(sgs);
        for(var j = 0, sLen = stackIds.length; j < sLen; j++){
            var _sgs$stackIds$j = sgs[stackIds[j]], items = _sgs$stackIds$j.items, cateAxisId = _sgs$stackIds$j.cateAxisId;
            var barItems = items.filter(function(item) {
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDisplayName"])(item.type).indexOf('Bar') >= 0;
            });
            if (barItems && barItems.length) {
                var barItemDefaultProps = barItems[0].type.defaultProps;
                var barItemProps = barItemDefaultProps !== undefined ? _objectSpread(_objectSpread({}, barItemDefaultProps), barItems[0].props) : barItems[0].props;
                var selfSize = barItemProps.barSize;
                var cateId = barItemProps[cateAxisId];
                if (!result[cateId]) {
                    result[cateId] = [];
                }
                var barSize = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(selfSize) ? globalSize : selfSize;
                result[cateId].push({
                    item: barItems[0],
                    stackList: barItems.slice(1),
                    barSize: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(barSize) ? undefined : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(barSize, totalSize, 0)
                });
            }
        }
    }
    return result;
};
var getBarPosition = function getBarPosition(_ref3) {
    var barGap = _ref3.barGap, barCategoryGap = _ref3.barCategoryGap, bandSize = _ref3.bandSize, _ref3$sizeList = _ref3.sizeList, sizeList = _ref3$sizeList === void 0 ? [] : _ref3$sizeList, maxBarSize = _ref3.maxBarSize;
    var len = sizeList.length;
    if (len < 1) return null;
    var realBarGap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(barGap, bandSize, 0, true);
    var result;
    var initialValue = [];
    // whether or not is barSize setted by user
    if (sizeList[0].barSize === +sizeList[0].barSize) {
        var useFull = false;
        var fullBarSize = bandSize / len;
        // @ts-expect-error the type check above does not check for type number explicitly
        var sum = sizeList.reduce(function(res, entry) {
            return res + entry.barSize || 0;
        }, 0);
        sum += (len - 1) * realBarGap;
        if (sum >= bandSize) {
            sum -= (len - 1) * realBarGap;
            realBarGap = 0;
        }
        if (sum >= bandSize && fullBarSize > 0) {
            useFull = true;
            fullBarSize *= 0.9;
            sum = len * fullBarSize;
        }
        var offset = (bandSize - sum) / 2 >> 0;
        var prev = {
            offset: offset - realBarGap,
            size: 0
        };
        result = sizeList.reduce(function(res, entry) {
            var newPosition = {
                item: entry.item,
                position: {
                    offset: prev.offset + prev.size + realBarGap,
                    // @ts-expect-error the type check above does not check for type number explicitly
                    size: useFull ? fullBarSize : entry.barSize
                }
            };
            var newRes = [].concat(_toConsumableArray(res), [
                newPosition
            ]);
            prev = newRes[newRes.length - 1].position;
            if (entry.stackList && entry.stackList.length) {
                entry.stackList.forEach(function(item) {
                    newRes.push({
                        item: item,
                        position: prev
                    });
                });
            }
            return newRes;
        }, initialValue);
    } else {
        var _offset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(barCategoryGap, bandSize, 0, true);
        if (bandSize - 2 * _offset - (len - 1) * realBarGap <= 0) {
            realBarGap = 0;
        }
        var originalSize = (bandSize - 2 * _offset - (len - 1) * realBarGap) / len;
        if (originalSize > 1) {
            originalSize >>= 0;
        }
        var size = maxBarSize === +maxBarSize ? Math.min(originalSize, maxBarSize) : originalSize;
        result = sizeList.reduce(function(res, entry, i) {
            var newRes = [].concat(_toConsumableArray(res), [
                {
                    item: entry.item,
                    position: {
                        offset: _offset + (originalSize + realBarGap) * i + (originalSize - size) / 2,
                        size: size
                    }
                }
            ]);
            if (entry.stackList && entry.stackList.length) {
                entry.stackList.forEach(function(item) {
                    newRes.push({
                        item: item,
                        position: newRes[newRes.length - 1].position
                    });
                });
            }
            return newRes;
        }, initialValue);
    }
    return result;
};
var appendOffsetOfLegend = function appendOffsetOfLegend(offset, _unused, props, legendBox) {
    var children = props.children, width = props.width, margin = props.margin;
    var legendWidth = width - (margin.left || 0) - (margin.right || 0);
    var legendProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getLegendProps$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getLegendProps"])({
        children: children,
        legendWidth: legendWidth
    });
    if (legendProps) {
        var _ref4 = legendBox || {}, boxWidth = _ref4.width, boxHeight = _ref4.height;
        var align = legendProps.align, verticalAlign = legendProps.verticalAlign, layout = legendProps.layout;
        if ((layout === 'vertical' || layout === 'horizontal' && verticalAlign === 'middle') && align !== 'center' && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(offset[align])) {
            return _objectSpread(_objectSpread({}, offset), {}, _defineProperty({}, align, offset[align] + (boxWidth || 0)));
        }
        if ((layout === 'horizontal' || layout === 'vertical' && align === 'center') && verticalAlign !== 'middle' && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(offset[verticalAlign])) {
            return _objectSpread(_objectSpread({}, offset), {}, _defineProperty({}, verticalAlign, offset[verticalAlign] + (boxHeight || 0)));
        }
    }
    return offset;
};
var isErrorBarRelevantForAxis = function isErrorBarRelevantForAxis(layout, axisType, direction) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(axisType)) {
        return true;
    }
    if (layout === 'horizontal') {
        return axisType === 'yAxis';
    }
    if (layout === 'vertical') {
        return axisType === 'xAxis';
    }
    if (direction === 'x') {
        return axisType === 'xAxis';
    }
    if (direction === 'y') {
        return axisType === 'yAxis';
    }
    return true;
};
var getDomainOfErrorBars = function getDomainOfErrorBars(data, item, dataKey, layout, axisType) {
    var children = item.props.children;
    var errorBars = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ErrorBar$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ErrorBar"]).filter(function(errorBarChild) {
        return isErrorBarRelevantForAxis(layout, axisType, errorBarChild.props.direction);
    });
    if (errorBars && errorBars.length) {
        var keys = errorBars.map(function(errorBarChild) {
            return errorBarChild.props.dataKey;
        });
        return data.reduce(function(result, entry) {
            var entryValue = getValueByDataKey(entry, dataKey);
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entryValue)) return result;
            var mainValue = Array.isArray(entryValue) ? [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$min$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entryValue),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entryValue)
            ] : [
                entryValue,
                entryValue
            ];
            var errorDomain = keys.reduce(function(prevErrorArr, k) {
                var errorValue = getValueByDataKey(entry, k, 0);
                var lowerValue = mainValue[0] - Math.abs(Array.isArray(errorValue) ? errorValue[0] : errorValue);
                var upperValue = mainValue[1] + Math.abs(Array.isArray(errorValue) ? errorValue[1] : errorValue);
                return [
                    Math.min(lowerValue, prevErrorArr[0]),
                    Math.max(upperValue, prevErrorArr[1])
                ];
            }, [
                Infinity,
                -Infinity
            ]);
            return [
                Math.min(errorDomain[0], result[0]),
                Math.max(errorDomain[1], result[1])
            ];
        }, [
            Infinity,
            -Infinity
        ]);
    }
    return null;
};
var parseErrorBarsOfAxis = function parseErrorBarsOfAxis(data, items, dataKey, axisType, layout) {
    var domains = items.map(function(item) {
        return getDomainOfErrorBars(data, item, dataKey, layout, axisType);
    }).filter(function(entry) {
        return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry);
    });
    if (domains && domains.length) {
        return domains.reduce(function(result, entry) {
            return [
                Math.min(result[0], entry[0]),
                Math.max(result[1], entry[1])
            ];
        }, [
            Infinity,
            -Infinity
        ]);
    }
    return null;
};
var getDomainOfItemsWithSameAxis = function getDomainOfItemsWithSameAxis(data, items, type, layout, filterNil) {
    var domains = items.map(function(item) {
        var dataKey = item.props.dataKey;
        if (type === 'number' && dataKey) {
            return getDomainOfErrorBars(data, item, dataKey, layout) || getDomainOfDataByKey(data, dataKey, type, filterNil);
        }
        return getDomainOfDataByKey(data, dataKey, type, filterNil);
    });
    if (type === 'number') {
        // Calculate the domain of number axis
        return domains.reduce(// @ts-expect-error if (type === number) means that the domain is numerical type
        // - but this link is missing in the type definition
        function(result, entry) {
            return [
                Math.min(result[0], entry[0]),
                Math.max(result[1], entry[1])
            ];
        }, [
            Infinity,
            -Infinity
        ]);
    }
    var tag = {};
    // Get the union set of category axis
    return domains.reduce(function(result, entry) {
        for(var i = 0, len = entry.length; i < len; i++){
            // @ts-expect-error Date cannot index an object
            if (!tag[entry[i]]) {
                // @ts-expect-error Date cannot index an object
                tag[entry[i]] = true;
                // @ts-expect-error Date cannot index an object
                result.push(entry[i]);
            }
        }
        return result;
    }, []);
};
var isCategoricalAxis = function isCategoricalAxis(layout, axisType) {
    return layout === 'horizontal' && axisType === 'xAxis' || layout === 'vertical' && axisType === 'yAxis' || layout === 'centric' && axisType === 'angleAxis' || layout === 'radial' && axisType === 'radiusAxis';
};
var getCoordinatesOfGrid = function getCoordinatesOfGrid(ticks, minValue, maxValue, syncWithTicks) {
    if (syncWithTicks) {
        return ticks.map(function(entry) {
            return entry.coordinate;
        });
    }
    var hasMin, hasMax;
    var values = ticks.map(function(entry) {
        if (entry.coordinate === minValue) {
            hasMin = true;
        }
        if (entry.coordinate === maxValue) {
            hasMax = true;
        }
        return entry.coordinate;
    });
    if (!hasMin) {
        values.push(minValue);
    }
    if (!hasMax) {
        values.push(maxValue);
    }
    return values;
};
var getTicksOfAxis = function getTicksOfAxis(axis, isGrid, isAll) {
    if (!axis) return null;
    var scale = axis.scale;
    var duplicateDomain = axis.duplicateDomain, type = axis.type, range = axis.range;
    var offsetForBand = axis.realScaleType === 'scaleBand' ? scale.bandwidth() / 2 : 2;
    var offset = (isGrid || isAll) && type === 'category' && scale.bandwidth ? scale.bandwidth() / offsetForBand : 0;
    offset = axis.axisType === 'angleAxis' && (range === null || range === void 0 ? void 0 : range.length) >= 2 ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(range[0] - range[1]) * 2 * offset : offset;
    // The ticks set by user should only affect the ticks adjacent to axis line
    if (isGrid && (axis.ticks || axis.niceTicks)) {
        var result = (axis.ticks || axis.niceTicks).map(function(entry) {
            var scaleContent = duplicateDomain ? duplicateDomain.indexOf(entry) : entry;
            return {
                // If the scaleContent is not a number, the coordinate will be NaN.
                // That could be the case for example with a PointScale and a string as domain.
                coordinate: scale(scaleContent) + offset,
                value: entry,
                offset: offset
            };
        });
        return result.filter(function(row) {
            return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(row.coordinate);
        });
    }
    // When axis is a categorial axis, but the type of axis is number or the scale of axis is not "auto"
    if (axis.isCategorical && axis.categoricalDomain) {
        return axis.categoricalDomain.map(function(entry, index) {
            return {
                coordinate: scale(entry) + offset,
                value: entry,
                index: index,
                offset: offset
            };
        });
    }
    if (scale.ticks && !isAll) {
        return scale.ticks(axis.tickCount).map(function(entry) {
            return {
                coordinate: scale(entry) + offset,
                value: entry,
                offset: offset
            };
        });
    }
    // When axis has duplicated text, serial numbers are used to generate scale
    return scale.domain().map(function(entry, index) {
        return {
            coordinate: scale(entry) + offset,
            value: duplicateDomain ? duplicateDomain[entry] : entry,
            index: index,
            offset: offset
        };
    });
};
/**
 * combine the handlers
 * @param  {Function} defaultHandler Internal private handler
 * @param  {Function} childHandler Handler function specified in child component
 * @return {Function}                The combined handler
 */ var handlerWeakMap = new WeakMap();
var combineEventHandlers = function combineEventHandlers(defaultHandler, childHandler) {
    if (typeof childHandler !== 'function') {
        return defaultHandler;
    }
    if (!handlerWeakMap.has(defaultHandler)) {
        handlerWeakMap.set(defaultHandler, new WeakMap());
    }
    var childWeakMap = handlerWeakMap.get(defaultHandler);
    if (childWeakMap.has(childHandler)) {
        return childWeakMap.get(childHandler);
    }
    var combineHandler = function combineHandler() {
        defaultHandler.apply(void 0, arguments);
        childHandler.apply(void 0, arguments);
    };
    childWeakMap.set(childHandler, combineHandler);
    return combineHandler;
};
var parseScale = function parseScale(axis, chartType, hasBar) {
    var scale = axis.scale, type = axis.type, layout = axis.layout, axisType = axis.axisType;
    if (scale === 'auto') {
        if (layout === 'radial' && axisType === 'radiusAxis') {
            return {
                scale: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scaleBand(),
                realScaleType: 'band'
            };
        }
        if (layout === 'radial' && axisType === 'angleAxis') {
            return {
                scale: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scaleLinear(),
                realScaleType: 'linear'
            };
        }
        if (type === 'category' && chartType && (chartType.indexOf('LineChart') >= 0 || chartType.indexOf('AreaChart') >= 0 || chartType.indexOf('ComposedChart') >= 0 && !hasBar)) {
            return {
                scale: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scalePoint(),
                realScaleType: 'point'
            };
        }
        if (type === 'category') {
            return {
                scale: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scaleBand(),
                realScaleType: 'band'
            };
        }
        return {
            scale: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scaleLinear(),
            realScaleType: 'linear'
        };
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isString$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(scale)) {
        var name = "scale".concat((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(scale));
        return {
            scale: (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__[name] || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scalePoint)(),
            realScaleType: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__[name] ? name : 'point'
        };
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(scale) ? {
        scale: scale
    } : {
        scale: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__.scalePoint(),
        realScaleType: 'point'
    };
};
var EPS = 1e-4;
var checkDomainOfScale = function checkDomainOfScale(scale) {
    var domain = scale.domain();
    if (!domain || domain.length <= 2) {
        return;
    }
    var len = domain.length;
    var range = scale.range();
    var minValue = Math.min(range[0], range[1]) - EPS;
    var maxValue = Math.max(range[0], range[1]) + EPS;
    var first = scale(domain[0]);
    var last = scale(domain[len - 1]);
    if (first < minValue || first > maxValue || last < minValue || last > maxValue) {
        scale.domain([
            domain[0],
            domain[len - 1]
        ]);
    }
};
var findPositionOfBar = function findPositionOfBar(barPosition, child) {
    if (!barPosition) {
        return null;
    }
    for(var i = 0, len = barPosition.length; i < len; i++){
        if (barPosition[i].item === child) {
            return barPosition[i].position;
        }
    }
    return null;
};
var truncateByDomain = function truncateByDomain(value, domain) {
    if (!domain || domain.length !== 2 || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(domain[0]) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(domain[1])) {
        return value;
    }
    var minValue = Math.min(domain[0], domain[1]);
    var maxValue = Math.max(domain[0], domain[1]);
    var result = [
        value[0],
        value[1]
    ];
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(value[0]) || value[0] < minValue) {
        result[0] = minValue;
    }
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(value[1]) || value[1] > maxValue) {
        result[1] = maxValue;
    }
    if (result[0] > maxValue) {
        result[0] = maxValue;
    }
    if (result[1] < minValue) {
        result[1] = minValue;
    }
    return result;
};
var offsetSign = function offsetSign(series) {
    var n = series.length;
    if (n <= 0) {
        return;
    }
    for(var j = 0, m = series[0].length; j < m; ++j){
        var positive = 0;
        var negative = 0;
        for(var i = 0; i < n; ++i){
            var value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(series[i][j][1]) ? series[i][j][0] : series[i][j][1];
            /* eslint-disable prefer-destructuring, no-param-reassign */ if (value >= 0) {
                series[i][j][0] = positive;
                series[i][j][1] = positive + value;
                positive = series[i][j][1];
            } else {
                series[i][j][0] = negative;
                series[i][j][1] = negative + value;
                negative = series[i][j][1];
            }
        /* eslint-enable prefer-destructuring, no-param-reassign */ }
    }
};
var offsetPositive = function offsetPositive(series) {
    var n = series.length;
    if (n <= 0) {
        return;
    }
    for(var j = 0, m = series[0].length; j < m; ++j){
        var positive = 0;
        for(var i = 0; i < n; ++i){
            var value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(series[i][j][1]) ? series[i][j][0] : series[i][j][1];
            /* eslint-disable prefer-destructuring, no-param-reassign */ if (value >= 0) {
                series[i][j][0] = positive;
                series[i][j][1] = positive + value;
                positive = series[i][j][1];
            } else {
                series[i][j][0] = 0;
                series[i][j][1] = 0;
            }
        /* eslint-enable prefer-destructuring, no-param-reassign */ }
    }
};
/**
 * Function type to compute offset for stacked data.
 *
 * d3-shape has something fishy going on with its types.
 * In @definitelytyped/d3-shape, this function (the offset accessor) is typed as Series<> => void.
 * However! When I actually open the storybook I can see that the offset accessor actually receives Array<Series<>>.
 * The same I can see in the source code itself:
 * https://github.com/DefinitelyTyped/DefinitelyTyped/discussions/66042
 * That one unfortunately has no types but we can tell it passes three-dimensional array.
 *
 * Which leads me to believe that definitelytyped is wrong on this one.
 * There's open discussion on this topic without much attention:
 * https://github.com/DefinitelyTyped/DefinitelyTyped/discussions/66042
 */ var STACK_OFFSET_MAP = {
    sign: offsetSign,
    // @ts-expect-error definitelytyped types are incorrect
    expand: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$expand$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetExpand$3e$__["stackOffsetExpand"],
    // @ts-expect-error definitelytyped types are incorrect
    none: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$none$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetNone$3e$__["stackOffsetNone"],
    // @ts-expect-error definitelytyped types are incorrect
    silhouette: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$silhouette$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetSilhouette$3e$__["stackOffsetSilhouette"],
    // @ts-expect-error definitelytyped types are incorrect
    wiggle: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$offset$2f$wiggle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOffsetWiggle$3e$__["stackOffsetWiggle"],
    positive: offsetPositive
};
var getStackedData = function getStackedData(data, stackItems, offsetType) {
    var dataKeys = stackItems.map(function(item) {
        return item.props.dataKey;
    });
    var offsetAccessor = STACK_OFFSET_MAP[offsetType];
    var stack = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$stack$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stack$3e$__["stack"])()// @ts-expect-error stack.keys type wants an array of strings, but we provide array of DataKeys
    .keys(dataKeys).value(function(d, key) {
        return +getValueByDataKey(d, key, 0);
    }).order(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$order$2f$none$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__stackOrderNone$3e$__["stackOrderNone"])// @ts-expect-error definitelytyped types are incorrect
    .offset(offsetAccessor);
    return stack(data);
};
var getStackGroupsByAxisId = function getStackGroupsByAxisId(data, _items, numericAxisId, cateAxisId, offsetType, reverseStackOrder) {
    if (!data) {
        return null;
    }
    // reversing items to affect render order (for layering)
    var items = reverseStackOrder ? _items.reverse() : _items;
    var parentStackGroupsInitialValue = {};
    var stackGroups = items.reduce(function(result, item) {
        var _item$type2;
        var defaultedProps = (_item$type2 = item.type) !== null && _item$type2 !== void 0 && _item$type2.defaultProps ? _objectSpread(_objectSpread({}, item.type.defaultProps), item.props) : item.props;
        var stackId = defaultedProps.stackId, hide = defaultedProps.hide;
        if (hide) {
            return result;
        }
        var axisId = defaultedProps[numericAxisId];
        var parentGroup = result[axisId] || {
            hasStack: false,
            stackGroups: {}
        };
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(stackId)) {
            var childGroup = parentGroup.stackGroups[stackId] || {
                numericAxisId: numericAxisId,
                cateAxisId: cateAxisId,
                items: []
            };
            childGroup.items.push(item);
            parentGroup.hasStack = true;
            parentGroup.stackGroups[stackId] = childGroup;
        } else {
            parentGroup.stackGroups[(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["uniqueId"])('_stackId_')] = {
                numericAxisId: numericAxisId,
                cateAxisId: cateAxisId,
                items: [
                    item
                ]
            };
        }
        return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, axisId, parentGroup));
    }, parentStackGroupsInitialValue);
    var axisStackGroupsInitialValue = {};
    return Object.keys(stackGroups).reduce(function(result, axisId) {
        var group = stackGroups[axisId];
        if (group.hasStack) {
            var stackGroupsInitialValue = {};
            group.stackGroups = Object.keys(group.stackGroups).reduce(function(res, stackId) {
                var g = group.stackGroups[stackId];
                return _objectSpread(_objectSpread({}, res), {}, _defineProperty({}, stackId, {
                    numericAxisId: numericAxisId,
                    cateAxisId: cateAxisId,
                    items: g.items,
                    stackedData: getStackedData(data, g.items, offsetType)
                }));
            }, stackGroupsInitialValue);
        }
        return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, axisId, group));
    }, axisStackGroupsInitialValue);
};
var getTicksOfScale = function getTicksOfScale(scale, opts) {
    var realScaleType = opts.realScaleType, type = opts.type, tickCount = opts.tickCount, originalDomain = opts.originalDomain, allowDecimals = opts.allowDecimals;
    var scaleType = realScaleType || opts.scale;
    if (scaleType !== 'auto' && scaleType !== 'linear') {
        return null;
    }
    if (tickCount && type === 'number' && originalDomain && (originalDomain[0] === 'auto' || originalDomain[1] === 'auto')) {
        // Calculate the ticks by the number of grid when the axis is a number axis
        var domain = scale.domain();
        if (!domain.length) {
            return null;
        }
        var tickValues = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2d$scale$2f$es6$2f$getNiceTickValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNiceTickValues"])(domain, tickCount, allowDecimals);
        scale.domain([
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$min$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tickValues),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tickValues)
        ]);
        return {
            niceTicks: tickValues
        };
    }
    if (tickCount && type === 'number') {
        var _domain = scale.domain();
        var _tickValues = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2d$scale$2f$es6$2f$getNiceTickValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTickValuesFixedDomain"])(_domain, tickCount, allowDecimals);
        return {
            niceTicks: _tickValues
        };
    }
    return null;
};
function getCateCoordinateOfLine(_ref5) {
    var axis = _ref5.axis, ticks = _ref5.ticks, bandSize = _ref5.bandSize, entry = _ref5.entry, index = _ref5.index, dataKey = _ref5.dataKey;
    if (axis.type === 'category') {
        // find coordinate of category axis by the value of category
        // @ts-expect-error why does this use direct object access instead of getValueByDataKey?
        if (!axis.allowDuplicatedCategory && axis.dataKey && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry[axis.dataKey])) {
            // @ts-expect-error why does this use direct object access instead of getValueByDataKey?
            var matchedTick = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findEntryInArray"])(ticks, 'value', entry[axis.dataKey]);
            if (matchedTick) {
                return matchedTick.coordinate + bandSize / 2;
            }
        }
        return ticks[index] ? ticks[index].coordinate + bandSize / 2 : null;
    }
    var value = getValueByDataKey(entry, !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(dataKey) ? dataKey : axis.dataKey);
    return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value) ? axis.scale(value) : null;
}
var getCateCoordinateOfBar = function getCateCoordinateOfBar(_ref6) {
    var axis = _ref6.axis, ticks = _ref6.ticks, offset = _ref6.offset, bandSize = _ref6.bandSize, entry = _ref6.entry, index = _ref6.index;
    if (axis.type === 'category') {
        return ticks[index] ? ticks[index].coordinate + offset : null;
    }
    var value = getValueByDataKey(entry, axis.dataKey, axis.domain[index]);
    return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value) ? axis.scale(value) - bandSize / 2 + offset : null;
};
var getBaseValueOfBar = function getBaseValueOfBar(_ref7) {
    var numericAxis = _ref7.numericAxis;
    var domain = numericAxis.scale.domain();
    if (numericAxis.type === 'number') {
        var minValue = Math.min(domain[0], domain[1]);
        var maxValue = Math.max(domain[0], domain[1]);
        if (minValue <= 0 && maxValue >= 0) {
            return 0;
        }
        if (maxValue < 0) {
            return maxValue;
        }
        return minValue;
    }
    return domain[0];
};
var getStackedDataOfItem = function getStackedDataOfItem(item, stackGroups) {
    var _item$type3;
    var defaultedProps = (_item$type3 = item.type) !== null && _item$type3 !== void 0 && _item$type3.defaultProps ? _objectSpread(_objectSpread({}, item.type.defaultProps), item.props) : item.props;
    var stackId = defaultedProps.stackId;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(stackId)) {
        var group = stackGroups[stackId];
        if (group) {
            var itemIndex = group.items.indexOf(item);
            return itemIndex >= 0 ? group.stackedData[itemIndex] : null;
        }
    }
    return null;
};
var getDomainOfSingle = function getDomainOfSingle(data) {
    return data.reduce(function(result, entry) {
        return [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$min$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry.concat([
                result[0]
            ]).filter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry.concat([
                result[1]
            ]).filter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"]))
        ];
    }, [
        Infinity,
        -Infinity
    ]);
};
var getDomainOfStackGroups = function getDomainOfStackGroups(stackGroups, startIndex, endIndex) {
    return Object.keys(stackGroups).reduce(function(result, stackId) {
        var group = stackGroups[stackId];
        var stackedData = group.stackedData;
        var domain = stackedData.reduce(function(res, entry) {
            var s = getDomainOfSingle(entry.slice(startIndex, endIndex + 1));
            return [
                Math.min(res[0], s[0]),
                Math.max(res[1], s[1])
            ];
        }, [
            Infinity,
            -Infinity
        ]);
        return [
            Math.min(domain[0], result[0]),
            Math.max(domain[1], result[1])
        ];
    }, [
        Infinity,
        -Infinity
    ]).map(function(result) {
        return result === Infinity || result === -Infinity ? 0 : result;
    });
};
var MIN_VALUE_REG = /^dataMin[\s]*-[\s]*([0-9]+([.]{1}[0-9]+){0,1})$/;
var MAX_VALUE_REG = /^dataMax[\s]*\+[\s]*([0-9]+([.]{1}[0-9]+){0,1})$/;
var parseSpecifiedDomain = function parseSpecifiedDomain(specifiedDomain, dataDomain, allowDataOverflow) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(specifiedDomain)) {
        return specifiedDomain(dataDomain, allowDataOverflow);
    }
    if (!Array.isArray(specifiedDomain)) {
        return dataDomain;
    }
    var domain = [];
    /* eslint-disable prefer-destructuring */ if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(specifiedDomain[0])) {
        domain[0] = allowDataOverflow ? specifiedDomain[0] : Math.min(specifiedDomain[0], dataDomain[0]);
    } else if (MIN_VALUE_REG.test(specifiedDomain[0])) {
        var value = +MIN_VALUE_REG.exec(specifiedDomain[0])[1];
        domain[0] = dataDomain[0] - value;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(specifiedDomain[0])) {
        domain[0] = specifiedDomain[0](dataDomain[0]);
    } else {
        domain[0] = dataDomain[0];
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(specifiedDomain[1])) {
        domain[1] = allowDataOverflow ? specifiedDomain[1] : Math.max(specifiedDomain[1], dataDomain[1]);
    } else if (MAX_VALUE_REG.test(specifiedDomain[1])) {
        var _value = +MAX_VALUE_REG.exec(specifiedDomain[1])[1];
        domain[1] = dataDomain[1] + _value;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(specifiedDomain[1])) {
        domain[1] = specifiedDomain[1](dataDomain[1]);
    } else {
        domain[1] = dataDomain[1];
    }
    /* eslint-enable prefer-destructuring */ return domain;
};
var getBandSizeOfAxis = function getBandSizeOfAxis(axis, ticks, isBar) {
    // @ts-expect-error we need to rethink scale type
    if (axis && axis.scale && axis.scale.bandwidth) {
        // @ts-expect-error we need to rethink scale type
        var bandWidth = axis.scale.bandwidth();
        if (!isBar || bandWidth > 0) {
            return bandWidth;
        }
    }
    if (axis && ticks && ticks.length >= 2) {
        var orderedTicks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$sortBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(ticks, function(o) {
            return o.coordinate;
        });
        var bandSize = Infinity;
        for(var i = 1, len = orderedTicks.length; i < len; i++){
            var cur = orderedTicks[i];
            var prev = orderedTicks[i - 1];
            bandSize = Math.min((cur.coordinate || 0) - (prev.coordinate || 0), bandSize);
        }
        return bandSize === Infinity ? 0 : bandSize;
    }
    return isBar ? undefined : 0;
};
var parseDomainOfCategoryAxis = function parseDomainOfCategoryAxis(specifiedDomain, calculatedDomain, axisChild) {
    if (!specifiedDomain || !specifiedDomain.length) {
        return calculatedDomain;
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(specifiedDomain, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(axisChild, 'type.defaultProps.domain'))) {
        return calculatedDomain;
    }
    return specifiedDomain;
};
var getTooltipItem = function getTooltipItem(graphicalItem, payload) {
    var defaultedProps = graphicalItem.type.defaultProps ? _objectSpread(_objectSpread({}, graphicalItem.type.defaultProps), graphicalItem.props) : graphicalItem.props;
    var dataKey = defaultedProps.dataKey, name = defaultedProps.name, unit = defaultedProps.unit, formatter = defaultedProps.formatter, tooltipType = defaultedProps.tooltipType, chartType = defaultedProps.chartType, hide = defaultedProps.hide;
    return _objectSpread(_objectSpread({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(graphicalItem, false)), {}, {
        dataKey: dataKey,
        unit: unit,
        formatter: formatter,
        name: name || dataKey,
        color: getMainColorOfGraphicItem(graphicalItem),
        value: getValueByDataKey(payload, dataKey),
        type: tooltipType,
        payload: payload,
        chartType: chartType,
        hide: hide
    });
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CssPrefixUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generatePrefixStyle",
    ()=>generatePrefixStyle
]);
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
var PREFIX_LIST = [
    'Webkit',
    'Moz',
    'O',
    'ms'
];
var generatePrefixStyle = function generatePrefixStyle(name, value) {
    if (!name) {
        return null;
    }
    var camelName = name.replace(/(\w)/, function(v) {
        return v.toUpperCase();
    });
    var result = PREFIX_LIST.reduce(function(res, entry) {
        return _objectSpread(_objectSpread({}, res), {}, _defineProperty({}, entry + camelName, value));
    }, {});
    result[name] = value;
    return result;
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/Brush.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Brush",
    ()=>Brush
]);
/**
 * @fileOverview Brush
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$scale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/victory-vendor/es/d3-scale.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$scale$2f$src$2f$band$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__point__as__scalePoint$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-scale/src/band.js [app-client] (ecmascript) <export point as scalePoint>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$range$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/range.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Text.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CssPrefixUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CssPrefixUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
var createScale = function createScale(_ref) {
    var data = _ref.data, startIndex = _ref.startIndex, endIndex = _ref.endIndex, x = _ref.x, width = _ref.width, travellerWidth = _ref.travellerWidth;
    if (!data || !data.length) {
        return {};
    }
    var len = data.length;
    var scale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$scale$2f$src$2f$band$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__point__as__scalePoint$3e$__["scalePoint"])().domain((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$range$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(0, len)).range([
        x,
        x + width - travellerWidth
    ]);
    var scaleValues = scale.domain().map(function(entry) {
        return scale(entry);
    });
    return {
        isTextActive: false,
        isSlideMoving: false,
        isTravellerMoving: false,
        isTravellerFocused: false,
        startX: scale(startIndex),
        endX: scale(endIndex),
        scale: scale,
        scaleValues: scaleValues
    };
};
var isTouch = function isTouch(e) {
    return e.changedTouches && !!e.changedTouches.length;
};
var Brush = /*#__PURE__*/ function(_PureComponent) {
    function Brush(props) {
        var _this;
        _classCallCheck(this, Brush);
        _this = _callSuper(this, Brush, [
            props
        ]);
        _defineProperty(_this, "handleDrag", function(e) {
            if (_this.leaveTimer) {
                clearTimeout(_this.leaveTimer);
                _this.leaveTimer = null;
            }
            if (_this.state.isTravellerMoving) {
                _this.handleTravellerMove(e);
            } else if (_this.state.isSlideMoving) {
                _this.handleSlideDrag(e);
            }
        });
        _defineProperty(_this, "handleTouchMove", function(e) {
            if (e.changedTouches != null && e.changedTouches.length > 0) {
                _this.handleDrag(e.changedTouches[0]);
            }
        });
        _defineProperty(_this, "handleDragEnd", function() {
            _this.setState({
                isTravellerMoving: false,
                isSlideMoving: false
            }, function() {
                var _this$props = _this.props, endIndex = _this$props.endIndex, onDragEnd = _this$props.onDragEnd, startIndex = _this$props.startIndex;
                onDragEnd === null || onDragEnd === void 0 || onDragEnd({
                    endIndex: endIndex,
                    startIndex: startIndex
                });
            });
            _this.detachDragEndListener();
        });
        _defineProperty(_this, "handleLeaveWrapper", function() {
            if (_this.state.isTravellerMoving || _this.state.isSlideMoving) {
                _this.leaveTimer = window.setTimeout(_this.handleDragEnd, _this.props.leaveTimeOut);
            }
        });
        _defineProperty(_this, "handleEnterSlideOrTraveller", function() {
            _this.setState({
                isTextActive: true
            });
        });
        _defineProperty(_this, "handleLeaveSlideOrTraveller", function() {
            _this.setState({
                isTextActive: false
            });
        });
        _defineProperty(_this, "handleSlideDragStart", function(e) {
            var event = isTouch(e) ? e.changedTouches[0] : e;
            _this.setState({
                isTravellerMoving: false,
                isSlideMoving: true,
                slideMoveStartX: event.pageX
            });
            _this.attachDragEndListener();
        });
        _this.travellerDragStartHandlers = {
            startX: _this.handleTravellerDragStart.bind(_this, 'startX'),
            endX: _this.handleTravellerDragStart.bind(_this, 'endX')
        };
        _this.state = {};
        return _this;
    }
    _inherits(Brush, _PureComponent);
    return _createClass(Brush, [
        {
            key: "componentWillUnmount",
            value: function componentWillUnmount() {
                if (this.leaveTimer) {
                    clearTimeout(this.leaveTimer);
                    this.leaveTimer = null;
                }
                this.detachDragEndListener();
            }
        },
        {
            key: "getIndex",
            value: function getIndex(_ref2) {
                var startX = _ref2.startX, endX = _ref2.endX;
                var scaleValues = this.state.scaleValues;
                var _this$props2 = this.props, gap = _this$props2.gap, data = _this$props2.data;
                var lastIndex = data.length - 1;
                var min = Math.min(startX, endX);
                var max = Math.max(startX, endX);
                var minIndex = Brush.getIndexInRange(scaleValues, min);
                var maxIndex = Brush.getIndexInRange(scaleValues, max);
                return {
                    startIndex: minIndex - minIndex % gap,
                    endIndex: maxIndex === lastIndex ? lastIndex : maxIndex - maxIndex % gap
                };
            }
        },
        {
            key: "getTextOfTick",
            value: function getTextOfTick(index) {
                var _this$props3 = this.props, data = _this$props3.data, tickFormatter = _this$props3.tickFormatter, dataKey = _this$props3.dataKey;
                var text = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getValueByDataKey"])(data[index], dataKey, index);
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tickFormatter) ? tickFormatter(text, index) : text;
            }
        },
        {
            key: "attachDragEndListener",
            value: function attachDragEndListener() {
                window.addEventListener('mouseup', this.handleDragEnd, true);
                window.addEventListener('touchend', this.handleDragEnd, true);
                window.addEventListener('mousemove', this.handleDrag, true);
            }
        },
        {
            key: "detachDragEndListener",
            value: function detachDragEndListener() {
                window.removeEventListener('mouseup', this.handleDragEnd, true);
                window.removeEventListener('touchend', this.handleDragEnd, true);
                window.removeEventListener('mousemove', this.handleDrag, true);
            }
        },
        {
            key: "handleSlideDrag",
            value: function handleSlideDrag(e) {
                var _this$state = this.state, slideMoveStartX = _this$state.slideMoveStartX, startX = _this$state.startX, endX = _this$state.endX;
                var _this$props4 = this.props, x = _this$props4.x, width = _this$props4.width, travellerWidth = _this$props4.travellerWidth, startIndex = _this$props4.startIndex, endIndex = _this$props4.endIndex, onChange = _this$props4.onChange;
                var delta = e.pageX - slideMoveStartX;
                if (delta > 0) {
                    delta = Math.min(delta, x + width - travellerWidth - endX, x + width - travellerWidth - startX);
                } else if (delta < 0) {
                    delta = Math.max(delta, x - startX, x - endX);
                }
                var newIndex = this.getIndex({
                    startX: startX + delta,
                    endX: endX + delta
                });
                if ((newIndex.startIndex !== startIndex || newIndex.endIndex !== endIndex) && onChange) {
                    onChange(newIndex);
                }
                this.setState({
                    startX: startX + delta,
                    endX: endX + delta,
                    slideMoveStartX: e.pageX
                });
            }
        },
        {
            key: "handleTravellerDragStart",
            value: function handleTravellerDragStart(id, e) {
                var event = isTouch(e) ? e.changedTouches[0] : e;
                this.setState({
                    isSlideMoving: false,
                    isTravellerMoving: true,
                    movingTravellerId: id,
                    brushMoveStartX: event.pageX
                });
                this.attachDragEndListener();
            }
        },
        {
            key: "handleTravellerMove",
            value: function handleTravellerMove(e) {
                var _this$state2 = this.state, brushMoveStartX = _this$state2.brushMoveStartX, movingTravellerId = _this$state2.movingTravellerId, endX = _this$state2.endX, startX = _this$state2.startX;
                var prevValue = this.state[movingTravellerId];
                var _this$props5 = this.props, x = _this$props5.x, width = _this$props5.width, travellerWidth = _this$props5.travellerWidth, onChange = _this$props5.onChange, gap = _this$props5.gap, data = _this$props5.data;
                var params = {
                    startX: this.state.startX,
                    endX: this.state.endX
                };
                var delta = e.pageX - brushMoveStartX;
                if (delta > 0) {
                    delta = Math.min(delta, x + width - travellerWidth - prevValue);
                } else if (delta < 0) {
                    delta = Math.max(delta, x - prevValue);
                }
                params[movingTravellerId] = prevValue + delta;
                var newIndex = this.getIndex(params);
                var startIndex = newIndex.startIndex, endIndex = newIndex.endIndex;
                var isFullGap = function isFullGap() {
                    var lastIndex = data.length - 1;
                    if (movingTravellerId === 'startX' && (endX > startX ? startIndex % gap === 0 : endIndex % gap === 0) || endX < startX && endIndex === lastIndex || movingTravellerId === 'endX' && (endX > startX ? endIndex % gap === 0 : startIndex % gap === 0) || endX > startX && endIndex === lastIndex) {
                        return true;
                    }
                    return false;
                };
                this.setState(_defineProperty(_defineProperty({}, movingTravellerId, prevValue + delta), "brushMoveStartX", e.pageX), function() {
                    if (onChange) {
                        if (isFullGap()) {
                            onChange(newIndex);
                        }
                    }
                });
            }
        },
        {
            key: "handleTravellerMoveKeyboard",
            value: function handleTravellerMoveKeyboard(direction, id) {
                var _this2 = this;
                // scaleValues are a list of coordinates. For example: [65, 250, 435, 620, 805, 990].
                var _this$state3 = this.state, scaleValues = _this$state3.scaleValues, startX = _this$state3.startX, endX = _this$state3.endX;
                // currentScaleValue refers to which coordinate the current traveller should be placed at.
                var currentScaleValue = this.state[id];
                var currentIndex = scaleValues.indexOf(currentScaleValue);
                if (currentIndex === -1) {
                    return;
                }
                var newIndex = currentIndex + direction;
                if (newIndex === -1 || newIndex >= scaleValues.length) {
                    return;
                }
                var newScaleValue = scaleValues[newIndex];
                // Prevent travellers from being on top of each other or overlapping
                if (id === 'startX' && newScaleValue >= endX || id === 'endX' && newScaleValue <= startX) {
                    return;
                }
                this.setState(_defineProperty({}, id, newScaleValue), function() {
                    _this2.props.onChange(_this2.getIndex({
                        startX: _this2.state.startX,
                        endX: _this2.state.endX
                    }));
                });
            }
        },
        {
            key: "renderBackground",
            value: function renderBackground() {
                var _this$props6 = this.props, x = _this$props6.x, y = _this$props6.y, width = _this$props6.width, height = _this$props6.height, fill = _this$props6.fill, stroke = _this$props6.stroke;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                    stroke: stroke,
                    fill: fill,
                    x: x,
                    y: y,
                    width: width,
                    height: height
                });
            }
        },
        {
            key: "renderPanorama",
            value: function renderPanorama() {
                var _this$props7 = this.props, x = _this$props7.x, y = _this$props7.y, width = _this$props7.width, height = _this$props7.height, data = _this$props7.data, children = _this$props7.children, padding = _this$props7.padding;
                var chartElement = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Children"].only(children);
                if (!chartElement) {
                    return null;
                }
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(chartElement, {
                    x: x,
                    y: y,
                    width: width,
                    height: height,
                    margin: padding,
                    compact: true,
                    data: data
                });
            }
        },
        {
            key: "renderTravellerLayer",
            value: function renderTravellerLayer(travellerX, id) {
                var _data$startIndex, _data$endIndex, _this3 = this;
                var _this$props8 = this.props, y = _this$props8.y, travellerWidth = _this$props8.travellerWidth, height = _this$props8.height, traveller = _this$props8.traveller, ariaLabel = _this$props8.ariaLabel, data = _this$props8.data, startIndex = _this$props8.startIndex, endIndex = _this$props8.endIndex;
                var x = Math.max(travellerX, this.props.x);
                var travellerProps = _objectSpread(_objectSpread({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false)), {}, {
                    x: x,
                    y: y,
                    width: travellerWidth,
                    height: height
                });
                var ariaLabelBrush = ariaLabel || "Min value: ".concat((_data$startIndex = data[startIndex]) === null || _data$startIndex === void 0 ? void 0 : _data$startIndex.name, ", Max value: ").concat((_data$endIndex = data[endIndex]) === null || _data$endIndex === void 0 ? void 0 : _data$endIndex.name);
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    tabIndex: 0,
                    role: "slider",
                    "aria-label": ariaLabelBrush,
                    "aria-valuenow": travellerX,
                    className: "recharts-brush-traveller",
                    onMouseEnter: this.handleEnterSlideOrTraveller,
                    onMouseLeave: this.handleLeaveSlideOrTraveller,
                    onMouseDown: this.travellerDragStartHandlers[id],
                    onTouchStart: this.travellerDragStartHandlers[id],
                    onKeyDown: function onKeyDown(e) {
                        if (![
                            'ArrowLeft',
                            'ArrowRight'
                        ].includes(e.key)) {
                            return;
                        }
                        e.preventDefault();
                        e.stopPropagation();
                        _this3.handleTravellerMoveKeyboard(e.key === 'ArrowRight' ? 1 : -1, id);
                    },
                    onFocus: function onFocus() {
                        _this3.setState({
                            isTravellerFocused: true
                        });
                    },
                    onBlur: function onBlur() {
                        _this3.setState({
                            isTravellerFocused: false
                        });
                    },
                    style: {
                        cursor: 'col-resize'
                    }
                }, Brush.renderTraveller(traveller, travellerProps));
            }
        },
        {
            key: "renderSlide",
            value: function renderSlide(startX, endX) {
                var _this$props9 = this.props, y = _this$props9.y, height = _this$props9.height, stroke = _this$props9.stroke, travellerWidth = _this$props9.travellerWidth;
                var x = Math.min(startX, endX) + travellerWidth;
                var width = Math.max(Math.abs(endX - startX) - travellerWidth, 0);
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                    className: "recharts-brush-slide",
                    onMouseEnter: this.handleEnterSlideOrTraveller,
                    onMouseLeave: this.handleLeaveSlideOrTraveller,
                    onMouseDown: this.handleSlideDragStart,
                    onTouchStart: this.handleSlideDragStart,
                    style: {
                        cursor: 'move'
                    },
                    stroke: "none",
                    fill: stroke,
                    fillOpacity: 0.2,
                    x: x,
                    y: y,
                    width: width,
                    height: height
                });
            }
        },
        {
            key: "renderText",
            value: function renderText() {
                var _this$props10 = this.props, startIndex = _this$props10.startIndex, endIndex = _this$props10.endIndex, y = _this$props10.y, height = _this$props10.height, travellerWidth = _this$props10.travellerWidth, stroke = _this$props10.stroke;
                var _this$state4 = this.state, startX = _this$state4.startX, endX = _this$state4.endX;
                var offset = 5;
                var attrs = {
                    pointerEvents: 'none',
                    fill: stroke
                };
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: "recharts-brush-texts"
                }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Text"], _extends({
                    textAnchor: "end",
                    verticalAnchor: "middle",
                    x: Math.min(startX, endX) - offset,
                    y: y + height / 2
                }, attrs), this.getTextOfTick(startIndex)), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Text"], _extends({
                    textAnchor: "start",
                    verticalAnchor: "middle",
                    x: Math.max(startX, endX) + travellerWidth + offset,
                    y: y + height / 2
                }, attrs), this.getTextOfTick(endIndex)));
            }
        },
        {
            key: "render",
            value: function render() {
                var _this$props11 = this.props, data = _this$props11.data, className = _this$props11.className, children = _this$props11.children, x = _this$props11.x, y = _this$props11.y, width = _this$props11.width, height = _this$props11.height, alwaysShowText = _this$props11.alwaysShowText;
                var _this$state5 = this.state, startX = _this$state5.startX, endX = _this$state5.endX, isTextActive = _this$state5.isTextActive, isSlideMoving = _this$state5.isSlideMoving, isTravellerMoving = _this$state5.isTravellerMoving, isTravellerFocused = _this$state5.isTravellerFocused;
                if (!data || !data.length || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(x) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(y) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(width) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(height) || width <= 0 || height <= 0) {
                    return null;
                }
                var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-brush', className);
                var isPanoramic = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Children.count(children) === 1;
                var style = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CssPrefixUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["generatePrefixStyle"])('userSelect', 'none');
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: layerClass,
                    onMouseLeave: this.handleLeaveWrapper,
                    onTouchMove: this.handleTouchMove,
                    style: style
                }, this.renderBackground(), isPanoramic && this.renderPanorama(), this.renderSlide(startX, endX), this.renderTravellerLayer(startX, 'startX'), this.renderTravellerLayer(endX, 'endX'), (isTextActive || isSlideMoving || isTravellerMoving || isTravellerFocused || alwaysShowText) && this.renderText());
            }
        }
    ], [
        {
            key: "renderDefaultTraveller",
            value: function renderDefaultTraveller(props) {
                var x = props.x, y = props.y, width = props.width, height = props.height, stroke = props.stroke;
                var lineY = Math.floor(y + height / 2) - 1;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                    x: x,
                    y: y,
                    width: width,
                    height: height,
                    fill: stroke,
                    stroke: "none"
                }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", {
                    x1: x + 1,
                    y1: lineY,
                    x2: x + width - 1,
                    y2: lineY,
                    fill: "none",
                    stroke: "#fff"
                }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", {
                    x1: x + 1,
                    y1: lineY + 2,
                    x2: x + width - 1,
                    y2: lineY + 2,
                    fill: "none",
                    stroke: "#fff"
                }));
            }
        },
        {
            key: "renderTraveller",
            value: function renderTraveller(option, props) {
                var rectangle;
                if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
                    rectangle = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, props);
                } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
                    rectangle = option(props);
                } else {
                    rectangle = Brush.renderDefaultTraveller(props);
                }
                return rectangle;
            }
        },
        {
            key: "getDerivedStateFromProps",
            value: function getDerivedStateFromProps(nextProps, prevState) {
                var data = nextProps.data, width = nextProps.width, x = nextProps.x, travellerWidth = nextProps.travellerWidth, updateId = nextProps.updateId, startIndex = nextProps.startIndex, endIndex = nextProps.endIndex;
                if (data !== prevState.prevData || updateId !== prevState.prevUpdateId) {
                    return _objectSpread({
                        prevData: data,
                        prevTravellerWidth: travellerWidth,
                        prevUpdateId: updateId,
                        prevX: x,
                        prevWidth: width
                    }, data && data.length ? createScale({
                        data: data,
                        width: width,
                        x: x,
                        travellerWidth: travellerWidth,
                        startIndex: startIndex,
                        endIndex: endIndex
                    }) : {
                        scale: null,
                        scaleValues: null
                    });
                }
                if (prevState.scale && (width !== prevState.prevWidth || x !== prevState.prevX || travellerWidth !== prevState.prevTravellerWidth)) {
                    prevState.scale.range([
                        x,
                        x + width - travellerWidth
                    ]);
                    var scaleValues = prevState.scale.domain().map(function(entry) {
                        return prevState.scale(entry);
                    });
                    return {
                        prevData: data,
                        prevTravellerWidth: travellerWidth,
                        prevUpdateId: updateId,
                        prevX: x,
                        prevWidth: width,
                        startX: prevState.scale(nextProps.startIndex),
                        endX: prevState.scale(nextProps.endIndex),
                        scaleValues: scaleValues
                    };
                }
                return null;
            }
        },
        {
            key: "getIndexInRange",
            value: function getIndexInRange(valueRange, x) {
                var len = valueRange.length;
                var start = 0;
                var end = len - 1;
                while(end - start > 1){
                    var middle = Math.floor((start + end) / 2);
                    if (valueRange[middle] > x) {
                        end = middle;
                    } else {
                        start = middle;
                    }
                }
                return x >= valueRange[end] ? end : start;
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
_defineProperty(Brush, "displayName", 'Brush');
_defineProperty(Brush, "defaultProps", {
    height: 40,
    travellerWidth: 5,
    gap: 1,
    fill: '#fff',
    stroke: '#666',
    padding: {
        top: 1,
        right: 1,
        bottom: 1,
        left: 1
    },
    leaveTimeOut: 1000,
    alwaysShowText: false
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/PolarUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "RADIAN",
    ()=>RADIAN,
    "degreeToRadian",
    ()=>degreeToRadian,
    "distanceBetweenPoints",
    ()=>distanceBetweenPoints,
    "formatAngleOfSector",
    ()=>formatAngleOfSector,
    "formatAxisMap",
    ()=>formatAxisMap,
    "getAngleOfPoint",
    ()=>getAngleOfPoint,
    "getMaxRadius",
    ()=>getMaxRadius,
    "getTickClassName",
    ()=>getTickClassName,
    "inRangeOfSector",
    ()=>inRangeOfSector,
    "polarToCartesian",
    ()=>polarToCartesian,
    "radianToDegree",
    ()=>radianToDegree
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
;
;
;
;
;
var RADIAN = Math.PI / 180;
var degreeToRadian = function degreeToRadian(angle) {
    return angle * Math.PI / 180;
};
var radianToDegree = function radianToDegree(angleInRadian) {
    return angleInRadian * 180 / Math.PI;
};
var polarToCartesian = function polarToCartesian(cx, cy, radius, angle) {
    return {
        x: cx + Math.cos(-RADIAN * angle) * radius,
        y: cy + Math.sin(-RADIAN * angle) * radius
    };
};
var getMaxRadius = function getMaxRadius(width, height) {
    var offset = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {
        top: 0,
        right: 0,
        bottom: 0,
        left: 0
    };
    return Math.min(Math.abs(width - (offset.left || 0) - (offset.right || 0)), Math.abs(height - (offset.top || 0) - (offset.bottom || 0))) / 2;
};
var formatAxisMap = function formatAxisMap(props, axisMap, offset, axisType, chartName) {
    var width = props.width, height = props.height;
    var startAngle = props.startAngle, endAngle = props.endAngle;
    var cx = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(props.cx, width, width / 2);
    var cy = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(props.cy, height, height / 2);
    var maxRadius = getMaxRadius(width, height, offset);
    var innerRadius = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(props.innerRadius, maxRadius, 0);
    var outerRadius = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(props.outerRadius, maxRadius, maxRadius * 0.8);
    var ids = Object.keys(axisMap);
    return ids.reduce(function(result, id) {
        var axis = axisMap[id];
        var domain = axis.domain, reversed = axis.reversed;
        var range;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(axis.range)) {
            if (axisType === 'angleAxis') {
                range = [
                    startAngle,
                    endAngle
                ];
            } else if (axisType === 'radiusAxis') {
                range = [
                    innerRadius,
                    outerRadius
                ];
            }
            if (reversed) {
                range = [
                    range[1],
                    range[0]
                ];
            }
        } else {
            range = axis.range;
            var _range = range;
            var _range2 = _slicedToArray(_range, 2);
            startAngle = _range2[0];
            endAngle = _range2[1];
        }
        var _parseScale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseScale"])(axis, chartName), realScaleType = _parseScale.realScaleType, scale = _parseScale.scale;
        scale.domain(domain).range(range);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["checkDomainOfScale"])(scale);
        var ticks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfScale"])(scale, _objectSpread(_objectSpread({}, axis), {}, {
            realScaleType: realScaleType
        }));
        var finalAxis = _objectSpread(_objectSpread(_objectSpread({}, axis), ticks), {}, {
            range: range,
            radius: outerRadius,
            realScaleType: realScaleType,
            scale: scale,
            cx: cx,
            cy: cy,
            innerRadius: innerRadius,
            outerRadius: outerRadius,
            startAngle: startAngle,
            endAngle: endAngle
        });
        return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, id, finalAxis));
    }, {});
};
var distanceBetweenPoints = function distanceBetweenPoints(point, anotherPoint) {
    var x1 = point.x, y1 = point.y;
    var x2 = anotherPoint.x, y2 = anotherPoint.y;
    return Math.sqrt(Math.pow(x1 - x2, 2) + Math.pow(y1 - y2, 2));
};
var getAngleOfPoint = function getAngleOfPoint(_ref, _ref2) {
    var x = _ref.x, y = _ref.y;
    var cx = _ref2.cx, cy = _ref2.cy;
    var radius = distanceBetweenPoints({
        x: x,
        y: y
    }, {
        x: cx,
        y: cy
    });
    if (radius <= 0) {
        return {
            radius: radius
        };
    }
    var cos = (x - cx) / radius;
    var angleInRadian = Math.acos(cos);
    if (y > cy) {
        angleInRadian = 2 * Math.PI - angleInRadian;
    }
    return {
        radius: radius,
        angle: radianToDegree(angleInRadian),
        angleInRadian: angleInRadian
    };
};
var formatAngleOfSector = function formatAngleOfSector(_ref3) {
    var startAngle = _ref3.startAngle, endAngle = _ref3.endAngle;
    var startCnt = Math.floor(startAngle / 360);
    var endCnt = Math.floor(endAngle / 360);
    var min = Math.min(startCnt, endCnt);
    return {
        startAngle: startAngle - min * 360,
        endAngle: endAngle - min * 360
    };
};
var reverseFormatAngleOfSetor = function reverseFormatAngleOfSetor(angle, _ref4) {
    var startAngle = _ref4.startAngle, endAngle = _ref4.endAngle;
    var startCnt = Math.floor(startAngle / 360);
    var endCnt = Math.floor(endAngle / 360);
    var min = Math.min(startCnt, endCnt);
    return angle + min * 360;
};
var inRangeOfSector = function inRangeOfSector(_ref5, sector) {
    var x = _ref5.x, y = _ref5.y;
    var _getAngleOfPoint = getAngleOfPoint({
        x: x,
        y: y
    }, sector), radius = _getAngleOfPoint.radius, angle = _getAngleOfPoint.angle;
    var innerRadius = sector.innerRadius, outerRadius = sector.outerRadius;
    if (radius < innerRadius || radius > outerRadius) {
        return false;
    }
    if (radius === 0) {
        return true;
    }
    var _formatAngleOfSector = formatAngleOfSector(sector), startAngle = _formatAngleOfSector.startAngle, endAngle = _formatAngleOfSector.endAngle;
    var formatAngle = angle;
    var inRange;
    if (startAngle <= endAngle) {
        while(formatAngle > endAngle){
            formatAngle -= 360;
        }
        while(formatAngle < startAngle){
            formatAngle += 360;
        }
        inRange = formatAngle >= startAngle && formatAngle <= endAngle;
    } else {
        while(formatAngle > startAngle){
            formatAngle -= 360;
        }
        while(formatAngle < endAngle){
            formatAngle += 360;
        }
        inRange = formatAngle >= endAngle && formatAngle <= startAngle;
    }
    if (inRange) {
        return _objectSpread(_objectSpread({}, sector), {}, {
            radius: radius,
            angle: reverseFormatAngleOfSetor(formatAngle, sector)
        });
    }
    return null;
};
var getTickClassName = function getTickClassName(tick) {
    return !/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(tick) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tick) && typeof tick !== 'boolean' ? tick.className : '';
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Label.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Label",
    ()=>Label
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Text.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/PolarUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
var _excluded = [
    "offset"
];
function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread();
}
function _nonIterableSpread() {
    throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _iterableToArray(iter) {
    if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter);
}
function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) return _arrayLikeToArray(arr);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
;
;
;
;
;
;
;
;
;
var getLabel = function getLabel(props) {
    var value = props.value, formatter = props.formatter;
    var label = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(props.children) ? value : props.children;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(formatter)) {
        return formatter(label);
    }
    return label;
};
var getDeltaAngle = function getDeltaAngle(startAngle, endAngle) {
    var sign = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(endAngle - startAngle);
    var deltaAngle = Math.min(Math.abs(endAngle - startAngle), 360);
    return sign * deltaAngle;
};
var renderRadialLabel = function renderRadialLabel(labelProps, label, attrs) {
    var position = labelProps.position, viewBox = labelProps.viewBox, offset = labelProps.offset, className = labelProps.className;
    var _ref = viewBox, cx = _ref.cx, cy = _ref.cy, innerRadius = _ref.innerRadius, outerRadius = _ref.outerRadius, startAngle = _ref.startAngle, endAngle = _ref.endAngle, clockWise = _ref.clockWise;
    var radius = (innerRadius + outerRadius) / 2;
    var deltaAngle = getDeltaAngle(startAngle, endAngle);
    var sign = deltaAngle >= 0 ? 1 : -1;
    var labelAngle, direction;
    if (position === 'insideStart') {
        labelAngle = startAngle + sign * offset;
        direction = clockWise;
    } else if (position === 'insideEnd') {
        labelAngle = endAngle - sign * offset;
        direction = !clockWise;
    } else if (position === 'end') {
        labelAngle = endAngle + sign * offset;
        direction = clockWise;
    }
    direction = deltaAngle <= 0 ? direction : !direction;
    var startPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, radius, labelAngle);
    var endPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, radius, labelAngle + (direction ? 1 : -1) * 359);
    var path = "M".concat(startPoint.x, ",").concat(startPoint.y, "\n    A").concat(radius, ",").concat(radius, ",0,1,").concat(direction ? 0 : 1, ",\n    ").concat(endPoint.x, ",").concat(endPoint.y);
    var id = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(labelProps.id) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["uniqueId"])('recharts-radial-line-') : labelProps.id;
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("text", _extends({}, attrs, {
        dominantBaseline: "central",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-radial-bar-label', className)
    }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("defs", null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", {
        id: id,
        d: path
    })), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("textPath", {
        xlinkHref: "#".concat(id)
    }, label));
};
var getAttrsOfPolarLabel = function getAttrsOfPolarLabel(props) {
    var viewBox = props.viewBox, offset = props.offset, position = props.position;
    var _ref2 = viewBox, cx = _ref2.cx, cy = _ref2.cy, innerRadius = _ref2.innerRadius, outerRadius = _ref2.outerRadius, startAngle = _ref2.startAngle, endAngle = _ref2.endAngle;
    var midAngle = (startAngle + endAngle) / 2;
    if (position === 'outside') {
        var _polarToCartesian = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, outerRadius + offset, midAngle), _x = _polarToCartesian.x, _y = _polarToCartesian.y;
        return {
            x: _x,
            y: _y,
            textAnchor: _x >= cx ? 'start' : 'end',
            verticalAnchor: 'middle'
        };
    }
    if (position === 'center') {
        return {
            x: cx,
            y: cy,
            textAnchor: 'middle',
            verticalAnchor: 'middle'
        };
    }
    if (position === 'centerTop') {
        return {
            x: cx,
            y: cy,
            textAnchor: 'middle',
            verticalAnchor: 'start'
        };
    }
    if (position === 'centerBottom') {
        return {
            x: cx,
            y: cy,
            textAnchor: 'middle',
            verticalAnchor: 'end'
        };
    }
    var r = (innerRadius + outerRadius) / 2;
    var _polarToCartesian2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, r, midAngle), x = _polarToCartesian2.x, y = _polarToCartesian2.y;
    return {
        x: x,
        y: y,
        textAnchor: 'middle',
        verticalAnchor: 'middle'
    };
};
var getAttrsOfCartesianLabel = function getAttrsOfCartesianLabel(props) {
    var viewBox = props.viewBox, parentViewBox = props.parentViewBox, offset = props.offset, position = props.position;
    var _ref3 = viewBox, x = _ref3.x, y = _ref3.y, width = _ref3.width, height = _ref3.height;
    // Define vertical offsets and position inverts based on the value being positive or negative
    var verticalSign = height >= 0 ? 1 : -1;
    var verticalOffset = verticalSign * offset;
    var verticalEnd = verticalSign > 0 ? 'end' : 'start';
    var verticalStart = verticalSign > 0 ? 'start' : 'end';
    // Define horizontal offsets and position inverts based on the value being positive or negative
    var horizontalSign = width >= 0 ? 1 : -1;
    var horizontalOffset = horizontalSign * offset;
    var horizontalEnd = horizontalSign > 0 ? 'end' : 'start';
    var horizontalStart = horizontalSign > 0 ? 'start' : 'end';
    if (position === 'top') {
        var attrs = {
            x: x + width / 2,
            y: y - verticalSign * offset,
            textAnchor: 'middle',
            verticalAnchor: verticalEnd
        };
        return _objectSpread(_objectSpread({}, attrs), parentViewBox ? {
            height: Math.max(y - parentViewBox.y, 0),
            width: width
        } : {});
    }
    if (position === 'bottom') {
        var _attrs = {
            x: x + width / 2,
            y: y + height + verticalOffset,
            textAnchor: 'middle',
            verticalAnchor: verticalStart
        };
        return _objectSpread(_objectSpread({}, _attrs), parentViewBox ? {
            height: Math.max(parentViewBox.y + parentViewBox.height - (y + height), 0),
            width: width
        } : {});
    }
    if (position === 'left') {
        var _attrs2 = {
            x: x - horizontalOffset,
            y: y + height / 2,
            textAnchor: horizontalEnd,
            verticalAnchor: 'middle'
        };
        return _objectSpread(_objectSpread({}, _attrs2), parentViewBox ? {
            width: Math.max(_attrs2.x - parentViewBox.x, 0),
            height: height
        } : {});
    }
    if (position === 'right') {
        var _attrs3 = {
            x: x + width + horizontalOffset,
            y: y + height / 2,
            textAnchor: horizontalStart,
            verticalAnchor: 'middle'
        };
        return _objectSpread(_objectSpread({}, _attrs3), parentViewBox ? {
            width: Math.max(parentViewBox.x + parentViewBox.width - _attrs3.x, 0),
            height: height
        } : {});
    }
    var sizeAttrs = parentViewBox ? {
        width: width,
        height: height
    } : {};
    if (position === 'insideLeft') {
        return _objectSpread({
            x: x + horizontalOffset,
            y: y + height / 2,
            textAnchor: horizontalStart,
            verticalAnchor: 'middle'
        }, sizeAttrs);
    }
    if (position === 'insideRight') {
        return _objectSpread({
            x: x + width - horizontalOffset,
            y: y + height / 2,
            textAnchor: horizontalEnd,
            verticalAnchor: 'middle'
        }, sizeAttrs);
    }
    if (position === 'insideTop') {
        return _objectSpread({
            x: x + width / 2,
            y: y + verticalOffset,
            textAnchor: 'middle',
            verticalAnchor: verticalStart
        }, sizeAttrs);
    }
    if (position === 'insideBottom') {
        return _objectSpread({
            x: x + width / 2,
            y: y + height - verticalOffset,
            textAnchor: 'middle',
            verticalAnchor: verticalEnd
        }, sizeAttrs);
    }
    if (position === 'insideTopLeft') {
        return _objectSpread({
            x: x + horizontalOffset,
            y: y + verticalOffset,
            textAnchor: horizontalStart,
            verticalAnchor: verticalStart
        }, sizeAttrs);
    }
    if (position === 'insideTopRight') {
        return _objectSpread({
            x: x + width - horizontalOffset,
            y: y + verticalOffset,
            textAnchor: horizontalEnd,
            verticalAnchor: verticalStart
        }, sizeAttrs);
    }
    if (position === 'insideBottomLeft') {
        return _objectSpread({
            x: x + horizontalOffset,
            y: y + height - verticalOffset,
            textAnchor: horizontalStart,
            verticalAnchor: verticalEnd
        }, sizeAttrs);
    }
    if (position === 'insideBottomRight') {
        return _objectSpread({
            x: x + width - horizontalOffset,
            y: y + height - verticalOffset,
            textAnchor: horizontalEnd,
            verticalAnchor: verticalEnd
        }, sizeAttrs);
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(position) && ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(position.x) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPercent"])(position.x)) && ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(position.y) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPercent"])(position.y))) {
        return _objectSpread({
            x: x + (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(position.x, width),
            y: y + (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(position.y, height),
            textAnchor: 'end',
            verticalAnchor: 'end'
        }, sizeAttrs);
    }
    return _objectSpread({
        x: x + width / 2,
        y: y + height / 2,
        textAnchor: 'middle',
        verticalAnchor: 'middle'
    }, sizeAttrs);
};
var isPolar = function isPolar(viewBox) {
    return 'cx' in viewBox && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(viewBox.cx);
};
function Label(_ref4) {
    var _ref4$offset = _ref4.offset, offset = _ref4$offset === void 0 ? 5 : _ref4$offset, restProps = _objectWithoutProperties(_ref4, _excluded);
    var props = _objectSpread({
        offset: offset
    }, restProps);
    var viewBox = props.viewBox, position = props.position, value = props.value, children = props.children, content = props.content, _props$className = props.className, className = _props$className === void 0 ? '' : _props$className, textBreakAll = props.textBreakAll;
    if (!viewBox || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(value) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(children) && !/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(content) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(content)) {
        return null;
    }
    if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(content)) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(content, props);
    }
    var label;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(content)) {
        label = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"])(content, props);
        if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(label)) {
            return label;
        }
    } else {
        label = getLabel(props);
    }
    var isPolarLabel = isPolar(viewBox);
    var attrs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true);
    if (isPolarLabel && (position === 'insideStart' || position === 'insideEnd' || position === 'end')) {
        return renderRadialLabel(props, label, attrs);
    }
    var positionAttrs = isPolarLabel ? getAttrsOfPolarLabel(props) : getAttrsOfCartesianLabel(props);
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Text"], _extends({
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-label', className)
    }, attrs, positionAttrs, {
        breakAll: textBreakAll
    }), label);
}
Label.displayName = 'Label';
var parseViewBox = function parseViewBox(props) {
    var cx = props.cx, cy = props.cy, angle = props.angle, startAngle = props.startAngle, endAngle = props.endAngle, r = props.r, radius = props.radius, innerRadius = props.innerRadius, outerRadius = props.outerRadius, x = props.x, y = props.y, top = props.top, left = props.left, width = props.width, height = props.height, clockWise = props.clockWise, labelViewBox = props.labelViewBox;
    if (labelViewBox) {
        return labelViewBox;
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(width) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(height)) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(x) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(y)) {
            return {
                x: x,
                y: y,
                width: width,
                height: height
            };
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(top) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(left)) {
            return {
                x: top,
                y: left,
                width: width,
                height: height
            };
        }
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(x) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(y)) {
        return {
            x: x,
            y: y,
            width: 0,
            height: 0
        };
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(cx) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(cy)) {
        return {
            cx: cx,
            cy: cy,
            startAngle: startAngle || angle || 0,
            endAngle: endAngle || angle || 0,
            innerRadius: innerRadius || 0,
            outerRadius: outerRadius || radius || r || 0,
            clockWise: clockWise
        };
    }
    if (props.viewBox) {
        return props.viewBox;
    }
    return {};
};
var parseLabel = function parseLabel(label, viewBox) {
    if (!label) {
        return null;
    }
    if (label === true) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Label, {
            key: "label-implicit",
            viewBox: viewBox
        });
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(label)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Label, {
            key: "label-implicit",
            viewBox: viewBox,
            value: label
        });
    }
    if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(label)) {
        if (label.type === Label) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(label, {
                key: 'label-implicit',
                viewBox: viewBox
            });
        }
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Label, {
            key: "label-implicit",
            content: label,
            viewBox: viewBox
        });
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(label)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Label, {
            key: "label-implicit",
            content: label,
            viewBox: viewBox
        });
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(label)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Label, _extends({
            viewBox: viewBox
        }, label, {
            key: "label-implicit"
        }));
    }
    return null;
};
var renderCallByParent = function renderCallByParent(parentProps, viewBox) {
    var checkPropsLabel = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : true;
    if (!parentProps || !parentProps.children && checkPropsLabel && !parentProps.label) {
        return null;
    }
    var children = parentProps.children;
    var parentViewBox = parseViewBox(parentProps);
    var explicitChildren = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, Label).map(function(child, index) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(child, {
            viewBox: viewBox || parentViewBox,
            // eslint-disable-next-line react/no-array-index-key
            key: "label-".concat(index)
        });
    });
    if (!checkPropsLabel) {
        return explicitChildren;
    }
    var implicitLabel = parseLabel(parentProps.label, viewBox || parentViewBox);
    return [
        implicitLabel
    ].concat(_toConsumableArray(explicitChildren));
};
Label.parseViewBox = parseViewBox;
Label.renderCallByParent = renderCallByParent;
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/IfOverflowMatches.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ifOverflowMatches",
    ()=>ifOverflowMatches
]);
var ifOverflowMatches = function ifOverflowMatches(props, value) {
    var alwaysShow = props.alwaysShow;
    var ifOverflow = props.ifOverflow;
    if (alwaysShow) {
        ifOverflow = 'extendDomain';
    }
    return ifOverflow === value;
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Cell.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @fileOverview Cross
 */ __turbopack_context__.s([
    "Cell",
    ()=>Cell
]);
var Cell = function Cell(_props) {
    return null;
};
Cell.displayName = 'Cell';
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/LabelList.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LabelList",
    ()=>LabelList
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$last$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/last.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Label.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
var _excluded = [
    "valueAccessor"
], _excluded2 = [
    "data",
    "dataKey",
    "clockWise",
    "id",
    "textBreakAll"
];
function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread();
}
function _nonIterableSpread() {
    throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _iterableToArray(iter) {
    if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter);
}
function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) return _arrayLikeToArray(arr);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
;
;
;
;
;
;
var defaultAccessor = function defaultAccessor(entry) {
    return Array.isArray(entry.value) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$last$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry.value) : entry.value;
};
function LabelList(_ref) {
    var _ref$valueAccessor = _ref.valueAccessor, valueAccessor = _ref$valueAccessor === void 0 ? defaultAccessor : _ref$valueAccessor, restProps = _objectWithoutProperties(_ref, _excluded);
    var data = restProps.data, dataKey = restProps.dataKey, clockWise = restProps.clockWise, id = restProps.id, textBreakAll = restProps.textBreakAll, others = _objectWithoutProperties(restProps, _excluded2);
    if (!data || !data.length) {
        return null;
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
        className: "recharts-label-list"
    }, data.map(function(entry, index) {
        var value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(dataKey) ? valueAccessor(entry, index) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getValueByDataKey"])(entry && entry.payload, dataKey);
        var idProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(id) ? {} : {
            id: "".concat(id, "-").concat(index)
        };
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"], _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(entry, true), others, idProps, {
            parentViewBox: entry.parentViewBox,
            value: value,
            textBreakAll: textBreakAll,
            viewBox: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"].parseViewBox((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(clockWise) ? entry : _objectSpread(_objectSpread({}, entry), {}, {
                clockWise: clockWise
            })),
            key: "label-".concat(index) // eslint-disable-line react/no-array-index-key
            ,
            index: index
        }));
    }));
}
LabelList.displayName = 'LabelList';
function parseLabelList(label, data) {
    if (!label) {
        return null;
    }
    if (label === true) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(LabelList, {
            key: "labelList-implicit",
            data: data
        });
    }
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(label) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(label)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(LabelList, {
            key: "labelList-implicit",
            data: data,
            content: label
        });
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(label)) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(LabelList, _extends({
            data: data
        }, label, {
            key: "labelList-implicit"
        }));
    }
    return null;
}
function renderCallByParent(parentProps, data) {
    var checkPropsLabel = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : true;
    if (!parentProps || !parentProps.children && checkPropsLabel && !parentProps.label) {
        return null;
    }
    var children = parentProps.children;
    var explicitChildren = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, LabelList).map(function(child, index) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(child, {
            data: data,
            // eslint-disable-next-line react/no-array-index-key
            key: "labelList-".concat(index)
        });
    });
    if (!checkPropsLabel) {
        return explicitChildren;
    }
    var implicitLabelList = parseLabelList(parentProps.label, data);
    return [
        implicitLabelList
    ].concat(_toConsumableArray(explicitChildren));
}
LabelList.renderCallByParent = renderCallByParent;
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Trapezoid.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Trapezoid",
    ()=>Trapezoid
]);
/**
 * @fileOverview Rectangle
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-smooth/es6/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
var getTrapezoidPath = function getTrapezoidPath(x, y, upperWidth, lowerWidth, height) {
    var widthGap = upperWidth - lowerWidth;
    var path;
    path = "M ".concat(x, ",").concat(y);
    path += "L ".concat(x + upperWidth, ",").concat(y);
    path += "L ".concat(x + upperWidth - widthGap / 2, ",").concat(y + height);
    path += "L ".concat(x + upperWidth - widthGap / 2 - lowerWidth, ",").concat(y + height);
    path += "L ".concat(x, ",").concat(y, " Z");
    return path;
};
var defaultProps = {
    x: 0,
    y: 0,
    upperWidth: 0,
    lowerWidth: 0,
    height: 0,
    isUpdateAnimationActive: false,
    animationBegin: 0,
    animationDuration: 1500,
    animationEasing: 'ease'
};
var Trapezoid = function Trapezoid(props) {
    var trapezoidProps = _objectSpread(_objectSpread({}, defaultProps), props);
    var pathRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])();
    var _useState = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(-1), _useState2 = _slicedToArray(_useState, 2), totalLength = _useState2[0], setTotalLength = _useState2[1];
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Trapezoid.useEffect": function() {
            if (pathRef.current && pathRef.current.getTotalLength) {
                try {
                    var pathTotalLength = pathRef.current.getTotalLength();
                    if (pathTotalLength) {
                        setTotalLength(pathTotalLength);
                    }
                } catch (err) {
                // calculate total length error
                }
            }
        }
    }["Trapezoid.useEffect"], []);
    var x = trapezoidProps.x, y = trapezoidProps.y, upperWidth = trapezoidProps.upperWidth, lowerWidth = trapezoidProps.lowerWidth, height = trapezoidProps.height, className = trapezoidProps.className;
    var animationEasing = trapezoidProps.animationEasing, animationDuration = trapezoidProps.animationDuration, animationBegin = trapezoidProps.animationBegin, isUpdateAnimationActive = trapezoidProps.isUpdateAnimationActive;
    if (x !== +x || y !== +y || upperWidth !== +upperWidth || lowerWidth !== +lowerWidth || height !== +height || upperWidth === 0 && lowerWidth === 0 || height === 0) {
        return null;
    }
    var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-trapezoid', className);
    if (!isUpdateAnimationActive) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(trapezoidProps, true), {
            className: layerClass,
            d: getTrapezoidPath(x, y, upperWidth, lowerWidth, height)
        })));
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"], {
        canBegin: totalLength > 0,
        from: {
            upperWidth: 0,
            lowerWidth: 0,
            height: height,
            x: x,
            y: y
        },
        to: {
            upperWidth: upperWidth,
            lowerWidth: lowerWidth,
            height: height,
            x: x,
            y: y
        },
        duration: animationDuration,
        animationEasing: animationEasing,
        isActive: isUpdateAnimationActive
    }, function(_ref) {
        var currUpperWidth = _ref.upperWidth, currLowerWidth = _ref.lowerWidth, currHeight = _ref.height, currX = _ref.x, currY = _ref.y;
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"], {
            canBegin: totalLength > 0,
            from: "0px ".concat(totalLength === -1 ? 1 : totalLength, "px"),
            to: "".concat(totalLength, "px 0px"),
            attributeName: "strokeDasharray",
            begin: animationBegin,
            duration: animationDuration,
            easing: animationEasing
        }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(trapezoidProps, true), {
            className: layerClass,
            d: getTrapezoidPath(currX, currY, currUpperWidth, currLowerWidth, currHeight),
            ref: pathRef
        })));
    });
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Sector.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Sector",
    ()=>Sector
]);
/**
 * @fileOverview Sector
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/PolarUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
var getDeltaAngle = function getDeltaAngle(startAngle, endAngle) {
    var sign = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(endAngle - startAngle);
    var deltaAngle = Math.min(Math.abs(endAngle - startAngle), 359.999);
    return sign * deltaAngle;
};
var getTangentCircle = function getTangentCircle(_ref) {
    var cx = _ref.cx, cy = _ref.cy, radius = _ref.radius, angle = _ref.angle, sign = _ref.sign, isExternal = _ref.isExternal, cornerRadius = _ref.cornerRadius, cornerIsExternal = _ref.cornerIsExternal;
    var centerRadius = cornerRadius * (isExternal ? 1 : -1) + radius;
    var theta = Math.asin(cornerRadius / centerRadius) / __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RADIAN"];
    var centerAngle = cornerIsExternal ? angle : angle + sign * theta;
    var center = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, centerRadius, centerAngle);
    // The coordinate of point which is tangent to the circle
    var circleTangency = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, radius, centerAngle);
    // The coordinate of point which is tangent to the radius line
    var lineTangencyAngle = cornerIsExternal ? angle - sign * theta : angle;
    var lineTangency = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, centerRadius * Math.cos(theta * __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RADIAN"]), lineTangencyAngle);
    return {
        center: center,
        circleTangency: circleTangency,
        lineTangency: lineTangency,
        theta: theta
    };
};
var getSectorPath = function getSectorPath(_ref2) {
    var cx = _ref2.cx, cy = _ref2.cy, innerRadius = _ref2.innerRadius, outerRadius = _ref2.outerRadius, startAngle = _ref2.startAngle, endAngle = _ref2.endAngle;
    var angle = getDeltaAngle(startAngle, endAngle);
    // When the angle of sector equals to 360, star point and end point coincide
    var tempEndAngle = startAngle + angle;
    var outerStartPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, outerRadius, startAngle);
    var outerEndPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, outerRadius, tempEndAngle);
    var path = "M ".concat(outerStartPoint.x, ",").concat(outerStartPoint.y, "\n    A ").concat(outerRadius, ",").concat(outerRadius, ",0,\n    ").concat(+(Math.abs(angle) > 180), ",").concat(+(startAngle > tempEndAngle), ",\n    ").concat(outerEndPoint.x, ",").concat(outerEndPoint.y, "\n  ");
    if (innerRadius > 0) {
        var innerStartPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, innerRadius, startAngle);
        var innerEndPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, innerRadius, tempEndAngle);
        path += "L ".concat(innerEndPoint.x, ",").concat(innerEndPoint.y, "\n            A ").concat(innerRadius, ",").concat(innerRadius, ",0,\n            ").concat(+(Math.abs(angle) > 180), ",").concat(+(startAngle <= tempEndAngle), ",\n            ").concat(innerStartPoint.x, ",").concat(innerStartPoint.y, " Z");
    } else {
        path += "L ".concat(cx, ",").concat(cy, " Z");
    }
    return path;
};
var getSectorWithCorner = function getSectorWithCorner(_ref3) {
    var cx = _ref3.cx, cy = _ref3.cy, innerRadius = _ref3.innerRadius, outerRadius = _ref3.outerRadius, cornerRadius = _ref3.cornerRadius, forceCornerRadius = _ref3.forceCornerRadius, cornerIsExternal = _ref3.cornerIsExternal, startAngle = _ref3.startAngle, endAngle = _ref3.endAngle;
    var sign = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(endAngle - startAngle);
    var _getTangentCircle = getTangentCircle({
        cx: cx,
        cy: cy,
        radius: outerRadius,
        angle: startAngle,
        sign: sign,
        cornerRadius: cornerRadius,
        cornerIsExternal: cornerIsExternal
    }), soct = _getTangentCircle.circleTangency, solt = _getTangentCircle.lineTangency, sot = _getTangentCircle.theta;
    var _getTangentCircle2 = getTangentCircle({
        cx: cx,
        cy: cy,
        radius: outerRadius,
        angle: endAngle,
        sign: -sign,
        cornerRadius: cornerRadius,
        cornerIsExternal: cornerIsExternal
    }), eoct = _getTangentCircle2.circleTangency, eolt = _getTangentCircle2.lineTangency, eot = _getTangentCircle2.theta;
    var outerArcAngle = cornerIsExternal ? Math.abs(startAngle - endAngle) : Math.abs(startAngle - endAngle) - sot - eot;
    if (outerArcAngle < 0) {
        if (forceCornerRadius) {
            return "M ".concat(solt.x, ",").concat(solt.y, "\n        a").concat(cornerRadius, ",").concat(cornerRadius, ",0,0,1,").concat(cornerRadius * 2, ",0\n        a").concat(cornerRadius, ",").concat(cornerRadius, ",0,0,1,").concat(-cornerRadius * 2, ",0\n      ");
        }
        return getSectorPath({
            cx: cx,
            cy: cy,
            innerRadius: innerRadius,
            outerRadius: outerRadius,
            startAngle: startAngle,
            endAngle: endAngle
        });
    }
    var path = "M ".concat(solt.x, ",").concat(solt.y, "\n    A").concat(cornerRadius, ",").concat(cornerRadius, ",0,0,").concat(+(sign < 0), ",").concat(soct.x, ",").concat(soct.y, "\n    A").concat(outerRadius, ",").concat(outerRadius, ",0,").concat(+(outerArcAngle > 180), ",").concat(+(sign < 0), ",").concat(eoct.x, ",").concat(eoct.y, "\n    A").concat(cornerRadius, ",").concat(cornerRadius, ",0,0,").concat(+(sign < 0), ",").concat(eolt.x, ",").concat(eolt.y, "\n  ");
    if (innerRadius > 0) {
        var _getTangentCircle3 = getTangentCircle({
            cx: cx,
            cy: cy,
            radius: innerRadius,
            angle: startAngle,
            sign: sign,
            isExternal: true,
            cornerRadius: cornerRadius,
            cornerIsExternal: cornerIsExternal
        }), sict = _getTangentCircle3.circleTangency, silt = _getTangentCircle3.lineTangency, sit = _getTangentCircle3.theta;
        var _getTangentCircle4 = getTangentCircle({
            cx: cx,
            cy: cy,
            radius: innerRadius,
            angle: endAngle,
            sign: -sign,
            isExternal: true,
            cornerRadius: cornerRadius,
            cornerIsExternal: cornerIsExternal
        }), eict = _getTangentCircle4.circleTangency, eilt = _getTangentCircle4.lineTangency, eit = _getTangentCircle4.theta;
        var innerArcAngle = cornerIsExternal ? Math.abs(startAngle - endAngle) : Math.abs(startAngle - endAngle) - sit - eit;
        if (innerArcAngle < 0 && cornerRadius === 0) {
            return "".concat(path, "L").concat(cx, ",").concat(cy, "Z");
        }
        path += "L".concat(eilt.x, ",").concat(eilt.y, "\n      A").concat(cornerRadius, ",").concat(cornerRadius, ",0,0,").concat(+(sign < 0), ",").concat(eict.x, ",").concat(eict.y, "\n      A").concat(innerRadius, ",").concat(innerRadius, ",0,").concat(+(innerArcAngle > 180), ",").concat(+(sign > 0), ",").concat(sict.x, ",").concat(sict.y, "\n      A").concat(cornerRadius, ",").concat(cornerRadius, ",0,0,").concat(+(sign < 0), ",").concat(silt.x, ",").concat(silt.y, "Z");
    } else {
        path += "L".concat(cx, ",").concat(cy, "Z");
    }
    return path;
};
var defaultProps = {
    cx: 0,
    cy: 0,
    innerRadius: 0,
    outerRadius: 0,
    startAngle: 0,
    endAngle: 0,
    cornerRadius: 0,
    forceCornerRadius: false,
    cornerIsExternal: false
};
var Sector = function Sector(sectorProps) {
    var props = _objectSpread(_objectSpread({}, defaultProps), sectorProps);
    var cx = props.cx, cy = props.cy, innerRadius = props.innerRadius, outerRadius = props.outerRadius, cornerRadius = props.cornerRadius, forceCornerRadius = props.forceCornerRadius, cornerIsExternal = props.cornerIsExternal, startAngle = props.startAngle, endAngle = props.endAngle, className = props.className;
    if (outerRadius < innerRadius || startAngle === endAngle) {
        return null;
    }
    var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-sector', className);
    var deltaRadius = outerRadius - innerRadius;
    var cr = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(cornerRadius, deltaRadius, 0, true);
    var path;
    if (cr > 0 && Math.abs(startAngle - endAngle) < 360) {
        path = getSectorWithCorner({
            cx: cx,
            cy: cy,
            innerRadius: innerRadius,
            outerRadius: outerRadius,
            cornerRadius: Math.min(cr, deltaRadius / 2),
            forceCornerRadius: forceCornerRadius,
            cornerIsExternal: cornerIsExternal,
            startAngle: startAngle,
            endAngle: endAngle
        });
    } else {
        path = getSectorPath({
            cx: cx,
            cy: cy,
            innerRadius: innerRadius,
            outerRadius: outerRadius,
            startAngle: startAngle,
            endAngle: endAngle
        });
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true), {
        className: layerClass,
        d: path,
        role: "img"
    }));
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ActiveShapeUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Shape",
    ()=>Shape,
    "compareFunnel",
    ()=>compareFunnel,
    "comparePie",
    ()=>comparePie,
    "compareScatter",
    ()=>compareScatter,
    "getActiveShapeIndexForTooltip",
    ()=>getActiveShapeIndexForTooltip,
    "getPropsFromShapeOption",
    ()=>getPropsFromShapeOption,
    "isFunnel",
    ()=>isFunnel,
    "isPie",
    ()=>isPie,
    "isScatter",
    ()=>isScatter
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isPlainObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isPlainObject.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isBoolean$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isBoolean.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Rectangle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Trapezoid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Trapezoid.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Sector$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Sector.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Symbols$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Symbols.js [app-client] (ecmascript)");
var _excluded = [
    "option",
    "shapeType",
    "propTransformer",
    "activeClassName",
    "isActive"
];
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
/**
 * This is an abstraction for rendering a user defined prop for a customized shape in several forms.
 *
 * <Shape /> is the root and will handle taking in:
 *  - an object of svg properties
 *  - a boolean
 *  - a render prop(inline function that returns jsx)
 *  - a react element
 *
 * <ShapeSelector /> is a subcomponent of <Shape /> and used to match a component
 * to the value of props.shapeType that is passed to the root.
 *
 */ function defaultPropTransformer(option, props) {
    return _objectSpread(_objectSpread({}, props), option);
}
function isSymbolsProps(shapeType, _elementProps) {
    return shapeType === 'symbols';
}
function ShapeSelector(_ref) {
    var shapeType = _ref.shapeType, elementProps = _ref.elementProps;
    switch(shapeType){
        case 'rectangle':
            return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Rectangle"], elementProps);
        case 'trapezoid':
            return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Trapezoid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Trapezoid"], elementProps);
        case 'sector':
            return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Sector$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Sector"], elementProps);
        case 'symbols':
            if (isSymbolsProps(shapeType, elementProps)) {
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Symbols$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Symbols"], elementProps);
            }
            break;
        default:
            return null;
    }
}
function getPropsFromShapeOption(option) {
    if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(option)) {
        return option.props;
    }
    return option;
}
function Shape(_ref2) {
    var option = _ref2.option, shapeType = _ref2.shapeType, _ref2$propTransformer = _ref2.propTransformer, propTransformer = _ref2$propTransformer === void 0 ? defaultPropTransformer : _ref2$propTransformer, _ref2$activeClassName = _ref2.activeClassName, activeClassName = _ref2$activeClassName === void 0 ? 'recharts-active-shape' : _ref2$activeClassName, isActive = _ref2.isActive, props = _objectWithoutProperties(_ref2, _excluded);
    var shape;
    if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(option)) {
        shape = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(option, _objectSpread(_objectSpread({}, props), getPropsFromShapeOption(option)));
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        shape = option(props);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isPlainObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isBoolean$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        var nextProps = propTransformer(option, props);
        shape = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ShapeSelector, {
            shapeType: shapeType,
            elementProps: nextProps
        });
    } else {
        var elementProps = props;
        shape = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ShapeSelector, {
            shapeType: shapeType,
            elementProps: elementProps
        });
    }
    if (isActive) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
            className: activeClassName
        }, shape);
    }
    return shape;
}
function isFunnel(graphicalItem, _item) {
    return _item != null && 'trapezoids' in graphicalItem.props;
}
function isPie(graphicalItem, _item) {
    return _item != null && 'sectors' in graphicalItem.props;
}
function isScatter(graphicalItem, _item) {
    return _item != null && 'points' in graphicalItem.props;
}
function compareFunnel(shapeData, activeTooltipItem) {
    var _activeTooltipItem$la, _activeTooltipItem$la2;
    var xMatches = shapeData.x === (activeTooltipItem === null || activeTooltipItem === void 0 || (_activeTooltipItem$la = activeTooltipItem.labelViewBox) === null || _activeTooltipItem$la === void 0 ? void 0 : _activeTooltipItem$la.x) || shapeData.x === activeTooltipItem.x;
    var yMatches = shapeData.y === (activeTooltipItem === null || activeTooltipItem === void 0 || (_activeTooltipItem$la2 = activeTooltipItem.labelViewBox) === null || _activeTooltipItem$la2 === void 0 ? void 0 : _activeTooltipItem$la2.y) || shapeData.y === activeTooltipItem.y;
    return xMatches && yMatches;
}
function comparePie(shapeData, activeTooltipItem) {
    var startAngleMatches = shapeData.endAngle === activeTooltipItem.endAngle;
    var endAngleMatches = shapeData.startAngle === activeTooltipItem.startAngle;
    return startAngleMatches && endAngleMatches;
}
function compareScatter(shapeData, activeTooltipItem) {
    var xMatches = shapeData.x === activeTooltipItem.x;
    var yMatches = shapeData.y === activeTooltipItem.y;
    var zMatches = shapeData.z === activeTooltipItem.z;
    return xMatches && yMatches && zMatches;
}
function getComparisonFn(graphicalItem, activeItem) {
    var comparison;
    if (isFunnel(graphicalItem, activeItem)) {
        comparison = compareFunnel;
    } else if (isPie(graphicalItem, activeItem)) {
        comparison = comparePie;
    } else if (isScatter(graphicalItem, activeItem)) {
        comparison = compareScatter;
    }
    return comparison;
}
function getShapeDataKey(graphicalItem, activeItem) {
    var shapeKey;
    if (isFunnel(graphicalItem, activeItem)) {
        shapeKey = 'trapezoids';
    } else if (isPie(graphicalItem, activeItem)) {
        shapeKey = 'sectors';
    } else if (isScatter(graphicalItem, activeItem)) {
        shapeKey = 'points';
    }
    return shapeKey;
}
function getActiveShapeTooltipPayload(graphicalItem, activeItem) {
    if (isFunnel(graphicalItem, activeItem)) {
        var _activeItem$tooltipPa;
        return (_activeItem$tooltipPa = activeItem.tooltipPayload) === null || _activeItem$tooltipPa === void 0 || (_activeItem$tooltipPa = _activeItem$tooltipPa[0]) === null || _activeItem$tooltipPa === void 0 || (_activeItem$tooltipPa = _activeItem$tooltipPa.payload) === null || _activeItem$tooltipPa === void 0 ? void 0 : _activeItem$tooltipPa.payload;
    }
    if (isPie(graphicalItem, activeItem)) {
        var _activeItem$tooltipPa2;
        return (_activeItem$tooltipPa2 = activeItem.tooltipPayload) === null || _activeItem$tooltipPa2 === void 0 || (_activeItem$tooltipPa2 = _activeItem$tooltipPa2[0]) === null || _activeItem$tooltipPa2 === void 0 || (_activeItem$tooltipPa2 = _activeItem$tooltipPa2.payload) === null || _activeItem$tooltipPa2 === void 0 ? void 0 : _activeItem$tooltipPa2.payload;
    }
    if (isScatter(graphicalItem, activeItem)) {
        return activeItem.payload;
    }
    return {};
}
function getActiveShapeIndexForTooltip(_ref3) {
    var activeTooltipItem = _ref3.activeTooltipItem, graphicalItem = _ref3.graphicalItem, itemData = _ref3.itemData;
    var shapeKey = getShapeDataKey(graphicalItem, activeTooltipItem);
    var tooltipPayload = getActiveShapeTooltipPayload(graphicalItem, activeTooltipItem);
    var activeItemMatches = itemData.filter(function(datum, dataIndex) {
        var valuesMatch = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tooltipPayload, datum);
        var mouseCoordinateMatches = graphicalItem.props[shapeKey].filter(function(shapeData) {
            var comparison = getComparisonFn(graphicalItem, activeTooltipItem);
            return comparison(shapeData, activeTooltipItem);
        });
        // get the last index in case of multiple matches
        var indexOfMouseCoordinates = graphicalItem.props[shapeKey].indexOf(mouseCoordinateMatches[mouseCoordinateMatches.length - 1]);
        var coordinatesMatch = dataIndex === indexOfMouseCoordinates;
        return valuesMatch && coordinatesMatch;
    });
    // get the last index in case of multiple matches
    var activeIndex = itemData.indexOf(activeItemMatches[activeItemMatches.length - 1]);
    return activeIndex;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/BarUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "BarRectangle",
    ()=>BarRectangle,
    "minPointSizeCallback",
    ()=>minPointSizeCallback
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/tiny-invariant/dist/esm/tiny-invariant.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ActiveShapeUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var _excluded = [
    "x",
    "y"
];
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
;
// Rectangle props is expecting x, y, height, width as numbers, name as a string, and radius as a custom type
// When props are being spread in from a user defined component in Bar,
// the prop types of an SVGElement have these typed as something else.
// This function will return the passed in props
// along with x, y, height as numbers, name as a string, and radius as number | [number, number, number, number]
function typeguardBarRectangleProps(_ref, props) {
    var xProp = _ref.x, yProp = _ref.y, option = _objectWithoutProperties(_ref, _excluded);
    var xValue = "".concat(xProp);
    var x = parseInt(xValue, 10);
    var yValue = "".concat(yProp);
    var y = parseInt(yValue, 10);
    var heightValue = "".concat(props.height || option.height);
    var height = parseInt(heightValue, 10);
    var widthValue = "".concat(props.width || option.width);
    var width = parseInt(widthValue, 10);
    return _objectSpread(_objectSpread(_objectSpread(_objectSpread(_objectSpread({}, props), option), x ? {
        x: x
    } : {}), y ? {
        y: y
    } : {}), {}, {
        height: height,
        width: width,
        name: props.name,
        radius: props.radius
    });
}
function BarRectangle(props) {
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Shape"], _extends({
        shapeType: "rectangle",
        propTransformer: typeguardBarRectangleProps,
        activeClassName: "recharts-active-bar"
    }, props));
}
var minPointSizeCallback = function minPointSizeCallback(minPointSize) {
    var defaultValue = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;
    return function(value, index) {
        if (typeof minPointSize === 'number') return minPointSize;
        var isValueNumberOrNil = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(value) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNullish"])(value);
        if (isValueNumberOrNil) {
            return minPointSize(value, index);
        }
        !isValueNumberOrNil ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, "minPointSize callback function received a value with type of ".concat(_typeof(value), ". Currently only numbers or null/undefined are supported.")) : "TURBOPACK unreachable" : void 0;
        return defaultValue;
    };
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/Bar.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Bar",
    ()=>Bar
]);
/**
 * @fileOverview Render a group of bar
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-smooth/es6/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ErrorBar$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ErrorBar.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Cell$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Cell.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$LabelList$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/LabelList.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$BarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/BarUtils.js [app-client] (ecmascript)");
var _excluded = [
    "value",
    "background"
];
var _Bar;
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
var Bar = /*#__PURE__*/ function(_PureComponent) {
    function Bar() {
        var _this;
        _classCallCheck(this, Bar);
        for(var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++){
            args[_key] = arguments[_key];
        }
        _this = _callSuper(this, Bar, [].concat(args));
        _defineProperty(_this, "state", {
            isAnimationFinished: false
        });
        _defineProperty(_this, "id", (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["uniqueId"])('recharts-bar-'));
        _defineProperty(_this, "handleAnimationEnd", function() {
            var onAnimationEnd = _this.props.onAnimationEnd;
            _this.setState({
                isAnimationFinished: true
            });
            if (onAnimationEnd) {
                onAnimationEnd();
            }
        });
        _defineProperty(_this, "handleAnimationStart", function() {
            var onAnimationStart = _this.props.onAnimationStart;
            _this.setState({
                isAnimationFinished: false
            });
            if (onAnimationStart) {
                onAnimationStart();
            }
        });
        return _this;
    }
    _inherits(Bar, _PureComponent);
    return _createClass(Bar, [
        {
            key: "renderRectanglesStatically",
            value: function renderRectanglesStatically(data) {
                var _this2 = this;
                var _this$props = this.props, shape = _this$props.shape, dataKey = _this$props.dataKey, activeIndex = _this$props.activeIndex, activeBar = _this$props.activeBar;
                var baseProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false);
                return data && data.map(function(entry, i) {
                    var isActive = i === activeIndex;
                    var option = isActive ? activeBar : shape;
                    var props = _objectSpread(_objectSpread(_objectSpread({}, baseProps), entry), {}, {
                        isActive: isActive,
                        option: option,
                        index: i,
                        dataKey: dataKey,
                        onAnimationStart: _this2.handleAnimationStart,
                        onAnimationEnd: _this2.handleAnimationEnd
                    });
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], _extends({
                        className: "recharts-bar-rectangle"
                    }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventsOfChild"])(_this2.props, entry, i), {
                        // https://github.com/recharts/recharts/issues/5415
                        // eslint-disable-next-line react/no-array-index-key
                        key: "rectangle-".concat(entry === null || entry === void 0 ? void 0 : entry.x, "-").concat(entry === null || entry === void 0 ? void 0 : entry.y, "-").concat(entry === null || entry === void 0 ? void 0 : entry.value, "-").concat(i)
                    }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$BarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BarRectangle"], props));
                });
            }
        },
        {
            key: "renderRectanglesWithAnimation",
            value: function renderRectanglesWithAnimation() {
                var _this3 = this;
                var _this$props2 = this.props, data = _this$props2.data, layout = _this$props2.layout, isAnimationActive = _this$props2.isAnimationActive, animationBegin = _this$props2.animationBegin, animationDuration = _this$props2.animationDuration, animationEasing = _this$props2.animationEasing, animationId = _this$props2.animationId;
                var prevData = this.state.prevData;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"], {
                    begin: animationBegin,
                    duration: animationDuration,
                    isActive: isAnimationActive,
                    easing: animationEasing,
                    from: {
                        t: 0
                    },
                    to: {
                        t: 1
                    },
                    key: "bar-".concat(animationId),
                    onAnimationEnd: this.handleAnimationEnd,
                    onAnimationStart: this.handleAnimationStart
                }, function(_ref) {
                    var t = _ref.t;
                    var stepData = data.map(function(entry, index) {
                        var prev = prevData && prevData[index];
                        if (prev) {
                            var interpolatorX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.x, entry.x);
                            var interpolatorY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.y, entry.y);
                            var interpolatorWidth = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.width, entry.width);
                            var interpolatorHeight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.height, entry.height);
                            return _objectSpread(_objectSpread({}, entry), {}, {
                                x: interpolatorX(t),
                                y: interpolatorY(t),
                                width: interpolatorWidth(t),
                                height: interpolatorHeight(t)
                            });
                        }
                        if (layout === 'horizontal') {
                            var _interpolatorHeight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(0, entry.height);
                            var h = _interpolatorHeight(t);
                            return _objectSpread(_objectSpread({}, entry), {}, {
                                y: entry.y + entry.height - h,
                                height: h
                            });
                        }
                        var interpolator = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(0, entry.width);
                        var w = interpolator(t);
                        return _objectSpread(_objectSpread({}, entry), {}, {
                            width: w
                        });
                    });
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], null, _this3.renderRectanglesStatically(stepData));
                });
            }
        },
        {
            key: "renderRectangles",
            value: function renderRectangles() {
                var _this$props3 = this.props, data = _this$props3.data, isAnimationActive = _this$props3.isAnimationActive;
                var prevData = this.state.prevData;
                if (isAnimationActive && data && data.length && (!prevData || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(prevData, data))) {
                    return this.renderRectanglesWithAnimation();
                }
                return this.renderRectanglesStatically(data);
            }
        },
        {
            key: "renderBackground",
            value: function renderBackground() {
                var _this4 = this;
                var _this$props4 = this.props, data = _this$props4.data, dataKey = _this$props4.dataKey, activeIndex = _this$props4.activeIndex;
                var backgroundProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props.background, false);
                return data.map(function(entry, i) {
                    var value = entry.value, background = entry.background, rest = _objectWithoutProperties(entry, _excluded);
                    if (!background) {
                        return null;
                    }
                    var props = _objectSpread(_objectSpread(_objectSpread(_objectSpread(_objectSpread({}, rest), {}, {
                        fill: '#eee'
                    }, background), backgroundProps), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventsOfChild"])(_this4.props, entry, i)), {}, {
                        onAnimationStart: _this4.handleAnimationStart,
                        onAnimationEnd: _this4.handleAnimationEnd,
                        dataKey: dataKey,
                        index: i,
                        className: 'recharts-bar-background-rectangle'
                    });
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$BarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BarRectangle"], _extends({
                        key: "background-bar-".concat(i),
                        option: _this4.props.background,
                        isActive: i === activeIndex
                    }, props));
                });
            }
        },
        {
            key: "renderErrorBar",
            value: function renderErrorBar(needClip, clipPathId) {
                if (this.props.isAnimationActive && !this.state.isAnimationFinished) {
                    return null;
                }
                var _this$props5 = this.props, data = _this$props5.data, xAxis = _this$props5.xAxis, yAxis = _this$props5.yAxis, layout = _this$props5.layout, children = _this$props5.children;
                var errorBarItems = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ErrorBar$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ErrorBar"]);
                if (!errorBarItems) {
                    return null;
                }
                var offset = layout === 'vertical' ? data[0].height / 2 : data[0].width / 2;
                var dataPointFormatter = function dataPointFormatter(dataPoint, dataKey) {
                    /**
         * if the value coming from `getComposedData` is an array then this is a stacked bar chart.
         * arr[1] represents end value of the bar since the data is in the form of [startValue, endValue].
         * */ var value = Array.isArray(dataPoint.value) ? dataPoint.value[1] : dataPoint.value;
                    return {
                        x: dataPoint.x,
                        y: dataPoint.y,
                        value: value,
                        errorVal: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getValueByDataKey"])(dataPoint, dataKey)
                    };
                };
                var errorBarProps = {
                    clipPath: needClip ? "url(#clipPath-".concat(clipPathId, ")") : null
                };
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], errorBarProps, errorBarItems.map(function(item) {
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(item, {
                        key: "error-bar-".concat(clipPathId, "-").concat(item.props.dataKey),
                        data: data,
                        xAxis: xAxis,
                        yAxis: yAxis,
                        layout: layout,
                        offset: offset,
                        dataPointFormatter: dataPointFormatter
                    });
                }));
            }
        },
        {
            key: "render",
            value: function render() {
                var _this$props6 = this.props, hide = _this$props6.hide, data = _this$props6.data, className = _this$props6.className, xAxis = _this$props6.xAxis, yAxis = _this$props6.yAxis, left = _this$props6.left, top = _this$props6.top, width = _this$props6.width, height = _this$props6.height, isAnimationActive = _this$props6.isAnimationActive, background = _this$props6.background, id = _this$props6.id;
                if (hide || !data || !data.length) {
                    return null;
                }
                var isAnimationFinished = this.state.isAnimationFinished;
                var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-bar', className);
                var needClipX = xAxis && xAxis.allowDataOverflow;
                var needClipY = yAxis && yAxis.allowDataOverflow;
                var needClip = needClipX || needClipY;
                var clipPathId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(id) ? this.id : id;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: layerClass
                }, needClipX || needClipY ? /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("defs", null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("clipPath", {
                    id: "clipPath-".concat(clipPathId)
                }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                    x: needClipX ? left : left - width / 2,
                    y: needClipY ? top : top - height / 2,
                    width: needClipX ? width : width * 2,
                    height: needClipY ? height : height * 2
                }))) : null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: "recharts-bar-rectangles",
                    clipPath: needClip ? "url(#clipPath-".concat(clipPathId, ")") : null
                }, background ? this.renderBackground() : null, this.renderRectangles()), this.renderErrorBar(needClip, clipPathId), (!isAnimationActive || isAnimationFinished) && __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$LabelList$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LabelList"].renderCallByParent(this.props, data));
            }
        }
    ], [
        {
            key: "getDerivedStateFromProps",
            value: function getDerivedStateFromProps(nextProps, prevState) {
                if (nextProps.animationId !== prevState.prevAnimationId) {
                    return {
                        prevAnimationId: nextProps.animationId,
                        curData: nextProps.data,
                        prevData: prevState.curData
                    };
                }
                if (nextProps.data !== prevState.curData) {
                    return {
                        curData: nextProps.data
                    };
                }
                return null;
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
_Bar = Bar;
_defineProperty(Bar, "displayName", 'Bar');
_defineProperty(Bar, "defaultProps", {
    xAxisId: 0,
    yAxisId: 0,
    legendType: 'rect',
    minPointSize: 0,
    hide: false,
    data: [],
    layout: 'vertical',
    activeBar: false,
    isAnimationActive: !__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Global"].isSsr,
    animationBegin: 0,
    animationDuration: 400,
    animationEasing: 'ease'
});
/**
 * Compose the data of each group
 * @param {Object} props Props for the component
 * @param {Object} item        An instance of Bar
 * @param {Array} barPosition  The offset and size of each bar
 * @param {Object} xAxis       The configuration of x-axis
 * @param {Object} yAxis       The configuration of y-axis
 * @param {Array} stackedData  The stacked data of a bar item
 * @return{Array} Composed data
 */ _defineProperty(Bar, "getComposedData", function(_ref2) {
    var props = _ref2.props, item = _ref2.item, barPosition = _ref2.barPosition, bandSize = _ref2.bandSize, xAxis = _ref2.xAxis, yAxis = _ref2.yAxis, xAxisTicks = _ref2.xAxisTicks, yAxisTicks = _ref2.yAxisTicks, stackedData = _ref2.stackedData, dataStartIndex = _ref2.dataStartIndex, displayedData = _ref2.displayedData, offset = _ref2.offset;
    var pos = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["findPositionOfBar"])(barPosition, item);
    if (!pos) {
        return null;
    }
    var layout = props.layout;
    var itemDefaultProps = item.type.defaultProps;
    var itemProps = itemDefaultProps !== undefined ? _objectSpread(_objectSpread({}, itemDefaultProps), item.props) : item.props;
    var dataKey = itemProps.dataKey, children = itemProps.children, minPointSizeProp = itemProps.minPointSize;
    var numericAxis = layout === 'horizontal' ? yAxis : xAxis;
    var stackedDomain = stackedData ? numericAxis.scale.domain() : null;
    var baseValue = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBaseValueOfBar"])({
        numericAxis: numericAxis
    });
    var cells = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Cell$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Cell"]);
    var rects = displayedData.map(function(entry, index) {
        var value, x, y, width, height, background;
        if (stackedData) {
            value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["truncateByDomain"])(stackedData[dataStartIndex + index], stackedDomain);
        } else {
            value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getValueByDataKey"])(entry, dataKey);
            if (!Array.isArray(value)) {
                value = [
                    baseValue,
                    value
                ];
            }
        }
        var minPointSize = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$BarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["minPointSizeCallback"])(minPointSizeProp, _Bar.defaultProps.minPointSize)(value[1], index);
        if (layout === 'horizontal') {
            var _ref4;
            var _ref3 = [
                yAxis.scale(value[0]),
                yAxis.scale(value[1])
            ], baseValueScale = _ref3[0], currentValueScale = _ref3[1];
            x = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCateCoordinateOfBar"])({
                axis: xAxis,
                ticks: xAxisTicks,
                bandSize: bandSize,
                offset: pos.offset,
                entry: entry,
                index: index
            });
            y = (_ref4 = currentValueScale !== null && currentValueScale !== void 0 ? currentValueScale : baseValueScale) !== null && _ref4 !== void 0 ? _ref4 : undefined;
            width = pos.size;
            var computedHeight = baseValueScale - currentValueScale;
            height = Number.isNaN(computedHeight) ? 0 : computedHeight;
            background = {
                x: x,
                y: yAxis.y,
                width: width,
                height: yAxis.height
            };
            if (Math.abs(minPointSize) > 0 && Math.abs(height) < Math.abs(minPointSize)) {
                var delta = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(height || minPointSize) * (Math.abs(minPointSize) - Math.abs(height));
                y -= delta;
                height += delta;
            }
        } else {
            var _ref5 = [
                xAxis.scale(value[0]),
                xAxis.scale(value[1])
            ], _baseValueScale = _ref5[0], _currentValueScale = _ref5[1];
            x = _baseValueScale;
            y = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCateCoordinateOfBar"])({
                axis: yAxis,
                ticks: yAxisTicks,
                bandSize: bandSize,
                offset: pos.offset,
                entry: entry,
                index: index
            });
            width = _currentValueScale - _baseValueScale;
            height = pos.size;
            background = {
                x: xAxis.x,
                y: y,
                width: xAxis.width,
                height: height
            };
            if (Math.abs(minPointSize) > 0 && Math.abs(width) < Math.abs(minPointSize)) {
                var _delta = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(width || minPointSize) * (Math.abs(minPointSize) - Math.abs(width));
                width += _delta;
            }
        }
        return _objectSpread(_objectSpread(_objectSpread({}, entry), {}, {
            x: x,
            y: y,
            width: width,
            height: height,
            value: stackedData ? value : value[1],
            payload: entry,
            background: background
        }, cells && cells[index] && cells[index].props), {}, {
            tooltipPayload: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTooltipItem"])(item, entry)
            ],
            tooltipPosition: {
                x: x + width / 2,
                y: y + height / 2
            }
        });
    });
    return _objectSpread({
        data: rects,
        layout: layout
    }, offset);
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CartesianUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ScaleHelper",
    ()=>ScaleHelper,
    "createLabeledScales",
    ()=>createLabeledScales,
    "formatAxisMap",
    ()=>formatAxisMap,
    "getAngledRectangleWidth",
    ()=>getAngledRectangleWidth,
    "normalizeAngle",
    ()=>normalizeAngle,
    "rectWithCoords",
    ()=>rectWithCoords,
    "rectWithPoints",
    ()=>rectWithPoints
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$mapValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/mapValues.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$every$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/every.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Bar$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/Bar.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
;
var formatAxisMap = function formatAxisMap(props, axisMap, offset, axisType, chartName) {
    var width = props.width, height = props.height, layout = props.layout, children = props.children;
    var ids = Object.keys(axisMap);
    var steps = {
        left: offset.left,
        leftMirror: offset.left,
        right: width - offset.right,
        rightMirror: width - offset.right,
        top: offset.top,
        topMirror: offset.top,
        bottom: height - offset.bottom,
        bottomMirror: height - offset.bottom
    };
    var hasBar = !!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Bar$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Bar"]);
    return ids.reduce(function(result, id) {
        var axis = axisMap[id];
        var orientation = axis.orientation, domain = axis.domain, _axis$padding = axis.padding, padding = _axis$padding === void 0 ? {} : _axis$padding, mirror = axis.mirror, reversed = axis.reversed;
        var offsetKey = "".concat(orientation).concat(mirror ? 'Mirror' : '');
        var calculatedPadding, range, x, y, needSpace;
        if (axis.type === 'number' && (axis.padding === 'gap' || axis.padding === 'no-gap')) {
            var diff = domain[1] - domain[0];
            var smallestDistanceBetweenValues = Infinity;
            var sortedValues = axis.categoricalDomain.sort(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["compareValues"]);
            sortedValues.forEach(function(value, index) {
                if (index > 0) {
                    smallestDistanceBetweenValues = Math.min((value || 0) - (sortedValues[index - 1] || 0), smallestDistanceBetweenValues);
                }
            });
            if (Number.isFinite(smallestDistanceBetweenValues)) {
                var smallestDistanceInPercent = smallestDistanceBetweenValues / diff;
                var rangeWidth = axis.layout === 'vertical' ? offset.height : offset.width;
                if (axis.padding === 'gap') {
                    calculatedPadding = smallestDistanceInPercent * rangeWidth / 2;
                }
                if (axis.padding === 'no-gap') {
                    var gap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPercentValue"])(props.barCategoryGap, smallestDistanceInPercent * rangeWidth);
                    var halfBand = smallestDistanceInPercent * rangeWidth / 2;
                    calculatedPadding = halfBand - gap - (halfBand - gap) / rangeWidth * gap;
                }
            }
        }
        if (axisType === 'xAxis') {
            range = [
                offset.left + (padding.left || 0) + (calculatedPadding || 0),
                offset.left + offset.width - (padding.right || 0) - (calculatedPadding || 0)
            ];
        } else if (axisType === 'yAxis') {
            range = layout === 'horizontal' ? [
                offset.top + offset.height - (padding.bottom || 0),
                offset.top + (padding.top || 0)
            ] : [
                offset.top + (padding.top || 0) + (calculatedPadding || 0),
                offset.top + offset.height - (padding.bottom || 0) - (calculatedPadding || 0)
            ];
        } else {
            range = axis.range;
        }
        if (reversed) {
            range = [
                range[1],
                range[0]
            ];
        }
        var _parseScale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseScale"])(axis, chartName, hasBar), scale = _parseScale.scale, realScaleType = _parseScale.realScaleType;
        scale.domain(domain).range(range);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["checkDomainOfScale"])(scale);
        var ticks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfScale"])(scale, _objectSpread(_objectSpread({}, axis), {}, {
            realScaleType: realScaleType
        }));
        if (axisType === 'xAxis') {
            needSpace = orientation === 'top' && !mirror || orientation === 'bottom' && mirror;
            x = offset.left;
            y = steps[offsetKey] - needSpace * axis.height;
        } else if (axisType === 'yAxis') {
            needSpace = orientation === 'left' && !mirror || orientation === 'right' && mirror;
            x = steps[offsetKey] - needSpace * axis.width;
            y = offset.top;
        }
        var finalAxis = _objectSpread(_objectSpread(_objectSpread({}, axis), ticks), {}, {
            realScaleType: realScaleType,
            x: x,
            y: y,
            scale: scale,
            width: axisType === 'xAxis' ? offset.width : axis.width,
            height: axisType === 'yAxis' ? offset.height : axis.height
        });
        finalAxis.bandSize = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBandSizeOfAxis"])(finalAxis, ticks);
        if (!axis.hide && axisType === 'xAxis') {
            steps[offsetKey] += (needSpace ? -1 : 1) * finalAxis.height;
        } else if (!axis.hide) {
            steps[offsetKey] += (needSpace ? -1 : 1) * finalAxis.width;
        }
        return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, id, finalAxis));
    }, {});
};
var rectWithPoints = function rectWithPoints(_ref, _ref2) {
    var x1 = _ref.x, y1 = _ref.y;
    var x2 = _ref2.x, y2 = _ref2.y;
    return {
        x: Math.min(x1, x2),
        y: Math.min(y1, y2),
        width: Math.abs(x2 - x1),
        height: Math.abs(y2 - y1)
    };
};
var rectWithCoords = function rectWithCoords(_ref3) {
    var x1 = _ref3.x1, y1 = _ref3.y1, x2 = _ref3.x2, y2 = _ref3.y2;
    return rectWithPoints({
        x: x1,
        y: y1
    }, {
        x: x2,
        y: y2
    });
};
var ScaleHelper = /*#__PURE__*/ function() {
    function ScaleHelper(scale) {
        _classCallCheck(this, ScaleHelper);
        this.scale = scale;
    }
    return _createClass(ScaleHelper, [
        {
            key: "domain",
            get: function get() {
                return this.scale.domain;
            }
        },
        {
            key: "range",
            get: function get() {
                return this.scale.range;
            }
        },
        {
            key: "rangeMin",
            get: function get() {
                return this.range()[0];
            }
        },
        {
            key: "rangeMax",
            get: function get() {
                return this.range()[1];
            }
        },
        {
            key: "bandwidth",
            get: function get() {
                return this.scale.bandwidth;
            }
        },
        {
            key: "apply",
            value: function apply(value) {
                var _ref4 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {}, bandAware = _ref4.bandAware, position = _ref4.position;
                if (value === undefined) {
                    return undefined;
                }
                if (position) {
                    switch(position){
                        case 'start':
                            {
                                return this.scale(value);
                            }
                        case 'middle':
                            {
                                var offset = this.bandwidth ? this.bandwidth() / 2 : 0;
                                return this.scale(value) + offset;
                            }
                        case 'end':
                            {
                                var _offset = this.bandwidth ? this.bandwidth() : 0;
                                return this.scale(value) + _offset;
                            }
                        default:
                            {
                                return this.scale(value);
                            }
                    }
                }
                if (bandAware) {
                    var _offset2 = this.bandwidth ? this.bandwidth() / 2 : 0;
                    return this.scale(value) + _offset2;
                }
                return this.scale(value);
            }
        },
        {
            key: "isInRange",
            value: function isInRange(value) {
                var range = this.range();
                var first = range[0];
                var last = range[range.length - 1];
                return first <= last ? value >= first && value <= last : value >= last && value <= first;
            }
        }
    ], [
        {
            key: "create",
            value: function create(obj) {
                return new ScaleHelper(obj);
            }
        }
    ]);
}();
_defineProperty(ScaleHelper, "EPS", 1e-4);
var createLabeledScales = function createLabeledScales(options) {
    var scales = Object.keys(options).reduce(function(res, key) {
        return _objectSpread(_objectSpread({}, res), {}, _defineProperty({}, key, ScaleHelper.create(options[key])));
    }, {});
    return _objectSpread(_objectSpread({}, scales), {}, {
        apply: function apply(coord) {
            var _ref5 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {}, bandAware = _ref5.bandAware, position = _ref5.position;
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$mapValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(coord, function(value, label) {
                return scales[label].apply(value, {
                    bandAware: bandAware,
                    position: position
                });
            });
        },
        isInRange: function isInRange(coord) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$every$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(coord, function(value, label) {
                return scales[label].isInRange(value);
            });
        }
    });
};
function normalizeAngle(angle) {
    return (angle % 180 + 180) % 180;
}
var getAngledRectangleWidth = function getAngledRectangleWidth(_ref6) {
    var width = _ref6.width, height = _ref6.height;
    var angle = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;
    // Ensure angle is >= 0 && < 180
    var normalizedAngle = normalizeAngle(angle);
    var angleRadians = normalizedAngle * Math.PI / 180;
    /* Depending on the height and width of the rectangle, we may need to use different formulas to calculate the angled
   * width. This threshold defines when each formula should kick in. */ var angleThreshold = Math.atan(height / width);
    var angledWidth = angleRadians > angleThreshold && angleRadians < Math.PI - angleThreshold ? height / Math.sin(angleRadians) : width / Math.cos(angleRadians);
    return Math.abs(angledWidth);
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ReferenceDot.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ReferenceDot",
    ()=>ReferenceDot
]);
/**
 * @fileOverview Reference Dot
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Dot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Dot.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Label.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/IfOverflowMatches.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CartesianUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
var getCoordinate = function getCoordinate(props) {
    var x = props.x, y = props.y, xAxis = props.xAxis, yAxis = props.yAxis;
    var scales = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createLabeledScales"])({
        x: xAxis.scale,
        y: yAxis.scale
    });
    var result = scales.apply({
        x: x,
        y: y
    }, {
        bandAware: true
    });
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(props, 'discard') && !scales.isInRange(result)) {
        return null;
    }
    return result;
};
var ReferenceDot = /*#__PURE__*/ function(_React$Component) {
    function ReferenceDot() {
        _classCallCheck(this, ReferenceDot);
        return _callSuper(this, ReferenceDot, arguments);
    }
    _inherits(ReferenceDot, _React$Component);
    return _createClass(ReferenceDot, [
        {
            key: "render",
            value: function render() {
                var _this$props = this.props, x = _this$props.x, y = _this$props.y, r = _this$props.r, alwaysShow = _this$props.alwaysShow, clipPathId = _this$props.clipPathId;
                var isX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(x);
                var isY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(y);
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(alwaysShow === undefined, 'The alwaysShow prop is deprecated. Please use ifOverflow="extendDomain" instead.');
                if (!isX || !isY) {
                    return null;
                }
                var coordinate = getCoordinate(this.props);
                if (!coordinate) {
                    return null;
                }
                var cx = coordinate.x, cy = coordinate.y;
                var _this$props2 = this.props, shape = _this$props2.shape, className = _this$props2.className;
                var clipPath = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(this.props, 'hidden') ? "url(#".concat(clipPathId, ")") : undefined;
                var dotProps = _objectSpread(_objectSpread({
                    clipPath: clipPath
                }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, true)), {}, {
                    cx: cx,
                    cy: cy
                });
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-reference-dot', className)
                }, ReferenceDot.renderDot(shape, dotProps), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"].renderCallByParent(this.props, {
                    x: cx - r,
                    y: cy - r,
                    width: 2 * r,
                    height: 2 * r
                }));
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Component);
_defineProperty(ReferenceDot, "displayName", 'ReferenceDot');
_defineProperty(ReferenceDot, "defaultProps", {
    isFront: false,
    ifOverflow: 'discard',
    xAxisId: 0,
    yAxisId: 0,
    r: 10,
    fill: '#fff',
    stroke: '#ccc',
    fillOpacity: 1,
    strokeWidth: 1
});
_defineProperty(ReferenceDot, "renderDot", function(option, props) {
    var dot;
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
        dot = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, props);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        dot = option(props);
    } else {
        dot = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Dot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dot"], _extends({}, props, {
            cx: props.cx,
            cy: props.cy,
            className: "recharts-reference-dot-dot"
        }));
    }
    return dot;
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/calculateViewBox.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "calculateViewBox",
    ()=>calculateViewBox
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$memoize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/memoize.js [app-client] (ecmascript)");
;
var calculateViewBox = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$memoize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(function(offset) {
    return {
        x: offset.left,
        y: offset.top,
        width: offset.width,
        height: offset.height
    };
}, function(offset) {
    return [
        'l',
        offset.left,
        't',
        offset.top,
        'w',
        offset.width,
        'h',
        offset.height
    ].join('');
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/context/chartLayoutContext.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ChartHeightContext",
    ()=>ChartHeightContext,
    "ChartLayoutContextProvider",
    ()=>ChartLayoutContextProvider,
    "ChartWidthContext",
    ()=>ChartWidthContext,
    "ClipPathIdContext",
    ()=>ClipPathIdContext,
    "OffsetContext",
    ()=>OffsetContext,
    "ViewBoxContext",
    ()=>ViewBoxContext,
    "XAxisContext",
    ()=>XAxisContext,
    "YAxisContext",
    ()=>YAxisContext,
    "useArbitraryXAxis",
    ()=>useArbitraryXAxis,
    "useArbitraryYAxis",
    ()=>useArbitraryYAxis,
    "useChartHeight",
    ()=>useChartHeight,
    "useChartWidth",
    ()=>useChartWidth,
    "useClipPathId",
    ()=>useClipPathId,
    "useOffset",
    ()=>useOffset,
    "useViewBox",
    ()=>useViewBox,
    "useXAxisOrThrow",
    ()=>useXAxisOrThrow,
    "useYAxisOrThrow",
    ()=>useYAxisOrThrow,
    "useYAxisWithFiniteDomainOrRandom",
    ()=>useYAxisWithFiniteDomainOrRandom
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/tiny-invariant/dist/esm/tiny-invariant.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$find$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/find.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$every$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/every.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$calculateViewBox$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/calculateViewBox.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
;
;
;
;
;
;
var XAxisContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(undefined);
var YAxisContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(undefined);
var ViewBoxContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(undefined);
var OffsetContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])({});
var ClipPathIdContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(undefined);
var ChartHeightContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(0);
var ChartWidthContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(0);
var ChartLayoutContextProvider = function ChartLayoutContextProvider(props) {
    var _props$state = props.state, xAxisMap = _props$state.xAxisMap, yAxisMap = _props$state.yAxisMap, offset = _props$state.offset, clipPathId = props.clipPathId, children = props.children, width = props.width, height = props.height;
    /**
   * Perhaps we should compute this property when reading? Let's see what is more often used
   */ var viewBox = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$calculateViewBox$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["calculateViewBox"])(offset);
    /*
   * This pretends to be a single context but actually is split into multiple smaller ones.
   * Why?
   * Because one React Context only allows to set one value.
   * But we need to set multiple values.
   * If we do that with one context, then we force re-render on components that might not even be interested
   * in the part of the state that has changed.
   *
   * By splitting into smaller contexts, we allow each components to be optimized and only re-render when its dependencies change.
   *
   * To actually achieve the optimal re-render, it is necessary to use React.memo().
   * See the test file for details.
   */ return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(XAxisContext.Provider, {
        value: xAxisMap
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(YAxisContext.Provider, {
        value: yAxisMap
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(OffsetContext.Provider, {
        value: offset
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ViewBoxContext.Provider, {
        value: viewBox
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ClipPathIdContext.Provider, {
        value: clipPathId
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ChartHeightContext.Provider, {
        value: height
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ChartWidthContext.Provider, {
        value: width
    }, children)))))));
};
var useClipPathId = function useClipPathId() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(ClipPathIdContext);
};
function getKeysForDebug(object) {
    var keys = Object.keys(object);
    if (keys.length === 0) {
        return 'There are no available ids.';
    }
    return "Available ids are: ".concat(keys, ".");
}
var useXAxisOrThrow = function useXAxisOrThrow(xAxisId) {
    var xAxisMap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(XAxisContext);
    !(xAxisMap != null) ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, 'Could not find Recharts context; are you sure this is rendered inside a Recharts wrapper component?') : "TURBOPACK unreachable" : void 0;
    var xAxis = xAxisMap[xAxisId];
    !(xAxis != null) ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, "Could not find xAxis by id \"".concat(xAxisId, "\" [").concat(_typeof(xAxisId), "]. ").concat(getKeysForDebug(xAxisMap))) : "TURBOPACK unreachable" : void 0;
    return xAxis;
};
var useArbitraryXAxis = function useArbitraryXAxis() {
    var xAxisMap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(XAxisContext);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(xAxisMap);
};
var useArbitraryYAxis = function useArbitraryYAxis() {
    var yAxisMap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(YAxisContext);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(yAxisMap);
};
var useYAxisWithFiniteDomainOrRandom = function useYAxisWithFiniteDomainOrRandom() {
    var yAxisMap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(YAxisContext);
    var yAxisWithFiniteDomain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$find$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(yAxisMap, function(axis) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$every$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(axis.domain, Number.isFinite);
    });
    return yAxisWithFiniteDomain || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(yAxisMap);
};
var useYAxisOrThrow = function useYAxisOrThrow(yAxisId) {
    var yAxisMap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(YAxisContext);
    !(yAxisMap != null) ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, 'Could not find Recharts context; are you sure this is rendered inside a Recharts wrapper component?') : "TURBOPACK unreachable" : void 0;
    var yAxis = yAxisMap[yAxisId];
    !(yAxis != null) ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, "Could not find yAxis by id \"".concat(yAxisId, "\" [").concat(_typeof(yAxisId), "]. ").concat(getKeysForDebug(yAxisMap))) : "TURBOPACK unreachable" : void 0;
    return yAxis;
};
var useViewBox = function useViewBox() {
    var viewBox = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(ViewBoxContext);
    return viewBox;
};
var useOffset = function useOffset() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(OffsetContext);
};
var useChartWidth = function useChartWidth() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(ChartWidthContext);
};
var useChartHeight = function useChartHeight() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(ChartHeightContext);
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ReferenceLine.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ReferenceLine",
    ()=>ReferenceLine,
    "getEndPoints",
    ()=>getEndPoints
]);
/**
 * @fileOverview Reference Line
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$some$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/some.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Label.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/IfOverflowMatches.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CartesianUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/context/chartLayoutContext.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
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
/**
 * This excludes `viewBox` prop from svg for two reasons:
 * 1. The components wants viewBox of object type, and svg wants string
 *    - so there's a conflict, and the component will throw if it gets string
 * 2. Internally the component calls `filterProps` which filters the viewBox away anyway
 */ var renderLine = function renderLine(option, props) {
    var line;
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
        line = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, props);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        line = option(props);
    } else {
        line = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", _extends({}, props, {
            className: "recharts-reference-line-line"
        }));
    }
    return line;
};
var getEndPoints = function getEndPoints(scales, isFixedX, isFixedY, isSegment, viewBox, position, xAxisOrientation, yAxisOrientation, props) {
    var x = viewBox.x, y = viewBox.y, width = viewBox.width, height = viewBox.height;
    if (isFixedY) {
        var yCoord = props.y;
        var coord = scales.y.apply(yCoord, {
            position: position
        });
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(props, 'discard') && !scales.y.isInRange(coord)) {
            return null;
        }
        var points = [
            {
                x: x + width,
                y: coord
            },
            {
                x: x,
                y: coord
            }
        ];
        return yAxisOrientation === 'left' ? points.reverse() : points;
    }
    if (isFixedX) {
        var xCoord = props.x;
        var _coord = scales.x.apply(xCoord, {
            position: position
        });
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(props, 'discard') && !scales.x.isInRange(_coord)) {
            return null;
        }
        var _points = [
            {
                x: _coord,
                y: y + height
            },
            {
                x: _coord,
                y: y
            }
        ];
        return xAxisOrientation === 'top' ? _points.reverse() : _points;
    }
    if (isSegment) {
        var segment = props.segment;
        var _points2 = segment.map(function(p) {
            return scales.apply(p, {
                position: position
            });
        });
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(props, 'discard') && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$some$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_points2, function(p) {
            return !scales.isInRange(p);
        })) {
            return null;
        }
        return _points2;
    }
    return null;
};
function ReferenceLineImpl(props) {
    var fixedX = props.x, fixedY = props.y, segment = props.segment, xAxisId = props.xAxisId, yAxisId = props.yAxisId, shape = props.shape, className = props.className, alwaysShow = props.alwaysShow;
    var clipPathId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useClipPathId"])();
    var xAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useXAxisOrThrow"])(xAxisId);
    var yAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useYAxisOrThrow"])(yAxisId);
    var viewBox = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useViewBox"])();
    if (!clipPathId || !viewBox) {
        return null;
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(alwaysShow === undefined, 'The alwaysShow prop is deprecated. Please use ifOverflow="extendDomain" instead.');
    var scales = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createLabeledScales"])({
        x: xAxis.scale,
        y: yAxis.scale
    });
    var isX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(fixedX);
    var isY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(fixedY);
    var isSegment = segment && segment.length === 2;
    var endPoints = getEndPoints(scales, isX, isY, isSegment, viewBox, props.position, xAxis.orientation, yAxis.orientation, props);
    if (!endPoints) {
        return null;
    }
    var _endPoints = _slicedToArray(endPoints, 2), _endPoints$ = _endPoints[0], x1 = _endPoints$.x, y1 = _endPoints$.y, _endPoints$2 = _endPoints[1], x2 = _endPoints$2.x, y2 = _endPoints$2.y;
    var clipPath = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(props, 'hidden') ? "url(#".concat(clipPathId, ")") : undefined;
    var lineProps = _objectSpread(_objectSpread({
        clipPath: clipPath
    }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true)), {}, {
        x1: x1,
        y1: y1,
        x2: x2,
        y2: y2
    });
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-reference-line', className)
    }, renderLine(shape, lineProps), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"].renderCallByParent(props, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectWithCoords"])({
        x1: x1,
        y1: y1,
        x2: x2,
        y2: y2
    })));
}
var ReferenceLine = /*#__PURE__*/ function(_React$Component) {
    function ReferenceLine() {
        _classCallCheck(this, ReferenceLine);
        return _callSuper(this, ReferenceLine, arguments);
    }
    _inherits(ReferenceLine, _React$Component);
    return _createClass(ReferenceLine, [
        {
            key: "render",
            value: function render() {
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(ReferenceLineImpl, this.props);
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Component);
_defineProperty(ReferenceLine, "displayName", 'ReferenceLine');
_defineProperty(ReferenceLine, "defaultProps", {
    isFront: false,
    ifOverflow: 'discard',
    xAxisId: 0,
    yAxisId: 0,
    fill: 'none',
    stroke: '#ccc',
    fillOpacity: 1,
    strokeWidth: 1,
    position: 'middle'
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ReferenceArea.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ReferenceArea",
    ()=>ReferenceArea
]);
/**
 * @fileOverview Reference Line
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Label.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CartesianUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/IfOverflowMatches.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Rectangle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
var getRect = function getRect(hasX1, hasX2, hasY1, hasY2, props) {
    var xValue1 = props.x1, xValue2 = props.x2, yValue1 = props.y1, yValue2 = props.y2, xAxis = props.xAxis, yAxis = props.yAxis;
    if (!xAxis || !yAxis) return null;
    var scales = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createLabeledScales"])({
        x: xAxis.scale,
        y: yAxis.scale
    });
    var p1 = {
        x: hasX1 ? scales.x.apply(xValue1, {
            position: 'start'
        }) : scales.x.rangeMin,
        y: hasY1 ? scales.y.apply(yValue1, {
            position: 'start'
        }) : scales.y.rangeMin
    };
    var p2 = {
        x: hasX2 ? scales.x.apply(xValue2, {
            position: 'end'
        }) : scales.x.rangeMax,
        y: hasY2 ? scales.y.apply(yValue2, {
            position: 'end'
        }) : scales.y.rangeMax
    };
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(props, 'discard') && (!scales.isInRange(p1) || !scales.isInRange(p2))) {
        return null;
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectWithPoints"])(p1, p2);
};
var ReferenceArea = /*#__PURE__*/ function(_React$Component) {
    function ReferenceArea() {
        _classCallCheck(this, ReferenceArea);
        return _callSuper(this, ReferenceArea, arguments);
    }
    _inherits(ReferenceArea, _React$Component);
    return _createClass(ReferenceArea, [
        {
            key: "render",
            value: function render() {
                var _this$props = this.props, x1 = _this$props.x1, x2 = _this$props.x2, y1 = _this$props.y1, y2 = _this$props.y2, className = _this$props.className, alwaysShow = _this$props.alwaysShow, clipPathId = _this$props.clipPathId;
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(alwaysShow === undefined, 'The alwaysShow prop is deprecated. Please use ifOverflow="extendDomain" instead.');
                var hasX1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(x1);
                var hasX2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(x2);
                var hasY1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(y1);
                var hasY2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumOrStr"])(y2);
                var shape = this.props.shape;
                if (!hasX1 && !hasX2 && !hasY1 && !hasY2 && !shape) {
                    return null;
                }
                var rect = getRect(hasX1, hasX2, hasY1, hasY2, this.props);
                if (!rect && !shape) {
                    return null;
                }
                var clipPath = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(this.props, 'hidden') ? "url(#".concat(clipPathId, ")") : undefined;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-reference-area', className)
                }, ReferenceArea.renderRect(shape, _objectSpread(_objectSpread({
                    clipPath: clipPath
                }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, true)), rect)), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"].renderCallByParent(this.props, rect));
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Component);
_defineProperty(ReferenceArea, "displayName", 'ReferenceArea');
_defineProperty(ReferenceArea, "defaultProps", {
    isFront: false,
    ifOverflow: 'discard',
    xAxisId: 0,
    yAxisId: 0,
    r: 10,
    fill: '#ccc',
    fillOpacity: 0.5,
    stroke: 'none',
    strokeWidth: 1
});
_defineProperty(ReferenceArea, "renderRect", function(option, props) {
    var rect;
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
        rect = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, props);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        rect = option(props);
    } else {
        rect = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Rectangle"], _extends({}, props, {
            className: "recharts-reference-area-rect"
        }));
    }
    return rect;
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DetectReferenceElementsDomain.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "detectReferenceElementsDomain",
    ()=>detectReferenceElementsDomain
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ReferenceDot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ReferenceDot.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ReferenceLine$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ReferenceLine.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ReferenceArea$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/ReferenceArea.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/IfOverflowMatches.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread();
}
function _nonIterableSpread() {
    throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _iterableToArray(iter) {
    if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter);
}
function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) return _arrayLikeToArray(arr);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
;
;
;
;
;
;
var detectReferenceElementsDomain = function detectReferenceElementsDomain(children, domain, axisId, axisType, specifiedTicks) {
    var lines = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ReferenceLine$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ReferenceLine"]);
    var dots = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ReferenceDot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ReferenceDot"]);
    var elements = [].concat(_toConsumableArray(lines), _toConsumableArray(dots));
    var areas = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$ReferenceArea$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ReferenceArea"]);
    var idKey = "".concat(axisType, "Id");
    var valueKey = axisType[0];
    var finalDomain = domain;
    if (elements.length) {
        finalDomain = elements.reduce(function(result, el) {
            if (el.props[idKey] === axisId && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(el.props, 'extendDomain') && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(el.props[valueKey])) {
                var value = el.props[valueKey];
                return [
                    Math.min(result[0], value),
                    Math.max(result[1], value)
                ];
            }
            return result;
        }, finalDomain);
    }
    if (areas.length) {
        var key1 = "".concat(valueKey, "1");
        var key2 = "".concat(valueKey, "2");
        finalDomain = areas.reduce(function(result, el) {
            if (el.props[idKey] === axisId && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$IfOverflowMatches$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ifOverflowMatches"])(el.props, 'extendDomain') && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(el.props[key1]) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(el.props[key2])) {
                var value1 = el.props[key1];
                var value2 = el.props[key2];
                return [
                    Math.min(result[0], value1, value2),
                    Math.max(result[1], value1, value2)
                ];
            }
            return result;
        }, finalDomain);
    }
    if (specifiedTicks && specifiedTicks.length) {
        finalDomain = specifiedTicks.reduce(function(result, tick) {
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(tick)) {
                return [
                    Math.min(result[0], tick),
                    Math.max(result[1], tick)
                ];
            }
            return result;
        }, finalDomain);
    }
    return finalDomain;
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Events.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "SYNC_EVENT",
    ()=>SYNC_EVENT,
    "eventCenter",
    ()=>eventCenter
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$node_modules$2f$eventemitter3$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/node_modules/eventemitter3/index.js [app-client] (ecmascript)");
;
var eventCenter = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$node_modules$2f$eventemitter3$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]();
;
var SYNC_EVENT = 'recharts.syncMouseEvents';
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/chart/AccessibilityManager.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "AccessibilityManager",
    ()=>AccessibilityManager
]);
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
var AccessibilityManager = /*#__PURE__*/ function() {
    function AccessibilityManager() {
        _classCallCheck(this, AccessibilityManager);
        _defineProperty(this, "activeIndex", 0);
        _defineProperty(this, "coordinateList", []);
        _defineProperty(this, "layout", 'horizontal');
    }
    return _createClass(AccessibilityManager, [
        {
            key: "setDetails",
            value: function setDetails(_ref) {
                var _ref2;
                var _ref$coordinateList = _ref.coordinateList, coordinateList = _ref$coordinateList === void 0 ? null : _ref$coordinateList, _ref$container = _ref.container, container = _ref$container === void 0 ? null : _ref$container, _ref$layout = _ref.layout, layout = _ref$layout === void 0 ? null : _ref$layout, _ref$offset = _ref.offset, offset = _ref$offset === void 0 ? null : _ref$offset, _ref$mouseHandlerCall = _ref.mouseHandlerCallback, mouseHandlerCallback = _ref$mouseHandlerCall === void 0 ? null : _ref$mouseHandlerCall;
                this.coordinateList = (_ref2 = coordinateList !== null && coordinateList !== void 0 ? coordinateList : this.coordinateList) !== null && _ref2 !== void 0 ? _ref2 : [];
                this.container = container !== null && container !== void 0 ? container : this.container;
                this.layout = layout !== null && layout !== void 0 ? layout : this.layout;
                this.offset = offset !== null && offset !== void 0 ? offset : this.offset;
                this.mouseHandlerCallback = mouseHandlerCallback !== null && mouseHandlerCallback !== void 0 ? mouseHandlerCallback : this.mouseHandlerCallback;
                // Keep activeIndex in the bounds between 0 and the last coordinate index
                this.activeIndex = Math.min(Math.max(this.activeIndex, 0), this.coordinateList.length - 1);
            }
        },
        {
            key: "focus",
            value: function focus() {
                this.spoofMouse();
            }
        },
        {
            key: "keyboardEvent",
            value: function keyboardEvent(e) {
                // The AccessibilityManager relies on the Tooltip component. When tooltips suddenly stop existing,
                // it can cause errors. We use this function to check. We don't want arrow keys to be processed
                // if there are no tooltips, since that will cause unexpected behavior of users.
                if (this.coordinateList.length === 0) {
                    return;
                }
                switch(e.key){
                    case 'ArrowRight':
                        {
                            if (this.layout !== 'horizontal') {
                                return;
                            }
                            this.activeIndex = Math.min(this.activeIndex + 1, this.coordinateList.length - 1);
                            this.spoofMouse();
                            break;
                        }
                    case 'ArrowLeft':
                        {
                            if (this.layout !== 'horizontal') {
                                return;
                            }
                            this.activeIndex = Math.max(this.activeIndex - 1, 0);
                            this.spoofMouse();
                            break;
                        }
                    default:
                        {
                            break;
                        }
                }
            }
        },
        {
            key: "setIndex",
            value: function setIndex(newIndex) {
                this.activeIndex = newIndex;
            }
        },
        {
            key: "spoofMouse",
            value: function spoofMouse() {
                var _window, _window2;
                if (this.layout !== 'horizontal') {
                    return;
                }
                // This can happen when the tooltips suddenly stop existing as children of the component
                // That update doesn't otherwise fire events, so we have to double check here.
                if (this.coordinateList.length === 0) {
                    return;
                }
                var _this$container$getBo = this.container.getBoundingClientRect(), x = _this$container$getBo.x, y = _this$container$getBo.y, height = _this$container$getBo.height;
                var coordinate = this.coordinateList[this.activeIndex].coordinate;
                var scrollOffsetX = ((_window = window) === null || _window === void 0 ? void 0 : _window.scrollX) || 0;
                var scrollOffsetY = ((_window2 = window) === null || _window2 === void 0 ? void 0 : _window2.scrollY) || 0;
                var pageX = x + coordinate + scrollOffsetX;
                var pageY = y + this.offset.top + height / 2 + scrollOffsetY;
                this.mouseHandlerCallback({
                    pageX: pageX,
                    pageY: pageY
                });
            }
        }
    ]);
}();
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/isDomainSpecifiedByUser.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isDomainSpecifiedByUser",
    ()=>isDomainSpecifiedByUser
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
;
function isDomainSpecifiedByUser(domain, allowDataOverflow, axisType) {
    if (axisType === 'number' && allowDataOverflow === true && Array.isArray(domain)) {
        var domainStart = domain === null || domain === void 0 ? void 0 : domain[0];
        var domainEnd = domain === null || domain === void 0 ? void 0 : domain[1];
        /*
     * The `isNumber` check is needed because the user could also provide strings like "dataMin" via the domain props.
     * In such case, we have to compute the domain from the data.
     */ if (!!domainStart && !!domainEnd && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(domainStart) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(domainEnd)) {
            return true;
        }
    }
    return false;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Curve.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Curve",
    ()=>Curve,
    "getPath",
    ()=>getPath
]);
/**
 * @fileOverview Curve
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$victory$2d$vendor$2f$es$2f$d3$2d$shape$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/victory-vendor/es/d3-shape.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$line$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__line$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/line.js [app-client] (ecmascript) <export default as line>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__area$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/area.js [app-client] (ecmascript) <export default as area>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$basisClosed$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveBasisClosed$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/basisClosed.js [app-client] (ecmascript) <export default as curveBasisClosed>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$basisOpen$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveBasisOpen$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/basisOpen.js [app-client] (ecmascript) <export default as curveBasisOpen>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$basis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveBasis$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/basis.js [app-client] (ecmascript) <export default as curveBasis>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$bump$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__bumpX__as__curveBumpX$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/bump.js [app-client] (ecmascript) <export bumpX as curveBumpX>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$bump$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__bumpY__as__curveBumpY$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/bump.js [app-client] (ecmascript) <export bumpY as curveBumpY>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$linearClosed$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveLinearClosed$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/linearClosed.js [app-client] (ecmascript) <export default as curveLinearClosed>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$linear$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveLinear$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/linear.js [app-client] (ecmascript) <export default as curveLinear>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$monotone$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__monotoneX__as__curveMonotoneX$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/monotone.js [app-client] (ecmascript) <export monotoneX as curveMonotoneX>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$monotone$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__monotoneY__as__curveMonotoneY$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/monotone.js [app-client] (ecmascript) <export monotoneY as curveMonotoneY>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$natural$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveNatural$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/natural.js [app-client] (ecmascript) <export default as curveNatural>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$step$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveStep$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/step.js [app-client] (ecmascript) <export default as curveStep>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$step$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__stepAfter__as__curveStepAfter$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/step.js [app-client] (ecmascript) <export stepAfter as curveStepAfter>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$step$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__stepBefore__as__curveStepBefore$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/d3-shape/src/curve/step.js [app-client] (ecmascript) <export stepBefore as curveStepBefore>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/upperFirst.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
;
;
;
var CURVE_FACTORIES = {
    curveBasisClosed: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$basisClosed$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveBasisClosed$3e$__["curveBasisClosed"],
    curveBasisOpen: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$basisOpen$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveBasisOpen$3e$__["curveBasisOpen"],
    curveBasis: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$basis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveBasis$3e$__["curveBasis"],
    curveBumpX: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$bump$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__bumpX__as__curveBumpX$3e$__["curveBumpX"],
    curveBumpY: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$bump$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__bumpY__as__curveBumpY$3e$__["curveBumpY"],
    curveLinearClosed: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$linearClosed$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveLinearClosed$3e$__["curveLinearClosed"],
    curveLinear: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$linear$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveLinear$3e$__["curveLinear"],
    curveMonotoneX: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$monotone$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__monotoneX__as__curveMonotoneX$3e$__["curveMonotoneX"],
    curveMonotoneY: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$monotone$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__monotoneY__as__curveMonotoneY$3e$__["curveMonotoneY"],
    curveNatural: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$natural$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveNatural$3e$__["curveNatural"],
    curveStep: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$step$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveStep$3e$__["curveStep"],
    curveStepAfter: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$step$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__stepAfter__as__curveStepAfter$3e$__["curveStepAfter"],
    curveStepBefore: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$step$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__stepBefore__as__curveStepBefore$3e$__["curveStepBefore"]
};
var defined = function defined(p) {
    return p.x === +p.x && p.y === +p.y;
};
var getX = function getX(p) {
    return p.x;
};
var getY = function getY(p) {
    return p.y;
};
var getCurveFactory = function getCurveFactory(type, layout) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(type)) {
        return type;
    }
    var name = "curve".concat((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$upperFirst$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(type));
    if ((name === 'curveMonotone' || name === 'curveBump') && layout) {
        return CURVE_FACTORIES["".concat(name).concat(layout === 'vertical' ? 'Y' : 'X')];
    }
    return CURVE_FACTORIES[name] || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$curve$2f$linear$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__curveLinear$3e$__["curveLinear"];
};
var getPath = function getPath(_ref) {
    var _ref$type = _ref.type, type = _ref$type === void 0 ? 'linear' : _ref$type, _ref$points = _ref.points, points = _ref$points === void 0 ? [] : _ref$points, baseLine = _ref.baseLine, layout = _ref.layout, _ref$connectNulls = _ref.connectNulls, connectNulls = _ref$connectNulls === void 0 ? false : _ref$connectNulls;
    var curveFactory = getCurveFactory(type, layout);
    var formatPoints = connectNulls ? points.filter(function(entry) {
        return defined(entry);
    }) : points;
    var lineFunction;
    if (Array.isArray(baseLine)) {
        var formatBaseLine = connectNulls ? baseLine.filter(function(base) {
            return defined(base);
        }) : baseLine;
        var areaPoints = formatPoints.map(function(entry, index) {
            return _objectSpread(_objectSpread({}, entry), {}, {
                base: formatBaseLine[index]
            });
        });
        if (layout === 'vertical') {
            lineFunction = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__area$3e$__["area"])().y(getY).x1(getX).x0(function(d) {
                return d.base.x;
            });
        } else {
            lineFunction = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__area$3e$__["area"])().x(getX).y1(getY).y0(function(d) {
                return d.base.y;
            });
        }
        lineFunction.defined(defined).curve(curveFactory);
        return lineFunction(areaPoints);
    }
    if (layout === 'vertical' && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(baseLine)) {
        lineFunction = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__area$3e$__["area"])().y(getY).x1(getX).x0(baseLine);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(baseLine)) {
        lineFunction = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__area$3e$__["area"])().x(getX).y1(getY).y0(baseLine);
    } else {
        lineFunction = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$d3$2d$shape$2f$src$2f$line$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__line$3e$__["line"])().x(getX).y(getY);
    }
    lineFunction.defined(defined).curve(curveFactory);
    return lineFunction(formatPoints);
};
var Curve = function Curve(props) {
    var className = props.className, points = props.points, path = props.path, pathRef = props.pathRef;
    if ((!points || !points.length) && !path) {
        return null;
    }
    var realPath = points && points.length ? getPath(props) : path;
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"]("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, false), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventHandlers"])(props), {
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-curve', className),
        d: realPath,
        ref: pathRef
    }));
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Cross.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Cross",
    ()=>Cross
]);
/**
 * @fileOverview Cross
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
var _excluded = [
    "x",
    "y",
    "top",
    "left",
    "width",
    "height",
    "className"
];
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
;
var getPath = function getPath(x, y, width, height, top, left) {
    return "M".concat(x, ",").concat(top, "v").concat(height, "M").concat(left, ",").concat(y, "h").concat(width);
};
var Cross = function Cross(_ref) {
    var _ref$x = _ref.x, x = _ref$x === void 0 ? 0 : _ref$x, _ref$y = _ref.y, y = _ref$y === void 0 ? 0 : _ref$y, _ref$top = _ref.top, top = _ref$top === void 0 ? 0 : _ref$top, _ref$left = _ref.left, left = _ref$left === void 0 ? 0 : _ref$left, _ref$width = _ref.width, width = _ref$width === void 0 ? 0 : _ref$width, _ref$height = _ref.height, height = _ref$height === void 0 ? 0 : _ref$height, className = _ref.className, rest = _objectWithoutProperties(_ref, _excluded);
    var props = _objectSpread({
        x: x,
        y: y,
        top: top,
        left: left,
        width: width,
        height: height
    }, rest);
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(x) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(y) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(width) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(height) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(top) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(left)) {
        return null;
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("path", _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(props, true), {
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-cross', className),
        d: getPath(x, y, width, height, top, left)
    }));
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getCursorRectangle.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getCursorRectangle",
    ()=>getCursorRectangle
]);
function getCursorRectangle(layout, activeCoordinate, offset, tooltipAxisBandSize) {
    var halfSize = tooltipAxisBandSize / 2;
    return {
        stroke: 'none',
        fill: '#ccc',
        x: layout === 'horizontal' ? activeCoordinate.x - halfSize : offset.left + 0.5,
        y: layout === 'horizontal' ? offset.top + 0.5 : activeCoordinate.y - halfSize,
        width: layout === 'horizontal' ? tooltipAxisBandSize : offset.width - 1,
        height: layout === 'horizontal' ? offset.height - 1 : tooltipAxisBandSize
    };
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getRadialCursorPoints.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getRadialCursorPoints",
    ()=>getRadialCursorPoints
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/PolarUtils.js [app-client] (ecmascript)");
;
function getRadialCursorPoints(activeCoordinate) {
    var cx = activeCoordinate.cx, cy = activeCoordinate.cy, radius = activeCoordinate.radius, startAngle = activeCoordinate.startAngle, endAngle = activeCoordinate.endAngle;
    var startPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, radius, startAngle);
    var endPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, radius, endAngle);
    return {
        points: [
            startPoint,
            endPoint
        ],
        cx: cx,
        cy: cy,
        radius: radius,
        startAngle: startAngle,
        endAngle: endAngle
    };
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getCursorPoints.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getCursorPoints",
    ()=>getCursorPoints
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/PolarUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getRadialCursorPoints$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getRadialCursorPoints.js [app-client] (ecmascript)");
;
;
function getCursorPoints(layout, activeCoordinate, offset) {
    var x1, y1, x2, y2;
    if (layout === 'horizontal') {
        x1 = activeCoordinate.x;
        x2 = x1;
        y1 = offset.top;
        y2 = offset.top + offset.height;
    } else if (layout === 'vertical') {
        y1 = activeCoordinate.y;
        y2 = y1;
        x1 = offset.left;
        x2 = offset.left + offset.width;
    } else if (activeCoordinate.cx != null && activeCoordinate.cy != null) {
        if (layout === 'centric') {
            var cx = activeCoordinate.cx, cy = activeCoordinate.cy, innerRadius = activeCoordinate.innerRadius, outerRadius = activeCoordinate.outerRadius, angle = activeCoordinate.angle;
            var innerPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, innerRadius, angle);
            var outerPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(cx, cy, outerRadius, angle);
            x1 = innerPoint.x;
            y1 = innerPoint.y;
            x2 = outerPoint.x;
            y2 = outerPoint.y;
        } else {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getRadialCursorPoints$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getRadialCursorPoints"])(activeCoordinate);
        }
    }
    return [
        {
            x: x1,
            y: y1
        },
        {
            x: x2,
            y: y2
        }
    ];
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Cursor.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Cursor",
    ()=>Cursor
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Curve.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Cross$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Cross.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getCursorRectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getCursorRectangle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Rectangle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getRadialCursorPoints$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getRadialCursorPoints.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Sector$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Sector.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getCursorPoints$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/cursor/getCursorPoints.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
function Cursor(props) {
    var _element$props$cursor, _defaultProps;
    var element = props.element, tooltipEventType = props.tooltipEventType, isActive = props.isActive, activeCoordinate = props.activeCoordinate, activePayload = props.activePayload, offset = props.offset, activeTooltipIndex = props.activeTooltipIndex, tooltipAxisBandSize = props.tooltipAxisBandSize, layout = props.layout, chartName = props.chartName;
    var elementPropsCursor = (_element$props$cursor = element.props.cursor) !== null && _element$props$cursor !== void 0 ? _element$props$cursor : (_defaultProps = element.type.defaultProps) === null || _defaultProps === void 0 ? void 0 : _defaultProps.cursor;
    if (!element || !elementPropsCursor || !isActive || !activeCoordinate || chartName !== 'ScatterChart' && tooltipEventType !== 'axis') {
        return null;
    }
    var restProps;
    var cursorComp = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Curve"];
    if (chartName === 'ScatterChart') {
        restProps = activeCoordinate;
        cursorComp = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Cross$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Cross"];
    } else if (chartName === 'BarChart') {
        restProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getCursorRectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getCursorRectangle"])(layout, activeCoordinate, offset, tooltipAxisBandSize);
        cursorComp = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Rectangle"];
    } else if (layout === 'radial') {
        var _getRadialCursorPoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getRadialCursorPoints$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getRadialCursorPoints"])(activeCoordinate), cx = _getRadialCursorPoint.cx, cy = _getRadialCursorPoint.cy, radius = _getRadialCursorPoint.radius, startAngle = _getRadialCursorPoint.startAngle, endAngle = _getRadialCursorPoint.endAngle;
        restProps = {
            cx: cx,
            cy: cy,
            startAngle: startAngle,
            endAngle: endAngle,
            innerRadius: radius,
            outerRadius: radius
        };
        cursorComp = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Sector$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Sector"];
    } else {
        restProps = {
            points: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$cursor$2f$getCursorPoints$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getCursorPoints"])(layout, activeCoordinate, offset)
        };
        cursorComp = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Curve"];
    }
    var cursorProps = _objectSpread(_objectSpread(_objectSpread(_objectSpread({
        stroke: '#ccc',
        pointerEvents: 'none'
    }, offset), restProps), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(elementPropsCursor, false)), {}, {
        payload: activePayload,
        payloadIndex: activeTooltipIndex,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-tooltip-cursor', elementPropsCursor.className)
    });
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(elementPropsCursor) ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(elementPropsCursor, cursorProps) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"])(cursorComp, cursorProps);
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/chart/generateCategoricalChart.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "createDefaultState",
    ()=>createDefaultState,
    "generateCategoricalChart",
    ()=>generateCategoricalChart,
    "getAxisMapByAxes",
    ()=>getAxisMapByAxes
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$range$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/range.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$sortBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/sortBy.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$throttle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/throttle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
// eslint-disable-next-line no-restricted-imports
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/tiny-invariant/dist/esm/tiny-invariant.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Surface$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Surface.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Tooltip.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Legend$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Legend.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Dot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Dot.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Rectangle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Brush$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/Brush.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DOMUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getLegendProps$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/getLegendProps.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DetectReferenceElementsDomain$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DetectReferenceElementsDomain.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/PolarUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ShallowEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Events.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$chart$2f$AccessibilityManager$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/chart/AccessibilityManager.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$isDomainSpecifiedByUser$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/isDomainSpecifiedByUser.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ActiveShapeUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Cursor$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Cursor.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/context/chartLayoutContext.js [app-client] (ecmascript)");
var _excluded = [
    "item"
], _excluded2 = [
    "children",
    "className",
    "width",
    "height",
    "style",
    "compact",
    "title",
    "desc"
];
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread();
}
function _nonIterableSpread() {
    throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _iterableToArray(iter) {
    if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter);
}
function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) return _arrayLikeToArray(arr);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
;
;
;
;
;
;
;
;
var ORIENT_MAP = {
    xAxis: [
        'bottom',
        'top'
    ],
    yAxis: [
        'left',
        'right'
    ]
};
var FULL_WIDTH_AND_HEIGHT = {
    width: '100%',
    height: '100%'
};
var originCoordinate = {
    x: 0,
    y: 0
};
/**
 * This function exists as a temporary workaround.
 *
 * Why? generateCategoricalChart does not render `{children}` directly;
 * instead it passes them through `renderByOrder` function which reads their handlers.
 *
 * So, this is a handler that does nothing.
 * Once we get rid of `renderByOrder` and switch to JSX only, we can get rid of this handler too.
 *
 * @param {JSX} element as is in JSX
 * @returns {JSX} the same element
 */ function renderAsIs(element) {
    return element;
}
var calculateTooltipPos = function calculateTooltipPos(rangeObj, layout) {
    if (layout === 'horizontal') {
        return rangeObj.x;
    }
    if (layout === 'vertical') {
        return rangeObj.y;
    }
    if (layout === 'centric') {
        return rangeObj.angle;
    }
    return rangeObj.radius;
};
var getActiveCoordinate = function getActiveCoordinate(layout, tooltipTicks, activeIndex, rangeObj) {
    var entry = tooltipTicks.find(function(tick) {
        return tick && tick.index === activeIndex;
    });
    if (entry) {
        if (layout === 'horizontal') {
            return {
                x: entry.coordinate,
                y: rangeObj.y
            };
        }
        if (layout === 'vertical') {
            return {
                x: rangeObj.x,
                y: entry.coordinate
            };
        }
        if (layout === 'centric') {
            var _angle = entry.coordinate;
            var _radius = rangeObj.radius;
            return _objectSpread(_objectSpread(_objectSpread({}, rangeObj), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(rangeObj.cx, rangeObj.cy, _radius, _angle)), {}, {
                angle: _angle,
                radius: _radius
            });
        }
        var radius = entry.coordinate;
        var angle = rangeObj.angle;
        return _objectSpread(_objectSpread(_objectSpread({}, rangeObj), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["polarToCartesian"])(rangeObj.cx, rangeObj.cy, radius, angle)), {}, {
            angle: angle,
            radius: radius
        });
    }
    return originCoordinate;
};
var getDisplayedData = function getDisplayedData(data, _ref) {
    var graphicalItems = _ref.graphicalItems, dataStartIndex = _ref.dataStartIndex, dataEndIndex = _ref.dataEndIndex;
    var itemsData = (graphicalItems !== null && graphicalItems !== void 0 ? graphicalItems : []).reduce(function(result, child) {
        var itemData = child.props.data;
        if (itemData && itemData.length) {
            return [].concat(_toConsumableArray(result), _toConsumableArray(itemData));
        }
        return result;
    }, []);
    if (itemsData.length > 0) {
        return itemsData;
    }
    if (data && data.length && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(dataStartIndex) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(dataEndIndex)) {
        return data.slice(dataStartIndex, dataEndIndex + 1);
    }
    return [];
};
function getDefaultDomainByAxisType(axisType) {
    return axisType === 'number' ? [
        0,
        'auto'
    ] : undefined;
}
/**
 * Get the content to be displayed in the tooltip
 * @param  {Object} state          Current state
 * @param  {Array}  chartData      The data defined in chart
 * @param  {Number} activeIndex    Active index of data
 * @param  {String} activeLabel    Active label of data
 * @return {Array}                 The content of tooltip
 */ var getTooltipContent = function getTooltipContent(state, chartData, activeIndex, activeLabel) {
    var graphicalItems = state.graphicalItems, tooltipAxis = state.tooltipAxis;
    var displayedData = getDisplayedData(chartData, state);
    if (activeIndex < 0 || !graphicalItems || !graphicalItems.length || activeIndex >= displayedData.length) {
        return null;
    }
    // get data by activeIndex when the axis don't allow duplicated category
    return graphicalItems.reduce(function(result, child) {
        var _child$props$data;
        /**
     * Fixes: https://github.com/recharts/recharts/issues/3669
     * Defaulting to chartData below to fix an edge case where the tooltip does not include data from all charts
     * when a separate dataset is passed to chart prop data and specified on Line/Area/etc prop data
     */ var data = (_child$props$data = child.props.data) !== null && _child$props$data !== void 0 ? _child$props$data : chartData;
        if (data && state.dataStartIndex + state.dataEndIndex !== 0 && // https://github.com/recharts/recharts/issues/4717
        // The data is sliced only when the active index is within the start/end index range.
        state.dataEndIndex - state.dataStartIndex >= activeIndex) {
            data = data.slice(state.dataStartIndex, state.dataEndIndex + 1);
        }
        var payload;
        if (tooltipAxis.dataKey && !tooltipAxis.allowDuplicatedCategory) {
            // graphic child has data props
            var entries = data === undefined ? displayedData : data;
            payload = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findEntryInArray"])(entries, tooltipAxis.dataKey, activeLabel);
        } else {
            payload = data && data[activeIndex] || displayedData[activeIndex];
        }
        if (!payload) {
            return result;
        }
        return [].concat(_toConsumableArray(result), [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTooltipItem"])(child, payload)
        ]);
    }, []);
};
/**
 * Returns tooltip data based on a mouse position (as a parameter or in state)
 * @param  {Object} state     current state
 * @param  {Array}  chartData the data defined in chart
 * @param  {String} layout     The layout type of chart
 * @param  {Object} rangeObj  { x, y } coordinates
 * @return {Object}           Tooltip data data
 */ var getTooltipData = function getTooltipData(state, chartData, layout, rangeObj) {
    var rangeData = rangeObj || {
        x: state.chartX,
        y: state.chartY
    };
    var pos = calculateTooltipPos(rangeData, layout);
    var ticks = state.orderedTooltipTicks, axis = state.tooltipAxis, tooltipTicks = state.tooltipTicks;
    var activeIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["calculateActiveTickIndex"])(pos, ticks, tooltipTicks, axis);
    if (activeIndex >= 0 && tooltipTicks) {
        var activeLabel = tooltipTicks[activeIndex] && tooltipTicks[activeIndex].value;
        var activePayload = getTooltipContent(state, chartData, activeIndex, activeLabel);
        var activeCoordinate = getActiveCoordinate(layout, ticks, activeIndex, rangeData);
        return {
            activeTooltipIndex: activeIndex,
            activeLabel: activeLabel,
            activePayload: activePayload,
            activeCoordinate: activeCoordinate
        };
    }
    return null;
};
var getAxisMapByAxes = function getAxisMapByAxes(props, _ref2) {
    var axes = _ref2.axes, graphicalItems = _ref2.graphicalItems, axisType = _ref2.axisType, axisIdKey = _ref2.axisIdKey, stackGroups = _ref2.stackGroups, dataStartIndex = _ref2.dataStartIndex, dataEndIndex = _ref2.dataEndIndex;
    var layout = props.layout, children = props.children, stackOffset = props.stackOffset;
    var isCategorical = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["isCategoricalAxis"])(layout, axisType);
    // Eliminate duplicated axes
    return axes.reduce(function(result, child) {
        var _childProps$domain2;
        var childProps = child.type.defaultProps !== undefined ? _objectSpread(_objectSpread({}, child.type.defaultProps), child.props) : child.props;
        var type = childProps.type, dataKey = childProps.dataKey, allowDataOverflow = childProps.allowDataOverflow, allowDuplicatedCategory = childProps.allowDuplicatedCategory, scale = childProps.scale, ticks = childProps.ticks, includeHidden = childProps.includeHidden;
        var axisId = childProps[axisIdKey];
        if (result[axisId]) {
            return result;
        }
        var displayedData = getDisplayedData(props.data, {
            graphicalItems: graphicalItems.filter(function(item) {
                var _defaultProps;
                var itemAxisId = axisIdKey in item.props ? item.props[axisIdKey] : (_defaultProps = item.type.defaultProps) === null || _defaultProps === void 0 ? void 0 : _defaultProps[axisIdKey];
                return itemAxisId === axisId;
            }),
            dataStartIndex: dataStartIndex,
            dataEndIndex: dataEndIndex
        });
        var len = displayedData.length;
        var domain, duplicateDomain, categoricalDomain;
        /*
     * This is a hack to short-circuit the domain creation here to enhance performance.
     * Usually, the data is used to determine the domain, but when the user specifies
     * a domain upfront (via props), there is no need to calculate the domain start and end,
     * which is very expensive for a larger amount of data.
     * The only thing that would prohibit short-circuiting is when the user doesn't allow data overflow,
     * because the axis is supposed to ignore the specified domain that way.
     */ if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$isDomainSpecifiedByUser$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isDomainSpecifiedByUser"])(childProps.domain, allowDataOverflow, type)) {
            domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseSpecifiedDomain"])(childProps.domain, null, allowDataOverflow);
            /* The chart can be categorical and have the domain specified in numbers
       * we still need to calculate the categorical domain
       * TODO: refactor this more
       */ if (isCategorical && (type === 'number' || scale !== 'auto')) {
                categoricalDomain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfDataByKey"])(displayedData, dataKey, 'category');
            }
        }
        // if the domain is defaulted we need this for `originalDomain` as well
        var defaultDomain = getDefaultDomainByAxisType(type);
        // we didn't create the domain from user's props above, so we need to calculate it
        if (!domain || domain.length === 0) {
            var _childProps$domain;
            var childDomain = (_childProps$domain = childProps.domain) !== null && _childProps$domain !== void 0 ? _childProps$domain : defaultDomain;
            if (dataKey) {
                // has dataKey in <Axis />
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfDataByKey"])(displayedData, dataKey, type);
                if (type === 'category' && isCategorical) {
                    // the field type is category data and this axis is categorical axis
                    var duplicate = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["hasDuplicate"])(domain);
                    if (allowDuplicatedCategory && duplicate) {
                        duplicateDomain = domain;
                        // When category axis has duplicated text, serial numbers are used to generate scale
                        domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$range$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(0, len);
                    } else if (!allowDuplicatedCategory) {
                        // remove duplicated category
                        domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseDomainOfCategoryAxis"])(childDomain, domain, child).reduce(function(finalDomain, entry) {
                            return finalDomain.indexOf(entry) >= 0 ? finalDomain : [].concat(_toConsumableArray(finalDomain), [
                                entry
                            ]);
                        }, []);
                    }
                } else if (type === 'category') {
                    // the field type is category data and this axis is numerical axis
                    if (!allowDuplicatedCategory) {
                        domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseDomainOfCategoryAxis"])(childDomain, domain, child).reduce(function(finalDomain, entry) {
                            return finalDomain.indexOf(entry) >= 0 || entry === '' || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry) ? finalDomain : [].concat(_toConsumableArray(finalDomain), [
                                entry
                            ]);
                        }, []);
                    } else {
                        // eliminate undefined or null or empty string
                        domain = domain.filter(function(entry) {
                            return entry !== '' && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(entry);
                        });
                    }
                } else if (type === 'number') {
                    // the field type is numerical
                    var errorBarsDomain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseErrorBarsOfAxis"])(displayedData, graphicalItems.filter(function(item) {
                        var _defaultProps2, _defaultProps3;
                        var itemAxisId = axisIdKey in item.props ? item.props[axisIdKey] : (_defaultProps2 = item.type.defaultProps) === null || _defaultProps2 === void 0 ? void 0 : _defaultProps2[axisIdKey];
                        var itemHide = 'hide' in item.props ? item.props.hide : (_defaultProps3 = item.type.defaultProps) === null || _defaultProps3 === void 0 ? void 0 : _defaultProps3.hide;
                        return itemAxisId === axisId && (includeHidden || !itemHide);
                    }), dataKey, axisType, layout);
                    if (errorBarsDomain) {
                        domain = errorBarsDomain;
                    }
                }
                if (isCategorical && (type === 'number' || scale !== 'auto')) {
                    categoricalDomain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfDataByKey"])(displayedData, dataKey, 'category');
                }
            } else if (isCategorical) {
                // the axis is a categorical axis
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$range$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(0, len);
            } else if (stackGroups && stackGroups[axisId] && stackGroups[axisId].hasStack && type === 'number') {
                // when stackOffset is 'expand', the domain may be calculated as [0, 1.000000000002]
                domain = stackOffset === 'expand' ? [
                    0,
                    1
                ] : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfStackGroups"])(stackGroups[axisId].stackGroups, dataStartIndex, dataEndIndex);
            } else {
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfItemsWithSameAxis"])(displayedData, graphicalItems.filter(function(item) {
                    var itemAxisId = axisIdKey in item.props ? item.props[axisIdKey] : item.type.defaultProps[axisIdKey];
                    var itemHide = 'hide' in item.props ? item.props.hide : item.type.defaultProps.hide;
                    return itemAxisId === axisId && (includeHidden || !itemHide);
                }), type, layout, true);
            }
            if (type === 'number') {
                // To detect wether there is any reference lines whose props alwaysShow is true
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DetectReferenceElementsDomain$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["detectReferenceElementsDomain"])(children, domain, axisId, axisType, ticks);
                if (childDomain) {
                    domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseSpecifiedDomain"])(childDomain, domain, allowDataOverflow);
                }
            } else if (type === 'category' && childDomain) {
                var axisDomain = childDomain;
                var isDomainValid = domain.every(function(entry) {
                    return axisDomain.indexOf(entry) >= 0;
                });
                if (isDomainValid) {
                    domain = axisDomain;
                }
            }
        }
        return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, axisId, _objectSpread(_objectSpread({}, childProps), {}, {
            axisType: axisType,
            domain: domain,
            categoricalDomain: categoricalDomain,
            duplicateDomain: duplicateDomain,
            originalDomain: (_childProps$domain2 = childProps.domain) !== null && _childProps$domain2 !== void 0 ? _childProps$domain2 : defaultDomain,
            isCategorical: isCategorical,
            layout: layout
        })));
    }, {});
};
/**
 * Get the configuration of axis by the options of item,
 * this kind of axis does not display in chart
 * @param  {Object} props         Latest props
 * @param  {Array} graphicalItems The instances of item
 * @param  {ReactElement} Axis    Axis Component
 * @param  {String} axisType      The type of axis, xAxis - x-axis, yAxis - y-axis
 * @param  {String} axisIdKey     The unique id of an axis
 * @param  {Object} stackGroups   The items grouped by axisId and stackId
 * @param {Number} dataStartIndex The start index of the data series when a brush is applied
 * @param {Number} dataEndIndex   The end index of the data series when a brush is applied
 * @return {Object}               Configuration
 */ var getAxisMapByItems = function getAxisMapByItems(props, _ref3) {
    var graphicalItems = _ref3.graphicalItems, Axis = _ref3.Axis, axisType = _ref3.axisType, axisIdKey = _ref3.axisIdKey, stackGroups = _ref3.stackGroups, dataStartIndex = _ref3.dataStartIndex, dataEndIndex = _ref3.dataEndIndex;
    var layout = props.layout, children = props.children;
    var displayedData = getDisplayedData(props.data, {
        graphicalItems: graphicalItems,
        dataStartIndex: dataStartIndex,
        dataEndIndex: dataEndIndex
    });
    var len = displayedData.length;
    var isCategorical = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["isCategoricalAxis"])(layout, axisType);
    var index = -1;
    // The default type of x-axis is category axis,
    // The default contents of x-axis is the serial numbers of data
    // The default type of y-axis is number axis
    // The default contents of y-axis is the domain of data
    return graphicalItems.reduce(function(result, child) {
        var childProps = child.type.defaultProps !== undefined ? _objectSpread(_objectSpread({}, child.type.defaultProps), child.props) : child.props;
        var axisId = childProps[axisIdKey];
        var originalDomain = getDefaultDomainByAxisType('number');
        if (!result[axisId]) {
            index++;
            var domain;
            if (isCategorical) {
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$range$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(0, len);
            } else if (stackGroups && stackGroups[axisId] && stackGroups[axisId].hasStack) {
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfStackGroups"])(stackGroups[axisId].stackGroups, dataStartIndex, dataEndIndex);
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DetectReferenceElementsDomain$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["detectReferenceElementsDomain"])(children, domain, axisId, axisType);
            } else {
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseSpecifiedDomain"])(originalDomain, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getDomainOfItemsWithSameAxis"])(displayedData, graphicalItems.filter(function(item) {
                    var _defaultProps4, _defaultProps5;
                    var itemAxisId = axisIdKey in item.props ? item.props[axisIdKey] : (_defaultProps4 = item.type.defaultProps) === null || _defaultProps4 === void 0 ? void 0 : _defaultProps4[axisIdKey];
                    var itemHide = 'hide' in item.props ? item.props.hide : (_defaultProps5 = item.type.defaultProps) === null || _defaultProps5 === void 0 ? void 0 : _defaultProps5.hide;
                    return itemAxisId === axisId && !itemHide;
                }), 'number', layout), Axis.defaultProps.allowDataOverflow);
                domain = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DetectReferenceElementsDomain$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["detectReferenceElementsDomain"])(children, domain, axisId, axisType);
            }
            return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, axisId, _objectSpread(_objectSpread({
                axisType: axisType
            }, Axis.defaultProps), {}, {
                hide: true,
                orientation: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(ORIENT_MAP, "".concat(axisType, ".").concat(index % 2), null),
                domain: domain,
                originalDomain: originalDomain,
                isCategorical: isCategorical,
                layout: layout
            })));
        }
        return result;
    }, {});
};
/**
 * Get the configuration of all x-axis or y-axis
 * @param  {Object} props          Latest props
 * @param  {String} axisType       The type of axis
 * @param  {React.ComponentType}  [AxisComp]      Axis Component
 * @param  {Array}  graphicalItems The instances of item
 * @param  {Object} stackGroups    The items grouped by axisId and stackId
 * @param {Number} dataStartIndex  The start index of the data series when a brush is applied
 * @param {Number} dataEndIndex    The end index of the data series when a brush is applied
 * @return {Object}          Configuration
 */ var getAxisMap = function getAxisMap(props, _ref4) {
    var _ref4$axisType = _ref4.axisType, axisType = _ref4$axisType === void 0 ? 'xAxis' : _ref4$axisType, AxisComp = _ref4.AxisComp, graphicalItems = _ref4.graphicalItems, stackGroups = _ref4.stackGroups, dataStartIndex = _ref4.dataStartIndex, dataEndIndex = _ref4.dataEndIndex;
    var children = props.children;
    var axisIdKey = "".concat(axisType, "Id");
    // Get all the instance of Axis
    var axes = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, AxisComp);
    var axisMap = {};
    if (axes && axes.length) {
        axisMap = getAxisMapByAxes(props, {
            axes: axes,
            graphicalItems: graphicalItems,
            axisType: axisType,
            axisIdKey: axisIdKey,
            stackGroups: stackGroups,
            dataStartIndex: dataStartIndex,
            dataEndIndex: dataEndIndex
        });
    } else if (graphicalItems && graphicalItems.length) {
        axisMap = getAxisMapByItems(props, {
            Axis: AxisComp,
            graphicalItems: graphicalItems,
            axisType: axisType,
            axisIdKey: axisIdKey,
            stackGroups: stackGroups,
            dataStartIndex: dataStartIndex,
            dataEndIndex: dataEndIndex
        });
    }
    return axisMap;
};
var tooltipTicksGenerator = function tooltipTicksGenerator(axisMap) {
    var axis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(axisMap);
    var tooltipTicks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(axis, false, true);
    return {
        tooltipTicks: tooltipTicks,
        orderedTooltipTicks: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$sortBy$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tooltipTicks, function(o) {
            return o.coordinate;
        }),
        tooltipAxis: axis,
        tooltipAxisBandSize: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBandSizeOfAxis"])(axis, tooltipTicks)
    };
};
var createDefaultState = function createDefaultState(props) {
    var children = props.children, defaultShowTooltip = props.defaultShowTooltip;
    var brushItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Brush$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Brush"]);
    var startIndex = 0;
    var endIndex = 0;
    if (props.data && props.data.length !== 0) {
        endIndex = props.data.length - 1;
    }
    if (brushItem && brushItem.props) {
        if (brushItem.props.startIndex >= 0) {
            startIndex = brushItem.props.startIndex;
        }
        if (brushItem.props.endIndex >= 0) {
            endIndex = brushItem.props.endIndex;
        }
    }
    return {
        chartX: 0,
        chartY: 0,
        dataStartIndex: startIndex,
        dataEndIndex: endIndex,
        activeTooltipIndex: -1,
        isTooltipActive: Boolean(defaultShowTooltip)
    };
};
var hasGraphicalBarItem = function hasGraphicalBarItem(graphicalItems) {
    if (!graphicalItems || !graphicalItems.length) {
        return false;
    }
    return graphicalItems.some(function(item) {
        var name = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDisplayName"])(item && item.type);
        return name && name.indexOf('Bar') >= 0;
    });
};
var getAxisNameByLayout = function getAxisNameByLayout(layout) {
    if (layout === 'horizontal') {
        return {
            numericAxisName: 'yAxis',
            cateAxisName: 'xAxis'
        };
    }
    if (layout === 'vertical') {
        return {
            numericAxisName: 'xAxis',
            cateAxisName: 'yAxis'
        };
    }
    if (layout === 'centric') {
        return {
            numericAxisName: 'radiusAxis',
            cateAxisName: 'angleAxis'
        };
    }
    return {
        numericAxisName: 'angleAxis',
        cateAxisName: 'radiusAxis'
    };
};
/**
 * Calculate the offset of main part in the svg element
 * @param  {Object} params.props          Latest props
 * @param  {Array}  params.graphicalItems The instances of item
 * @param  {Object} params.xAxisMap       The configuration of x-axis
 * @param  {Object} params.yAxisMap       The configuration of y-axis
 * @param  {Object} prevLegendBBox        The boundary box of legend
 * @return {Object} The offset of main part in the svg element
 */ var calculateOffset = function calculateOffset(_ref5, prevLegendBBox) {
    var props = _ref5.props, graphicalItems = _ref5.graphicalItems, _ref5$xAxisMap = _ref5.xAxisMap, xAxisMap = _ref5$xAxisMap === void 0 ? {} : _ref5$xAxisMap, _ref5$yAxisMap = _ref5.yAxisMap, yAxisMap = _ref5$yAxisMap === void 0 ? {} : _ref5$yAxisMap;
    var width = props.width, height = props.height, children = props.children;
    var margin = props.margin || {};
    var brushItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Brush$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Brush"]);
    var legendItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Legend$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Legend"]);
    var offsetH = Object.keys(yAxisMap).reduce(function(result, id) {
        var entry = yAxisMap[id];
        var orientation = entry.orientation;
        if (!entry.mirror && !entry.hide) {
            return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, orientation, result[orientation] + entry.width));
        }
        return result;
    }, {
        left: margin.left || 0,
        right: margin.right || 0
    });
    var offsetV = Object.keys(xAxisMap).reduce(function(result, id) {
        var entry = xAxisMap[id];
        var orientation = entry.orientation;
        if (!entry.mirror && !entry.hide) {
            return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, orientation, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(result, "".concat(orientation)) + entry.height));
        }
        return result;
    }, {
        top: margin.top || 0,
        bottom: margin.bottom || 0
    });
    var offset = _objectSpread(_objectSpread({}, offsetV), offsetH);
    var brushBottom = offset.bottom;
    if (brushItem) {
        offset.bottom += brushItem.props.height || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Brush$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Brush"].defaultProps.height;
    }
    if (legendItem && prevLegendBBox) {
        // @ts-expect-error margin is optional in props but required in appendOffsetOfLegend
        offset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["appendOffsetOfLegend"])(offset, graphicalItems, props, prevLegendBBox);
    }
    var offsetWidth = width - offset.left - offset.right;
    var offsetHeight = height - offset.top - offset.bottom;
    return _objectSpread(_objectSpread({
        brushBottom: brushBottom
    }, offset), {}, {
        // never return negative values for height and width
        width: Math.max(offsetWidth, 0),
        height: Math.max(offsetHeight, 0)
    });
};
// Determine the size of the axis, used for calculation of relative bar sizes
var getCartesianAxisSize = function getCartesianAxisSize(axisObj, axisName) {
    if (axisName === 'xAxis') {
        return axisObj[axisName].width;
    }
    if (axisName === 'yAxis') {
        return axisObj[axisName].height;
    }
    // This is only supported for Bar charts (i.e. charts with cartesian axes), so we should never get here
    return undefined;
};
var generateCategoricalChart = function generateCategoricalChart(_ref6) {
    var chartName = _ref6.chartName, GraphicalChild = _ref6.GraphicalChild, _ref6$defaultTooltipE = _ref6.defaultTooltipEventType, defaultTooltipEventType = _ref6$defaultTooltipE === void 0 ? 'axis' : _ref6$defaultTooltipE, _ref6$validateTooltip = _ref6.validateTooltipEventTypes, validateTooltipEventTypes = _ref6$validateTooltip === void 0 ? [
        'axis'
    ] : _ref6$validateTooltip, axisComponents = _ref6.axisComponents, legendContent = _ref6.legendContent, formatAxisMap = _ref6.formatAxisMap, defaultProps = _ref6.defaultProps;
    var getFormatItems = function getFormatItems(props, currentState) {
        var graphicalItems = currentState.graphicalItems, stackGroups = currentState.stackGroups, offset = currentState.offset, updateId = currentState.updateId, dataStartIndex = currentState.dataStartIndex, dataEndIndex = currentState.dataEndIndex;
        var barSize = props.barSize, layout = props.layout, barGap = props.barGap, barCategoryGap = props.barCategoryGap, globalMaxBarSize = props.maxBarSize;
        var _getAxisNameByLayout = getAxisNameByLayout(layout), numericAxisName = _getAxisNameByLayout.numericAxisName, cateAxisName = _getAxisNameByLayout.cateAxisName;
        var hasBar = hasGraphicalBarItem(graphicalItems);
        var formattedItems = [];
        graphicalItems.forEach(function(item, index) {
            var displayedData = getDisplayedData(props.data, {
                graphicalItems: [
                    item
                ],
                dataStartIndex: dataStartIndex,
                dataEndIndex: dataEndIndex
            });
            var itemProps = item.type.defaultProps !== undefined ? _objectSpread(_objectSpread({}, item.type.defaultProps), item.props) : item.props;
            var dataKey = itemProps.dataKey, childMaxBarSize = itemProps.maxBarSize;
            // axisId of the numerical axis
            var numericAxisId = itemProps["".concat(numericAxisName, "Id")];
            // axisId of the categorical axis
            var cateAxisId = itemProps["".concat(cateAxisName, "Id")];
            var axisObjInitialValue = {};
            var axisObj = axisComponents.reduce(function(result, entry) {
                var _item$type$displayNam, _item$type;
                // map of axisId to axis for a specific axis type
                var axisMap = currentState["".concat(entry.axisType, "Map")];
                // axisId of axis we are currently computing
                var id = itemProps["".concat(entry.axisType, "Id")];
                /**
         * tell the user in dev mode that their configuration is incorrect if we cannot find a match between
         * axisId on the chart and axisId on the axis. zAxis does not get passed in the map for ComposedChart,
         * leave it out of the check for now.
         */ !(axisMap && axisMap[id] || entry.axisType === 'zAxis') ? ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tiny$2d$invariant$2f$dist$2f$esm$2f$tiny$2d$invariant$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(false, "Specifying a(n) ".concat(entry.axisType, "Id requires a corresponding ").concat(entry.axisType, "Id on the targeted graphical component ").concat((_item$type$displayNam = item === null || item === void 0 || (_item$type = item.type) === null || _item$type === void 0 ? void 0 : _item$type.displayName) !== null && _item$type$displayNam !== void 0 ? _item$type$displayNam : '')) : "TURBOPACK unreachable" : void 0;
                // the axis we are currently formatting
                var axis = axisMap[id];
                return _objectSpread(_objectSpread({}, result), {}, _defineProperty(_defineProperty({}, entry.axisType, axis), "".concat(entry.axisType, "Ticks"), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(axis)));
            }, axisObjInitialValue);
            var cateAxis = axisObj[cateAxisName];
            var cateTicks = axisObj["".concat(cateAxisName, "Ticks")];
            var stackedData = stackGroups && stackGroups[numericAxisId] && stackGroups[numericAxisId].hasStack && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getStackedDataOfItem"])(item, stackGroups[numericAxisId].stackGroups);
            var itemIsBar = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDisplayName"])(item.type).indexOf('Bar') >= 0;
            var bandSize = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBandSizeOfAxis"])(cateAxis, cateTicks);
            var barPosition = [];
            var sizeList = hasBar && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBarSizeList"])({
                barSize: barSize,
                stackGroups: stackGroups,
                totalSize: getCartesianAxisSize(axisObj, cateAxisName)
            });
            if (itemIsBar) {
                var _ref7, _getBandSizeOfAxis;
                // If it is bar, calculate the position of bar
                var maxBarSize = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(childMaxBarSize) ? globalMaxBarSize : childMaxBarSize;
                var barBandSize = (_ref7 = (_getBandSizeOfAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBandSizeOfAxis"])(cateAxis, cateTicks, true)) !== null && _getBandSizeOfAxis !== void 0 ? _getBandSizeOfAxis : maxBarSize) !== null && _ref7 !== void 0 ? _ref7 : 0;
                barPosition = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getBarPosition"])({
                    barGap: barGap,
                    barCategoryGap: barCategoryGap,
                    bandSize: barBandSize !== bandSize ? barBandSize : bandSize,
                    sizeList: sizeList[cateAxisId],
                    maxBarSize: maxBarSize
                });
                if (barBandSize !== bandSize) {
                    barPosition = barPosition.map(function(pos) {
                        return _objectSpread(_objectSpread({}, pos), {}, {
                            position: _objectSpread(_objectSpread({}, pos.position), {}, {
                                offset: pos.position.offset - barBandSize / 2
                            })
                        });
                    });
                }
            }
            // @ts-expect-error we should stop reading data from ReactElements
            var composedFn = item && item.type && item.type.getComposedData;
            if (composedFn) {
                formattedItems.push({
                    props: _objectSpread(_objectSpread({}, composedFn(_objectSpread(_objectSpread({}, axisObj), {}, {
                        displayedData: displayedData,
                        props: props,
                        dataKey: dataKey,
                        item: item,
                        bandSize: bandSize,
                        barPosition: barPosition,
                        offset: offset,
                        stackedData: stackedData,
                        layout: layout,
                        dataStartIndex: dataStartIndex,
                        dataEndIndex: dataEndIndex
                    }))), {}, _defineProperty(_defineProperty(_defineProperty({
                        key: item.key || "item-".concat(index)
                    }, numericAxisName, axisObj[numericAxisName]), cateAxisName, axisObj[cateAxisName]), "animationId", updateId)),
                    childIndex: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["parseChildIndex"])(item, props.children),
                    item: item
                });
            }
        });
        return formattedItems;
    };
    /**
   * The AxisMaps are expensive to render on large data sets
   * so provide the ability to store them in state and only update them when necessary
   * they are dependent upon the start and end index of
   * the brush so it's important that this method is called _after_
   * the state is updated with any new start/end indices
   *
   * @param {Object} props          The props object to be used for updating the axismaps
   * dataStartIndex: The start index of the data series when a brush is applied
   * dataEndIndex: The end index of the data series when a brush is applied
   * updateId: The update id
   * @param {Object} prevState      Prev state
   * @return {Object} state New state to set
   */ var updateStateOfAxisMapsOffsetAndStackGroups = function updateStateOfAxisMapsOffsetAndStackGroups(_ref8, prevState) {
        var props = _ref8.props, dataStartIndex = _ref8.dataStartIndex, dataEndIndex = _ref8.dataEndIndex, updateId = _ref8.updateId;
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["validateWidthHeight"])({
            props: props
        })) {
            return null;
        }
        var children = props.children, layout = props.layout, stackOffset = props.stackOffset, data = props.data, reverseStackOrder = props.reverseStackOrder;
        var _getAxisNameByLayout2 = getAxisNameByLayout(layout), numericAxisName = _getAxisNameByLayout2.numericAxisName, cateAxisName = _getAxisNameByLayout2.cateAxisName;
        var graphicalItems = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findAllByType"])(children, GraphicalChild);
        var stackGroups = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getStackGroupsByAxisId"])(data, graphicalItems, "".concat(numericAxisName, "Id"), "".concat(cateAxisName, "Id"), stackOffset, reverseStackOrder);
        var axisObj = axisComponents.reduce(function(result, entry) {
            var name = "".concat(entry.axisType, "Map");
            return _objectSpread(_objectSpread({}, result), {}, _defineProperty({}, name, getAxisMap(props, _objectSpread(_objectSpread({}, entry), {}, {
                graphicalItems: graphicalItems,
                stackGroups: entry.axisType === numericAxisName && stackGroups,
                dataStartIndex: dataStartIndex,
                dataEndIndex: dataEndIndex
            }))));
        }, {});
        var offset = calculateOffset(_objectSpread(_objectSpread({}, axisObj), {}, {
            props: props,
            graphicalItems: graphicalItems
        }), prevState === null || prevState === void 0 ? void 0 : prevState.legendBBox);
        Object.keys(axisObj).forEach(function(key) {
            axisObj[key] = formatAxisMap(props, axisObj[key], offset, key.replace('Map', ''), chartName);
        });
        var cateAxisMap = axisObj["".concat(cateAxisName, "Map")];
        var ticksObj = tooltipTicksGenerator(cateAxisMap);
        var formattedGraphicalItems = getFormatItems(props, _objectSpread(_objectSpread({}, axisObj), {}, {
            dataStartIndex: dataStartIndex,
            dataEndIndex: dataEndIndex,
            updateId: updateId,
            graphicalItems: graphicalItems,
            stackGroups: stackGroups,
            offset: offset
        }));
        return _objectSpread(_objectSpread({
            formattedGraphicalItems: formattedGraphicalItems,
            graphicalItems: graphicalItems,
            offset: offset,
            stackGroups: stackGroups
        }, ticksObj), axisObj);
    };
    var CategoricalChartWrapper = /*#__PURE__*/ function(_Component) {
        function CategoricalChartWrapper(_props) {
            var _props$id, _props$throttleDelay;
            var _this;
            _classCallCheck(this, CategoricalChartWrapper);
            _this = _callSuper(this, CategoricalChartWrapper, [
                _props
            ]);
            _defineProperty(_this, "eventEmitterSymbol", Symbol('rechartsEventEmitter'));
            _defineProperty(_this, "accessibilityManager", new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$chart$2f$AccessibilityManager$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["AccessibilityManager"]());
            _defineProperty(_this, "handleLegendBBoxUpdate", function(box) {
                if (box) {
                    var _this$state = _this.state, dataStartIndex = _this$state.dataStartIndex, dataEndIndex = _this$state.dataEndIndex, updateId = _this$state.updateId;
                    _this.setState(_objectSpread({
                        legendBBox: box
                    }, updateStateOfAxisMapsOffsetAndStackGroups({
                        props: _this.props,
                        dataStartIndex: dataStartIndex,
                        dataEndIndex: dataEndIndex,
                        updateId: updateId
                    }, _objectSpread(_objectSpread({}, _this.state), {}, {
                        legendBBox: box
                    }))));
                }
            });
            _defineProperty(_this, "handleReceiveSyncEvent", function(cId, data, emitter) {
                if (_this.props.syncId === cId) {
                    if (emitter === _this.eventEmitterSymbol && typeof _this.props.syncMethod !== 'function') {
                        return;
                    }
                    _this.applySyncEvent(data);
                }
            });
            _defineProperty(_this, "handleBrushChange", function(_ref9) {
                var startIndex = _ref9.startIndex, endIndex = _ref9.endIndex;
                // Only trigger changes if the extents of the brush have actually changed
                if (startIndex !== _this.state.dataStartIndex || endIndex !== _this.state.dataEndIndex) {
                    var updateId = _this.state.updateId;
                    _this.setState(function() {
                        return _objectSpread({
                            dataStartIndex: startIndex,
                            dataEndIndex: endIndex
                        }, updateStateOfAxisMapsOffsetAndStackGroups({
                            props: _this.props,
                            dataStartIndex: startIndex,
                            dataEndIndex: endIndex,
                            updateId: updateId
                        }, _this.state));
                    });
                    _this.triggerSyncEvent({
                        dataStartIndex: startIndex,
                        dataEndIndex: endIndex
                    });
                }
            });
            /**
       * The handler of mouse entering chart
       * @param  {Object} e              Event object
       * @return {Null}                  null
       */ _defineProperty(_this, "handleMouseEnter", function(e) {
                var mouse = _this.getMouseInfo(e);
                if (mouse) {
                    var _nextState = _objectSpread(_objectSpread({}, mouse), {}, {
                        isTooltipActive: true
                    });
                    _this.setState(_nextState);
                    _this.triggerSyncEvent(_nextState);
                    var onMouseEnter = _this.props.onMouseEnter;
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onMouseEnter)) {
                        onMouseEnter(_nextState, e);
                    }
                }
            });
            _defineProperty(_this, "triggeredAfterMouseMove", function(e) {
                var mouse = _this.getMouseInfo(e);
                var nextState = mouse ? _objectSpread(_objectSpread({}, mouse), {}, {
                    isTooltipActive: true
                }) : {
                    isTooltipActive: false
                };
                _this.setState(nextState);
                _this.triggerSyncEvent(nextState);
                var onMouseMove = _this.props.onMouseMove;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onMouseMove)) {
                    onMouseMove(nextState, e);
                }
            });
            /**
       * The handler of mouse entering a scatter
       * @param {Object} el The active scatter
       * @return {Object} no return
       */ _defineProperty(_this, "handleItemMouseEnter", function(el) {
                _this.setState(function() {
                    return {
                        isTooltipActive: true,
                        activeItem: el,
                        activePayload: el.tooltipPayload,
                        activeCoordinate: el.tooltipPosition || {
                            x: el.cx,
                            y: el.cy
                        }
                    };
                });
            });
            /**
       * The handler of mouse leaving a scatter
       * @return {Object} no return
       */ _defineProperty(_this, "handleItemMouseLeave", function() {
                _this.setState(function() {
                    return {
                        isTooltipActive: false
                    };
                });
            });
            /**
       * The handler of mouse moving in chart
       * @param  {React.MouseEvent} e        Event object
       * @return {void} no return
       */ _defineProperty(_this, "handleMouseMove", function(e) {
                e.persist();
                _this.throttleTriggeredAfterMouseMove(e);
            });
            /**
       * The handler if mouse leaving chart
       * @param {Object} e Event object
       * @return {Null} no return
       */ _defineProperty(_this, "handleMouseLeave", function(e) {
                _this.throttleTriggeredAfterMouseMove.cancel();
                var nextState = {
                    isTooltipActive: false
                };
                _this.setState(nextState);
                _this.triggerSyncEvent(nextState);
                var onMouseLeave = _this.props.onMouseLeave;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onMouseLeave)) {
                    onMouseLeave(nextState, e);
                }
            });
            _defineProperty(_this, "handleOuterEvent", function(e) {
                var eventName = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getReactEventByType"])(e);
                var event = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_this.props, "".concat(eventName));
                if (eventName && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(event)) {
                    var _mouse;
                    var mouse;
                    if (/.*touch.*/i.test(eventName)) {
                        mouse = _this.getMouseInfo(e.changedTouches[0]);
                    } else {
                        mouse = _this.getMouseInfo(e);
                    }
                    event((_mouse = mouse) !== null && _mouse !== void 0 ? _mouse : {}, e);
                }
            });
            _defineProperty(_this, "handleClick", function(e) {
                var mouse = _this.getMouseInfo(e);
                if (mouse) {
                    var _nextState2 = _objectSpread(_objectSpread({}, mouse), {}, {
                        isTooltipActive: true
                    });
                    _this.setState(_nextState2);
                    _this.triggerSyncEvent(_nextState2);
                    var onClick = _this.props.onClick;
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onClick)) {
                        onClick(_nextState2, e);
                    }
                }
            });
            _defineProperty(_this, "handleMouseDown", function(e) {
                var onMouseDown = _this.props.onMouseDown;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onMouseDown)) {
                    var _nextState3 = _this.getMouseInfo(e);
                    onMouseDown(_nextState3, e);
                }
            });
            _defineProperty(_this, "handleMouseUp", function(e) {
                var onMouseUp = _this.props.onMouseUp;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onMouseUp)) {
                    var _nextState4 = _this.getMouseInfo(e);
                    onMouseUp(_nextState4, e);
                }
            });
            _defineProperty(_this, "handleTouchMove", function(e) {
                if (e.changedTouches != null && e.changedTouches.length > 0) {
                    _this.throttleTriggeredAfterMouseMove(e.changedTouches[0]);
                }
            });
            _defineProperty(_this, "handleTouchStart", function(e) {
                if (e.changedTouches != null && e.changedTouches.length > 0) {
                    _this.handleMouseDown(e.changedTouches[0]);
                }
            });
            _defineProperty(_this, "handleTouchEnd", function(e) {
                if (e.changedTouches != null && e.changedTouches.length > 0) {
                    _this.handleMouseUp(e.changedTouches[0]);
                }
            });
            _defineProperty(_this, "handleDoubleClick", function(e) {
                var onDoubleClick = _this.props.onDoubleClick;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onDoubleClick)) {
                    var _nextState5 = _this.getMouseInfo(e);
                    onDoubleClick(_nextState5, e);
                }
            });
            _defineProperty(_this, "handleContextMenu", function(e) {
                var onContextMenu = _this.props.onContextMenu;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onContextMenu)) {
                    var _nextState6 = _this.getMouseInfo(e);
                    onContextMenu(_nextState6, e);
                }
            });
            _defineProperty(_this, "triggerSyncEvent", function(data) {
                if (_this.props.syncId !== undefined) {
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["eventCenter"].emit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SYNC_EVENT"], _this.props.syncId, data, _this.eventEmitterSymbol);
                }
            });
            _defineProperty(_this, "applySyncEvent", function(data) {
                var _this$props = _this.props, layout = _this$props.layout, syncMethod = _this$props.syncMethod;
                var updateId = _this.state.updateId;
                var dataStartIndex = data.dataStartIndex, dataEndIndex = data.dataEndIndex;
                if (data.dataStartIndex !== undefined || data.dataEndIndex !== undefined) {
                    _this.setState(_objectSpread({
                        dataStartIndex: dataStartIndex,
                        dataEndIndex: dataEndIndex
                    }, updateStateOfAxisMapsOffsetAndStackGroups({
                        props: _this.props,
                        dataStartIndex: dataStartIndex,
                        dataEndIndex: dataEndIndex,
                        updateId: updateId
                    }, _this.state)));
                } else if (data.activeTooltipIndex !== undefined) {
                    var chartX = data.chartX, chartY = data.chartY;
                    var activeTooltipIndex = data.activeTooltipIndex;
                    var _this$state2 = _this.state, offset = _this$state2.offset, tooltipTicks = _this$state2.tooltipTicks;
                    if (!offset) {
                        return;
                    }
                    if (typeof syncMethod === 'function') {
                        // Call a callback function. If there is an application specific algorithm
                        activeTooltipIndex = syncMethod(tooltipTicks, data);
                    } else if (syncMethod === 'value') {
                        // Set activeTooltipIndex to the index with the same value as data.activeLabel
                        // For loop instead of findIndex because the latter is very slow in some browsers
                        activeTooltipIndex = -1; // in case we cannot find the element
                        for(var i = 0; i < tooltipTicks.length; i++){
                            if (tooltipTicks[i].value === data.activeLabel) {
                                activeTooltipIndex = i;
                                break;
                            }
                        }
                    }
                    var viewBox = _objectSpread(_objectSpread({}, offset), {}, {
                        x: offset.left,
                        y: offset.top
                    });
                    // When a categorical chart is combined with another chart, the value of chartX
                    // and chartY may beyond the boundaries.
                    var validateChartX = Math.min(chartX, viewBox.x + viewBox.width);
                    var validateChartY = Math.min(chartY, viewBox.y + viewBox.height);
                    var activeLabel = tooltipTicks[activeTooltipIndex] && tooltipTicks[activeTooltipIndex].value;
                    var activePayload = getTooltipContent(_this.state, _this.props.data, activeTooltipIndex);
                    var activeCoordinate = tooltipTicks[activeTooltipIndex] ? {
                        x: layout === 'horizontal' ? tooltipTicks[activeTooltipIndex].coordinate : validateChartX,
                        y: layout === 'horizontal' ? validateChartY : tooltipTicks[activeTooltipIndex].coordinate
                    } : originCoordinate;
                    _this.setState(_objectSpread(_objectSpread({}, data), {}, {
                        activeLabel: activeLabel,
                        activeCoordinate: activeCoordinate,
                        activePayload: activePayload,
                        activeTooltipIndex: activeTooltipIndex
                    }));
                } else {
                    _this.setState(data);
                }
            });
            _defineProperty(_this, "renderCursor", function(element) {
                var _element$props$active;
                var _this$state3 = _this.state, isTooltipActive = _this$state3.isTooltipActive, activeCoordinate = _this$state3.activeCoordinate, activePayload = _this$state3.activePayload, offset = _this$state3.offset, activeTooltipIndex = _this$state3.activeTooltipIndex, tooltipAxisBandSize = _this$state3.tooltipAxisBandSize;
                var tooltipEventType = _this.getTooltipEventType();
                // The cursor is a part of the Tooltip, and it should be shown (by default) when the Tooltip is active.
                var isActive = (_element$props$active = element.props.active) !== null && _element$props$active !== void 0 ? _element$props$active : isTooltipActive;
                var layout = _this.props.layout;
                var key = element.key || '_recharts-cursor';
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Cursor$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Cursor"], {
                    key: key,
                    activeCoordinate: activeCoordinate,
                    activePayload: activePayload,
                    activeTooltipIndex: activeTooltipIndex,
                    chartName: chartName,
                    element: element,
                    isActive: isActive,
                    layout: layout,
                    offset: offset,
                    tooltipAxisBandSize: tooltipAxisBandSize,
                    tooltipEventType: tooltipEventType
                });
            });
            _defineProperty(_this, "renderPolarAxis", function(element, displayName, index) {
                var axisType = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(element, 'type.axisType');
                var axisMap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_this.state, "".concat(axisType, "Map"));
                var elementDefaultProps = element.type.defaultProps;
                var elementProps = elementDefaultProps !== undefined ? _objectSpread(_objectSpread({}, elementDefaultProps), element.props) : element.props;
                var axisOption = axisMap && axisMap[elementProps["".concat(axisType, "Id")]];
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, _objectSpread(_objectSpread({}, axisOption), {}, {
                    className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(axisType, axisOption.className),
                    key: element.key || "".concat(displayName, "-").concat(index),
                    ticks: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(axisOption, true)
                }));
            });
            _defineProperty(_this, "renderPolarGrid", function(element) {
                var _element$props = element.props, radialLines = _element$props.radialLines, polarAngles = _element$props.polarAngles, polarRadius = _element$props.polarRadius;
                var _this$state4 = _this.state, radiusAxisMap = _this$state4.radiusAxisMap, angleAxisMap = _this$state4.angleAxisMap;
                var radiusAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(radiusAxisMap);
                var angleAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(angleAxisMap);
                var cx = angleAxis.cx, cy = angleAxis.cy, innerRadius = angleAxis.innerRadius, outerRadius = angleAxis.outerRadius;
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, {
                    polarAngles: Array.isArray(polarAngles) ? polarAngles : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(angleAxis, true).map(function(entry) {
                        return entry.coordinate;
                    }),
                    polarRadius: Array.isArray(polarRadius) ? polarRadius : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(radiusAxis, true).map(function(entry) {
                        return entry.coordinate;
                    }),
                    cx: cx,
                    cy: cy,
                    innerRadius: innerRadius,
                    outerRadius: outerRadius,
                    key: element.key || 'polar-grid',
                    radialLines: radialLines
                });
            });
            /**
       * Draw legend
       * @return {ReactElement}            The instance of Legend
       */ _defineProperty(_this, "renderLegend", function() {
                var formattedGraphicalItems = _this.state.formattedGraphicalItems;
                var _this$props2 = _this.props, children = _this$props2.children, width = _this$props2.width, height = _this$props2.height;
                var margin = _this.props.margin || {};
                var legendWidth = width - (margin.left || 0) - (margin.right || 0);
                var props = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getLegendProps$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getLegendProps"])({
                    children: children,
                    formattedGraphicalItems: formattedGraphicalItems,
                    legendWidth: legendWidth,
                    legendContent: legendContent
                });
                if (!props) {
                    return null;
                }
                var item = props.item, otherProps = _objectWithoutProperties(props, _excluded);
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(item, _objectSpread(_objectSpread({}, otherProps), {}, {
                    chartWidth: width,
                    chartHeight: height,
                    margin: margin,
                    onBBoxUpdate: _this.handleLegendBBoxUpdate
                }));
            });
            /**
       * Draw Tooltip
       * @return {ReactElement}  The instance of Tooltip
       */ _defineProperty(_this, "renderTooltip", function() {
                var _tooltipItem$props$ac;
                var _this$props3 = _this.props, children = _this$props3.children, accessibilityLayer = _this$props3.accessibilityLayer;
                var tooltipItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"]);
                if (!tooltipItem) {
                    return null;
                }
                var _this$state5 = _this.state, isTooltipActive = _this$state5.isTooltipActive, activeCoordinate = _this$state5.activeCoordinate, activePayload = _this$state5.activePayload, activeLabel = _this$state5.activeLabel, offset = _this$state5.offset;
                // The user can set isActive on the Tooltip,
                // and we respect the user to enable customisation.
                // The Tooltip is active if the user has set isActive, or if the tooltip is active due to a mouse event.
                var isActive = (_tooltipItem$props$ac = tooltipItem.props.active) !== null && _tooltipItem$props$ac !== void 0 ? _tooltipItem$props$ac : isTooltipActive;
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(tooltipItem, {
                    viewBox: _objectSpread(_objectSpread({}, offset), {}, {
                        x: offset.left,
                        y: offset.top
                    }),
                    active: isActive,
                    label: activeLabel,
                    payload: isActive ? activePayload : [],
                    coordinate: activeCoordinate,
                    accessibilityLayer: accessibilityLayer
                });
            });
            _defineProperty(_this, "renderBrush", function(element) {
                var _this$props4 = _this.props, margin = _this$props4.margin, data = _this$props4.data;
                var _this$state6 = _this.state, offset = _this$state6.offset, dataStartIndex = _this$state6.dataStartIndex, dataEndIndex = _this$state6.dataEndIndex, updateId = _this$state6.updateId;
                // TODO: update brush when children update
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, {
                    key: element.key || '_recharts-brush',
                    onChange: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineEventHandlers"])(_this.handleBrushChange, element.props.onChange),
                    data: data,
                    x: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(element.props.x) ? element.props.x : offset.left,
                    y: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(element.props.y) ? element.props.y : offset.top + offset.height + offset.brushBottom - (margin.bottom || 0),
                    width: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(element.props.width) ? element.props.width : offset.width,
                    startIndex: dataStartIndex,
                    endIndex: dataEndIndex,
                    updateId: "brush-".concat(updateId)
                });
            });
            _defineProperty(_this, "renderReferenceElement", function(element, displayName, index) {
                if (!element) {
                    return null;
                }
                var _this2 = _this, clipPathId = _this2.clipPathId;
                var _this$state7 = _this.state, xAxisMap = _this$state7.xAxisMap, yAxisMap = _this$state7.yAxisMap, offset = _this$state7.offset;
                var elementDefaultProps = element.type.defaultProps || {};
                var _element$props2 = element.props, _element$props2$xAxis = _element$props2.xAxisId, xAxisId = _element$props2$xAxis === void 0 ? elementDefaultProps.xAxisId : _element$props2$xAxis, _element$props2$yAxis = _element$props2.yAxisId, yAxisId = _element$props2$yAxis === void 0 ? elementDefaultProps.yAxisId : _element$props2$yAxis;
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, {
                    key: element.key || "".concat(displayName, "-").concat(index),
                    xAxis: xAxisMap[xAxisId],
                    yAxis: yAxisMap[yAxisId],
                    viewBox: {
                        x: offset.left,
                        y: offset.top,
                        width: offset.width,
                        height: offset.height
                    },
                    clipPathId: clipPathId
                });
            });
            _defineProperty(_this, "renderActivePoints", function(_ref10) {
                var item = _ref10.item, activePoint = _ref10.activePoint, basePoint = _ref10.basePoint, childIndex = _ref10.childIndex, isRange = _ref10.isRange;
                var result = [];
                // item is not a React Element so we don't need to resolve defaultProps.
                var key = item.props.key;
                var itemItemProps = item.item.type.defaultProps !== undefined ? _objectSpread(_objectSpread({}, item.item.type.defaultProps), item.item.props) : item.item.props;
                var activeDot = itemItemProps.activeDot, dataKey = itemItemProps.dataKey;
                var dotProps = _objectSpread(_objectSpread({
                    index: childIndex,
                    dataKey: dataKey,
                    cx: activePoint.x,
                    cy: activePoint.y,
                    r: 4,
                    fill: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getMainColorOfGraphicItem"])(item.item),
                    strokeWidth: 2,
                    stroke: '#fff',
                    payload: activePoint.payload,
                    value: activePoint.value
                }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(activeDot, false)), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventHandlers"])(activeDot));
                result.push(CategoricalChartWrapper.renderActiveDot(activeDot, dotProps, "".concat(key, "-activePoint-").concat(childIndex)));
                if (basePoint) {
                    result.push(CategoricalChartWrapper.renderActiveDot(activeDot, _objectSpread(_objectSpread({}, dotProps), {}, {
                        cx: basePoint.x,
                        cy: basePoint.y
                    }), "".concat(key, "-basePoint-").concat(childIndex)));
                } else if (isRange) {
                    result.push(null);
                }
                return result;
            });
            _defineProperty(_this, "renderGraphicChild", function(element, displayName, index) {
                var item = _this.filterFormatItem(element, displayName, index);
                if (!item) {
                    return null;
                }
                var tooltipEventType = _this.getTooltipEventType();
                var _this$state8 = _this.state, isTooltipActive = _this$state8.isTooltipActive, tooltipAxis = _this$state8.tooltipAxis, activeTooltipIndex = _this$state8.activeTooltipIndex, activeLabel = _this$state8.activeLabel;
                var children = _this.props.children;
                var tooltipItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"]);
                // item is not a React Element so we don't need to resolve defaultProps
                var _item$props = item.props, points = _item$props.points, isRange = _item$props.isRange, baseLine = _item$props.baseLine;
                var itemItemProps = item.item.type.defaultProps !== undefined ? _objectSpread(_objectSpread({}, item.item.type.defaultProps), item.item.props) : item.item.props;
                var activeDot = itemItemProps.activeDot, hide = itemItemProps.hide, activeBar = itemItemProps.activeBar, activeShape = itemItemProps.activeShape;
                var hasActive = Boolean(!hide && isTooltipActive && tooltipItem && (activeDot || activeBar || activeShape));
                var itemEvents = {};
                if (tooltipEventType !== 'axis' && tooltipItem && tooltipItem.props.trigger === 'click') {
                    itemEvents = {
                        onClick: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineEventHandlers"])(_this.handleItemMouseEnter, element.props.onClick)
                    };
                } else if (tooltipEventType !== 'axis') {
                    itemEvents = {
                        onMouseLeave: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineEventHandlers"])(_this.handleItemMouseLeave, element.props.onMouseLeave),
                        onMouseEnter: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineEventHandlers"])(_this.handleItemMouseEnter, element.props.onMouseEnter)
                    };
                }
                var graphicalItem = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, _objectSpread(_objectSpread({}, item.props), itemEvents));
                function findWithPayload(entry) {
                    // TODO needs to verify dataKey is Function
                    return typeof tooltipAxis.dataKey === 'function' ? tooltipAxis.dataKey(entry.payload) : null;
                }
                if (hasActive) {
                    if (activeTooltipIndex >= 0) {
                        var activePoint, basePoint;
                        if (tooltipAxis.dataKey && !tooltipAxis.allowDuplicatedCategory) {
                            // number transform to string
                            var specifiedKey = typeof tooltipAxis.dataKey === 'function' ? findWithPayload : 'payload.'.concat(tooltipAxis.dataKey.toString());
                            activePoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findEntryInArray"])(points, specifiedKey, activeLabel);
                            basePoint = isRange && baseLine && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findEntryInArray"])(baseLine, specifiedKey, activeLabel);
                        } else {
                            activePoint = points === null || points === void 0 ? void 0 : points[activeTooltipIndex];
                            basePoint = isRange && baseLine && baseLine[activeTooltipIndex];
                        }
                        if (activeShape || activeBar) {
                            var activeIndex = element.props.activeIndex !== undefined ? element.props.activeIndex : activeTooltipIndex;
                            return [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, _objectSpread(_objectSpread(_objectSpread({}, item.props), itemEvents), {}, {
                                    activeIndex: activeIndex
                                })),
                                null,
                                null
                            ];
                        }
                        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(activePoint)) {
                            return [
                                graphicalItem
                            ].concat(_toConsumableArray(_this.renderActivePoints({
                                item: item,
                                activePoint: activePoint,
                                basePoint: basePoint,
                                childIndex: activeTooltipIndex,
                                isRange: isRange
                            })));
                        }
                    } else {
                        var _this$getItemByXY;
                        /**
             * We hit this block if consumer uses a Tooltip without XAxis and/or YAxis.
             * In which case, this.state.activeTooltipIndex never gets set
             * because the mouse events that trigger that value getting set never get trigged without the axis components.
             *
             * An example usage case is a FunnelChart
             */ var _ref11 = (_this$getItemByXY = _this.getItemByXY(_this.state.activeCoordinate)) !== null && _this$getItemByXY !== void 0 ? _this$getItemByXY : {
                            graphicalItem: graphicalItem
                        }, _ref11$graphicalItem = _ref11.graphicalItem, _ref11$graphicalItem$ = _ref11$graphicalItem.item, xyItem = _ref11$graphicalItem$ === void 0 ? element : _ref11$graphicalItem$, childIndex = _ref11$graphicalItem.childIndex;
                        var elementProps = _objectSpread(_objectSpread(_objectSpread({}, item.props), itemEvents), {}, {
                            activeIndex: childIndex
                        });
                        return [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(xyItem, elementProps),
                            null,
                            null
                        ];
                    }
                }
                if (isRange) {
                    return [
                        graphicalItem,
                        null,
                        null
                    ];
                }
                return [
                    graphicalItem,
                    null
                ];
            });
            _defineProperty(_this, "renderCustomized", function(element, displayName, index) {
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(element, _objectSpread(_objectSpread({
                    key: "recharts-customized-".concat(index)
                }, _this.props), _this.state));
            });
            _defineProperty(_this, "renderMap", {
                CartesianGrid: {
                    handler: renderAsIs,
                    once: true
                },
                ReferenceArea: {
                    handler: _this.renderReferenceElement
                },
                ReferenceLine: {
                    handler: renderAsIs
                },
                ReferenceDot: {
                    handler: _this.renderReferenceElement
                },
                XAxis: {
                    handler: renderAsIs
                },
                YAxis: {
                    handler: renderAsIs
                },
                Brush: {
                    handler: _this.renderBrush,
                    once: true
                },
                Bar: {
                    handler: _this.renderGraphicChild
                },
                Line: {
                    handler: _this.renderGraphicChild
                },
                Area: {
                    handler: _this.renderGraphicChild
                },
                Radar: {
                    handler: _this.renderGraphicChild
                },
                RadialBar: {
                    handler: _this.renderGraphicChild
                },
                Scatter: {
                    handler: _this.renderGraphicChild
                },
                Pie: {
                    handler: _this.renderGraphicChild
                },
                Funnel: {
                    handler: _this.renderGraphicChild
                },
                Tooltip: {
                    handler: _this.renderCursor,
                    once: true
                },
                PolarGrid: {
                    handler: _this.renderPolarGrid,
                    once: true
                },
                PolarAngleAxis: {
                    handler: _this.renderPolarAxis
                },
                PolarRadiusAxis: {
                    handler: _this.renderPolarAxis
                },
                Customized: {
                    handler: _this.renderCustomized
                }
            });
            _this.clipPathId = "".concat((_props$id = _props.id) !== null && _props$id !== void 0 ? _props$id : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["uniqueId"])('recharts'), "-clip");
            // trigger 60fps
            _this.throttleTriggeredAfterMouseMove = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$throttle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_this.triggeredAfterMouseMove, (_props$throttleDelay = _props.throttleDelay) !== null && _props$throttleDelay !== void 0 ? _props$throttleDelay : 1000 / 60);
            _this.state = {};
            return _this;
        }
        _inherits(CategoricalChartWrapper, _Component);
        return _createClass(CategoricalChartWrapper, [
            {
                key: "componentDidMount",
                value: function componentDidMount() {
                    var _this$props$margin$le, _this$props$margin$to;
                    this.addListener();
                    this.accessibilityManager.setDetails({
                        container: this.container,
                        offset: {
                            left: (_this$props$margin$le = this.props.margin.left) !== null && _this$props$margin$le !== void 0 ? _this$props$margin$le : 0,
                            top: (_this$props$margin$to = this.props.margin.top) !== null && _this$props$margin$to !== void 0 ? _this$props$margin$to : 0
                        },
                        coordinateList: this.state.tooltipTicks,
                        mouseHandlerCallback: this.triggeredAfterMouseMove,
                        layout: this.props.layout
                    });
                    this.displayDefaultTooltip();
                }
            },
            {
                key: "displayDefaultTooltip",
                value: function displayDefaultTooltip() {
                    var _this$props5 = this.props, children = _this$props5.children, data = _this$props5.data, height = _this$props5.height, layout = _this$props5.layout;
                    var tooltipElem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"]);
                    // If the chart doesn't include a <Tooltip /> element, there's no tooltip to display
                    if (!tooltipElem) {
                        return;
                    }
                    var defaultIndex = tooltipElem.props.defaultIndex;
                    // Protect against runtime errors
                    if (typeof defaultIndex !== 'number' || defaultIndex < 0 || defaultIndex > this.state.tooltipTicks.length - 1) {
                        return;
                    }
                    var activeLabel = this.state.tooltipTicks[defaultIndex] && this.state.tooltipTicks[defaultIndex].value;
                    var activePayload = getTooltipContent(this.state, data, defaultIndex, activeLabel);
                    var independentAxisCoord = this.state.tooltipTicks[defaultIndex].coordinate;
                    var dependentAxisCoord = (this.state.offset.top + height) / 2;
                    var isHorizontal = layout === 'horizontal';
                    var activeCoordinate = isHorizontal ? {
                        x: independentAxisCoord,
                        y: dependentAxisCoord
                    } : {
                        y: independentAxisCoord,
                        x: dependentAxisCoord
                    };
                    // Unlike other chart types, scatter plot's tooltip positions rely on both X and Y coordinates. Only the scatter plot
                    // element knows its own Y coordinates.
                    // If there's a scatter plot, we'll want to grab that element for an interrogation.
                    var scatterPlotElement = this.state.formattedGraphicalItems.find(function(_ref12) {
                        var item = _ref12.item;
                        return item.type.name === 'Scatter';
                    });
                    if (scatterPlotElement) {
                        activeCoordinate = _objectSpread(_objectSpread({}, activeCoordinate), scatterPlotElement.props.points[defaultIndex].tooltipPosition);
                        activePayload = scatterPlotElement.props.points[defaultIndex].tooltipPayload;
                    }
                    var nextState = {
                        activeTooltipIndex: defaultIndex,
                        isTooltipActive: true,
                        activeLabel: activeLabel,
                        activePayload: activePayload,
                        activeCoordinate: activeCoordinate
                    };
                    this.setState(nextState);
                    this.renderCursor(tooltipElem);
                    // Make sure that anyone who keyboard-only users who tab to the chart will start their
                    // cursors at defaultIndex
                    this.accessibilityManager.setIndex(defaultIndex);
                }
            },
            {
                key: "getSnapshotBeforeUpdate",
                value: function getSnapshotBeforeUpdate(prevProps, prevState) {
                    if (!this.props.accessibilityLayer) {
                        return null;
                    }
                    if (this.state.tooltipTicks !== prevState.tooltipTicks) {
                        this.accessibilityManager.setDetails({
                            coordinateList: this.state.tooltipTicks
                        });
                    }
                    if (this.props.layout !== prevProps.layout) {
                        this.accessibilityManager.setDetails({
                            layout: this.props.layout
                        });
                    }
                    if (this.props.margin !== prevProps.margin) {
                        var _this$props$margin$le2, _this$props$margin$to2;
                        this.accessibilityManager.setDetails({
                            offset: {
                                left: (_this$props$margin$le2 = this.props.margin.left) !== null && _this$props$margin$le2 !== void 0 ? _this$props$margin$le2 : 0,
                                top: (_this$props$margin$to2 = this.props.margin.top) !== null && _this$props$margin$to2 !== void 0 ? _this$props$margin$to2 : 0
                            }
                        });
                    }
                    // Something has to be returned for getSnapshotBeforeUpdate
                    return null;
                }
            },
            {
                key: "componentDidUpdate",
                value: function componentDidUpdate(prevProps) {
                    // Check to see if the Tooltip updated. If so, re-check default tooltip position
                    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isChildrenEqual"])([
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(prevProps.children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"])
                    ], [
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(this.props.children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"])
                    ])) {
                        this.displayDefaultTooltip();
                    }
                }
            },
            {
                key: "componentWillUnmount",
                value: function componentWillUnmount() {
                    this.removeListener();
                    this.throttleTriggeredAfterMouseMove.cancel();
                }
            },
            {
                key: "getTooltipEventType",
                value: function getTooltipEventType() {
                    var tooltipItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(this.props.children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"]);
                    if (tooltipItem && typeof tooltipItem.props.shared === 'boolean') {
                        var eventType = tooltipItem.props.shared ? 'axis' : 'item';
                        return validateTooltipEventTypes.indexOf(eventType) >= 0 ? eventType : defaultTooltipEventType;
                    }
                    return defaultTooltipEventType;
                }
            },
            {
                key: "getMouseInfo",
                value: function getMouseInfo(event) {
                    if (!this.container) {
                        return null;
                    }
                    var element = this.container;
                    var boundingRect = element.getBoundingClientRect();
                    var containerOffset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOffset"])(boundingRect);
                    var e = {
                        chartX: Math.round(event.pageX - containerOffset.left),
                        chartY: Math.round(event.pageY - containerOffset.top)
                    };
                    var scale = boundingRect.width / element.offsetWidth || 1;
                    var rangeObj = this.inRange(e.chartX, e.chartY, scale);
                    if (!rangeObj) {
                        return null;
                    }
                    var _this$state9 = this.state, xAxisMap = _this$state9.xAxisMap, yAxisMap = _this$state9.yAxisMap;
                    var tooltipEventType = this.getTooltipEventType();
                    var toolTipData = getTooltipData(this.state, this.props.data, this.props.layout, rangeObj);
                    if (tooltipEventType !== 'axis' && xAxisMap && yAxisMap) {
                        var xScale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(xAxisMap).scale;
                        var yScale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(yAxisMap).scale;
                        var xValue = xScale && xScale.invert ? xScale.invert(e.chartX) : null;
                        var yValue = yScale && yScale.invert ? yScale.invert(e.chartY) : null;
                        return _objectSpread(_objectSpread({}, e), {}, {
                            xValue: xValue,
                            yValue: yValue
                        }, toolTipData);
                    }
                    if (toolTipData) {
                        return _objectSpread(_objectSpread({}, e), toolTipData);
                    }
                    return null;
                }
            },
            {
                key: "inRange",
                value: function inRange(x, y) {
                    var scale = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 1;
                    var layout = this.props.layout;
                    var scaledX = x / scale, scaledY = y / scale;
                    if (layout === 'horizontal' || layout === 'vertical') {
                        var offset = this.state.offset;
                        var isInRange = scaledX >= offset.left && scaledX <= offset.left + offset.width && scaledY >= offset.top && scaledY <= offset.top + offset.height;
                        return isInRange ? {
                            x: scaledX,
                            y: scaledY
                        } : null;
                    }
                    var _this$state10 = this.state, angleAxisMap = _this$state10.angleAxisMap, radiusAxisMap = _this$state10.radiusAxisMap;
                    if (angleAxisMap && radiusAxisMap) {
                        var angleAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAnyElementOfObject"])(angleAxisMap);
                        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["inRangeOfSector"])({
                            x: scaledX,
                            y: scaledY
                        }, angleAxis);
                    }
                    return null;
                }
            },
            {
                key: "parseEventsOfWrapper",
                value: function parseEventsOfWrapper() {
                    var children = this.props.children;
                    var tooltipEventType = this.getTooltipEventType();
                    var tooltipItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Tooltip$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"]);
                    var tooltipEvents = {};
                    if (tooltipItem && tooltipEventType === 'axis') {
                        if (tooltipItem.props.trigger === 'click') {
                            tooltipEvents = {
                                onClick: this.handleClick
                            };
                        } else {
                            tooltipEvents = {
                                onMouseEnter: this.handleMouseEnter,
                                onDoubleClick: this.handleDoubleClick,
                                onMouseMove: this.handleMouseMove,
                                onMouseLeave: this.handleMouseLeave,
                                onTouchMove: this.handleTouchMove,
                                onTouchStart: this.handleTouchStart,
                                onTouchEnd: this.handleTouchEnd,
                                onContextMenu: this.handleContextMenu
                            };
                        }
                    }
                    // @ts-expect-error adaptEventHandlers expects DOM Event but generateCategoricalChart works with React UIEvents
                    var outerEvents = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventHandlers"])(this.props, this.handleOuterEvent);
                    return _objectSpread(_objectSpread({}, outerEvents), tooltipEvents);
                }
            },
            {
                key: "addListener",
                value: function addListener() {
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["eventCenter"].on(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SYNC_EVENT"], this.handleReceiveSyncEvent);
                }
            },
            {
                key: "removeListener",
                value: function removeListener() {
                    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["eventCenter"].removeListener(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Events$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SYNC_EVENT"], this.handleReceiveSyncEvent);
                }
            },
            {
                key: "filterFormatItem",
                value: function filterFormatItem(item, displayName, childIndex) {
                    var formattedGraphicalItems = this.state.formattedGraphicalItems;
                    for(var i = 0, len = formattedGraphicalItems.length; i < len; i++){
                        var entry = formattedGraphicalItems[i];
                        if (entry.item === item || entry.props.key === item.key || displayName === (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDisplayName"])(entry.item.type) && childIndex === entry.childIndex) {
                            return entry;
                        }
                    }
                    return null;
                }
            },
            {
                key: "renderClipPath",
                value: function renderClipPath() {
                    var clipPathId = this.clipPathId;
                    var _this$state$offset = this.state.offset, left = _this$state$offset.left, top = _this$state$offset.top, height = _this$state$offset.height, width = _this$state$offset.width;
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("defs", null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("clipPath", {
                        id: clipPathId
                    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                        x: left,
                        y: top,
                        height: height,
                        width: width
                    })));
                }
            },
            {
                key: "getXScales",
                value: function getXScales() {
                    var xAxisMap = this.state.xAxisMap;
                    return xAxisMap ? Object.entries(xAxisMap).reduce(function(res, _ref13) {
                        var _ref14 = _slicedToArray(_ref13, 2), axisId = _ref14[0], axisProps = _ref14[1];
                        return _objectSpread(_objectSpread({}, res), {}, _defineProperty({}, axisId, axisProps.scale));
                    }, {}) : null;
                }
            },
            {
                key: "getYScales",
                value: function getYScales() {
                    var yAxisMap = this.state.yAxisMap;
                    return yAxisMap ? Object.entries(yAxisMap).reduce(function(res, _ref15) {
                        var _ref16 = _slicedToArray(_ref15, 2), axisId = _ref16[0], axisProps = _ref16[1];
                        return _objectSpread(_objectSpread({}, res), {}, _defineProperty({}, axisId, axisProps.scale));
                    }, {}) : null;
                }
            },
            {
                key: "getXScaleByAxisId",
                value: function getXScaleByAxisId(axisId) {
                    var _this$state$xAxisMap;
                    return (_this$state$xAxisMap = this.state.xAxisMap) === null || _this$state$xAxisMap === void 0 || (_this$state$xAxisMap = _this$state$xAxisMap[axisId]) === null || _this$state$xAxisMap === void 0 ? void 0 : _this$state$xAxisMap.scale;
                }
            },
            {
                key: "getYScaleByAxisId",
                value: function getYScaleByAxisId(axisId) {
                    var _this$state$yAxisMap;
                    return (_this$state$yAxisMap = this.state.yAxisMap) === null || _this$state$yAxisMap === void 0 || (_this$state$yAxisMap = _this$state$yAxisMap[axisId]) === null || _this$state$yAxisMap === void 0 ? void 0 : _this$state$yAxisMap.scale;
                }
            },
            {
                key: "getItemByXY",
                value: function getItemByXY(chartXY) {
                    var _this$state11 = this.state, formattedGraphicalItems = _this$state11.formattedGraphicalItems, activeItem = _this$state11.activeItem;
                    if (formattedGraphicalItems && formattedGraphicalItems.length) {
                        for(var i = 0, len = formattedGraphicalItems.length; i < len; i++){
                            var graphicalItem = formattedGraphicalItems[i];
                            // graphicalItem is not a React Element so we don't need to resolve defaultProps
                            var props = graphicalItem.props, item = graphicalItem.item;
                            var itemProps = item.type.defaultProps !== undefined ? _objectSpread(_objectSpread({}, item.type.defaultProps), item.props) : item.props;
                            var itemDisplayName = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDisplayName"])(item.type);
                            if (itemDisplayName === 'Bar') {
                                var activeBarItem = (props.data || []).find(function(entry) {
                                    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Rectangle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isInRectangle"])(chartXY, entry);
                                });
                                if (activeBarItem) {
                                    return {
                                        graphicalItem: graphicalItem,
                                        payload: activeBarItem
                                    };
                                }
                            } else if (itemDisplayName === 'RadialBar') {
                                var _activeBarItem = (props.data || []).find(function(entry) {
                                    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$PolarUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["inRangeOfSector"])(chartXY, entry);
                                });
                                if (_activeBarItem) {
                                    return {
                                        graphicalItem: graphicalItem,
                                        payload: _activeBarItem
                                    };
                                }
                            } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isFunnel"])(graphicalItem, activeItem) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPie"])(graphicalItem, activeItem) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isScatter"])(graphicalItem, activeItem)) {
                                var activeIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getActiveShapeIndexForTooltip"])({
                                    graphicalItem: graphicalItem,
                                    activeTooltipItem: activeItem,
                                    itemData: itemProps.data
                                });
                                var childIndex = itemProps.activeIndex === undefined ? activeIndex : itemProps.activeIndex;
                                return {
                                    graphicalItem: _objectSpread(_objectSpread({}, graphicalItem), {}, {
                                        childIndex: childIndex
                                    }),
                                    payload: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ActiveShapeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isScatter"])(graphicalItem, activeItem) ? itemProps.data[activeIndex] : graphicalItem.props.data[activeIndex]
                                };
                            }
                        }
                    }
                    return null;
                }
            },
            {
                key: "render",
                value: function render() {
                    var _this3 = this;
                    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["validateWidthHeight"])(this)) {
                        return null;
                    }
                    var _this$props6 = this.props, children = _this$props6.children, className = _this$props6.className, width = _this$props6.width, height = _this$props6.height, style = _this$props6.style, compact = _this$props6.compact, title = _this$props6.title, desc = _this$props6.desc, others = _objectWithoutProperties(_this$props6, _excluded2);
                    var attrs = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(others, false);
                    // The "compact" mode is mainly used as the panorama within Brush
                    if (compact) {
                        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ChartLayoutContextProvider"], {
                            state: this.state,
                            width: this.props.width,
                            height: this.props.height,
                            clipPathId: this.clipPathId
                        }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Surface$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Surface"], _extends({}, attrs, {
                            width: width,
                            height: height,
                            title: title,
                            desc: desc
                        }), this.renderClipPath(), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["renderByOrder"])(children, this.renderMap)));
                    }
                    if (this.props.accessibilityLayer) {
                        var _this$props$tabIndex, _this$props$role;
                        // Set tabIndex to 0 by default (can be overwritten)
                        attrs.tabIndex = (_this$props$tabIndex = this.props.tabIndex) !== null && _this$props$tabIndex !== void 0 ? _this$props$tabIndex : 0;
                        // Set role to img by default (can be overwritten)
                        attrs.role = (_this$props$role = this.props.role) !== null && _this$props$role !== void 0 ? _this$props$role : 'application';
                        attrs.onKeyDown = function(e) {
                            _this3.accessibilityManager.keyboardEvent(e);
                        // 'onKeyDown' is not currently a supported prop that can be passed through
                        // if it's added, this should be added: this.props.onKeyDown(e);
                        };
                        attrs.onFocus = function() {
                            _this3.accessibilityManager.focus();
                        // 'onFocus' is not currently a supported prop that can be passed through
                        // if it's added, the focus event should be forwarded to the prop
                        };
                    }
                    var events = this.parseEventsOfWrapper();
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ChartLayoutContextProvider"], {
                        state: this.state,
                        width: this.props.width,
                        height: this.props.height,
                        clipPathId: this.clipPathId
                    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", _extends({
                        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-wrapper', className),
                        style: _objectSpread({
                            position: 'relative',
                            cursor: 'default',
                            width: width,
                            height: height
                        }, style)
                    }, events, {
                        ref: function ref(node) {
                            _this3.container = node;
                        }
                    }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Surface$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Surface"], _extends({}, attrs, {
                        width: width,
                        height: height,
                        title: title,
                        desc: desc,
                        style: FULL_WIDTH_AND_HEIGHT
                    }), this.renderClipPath(), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["renderByOrder"])(children, this.renderMap)), this.renderLegend(), this.renderTooltip()));
                }
            }
        ]);
    }(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Component"]);
    _defineProperty(CategoricalChartWrapper, "displayName", chartName);
    // todo join specific chart propTypes
    _defineProperty(CategoricalChartWrapper, "defaultProps", _objectSpread({
        layout: 'horizontal',
        stackOffset: 'none',
        barCategoryGap: '10%',
        barGap: 4,
        margin: {
            top: 5,
            right: 5,
            bottom: 5,
            left: 5
        },
        reverseStackOrder: false,
        syncMethod: 'index'
    }, defaultProps));
    _defineProperty(CategoricalChartWrapper, "getDerivedStateFromProps", function(nextProps, prevState) {
        var dataKey = nextProps.dataKey, data = nextProps.data, children = nextProps.children, width = nextProps.width, height = nextProps.height, layout = nextProps.layout, stackOffset = nextProps.stackOffset, margin = nextProps.margin;
        var dataStartIndex = prevState.dataStartIndex, dataEndIndex = prevState.dataEndIndex;
        if (prevState.updateId === undefined) {
            var defaultState = createDefaultState(nextProps);
            return _objectSpread(_objectSpread(_objectSpread({}, defaultState), {}, {
                updateId: 0
            }, updateStateOfAxisMapsOffsetAndStackGroups(_objectSpread(_objectSpread({
                props: nextProps
            }, defaultState), {}, {
                updateId: 0
            }), prevState)), {}, {
                prevDataKey: dataKey,
                prevData: data,
                prevWidth: width,
                prevHeight: height,
                prevLayout: layout,
                prevStackOffset: stackOffset,
                prevMargin: margin,
                prevChildren: children
            });
        }
        if (dataKey !== prevState.prevDataKey || data !== prevState.prevData || width !== prevState.prevWidth || height !== prevState.prevHeight || layout !== prevState.prevLayout || stackOffset !== prevState.prevStackOffset || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["shallowEqual"])(margin, prevState.prevMargin)) {
            var _defaultState = createDefaultState(nextProps);
            // Fixes https://github.com/recharts/recharts/issues/2143
            var keepFromPrevState = {
                // (chartX, chartY) are (0,0) in default state, but we want to keep the last mouse position to avoid
                // any flickering
                chartX: prevState.chartX,
                chartY: prevState.chartY,
                // The tooltip should stay active when it was active in the previous render. If this is not
                // the case, the tooltip disappears and immediately re-appears, causing a flickering effect
                isTooltipActive: prevState.isTooltipActive
            };
            var updatesToState = _objectSpread(_objectSpread({}, getTooltipData(prevState, data, layout)), {}, {
                updateId: prevState.updateId + 1
            });
            var newState = _objectSpread(_objectSpread(_objectSpread({}, _defaultState), keepFromPrevState), updatesToState);
            return _objectSpread(_objectSpread(_objectSpread({}, newState), updateStateOfAxisMapsOffsetAndStackGroups(_objectSpread({
                props: nextProps
            }, newState), prevState)), {}, {
                prevDataKey: dataKey,
                prevData: data,
                prevWidth: width,
                prevHeight: height,
                prevLayout: layout,
                prevStackOffset: stackOffset,
                prevMargin: margin,
                prevChildren: children
            });
        }
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isChildrenEqual"])(children, prevState.prevChildren)) {
            var _brush$props$startInd, _brush$props, _brush$props$endIndex, _brush$props2;
            // specifically check for Brush - if it exists and the start and end indexes are different, re-render with the new ones
            var brush = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["findChildByType"])(children, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Brush$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Brush"]);
            var startIndex = brush ? (_brush$props$startInd = (_brush$props = brush.props) === null || _brush$props === void 0 ? void 0 : _brush$props.startIndex) !== null && _brush$props$startInd !== void 0 ? _brush$props$startInd : dataStartIndex : dataStartIndex;
            var endIndex = brush ? (_brush$props$endIndex = (_brush$props2 = brush.props) === null || _brush$props2 === void 0 ? void 0 : _brush$props2.endIndex) !== null && _brush$props$endIndex !== void 0 ? _brush$props$endIndex : dataEndIndex : dataEndIndex;
            var hasDifferentStartOrEndIndex = startIndex !== dataStartIndex || endIndex !== dataEndIndex;
            // update configuration in children
            var hasGlobalData = !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(data);
            var newUpdateId = hasGlobalData && !hasDifferentStartOrEndIndex ? prevState.updateId : prevState.updateId + 1;
            return _objectSpread(_objectSpread({
                updateId: newUpdateId
            }, updateStateOfAxisMapsOffsetAndStackGroups(_objectSpread(_objectSpread({
                props: nextProps
            }, prevState), {}, {
                updateId: newUpdateId,
                dataStartIndex: startIndex,
                dataEndIndex: endIndex
            }), prevState)), {}, {
                prevChildren: children,
                dataStartIndex: startIndex,
                dataEndIndex: endIndex
            });
        }
        return null;
    });
    _defineProperty(CategoricalChartWrapper, "renderActiveDot", function(option, props, key) {
        var dot;
        if (/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(option)) {
            dot = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(option, props);
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
            dot = option(props);
        } else {
            dot = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Dot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dot"], props);
        }
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
            className: "recharts-active-dot",
            key: key
        }, dot);
    });
    var CategoricalChart = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"])(function CategoricalChart(props, ref) {
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(CategoricalChartWrapper, _extends({}, props, {
            ref: ref
        }));
    });
    CategoricalChart.displayName = CategoricalChartWrapper.displayName;
    return CategoricalChart;
};
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/Area.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Area",
    ()=>Area
]);
/**
 * @fileOverview Area
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-smooth/es6/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/max.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isNaN.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Curve.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Dot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/shape/Dot.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$LabelList$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/LabelList.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var _excluded = [
    "layout",
    "type",
    "stroke",
    "connectNulls",
    "isRange",
    "ref"
], _excluded2 = [
    "key"
];
var _Area;
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
var Area = /*#__PURE__*/ function(_PureComponent) {
    function Area() {
        var _this;
        _classCallCheck(this, Area);
        for(var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++){
            args[_key] = arguments[_key];
        }
        _this = _callSuper(this, Area, [].concat(args));
        _defineProperty(_this, "state", {
            isAnimationFinished: true
        });
        _defineProperty(_this, "id", (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["uniqueId"])('recharts-area-'));
        _defineProperty(_this, "handleAnimationEnd", function() {
            var onAnimationEnd = _this.props.onAnimationEnd;
            _this.setState({
                isAnimationFinished: true
            });
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onAnimationEnd)) {
                onAnimationEnd();
            }
        });
        _defineProperty(_this, "handleAnimationStart", function() {
            var onAnimationStart = _this.props.onAnimationStart;
            _this.setState({
                isAnimationFinished: false
            });
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(onAnimationStart)) {
                onAnimationStart();
            }
        });
        return _this;
    }
    _inherits(Area, _PureComponent);
    return _createClass(Area, [
        {
            key: "renderDots",
            value: function renderDots(needClip, clipDot, clipPathId) {
                var isAnimationActive = this.props.isAnimationActive;
                var isAnimationFinished = this.state.isAnimationFinished;
                if (isAnimationActive && !isAnimationFinished) {
                    return null;
                }
                var _this$props = this.props, dot = _this$props.dot, points = _this$props.points, dataKey = _this$props.dataKey;
                var areaProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false);
                var customDotProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(dot, true);
                var dots = points.map(function(entry, i) {
                    var dotProps = _objectSpread(_objectSpread(_objectSpread({
                        key: "dot-".concat(i),
                        r: 3
                    }, areaProps), customDotProps), {}, {
                        index: i,
                        cx: entry.x,
                        cy: entry.y,
                        dataKey: dataKey,
                        value: entry.value,
                        payload: entry.payload,
                        points: points
                    });
                    return Area.renderDotItem(dot, dotProps);
                });
                var dotsProps = {
                    clipPath: needClip ? "url(#clipPath-".concat(clipDot ? '' : 'dots-').concat(clipPathId, ")") : null
                };
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], _extends({
                    className: "recharts-area-dots"
                }, dotsProps), dots);
            }
        },
        {
            key: "renderHorizontalRect",
            value: function renderHorizontalRect(alpha) {
                var _this$props2 = this.props, baseLine = _this$props2.baseLine, points = _this$props2.points, strokeWidth = _this$props2.strokeWidth;
                var startX = points[0].x;
                var endX = points[points.length - 1].x;
                var width = alpha * Math.abs(startX - endX);
                var maxY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(points.map(function(entry) {
                    return entry.y || 0;
                }));
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(baseLine) && typeof baseLine === 'number') {
                    maxY = Math.max(baseLine, maxY);
                } else if (baseLine && Array.isArray(baseLine) && baseLine.length) {
                    maxY = Math.max((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(baseLine.map(function(entry) {
                        return entry.y || 0;
                    })), maxY);
                }
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(maxY)) {
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                        x: startX < endX ? startX : startX - width,
                        y: 0,
                        width: width,
                        height: Math.floor(maxY + (strokeWidth ? parseInt("".concat(strokeWidth), 10) : 1))
                    });
                }
                return null;
            }
        },
        {
            key: "renderVerticalRect",
            value: function renderVerticalRect(alpha) {
                var _this$props3 = this.props, baseLine = _this$props3.baseLine, points = _this$props3.points, strokeWidth = _this$props3.strokeWidth;
                var startY = points[0].y;
                var endY = points[points.length - 1].y;
                var height = alpha * Math.abs(startY - endY);
                var maxX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(points.map(function(entry) {
                    return entry.x || 0;
                }));
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(baseLine) && typeof baseLine === 'number') {
                    maxX = Math.max(baseLine, maxX);
                } else if (baseLine && Array.isArray(baseLine) && baseLine.length) {
                    maxX = Math.max((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$max$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(baseLine.map(function(entry) {
                        return entry.x || 0;
                    })), maxX);
                }
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(maxX)) {
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                        x: 0,
                        y: startY < endY ? startY : startY - height,
                        width: maxX + (strokeWidth ? parseInt("".concat(strokeWidth), 10) : 1),
                        height: Math.floor(height)
                    });
                }
                return null;
            }
        },
        {
            key: "renderClipRect",
            value: function renderClipRect(alpha) {
                var layout = this.props.layout;
                if (layout === 'vertical') {
                    return this.renderVerticalRect(alpha);
                }
                return this.renderHorizontalRect(alpha);
            }
        },
        {
            key: "renderAreaStatically",
            value: function renderAreaStatically(points, baseLine, needClip, clipPathId) {
                var _this$props4 = this.props, layout = _this$props4.layout, type = _this$props4.type, stroke = _this$props4.stroke, connectNulls = _this$props4.connectNulls, isRange = _this$props4.isRange, ref = _this$props4.ref, others = _objectWithoutProperties(_this$props4, _excluded);
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    clipPath: needClip ? "url(#clipPath-".concat(clipPathId, ")") : null
                }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Curve"], _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(others, true), {
                    points: points,
                    connectNulls: connectNulls,
                    type: type,
                    baseLine: baseLine,
                    layout: layout,
                    stroke: "none",
                    className: "recharts-area-area"
                })), stroke !== 'none' && /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Curve"], _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false), {
                    className: "recharts-area-curve",
                    layout: layout,
                    type: type,
                    connectNulls: connectNulls,
                    fill: "none",
                    points: points
                })), stroke !== 'none' && isRange && /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Curve$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Curve"], _extends({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false), {
                    className: "recharts-area-curve",
                    layout: layout,
                    type: type,
                    connectNulls: connectNulls,
                    fill: "none",
                    points: baseLine
                })));
            }
        },
        {
            key: "renderAreaWithAnimation",
            value: function renderAreaWithAnimation(needClip, clipPathId) {
                var _this2 = this;
                var _this$props5 = this.props, points = _this$props5.points, baseLine = _this$props5.baseLine, isAnimationActive = _this$props5.isAnimationActive, animationBegin = _this$props5.animationBegin, animationDuration = _this$props5.animationDuration, animationEasing = _this$props5.animationEasing, animationId = _this$props5.animationId;
                var _this$state = this.state, prevPoints = _this$state.prevPoints, prevBaseLine = _this$state.prevBaseLine;
                // const clipPathId = isNil(id) ? this.id : id;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$smooth$2f$es6$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["default"], {
                    begin: animationBegin,
                    duration: animationDuration,
                    isActive: isAnimationActive,
                    easing: animationEasing,
                    from: {
                        t: 0
                    },
                    to: {
                        t: 1
                    },
                    key: "area-".concat(animationId),
                    onAnimationEnd: this.handleAnimationEnd,
                    onAnimationStart: this.handleAnimationStart
                }, function(_ref) {
                    var t = _ref.t;
                    if (prevPoints) {
                        var prevPointsDiffFactor = prevPoints.length / points.length;
                        // update animtaion
                        var stepPoints = points.map(function(entry, index) {
                            var prevPointIndex = Math.floor(index * prevPointsDiffFactor);
                            if (prevPoints[prevPointIndex]) {
                                var prev = prevPoints[prevPointIndex];
                                var interpolatorX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.x, entry.x);
                                var interpolatorY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.y, entry.y);
                                return _objectSpread(_objectSpread({}, entry), {}, {
                                    x: interpolatorX(t),
                                    y: interpolatorY(t)
                                });
                            }
                            return entry;
                        });
                        var stepBaseLine;
                        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(baseLine) && typeof baseLine === 'number') {
                            var interpolator = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prevBaseLine, baseLine);
                            stepBaseLine = interpolator(t);
                        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(baseLine) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNaN$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(baseLine)) {
                            var _interpolator = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prevBaseLine, 0);
                            stepBaseLine = _interpolator(t);
                        } else {
                            stepBaseLine = baseLine.map(function(entry, index) {
                                var prevPointIndex = Math.floor(index * prevPointsDiffFactor);
                                if (prevBaseLine[prevPointIndex]) {
                                    var prev = prevBaseLine[prevPointIndex];
                                    var interpolatorX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.x, entry.x);
                                    var interpolatorY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["interpolateNumber"])(prev.y, entry.y);
                                    return _objectSpread(_objectSpread({}, entry), {}, {
                                        x: interpolatorX(t),
                                        y: interpolatorY(t)
                                    });
                                }
                                return entry;
                            });
                        }
                        return _this2.renderAreaStatically(stepPoints, stepBaseLine, needClip, clipPathId);
                    }
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("defs", null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("clipPath", {
                        id: "animationClipPath-".concat(clipPathId)
                    }, _this2.renderClipRect(t))), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                        clipPath: "url(#animationClipPath-".concat(clipPathId, ")")
                    }, _this2.renderAreaStatically(points, baseLine, needClip, clipPathId)));
                });
            }
        },
        {
            key: "renderArea",
            value: function renderArea(needClip, clipPathId) {
                var _this$props6 = this.props, points = _this$props6.points, baseLine = _this$props6.baseLine, isAnimationActive = _this$props6.isAnimationActive;
                var _this$state2 = this.state, prevPoints = _this$state2.prevPoints, prevBaseLine = _this$state2.prevBaseLine, totalLength = _this$state2.totalLength;
                if (isAnimationActive && points && points.length && (!prevPoints && totalLength > 0 || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(prevPoints, points) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(prevBaseLine, baseLine))) {
                    return this.renderAreaWithAnimation(needClip, clipPathId);
                }
                return this.renderAreaStatically(points, baseLine, needClip, clipPathId);
            }
        },
        {
            key: "render",
            value: function render() {
                var _filterProps;
                var _this$props7 = this.props, hide = _this$props7.hide, dot = _this$props7.dot, points = _this$props7.points, className = _this$props7.className, top = _this$props7.top, left = _this$props7.left, xAxis = _this$props7.xAxis, yAxis = _this$props7.yAxis, width = _this$props7.width, height = _this$props7.height, isAnimationActive = _this$props7.isAnimationActive, id = _this$props7.id;
                if (hide || !points || !points.length) {
                    return null;
                }
                var isAnimationFinished = this.state.isAnimationFinished;
                var hasSinglePoint = points.length === 1;
                var layerClass = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-area', className);
                var needClipX = xAxis && xAxis.allowDataOverflow;
                var needClipY = yAxis && yAxis.allowDataOverflow;
                var needClip = needClipX || needClipY;
                var clipPathId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isNil$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(id) ? this.id : id;
                var _ref2 = (_filterProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(dot, false)) !== null && _filterProps !== void 0 ? _filterProps : {
                    r: 3,
                    strokeWidth: 2
                }, _ref2$r = _ref2.r, r = _ref2$r === void 0 ? 3 : _ref2$r, _ref2$strokeWidth = _ref2.strokeWidth, strokeWidth = _ref2$strokeWidth === void 0 ? 2 : _ref2$strokeWidth;
                var _ref3 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["hasClipDot"])(dot) ? dot : {}, _ref3$clipDot = _ref3.clipDot, clipDot = _ref3$clipDot === void 0 ? true : _ref3$clipDot;
                var dotSize = r * 2 + strokeWidth;
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: layerClass
                }, needClipX || needClipY ? /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("defs", null, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("clipPath", {
                    id: "clipPath-".concat(clipPathId)
                }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                    x: needClipX ? left : left - width / 2,
                    y: needClipY ? top : top - height / 2,
                    width: needClipX ? width : width * 2,
                    height: needClipY ? height : height * 2
                })), !clipDot && /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("clipPath", {
                    id: "clipPath-dots-".concat(clipPathId)
                }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
                    x: left - dotSize / 2,
                    y: top - dotSize / 2,
                    width: width + dotSize,
                    height: height + dotSize
                }))) : null, !hasSinglePoint ? this.renderArea(needClip, clipPathId) : null, (dot || hasSinglePoint) && this.renderDots(needClip, clipDot, clipPathId), (!isAnimationActive || isAnimationFinished) && __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$LabelList$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LabelList"].renderCallByParent(this.props, points));
            }
        }
    ], [
        {
            key: "getDerivedStateFromProps",
            value: function getDerivedStateFromProps(nextProps, prevState) {
                if (nextProps.animationId !== prevState.prevAnimationId) {
                    return {
                        prevAnimationId: nextProps.animationId,
                        curPoints: nextProps.points,
                        curBaseLine: nextProps.baseLine,
                        prevPoints: prevState.curPoints,
                        prevBaseLine: prevState.curBaseLine
                    };
                }
                if (nextProps.points !== prevState.curPoints || nextProps.baseLine !== prevState.curBaseLine) {
                    return {
                        curPoints: nextProps.points,
                        curBaseLine: nextProps.baseLine
                    };
                }
                return null;
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PureComponent"]);
_Area = Area;
_defineProperty(Area, "displayName", 'Area');
_defineProperty(Area, "defaultProps", {
    stroke: '#3182bd',
    fill: '#3182bd',
    fillOpacity: 0.6,
    xAxisId: 0,
    yAxisId: 0,
    legendType: 'line',
    connectNulls: false,
    // points of area
    points: [],
    dot: false,
    activeDot: true,
    hide: false,
    isAnimationActive: !__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Global"].isSsr,
    animationBegin: 0,
    animationDuration: 1500,
    animationEasing: 'ease'
});
_defineProperty(Area, "getBaseValue", function(props, item, xAxis, yAxis) {
    var layout = props.layout, chartBaseValue = props.baseValue;
    var itemBaseValue = item.props.baseValue;
    // The baseValue can be defined both on the AreaChart as well as on the Area.
    // The value for the item takes precedence.
    var baseValue = itemBaseValue !== null && itemBaseValue !== void 0 ? itemBaseValue : chartBaseValue;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(baseValue) && typeof baseValue === 'number') {
        return baseValue;
    }
    var numericAxis = layout === 'horizontal' ? yAxis : xAxis;
    var domain = numericAxis.scale.domain();
    if (numericAxis.type === 'number') {
        var domainMax = Math.max(domain[0], domain[1]);
        var domainMin = Math.min(domain[0], domain[1]);
        if (baseValue === 'dataMin') {
            return domainMin;
        }
        if (baseValue === 'dataMax') {
            return domainMax;
        }
        return domainMax < 0 ? domainMax : Math.max(Math.min(domain[0], domain[1]), 0);
    }
    if (baseValue === 'dataMin') {
        return domain[0];
    }
    if (baseValue === 'dataMax') {
        return domain[1];
    }
    return domain[0];
});
_defineProperty(Area, "getComposedData", function(_ref4) {
    var props = _ref4.props, item = _ref4.item, xAxis = _ref4.xAxis, yAxis = _ref4.yAxis, xAxisTicks = _ref4.xAxisTicks, yAxisTicks = _ref4.yAxisTicks, bandSize = _ref4.bandSize, dataKey = _ref4.dataKey, stackedData = _ref4.stackedData, dataStartIndex = _ref4.dataStartIndex, displayedData = _ref4.displayedData, offset = _ref4.offset;
    var layout = props.layout;
    var hasStack = stackedData && stackedData.length;
    var baseValue = _Area.getBaseValue(props, item, xAxis, yAxis);
    var isHorizontalLayout = layout === 'horizontal';
    var isRange = false;
    var points = displayedData.map(function(entry, index) {
        var value;
        if (hasStack) {
            value = stackedData[dataStartIndex + index];
        } else {
            value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getValueByDataKey"])(entry, dataKey);
            if (!Array.isArray(value)) {
                value = [
                    baseValue,
                    value
                ];
            } else {
                isRange = true;
            }
        }
        var isBreakPoint = value[1] == null || hasStack && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getValueByDataKey"])(entry, dataKey) == null;
        if (isHorizontalLayout) {
            return {
                x: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCateCoordinateOfLine"])({
                    axis: xAxis,
                    ticks: xAxisTicks,
                    bandSize: bandSize,
                    entry: entry,
                    index: index
                }),
                y: isBreakPoint ? null : yAxis.scale(value[1]),
                value: value,
                payload: entry
            };
        }
        return {
            x: isBreakPoint ? null : xAxis.scale(value[1]),
            y: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCateCoordinateOfLine"])({
                axis: yAxis,
                ticks: yAxisTicks,
                bandSize: bandSize,
                entry: entry,
                index: index
            }),
            value: value,
            payload: entry
        };
    });
    var baseLine;
    if (hasStack || isRange) {
        baseLine = points.map(function(entry) {
            var x = Array.isArray(entry.value) ? entry.value[0] : null;
            if (isHorizontalLayout) {
                return {
                    x: entry.x,
                    y: x != null && entry.y != null ? yAxis.scale(x) : null
                };
            }
            return {
                x: x != null ? xAxis.scale(x) : null,
                y: entry.y
            };
        });
    } else {
        baseLine = isHorizontalLayout ? yAxis.scale(baseValue) : xAxis.scale(baseValue);
    }
    return _objectSpread({
        points: points,
        baseLine: baseLine,
        layout: layout,
        isRange: isRange
    }, offset);
});
_defineProperty(Area, "renderDotItem", function(option, props) {
    var dotItem;
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
        dotItem = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, props);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        dotItem = option(props);
    } else {
        var className = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-area-dot', typeof option !== 'boolean' ? option.className : '');
        var key = props.key, rest = _objectWithoutProperties(props, _excluded2);
        dotItem = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$shape$2f$Dot$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Dot"], _extends({}, rest, {
            key: key,
            className: className
        }));
    }
    return dotItem;
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/getEveryNthWithCondition.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Given an array and a number N, return a new array which contains every nTh
 * element of the input array. For n below 1, an empty array is returned.
 * If isValid is provided, all candidates must suffice the condition, else undefined is returned.
 * @param {T[]} array An input array.
 * @param {integer} n A number
 * @param {Function} isValid A function to evaluate a candidate form the array
 * @returns {T[]} The result array of the same type as the input array.
 */ __turbopack_context__.s([
    "getEveryNthWithCondition",
    ()=>getEveryNthWithCondition
]);
function getEveryNthWithCondition(array, n, isValid) {
    if (n < 1) {
        return [];
    }
    if (n === 1 && isValid === undefined) {
        return array;
    }
    var result = [];
    for(var i = 0; i < array.length; i += n){
        if (isValid === undefined || isValid(array[i]) === true) {
            result.push(array[i]);
        } else {
            return undefined;
        }
    }
    return result;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/TickUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getAngledTickWidth",
    ()=>getAngledTickWidth,
    "getNumberIntervalTicks",
    ()=>getNumberIntervalTicks,
    "getTickBoundaries",
    ()=>getTickBoundaries,
    "isVisible",
    ()=>isVisible
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CartesianUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getEveryNthWithCondition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/getEveryNthWithCondition.js [app-client] (ecmascript)");
;
;
function getAngledTickWidth(contentSize, unitSize, angle) {
    var size = {
        width: contentSize.width + unitSize.width,
        height: contentSize.height + unitSize.height
    };
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAngledRectangleWidth"])(size, angle);
}
function getTickBoundaries(viewBox, sign, sizeKey) {
    var isWidth = sizeKey === 'width';
    var x = viewBox.x, y = viewBox.y, width = viewBox.width, height = viewBox.height;
    if (sign === 1) {
        return {
            start: isWidth ? x : y,
            end: isWidth ? x + width : y + height
        };
    }
    return {
        start: isWidth ? x + width : y + height,
        end: isWidth ? x : y
    };
}
function isVisible(sign, tickPosition, getSize, start, end) {
    /* Since getSize() is expensive (it reads the ticks' size from the DOM), we do this check first to avoid calculating
   * the tick's size. */ if (sign * tickPosition < sign * start || sign * tickPosition > sign * end) {
        return false;
    }
    var size = getSize();
    return sign * (tickPosition - sign * size / 2 - start) >= 0 && sign * (tickPosition + sign * size / 2 - end) <= 0;
}
function getNumberIntervalTicks(ticks, interval) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getEveryNthWithCondition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getEveryNthWithCondition"])(ticks, interval + 1);
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/getEquidistantTicks.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getEquidistantTicks",
    ()=>getEquidistantTicks
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/TickUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getEveryNthWithCondition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/getEveryNthWithCondition.js [app-client] (ecmascript)");
;
;
function getEquidistantTicks(sign, boundaries, getTickSize, ticks, minTickGap) {
    var result = (ticks || []).slice();
    var initialStart = boundaries.start, end = boundaries.end;
    var index = 0;
    // Premature optimisation idea 1: Estimate a lower bound, and start from there.
    // For now, start from every tick
    var stepsize = 1;
    var start = initialStart;
    var _loop = function _loop() {
        // Given stepsize, evaluate whether every stepsize-th tick can be shown.
        // If it can not, then increase the stepsize by 1, and try again.
        var entry = ticks === null || ticks === void 0 ? void 0 : ticks[index];
        // Break condition - If we have evaluate all the ticks, then we are done.
        if (entry === undefined) {
            return {
                v: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$getEveryNthWithCondition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getEveryNthWithCondition"])(ticks, stepsize)
            };
        }
        // Check if the element collides with the next element
        var i = index;
        var size;
        var getSize = function getSize() {
            if (size === undefined) {
                size = getTickSize(entry, i);
            }
            return size;
        };
        var tickCoord = entry.coordinate;
        // We will always show the first tick.
        var isShow = index === 0 || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isVisible"])(sign, tickCoord, getSize, start, end);
        if (!isShow) {
            // Start all over with a larger stepsize
            index = 0;
            start = initialStart;
            stepsize += 1;
        }
        if (isShow) {
            // If it can be shown, update the start
            start = tickCoord + sign * (getSize() / 2 + minTickGap);
            index += stepsize;
        }
    }, _ret;
    while(stepsize <= result.length){
        _ret = _loop();
        if (_ret) return _ret.v;
    }
    return [];
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/getTicks.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getTicks",
    ()=>getTicks
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DOMUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/Global.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/TickUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getEquidistantTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/getEquidistantTicks.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
;
;
;
;
;
;
function getTicksEnd(sign, boundaries, getTickSize, ticks, minTickGap) {
    var result = (ticks || []).slice();
    var len = result.length;
    var start = boundaries.start;
    var end = boundaries.end;
    var _loop = function _loop(i) {
        var entry = result[i];
        var size;
        var getSize = function getSize() {
            if (size === undefined) {
                size = getTickSize(entry, i);
            }
            return size;
        };
        if (i === len - 1) {
            var gap = sign * (entry.coordinate + sign * getSize() / 2 - end);
            result[i] = entry = _objectSpread(_objectSpread({}, entry), {}, {
                tickCoord: gap > 0 ? entry.coordinate - gap * sign : entry.coordinate
            });
        } else {
            result[i] = entry = _objectSpread(_objectSpread({}, entry), {}, {
                tickCoord: entry.coordinate
            });
        }
        var isShow = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isVisible"])(sign, entry.tickCoord, getSize, start, end);
        if (isShow) {
            end = entry.tickCoord - sign * (getSize() / 2 + minTickGap);
            result[i] = _objectSpread(_objectSpread({}, entry), {}, {
                isShow: true
            });
        }
    };
    for(var i = len - 1; i >= 0; i--){
        _loop(i);
    }
    return result;
}
function getTicksStart(sign, boundaries, getTickSize, ticks, minTickGap, preserveEnd) {
    var result = (ticks || []).slice();
    var len = result.length;
    var start = boundaries.start, end = boundaries.end;
    if (preserveEnd) {
        // Try to guarantee the tail to be displayed
        var tail = ticks[len - 1];
        var tailSize = getTickSize(tail, len - 1);
        var tailGap = sign * (tail.coordinate + sign * tailSize / 2 - end);
        result[len - 1] = tail = _objectSpread(_objectSpread({}, tail), {}, {
            tickCoord: tailGap > 0 ? tail.coordinate - tailGap * sign : tail.coordinate
        });
        var isTailShow = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isVisible"])(sign, tail.tickCoord, function() {
            return tailSize;
        }, start, end);
        if (isTailShow) {
            end = tail.tickCoord - sign * (tailSize / 2 + minTickGap);
            result[len - 1] = _objectSpread(_objectSpread({}, tail), {}, {
                isShow: true
            });
        }
    }
    var count = preserveEnd ? len - 1 : len;
    var _loop2 = function _loop2(i) {
        var entry = result[i];
        var size;
        var getSize = function getSize() {
            if (size === undefined) {
                size = getTickSize(entry, i);
            }
            return size;
        };
        if (i === 0) {
            var gap = sign * (entry.coordinate - sign * getSize() / 2 - start);
            result[i] = entry = _objectSpread(_objectSpread({}, entry), {}, {
                tickCoord: gap < 0 ? entry.coordinate - gap * sign : entry.coordinate
            });
        } else {
            result[i] = entry = _objectSpread(_objectSpread({}, entry), {}, {
                tickCoord: entry.coordinate
            });
        }
        var isShow = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isVisible"])(sign, entry.tickCoord, getSize, start, end);
        if (isShow) {
            start = entry.tickCoord + sign * (getSize() / 2 + minTickGap);
            result[i] = _objectSpread(_objectSpread({}, entry), {}, {
                isShow: true
            });
        }
    };
    for(var i = 0; i < count; i++){
        _loop2(i);
    }
    return result;
}
function getTicks(props, fontSize, letterSpacing) {
    var tick = props.tick, ticks = props.ticks, viewBox = props.viewBox, minTickGap = props.minTickGap, orientation = props.orientation, interval = props.interval, tickFormatter = props.tickFormatter, unit = props.unit, angle = props.angle;
    if (!ticks || !ticks.length || !tick) {
        return [];
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(interval) || __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$Global$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Global"].isSsr) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNumberIntervalTicks"])(ticks, typeof interval === 'number' && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(interval) ? interval : 0);
    }
    var candidates = [];
    var sizeKey = orientation === 'top' || orientation === 'bottom' ? 'width' : 'height';
    var unitSize = unit && sizeKey === 'width' ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getStringSize"])(unit, {
        fontSize: fontSize,
        letterSpacing: letterSpacing
    }) : {
        width: 0,
        height: 0
    };
    var getTickSize = function getTickSize(content, index) {
        var value = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tickFormatter) ? tickFormatter(content.value, index) : content.value;
        // Recharts only supports angles when sizeKey === 'width'
        return sizeKey === 'width' ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAngledTickWidth"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getStringSize"])(value, {
            fontSize: fontSize,
            letterSpacing: letterSpacing
        }), unitSize, angle) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DOMUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getStringSize"])(value, {
            fontSize: fontSize,
            letterSpacing: letterSpacing
        })[sizeKey];
    };
    var sign = ticks.length >= 2 ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mathSign"])(ticks[1].coordinate - ticks[0].coordinate) : 1;
    var boundaries = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$TickUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTickBoundaries"])(viewBox, sign, sizeKey);
    if (interval === 'equidistantPreserveStart') {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getEquidistantTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getEquidistantTicks"])(sign, boundaries, getTickSize, ticks, minTickGap);
    }
    if (interval === 'preserveStart' || interval === 'preserveStartEnd') {
        candidates = getTicksStart(sign, boundaries, getTickSize, ticks, minTickGap, interval === 'preserveStartEnd');
    } else {
        candidates = getTicksEnd(sign, boundaries, getTickSize, ticks, minTickGap);
    }
    return candidates.filter(function(entry) {
        return entry.isShow;
    });
}
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/CartesianAxis.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CartesianAxis",
    ()=>CartesianAxis
]);
/**
 * @fileOverview Cartesian Axis
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ShallowEqual.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/container/Layer.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Text.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/Label.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/types.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/getTicks.js [app-client] (ecmascript)");
var _excluded = [
    "viewBox"
], _excluded2 = [
    "viewBox"
], _excluded3 = [
    "ticks"
];
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
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
var CartesianAxis = /*#__PURE__*/ function(_Component) {
    function CartesianAxis(props) {
        var _this;
        _classCallCheck(this, CartesianAxis);
        _this = _callSuper(this, CartesianAxis, [
            props
        ]);
        _this.state = {
            fontSize: '',
            letterSpacing: ''
        };
        return _this;
    }
    _inherits(CartesianAxis, _Component);
    return _createClass(CartesianAxis, [
        {
            key: "shouldComponentUpdate",
            value: function shouldComponentUpdate(_ref, nextState) {
                var viewBox = _ref.viewBox, restProps = _objectWithoutProperties(_ref, _excluded);
                // props.viewBox is sometimes generated every time -
                // check that specially as object equality is likely to fail
                var _this$props = this.props, viewBoxOld = _this$props.viewBox, restPropsOld = _objectWithoutProperties(_this$props, _excluded2);
                return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["shallowEqual"])(viewBox, viewBoxOld) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["shallowEqual"])(restProps, restPropsOld) || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ShallowEqual$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["shallowEqual"])(nextState, this.state);
            }
        },
        {
            key: "componentDidMount",
            value: function componentDidMount() {
                var htmlLayer = this.layerReference;
                if (!htmlLayer) return;
                var tick = htmlLayer.getElementsByClassName('recharts-cartesian-axis-tick-value')[0];
                if (tick) {
                    this.setState({
                        fontSize: window.getComputedStyle(tick).fontSize,
                        letterSpacing: window.getComputedStyle(tick).letterSpacing
                    });
                }
            }
        },
        {
            key: "getTickLineCoord",
            value: function getTickLineCoord(data) {
                var _this$props2 = this.props, x = _this$props2.x, y = _this$props2.y, width = _this$props2.width, height = _this$props2.height, orientation = _this$props2.orientation, tickSize = _this$props2.tickSize, mirror = _this$props2.mirror, tickMargin = _this$props2.tickMargin;
                var x1, x2, y1, y2, tx, ty;
                var sign = mirror ? -1 : 1;
                var finalTickSize = data.tickSize || tickSize;
                var tickCoord = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(data.tickCoord) ? data.tickCoord : data.coordinate;
                switch(orientation){
                    case 'top':
                        x1 = x2 = data.coordinate;
                        y2 = y + +!mirror * height;
                        y1 = y2 - sign * finalTickSize;
                        ty = y1 - sign * tickMargin;
                        tx = tickCoord;
                        break;
                    case 'left':
                        y1 = y2 = data.coordinate;
                        x2 = x + +!mirror * width;
                        x1 = x2 - sign * finalTickSize;
                        tx = x1 - sign * tickMargin;
                        ty = tickCoord;
                        break;
                    case 'right':
                        y1 = y2 = data.coordinate;
                        x2 = x + +mirror * width;
                        x1 = x2 + sign * finalTickSize;
                        tx = x1 + sign * tickMargin;
                        ty = tickCoord;
                        break;
                    default:
                        x1 = x2 = data.coordinate;
                        y2 = y + +mirror * height;
                        y1 = y2 + sign * finalTickSize;
                        ty = y1 + sign * tickMargin;
                        tx = tickCoord;
                        break;
                }
                return {
                    line: {
                        x1: x1,
                        y1: y1,
                        x2: x2,
                        y2: y2
                    },
                    tick: {
                        x: tx,
                        y: ty
                    }
                };
            }
        },
        {
            key: "getTickTextAnchor",
            value: function getTickTextAnchor() {
                var _this$props3 = this.props, orientation = _this$props3.orientation, mirror = _this$props3.mirror;
                var textAnchor;
                switch(orientation){
                    case 'left':
                        textAnchor = mirror ? 'start' : 'end';
                        break;
                    case 'right':
                        textAnchor = mirror ? 'end' : 'start';
                        break;
                    default:
                        textAnchor = 'middle';
                        break;
                }
                return textAnchor;
            }
        },
        {
            key: "getTickVerticalAnchor",
            value: function getTickVerticalAnchor() {
                var _this$props4 = this.props, orientation = _this$props4.orientation, mirror = _this$props4.mirror;
                var verticalAnchor = 'end';
                switch(orientation){
                    case 'left':
                    case 'right':
                        verticalAnchor = 'middle';
                        break;
                    case 'top':
                        verticalAnchor = mirror ? 'start' : 'end';
                        break;
                    default:
                        verticalAnchor = mirror ? 'end' : 'start';
                        break;
                }
                return verticalAnchor;
            }
        },
        {
            key: "renderAxisLine",
            value: function renderAxisLine() {
                var _this$props5 = this.props, x = _this$props5.x, y = _this$props5.y, width = _this$props5.width, height = _this$props5.height, orientation = _this$props5.orientation, mirror = _this$props5.mirror, axisLine = _this$props5.axisLine;
                var props = _objectSpread(_objectSpread(_objectSpread({}, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false)), (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(axisLine, false)), {}, {
                    fill: 'none'
                });
                if (orientation === 'top' || orientation === 'bottom') {
                    var needHeight = +(orientation === 'top' && !mirror || orientation === 'bottom' && mirror);
                    props = _objectSpread(_objectSpread({}, props), {}, {
                        x1: x,
                        y1: y + needHeight * height,
                        x2: x + width,
                        y2: y + needHeight * height
                    });
                } else {
                    var needWidth = +(orientation === 'left' && !mirror || orientation === 'right' && mirror);
                    props = _objectSpread(_objectSpread({}, props), {}, {
                        x1: x + needWidth * width,
                        y1: y,
                        x2: x + needWidth * width,
                        y2: y + height
                    });
                }
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", _extends({}, props, {
                    className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-cartesian-axis-line', (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(axisLine, 'className'))
                }));
            }
        },
        {
            key: "renderTicks",
            value: /**
     * render the ticks
     * @param {Array} ticks The ticks to actually render (overrides what was passed in props)
     * @param {string} fontSize Fontsize to consider for tick spacing
     * @param {string} letterSpacing Letterspacing to consider for tick spacing
     * @return {ReactComponent} renderedTicks
     */ function renderTicks(ticks, fontSize, letterSpacing) {
                var _this2 = this;
                var _this$props6 = this.props, tickLine = _this$props6.tickLine, stroke = _this$props6.stroke, tick = _this$props6.tick, tickFormatter = _this$props6.tickFormatter, unit = _this$props6.unit;
                var finalTicks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTicks"])(_objectSpread(_objectSpread({}, this.props), {}, {
                    ticks: ticks
                }), fontSize, letterSpacing);
                var textAnchor = this.getTickTextAnchor();
                var verticalAnchor = this.getTickVerticalAnchor();
                var axisProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(this.props, false);
                var customTickProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(tick, false);
                var tickLineProps = _objectSpread(_objectSpread({}, axisProps), {}, {
                    fill: 'none'
                }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(tickLine, false));
                var items = finalTicks.map(function(entry, i) {
                    var _this2$getTickLineCoo = _this2.getTickLineCoord(entry), lineCoord = _this2$getTickLineCoo.line, tickCoord = _this2$getTickLineCoo.tick;
                    var tickProps = _objectSpread(_objectSpread(_objectSpread(_objectSpread({
                        textAnchor: textAnchor,
                        verticalAnchor: verticalAnchor
                    }, axisProps), {}, {
                        stroke: 'none',
                        fill: stroke
                    }, customTickProps), tickCoord), {}, {
                        index: i,
                        payload: entry,
                        visibleTicksCount: finalTicks.length,
                        tickFormatter: tickFormatter
                    });
                    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], _extends({
                        className: "recharts-cartesian-axis-tick",
                        key: "tick-".concat(entry.value, "-").concat(entry.coordinate, "-").concat(entry.tickCoord)
                    }, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["adaptEventsOfChild"])(_this2.props, entry, i)), tickLine && /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", _extends({}, tickLineProps, lineCoord, {
                        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-cartesian-axis-tick-line', (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$get$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tickLine, 'className'))
                    })), tick && CartesianAxis.renderTickItem(tick, tickProps, "".concat((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(tickFormatter) ? tickFormatter(entry.value, i) : entry.value).concat(unit || '')));
                });
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", {
                    className: "recharts-cartesian-axis-ticks"
                }, items);
            }
        },
        {
            key: "render",
            value: function render() {
                var _this3 = this;
                var _this$props7 = this.props, axisLine = _this$props7.axisLine, width = _this$props7.width, height = _this$props7.height, ticksGenerator = _this$props7.ticksGenerator, className = _this$props7.className, hide = _this$props7.hide;
                if (hide) {
                    return null;
                }
                var _this$props8 = this.props, ticks = _this$props8.ticks, noTicksProps = _objectWithoutProperties(_this$props8, _excluded3);
                var finalTicks = ticks;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(ticksGenerator)) {
                    finalTicks = ticks && ticks.length > 0 ? ticksGenerator(this.props) : ticksGenerator(noTicksProps);
                }
                if (width <= 0 || height <= 0 || !finalTicks || !finalTicks.length) {
                    return null;
                }
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$container$2f$Layer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Layer"], {
                    className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-cartesian-axis', className),
                    ref: function ref(_ref2) {
                        _this3.layerReference = _ref2;
                    }
                }, axisLine && this.renderAxisLine(), this.renderTicks(finalTicks, this.state.fontSize, this.state.letterSpacing), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Label$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Label"].renderCallByParent(this.props));
            }
        }
    ], [
        {
            key: "renderTickItem",
            value: function renderTickItem(option, props, value) {
                var tickItem;
                var combinedClassName = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(props.className, 'recharts-cartesian-axis-tick-value');
                if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
                    tickItem = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, _objectSpread(_objectSpread({}, props), {}, {
                        className: combinedClassName
                    }));
                } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
                    tickItem = option(_objectSpread(_objectSpread({}, props), {}, {
                        className: combinedClassName
                    }));
                } else {
                    tickItem = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$component$2f$Text$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Text"], _extends({}, props, {
                        className: "recharts-cartesian-axis-tick-value"
                    }), value);
                }
                return tickItem;
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Component"]);
_defineProperty(CartesianAxis, "displayName", 'CartesianAxis');
_defineProperty(CartesianAxis, "defaultProps", {
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    viewBox: {
        x: 0,
        y: 0,
        width: 0,
        height: 0
    },
    // The orientation of axis
    orientation: 'bottom',
    // The ticks
    ticks: [],
    stroke: '#666',
    tickLine: true,
    axisLine: true,
    tick: true,
    mirror: false,
    minTickGap: 5,
    // The width or height of tick
    tickSize: 6,
    tickMargin: 2,
    interval: 'preserveEnd'
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/XAxis.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "XAxis",
    ()=>XAxis
]);
/**
 * @fileOverview X Axis
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/context/chartLayoutContext.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/CartesianAxis.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
;
;
;
;
;
/** Define of XAxis props */ function XAxisImpl(_ref) {
    var xAxisId = _ref.xAxisId;
    var width = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useChartWidth"])();
    var height = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useChartHeight"])();
    var axisOptions = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useXAxisOrThrow"])(xAxisId);
    if (axisOptions == null) {
        return null;
    }
    return(/*#__PURE__*/ // @ts-expect-error the axisOptions type is not exactly what CartesianAxis is expecting.
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"](__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CartesianAxis"], _extends({}, axisOptions, {
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])("recharts-".concat(axisOptions.axisType, " ").concat(axisOptions.axisType), axisOptions.className),
        viewBox: {
            x: 0,
            y: 0,
            width: width,
            height: height
        },
        ticksGenerator: function ticksGenerator(axis) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(axis, true);
        }
    })));
}
var XAxis = /*#__PURE__*/ function(_React$Component) {
    function XAxis() {
        _classCallCheck(this, XAxis);
        return _callSuper(this, XAxis, arguments);
    }
    _inherits(XAxis, _React$Component);
    return _createClass(XAxis, [
        {
            key: "render",
            value: function render() {
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"](XAxisImpl, this.props);
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Component"]);
_defineProperty(XAxis, "displayName", 'XAxis');
_defineProperty(XAxis, "defaultProps", {
    allowDecimals: true,
    hide: false,
    orientation: 'bottom',
    width: 0,
    height: 30,
    mirror: false,
    xAxisId: 0,
    tickCount: 5,
    type: 'category',
    padding: {
        left: 0,
        right: 0
    },
    allowDataOverflow: false,
    scale: 'auto',
    reversed: false,
    allowDuplicatedCategory: true
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/YAxis.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "YAxis",
    ()=>YAxis
]);
/**
 * @fileOverview Y Axis
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/context/chartLayoutContext.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/CartesianAxis.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
        throw new TypeError("Cannot call a class as a function");
    }
}
function _defineProperties(target, props) {
    for(var i = 0; i < props.length; i++){
        var descriptor = props[i];
        descriptor.enumerable = descriptor.enumerable || false;
        descriptor.configurable = true;
        if ("value" in descriptor) descriptor.writable = true;
        Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor);
    }
}
function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) _defineProperties(Constructor.prototype, protoProps);
    if (staticProps) _defineProperties(Constructor, staticProps);
    Object.defineProperty(Constructor, "prototype", {
        writable: false
    });
    return Constructor;
}
function _callSuper(t, o, e) {
    return o = _getPrototypeOf(o), _possibleConstructorReturn(t, _isNativeReflectConstruct() ? Reflect.construct(o, e || [], _getPrototypeOf(t).constructor) : o.apply(t, e));
}
function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === "object" || typeof call === "function")) {
        return call;
    } else if (call !== void 0) {
        throw new TypeError("Derived constructors may only return object or undefined");
    }
    return _assertThisInitialized(self);
}
function _assertThisInitialized(self) {
    if (self === void 0) {
        throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
    }
    return self;
}
function _isNativeReflectConstruct() {
    try {
        var t = !Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function() {}));
    } catch (t) {}
    return (_isNativeReflectConstruct = function _isNativeReflectConstruct() {
        return !!t;
    })();
}
function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) {
        return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
}
function _inherits(subClass, superClass) {
    if (typeof superClass !== "function" && superClass !== null) {
        throw new TypeError("Super expression must either be null or a function");
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
        constructor: {
            value: subClass,
            writable: true,
            configurable: true
        }
    });
    Object.defineProperty(subClass, "prototype", {
        writable: false
    });
    if (superClass) _setPrototypeOf(subClass, superClass);
}
function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) {
        o.__proto__ = p;
        return o;
    };
    return _setPrototypeOf(o, p);
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
;
;
;
;
;
var YAxisImpl = function YAxisImpl(_ref) {
    var yAxisId = _ref.yAxisId;
    var width = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useChartWidth"])();
    var height = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useChartHeight"])();
    var axisOptions = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useYAxisOrThrow"])(yAxisId);
    if (axisOptions == null) {
        return null;
    }
    return(/*#__PURE__*/ // @ts-expect-error the axisOptions type is not exactly what CartesianAxis is expecting.
    __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"](__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CartesianAxis"], _extends({}, axisOptions, {
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])("recharts-".concat(axisOptions.axisType, " ").concat(axisOptions.axisType), axisOptions.className),
        viewBox: {
            x: 0,
            y: 0,
            width: width,
            height: height
        },
        ticksGenerator: function ticksGenerator(axis) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(axis, true);
        }
    })));
};
var YAxis = /*#__PURE__*/ function(_React$Component) {
    function YAxis() {
        _classCallCheck(this, YAxis);
        return _callSuper(this, YAxis, arguments);
    }
    _inherits(YAxis, _React$Component);
    return _createClass(YAxis, [
        {
            key: "render",
            value: function render() {
                return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createElement"](YAxisImpl, this.props);
            }
        }
    ]);
}(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Component"]);
_defineProperty(YAxis, "displayName", 'YAxis');
_defineProperty(YAxis, "defaultProps", {
    allowDuplicatedCategory: true,
    allowDecimals: true,
    hide: false,
    orientation: 'left',
    width: 60,
    height: 0,
    mirror: false,
    yAxisId: 0,
    tickCount: 5,
    type: 'number',
    padding: {
        top: 0,
        bottom: 0
    },
    allowDataOverflow: false,
    scale: 'auto',
    reversed: false
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/chart/AreaChart.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "AreaChart",
    ()=>AreaChart
]);
/**
 * @fileOverview Area Chart
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$chart$2f$generateCategoricalChart$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/chart/generateCategoricalChart.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/Area.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$XAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/XAxis.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$YAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/YAxis.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/CartesianUtils.js [app-client] (ecmascript)");
;
;
;
;
;
var AreaChart = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$chart$2f$generateCategoricalChart$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["generateCategoricalChart"])({
    chartName: 'AreaChart',
    GraphicalChild: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$Area$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Area"],
    axisComponents: [
        {
            axisType: 'xAxis',
            AxisComp: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$XAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["XAxis"]
        },
        {
            axisType: 'yAxis',
            AxisComp: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$YAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["YAxis"]
        }
    ],
    formatAxisMap: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$CartesianUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAxisMap"]
});
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/CartesianGrid.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CartesianGrid",
    ()=>CartesianGrid
]);
/**
 * @fileOverview Cartesian Grid
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ChartUtils.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/getTicks.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/cartesian/CartesianAxis.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/context/chartLayoutContext.js [app-client] (ecmascript)");
var _excluded = [
    "x1",
    "y1",
    "x2",
    "y2",
    "key"
], _excluded2 = [
    "offset"
];
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _extends() {
    _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable";
    return _extends.apply(this, arguments);
}
function _objectWithoutProperties(source, excluded) {
    if (source == null) return {};
    var target = _objectWithoutPropertiesLoose(source, excluded);
    var key, i;
    if (Object.getOwnPropertySymbols) {
        var sourceSymbolKeys = Object.getOwnPropertySymbols(source);
        for(i = 0; i < sourceSymbolKeys.length; i++){
            key = sourceSymbolKeys[i];
            if (excluded.indexOf(key) >= 0) continue;
            if (!Object.prototype.propertyIsEnumerable.call(source, key)) continue;
            target[key] = source[key];
        }
    }
    return target;
}
function _objectWithoutPropertiesLoose(source, excluded) {
    if (source == null) return {};
    var target = {};
    for(var key in source){
        if (Object.prototype.hasOwnProperty.call(source, key)) {
            if (excluded.indexOf(key) >= 0) continue;
            target[key] = source[key];
        }
    }
    return target;
}
;
;
;
;
;
;
;
;
;
/**
 * The <CartesianGrid horizontal
 */ var Background = function Background(props) {
    var fill = props.fill;
    if (!fill || fill === 'none') {
        return null;
    }
    var fillOpacity = props.fillOpacity, x = props.x, y = props.y, width = props.width, height = props.height, ry = props.ry;
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
        x: x,
        y: y,
        ry: ry,
        width: width,
        height: height,
        stroke: "none",
        fill: fill,
        fillOpacity: fillOpacity,
        className: "recharts-cartesian-grid-bg"
    });
};
function renderLineItem(option, props) {
    var lineItem;
    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(option)) {
        // @ts-expect-error typescript does not see the props type when cloning an element
        lineItem = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(option, props);
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(option)) {
        lineItem = option(props);
    } else {
        var x1 = props.x1, y1 = props.y1, x2 = props.x2, y2 = props.y2, key = props.key, others = _objectWithoutProperties(props, _excluded);
        var _filterProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["filterProps"])(others, false), __ = _filterProps.offset, restOfFilteredProps = _objectWithoutProperties(_filterProps, _excluded2);
        lineItem = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("line", _extends({}, restOfFilteredProps, {
            x1: x1,
            y1: y1,
            x2: x2,
            y2: y2,
            fill: "none",
            key: key
        }));
    }
    return lineItem;
}
function HorizontalGridLines(props) {
    var x = props.x, width = props.width, _props$horizontal = props.horizontal, horizontal = _props$horizontal === void 0 ? true : _props$horizontal, horizontalPoints = props.horizontalPoints;
    if (!horizontal || !horizontalPoints || !horizontalPoints.length) {
        return null;
    }
    var items = horizontalPoints.map(function(entry, i) {
        var lineItemProps = _objectSpread(_objectSpread({}, props), {}, {
            x1: x,
            y1: entry,
            x2: x + width,
            y2: entry,
            key: "line-".concat(i),
            index: i
        });
        return renderLineItem(horizontal, lineItemProps);
    });
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", {
        className: "recharts-cartesian-grid-horizontal"
    }, items);
}
function VerticalGridLines(props) {
    var y = props.y, height = props.height, _props$vertical = props.vertical, vertical = _props$vertical === void 0 ? true : _props$vertical, verticalPoints = props.verticalPoints;
    if (!vertical || !verticalPoints || !verticalPoints.length) {
        return null;
    }
    var items = verticalPoints.map(function(entry, i) {
        var lineItemProps = _objectSpread(_objectSpread({}, props), {}, {
            x1: entry,
            y1: y,
            x2: entry,
            y2: y + height,
            key: "line-".concat(i),
            index: i
        });
        return renderLineItem(vertical, lineItemProps);
    });
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", {
        className: "recharts-cartesian-grid-vertical"
    }, items);
}
function HorizontalStripes(props) {
    var horizontalFill = props.horizontalFill, fillOpacity = props.fillOpacity, x = props.x, y = props.y, width = props.width, height = props.height, horizontalPoints = props.horizontalPoints, _props$horizontal2 = props.horizontal, horizontal = _props$horizontal2 === void 0 ? true : _props$horizontal2;
    if (!horizontal || !horizontalFill || !horizontalFill.length) {
        return null;
    }
    // Why =y -y? I was trying to find any difference that this makes, with floating point numbers and edge cases but ... nothing.
    var roundedSortedHorizontalPoints = horizontalPoints.map(function(e) {
        return Math.round(e + y - y);
    }).sort(function(a, b) {
        return a - b;
    });
    // Why is this condition `!==` instead of `<=` ?
    if (y !== roundedSortedHorizontalPoints[0]) {
        roundedSortedHorizontalPoints.unshift(0);
    }
    var items = roundedSortedHorizontalPoints.map(function(entry, i) {
        // Why do we strip only the last stripe if it is invisible, and not all invisible stripes?
        var lastStripe = !roundedSortedHorizontalPoints[i + 1];
        var lineHeight = lastStripe ? y + height - entry : roundedSortedHorizontalPoints[i + 1] - entry;
        if (lineHeight <= 0) {
            return null;
        }
        var colorIndex = i % horizontalFill.length;
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
            key: "react-".concat(i) // eslint-disable-line react/no-array-index-key
            ,
            y: entry,
            x: x,
            height: lineHeight,
            width: width,
            stroke: "none",
            fill: horizontalFill[colorIndex],
            fillOpacity: fillOpacity,
            className: "recharts-cartesian-grid-bg"
        });
    });
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", {
        className: "recharts-cartesian-gridstripes-horizontal"
    }, items);
}
function VerticalStripes(props) {
    var _props$vertical2 = props.vertical, vertical = _props$vertical2 === void 0 ? true : _props$vertical2, verticalFill = props.verticalFill, fillOpacity = props.fillOpacity, x = props.x, y = props.y, width = props.width, height = props.height, verticalPoints = props.verticalPoints;
    if (!vertical || !verticalFill || !verticalFill.length) {
        return null;
    }
    var roundedSortedVerticalPoints = verticalPoints.map(function(e) {
        return Math.round(e + x - x);
    }).sort(function(a, b) {
        return a - b;
    });
    if (x !== roundedSortedVerticalPoints[0]) {
        roundedSortedVerticalPoints.unshift(0);
    }
    var items = roundedSortedVerticalPoints.map(function(entry, i) {
        var lastStripe = !roundedSortedVerticalPoints[i + 1];
        var lineWidth = lastStripe ? x + width - entry : roundedSortedVerticalPoints[i + 1] - entry;
        if (lineWidth <= 0) {
            return null;
        }
        var colorIndex = i % verticalFill.length;
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("rect", {
            key: "react-".concat(i) // eslint-disable-line react/no-array-index-key
            ,
            x: entry,
            y: y,
            width: lineWidth,
            height: height,
            stroke: "none",
            fill: verticalFill[colorIndex],
            fillOpacity: fillOpacity,
            className: "recharts-cartesian-grid-bg"
        });
    });
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", {
        className: "recharts-cartesian-gridstripes-vertical"
    }, items);
}
var defaultVerticalCoordinatesGenerator = function defaultVerticalCoordinatesGenerator(_ref, syncWithTicks) {
    var xAxis = _ref.xAxis, width = _ref.width, height = _ref.height, offset = _ref.offset;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCoordinatesOfGrid"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTicks"])(_objectSpread(_objectSpread(_objectSpread({}, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CartesianAxis"].defaultProps), xAxis), {}, {
        ticks: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(xAxis, true),
        viewBox: {
            x: 0,
            y: 0,
            width: width,
            height: height
        }
    })), offset.left, offset.left + offset.width, syncWithTicks);
};
var defaultHorizontalCoordinatesGenerator = function defaultHorizontalCoordinatesGenerator(_ref2, syncWithTicks) {
    var yAxis = _ref2.yAxis, width = _ref2.width, height = _ref2.height, offset = _ref2.offset;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getCoordinatesOfGrid"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$getTicks$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTicks"])(_objectSpread(_objectSpread(_objectSpread({}, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$cartesian$2f$CartesianAxis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CartesianAxis"].defaultProps), yAxis), {}, {
        ticks: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ChartUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getTicksOfAxis"])(yAxis, true),
        viewBox: {
            x: 0,
            y: 0,
            width: width,
            height: height
        }
    })), offset.top, offset.top + offset.height, syncWithTicks);
};
var defaultProps = {
    horizontal: true,
    vertical: true,
    // The ordinates of horizontal grid lines
    horizontalPoints: [],
    // The abscissas of vertical grid lines
    verticalPoints: [],
    stroke: '#ccc',
    fill: 'none',
    // The fill of colors of grid lines
    verticalFill: [],
    horizontalFill: []
};
function CartesianGrid(props) {
    var _props$stroke, _props$fill, _props$horizontal3, _props$horizontalFill, _props$vertical3, _props$verticalFill;
    var chartWidth = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useChartWidth"])();
    var chartHeight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useChartHeight"])();
    var offset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useOffset"])();
    var propsIncludingDefaults = _objectSpread(_objectSpread({}, props), {}, {
        stroke: (_props$stroke = props.stroke) !== null && _props$stroke !== void 0 ? _props$stroke : defaultProps.stroke,
        fill: (_props$fill = props.fill) !== null && _props$fill !== void 0 ? _props$fill : defaultProps.fill,
        horizontal: (_props$horizontal3 = props.horizontal) !== null && _props$horizontal3 !== void 0 ? _props$horizontal3 : defaultProps.horizontal,
        horizontalFill: (_props$horizontalFill = props.horizontalFill) !== null && _props$horizontalFill !== void 0 ? _props$horizontalFill : defaultProps.horizontalFill,
        vertical: (_props$vertical3 = props.vertical) !== null && _props$vertical3 !== void 0 ? _props$vertical3 : defaultProps.vertical,
        verticalFill: (_props$verticalFill = props.verticalFill) !== null && _props$verticalFill !== void 0 ? _props$verticalFill : defaultProps.verticalFill,
        x: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(props.x) ? props.x : offset.left,
        y: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(props.y) ? props.y : offset.top,
        width: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(props.width) ? props.width : offset.width,
        height: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(props.height) ? props.height : offset.height
    });
    var x = propsIncludingDefaults.x, y = propsIncludingDefaults.y, width = propsIncludingDefaults.width, height = propsIncludingDefaults.height, syncWithTicks = propsIncludingDefaults.syncWithTicks, horizontalValues = propsIncludingDefaults.horizontalValues, verticalValues = propsIncludingDefaults.verticalValues;
    // @ts-expect-error the scale prop is mixed up - we need to untagle this at some point
    var xAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useArbitraryXAxis"])();
    // @ts-expect-error the scale prop is mixed up - we need to untagle this at some point
    var yAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$context$2f$chartLayoutContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useYAxisWithFiniteDomainOrRandom"])();
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(width) || width <= 0 || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(height) || height <= 0 || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(x) || x !== +x || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(y) || y !== +y) {
        return null;
    }
    /*
   * verticalCoordinatesGenerator and horizontalCoordinatesGenerator are defined
   * outside of the propsIncludingDefaults because they were never part of the original props
   * and they were never passed as a prop down to horizontal/vertical custom elements.
   * If we add these two to propsIncludingDefaults then we are changing public API.
   * Not a bad thing per se but also not necessary.
   */ var verticalCoordinatesGenerator = propsIncludingDefaults.verticalCoordinatesGenerator || defaultVerticalCoordinatesGenerator;
    var horizontalCoordinatesGenerator = propsIncludingDefaults.horizontalCoordinatesGenerator || defaultHorizontalCoordinatesGenerator;
    var horizontalPoints = propsIncludingDefaults.horizontalPoints, verticalPoints = propsIncludingDefaults.verticalPoints;
    // No horizontal points are specified
    if ((!horizontalPoints || !horizontalPoints.length) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(horizontalCoordinatesGenerator)) {
        var isHorizontalValues = horizontalValues && horizontalValues.length;
        var generatorResult = horizontalCoordinatesGenerator({
            yAxis: yAxis ? _objectSpread(_objectSpread({}, yAxis), {}, {
                ticks: isHorizontalValues ? horizontalValues : yAxis.ticks
            }) : undefined,
            width: chartWidth,
            height: chartHeight,
            offset: offset
        }, isHorizontalValues ? true : syncWithTicks);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(Array.isArray(generatorResult), "horizontalCoordinatesGenerator should return Array but instead it returned [".concat(_typeof(generatorResult), "]"));
        if (Array.isArray(generatorResult)) {
            horizontalPoints = generatorResult;
        }
    }
    // No vertical points are specified
    if ((!verticalPoints || !verticalPoints.length) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$isFunction$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(verticalCoordinatesGenerator)) {
        var isVerticalValues = verticalValues && verticalValues.length;
        var _generatorResult = verticalCoordinatesGenerator({
            xAxis: xAxis ? _objectSpread(_objectSpread({}, xAxis), {}, {
                ticks: isVerticalValues ? verticalValues : xAxis.ticks
            }) : undefined,
            width: chartWidth,
            height: chartHeight,
            offset: offset
        }, isVerticalValues ? true : syncWithTicks);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(Array.isArray(_generatorResult), "verticalCoordinatesGenerator should return Array but instead it returned [".concat(_typeof(_generatorResult), "]"));
        if (Array.isArray(_generatorResult)) {
            verticalPoints = _generatorResult;
        }
    }
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("g", {
        className: "recharts-cartesian-grid"
    }, /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Background, {
        fill: propsIncludingDefaults.fill,
        fillOpacity: propsIncludingDefaults.fillOpacity,
        x: propsIncludingDefaults.x,
        y: propsIncludingDefaults.y,
        width: propsIncludingDefaults.width,
        height: propsIncludingDefaults.height,
        ry: propsIncludingDefaults.ry
    }), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(HorizontalGridLines, _extends({}, propsIncludingDefaults, {
        offset: offset,
        horizontalPoints: horizontalPoints,
        xAxis: xAxis,
        yAxis: yAxis
    })), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(VerticalGridLines, _extends({}, propsIncludingDefaults, {
        offset: offset,
        verticalPoints: verticalPoints,
        xAxis: xAxis,
        yAxis: yAxis
    })), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(HorizontalStripes, _extends({}, propsIncludingDefaults, {
        horizontalPoints: horizontalPoints
    })), /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(VerticalStripes, _extends({}, propsIncludingDefaults, {
        verticalPoints: verticalPoints
    })));
}
CartesianGrid.displayName = 'CartesianGrid';
}),
"[project]/coding/projects/LangBot/web/node_modules/recharts/es6/component/ResponsiveContainer.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ResponsiveContainer",
    ()=>ResponsiveContainer
]);
/**
 * @fileOverview Wrapper component to make charts adapt to the size of parent * DOM
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$throttle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lodash/throttle.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/DataUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/LogUtils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/recharts/es6/util/ReactUtils.js [app-client] (ecmascript)");
function _typeof(o) {
    "@babel/helpers - typeof";
    return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(o) {
        return typeof o;
    } : function(o) {
        return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o;
    }, _typeof(o);
}
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPropertyKey(t) {
    var i = _toPrimitive(t, "string");
    return "symbol" == _typeof(i) ? i : i + "";
}
function _toPrimitive(t, r) {
    if ("object" != _typeof(t) || !t) return t;
    var e = t[Symbol.toPrimitive];
    if (void 0 !== e) {
        var i = e.call(t, r || "default");
        if ("object" != _typeof(i)) return i;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return ("string" === r ? String : Number)(t);
}
function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest();
}
function _nonIterableRest() {
    throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
}
function _unsupportedIterableToArray(o, minLen) {
    if (!o) return;
    if (typeof o === "string") return _arrayLikeToArray(o, minLen);
    var n = Object.prototype.toString.call(o).slice(8, -1);
    if (n === "Object" && o.constructor) n = o.constructor.name;
    if (n === "Map" || n === "Set") return Array.from(o);
    if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen);
}
function _arrayLikeToArray(arr, len) {
    if (len == null || len > arr.length) len = arr.length;
    for(var i = 0, arr2 = new Array(len); i < len; i++)arr2[i] = arr[i];
    return arr2;
}
function _iterableToArrayLimit(r, l) {
    var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"];
    if (null != t) {
        var e, n, i, u, a = [], f = !0, o = !1;
        try {
            if (i = (t = t.call(r)).next, 0 === l) {
                if (Object(t) !== t) return;
                f = !1;
            } else for(; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0);
        } catch (r) {
            o = !0, n = r;
        } finally{
            try {
                if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return;
            } finally{
                if (o) throw n;
            }
        }
        return a;
    }
}
function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) return arr;
}
;
;
;
;
;
;
var ResponsiveContainer = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forwardRef"])(function(_ref, ref) {
    var aspect = _ref.aspect, _ref$initialDimension = _ref.initialDimension, initialDimension = _ref$initialDimension === void 0 ? {
        width: -1,
        height: -1
    } : _ref$initialDimension, _ref$width = _ref.width, width = _ref$width === void 0 ? '100%' : _ref$width, _ref$height = _ref.height, height = _ref$height === void 0 ? '100%' : _ref$height, _ref$minWidth = _ref.minWidth, minWidth = _ref$minWidth === void 0 ? 0 : _ref$minWidth, minHeight = _ref.minHeight, maxHeight = _ref.maxHeight, children = _ref.children, _ref$debounce = _ref.debounce, debounce = _ref$debounce === void 0 ? 0 : _ref$debounce, id = _ref.id, className = _ref.className, onResize = _ref.onResize, _ref$style = _ref.style, style = _ref$style === void 0 ? {} : _ref$style;
    var containerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    var onResizeRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])();
    onResizeRef.current = onResize;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useImperativeHandle"])(ref, {
        "ResponsiveContainer.useImperativeHandle": function() {
            return Object.defineProperty(containerRef.current, 'current', {
                get: function get() {
                    // eslint-disable-next-line no-console
                    console.warn('The usage of ref.current.current is deprecated and will no longer be supported.');
                    return containerRef.current;
                },
                configurable: true
            });
        }
    }["ResponsiveContainer.useImperativeHandle"]);
    var _useState = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        containerWidth: initialDimension.width,
        containerHeight: initialDimension.height
    }), _useState2 = _slicedToArray(_useState, 2), sizes = _useState2[0], setSizes = _useState2[1];
    var setContainerSize = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "ResponsiveContainer.useCallback[setContainerSize]": function(newWidth, newHeight) {
            setSizes({
                "ResponsiveContainer.useCallback[setContainerSize]": function(prevState) {
                    var roundedWidth = Math.round(newWidth);
                    var roundedHeight = Math.round(newHeight);
                    if (prevState.containerWidth === roundedWidth && prevState.containerHeight === roundedHeight) {
                        return prevState;
                    }
                    return {
                        containerWidth: roundedWidth,
                        containerHeight: roundedHeight
                    };
                }
            }["ResponsiveContainer.useCallback[setContainerSize]"]);
        }
    }["ResponsiveContainer.useCallback[setContainerSize]"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "ResponsiveContainer.useEffect": function() {
            var callback = function callback(entries) {
                var _onResizeRef$current;
                var _entries$0$contentRec = entries[0].contentRect, containerWidth = _entries$0$contentRec.width, containerHeight = _entries$0$contentRec.height;
                setContainerSize(containerWidth, containerHeight);
                (_onResizeRef$current = onResizeRef.current) === null || _onResizeRef$current === void 0 || _onResizeRef$current.call(onResizeRef, containerWidth, containerHeight);
            };
            if (debounce > 0) {
                callback = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lodash$2f$throttle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(callback, debounce, {
                    trailing: true,
                    leading: false
                });
            }
            var observer = new ResizeObserver(callback);
            var _containerRef$current = containerRef.current.getBoundingClientRect(), containerWidth = _containerRef$current.width, containerHeight = _containerRef$current.height;
            setContainerSize(containerWidth, containerHeight);
            observer.observe(containerRef.current);
            return ({
                "ResponsiveContainer.useEffect": function() {
                    observer.disconnect();
                }
            })["ResponsiveContainer.useEffect"];
        }
    }["ResponsiveContainer.useEffect"], [
        setContainerSize,
        debounce
    ]);
    var chartContent = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "ResponsiveContainer.useMemo[chartContent]": function() {
            var containerWidth = sizes.containerWidth, containerHeight = sizes.containerHeight;
            if (containerWidth < 0 || containerHeight < 0) {
                return null;
            }
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPercent"])(width) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPercent"])(height), "The width(%s) and height(%s) are both fixed numbers,\n       maybe you don't need to use a ResponsiveContainer.", width, height);
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(!aspect || aspect > 0, 'The aspect(%s) must be greater than zero.', aspect);
            var calculatedWidth = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPercent"])(width) ? containerWidth : width;
            var calculatedHeight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$DataUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isPercent"])(height) ? containerHeight : height;
            if (aspect && aspect > 0) {
                // Preserve the desired aspect ratio
                if (calculatedWidth) {
                    // Will default to using width for aspect ratio
                    calculatedHeight = calculatedWidth / aspect;
                } else if (calculatedHeight) {
                    // But we should also take height into consideration
                    calculatedWidth = calculatedHeight * aspect;
                }
                // if maxHeight is set, overwrite if calculatedHeight is greater than maxHeight
                if (maxHeight && calculatedHeight > maxHeight) {
                    calculatedHeight = maxHeight;
                }
            }
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$LogUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["warn"])(calculatedWidth > 0 || calculatedHeight > 0, "The width(%s) and height(%s) of chart should be greater than 0,\n       please check the style of container, or the props width(%s) and height(%s),\n       or add a minWidth(%s) or minHeight(%s) or use aspect(%s) to control the\n       height and width.", calculatedWidth, calculatedHeight, width, height, minWidth, minHeight, aspect);
            var isCharts = !Array.isArray(children) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$recharts$2f$es6$2f$util$2f$ReactUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDisplayName"])(children.type).endsWith('Chart');
            return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Children.map(children, {
                "ResponsiveContainer.useMemo[chartContent]": function(child) {
                    if (/*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isValidElement(child)) {
                        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cloneElement"])(child, _objectSpread({
                            width: calculatedWidth,
                            height: calculatedHeight
                        }, isCharts ? {
                            style: _objectSpread({
                                height: '100%',
                                width: '100%',
                                maxHeight: calculatedHeight,
                                maxWidth: calculatedWidth
                            }, child.props.style)
                        } : {}));
                    }
                    return child;
                }
            }["ResponsiveContainer.useMemo[chartContent]"]);
        }
    }["ResponsiveContainer.useMemo[chartContent]"], [
        aspect,
        children,
        height,
        maxHeight,
        minHeight,
        minWidth,
        sizes,
        width
    ]);
    return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", {
        id: id ? "".concat(id) : undefined,
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])('recharts-responsive-container', className),
        style: _objectSpread(_objectSpread({}, style), {}, {
            width: width,
            height: height,
            minWidth: minWidth,
            minHeight: minHeight,
            maxHeight: maxHeight
        }),
        ref: containerRef
    }, chartContent);
});
}),
]);

//# sourceMappingURL=a2e30_recharts_es6_a77d62be._.js.map