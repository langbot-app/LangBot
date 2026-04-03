(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/coding/projects/LangBot/web/node_modules/lodash/isNil.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if `value` is `null` or `undefined`.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is nullish, else `false`.
 * @example
 *
 * _.isNil(null);
 * // => true
 *
 * _.isNil(void 0);
 * // => true
 *
 * _.isNil(NaN);
 * // => false
 */ function isNil(value) {
    return value == null;
}
module.exports = isNil;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_freeGlobal.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Detect free variable `global` from Node.js. */ var freeGlobal = ("TURBOPACK compile-time value", "object") == 'object' && /*TURBOPACK member replacement*/ __turbopack_context__.g && /*TURBOPACK member replacement*/ __turbopack_context__.g.Object === Object && /*TURBOPACK member replacement*/ __turbopack_context__.g;
module.exports = freeGlobal;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var freeGlobal = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_freeGlobal.js [app-client] (ecmascript)");
/** Detect free variable `self`. */ var freeSelf = typeof self == 'object' && self && self.Object === Object && self;
/** Used as a reference to the global object. */ var root = freeGlobal || freeSelf || Function('return this')();
module.exports = root;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Symbol.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/** Built-in value references. */ var Symbol = root.Symbol;
module.exports = Symbol;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getRawTag.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Symbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Symbol.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * Used to resolve the
 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
 * of values.
 */ var nativeObjectToString = objectProto.toString;
/** Built-in value references. */ var symToStringTag = Symbol ? Symbol.toStringTag : undefined;
/**
 * A specialized version of `baseGetTag` which ignores `Symbol.toStringTag` values.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the raw `toStringTag`.
 */ function getRawTag(value) {
    var isOwn = hasOwnProperty.call(value, symToStringTag), tag = value[symToStringTag];
    try {
        value[symToStringTag] = undefined;
        var unmasked = true;
    } catch (e) {}
    var result = nativeObjectToString.call(value);
    if (unmasked) {
        if (isOwn) {
            value[symToStringTag] = tag;
        } else {
            delete value[symToStringTag];
        }
    }
    return result;
}
module.exports = getRawTag;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_objectToString.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used for built-in method references. */ var objectProto = Object.prototype;
/**
 * Used to resolve the
 * [`toStringTag`](http://ecma-international.org/ecma-262/7.0/#sec-object.prototype.tostring)
 * of values.
 */ var nativeObjectToString = objectProto.toString;
/**
 * Converts `value` to a string using `Object.prototype.toString`.
 *
 * @private
 * @param {*} value The value to convert.
 * @returns {string} Returns the converted string.
 */ function objectToString(value) {
    return nativeObjectToString.call(value);
}
module.exports = objectToString;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Symbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Symbol.js [app-client] (ecmascript)"), getRawTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getRawTag.js [app-client] (ecmascript)"), objectToString = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_objectToString.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var nullTag = '[object Null]', undefinedTag = '[object Undefined]';
/** Built-in value references. */ var symToStringTag = Symbol ? Symbol.toStringTag : undefined;
/**
 * The base implementation of `getTag` without fallbacks for buggy environments.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the `toStringTag`.
 */ function baseGetTag(value) {
    if (value == null) {
        return value === undefined ? undefinedTag : nullTag;
    }
    return symToStringTag && symToStringTag in Object(value) ? getRawTag(value) : objectToString(value);
}
module.exports = baseGetTag;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if `value` is the
 * [language type](http://www.ecma-international.org/ecma-262/7.0/#sec-ecmascript-language-types)
 * of `Object`. (e.g. arrays, functions, objects, regexes, `new Number(0)`, and `new String('')`)
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an object, else `false`.
 * @example
 *
 * _.isObject({});
 * // => true
 *
 * _.isObject([1, 2, 3]);
 * // => true
 *
 * _.isObject(_.noop);
 * // => true
 *
 * _.isObject(null);
 * // => false
 */ function isObject(value) {
    var type = typeof value;
    return value != null && (type == 'object' || type == 'function');
}
module.exports = isObject;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var asyncTag = '[object AsyncFunction]', funcTag = '[object Function]', genTag = '[object GeneratorFunction]', proxyTag = '[object Proxy]';
/**
 * Checks if `value` is classified as a `Function` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a function, else `false`.
 * @example
 *
 * _.isFunction(_);
 * // => true
 *
 * _.isFunction(/abc/);
 * // => false
 */ function isFunction(value) {
    if (!isObject(value)) {
        return false;
    }
    // The use of `Object#toString` avoids issues with the `typeof` operator
    // in Safari 9 which returns 'object' for typed arrays and other constructors.
    var tag = baseGetTag(value);
    return tag == funcTag || tag == genTag || tag == asyncTag || tag == proxyTag;
}
module.exports = isFunction;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseRange.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeCeil = Math.ceil, nativeMax = Math.max;
/**
 * The base implementation of `_.range` and `_.rangeRight` which doesn't
 * coerce arguments.
 *
 * @private
 * @param {number} start The start of the range.
 * @param {number} end The end of the range.
 * @param {number} step The value to increment or decrement by.
 * @param {boolean} [fromRight] Specify iterating from right to left.
 * @returns {Array} Returns the range of numbers.
 */ function baseRange(start, end, step, fromRight) {
    var index = -1, length = nativeMax(nativeCeil((end - start) / (step || 1)), 0), result = Array(length);
    while(length--){
        result[fromRight ? length : ++index] = start;
        start += step;
    }
    return result;
}
module.exports = baseRange;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/eq.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Performs a
 * [`SameValueZero`](http://ecma-international.org/ecma-262/7.0/#sec-samevaluezero)
 * comparison between two values to determine if they are equivalent.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {boolean} Returns `true` if the values are equivalent, else `false`.
 * @example
 *
 * var object = { 'a': 1 };
 * var other = { 'a': 1 };
 *
 * _.eq(object, object);
 * // => true
 *
 * _.eq(object, other);
 * // => false
 *
 * _.eq('a', 'a');
 * // => true
 *
 * _.eq('a', Object('a'));
 * // => false
 *
 * _.eq(NaN, NaN);
 * // => true
 */ function eq(value, other) {
    return value === other || value !== value && other !== other;
}
module.exports = eq;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isLength.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used as references for various `Number` constants. */ var MAX_SAFE_INTEGER = 9007199254740991;
/**
 * Checks if `value` is a valid array-like length.
 *
 * **Note:** This method is loosely based on
 * [`ToLength`](http://ecma-international.org/ecma-262/7.0/#sec-tolength).
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a valid length, else `false`.
 * @example
 *
 * _.isLength(3);
 * // => true
 *
 * _.isLength(Number.MIN_VALUE);
 * // => false
 *
 * _.isLength(Infinity);
 * // => false
 *
 * _.isLength('3');
 * // => false
 */ function isLength(value) {
    return typeof value == 'number' && value > -1 && value % 1 == 0 && value <= MAX_SAFE_INTEGER;
}
module.exports = isLength;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isArrayLike.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isFunction = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)"), isLength = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isLength.js [app-client] (ecmascript)");
/**
 * Checks if `value` is array-like. A value is considered array-like if it's
 * not a function and has a `value.length` that's an integer greater than or
 * equal to `0` and less than or equal to `Number.MAX_SAFE_INTEGER`.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is array-like, else `false`.
 * @example
 *
 * _.isArrayLike([1, 2, 3]);
 * // => true
 *
 * _.isArrayLike(document.body.children);
 * // => true
 *
 * _.isArrayLike('abc');
 * // => true
 *
 * _.isArrayLike(_.noop);
 * // => false
 */ function isArrayLike(value) {
    return value != null && isLength(value.length) && !isFunction(value);
}
module.exports = isArrayLike;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isIndex.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used as references for various `Number` constants. */ var MAX_SAFE_INTEGER = 9007199254740991;
/** Used to detect unsigned integer values. */ var reIsUint = /^(?:0|[1-9]\d*)$/;
/**
 * Checks if `value` is a valid array-like index.
 *
 * @private
 * @param {*} value The value to check.
 * @param {number} [length=MAX_SAFE_INTEGER] The upper bounds of a valid index.
 * @returns {boolean} Returns `true` if `value` is a valid index, else `false`.
 */ function isIndex(value, length) {
    var type = typeof value;
    length = length == null ? MAX_SAFE_INTEGER : length;
    return !!length && (type == 'number' || type != 'symbol' && reIsUint.test(value)) && value > -1 && value % 1 == 0 && value < length;
}
module.exports = isIndex;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isIterateeCall.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var eq = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/eq.js [app-client] (ecmascript)"), isArrayLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArrayLike.js [app-client] (ecmascript)"), isIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIndex.js [app-client] (ecmascript)"), isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
/**
 * Checks if the given arguments are from an iteratee call.
 *
 * @private
 * @param {*} value The potential iteratee value argument.
 * @param {*} index The potential iteratee index or key argument.
 * @param {*} object The potential iteratee object argument.
 * @returns {boolean} Returns `true` if the arguments are from an iteratee call,
 *  else `false`.
 */ function isIterateeCall(value, index, object) {
    if (!isObject(object)) {
        return false;
    }
    var type = typeof index;
    if (type == 'number' ? isArrayLike(object) && isIndex(index, object.length) : type == 'string' && index in object) {
        return eq(object[index], value);
    }
    return false;
}
module.exports = isIterateeCall;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_trimmedEndIndex.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used to match a single whitespace character. */ var reWhitespace = /\s/;
/**
 * Used by `_.trim` and `_.trimEnd` to get the index of the last non-whitespace
 * character of `string`.
 *
 * @private
 * @param {string} string The string to inspect.
 * @returns {number} Returns the index of the last non-whitespace character.
 */ function trimmedEndIndex(string) {
    var index = string.length;
    while(index-- && reWhitespace.test(string.charAt(index))){}
    return index;
}
module.exports = trimmedEndIndex;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseTrim.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var trimmedEndIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_trimmedEndIndex.js [app-client] (ecmascript)");
/** Used to match leading whitespace. */ var reTrimStart = /^\s+/;
/**
 * The base implementation of `_.trim`.
 *
 * @private
 * @param {string} string The string to trim.
 * @returns {string} Returns the trimmed string.
 */ function baseTrim(string) {
    return string ? string.slice(0, trimmedEndIndex(string) + 1).replace(reTrimStart, '') : string;
}
module.exports = baseTrim;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if `value` is object-like. A value is object-like if it's not `null`
 * and has a `typeof` result of "object".
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is object-like, else `false`.
 * @example
 *
 * _.isObjectLike({});
 * // => true
 *
 * _.isObjectLike([1, 2, 3]);
 * // => true
 *
 * _.isObjectLike(_.noop);
 * // => false
 *
 * _.isObjectLike(null);
 * // => false
 */ function isObjectLike(value) {
    return value != null && typeof value == 'object';
}
module.exports = isObjectLike;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var symbolTag = '[object Symbol]';
/**
 * Checks if `value` is classified as a `Symbol` primitive or object.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a symbol, else `false`.
 * @example
 *
 * _.isSymbol(Symbol.iterator);
 * // => true
 *
 * _.isSymbol('abc');
 * // => false
 */ function isSymbol(value) {
    return typeof value == 'symbol' || isObjectLike(value) && baseGetTag(value) == symbolTag;
}
module.exports = isSymbol;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/toNumber.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseTrim = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseTrim.js [app-client] (ecmascript)"), isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)"), isSymbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)");
/** Used as references for various `Number` constants. */ var NAN = 0 / 0;
/** Used to detect bad signed hexadecimal string values. */ var reIsBadHex = /^[-+]0x[0-9a-f]+$/i;
/** Used to detect binary string values. */ var reIsBinary = /^0b[01]+$/i;
/** Used to detect octal string values. */ var reIsOctal = /^0o[0-7]+$/i;
/** Built-in method references without a dependency on `root`. */ var freeParseInt = parseInt;
/**
 * Converts `value` to a number.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to process.
 * @returns {number} Returns the number.
 * @example
 *
 * _.toNumber(3.2);
 * // => 3.2
 *
 * _.toNumber(Number.MIN_VALUE);
 * // => 5e-324
 *
 * _.toNumber(Infinity);
 * // => Infinity
 *
 * _.toNumber('3.2');
 * // => 3.2
 */ function toNumber(value) {
    if (typeof value == 'number') {
        return value;
    }
    if (isSymbol(value)) {
        return NAN;
    }
    if (isObject(value)) {
        var other = typeof value.valueOf == 'function' ? value.valueOf() : value;
        value = isObject(other) ? other + '' : other;
    }
    if (typeof value != 'string') {
        return value === 0 ? value : +value;
    }
    value = baseTrim(value);
    var isBinary = reIsBinary.test(value);
    return isBinary || reIsOctal.test(value) ? freeParseInt(value.slice(2), isBinary ? 2 : 8) : reIsBadHex.test(value) ? NAN : +value;
}
module.exports = toNumber;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/toFinite.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var toNumber = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toNumber.js [app-client] (ecmascript)");
/** Used as references for various `Number` constants. */ var INFINITY = 1 / 0, MAX_INTEGER = 1.7976931348623157e+308;
/**
 * Converts `value` to a finite number.
 *
 * @static
 * @memberOf _
 * @since 4.12.0
 * @category Lang
 * @param {*} value The value to convert.
 * @returns {number} Returns the converted number.
 * @example
 *
 * _.toFinite(3.2);
 * // => 3.2
 *
 * _.toFinite(Number.MIN_VALUE);
 * // => 5e-324
 *
 * _.toFinite(Infinity);
 * // => 1.7976931348623157e+308
 *
 * _.toFinite('3.2');
 * // => 3.2
 */ function toFinite(value) {
    if (!value) {
        return value === 0 ? value : 0;
    }
    value = toNumber(value);
    if (value === INFINITY || value === -INFINITY) {
        var sign = value < 0 ? -1 : 1;
        return sign * MAX_INTEGER;
    }
    return value === value ? value : 0;
}
module.exports = toFinite;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_createRange.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseRange = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseRange.js [app-client] (ecmascript)"), isIterateeCall = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIterateeCall.js [app-client] (ecmascript)"), toFinite = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toFinite.js [app-client] (ecmascript)");
/**
 * Creates a `_.range` or `_.rangeRight` function.
 *
 * @private
 * @param {boolean} [fromRight] Specify iterating from right to left.
 * @returns {Function} Returns the new range function.
 */ function createRange(fromRight) {
    return function(start, end, step) {
        if (step && typeof step != 'number' && isIterateeCall(start, end, step)) {
            end = step = undefined;
        }
        // Ensure the sign of `-0` is preserved.
        start = toFinite(start);
        if (end === undefined) {
            end = start;
            start = 0;
        } else {
            end = toFinite(end);
        }
        step = step === undefined ? start < end ? 1 : -1 : toFinite(step);
        return baseRange(start, end, step, fromRight);
    };
}
module.exports = createRange;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/range.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var createRange = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_createRange.js [app-client] (ecmascript)");
/**
 * Creates an array of numbers (positive and/or negative) progressing from
 * `start` up to, but not including, `end`. A step of `-1` is used if a negative
 * `start` is specified without an `end` or `step`. If `end` is not specified,
 * it's set to `start` with `start` then set to `0`.
 *
 * **Note:** JavaScript follows the IEEE-754 standard for resolving
 * floating-point values which can produce unexpected results.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Util
 * @param {number} [start=0] The start of the range.
 * @param {number} end The end of the range.
 * @param {number} [step=1] The value to increment or decrement by.
 * @returns {Array} Returns the range of numbers.
 * @see _.inRange, _.rangeRight
 * @example
 *
 * _.range(4);
 * // => [0, 1, 2, 3]
 *
 * _.range(-4);
 * // => [0, -1, -2, -3]
 *
 * _.range(1, 5);
 * // => [1, 2, 3, 4]
 *
 * _.range(0, 20, 5);
 * // => [0, 5, 10, 15]
 *
 * _.range(0, -4, -1);
 * // => [0, -1, -2, -3]
 *
 * _.range(1, 4, 0);
 * // => [1, 1, 1]
 *
 * _.range(0);
 * // => []
 */ var range = createRange();
module.exports = range;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if `value` is classified as an `Array` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an array, else `false`.
 * @example
 *
 * _.isArray([1, 2, 3]);
 * // => true
 *
 * _.isArray(document.body.children);
 * // => false
 *
 * _.isArray('abc');
 * // => false
 *
 * _.isArray(_.noop);
 * // => false
 */ var isArray = Array.isArray;
module.exports = isArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isKey.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isSymbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)");
/** Used to match property names within property paths. */ var reIsDeepProp = /\.|\[(?:[^[\]]*|(["'])(?:(?!\1)[^\\]|\\.)*?\1)\]/, reIsPlainProp = /^\w*$/;
/**
 * Checks if `value` is a property name and not a property path.
 *
 * @private
 * @param {*} value The value to check.
 * @param {Object} [object] The object to query keys on.
 * @returns {boolean} Returns `true` if `value` is a property name, else `false`.
 */ function isKey(value, object) {
    if (isArray(value)) {
        return false;
    }
    var type = typeof value;
    if (type == 'number' || type == 'symbol' || type == 'boolean' || value == null || isSymbol(value)) {
        return true;
    }
    return reIsPlainProp.test(value) || !reIsDeepProp.test(value) || object != null && value in Object(object);
}
module.exports = isKey;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_coreJsData.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/** Used to detect overreaching core-js shims. */ var coreJsData = root['__core-js_shared__'];
module.exports = coreJsData;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isMasked.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var coreJsData = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_coreJsData.js [app-client] (ecmascript)");
/** Used to detect methods masquerading as native. */ var maskSrcKey = function() {
    var uid = /[^.]+$/.exec(coreJsData && coreJsData.keys && coreJsData.keys.IE_PROTO || '');
    return uid ? 'Symbol(src)_1.' + uid : '';
}();
/**
 * Checks if `func` has its source masked.
 *
 * @private
 * @param {Function} func The function to check.
 * @returns {boolean} Returns `true` if `func` is masked, else `false`.
 */ function isMasked(func) {
    return !!maskSrcKey && maskSrcKey in func;
}
module.exports = isMasked;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_toSource.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used for built-in method references. */ var funcProto = Function.prototype;
/** Used to resolve the decompiled source of functions. */ var funcToString = funcProto.toString;
/**
 * Converts `func` to its source code.
 *
 * @private
 * @param {Function} func The function to convert.
 * @returns {string} Returns the source code.
 */ function toSource(func) {
    if (func != null) {
        try {
            return funcToString.call(func);
        } catch (e) {}
        try {
            return func + '';
        } catch (e) {}
    }
    return '';
}
module.exports = toSource;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsNative.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isFunction = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isFunction.js [app-client] (ecmascript)"), isMasked = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isMasked.js [app-client] (ecmascript)"), isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)"), toSource = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_toSource.js [app-client] (ecmascript)");
/**
 * Used to match `RegExp`
 * [syntax characters](http://ecma-international.org/ecma-262/7.0/#sec-patterns).
 */ var reRegExpChar = /[\\^$.*+?()[\]{}|]/g;
/** Used to detect host constructors (Safari). */ var reIsHostCtor = /^\[object .+?Constructor\]$/;
/** Used for built-in method references. */ var funcProto = Function.prototype, objectProto = Object.prototype;
/** Used to resolve the decompiled source of functions. */ var funcToString = funcProto.toString;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/** Used to detect if a method is native. */ var reIsNative = RegExp('^' + funcToString.call(hasOwnProperty).replace(reRegExpChar, '\\$&').replace(/hasOwnProperty|(function).*?(?=\\\()| for .+?(?=\\\])/g, '$1.*?') + '$');
/**
 * The base implementation of `_.isNative` without bad shim checks.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a native function,
 *  else `false`.
 */ function baseIsNative(value) {
    if (!isObject(value) || isMasked(value)) {
        return false;
    }
    var pattern = isFunction(value) ? reIsNative : reIsHostCtor;
    return pattern.test(toSource(value));
}
module.exports = baseIsNative;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getValue.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Gets the value at `key` of `object`.
 *
 * @private
 * @param {Object} [object] The object to query.
 * @param {string} key The key of the property to get.
 * @returns {*} Returns the property value.
 */ function getValue(object, key) {
    return object == null ? undefined : object[key];
}
module.exports = getValue;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsNative.js [app-client] (ecmascript)"), getValue = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getValue.js [app-client] (ecmascript)");
/**
 * Gets the native function at `key` of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {string} key The key of the method to get.
 * @returns {*} Returns the function if it's native, else `undefined`.
 */ function getNative(object, key) {
    var value = getValue(object, key);
    return baseIsNative(value) ? value : undefined;
}
module.exports = getNative;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeCreate.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)");
/* Built-in method references that are verified to be native. */ var nativeCreate = getNative(Object, 'create');
module.exports = nativeCreate;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hashClear.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var nativeCreate = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeCreate.js [app-client] (ecmascript)");
/**
 * Removes all key-value entries from the hash.
 *
 * @private
 * @name clear
 * @memberOf Hash
 */ function hashClear() {
    this.__data__ = nativeCreate ? nativeCreate(null) : {};
    this.size = 0;
}
module.exports = hashClear;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hashDelete.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Removes `key` and its value from the hash.
 *
 * @private
 * @name delete
 * @memberOf Hash
 * @param {Object} hash The hash to modify.
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */ function hashDelete(key) {
    var result = this.has(key) && delete this.__data__[key];
    this.size -= result ? 1 : 0;
    return result;
}
module.exports = hashDelete;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hashGet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var nativeCreate = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeCreate.js [app-client] (ecmascript)");
/** Used to stand-in for `undefined` hash values. */ var HASH_UNDEFINED = '__lodash_hash_undefined__';
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * Gets the hash value for `key`.
 *
 * @private
 * @name get
 * @memberOf Hash
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */ function hashGet(key) {
    var data = this.__data__;
    if (nativeCreate) {
        var result = data[key];
        return result === HASH_UNDEFINED ? undefined : result;
    }
    return hasOwnProperty.call(data, key) ? data[key] : undefined;
}
module.exports = hashGet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hashHas.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var nativeCreate = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeCreate.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * Checks if a hash value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf Hash
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */ function hashHas(key) {
    var data = this.__data__;
    return nativeCreate ? data[key] !== undefined : hasOwnProperty.call(data, key);
}
module.exports = hashHas;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hashSet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var nativeCreate = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeCreate.js [app-client] (ecmascript)");
/** Used to stand-in for `undefined` hash values. */ var HASH_UNDEFINED = '__lodash_hash_undefined__';
/**
 * Sets the hash `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf Hash
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the hash instance.
 */ function hashSet(key, value) {
    var data = this.__data__;
    this.size += this.has(key) ? 0 : 1;
    data[key] = nativeCreate && value === undefined ? HASH_UNDEFINED : value;
    return this;
}
module.exports = hashSet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Hash.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var hashClear = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hashClear.js [app-client] (ecmascript)"), hashDelete = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hashDelete.js [app-client] (ecmascript)"), hashGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hashGet.js [app-client] (ecmascript)"), hashHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hashHas.js [app-client] (ecmascript)"), hashSet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hashSet.js [app-client] (ecmascript)");
/**
 * Creates a hash object.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */ function Hash(entries) {
    var index = -1, length = entries == null ? 0 : entries.length;
    this.clear();
    while(++index < length){
        var entry = entries[index];
        this.set(entry[0], entry[1]);
    }
}
// Add methods to `Hash`.
Hash.prototype.clear = hashClear;
Hash.prototype['delete'] = hashDelete;
Hash.prototype.get = hashGet;
Hash.prototype.has = hashHas;
Hash.prototype.set = hashSet;
module.exports = Hash;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheClear.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Removes all key-value entries from the list cache.
 *
 * @private
 * @name clear
 * @memberOf ListCache
 */ function listCacheClear() {
    this.__data__ = [];
    this.size = 0;
}
module.exports = listCacheClear;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_assocIndexOf.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var eq = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/eq.js [app-client] (ecmascript)");
/**
 * Gets the index at which the `key` is found in `array` of key-value pairs.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {*} key The key to search for.
 * @returns {number} Returns the index of the matched value, else `-1`.
 */ function assocIndexOf(array, key) {
    var length = array.length;
    while(length--){
        if (eq(array[length][0], key)) {
            return length;
        }
    }
    return -1;
}
module.exports = assocIndexOf;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheDelete.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var assocIndexOf = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_assocIndexOf.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var arrayProto = Array.prototype;
/** Built-in value references. */ var splice = arrayProto.splice;
/**
 * Removes `key` and its value from the list cache.
 *
 * @private
 * @name delete
 * @memberOf ListCache
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */ function listCacheDelete(key) {
    var data = this.__data__, index = assocIndexOf(data, key);
    if (index < 0) {
        return false;
    }
    var lastIndex = data.length - 1;
    if (index == lastIndex) {
        data.pop();
    } else {
        splice.call(data, index, 1);
    }
    --this.size;
    return true;
}
module.exports = listCacheDelete;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheGet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var assocIndexOf = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_assocIndexOf.js [app-client] (ecmascript)");
/**
 * Gets the list cache value for `key`.
 *
 * @private
 * @name get
 * @memberOf ListCache
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */ function listCacheGet(key) {
    var data = this.__data__, index = assocIndexOf(data, key);
    return index < 0 ? undefined : data[index][1];
}
module.exports = listCacheGet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheHas.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var assocIndexOf = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_assocIndexOf.js [app-client] (ecmascript)");
/**
 * Checks if a list cache value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf ListCache
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */ function listCacheHas(key) {
    return assocIndexOf(this.__data__, key) > -1;
}
module.exports = listCacheHas;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheSet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var assocIndexOf = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_assocIndexOf.js [app-client] (ecmascript)");
/**
 * Sets the list cache `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf ListCache
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the list cache instance.
 */ function listCacheSet(key, value) {
    var data = this.__data__, index = assocIndexOf(data, key);
    if (index < 0) {
        ++this.size;
        data.push([
            key,
            value
        ]);
    } else {
        data[index][1] = value;
    }
    return this;
}
module.exports = listCacheSet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_ListCache.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var listCacheClear = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheClear.js [app-client] (ecmascript)"), listCacheDelete = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheDelete.js [app-client] (ecmascript)"), listCacheGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheGet.js [app-client] (ecmascript)"), listCacheHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheHas.js [app-client] (ecmascript)"), listCacheSet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_listCacheSet.js [app-client] (ecmascript)");
/**
 * Creates an list cache object.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */ function ListCache(entries) {
    var index = -1, length = entries == null ? 0 : entries.length;
    this.clear();
    while(++index < length){
        var entry = entries[index];
        this.set(entry[0], entry[1]);
    }
}
// Add methods to `ListCache`.
ListCache.prototype.clear = listCacheClear;
ListCache.prototype['delete'] = listCacheDelete;
ListCache.prototype.get = listCacheGet;
ListCache.prototype.has = listCacheHas;
ListCache.prototype.set = listCacheSet;
module.exports = ListCache;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Map.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)"), root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/* Built-in method references that are verified to be native. */ var Map = getNative(root, 'Map');
module.exports = Map;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheClear.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Hash = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Hash.js [app-client] (ecmascript)"), ListCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_ListCache.js [app-client] (ecmascript)"), Map = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Map.js [app-client] (ecmascript)");
/**
 * Removes all key-value entries from the map.
 *
 * @private
 * @name clear
 * @memberOf MapCache
 */ function mapCacheClear() {
    this.size = 0;
    this.__data__ = {
        'hash': new Hash,
        'map': new (Map || ListCache),
        'string': new Hash
    };
}
module.exports = mapCacheClear;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isKeyable.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if `value` is suitable for use as unique object key.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is suitable, else `false`.
 */ function isKeyable(value) {
    var type = typeof value;
    return type == 'string' || type == 'number' || type == 'symbol' || type == 'boolean' ? value !== '__proto__' : value === null;
}
module.exports = isKeyable;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getMapData.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isKeyable = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isKeyable.js [app-client] (ecmascript)");
/**
 * Gets the data for `map`.
 *
 * @private
 * @param {Object} map The map to query.
 * @param {string} key The reference key.
 * @returns {*} Returns the map data.
 */ function getMapData(map, key) {
    var data = map.__data__;
    return isKeyable(key) ? data[typeof key == 'string' ? 'string' : 'hash'] : data.map;
}
module.exports = getMapData;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheDelete.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getMapData = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getMapData.js [app-client] (ecmascript)");
/**
 * Removes `key` and its value from the map.
 *
 * @private
 * @name delete
 * @memberOf MapCache
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */ function mapCacheDelete(key) {
    var result = getMapData(this, key)['delete'](key);
    this.size -= result ? 1 : 0;
    return result;
}
module.exports = mapCacheDelete;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheGet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getMapData = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getMapData.js [app-client] (ecmascript)");
/**
 * Gets the map value for `key`.
 *
 * @private
 * @name get
 * @memberOf MapCache
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */ function mapCacheGet(key) {
    return getMapData(this, key).get(key);
}
module.exports = mapCacheGet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheHas.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getMapData = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getMapData.js [app-client] (ecmascript)");
/**
 * Checks if a map value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf MapCache
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */ function mapCacheHas(key) {
    return getMapData(this, key).has(key);
}
module.exports = mapCacheHas;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheSet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getMapData = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getMapData.js [app-client] (ecmascript)");
/**
 * Sets the map `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf MapCache
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the map cache instance.
 */ function mapCacheSet(key, value) {
    var data = getMapData(this, key), size = data.size;
    data.set(key, value);
    this.size += data.size == size ? 0 : 1;
    return this;
}
module.exports = mapCacheSet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_MapCache.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var mapCacheClear = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheClear.js [app-client] (ecmascript)"), mapCacheDelete = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheDelete.js [app-client] (ecmascript)"), mapCacheGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheGet.js [app-client] (ecmascript)"), mapCacheHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheHas.js [app-client] (ecmascript)"), mapCacheSet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_mapCacheSet.js [app-client] (ecmascript)");
/**
 * Creates a map cache object to store key-value pairs.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */ function MapCache(entries) {
    var index = -1, length = entries == null ? 0 : entries.length;
    this.clear();
    while(++index < length){
        var entry = entries[index];
        this.set(entry[0], entry[1]);
    }
}
// Add methods to `MapCache`.
MapCache.prototype.clear = mapCacheClear;
MapCache.prototype['delete'] = mapCacheDelete;
MapCache.prototype.get = mapCacheGet;
MapCache.prototype.has = mapCacheHas;
MapCache.prototype.set = mapCacheSet;
module.exports = MapCache;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/memoize.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var MapCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_MapCache.js [app-client] (ecmascript)");
/** Error message constants. */ var FUNC_ERROR_TEXT = 'Expected a function';
/**
 * Creates a function that memoizes the result of `func`. If `resolver` is
 * provided, it determines the cache key for storing the result based on the
 * arguments provided to the memoized function. By default, the first argument
 * provided to the memoized function is used as the map cache key. The `func`
 * is invoked with the `this` binding of the memoized function.
 *
 * **Note:** The cache is exposed as the `cache` property on the memoized
 * function. Its creation may be customized by replacing the `_.memoize.Cache`
 * constructor with one whose instances implement the
 * [`Map`](http://ecma-international.org/ecma-262/7.0/#sec-properties-of-the-map-prototype-object)
 * method interface of `clear`, `delete`, `get`, `has`, and `set`.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Function
 * @param {Function} func The function to have its output memoized.
 * @param {Function} [resolver] The function to resolve the cache key.
 * @returns {Function} Returns the new memoized function.
 * @example
 *
 * var object = { 'a': 1, 'b': 2 };
 * var other = { 'c': 3, 'd': 4 };
 *
 * var values = _.memoize(_.values);
 * values(object);
 * // => [1, 2]
 *
 * values(other);
 * // => [3, 4]
 *
 * object.a = 2;
 * values(object);
 * // => [1, 2]
 *
 * // Modify the result cache.
 * values.cache.set(object, ['a', 'b']);
 * values(object);
 * // => ['a', 'b']
 *
 * // Replace `_.memoize.Cache`.
 * _.memoize.Cache = WeakMap;
 */ function memoize(func, resolver) {
    if (typeof func != 'function' || resolver != null && typeof resolver != 'function') {
        throw new TypeError(FUNC_ERROR_TEXT);
    }
    var memoized = function() {
        var args = arguments, key = resolver ? resolver.apply(this, args) : args[0], cache = memoized.cache;
        if (cache.has(key)) {
            return cache.get(key);
        }
        var result = func.apply(this, args);
        memoized.cache = cache.set(key, result) || cache;
        return result;
    };
    memoized.cache = new (memoize.Cache || MapCache);
    return memoized;
}
// Expose `MapCache`.
memoize.Cache = MapCache;
module.exports = memoize;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_memoizeCapped.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var memoize = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/memoize.js [app-client] (ecmascript)");
/** Used as the maximum memoize cache size. */ var MAX_MEMOIZE_SIZE = 500;
/**
 * A specialized version of `_.memoize` which clears the memoized function's
 * cache when it exceeds `MAX_MEMOIZE_SIZE`.
 *
 * @private
 * @param {Function} func The function to have its output memoized.
 * @returns {Function} Returns the new memoized function.
 */ function memoizeCapped(func) {
    var result = memoize(func, function(key) {
        if (cache.size === MAX_MEMOIZE_SIZE) {
            cache.clear();
        }
        return key;
    });
    var cache = result.cache;
    return result;
}
module.exports = memoizeCapped;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stringToPath.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var memoizeCapped = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_memoizeCapped.js [app-client] (ecmascript)");
/** Used to match property names within property paths. */ var rePropName = /[^.[\]]+|\[(?:(-?\d+(?:\.\d+)?)|(["'])((?:(?!\2)[^\\]|\\.)*?)\2)\]|(?=(?:\.|\[\])(?:\.|\[\]|$))/g;
/** Used to match backslashes in property paths. */ var reEscapeChar = /\\(\\)?/g;
/**
 * Converts `string` to a property path array.
 *
 * @private
 * @param {string} string The string to convert.
 * @returns {Array} Returns the property path array.
 */ var stringToPath = memoizeCapped(function(string) {
    var result = [];
    if (string.charCodeAt(0) === 46 /* . */ ) {
        result.push('');
    }
    string.replace(rePropName, function(match, number, quote, subString) {
        result.push(quote ? subString.replace(reEscapeChar, '$1') : number || match);
    });
    return result;
});
module.exports = stringToPath;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayMap.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A specialized version of `_.map` for arrays without support for iteratee
 * shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns the new mapped array.
 */ function arrayMap(array, iteratee) {
    var index = -1, length = array == null ? 0 : array.length, result = Array(length);
    while(++index < length){
        result[index] = iteratee(array[index], index, array);
    }
    return result;
}
module.exports = arrayMap;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseToString.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Symbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Symbol.js [app-client] (ecmascript)"), arrayMap = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayMap.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isSymbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)");
/** Used as references for various `Number` constants. */ var INFINITY = 1 / 0;
/** Used to convert symbols to primitives and strings. */ var symbolProto = Symbol ? Symbol.prototype : undefined, symbolToString = symbolProto ? symbolProto.toString : undefined;
/**
 * The base implementation of `_.toString` which doesn't convert nullish
 * values to empty strings.
 *
 * @private
 * @param {*} value The value to process.
 * @returns {string} Returns the string.
 */ function baseToString(value) {
    // Exit early for strings to avoid a performance hit in some environments.
    if (typeof value == 'string') {
        return value;
    }
    if (isArray(value)) {
        // Recursively convert values (susceptible to call stack limits).
        return arrayMap(value, baseToString) + '';
    }
    if (isSymbol(value)) {
        return symbolToString ? symbolToString.call(value) : '';
    }
    var result = value + '';
    return result == '0' && 1 / value == -INFINITY ? '-0' : result;
}
module.exports = baseToString;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/toString.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseToString = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseToString.js [app-client] (ecmascript)");
/**
 * Converts `value` to a string. An empty string is returned for `null`
 * and `undefined` values. The sign of `-0` is preserved.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to convert.
 * @returns {string} Returns the converted string.
 * @example
 *
 * _.toString(null);
 * // => ''
 *
 * _.toString(-0);
 * // => '-0'
 *
 * _.toString([1, 2, 3]);
 * // => '1,2,3'
 */ function toString(value) {
    return value == null ? '' : baseToString(value);
}
module.exports = toString;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_castPath.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isKey.js [app-client] (ecmascript)"), stringToPath = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stringToPath.js [app-client] (ecmascript)"), toString = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toString.js [app-client] (ecmascript)");
/**
 * Casts `value` to a path array if it's not one.
 *
 * @private
 * @param {*} value The value to inspect.
 * @param {Object} [object] The object to query keys on.
 * @returns {Array} Returns the cast property path array.
 */ function castPath(value, object) {
    if (isArray(value)) {
        return value;
    }
    return isKey(value, object) ? [
        value
    ] : stringToPath(toString(value));
}
module.exports = castPath;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_toKey.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isSymbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)");
/** Used as references for various `Number` constants. */ var INFINITY = 1 / 0;
/**
 * Converts `value` to a string key if it's not a string or symbol.
 *
 * @private
 * @param {*} value The value to inspect.
 * @returns {string|symbol} Returns the key.
 */ function toKey(value) {
    if (typeof value == 'string' || isSymbol(value)) {
        return value;
    }
    var result = value + '';
    return result == '0' && 1 / value == -INFINITY ? '-0' : result;
}
module.exports = toKey;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var castPath = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_castPath.js [app-client] (ecmascript)"), toKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_toKey.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.get` without support for default values.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {Array|string} path The path of the property to get.
 * @returns {*} Returns the resolved value.
 */ function baseGet(object, path) {
    path = castPath(path, object);
    var index = 0, length = path.length;
    while(object != null && index < length){
        object = object[toKey(path[index++])];
    }
    return index && index == length ? object : undefined;
}
module.exports = baseGet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGet.js [app-client] (ecmascript)");
/**
 * Gets the value at `path` of `object`. If the resolved value is
 * `undefined`, the `defaultValue` is returned in its place.
 *
 * @static
 * @memberOf _
 * @since 3.7.0
 * @category Object
 * @param {Object} object The object to query.
 * @param {Array|string} path The path of the property to get.
 * @param {*} [defaultValue] The value returned for `undefined` resolved values.
 * @returns {*} Returns the resolved value.
 * @example
 *
 * var object = { 'a': [{ 'b': { 'c': 3 } }] };
 *
 * _.get(object, 'a[0].b.c');
 * // => 3
 *
 * _.get(object, ['a', '0', 'b', 'c']);
 * // => 3
 *
 * _.get(object, 'a.b.c', 'default');
 * // => 'default'
 */ function get(object, path, defaultValue) {
    var result = object == null ? undefined : baseGet(object, path);
    return result === undefined ? defaultValue : result;
}
module.exports = get;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayPush.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Appends the elements of `values` to `array`.
 *
 * @private
 * @param {Array} array The array to modify.
 * @param {Array} values The values to append.
 * @returns {Array} Returns `array`.
 */ function arrayPush(array, values) {
    var index = -1, length = values.length, offset = array.length;
    while(++index < length){
        array[offset + index] = values[index];
    }
    return array;
}
module.exports = arrayPush;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsArguments.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var argsTag = '[object Arguments]';
/**
 * The base implementation of `_.isArguments`.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an `arguments` object,
 */ function baseIsArguments(value) {
    return isObjectLike(value) && baseGetTag(value) == argsTag;
}
module.exports = baseIsArguments;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isArguments.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsArguments = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsArguments.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/** Built-in value references. */ var propertyIsEnumerable = objectProto.propertyIsEnumerable;
/**
 * Checks if `value` is likely an `arguments` object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is an `arguments` object,
 *  else `false`.
 * @example
 *
 * _.isArguments(function() { return arguments; }());
 * // => true
 *
 * _.isArguments([1, 2, 3]);
 * // => false
 */ var isArguments = baseIsArguments(function() {
    return arguments;
}()) ? baseIsArguments : function(value) {
    return isObjectLike(value) && hasOwnProperty.call(value, 'callee') && !propertyIsEnumerable.call(value, 'callee');
};
module.exports = isArguments;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isFlattenable.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Symbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Symbol.js [app-client] (ecmascript)"), isArguments = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArguments.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)");
/** Built-in value references. */ var spreadableSymbol = Symbol ? Symbol.isConcatSpreadable : undefined;
/**
 * Checks if `value` is a flattenable `arguments` object or array.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is flattenable, else `false`.
 */ function isFlattenable(value) {
    return isArray(value) || isArguments(value) || !!(spreadableSymbol && value && value[spreadableSymbol]);
}
module.exports = isFlattenable;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFlatten.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayPush = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayPush.js [app-client] (ecmascript)"), isFlattenable = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isFlattenable.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.flatten` with support for restricting flattening.
 *
 * @private
 * @param {Array} array The array to flatten.
 * @param {number} depth The maximum recursion depth.
 * @param {boolean} [predicate=isFlattenable] The function invoked per iteration.
 * @param {boolean} [isStrict] Restrict to values that pass `predicate` checks.
 * @param {Array} [result=[]] The initial result value.
 * @returns {Array} Returns the new flattened array.
 */ function baseFlatten(array, depth, predicate, isStrict, result) {
    var index = -1, length = array.length;
    predicate || (predicate = isFlattenable);
    result || (result = []);
    while(++index < length){
        var value = array[index];
        if (depth > 0 && predicate(value)) {
            if (depth > 1) {
                // Recursively flatten arrays (susceptible to call stack limits).
                baseFlatten(value, depth - 1, predicate, isStrict, result);
            } else {
                arrayPush(result, value);
            }
        } else if (!isStrict) {
            result[result.length] = value;
        }
    }
    return result;
}
module.exports = baseFlatten;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stackClear.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var ListCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_ListCache.js [app-client] (ecmascript)");
/**
 * Removes all key-value entries from the stack.
 *
 * @private
 * @name clear
 * @memberOf Stack
 */ function stackClear() {
    this.__data__ = new ListCache;
    this.size = 0;
}
module.exports = stackClear;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stackDelete.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Removes `key` and its value from the stack.
 *
 * @private
 * @name delete
 * @memberOf Stack
 * @param {string} key The key of the value to remove.
 * @returns {boolean} Returns `true` if the entry was removed, else `false`.
 */ function stackDelete(key) {
    var data = this.__data__, result = data['delete'](key);
    this.size = data.size;
    return result;
}
module.exports = stackDelete;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stackGet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Gets the stack value for `key`.
 *
 * @private
 * @name get
 * @memberOf Stack
 * @param {string} key The key of the value to get.
 * @returns {*} Returns the entry value.
 */ function stackGet(key) {
    return this.__data__.get(key);
}
module.exports = stackGet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stackHas.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if a stack value for `key` exists.
 *
 * @private
 * @name has
 * @memberOf Stack
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */ function stackHas(key) {
    return this.__data__.has(key);
}
module.exports = stackHas;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stackSet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var ListCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_ListCache.js [app-client] (ecmascript)"), Map = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Map.js [app-client] (ecmascript)"), MapCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_MapCache.js [app-client] (ecmascript)");
/** Used as the size to enable large array optimizations. */ var LARGE_ARRAY_SIZE = 200;
/**
 * Sets the stack `key` to `value`.
 *
 * @private
 * @name set
 * @memberOf Stack
 * @param {string} key The key of the value to set.
 * @param {*} value The value to set.
 * @returns {Object} Returns the stack cache instance.
 */ function stackSet(key, value) {
    var data = this.__data__;
    if (data instanceof ListCache) {
        var pairs = data.__data__;
        if (!Map || pairs.length < LARGE_ARRAY_SIZE - 1) {
            pairs.push([
                key,
                value
            ]);
            this.size = ++data.size;
            return this;
        }
        data = this.__data__ = new MapCache(pairs);
    }
    data.set(key, value);
    this.size = data.size;
    return this;
}
module.exports = stackSet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Stack.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var ListCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_ListCache.js [app-client] (ecmascript)"), stackClear = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stackClear.js [app-client] (ecmascript)"), stackDelete = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stackDelete.js [app-client] (ecmascript)"), stackGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stackGet.js [app-client] (ecmascript)"), stackHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stackHas.js [app-client] (ecmascript)"), stackSet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stackSet.js [app-client] (ecmascript)");
/**
 * Creates a stack cache object to store key-value pairs.
 *
 * @private
 * @constructor
 * @param {Array} [entries] The key-value pairs to cache.
 */ function Stack(entries) {
    var data = this.__data__ = new ListCache(entries);
    this.size = data.size;
}
// Add methods to `Stack`.
Stack.prototype.clear = stackClear;
Stack.prototype['delete'] = stackDelete;
Stack.prototype.get = stackGet;
Stack.prototype.has = stackHas;
Stack.prototype.set = stackSet;
module.exports = Stack;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_setCacheAdd.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used to stand-in for `undefined` hash values. */ var HASH_UNDEFINED = '__lodash_hash_undefined__';
/**
 * Adds `value` to the array cache.
 *
 * @private
 * @name add
 * @memberOf SetCache
 * @alias push
 * @param {*} value The value to cache.
 * @returns {Object} Returns the cache instance.
 */ function setCacheAdd(value) {
    this.__data__.set(value, HASH_UNDEFINED);
    return this;
}
module.exports = setCacheAdd;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_setCacheHas.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if `value` is in the array cache.
 *
 * @private
 * @name has
 * @memberOf SetCache
 * @param {*} value The value to search for.
 * @returns {number} Returns `true` if `value` is found, else `false`.
 */ function setCacheHas(value) {
    return this.__data__.has(value);
}
module.exports = setCacheHas;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_SetCache.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var MapCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_MapCache.js [app-client] (ecmascript)"), setCacheAdd = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_setCacheAdd.js [app-client] (ecmascript)"), setCacheHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_setCacheHas.js [app-client] (ecmascript)");
/**
 *
 * Creates an array cache object to store unique values.
 *
 * @private
 * @constructor
 * @param {Array} [values] The values to cache.
 */ function SetCache(values) {
    var index = -1, length = values == null ? 0 : values.length;
    this.__data__ = new MapCache;
    while(++index < length){
        this.add(values[index]);
    }
}
// Add methods to `SetCache`.
SetCache.prototype.add = SetCache.prototype.push = setCacheAdd;
SetCache.prototype.has = setCacheHas;
module.exports = SetCache;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arraySome.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A specialized version of `_.some` for arrays without support for iteratee
 * shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} predicate The function invoked per iteration.
 * @returns {boolean} Returns `true` if any element passes the predicate check,
 *  else `false`.
 */ function arraySome(array, predicate) {
    var index = -1, length = array == null ? 0 : array.length;
    while(++index < length){
        if (predicate(array[index], index, array)) {
            return true;
        }
    }
    return false;
}
module.exports = arraySome;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_cacheHas.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Checks if a `cache` value for `key` exists.
 *
 * @private
 * @param {Object} cache The cache to query.
 * @param {string} key The key of the entry to check.
 * @returns {boolean} Returns `true` if an entry for `key` exists, else `false`.
 */ function cacheHas(cache, key) {
    return cache.has(key);
}
module.exports = cacheHas;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_equalArrays.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var SetCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_SetCache.js [app-client] (ecmascript)"), arraySome = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arraySome.js [app-client] (ecmascript)"), cacheHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_cacheHas.js [app-client] (ecmascript)");
/** Used to compose bitmasks for value comparisons. */ var COMPARE_PARTIAL_FLAG = 1, COMPARE_UNORDERED_FLAG = 2;
/**
 * A specialized version of `baseIsEqualDeep` for arrays with support for
 * partial deep comparisons.
 *
 * @private
 * @param {Array} array The array to compare.
 * @param {Array} other The other array to compare.
 * @param {number} bitmask The bitmask flags. See `baseIsEqual` for more details.
 * @param {Function} customizer The function to customize comparisons.
 * @param {Function} equalFunc The function to determine equivalents of values.
 * @param {Object} stack Tracks traversed `array` and `other` objects.
 * @returns {boolean} Returns `true` if the arrays are equivalent, else `false`.
 */ function equalArrays(array, other, bitmask, customizer, equalFunc, stack) {
    var isPartial = bitmask & COMPARE_PARTIAL_FLAG, arrLength = array.length, othLength = other.length;
    if (arrLength != othLength && !(isPartial && othLength > arrLength)) {
        return false;
    }
    // Check that cyclic values are equal.
    var arrStacked = stack.get(array);
    var othStacked = stack.get(other);
    if (arrStacked && othStacked) {
        return arrStacked == other && othStacked == array;
    }
    var index = -1, result = true, seen = bitmask & COMPARE_UNORDERED_FLAG ? new SetCache : undefined;
    stack.set(array, other);
    stack.set(other, array);
    // Ignore non-index properties.
    while(++index < arrLength){
        var arrValue = array[index], othValue = other[index];
        if (customizer) {
            var compared = isPartial ? customizer(othValue, arrValue, index, other, array, stack) : customizer(arrValue, othValue, index, array, other, stack);
        }
        if (compared !== undefined) {
            if (compared) {
                continue;
            }
            result = false;
            break;
        }
        // Recursively compare arrays (susceptible to call stack limits).
        if (seen) {
            if (!arraySome(other, function(othValue, othIndex) {
                if (!cacheHas(seen, othIndex) && (arrValue === othValue || equalFunc(arrValue, othValue, bitmask, customizer, stack))) {
                    return seen.push(othIndex);
                }
            })) {
                result = false;
                break;
            }
        } else if (!(arrValue === othValue || equalFunc(arrValue, othValue, bitmask, customizer, stack))) {
            result = false;
            break;
        }
    }
    stack['delete'](array);
    stack['delete'](other);
    return result;
}
module.exports = equalArrays;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Uint8Array.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/** Built-in value references. */ var Uint8Array = root.Uint8Array;
module.exports = Uint8Array;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_mapToArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Converts `map` to its key-value pairs.
 *
 * @private
 * @param {Object} map The map to convert.
 * @returns {Array} Returns the key-value pairs.
 */ function mapToArray(map) {
    var index = -1, result = Array(map.size);
    map.forEach(function(value, key) {
        result[++index] = [
            key,
            value
        ];
    });
    return result;
}
module.exports = mapToArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_setToArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Converts `set` to an array of its values.
 *
 * @private
 * @param {Object} set The set to convert.
 * @returns {Array} Returns the values.
 */ function setToArray(set) {
    var index = -1, result = Array(set.size);
    set.forEach(function(value) {
        result[++index] = value;
    });
    return result;
}
module.exports = setToArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_equalByTag.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Symbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Symbol.js [app-client] (ecmascript)"), Uint8Array = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Uint8Array.js [app-client] (ecmascript)"), eq = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/eq.js [app-client] (ecmascript)"), equalArrays = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_equalArrays.js [app-client] (ecmascript)"), mapToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_mapToArray.js [app-client] (ecmascript)"), setToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_setToArray.js [app-client] (ecmascript)");
/** Used to compose bitmasks for value comparisons. */ var COMPARE_PARTIAL_FLAG = 1, COMPARE_UNORDERED_FLAG = 2;
/** `Object#toString` result references. */ var boolTag = '[object Boolean]', dateTag = '[object Date]', errorTag = '[object Error]', mapTag = '[object Map]', numberTag = '[object Number]', regexpTag = '[object RegExp]', setTag = '[object Set]', stringTag = '[object String]', symbolTag = '[object Symbol]';
var arrayBufferTag = '[object ArrayBuffer]', dataViewTag = '[object DataView]';
/** Used to convert symbols to primitives and strings. */ var symbolProto = Symbol ? Symbol.prototype : undefined, symbolValueOf = symbolProto ? symbolProto.valueOf : undefined;
/**
 * A specialized version of `baseIsEqualDeep` for comparing objects of
 * the same `toStringTag`.
 *
 * **Note:** This function only supports comparing values with tags of
 * `Boolean`, `Date`, `Error`, `Number`, `RegExp`, or `String`.
 *
 * @private
 * @param {Object} object The object to compare.
 * @param {Object} other The other object to compare.
 * @param {string} tag The `toStringTag` of the objects to compare.
 * @param {number} bitmask The bitmask flags. See `baseIsEqual` for more details.
 * @param {Function} customizer The function to customize comparisons.
 * @param {Function} equalFunc The function to determine equivalents of values.
 * @param {Object} stack Tracks traversed `object` and `other` objects.
 * @returns {boolean} Returns `true` if the objects are equivalent, else `false`.
 */ function equalByTag(object, other, tag, bitmask, customizer, equalFunc, stack) {
    switch(tag){
        case dataViewTag:
            if (object.byteLength != other.byteLength || object.byteOffset != other.byteOffset) {
                return false;
            }
            object = object.buffer;
            other = other.buffer;
        case arrayBufferTag:
            if (object.byteLength != other.byteLength || !equalFunc(new Uint8Array(object), new Uint8Array(other))) {
                return false;
            }
            return true;
        case boolTag:
        case dateTag:
        case numberTag:
            // Coerce booleans to `1` or `0` and dates to milliseconds.
            // Invalid dates are coerced to `NaN`.
            return eq(+object, +other);
        case errorTag:
            return object.name == other.name && object.message == other.message;
        case regexpTag:
        case stringTag:
            // Coerce regexes to strings and treat strings, primitives and objects,
            // as equal. See http://www.ecma-international.org/ecma-262/7.0/#sec-regexp.prototype.tostring
            // for more details.
            return object == other + '';
        case mapTag:
            var convert = mapToArray;
        case setTag:
            var isPartial = bitmask & COMPARE_PARTIAL_FLAG;
            convert || (convert = setToArray);
            if (object.size != other.size && !isPartial) {
                return false;
            }
            // Assume cyclic values are equal.
            var stacked = stack.get(object);
            if (stacked) {
                return stacked == other;
            }
            bitmask |= COMPARE_UNORDERED_FLAG;
            // Recursively compare objects (susceptible to call stack limits).
            stack.set(object, other);
            var result = equalArrays(convert(object), convert(other), bitmask, customizer, equalFunc, stack);
            stack['delete'](object);
            return result;
        case symbolTag:
            if (symbolValueOf) {
                return symbolValueOf.call(object) == symbolValueOf.call(other);
            }
    }
    return false;
}
module.exports = equalByTag;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetAllKeys.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayPush = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayPush.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)");
/**
 * The base implementation of `getAllKeys` and `getAllKeysIn` which uses
 * `keysFunc` and `symbolsFunc` to get the enumerable property names and
 * symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {Function} keysFunc The function to get the keys of `object`.
 * @param {Function} symbolsFunc The function to get the symbols of `object`.
 * @returns {Array} Returns the array of property names and symbols.
 */ function baseGetAllKeys(object, keysFunc, symbolsFunc) {
    var result = keysFunc(object);
    return isArray(object) ? result : arrayPush(result, symbolsFunc(object));
}
module.exports = baseGetAllKeys;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayFilter.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A specialized version of `_.filter` for arrays without support for
 * iteratee shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} predicate The function invoked per iteration.
 * @returns {Array} Returns the new filtered array.
 */ function arrayFilter(array, predicate) {
    var index = -1, length = array == null ? 0 : array.length, resIndex = 0, result = [];
    while(++index < length){
        var value = array[index];
        if (predicate(value, index, array)) {
            result[resIndex++] = value;
        }
    }
    return result;
}
module.exports = arrayFilter;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/stubArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * This method returns a new empty array.
 *
 * @static
 * @memberOf _
 * @since 4.13.0
 * @category Util
 * @returns {Array} Returns the new empty array.
 * @example
 *
 * var arrays = _.times(2, _.stubArray);
 *
 * console.log(arrays);
 * // => [[], []]
 *
 * console.log(arrays[0] === arrays[1]);
 * // => false
 */ function stubArray() {
    return [];
}
module.exports = stubArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getSymbols.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayFilter = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayFilter.js [app-client] (ecmascript)"), stubArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/stubArray.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Built-in value references. */ var propertyIsEnumerable = objectProto.propertyIsEnumerable;
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeGetSymbols = Object.getOwnPropertySymbols;
/**
 * Creates an array of the own enumerable symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of symbols.
 */ var getSymbols = !nativeGetSymbols ? stubArray : function(object) {
    if (object == null) {
        return [];
    }
    object = Object(object);
    return arrayFilter(nativeGetSymbols(object), function(symbol) {
        return propertyIsEnumerable.call(object, symbol);
    });
};
module.exports = getSymbols;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseTimes.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.times` without support for iteratee shorthands
 * or max array length checks.
 *
 * @private
 * @param {number} n The number of times to invoke `iteratee`.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns the array of results.
 */ function baseTimes(n, iteratee) {
    var index = -1, result = Array(n);
    while(++index < n){
        result[index] = iteratee(index);
    }
    return result;
}
module.exports = baseTimes;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/stubFalse.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * This method returns `false`.
 *
 * @static
 * @memberOf _
 * @since 4.13.0
 * @category Util
 * @returns {boolean} Returns `false`.
 * @example
 *
 * _.times(2, _.stubFalse);
 * // => [false, false]
 */ function stubFalse() {
    return false;
}
module.exports = stubFalse;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isBuffer.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)"), stubFalse = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/stubFalse.js [app-client] (ecmascript)");
/** Detect free variable `exports`. */ var freeExports = ("TURBOPACK compile-time value", "object") == 'object' && exports && !exports.nodeType && exports;
/** Detect free variable `module`. */ var freeModule = freeExports && ("TURBOPACK compile-time value", "object") == 'object' && module && !module.nodeType && module;
/** Detect the popular CommonJS extension `module.exports`. */ var moduleExports = freeModule && freeModule.exports === freeExports;
/** Built-in value references. */ var Buffer = moduleExports ? root.Buffer : undefined;
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeIsBuffer = Buffer ? Buffer.isBuffer : undefined;
/**
 * Checks if `value` is a buffer.
 *
 * @static
 * @memberOf _
 * @since 4.3.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a buffer, else `false`.
 * @example
 *
 * _.isBuffer(new Buffer(2));
 * // => true
 *
 * _.isBuffer(new Uint8Array(2));
 * // => false
 */ var isBuffer = nativeIsBuffer || stubFalse;
module.exports = isBuffer;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsTypedArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isLength = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isLength.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var argsTag = '[object Arguments]', arrayTag = '[object Array]', boolTag = '[object Boolean]', dateTag = '[object Date]', errorTag = '[object Error]', funcTag = '[object Function]', mapTag = '[object Map]', numberTag = '[object Number]', objectTag = '[object Object]', regexpTag = '[object RegExp]', setTag = '[object Set]', stringTag = '[object String]', weakMapTag = '[object WeakMap]';
var arrayBufferTag = '[object ArrayBuffer]', dataViewTag = '[object DataView]', float32Tag = '[object Float32Array]', float64Tag = '[object Float64Array]', int8Tag = '[object Int8Array]', int16Tag = '[object Int16Array]', int32Tag = '[object Int32Array]', uint8Tag = '[object Uint8Array]', uint8ClampedTag = '[object Uint8ClampedArray]', uint16Tag = '[object Uint16Array]', uint32Tag = '[object Uint32Array]';
/** Used to identify `toStringTag` values of typed arrays. */ var typedArrayTags = {};
typedArrayTags[float32Tag] = typedArrayTags[float64Tag] = typedArrayTags[int8Tag] = typedArrayTags[int16Tag] = typedArrayTags[int32Tag] = typedArrayTags[uint8Tag] = typedArrayTags[uint8ClampedTag] = typedArrayTags[uint16Tag] = typedArrayTags[uint32Tag] = true;
typedArrayTags[argsTag] = typedArrayTags[arrayTag] = typedArrayTags[arrayBufferTag] = typedArrayTags[boolTag] = typedArrayTags[dataViewTag] = typedArrayTags[dateTag] = typedArrayTags[errorTag] = typedArrayTags[funcTag] = typedArrayTags[mapTag] = typedArrayTags[numberTag] = typedArrayTags[objectTag] = typedArrayTags[regexpTag] = typedArrayTags[setTag] = typedArrayTags[stringTag] = typedArrayTags[weakMapTag] = false;
/**
 * The base implementation of `_.isTypedArray` without Node.js optimizations.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a typed array, else `false`.
 */ function baseIsTypedArray(value) {
    return isObjectLike(value) && isLength(value.length) && !!typedArrayTags[baseGetTag(value)];
}
module.exports = baseIsTypedArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseUnary.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.unary` without support for storing metadata.
 *
 * @private
 * @param {Function} func The function to cap arguments for.
 * @returns {Function} Returns the new capped function.
 */ function baseUnary(func) {
    return function(value) {
        return func(value);
    };
}
module.exports = baseUnary;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_nodeUtil.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var freeGlobal = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_freeGlobal.js [app-client] (ecmascript)");
/** Detect free variable `exports`. */ var freeExports = ("TURBOPACK compile-time value", "object") == 'object' && exports && !exports.nodeType && exports;
/** Detect free variable `module`. */ var freeModule = freeExports && ("TURBOPACK compile-time value", "object") == 'object' && module && !module.nodeType && module;
/** Detect the popular CommonJS extension `module.exports`. */ var moduleExports = freeModule && freeModule.exports === freeExports;
/** Detect free variable `process` from Node.js. */ var freeProcess = moduleExports && freeGlobal.process;
/** Used to access faster Node.js helpers. */ var nodeUtil = function() {
    try {
        // Use `util.types` for Node.js 10+.
        var types = freeModule && freeModule.require && freeModule.require('util').types;
        if (types) {
            return types;
        }
        // Legacy `process.binding('util')` for Node.js < 10.
        return freeProcess && freeProcess.binding && freeProcess.binding('util');
    } catch (e) {}
}();
module.exports = nodeUtil;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isTypedArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsTypedArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsTypedArray.js [app-client] (ecmascript)"), baseUnary = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseUnary.js [app-client] (ecmascript)"), nodeUtil = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_nodeUtil.js [app-client] (ecmascript)");
/* Node.js helper references. */ var nodeIsTypedArray = nodeUtil && nodeUtil.isTypedArray;
/**
 * Checks if `value` is classified as a typed array.
 *
 * @static
 * @memberOf _
 * @since 3.0.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a typed array, else `false`.
 * @example
 *
 * _.isTypedArray(new Uint8Array);
 * // => true
 *
 * _.isTypedArray([]);
 * // => false
 */ var isTypedArray = nodeIsTypedArray ? baseUnary(nodeIsTypedArray) : baseIsTypedArray;
module.exports = isTypedArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayLikeKeys.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseTimes = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseTimes.js [app-client] (ecmascript)"), isArguments = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArguments.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isBuffer = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isBuffer.js [app-client] (ecmascript)"), isIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIndex.js [app-client] (ecmascript)"), isTypedArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isTypedArray.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * Creates an array of the enumerable property names of the array-like `value`.
 *
 * @private
 * @param {*} value The value to query.
 * @param {boolean} inherited Specify returning inherited property names.
 * @returns {Array} Returns the array of property names.
 */ function arrayLikeKeys(value, inherited) {
    var isArr = isArray(value), isArg = !isArr && isArguments(value), isBuff = !isArr && !isArg && isBuffer(value), isType = !isArr && !isArg && !isBuff && isTypedArray(value), skipIndexes = isArr || isArg || isBuff || isType, result = skipIndexes ? baseTimes(value.length, String) : [], length = result.length;
    for(var key in value){
        if ((inherited || hasOwnProperty.call(value, key)) && !(skipIndexes && (// Safari 9 has enumerable `arguments.length` in strict mode.
        key == 'length' || isBuff && (key == 'offset' || key == 'parent') || isType && (key == 'buffer' || key == 'byteLength' || key == 'byteOffset') || // Skip index properties.
        isIndex(key, length)))) {
            result.push(key);
        }
    }
    return result;
}
module.exports = arrayLikeKeys;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isPrototype.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used for built-in method references. */ var objectProto = Object.prototype;
/**
 * Checks if `value` is likely a prototype object.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a prototype, else `false`.
 */ function isPrototype(value) {
    var Ctor = value && value.constructor, proto = typeof Ctor == 'function' && Ctor.prototype || objectProto;
    return value === proto;
}
module.exports = isPrototype;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_overArg.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Creates a unary function that invokes `func` with its argument transformed.
 *
 * @private
 * @param {Function} func The function to wrap.
 * @param {Function} transform The argument transform.
 * @returns {Function} Returns the new function.
 */ function overArg(func, transform) {
    return function(arg) {
        return func(transform(arg));
    };
}
module.exports = overArg;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeKeys.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var overArg = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_overArg.js [app-client] (ecmascript)");
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeKeys = overArg(Object.keys, Object);
module.exports = nativeKeys;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseKeys.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isPrototype = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isPrototype.js [app-client] (ecmascript)"), nativeKeys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_nativeKeys.js [app-client] (ecmascript)");
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * The base implementation of `_.keys` which doesn't treat sparse arrays as dense.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 */ function baseKeys(object) {
    if (!isPrototype(object)) {
        return nativeKeys(object);
    }
    var result = [];
    for(var key in Object(object)){
        if (hasOwnProperty.call(object, key) && key != 'constructor') {
            result.push(key);
        }
    }
    return result;
}
module.exports = baseKeys;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/keys.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayLikeKeys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayLikeKeys.js [app-client] (ecmascript)"), baseKeys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseKeys.js [app-client] (ecmascript)"), isArrayLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArrayLike.js [app-client] (ecmascript)");
/**
 * Creates an array of the own enumerable property names of `object`.
 *
 * **Note:** Non-object values are coerced to objects. See the
 * [ES spec](http://ecma-international.org/ecma-262/7.0/#sec-object.keys)
 * for more details.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Object
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names.
 * @example
 *
 * function Foo() {
 *   this.a = 1;
 *   this.b = 2;
 * }
 *
 * Foo.prototype.c = 3;
 *
 * _.keys(new Foo);
 * // => ['a', 'b'] (iteration order is not guaranteed)
 *
 * _.keys('hi');
 * // => ['0', '1']
 */ function keys(object) {
    return isArrayLike(object) ? arrayLikeKeys(object) : baseKeys(object);
}
module.exports = keys;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getAllKeys.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetAllKeys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetAllKeys.js [app-client] (ecmascript)"), getSymbols = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getSymbols.js [app-client] (ecmascript)"), keys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/keys.js [app-client] (ecmascript)");
/**
 * Creates an array of own enumerable property names and symbols of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the array of property names and symbols.
 */ function getAllKeys(object) {
    return baseGetAllKeys(object, keys, getSymbols);
}
module.exports = getAllKeys;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_equalObjects.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getAllKeys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getAllKeys.js [app-client] (ecmascript)");
/** Used to compose bitmasks for value comparisons. */ var COMPARE_PARTIAL_FLAG = 1;
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * A specialized version of `baseIsEqualDeep` for objects with support for
 * partial deep comparisons.
 *
 * @private
 * @param {Object} object The object to compare.
 * @param {Object} other The other object to compare.
 * @param {number} bitmask The bitmask flags. See `baseIsEqual` for more details.
 * @param {Function} customizer The function to customize comparisons.
 * @param {Function} equalFunc The function to determine equivalents of values.
 * @param {Object} stack Tracks traversed `object` and `other` objects.
 * @returns {boolean} Returns `true` if the objects are equivalent, else `false`.
 */ function equalObjects(object, other, bitmask, customizer, equalFunc, stack) {
    var isPartial = bitmask & COMPARE_PARTIAL_FLAG, objProps = getAllKeys(object), objLength = objProps.length, othProps = getAllKeys(other), othLength = othProps.length;
    if (objLength != othLength && !isPartial) {
        return false;
    }
    var index = objLength;
    while(index--){
        var key = objProps[index];
        if (!(isPartial ? key in other : hasOwnProperty.call(other, key))) {
            return false;
        }
    }
    // Check that cyclic values are equal.
    var objStacked = stack.get(object);
    var othStacked = stack.get(other);
    if (objStacked && othStacked) {
        return objStacked == other && othStacked == object;
    }
    var result = true;
    stack.set(object, other);
    stack.set(other, object);
    var skipCtor = isPartial;
    while(++index < objLength){
        key = objProps[index];
        var objValue = object[key], othValue = other[key];
        if (customizer) {
            var compared = isPartial ? customizer(othValue, objValue, key, other, object, stack) : customizer(objValue, othValue, key, object, other, stack);
        }
        // Recursively compare objects (susceptible to call stack limits).
        if (!(compared === undefined ? objValue === othValue || equalFunc(objValue, othValue, bitmask, customizer, stack) : compared)) {
            result = false;
            break;
        }
        skipCtor || (skipCtor = key == 'constructor');
    }
    if (result && !skipCtor) {
        var objCtor = object.constructor, othCtor = other.constructor;
        // Non `Object` object instances with different constructors are not equal.
        if (objCtor != othCtor && 'constructor' in object && 'constructor' in other && !(typeof objCtor == 'function' && objCtor instanceof objCtor && typeof othCtor == 'function' && othCtor instanceof othCtor)) {
            result = false;
        }
    }
    stack['delete'](object);
    stack['delete'](other);
    return result;
}
module.exports = equalObjects;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_DataView.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)"), root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/* Built-in method references that are verified to be native. */ var DataView = getNative(root, 'DataView');
module.exports = DataView;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Promise.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)"), root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/* Built-in method references that are verified to be native. */ var Promise = getNative(root, 'Promise');
module.exports = Promise;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_Set.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)"), root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/* Built-in method references that are verified to be native. */ var Set = getNative(root, 'Set');
module.exports = Set;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_WeakMap.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)"), root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/* Built-in method references that are verified to be native. */ var WeakMap = getNative(root, 'WeakMap');
module.exports = WeakMap;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getTag.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var DataView = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_DataView.js [app-client] (ecmascript)"), Map = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Map.js [app-client] (ecmascript)"), Promise = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Promise.js [app-client] (ecmascript)"), Set = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Set.js [app-client] (ecmascript)"), WeakMap = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_WeakMap.js [app-client] (ecmascript)"), baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), toSource = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_toSource.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var mapTag = '[object Map]', objectTag = '[object Object]', promiseTag = '[object Promise]', setTag = '[object Set]', weakMapTag = '[object WeakMap]';
var dataViewTag = '[object DataView]';
/** Used to detect maps, sets, and weakmaps. */ var dataViewCtorString = toSource(DataView), mapCtorString = toSource(Map), promiseCtorString = toSource(Promise), setCtorString = toSource(Set), weakMapCtorString = toSource(WeakMap);
/**
 * Gets the `toStringTag` of `value`.
 *
 * @private
 * @param {*} value The value to query.
 * @returns {string} Returns the `toStringTag`.
 */ var getTag = baseGetTag;
// Fallback for data views, maps, sets, and weak maps in IE 11 and promises in Node.js < 6.
if (DataView && getTag(new DataView(new ArrayBuffer(1))) != dataViewTag || Map && getTag(new Map) != mapTag || Promise && getTag(Promise.resolve()) != promiseTag || Set && getTag(new Set) != setTag || WeakMap && getTag(new WeakMap) != weakMapTag) {
    getTag = function(value) {
        var result = baseGetTag(value), Ctor = result == objectTag ? value.constructor : undefined, ctorString = Ctor ? toSource(Ctor) : '';
        if (ctorString) {
            switch(ctorString){
                case dataViewCtorString:
                    return dataViewTag;
                case mapCtorString:
                    return mapTag;
                case promiseCtorString:
                    return promiseTag;
                case setCtorString:
                    return setTag;
                case weakMapCtorString:
                    return weakMapTag;
            }
        }
        return result;
    };
}
module.exports = getTag;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsEqualDeep.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Stack = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Stack.js [app-client] (ecmascript)"), equalArrays = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_equalArrays.js [app-client] (ecmascript)"), equalByTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_equalByTag.js [app-client] (ecmascript)"), equalObjects = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_equalObjects.js [app-client] (ecmascript)"), getTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getTag.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isBuffer = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isBuffer.js [app-client] (ecmascript)"), isTypedArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isTypedArray.js [app-client] (ecmascript)");
/** Used to compose bitmasks for value comparisons. */ var COMPARE_PARTIAL_FLAG = 1;
/** `Object#toString` result references. */ var argsTag = '[object Arguments]', arrayTag = '[object Array]', objectTag = '[object Object]';
/** Used for built-in method references. */ var objectProto = Object.prototype;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/**
 * A specialized version of `baseIsEqual` for arrays and objects which performs
 * deep comparisons and tracks traversed objects enabling objects with circular
 * references to be compared.
 *
 * @private
 * @param {Object} object The object to compare.
 * @param {Object} other The other object to compare.
 * @param {number} bitmask The bitmask flags. See `baseIsEqual` for more details.
 * @param {Function} customizer The function to customize comparisons.
 * @param {Function} equalFunc The function to determine equivalents of values.
 * @param {Object} [stack] Tracks traversed `object` and `other` objects.
 * @returns {boolean} Returns `true` if the objects are equivalent, else `false`.
 */ function baseIsEqualDeep(object, other, bitmask, customizer, equalFunc, stack) {
    var objIsArr = isArray(object), othIsArr = isArray(other), objTag = objIsArr ? arrayTag : getTag(object), othTag = othIsArr ? arrayTag : getTag(other);
    objTag = objTag == argsTag ? objectTag : objTag;
    othTag = othTag == argsTag ? objectTag : othTag;
    var objIsObj = objTag == objectTag, othIsObj = othTag == objectTag, isSameTag = objTag == othTag;
    if (isSameTag && isBuffer(object)) {
        if (!isBuffer(other)) {
            return false;
        }
        objIsArr = true;
        objIsObj = false;
    }
    if (isSameTag && !objIsObj) {
        stack || (stack = new Stack);
        return objIsArr || isTypedArray(object) ? equalArrays(object, other, bitmask, customizer, equalFunc, stack) : equalByTag(object, other, objTag, bitmask, customizer, equalFunc, stack);
    }
    if (!(bitmask & COMPARE_PARTIAL_FLAG)) {
        var objIsWrapped = objIsObj && hasOwnProperty.call(object, '__wrapped__'), othIsWrapped = othIsObj && hasOwnProperty.call(other, '__wrapped__');
        if (objIsWrapped || othIsWrapped) {
            var objUnwrapped = objIsWrapped ? object.value() : object, othUnwrapped = othIsWrapped ? other.value() : other;
            stack || (stack = new Stack);
            return equalFunc(objUnwrapped, othUnwrapped, bitmask, customizer, stack);
        }
    }
    if (!isSameTag) {
        return false;
    }
    stack || (stack = new Stack);
    return equalObjects(object, other, bitmask, customizer, equalFunc, stack);
}
module.exports = baseIsEqualDeep;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsEqual.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsEqualDeep = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsEqualDeep.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.isEqual` which supports partial comparisons
 * and tracks traversed objects.
 *
 * @private
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @param {boolean} bitmask The bitmask flags.
 *  1 - Unordered comparison
 *  2 - Partial comparison
 * @param {Function} [customizer] The function to customize comparisons.
 * @param {Object} [stack] Tracks traversed `value` and `other` objects.
 * @returns {boolean} Returns `true` if the values are equivalent, else `false`.
 */ function baseIsEqual(value, other, bitmask, customizer, stack) {
    if (value === other) {
        return true;
    }
    if (value == null || other == null || !isObjectLike(value) && !isObjectLike(other)) {
        return value !== value && other !== other;
    }
    return baseIsEqualDeep(value, other, bitmask, customizer, baseIsEqual, stack);
}
module.exports = baseIsEqual;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsMatch.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Stack = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Stack.js [app-client] (ecmascript)"), baseIsEqual = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsEqual.js [app-client] (ecmascript)");
/** Used to compose bitmasks for value comparisons. */ var COMPARE_PARTIAL_FLAG = 1, COMPARE_UNORDERED_FLAG = 2;
/**
 * The base implementation of `_.isMatch` without support for iteratee shorthands.
 *
 * @private
 * @param {Object} object The object to inspect.
 * @param {Object} source The object of property values to match.
 * @param {Array} matchData The property names, values, and compare flags to match.
 * @param {Function} [customizer] The function to customize comparisons.
 * @returns {boolean} Returns `true` if `object` is a match, else `false`.
 */ function baseIsMatch(object, source, matchData, customizer) {
    var index = matchData.length, length = index, noCustomizer = !customizer;
    if (object == null) {
        return !length;
    }
    object = Object(object);
    while(index--){
        var data = matchData[index];
        if (noCustomizer && data[2] ? data[1] !== object[data[0]] : !(data[0] in object)) {
            return false;
        }
    }
    while(++index < length){
        data = matchData[index];
        var key = data[0], objValue = object[key], srcValue = data[1];
        if (noCustomizer && data[2]) {
            if (objValue === undefined && !(key in object)) {
                return false;
            }
        } else {
            var stack = new Stack;
            if (customizer) {
                var result = customizer(objValue, srcValue, key, object, source, stack);
            }
            if (!(result === undefined ? baseIsEqual(srcValue, objValue, COMPARE_PARTIAL_FLAG | COMPARE_UNORDERED_FLAG, customizer, stack) : result)) {
                return false;
            }
        }
    }
    return true;
}
module.exports = baseIsMatch;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_isStrictComparable.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
/**
 * Checks if `value` is suitable for strict equality comparisons, i.e. `===`.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` if suitable for strict
 *  equality comparisons, else `false`.
 */ function isStrictComparable(value) {
    return value === value && !isObject(value);
}
module.exports = isStrictComparable;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getMatchData.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isStrictComparable = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isStrictComparable.js [app-client] (ecmascript)"), keys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/keys.js [app-client] (ecmascript)");
/**
 * Gets the property names, values, and compare flags of `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @returns {Array} Returns the match data of `object`.
 */ function getMatchData(object) {
    var result = keys(object), length = result.length;
    while(length--){
        var key = result[length], value = object[key];
        result[length] = [
            key,
            value,
            isStrictComparable(value)
        ];
    }
    return result;
}
module.exports = getMatchData;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_matchesStrictComparable.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A specialized version of `matchesProperty` for source values suitable
 * for strict equality comparisons, i.e. `===`.
 *
 * @private
 * @param {string} key The key of the property to get.
 * @param {*} srcValue The value to match.
 * @returns {Function} Returns the new spec function.
 */ function matchesStrictComparable(key, srcValue) {
    return function(object) {
        if (object == null) {
            return false;
        }
        return object[key] === srcValue && (srcValue !== undefined || key in Object(object));
    };
}
module.exports = matchesStrictComparable;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMatches.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsMatch = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsMatch.js [app-client] (ecmascript)"), getMatchData = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getMatchData.js [app-client] (ecmascript)"), matchesStrictComparable = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_matchesStrictComparable.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.matches` which doesn't clone `source`.
 *
 * @private
 * @param {Object} source The object of property values to match.
 * @returns {Function} Returns the new spec function.
 */ function baseMatches(source) {
    var matchData = getMatchData(source);
    if (matchData.length == 1 && matchData[0][2]) {
        return matchesStrictComparable(matchData[0][0], matchData[0][1]);
    }
    return function(object) {
        return object === source || baseIsMatch(object, source, matchData);
    };
}
module.exports = baseMatches;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseHasIn.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.hasIn` without support for deep paths.
 *
 * @private
 * @param {Object} [object] The object to query.
 * @param {Array|string} key The key to check.
 * @returns {boolean} Returns `true` if `key` exists, else `false`.
 */ function baseHasIn(object, key) {
    return object != null && key in Object(object);
}
module.exports = baseHasIn;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hasPath.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var castPath = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_castPath.js [app-client] (ecmascript)"), isArguments = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArguments.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIndex.js [app-client] (ecmascript)"), isLength = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isLength.js [app-client] (ecmascript)"), toKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_toKey.js [app-client] (ecmascript)");
/**
 * Checks if `path` exists on `object`.
 *
 * @private
 * @param {Object} object The object to query.
 * @param {Array|string} path The path to check.
 * @param {Function} hasFunc The function to check properties.
 * @returns {boolean} Returns `true` if `path` exists, else `false`.
 */ function hasPath(object, path, hasFunc) {
    path = castPath(path, object);
    var index = -1, length = path.length, result = false;
    while(++index < length){
        var key = toKey(path[index]);
        if (!(result = object != null && hasFunc(object, key))) {
            break;
        }
        object = object[key];
    }
    if (result || ++index != length) {
        return result;
    }
    length = object == null ? 0 : object.length;
    return !!length && isLength(length) && isIndex(key, length) && (isArray(object) || isArguments(object));
}
module.exports = hasPath;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/hasIn.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseHasIn = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseHasIn.js [app-client] (ecmascript)"), hasPath = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hasPath.js [app-client] (ecmascript)");
/**
 * Checks if `path` is a direct or inherited property of `object`.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Object
 * @param {Object} object The object to query.
 * @param {Array|string} path The path to check.
 * @returns {boolean} Returns `true` if `path` exists, else `false`.
 * @example
 *
 * var object = _.create({ 'a': _.create({ 'b': 2 }) });
 *
 * _.hasIn(object, 'a');
 * // => true
 *
 * _.hasIn(object, 'a.b');
 * // => true
 *
 * _.hasIn(object, ['a', 'b']);
 * // => true
 *
 * _.hasIn(object, 'b');
 * // => false
 */ function hasIn(object, path) {
    return object != null && hasPath(object, path, baseHasIn);
}
module.exports = hasIn;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMatchesProperty.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsEqual = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsEqual.js [app-client] (ecmascript)"), get = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/get.js [app-client] (ecmascript)"), hasIn = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/hasIn.js [app-client] (ecmascript)"), isKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isKey.js [app-client] (ecmascript)"), isStrictComparable = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isStrictComparable.js [app-client] (ecmascript)"), matchesStrictComparable = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_matchesStrictComparable.js [app-client] (ecmascript)"), toKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_toKey.js [app-client] (ecmascript)");
/** Used to compose bitmasks for value comparisons. */ var COMPARE_PARTIAL_FLAG = 1, COMPARE_UNORDERED_FLAG = 2;
/**
 * The base implementation of `_.matchesProperty` which doesn't clone `srcValue`.
 *
 * @private
 * @param {string} path The path of the property to get.
 * @param {*} srcValue The value to match.
 * @returns {Function} Returns the new spec function.
 */ function baseMatchesProperty(path, srcValue) {
    if (isKey(path) && isStrictComparable(srcValue)) {
        return matchesStrictComparable(toKey(path), srcValue);
    }
    return function(object) {
        var objValue = get(object, path);
        return objValue === undefined && objValue === srcValue ? hasIn(object, path) : baseIsEqual(srcValue, objValue, COMPARE_PARTIAL_FLAG | COMPARE_UNORDERED_FLAG);
    };
}
module.exports = baseMatchesProperty;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * This method returns the first argument it receives.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Util
 * @param {*} value Any value.
 * @returns {*} Returns `value`.
 * @example
 *
 * var object = { 'a': 1 };
 *
 * console.log(_.identity(object) === object);
 * // => true
 */ function identity(value) {
    return value;
}
module.exports = identity;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseProperty.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.property` without support for deep paths.
 *
 * @private
 * @param {string} key The key of the property to get.
 * @returns {Function} Returns the new accessor function.
 */ function baseProperty(key) {
    return function(object) {
        return object == null ? undefined : object[key];
    };
}
module.exports = baseProperty;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_basePropertyDeep.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGet.js [app-client] (ecmascript)");
/**
 * A specialized version of `baseProperty` which supports deep paths.
 *
 * @private
 * @param {Array|string} path The path of the property to get.
 * @returns {Function} Returns the new accessor function.
 */ function basePropertyDeep(path) {
    return function(object) {
        return baseGet(object, path);
    };
}
module.exports = basePropertyDeep;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/property.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseProperty = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseProperty.js [app-client] (ecmascript)"), basePropertyDeep = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_basePropertyDeep.js [app-client] (ecmascript)"), isKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isKey.js [app-client] (ecmascript)"), toKey = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_toKey.js [app-client] (ecmascript)");
/**
 * Creates a function that returns the value at `path` of a given object.
 *
 * @static
 * @memberOf _
 * @since 2.4.0
 * @category Util
 * @param {Array|string} path The path of the property to get.
 * @returns {Function} Returns the new accessor function.
 * @example
 *
 * var objects = [
 *   { 'a': { 'b': 2 } },
 *   { 'a': { 'b': 1 } }
 * ];
 *
 * _.map(objects, _.property('a.b'));
 * // => [2, 1]
 *
 * _.map(_.sortBy(objects, _.property(['a', 'b'])), 'a.b');
 * // => [1, 2]
 */ function property(path) {
    return isKey(path) ? baseProperty(toKey(path)) : basePropertyDeep(path);
}
module.exports = property;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseMatches = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMatches.js [app-client] (ecmascript)"), baseMatchesProperty = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMatchesProperty.js [app-client] (ecmascript)"), identity = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), property = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/property.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.iteratee`.
 *
 * @private
 * @param {*} [value=_.identity] The value to convert to an iteratee.
 * @returns {Function} Returns the iteratee.
 */ function baseIteratee(value) {
    // Don't store the `typeof` result in a variable to avoid a JIT bug in Safari 9.
    // See https://bugs.webkit.org/show_bug.cgi?id=156034 for more details.
    if (typeof value == 'function') {
        return value;
    }
    if (value == null) {
        return identity;
    }
    if (typeof value == 'object') {
        return isArray(value) ? baseMatchesProperty(value[0], value[1]) : baseMatches(value);
    }
    return property(value);
}
module.exports = baseIteratee;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_createBaseFor.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Creates a base function for methods like `_.forIn` and `_.forOwn`.
 *
 * @private
 * @param {boolean} [fromRight] Specify iterating from right to left.
 * @returns {Function} Returns the new base function.
 */ function createBaseFor(fromRight) {
    return function(object, iteratee, keysFunc) {
        var index = -1, iterable = Object(object), props = keysFunc(object), length = props.length;
        while(length--){
            var key = props[fromRight ? length : ++index];
            if (iteratee(iterable[key], key, iterable) === false) {
                break;
            }
        }
        return object;
    };
}
module.exports = createBaseFor;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFor.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var createBaseFor = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_createBaseFor.js [app-client] (ecmascript)");
/**
 * The base implementation of `baseForOwn` which iterates over `object`
 * properties returned by `keysFunc` and invokes `iteratee` for each property.
 * Iteratee functions may exit iteration early by explicitly returning `false`.
 *
 * @private
 * @param {Object} object The object to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @param {Function} keysFunc The function to get the keys of `object`.
 * @returns {Object} Returns `object`.
 */ var baseFor = createBaseFor();
module.exports = baseFor;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseForOwn.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseFor = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFor.js [app-client] (ecmascript)"), keys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/keys.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.forOwn` without support for iteratee shorthands.
 *
 * @private
 * @param {Object} object The object to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Object} Returns `object`.
 */ function baseForOwn(object, iteratee) {
    return object && baseFor(object, iteratee, keys);
}
module.exports = baseForOwn;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_createBaseEach.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isArrayLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArrayLike.js [app-client] (ecmascript)");
/**
 * Creates a `baseEach` or `baseEachRight` function.
 *
 * @private
 * @param {Function} eachFunc The function to iterate over a collection.
 * @param {boolean} [fromRight] Specify iterating from right to left.
 * @returns {Function} Returns the new base function.
 */ function createBaseEach(eachFunc, fromRight) {
    return function(collection, iteratee) {
        if (collection == null) {
            return collection;
        }
        if (!isArrayLike(collection)) {
            return eachFunc(collection, iteratee);
        }
        var length = collection.length, index = fromRight ? length : -1, iterable = Object(collection);
        while(fromRight ? index-- : ++index < length){
            if (iteratee(iterable[index], index, iterable) === false) {
                break;
            }
        }
        return collection;
    };
}
module.exports = createBaseEach;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseEach.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseForOwn = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseForOwn.js [app-client] (ecmascript)"), createBaseEach = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_createBaseEach.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.forEach` without support for iteratee shorthands.
 *
 * @private
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array|Object} Returns `collection`.
 */ var baseEach = createBaseEach(baseForOwn);
module.exports = baseEach;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMap.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseEach = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseEach.js [app-client] (ecmascript)"), isArrayLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArrayLike.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.map` without support for iteratee shorthands.
 *
 * @private
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} iteratee The function invoked per iteration.
 * @returns {Array} Returns the new mapped array.
 */ function baseMap(collection, iteratee) {
    var index = -1, result = isArrayLike(collection) ? Array(collection.length) : [];
    baseEach(collection, function(value, key, collection) {
        result[++index] = iteratee(value, key, collection);
    });
    return result;
}
module.exports = baseMap;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSortBy.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.sortBy` which uses `comparer` to define the
 * sort order of `array` and replaces criteria objects with their corresponding
 * values.
 *
 * @private
 * @param {Array} array The array to sort.
 * @param {Function} comparer The function to define sort order.
 * @returns {Array} Returns `array`.
 */ function baseSortBy(array, comparer) {
    var length = array.length;
    array.sort(comparer);
    while(length--){
        array[length] = array[length].value;
    }
    return array;
}
module.exports = baseSortBy;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_compareAscending.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isSymbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)");
/**
 * Compares values to sort them in ascending order.
 *
 * @private
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {number} Returns the sort order indicator for `value`.
 */ function compareAscending(value, other) {
    if (value !== other) {
        var valIsDefined = value !== undefined, valIsNull = value === null, valIsReflexive = value === value, valIsSymbol = isSymbol(value);
        var othIsDefined = other !== undefined, othIsNull = other === null, othIsReflexive = other === other, othIsSymbol = isSymbol(other);
        if (!othIsNull && !othIsSymbol && !valIsSymbol && value > other || valIsSymbol && othIsDefined && othIsReflexive && !othIsNull && !othIsSymbol || valIsNull && othIsDefined && othIsReflexive || !valIsDefined && othIsReflexive || !valIsReflexive) {
            return 1;
        }
        if (!valIsNull && !valIsSymbol && !othIsSymbol && value < other || othIsSymbol && valIsDefined && valIsReflexive && !valIsNull && !valIsSymbol || othIsNull && valIsDefined && valIsReflexive || !othIsDefined && valIsReflexive || !othIsReflexive) {
            return -1;
        }
    }
    return 0;
}
module.exports = compareAscending;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_compareMultiple.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var compareAscending = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_compareAscending.js [app-client] (ecmascript)");
/**
 * Used by `_.orderBy` to compare multiple properties of a value to another
 * and stable sort them.
 *
 * If `orders` is unspecified, all values are sorted in ascending order. Otherwise,
 * specify an order of "desc" for descending or "asc" for ascending sort order
 * of corresponding values.
 *
 * @private
 * @param {Object} object The object to compare.
 * @param {Object} other The other object to compare.
 * @param {boolean[]|string[]} orders The order to sort by for each property.
 * @returns {number} Returns the sort order indicator for `object`.
 */ function compareMultiple(object, other, orders) {
    var index = -1, objCriteria = object.criteria, othCriteria = other.criteria, length = objCriteria.length, ordersLength = orders.length;
    while(++index < length){
        var result = compareAscending(objCriteria[index], othCriteria[index]);
        if (result) {
            if (index >= ordersLength) {
                return result;
            }
            var order = orders[index];
            return result * (order == 'desc' ? -1 : 1);
        }
    }
    // Fixes an `Array#sort` bug in the JS engine embedded in Adobe applications
    // that causes it, under certain circumstances, to provide the same value for
    // `object` and `other`. See https://github.com/jashkenas/underscore/pull/1247
    // for more details.
    //
    // This also ensures a stable sort in V8 and other engines.
    // See https://bugs.chromium.org/p/v8/issues/detail?id=90 for more details.
    return object.index - other.index;
}
module.exports = compareMultiple;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseOrderBy.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayMap = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayMap.js [app-client] (ecmascript)"), baseGet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGet.js [app-client] (ecmascript)"), baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), baseMap = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMap.js [app-client] (ecmascript)"), baseSortBy = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSortBy.js [app-client] (ecmascript)"), baseUnary = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseUnary.js [app-client] (ecmascript)"), compareMultiple = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_compareMultiple.js [app-client] (ecmascript)"), identity = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.orderBy` without param guards.
 *
 * @private
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function[]|Object[]|string[]} iteratees The iteratees to sort by.
 * @param {string[]} orders The sort orders of `iteratees`.
 * @returns {Array} Returns the new sorted array.
 */ function baseOrderBy(collection, iteratees, orders) {
    if (iteratees.length) {
        iteratees = arrayMap(iteratees, function(iteratee) {
            if (isArray(iteratee)) {
                return function(value) {
                    return baseGet(value, iteratee.length === 1 ? iteratee[0] : iteratee);
                };
            }
            return iteratee;
        });
    } else {
        iteratees = [
            identity
        ];
    }
    var index = -1;
    iteratees = arrayMap(iteratees, baseUnary(baseIteratee));
    var result = baseMap(collection, function(value, key, collection) {
        var criteria = arrayMap(iteratees, function(iteratee) {
            return iteratee(value);
        });
        return {
            'criteria': criteria,
            'index': ++index,
            'value': value
        };
    });
    return baseSortBy(result, function(object, other) {
        return compareMultiple(object, other, orders);
    });
}
module.exports = baseOrderBy;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_apply.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A faster alternative to `Function#apply`, this function invokes `func`
 * with the `this` binding of `thisArg` and the arguments of `args`.
 *
 * @private
 * @param {Function} func The function to invoke.
 * @param {*} thisArg The `this` binding of `func`.
 * @param {Array} args The arguments to invoke `func` with.
 * @returns {*} Returns the result of `func`.
 */ function apply(func, thisArg, args) {
    switch(args.length){
        case 0:
            return func.call(thisArg);
        case 1:
            return func.call(thisArg, args[0]);
        case 2:
            return func.call(thisArg, args[0], args[1]);
        case 3:
            return func.call(thisArg, args[0], args[1], args[2]);
    }
    return func.apply(thisArg, args);
}
module.exports = apply;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_overRest.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var apply = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_apply.js [app-client] (ecmascript)");
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeMax = Math.max;
/**
 * A specialized version of `baseRest` which transforms the rest array.
 *
 * @private
 * @param {Function} func The function to apply a rest parameter to.
 * @param {number} [start=func.length-1] The start position of the rest parameter.
 * @param {Function} transform The rest array transform.
 * @returns {Function} Returns the new function.
 */ function overRest(func, start, transform) {
    start = nativeMax(start === undefined ? func.length - 1 : start, 0);
    return function() {
        var args = arguments, index = -1, length = nativeMax(args.length - start, 0), array = Array(length);
        while(++index < length){
            array[index] = args[start + index];
        }
        index = -1;
        var otherArgs = Array(start + 1);
        while(++index < start){
            otherArgs[index] = args[index];
        }
        otherArgs[start] = transform(array);
        return apply(func, this, otherArgs);
    };
}
module.exports = overRest;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/constant.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Creates a function that returns `value`.
 *
 * @static
 * @memberOf _
 * @since 2.4.0
 * @category Util
 * @param {*} value The value to return from the new function.
 * @returns {Function} Returns the new constant function.
 * @example
 *
 * var objects = _.times(2, _.constant({ 'a': 1 }));
 *
 * console.log(objects);
 * // => [{ 'a': 1 }, { 'a': 1 }]
 *
 * console.log(objects[0] === objects[1]);
 * // => true
 */ function constant(value) {
    return function() {
        return value;
    };
}
module.exports = constant;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_defineProperty.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var getNative = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getNative.js [app-client] (ecmascript)");
var defineProperty = function() {
    try {
        var func = getNative(Object, 'defineProperty');
        func({}, '', {});
        return func;
    } catch (e) {}
}();
module.exports = defineProperty;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSetToString.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var constant = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/constant.js [app-client] (ecmascript)"), defineProperty = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_defineProperty.js [app-client] (ecmascript)"), identity = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)");
/**
 * The base implementation of `setToString` without support for hot loop shorting.
 *
 * @private
 * @param {Function} func The function to modify.
 * @param {Function} string The `toString` result.
 * @returns {Function} Returns `func`.
 */ var baseSetToString = !defineProperty ? identity : function(func, string) {
    return defineProperty(func, 'toString', {
        'configurable': true,
        'enumerable': false,
        'value': constant(string),
        'writable': true
    });
};
module.exports = baseSetToString;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_shortOut.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used to detect hot functions by number of calls within a span of milliseconds. */ var HOT_COUNT = 800, HOT_SPAN = 16;
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeNow = Date.now;
/**
 * Creates a function that'll short out and invoke `identity` instead
 * of `func` when it's called `HOT_COUNT` or more times in `HOT_SPAN`
 * milliseconds.
 *
 * @private
 * @param {Function} func The function to restrict.
 * @returns {Function} Returns the new shortable function.
 */ function shortOut(func) {
    var count = 0, lastCalled = 0;
    return function() {
        var stamp = nativeNow(), remaining = HOT_SPAN - (stamp - lastCalled);
        lastCalled = stamp;
        if (remaining > 0) {
            if (++count >= HOT_COUNT) {
                return arguments[0];
            }
        } else {
            count = 0;
        }
        return func.apply(undefined, arguments);
    };
}
module.exports = shortOut;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_setToString.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseSetToString = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSetToString.js [app-client] (ecmascript)"), shortOut = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_shortOut.js [app-client] (ecmascript)");
/**
 * Sets the `toString` method of `func` to return `string`.
 *
 * @private
 * @param {Function} func The function to modify.
 * @param {Function} string The `toString` result.
 * @returns {Function} Returns `func`.
 */ var setToString = shortOut(baseSetToString);
module.exports = setToString;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseRest.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var identity = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)"), overRest = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_overRest.js [app-client] (ecmascript)"), setToString = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_setToString.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.rest` which doesn't validate or coerce arguments.
 *
 * @private
 * @param {Function} func The function to apply a rest parameter to.
 * @param {number} [start=func.length-1] The start position of the rest parameter.
 * @returns {Function} Returns the new function.
 */ function baseRest(func, start) {
    return setToString(overRest(func, start, identity), func + '');
}
module.exports = baseRest;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/sortBy.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseFlatten = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFlatten.js [app-client] (ecmascript)"), baseOrderBy = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseOrderBy.js [app-client] (ecmascript)"), baseRest = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseRest.js [app-client] (ecmascript)"), isIterateeCall = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIterateeCall.js [app-client] (ecmascript)");
/**
 * Creates an array of elements, sorted in ascending order by the results of
 * running each element in a collection thru each iteratee. This method
 * performs a stable sort, that is, it preserves the original sort order of
 * equal elements. The iteratees are invoked with one argument: (value).
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Collection
 * @param {Array|Object} collection The collection to iterate over.
 * @param {...(Function|Function[])} [iteratees=[_.identity]]
 *  The iteratees to sort by.
 * @returns {Array} Returns the new sorted array.
 * @example
 *
 * var users = [
 *   { 'user': 'fred',   'age': 48 },
 *   { 'user': 'barney', 'age': 36 },
 *   { 'user': 'fred',   'age': 30 },
 *   { 'user': 'barney', 'age': 34 }
 * ];
 *
 * _.sortBy(users, [function(o) { return o.user; }]);
 * // => objects for [['barney', 36], ['barney', 34], ['fred', 48], ['fred', 30]]
 *
 * _.sortBy(users, ['user', 'age']);
 * // => objects for [['barney', 34], ['barney', 36], ['fred', 30], ['fred', 48]]
 */ var sortBy = baseRest(function(collection, iteratees) {
    if (collection == null) {
        return [];
    }
    var length = iteratees.length;
    if (length > 1 && isIterateeCall(collection, iteratees[0], iteratees[1])) {
        iteratees = [];
    } else if (length > 2 && isIterateeCall(iteratees[0], iteratees[1], iteratees[2])) {
        iteratees = [
            iteratees[0]
        ];
    }
    return baseOrderBy(collection, baseFlatten(iteratees, 1), []);
});
module.exports = sortBy;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/now.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var root = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_root.js [app-client] (ecmascript)");
/**
 * Gets the timestamp of the number of milliseconds that have elapsed since
 * the Unix epoch (1 January 1970 00:00:00 UTC).
 *
 * @static
 * @memberOf _
 * @since 2.4.0
 * @category Date
 * @returns {number} Returns the timestamp.
 * @example
 *
 * _.defer(function(stamp) {
 *   console.log(_.now() - stamp);
 * }, _.now());
 * // => Logs the number of milliseconds it took for the deferred invocation.
 */ var now = function() {
    return root.Date.now();
};
module.exports = now;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/debounce.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)"), now = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/now.js [app-client] (ecmascript)"), toNumber = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toNumber.js [app-client] (ecmascript)");
/** Error message constants. */ var FUNC_ERROR_TEXT = 'Expected a function';
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeMax = Math.max, nativeMin = Math.min;
/**
 * Creates a debounced function that delays invoking `func` until after `wait`
 * milliseconds have elapsed since the last time the debounced function was
 * invoked. The debounced function comes with a `cancel` method to cancel
 * delayed `func` invocations and a `flush` method to immediately invoke them.
 * Provide `options` to indicate whether `func` should be invoked on the
 * leading and/or trailing edge of the `wait` timeout. The `func` is invoked
 * with the last arguments provided to the debounced function. Subsequent
 * calls to the debounced function return the result of the last `func`
 * invocation.
 *
 * **Note:** If `leading` and `trailing` options are `true`, `func` is
 * invoked on the trailing edge of the timeout only if the debounced function
 * is invoked more than once during the `wait` timeout.
 *
 * If `wait` is `0` and `leading` is `false`, `func` invocation is deferred
 * until to the next tick, similar to `setTimeout` with a timeout of `0`.
 *
 * See [David Corbacho's article](https://css-tricks.com/debouncing-throttling-explained-examples/)
 * for details over the differences between `_.debounce` and `_.throttle`.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Function
 * @param {Function} func The function to debounce.
 * @param {number} [wait=0] The number of milliseconds to delay.
 * @param {Object} [options={}] The options object.
 * @param {boolean} [options.leading=false]
 *  Specify invoking on the leading edge of the timeout.
 * @param {number} [options.maxWait]
 *  The maximum time `func` is allowed to be delayed before it's invoked.
 * @param {boolean} [options.trailing=true]
 *  Specify invoking on the trailing edge of the timeout.
 * @returns {Function} Returns the new debounced function.
 * @example
 *
 * // Avoid costly calculations while the window size is in flux.
 * jQuery(window).on('resize', _.debounce(calculateLayout, 150));
 *
 * // Invoke `sendMail` when clicked, debouncing subsequent calls.
 * jQuery(element).on('click', _.debounce(sendMail, 300, {
 *   'leading': true,
 *   'trailing': false
 * }));
 *
 * // Ensure `batchLog` is invoked once after 1 second of debounced calls.
 * var debounced = _.debounce(batchLog, 250, { 'maxWait': 1000 });
 * var source = new EventSource('/stream');
 * jQuery(source).on('message', debounced);
 *
 * // Cancel the trailing debounced invocation.
 * jQuery(window).on('popstate', debounced.cancel);
 */ function debounce(func, wait, options) {
    var lastArgs, lastThis, maxWait, result, timerId, lastCallTime, lastInvokeTime = 0, leading = false, maxing = false, trailing = true;
    if (typeof func != 'function') {
        throw new TypeError(FUNC_ERROR_TEXT);
    }
    wait = toNumber(wait) || 0;
    if (isObject(options)) {
        leading = !!options.leading;
        maxing = 'maxWait' in options;
        maxWait = maxing ? nativeMax(toNumber(options.maxWait) || 0, wait) : maxWait;
        trailing = 'trailing' in options ? !!options.trailing : trailing;
    }
    function invokeFunc(time) {
        var args = lastArgs, thisArg = lastThis;
        lastArgs = lastThis = undefined;
        lastInvokeTime = time;
        result = func.apply(thisArg, args);
        return result;
    }
    function leadingEdge(time) {
        // Reset any `maxWait` timer.
        lastInvokeTime = time;
        // Start the timer for the trailing edge.
        timerId = setTimeout(timerExpired, wait);
        // Invoke the leading edge.
        return leading ? invokeFunc(time) : result;
    }
    function remainingWait(time) {
        var timeSinceLastCall = time - lastCallTime, timeSinceLastInvoke = time - lastInvokeTime, timeWaiting = wait - timeSinceLastCall;
        return maxing ? nativeMin(timeWaiting, maxWait - timeSinceLastInvoke) : timeWaiting;
    }
    function shouldInvoke(time) {
        var timeSinceLastCall = time - lastCallTime, timeSinceLastInvoke = time - lastInvokeTime;
        // Either this is the first call, activity has stopped and we're at the
        // trailing edge, the system time has gone backwards and we're treating
        // it as the trailing edge, or we've hit the `maxWait` limit.
        return lastCallTime === undefined || timeSinceLastCall >= wait || timeSinceLastCall < 0 || maxing && timeSinceLastInvoke >= maxWait;
    }
    function timerExpired() {
        var time = now();
        if (shouldInvoke(time)) {
            return trailingEdge(time);
        }
        // Restart the timer.
        timerId = setTimeout(timerExpired, remainingWait(time));
    }
    function trailingEdge(time) {
        timerId = undefined;
        // Only invoke if we have `lastArgs` which means `func` has been
        // debounced at least once.
        if (trailing && lastArgs) {
            return invokeFunc(time);
        }
        lastArgs = lastThis = undefined;
        return result;
    }
    function cancel() {
        if (timerId !== undefined) {
            clearTimeout(timerId);
        }
        lastInvokeTime = 0;
        lastArgs = lastCallTime = lastThis = timerId = undefined;
    }
    function flush() {
        return timerId === undefined ? result : trailingEdge(now());
    }
    function debounced() {
        var time = now(), isInvoking = shouldInvoke(time);
        lastArgs = arguments;
        lastThis = this;
        lastCallTime = time;
        if (isInvoking) {
            if (timerId === undefined) {
                return leadingEdge(lastCallTime);
            }
            if (maxing) {
                // Handle invocations in a tight loop.
                clearTimeout(timerId);
                timerId = setTimeout(timerExpired, wait);
                return invokeFunc(lastCallTime);
            }
        }
        if (timerId === undefined) {
            timerId = setTimeout(timerExpired, wait);
        }
        return result;
    }
    debounced.cancel = cancel;
    debounced.flush = flush;
    return debounced;
}
module.exports = debounce;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/throttle.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var debounce = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/debounce.js [app-client] (ecmascript)"), isObject = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObject.js [app-client] (ecmascript)");
/** Error message constants. */ var FUNC_ERROR_TEXT = 'Expected a function';
/**
 * Creates a throttled function that only invokes `func` at most once per
 * every `wait` milliseconds. The throttled function comes with a `cancel`
 * method to cancel delayed `func` invocations and a `flush` method to
 * immediately invoke them. Provide `options` to indicate whether `func`
 * should be invoked on the leading and/or trailing edge of the `wait`
 * timeout. The `func` is invoked with the last arguments provided to the
 * throttled function. Subsequent calls to the throttled function return the
 * result of the last `func` invocation.
 *
 * **Note:** If `leading` and `trailing` options are `true`, `func` is
 * invoked on the trailing edge of the timeout only if the throttled function
 * is invoked more than once during the `wait` timeout.
 *
 * If `wait` is `0` and `leading` is `false`, `func` invocation is deferred
 * until to the next tick, similar to `setTimeout` with a timeout of `0`.
 *
 * See [David Corbacho's article](https://css-tricks.com/debouncing-throttling-explained-examples/)
 * for details over the differences between `_.throttle` and `_.debounce`.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Function
 * @param {Function} func The function to throttle.
 * @param {number} [wait=0] The number of milliseconds to throttle invocations to.
 * @param {Object} [options={}] The options object.
 * @param {boolean} [options.leading=true]
 *  Specify invoking on the leading edge of the timeout.
 * @param {boolean} [options.trailing=true]
 *  Specify invoking on the trailing edge of the timeout.
 * @returns {Function} Returns the new throttled function.
 * @example
 *
 * // Avoid excessively updating the position while scrolling.
 * jQuery(window).on('scroll', _.throttle(updatePosition, 100));
 *
 * // Invoke `renewToken` when the click event is fired, but not more than once every 5 minutes.
 * var throttled = _.throttle(renewToken, 300000, { 'trailing': false });
 * jQuery(element).on('click', throttled);
 *
 * // Cancel the trailing throttled invocation.
 * jQuery(window).on('popstate', throttled.cancel);
 */ function throttle(func, wait, options) {
    var leading = true, trailing = true;
    if (typeof func != 'function') {
        throw new TypeError(FUNC_ERROR_TEXT);
    }
    if (isObject(options)) {
        leading = 'leading' in options ? !!options.leading : leading;
        trailing = 'trailing' in options ? !!options.trailing : trailing;
    }
    return debounce(func, wait, {
        'leading': leading,
        'maxWait': wait,
        'trailing': trailing
    });
}
module.exports = throttle;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isString.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var stringTag = '[object String]';
/**
 * Checks if `value` is classified as a `String` primitive or object.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a string, else `false`.
 * @example
 *
 * _.isString('abc');
 * // => true
 *
 * _.isString(1);
 * // => false
 */ function isString(value) {
    return typeof value == 'string' || !isArray(value) && isObjectLike(value) && baseGetTag(value) == stringTag;
}
module.exports = isString;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isNumber.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var numberTag = '[object Number]';
/**
 * Checks if `value` is classified as a `Number` primitive or object.
 *
 * **Note:** To exclude `Infinity`, `-Infinity`, and `NaN`, which are
 * classified as numbers, use the `_.isFinite` method.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a number, else `false`.
 * @example
 *
 * _.isNumber(3);
 * // => true
 *
 * _.isNumber(Number.MIN_VALUE);
 * // => true
 *
 * _.isNumber(Infinity);
 * // => true
 *
 * _.isNumber('3');
 * // => false
 */ function isNumber(value) {
    return typeof value == 'number' || isObjectLike(value) && baseGetTag(value) == numberTag;
}
module.exports = isNumber;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isNaN.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isNumber = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isNumber.js [app-client] (ecmascript)");
/**
 * Checks if `value` is `NaN`.
 *
 * **Note:** This method is based on
 * [`Number.isNaN`](https://mdn.io/Number/isNaN) and is not the same as
 * global [`isNaN`](https://mdn.io/isNaN) which returns `true` for
 * `undefined` and other non-number values.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is `NaN`, else `false`.
 * @example
 *
 * _.isNaN(NaN);
 * // => true
 *
 * _.isNaN(new Number(NaN));
 * // => true
 *
 * isNaN(undefined);
 * // => true
 *
 * _.isNaN(undefined);
 * // => false
 */ function isNaN(value) {
    // An `NaN` primitive is the only value that is not equal to itself.
    // Perform the `toStringTag` check first to avoid errors with some
    // ActiveX objects in IE.
    return isNumber(value) && value != +value;
}
module.exports = isNaN;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFindIndex.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.findIndex` and `_.findLastIndex` without
 * support for iteratee shorthands.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {Function} predicate The function invoked per iteration.
 * @param {number} fromIndex The index to search from.
 * @param {boolean} [fromRight] Specify iterating from right to left.
 * @returns {number} Returns the index of the matched value, else `-1`.
 */ function baseFindIndex(array, predicate, fromIndex, fromRight) {
    var length = array.length, index = fromIndex + (fromRight ? 1 : -1);
    while(fromRight ? index-- : ++index < length){
        if (predicate(array[index], index, array)) {
            return index;
        }
    }
    return -1;
}
module.exports = baseFindIndex;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsNaN.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.isNaN` without support for number objects.
 *
 * @private
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is `NaN`, else `false`.
 */ function baseIsNaN(value) {
    return value !== value;
}
module.exports = baseIsNaN;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_strictIndexOf.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A specialized version of `_.indexOf` which performs strict equality
 * comparisons of values, i.e. `===`.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {*} value The value to search for.
 * @param {number} fromIndex The index to search from.
 * @returns {number} Returns the index of the matched value, else `-1`.
 */ function strictIndexOf(array, value, fromIndex) {
    var index = fromIndex - 1, length = array.length;
    while(++index < length){
        if (array[index] === value) {
            return index;
        }
    }
    return -1;
}
module.exports = strictIndexOf;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIndexOf.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseFindIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFindIndex.js [app-client] (ecmascript)"), baseIsNaN = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsNaN.js [app-client] (ecmascript)"), strictIndexOf = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_strictIndexOf.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.indexOf` without `fromIndex` bounds checks.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {*} value The value to search for.
 * @param {number} fromIndex The index to search from.
 * @returns {number} Returns the index of the matched value, else `-1`.
 */ function baseIndexOf(array, value, fromIndex) {
    return value === value ? strictIndexOf(array, value, fromIndex) : baseFindIndex(array, baseIsNaN, fromIndex);
}
module.exports = baseIndexOf;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayIncludes.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIndexOf = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIndexOf.js [app-client] (ecmascript)");
/**
 * A specialized version of `_.includes` for arrays without support for
 * specifying an index to search from.
 *
 * @private
 * @param {Array} [array] The array to inspect.
 * @param {*} target The value to search for.
 * @returns {boolean} Returns `true` if `target` is found, else `false`.
 */ function arrayIncludes(array, value) {
    var length = array == null ? 0 : array.length;
    return !!length && baseIndexOf(array, value, 0) > -1;
}
module.exports = arrayIncludes;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayIncludesWith.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * This function is like `arrayIncludes` except that it accepts a comparator.
 *
 * @private
 * @param {Array} [array] The array to inspect.
 * @param {*} target The value to search for.
 * @param {Function} comparator The comparator invoked per element.
 * @returns {boolean} Returns `true` if `target` is found, else `false`.
 */ function arrayIncludesWith(array, value, comparator) {
    var index = -1, length = array == null ? 0 : array.length;
    while(++index < length){
        if (comparator(value, array[index])) {
            return true;
        }
    }
    return false;
}
module.exports = arrayIncludesWith;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/noop.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * This method returns `undefined`.
 *
 * @static
 * @memberOf _
 * @since 2.3.0
 * @category Util
 * @example
 *
 * _.times(2, _.noop);
 * // => [undefined, undefined]
 */ function noop() {
// No operation performed.
}
module.exports = noop;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_createSet.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var Set = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_Set.js [app-client] (ecmascript)"), noop = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/noop.js [app-client] (ecmascript)"), setToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_setToArray.js [app-client] (ecmascript)");
/** Used as references for various `Number` constants. */ var INFINITY = 1 / 0;
/**
 * Creates a set object of `values`.
 *
 * @private
 * @param {Array} values The values to add to the set.
 * @returns {Object} Returns the new set.
 */ var createSet = !(Set && 1 / setToArray(new Set([
    ,
    -0
]))[1] == INFINITY) ? noop : function(values) {
    return new Set(values);
};
module.exports = createSet;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseUniq.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var SetCache = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_SetCache.js [app-client] (ecmascript)"), arrayIncludes = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayIncludes.js [app-client] (ecmascript)"), arrayIncludesWith = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayIncludesWith.js [app-client] (ecmascript)"), cacheHas = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_cacheHas.js [app-client] (ecmascript)"), createSet = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_createSet.js [app-client] (ecmascript)"), setToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_setToArray.js [app-client] (ecmascript)");
/** Used as the size to enable large array optimizations. */ var LARGE_ARRAY_SIZE = 200;
/**
 * The base implementation of `_.uniqBy` without support for iteratee shorthands.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {Function} [iteratee] The iteratee invoked per element.
 * @param {Function} [comparator] The comparator invoked per element.
 * @returns {Array} Returns the new duplicate free array.
 */ function baseUniq(array, iteratee, comparator) {
    var index = -1, includes = arrayIncludes, length = array.length, isCommon = true, result = [], seen = result;
    if (comparator) {
        isCommon = false;
        includes = arrayIncludesWith;
    } else if (length >= LARGE_ARRAY_SIZE) {
        var set = iteratee ? null : createSet(array);
        if (set) {
            return setToArray(set);
        }
        isCommon = false;
        includes = cacheHas;
        seen = new SetCache;
    } else {
        seen = iteratee ? [] : result;
    }
    outer: while(++index < length){
        var value = array[index], computed = iteratee ? iteratee(value) : value;
        value = comparator || value !== 0 ? value : 0;
        if (isCommon && computed === computed) {
            var seenIndex = seen.length;
            while(seenIndex--){
                if (seen[seenIndex] === computed) {
                    continue outer;
                }
            }
            if (iteratee) {
                seen.push(computed);
            }
            result.push(value);
        } else if (!includes(seen, computed, comparator)) {
            if (seen !== result) {
                seen.push(computed);
            }
            result.push(value);
        }
    }
    return result;
}
module.exports = baseUniq;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/uniqBy.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), baseUniq = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseUniq.js [app-client] (ecmascript)");
/**
 * This method is like `_.uniq` except that it accepts `iteratee` which is
 * invoked for each element in `array` to generate the criterion by which
 * uniqueness is computed. The order of result values is determined by the
 * order they occur in the array. The iteratee is invoked with one argument:
 * (value).
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Array
 * @param {Array} array The array to inspect.
 * @param {Function} [iteratee=_.identity] The iteratee invoked per element.
 * @returns {Array} Returns the new duplicate free array.
 * @example
 *
 * _.uniqBy([2.1, 1.2, 2.3], Math.floor);
 * // => [2.1, 1.2]
 *
 * // The `_.property` iteratee shorthand.
 * _.uniqBy([{ 'x': 1 }, { 'x': 2 }, { 'x': 1 }], 'x');
 * // => [{ 'x': 1 }, { 'x': 2 }]
 */ function uniqBy(array, iteratee) {
    return array && array.length ? baseUniq(array, baseIteratee(iteratee, 2)) : [];
}
module.exports = uniqBy;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSlice.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.slice` without an iteratee call guard.
 *
 * @private
 * @param {Array} array The array to slice.
 * @param {number} [start=0] The start position.
 * @param {number} [end=array.length] The end position.
 * @returns {Array} Returns the slice of `array`.
 */ function baseSlice(array, start, end) {
    var index = -1, length = array.length;
    if (start < 0) {
        start = -start > length ? 0 : length + start;
    }
    end = end > length ? length : end;
    if (end < 0) {
        end += length;
    }
    length = start > end ? 0 : end - start >>> 0;
    start >>>= 0;
    var result = Array(length);
    while(++index < length){
        result[index] = array[index + start];
    }
    return result;
}
module.exports = baseSlice;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_castSlice.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseSlice = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSlice.js [app-client] (ecmascript)");
/**
 * Casts `array` to a slice if it's needed.
 *
 * @private
 * @param {Array} array The array to inspect.
 * @param {number} start The start position.
 * @param {number} [end=array.length] The end position.
 * @returns {Array} Returns the cast slice.
 */ function castSlice(array, start, end) {
    var length = array.length;
    end = end === undefined ? length : end;
    return !start && end >= length ? array : baseSlice(array, start, end);
}
module.exports = castSlice;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_hasUnicode.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used to compose unicode character classes. */ var rsAstralRange = '\\ud800-\\udfff', rsComboMarksRange = '\\u0300-\\u036f', reComboHalfMarksRange = '\\ufe20-\\ufe2f', rsComboSymbolsRange = '\\u20d0-\\u20ff', rsComboRange = rsComboMarksRange + reComboHalfMarksRange + rsComboSymbolsRange, rsVarRange = '\\ufe0e\\ufe0f';
/** Used to compose unicode capture groups. */ var rsZWJ = '\\u200d';
/** Used to detect strings with [zero-width joiners or code points from the astral planes](http://eev.ee/blog/2015/09/12/dark-corners-of-unicode/). */ var reHasUnicode = RegExp('[' + rsZWJ + rsAstralRange + rsComboRange + rsVarRange + ']');
/**
 * Checks if `string` contains Unicode symbols.
 *
 * @private
 * @param {string} string The string to inspect.
 * @returns {boolean} Returns `true` if a symbol is found, else `false`.
 */ function hasUnicode(string) {
    return reHasUnicode.test(string);
}
module.exports = hasUnicode;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_asciiToArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Converts an ASCII `string` to an array.
 *
 * @private
 * @param {string} string The string to convert.
 * @returns {Array} Returns the converted array.
 */ function asciiToArray(string) {
    return string.split('');
}
module.exports = asciiToArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_unicodeToArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/** Used to compose unicode character classes. */ var rsAstralRange = '\\ud800-\\udfff', rsComboMarksRange = '\\u0300-\\u036f', reComboHalfMarksRange = '\\ufe20-\\ufe2f', rsComboSymbolsRange = '\\u20d0-\\u20ff', rsComboRange = rsComboMarksRange + reComboHalfMarksRange + rsComboSymbolsRange, rsVarRange = '\\ufe0e\\ufe0f';
/** Used to compose unicode capture groups. */ var rsAstral = '[' + rsAstralRange + ']', rsCombo = '[' + rsComboRange + ']', rsFitz = '\\ud83c[\\udffb-\\udfff]', rsModifier = '(?:' + rsCombo + '|' + rsFitz + ')', rsNonAstral = '[^' + rsAstralRange + ']', rsRegional = '(?:\\ud83c[\\udde6-\\uddff]){2}', rsSurrPair = '[\\ud800-\\udbff][\\udc00-\\udfff]', rsZWJ = '\\u200d';
/** Used to compose unicode regexes. */ var reOptMod = rsModifier + '?', rsOptVar = '[' + rsVarRange + ']?', rsOptJoin = '(?:' + rsZWJ + '(?:' + [
    rsNonAstral,
    rsRegional,
    rsSurrPair
].join('|') + ')' + rsOptVar + reOptMod + ')*', rsSeq = rsOptVar + reOptMod + rsOptJoin, rsSymbol = '(?:' + [
    rsNonAstral + rsCombo + '?',
    rsCombo,
    rsRegional,
    rsSurrPair,
    rsAstral
].join('|') + ')';
/** Used to match [string symbols](https://mathiasbynens.be/notes/javascript-unicode). */ var reUnicode = RegExp(rsFitz + '(?=' + rsFitz + ')|' + rsSymbol + rsSeq, 'g');
/**
 * Converts a Unicode `string` to an array.
 *
 * @private
 * @param {string} string The string to convert.
 * @returns {Array} Returns the converted array.
 */ function unicodeToArray(string) {
    return string.match(reUnicode) || [];
}
module.exports = unicodeToArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_stringToArray.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var asciiToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_asciiToArray.js [app-client] (ecmascript)"), hasUnicode = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hasUnicode.js [app-client] (ecmascript)"), unicodeToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_unicodeToArray.js [app-client] (ecmascript)");
/**
 * Converts `string` to an array.
 *
 * @private
 * @param {string} string The string to convert.
 * @returns {Array} Returns the converted array.
 */ function stringToArray(string) {
    return hasUnicode(string) ? unicodeToArray(string) : asciiToArray(string);
}
module.exports = stringToArray;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_createCaseFirst.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var castSlice = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_castSlice.js [app-client] (ecmascript)"), hasUnicode = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_hasUnicode.js [app-client] (ecmascript)"), stringToArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_stringToArray.js [app-client] (ecmascript)"), toString = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toString.js [app-client] (ecmascript)");
/**
 * Creates a function like `_.lowerFirst`.
 *
 * @private
 * @param {string} methodName The name of the `String` case method to use.
 * @returns {Function} Returns the new case function.
 */ function createCaseFirst(methodName) {
    return function(string) {
        string = toString(string);
        var strSymbols = hasUnicode(string) ? stringToArray(string) : undefined;
        var chr = strSymbols ? strSymbols[0] : string.charAt(0);
        var trailing = strSymbols ? castSlice(strSymbols, 1).join('') : string.slice(1);
        return chr[methodName]() + trailing;
    };
}
module.exports = createCaseFirst;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/upperFirst.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var createCaseFirst = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_createCaseFirst.js [app-client] (ecmascript)");
/**
 * Converts the first character of `string` to upper case.
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category String
 * @param {string} [string=''] The string to convert.
 * @returns {string} Returns the converted string.
 * @example
 *
 * _.upperFirst('fred');
 * // => 'Fred'
 *
 * _.upperFirst('FRED');
 * // => 'FRED'
 */ var upperFirst = createCaseFirst('toUpperCase');
module.exports = upperFirst;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseExtremum.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var isSymbol = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isSymbol.js [app-client] (ecmascript)");
/**
 * The base implementation of methods like `_.max` and `_.min` which accepts a
 * `comparator` to determine the extremum value.
 *
 * @private
 * @param {Array} array The array to iterate over.
 * @param {Function} iteratee The iteratee invoked per iteration.
 * @param {Function} comparator The comparator used to compare values.
 * @returns {*} Returns the extremum value.
 */ function baseExtremum(array, iteratee, comparator) {
    var index = -1, length = array.length;
    while(++index < length){
        var value = array[index], current = iteratee(value);
        if (current != null && (computed === undefined ? current === current && !isSymbol(current) : comparator(current, computed))) {
            var computed = current, result = value;
        }
    }
    return result;
}
module.exports = baseExtremum;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGt.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.gt` which doesn't coerce arguments.
 *
 * @private
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {boolean} Returns `true` if `value` is greater than `other`,
 *  else `false`.
 */ function baseGt(value, other) {
    return value > other;
}
module.exports = baseGt;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/max.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseExtremum = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseExtremum.js [app-client] (ecmascript)"), baseGt = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGt.js [app-client] (ecmascript)"), identity = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)");
/**
 * Computes the maximum value of `array`. If `array` is empty or falsey,
 * `undefined` is returned.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Math
 * @param {Array} array The array to iterate over.
 * @returns {*} Returns the maximum value.
 * @example
 *
 * _.max([4, 2, 8, 6]);
 * // => 8
 *
 * _.max([]);
 * // => undefined
 */ function max(array) {
    return array && array.length ? baseExtremum(array, identity, baseGt) : undefined;
}
module.exports = max;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseLt.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * The base implementation of `_.lt` which doesn't coerce arguments.
 *
 * @private
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {boolean} Returns `true` if `value` is less than `other`,
 *  else `false`.
 */ function baseLt(value, other) {
    return value < other;
}
module.exports = baseLt;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/min.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseExtremum = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseExtremum.js [app-client] (ecmascript)"), baseLt = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseLt.js [app-client] (ecmascript)"), identity = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/identity.js [app-client] (ecmascript)");
/**
 * Computes the minimum value of `array`. If `array` is empty or falsey,
 * `undefined` is returned.
 *
 * @static
 * @since 0.1.0
 * @memberOf _
 * @category Math
 * @param {Array} array The array to iterate over.
 * @returns {*} Returns the minimum value.
 * @example
 *
 * _.min([4, 2, 8, 6]);
 * // => 2
 *
 * _.min([]);
 * // => undefined
 */ function min(array) {
    return array && array.length ? baseExtremum(array, identity, baseLt) : undefined;
}
module.exports = min;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/map.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayMap = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayMap.js [app-client] (ecmascript)"), baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), baseMap = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseMap.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)");
/**
 * Creates an array of values by running each element in `collection` thru
 * `iteratee`. The iteratee is invoked with three arguments:
 * (value, index|key, collection).
 *
 * Many lodash methods are guarded to work as iteratees for methods like
 * `_.every`, `_.filter`, `_.map`, `_.mapValues`, `_.reject`, and `_.some`.
 *
 * The guarded methods are:
 * `ary`, `chunk`, `curry`, `curryRight`, `drop`, `dropRight`, `every`,
 * `fill`, `invert`, `parseInt`, `random`, `range`, `rangeRight`, `repeat`,
 * `sampleSize`, `slice`, `some`, `sortBy`, `split`, `take`, `takeRight`,
 * `template`, `trim`, `trimEnd`, `trimStart`, and `words`
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Collection
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} [iteratee=_.identity] The function invoked per iteration.
 * @returns {Array} Returns the new mapped array.
 * @example
 *
 * function square(n) {
 *   return n * n;
 * }
 *
 * _.map([4, 8], square);
 * // => [16, 64]
 *
 * _.map({ 'a': 4, 'b': 8 }, square);
 * // => [16, 64] (iteration order is not guaranteed)
 *
 * var users = [
 *   { 'user': 'barney' },
 *   { 'user': 'fred' }
 * ];
 *
 * // The `_.property` iteratee shorthand.
 * _.map(users, 'user');
 * // => ['barney', 'fred']
 */ function map(collection, iteratee) {
    var func = isArray(collection) ? arrayMap : baseMap;
    return func(collection, baseIteratee(iteratee, 3));
}
module.exports = map;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/flatMap.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseFlatten = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFlatten.js [app-client] (ecmascript)"), map = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/map.js [app-client] (ecmascript)");
/**
 * Creates a flattened array of values by running each element in `collection`
 * thru `iteratee` and flattening the mapped results. The iteratee is invoked
 * with three arguments: (value, index|key, collection).
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Collection
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} [iteratee=_.identity] The function invoked per iteration.
 * @returns {Array} Returns the new flattened array.
 * @example
 *
 * function duplicate(n) {
 *   return [n, n];
 * }
 *
 * _.flatMap([1, 2], duplicate);
 * // => [1, 1, 2, 2]
 */ function flatMap(collection, iteratee) {
    return baseFlatten(map(collection, iteratee), 1);
}
module.exports = flatMap;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isEqual.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIsEqual = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIsEqual.js [app-client] (ecmascript)");
/**
 * Performs a deep comparison between two values to determine if they are
 * equivalent.
 *
 * **Note:** This method supports comparing arrays, array buffers, booleans,
 * date objects, error objects, maps, numbers, `Object` objects, regexes,
 * sets, strings, symbols, and typed arrays. `Object` objects are compared
 * by their own, not inherited, enumerable properties. Functions and DOM
 * nodes are compared by strict equality, i.e. `===`.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to compare.
 * @param {*} other The other value to compare.
 * @returns {boolean} Returns `true` if the values are equivalent, else `false`.
 * @example
 *
 * var object = { 'a': 1 };
 * var other = { 'a': 1 };
 *
 * _.isEqual(object, other);
 * // => true
 *
 * object === other;
 * // => false
 */ function isEqual(value, other) {
    return baseIsEqual(value, other);
}
module.exports = isEqual;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseAssignValue.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var defineProperty = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_defineProperty.js [app-client] (ecmascript)");
/**
 * The base implementation of `assignValue` and `assignMergeValue` without
 * value checks.
 *
 * @private
 * @param {Object} object The object to modify.
 * @param {string} key The key of the property to assign.
 * @param {*} value The value to assign.
 */ function baseAssignValue(object, key, value) {
    if (key == '__proto__' && defineProperty) {
        defineProperty(object, key, {
            'configurable': true,
            'enumerable': true,
            'value': value,
            'writable': true
        });
    } else {
        object[key] = value;
    }
}
module.exports = baseAssignValue;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/mapValues.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseAssignValue = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseAssignValue.js [app-client] (ecmascript)"), baseForOwn = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseForOwn.js [app-client] (ecmascript)"), baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)");
/**
 * Creates an object with the same keys as `object` and values generated
 * by running each own enumerable string keyed property of `object` thru
 * `iteratee`. The iteratee is invoked with three arguments:
 * (value, key, object).
 *
 * @static
 * @memberOf _
 * @since 2.4.0
 * @category Object
 * @param {Object} object The object to iterate over.
 * @param {Function} [iteratee=_.identity] The function invoked per iteration.
 * @returns {Object} Returns the new mapped object.
 * @see _.mapKeys
 * @example
 *
 * var users = {
 *   'fred':    { 'user': 'fred',    'age': 40 },
 *   'pebbles': { 'user': 'pebbles', 'age': 1 }
 * };
 *
 * _.mapValues(users, function(o) { return o.age; });
 * // => { 'fred': 40, 'pebbles': 1 } (iteration order is not guaranteed)
 *
 * // The `_.property` iteratee shorthand.
 * _.mapValues(users, 'age');
 * // => { 'fred': 40, 'pebbles': 1 } (iteration order is not guaranteed)
 */ function mapValues(object, iteratee) {
    var result = {};
    iteratee = baseIteratee(iteratee, 3);
    baseForOwn(object, function(value, key, object) {
        baseAssignValue(result, key, iteratee(value, key, object));
    });
    return result;
}
module.exports = mapValues;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayEvery.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * A specialized version of `_.every` for arrays without support for
 * iteratee shorthands.
 *
 * @private
 * @param {Array} [array] The array to iterate over.
 * @param {Function} predicate The function invoked per iteration.
 * @returns {boolean} Returns `true` if all elements pass the predicate check,
 *  else `false`.
 */ function arrayEvery(array, predicate) {
    var index = -1, length = array == null ? 0 : array.length;
    while(++index < length){
        if (!predicate(array[index], index, array)) {
            return false;
        }
    }
    return true;
}
module.exports = arrayEvery;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseEvery.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseEach = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseEach.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.every` without support for iteratee shorthands.
 *
 * @private
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} predicate The function invoked per iteration.
 * @returns {boolean} Returns `true` if all elements pass the predicate check,
 *  else `false`
 */ function baseEvery(collection, predicate) {
    var result = true;
    baseEach(collection, function(value, index, collection) {
        result = !!predicate(value, index, collection);
        return result;
    });
    return result;
}
module.exports = baseEvery;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/every.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arrayEvery = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arrayEvery.js [app-client] (ecmascript)"), baseEvery = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseEvery.js [app-client] (ecmascript)"), baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isIterateeCall = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIterateeCall.js [app-client] (ecmascript)");
/**
 * Checks if `predicate` returns truthy for **all** elements of `collection`.
 * Iteration is stopped once `predicate` returns falsey. The predicate is
 * invoked with three arguments: (value, index|key, collection).
 *
 * **Note:** This method returns `true` for
 * [empty collections](https://en.wikipedia.org/wiki/Empty_set) because
 * [everything is true](https://en.wikipedia.org/wiki/Vacuous_truth) of
 * elements of empty collections.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Collection
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} [predicate=_.identity] The function invoked per iteration.
 * @param- {Object} [guard] Enables use as an iteratee for methods like `_.map`.
 * @returns {boolean} Returns `true` if all elements pass the predicate check,
 *  else `false`.
 * @example
 *
 * _.every([true, 1, null, 'yes'], Boolean);
 * // => false
 *
 * var users = [
 *   { 'user': 'barney', 'age': 36, 'active': false },
 *   { 'user': 'fred',   'age': 40, 'active': false }
 * ];
 *
 * // The `_.matches` iteratee shorthand.
 * _.every(users, { 'user': 'barney', 'active': false });
 * // => false
 *
 * // The `_.matchesProperty` iteratee shorthand.
 * _.every(users, ['active', false]);
 * // => true
 *
 * // The `_.property` iteratee shorthand.
 * _.every(users, 'active');
 * // => false
 */ function every(collection, predicate, guard) {
    var func = isArray(collection) ? arrayEvery : baseEvery;
    if (guard && isIterateeCall(collection, predicate, guard)) {
        predicate = undefined;
    }
    return func(collection, baseIteratee(predicate, 3));
}
module.exports = every;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/last.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/**
 * Gets the last element of `array`.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Array
 * @param {Array} array The array to query.
 * @returns {*} Returns the last element of `array`.
 * @example
 *
 * _.last([1, 2, 3]);
 * // => 3
 */ function last(array) {
    var length = array == null ? 0 : array.length;
    return length ? array[length - 1] : undefined;
}
module.exports = last;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_getPrototype.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var overArg = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_overArg.js [app-client] (ecmascript)");
/** Built-in value references. */ var getPrototype = overArg(Object.getPrototypeOf, Object);
module.exports = getPrototype;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isPlainObject.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), getPrototype = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_getPrototype.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var objectTag = '[object Object]';
/** Used for built-in method references. */ var funcProto = Function.prototype, objectProto = Object.prototype;
/** Used to resolve the decompiled source of functions. */ var funcToString = funcProto.toString;
/** Used to check objects for own properties. */ var hasOwnProperty = objectProto.hasOwnProperty;
/** Used to infer the `Object` constructor. */ var objectCtorString = funcToString.call(Object);
/**
 * Checks if `value` is a plain object, that is, an object created by the
 * `Object` constructor or one with a `[[Prototype]]` of `null`.
 *
 * @static
 * @memberOf _
 * @since 0.8.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a plain object, else `false`.
 * @example
 *
 * function Foo() {
 *   this.a = 1;
 * }
 *
 * _.isPlainObject(new Foo);
 * // => false
 *
 * _.isPlainObject([1, 2, 3]);
 * // => false
 *
 * _.isPlainObject({ 'x': 0, 'y': 0 });
 * // => true
 *
 * _.isPlainObject(Object.create(null));
 * // => true
 */ function isPlainObject(value) {
    if (!isObjectLike(value) || baseGetTag(value) != objectTag) {
        return false;
    }
    var proto = getPrototype(value);
    if (proto === null) {
        return true;
    }
    var Ctor = hasOwnProperty.call(proto, 'constructor') && proto.constructor;
    return typeof Ctor == 'function' && Ctor instanceof Ctor && funcToString.call(Ctor) == objectCtorString;
}
module.exports = isPlainObject;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/isBoolean.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseGetTag = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseGetTag.js [app-client] (ecmascript)"), isObjectLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isObjectLike.js [app-client] (ecmascript)");
/** `Object#toString` result references. */ var boolTag = '[object Boolean]';
/**
 * Checks if `value` is classified as a boolean primitive or object.
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Lang
 * @param {*} value The value to check.
 * @returns {boolean} Returns `true` if `value` is a boolean, else `false`.
 * @example
 *
 * _.isBoolean(false);
 * // => true
 *
 * _.isBoolean(null);
 * // => false
 */ function isBoolean(value) {
    return value === true || value === false || isObjectLike(value) && baseGetTag(value) == boolTag;
}
module.exports = isBoolean;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSome.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseEach = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseEach.js [app-client] (ecmascript)");
/**
 * The base implementation of `_.some` without support for iteratee shorthands.
 *
 * @private
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} predicate The function invoked per iteration.
 * @returns {boolean} Returns `true` if any element passes the predicate check,
 *  else `false`.
 */ function baseSome(collection, predicate) {
    var result;
    baseEach(collection, function(value, index, collection) {
        result = predicate(value, index, collection);
        return !result;
    });
    return !!result;
}
module.exports = baseSome;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/some.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var arraySome = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_arraySome.js [app-client] (ecmascript)"), baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), baseSome = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseSome.js [app-client] (ecmascript)"), isArray = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArray.js [app-client] (ecmascript)"), isIterateeCall = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_isIterateeCall.js [app-client] (ecmascript)");
/**
 * Checks if `predicate` returns truthy for **any** element of `collection`.
 * Iteration is stopped once `predicate` returns truthy. The predicate is
 * invoked with three arguments: (value, index|key, collection).
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Collection
 * @param {Array|Object} collection The collection to iterate over.
 * @param {Function} [predicate=_.identity] The function invoked per iteration.
 * @param- {Object} [guard] Enables use as an iteratee for methods like `_.map`.
 * @returns {boolean} Returns `true` if any element passes the predicate check,
 *  else `false`.
 * @example
 *
 * _.some([null, 0, 'yes', false], Boolean);
 * // => true
 *
 * var users = [
 *   { 'user': 'barney', 'active': true },
 *   { 'user': 'fred',   'active': false }
 * ];
 *
 * // The `_.matches` iteratee shorthand.
 * _.some(users, { 'user': 'barney', 'active': false });
 * // => false
 *
 * // The `_.matchesProperty` iteratee shorthand.
 * _.some(users, ['active', false]);
 * // => true
 *
 * // The `_.property` iteratee shorthand.
 * _.some(users, 'active');
 * // => true
 */ function some(collection, predicate, guard) {
    var func = isArray(collection) ? arraySome : baseSome;
    if (guard && isIterateeCall(collection, predicate, guard)) {
        predicate = undefined;
    }
    return func(collection, baseIteratee(predicate, 3));
}
module.exports = some;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/_createFind.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), isArrayLike = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/isArrayLike.js [app-client] (ecmascript)"), keys = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/keys.js [app-client] (ecmascript)");
/**
 * Creates a `_.find` or `_.findLast` function.
 *
 * @private
 * @param {Function} findIndexFunc The function to find the collection index.
 * @returns {Function} Returns the new find function.
 */ function createFind(findIndexFunc) {
    return function(collection, predicate, fromIndex) {
        var iterable = Object(collection);
        if (!isArrayLike(collection)) {
            var iteratee = baseIteratee(predicate, 3);
            collection = keys(collection);
            predicate = function(key) {
                return iteratee(iterable[key], key, iterable);
            };
        }
        var index = findIndexFunc(collection, predicate, fromIndex);
        return index > -1 ? iterable[iteratee ? collection[index] : index] : undefined;
    };
}
module.exports = createFind;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/toInteger.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var toFinite = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toFinite.js [app-client] (ecmascript)");
/**
 * Converts `value` to an integer.
 *
 * **Note:** This method is loosely based on
 * [`ToInteger`](http://www.ecma-international.org/ecma-262/7.0/#sec-tointeger).
 *
 * @static
 * @memberOf _
 * @since 4.0.0
 * @category Lang
 * @param {*} value The value to convert.
 * @returns {number} Returns the converted integer.
 * @example
 *
 * _.toInteger(3.2);
 * // => 3
 *
 * _.toInteger(Number.MIN_VALUE);
 * // => 0
 *
 * _.toInteger(Infinity);
 * // => 1.7976931348623157e+308
 *
 * _.toInteger('3.2');
 * // => 3
 */ function toInteger(value) {
    var result = toFinite(value), remainder = result % 1;
    return result === result ? remainder ? result - remainder : result : 0;
}
module.exports = toInteger;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/findIndex.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var baseFindIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseFindIndex.js [app-client] (ecmascript)"), baseIteratee = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_baseIteratee.js [app-client] (ecmascript)"), toInteger = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/toInteger.js [app-client] (ecmascript)");
/* Built-in method references for those with the same name as other `lodash` methods. */ var nativeMax = Math.max;
/**
 * This method is like `_.find` except that it returns the index of the first
 * element `predicate` returns truthy for instead of the element itself.
 *
 * @static
 * @memberOf _
 * @since 1.1.0
 * @category Array
 * @param {Array} array The array to inspect.
 * @param {Function} [predicate=_.identity] The function invoked per iteration.
 * @param {number} [fromIndex=0] The index to search from.
 * @returns {number} Returns the index of the found element, else `-1`.
 * @example
 *
 * var users = [
 *   { 'user': 'barney',  'active': false },
 *   { 'user': 'fred',    'active': false },
 *   { 'user': 'pebbles', 'active': true }
 * ];
 *
 * _.findIndex(users, function(o) { return o.user == 'barney'; });
 * // => 0
 *
 * // The `_.matches` iteratee shorthand.
 * _.findIndex(users, { 'user': 'fred', 'active': false });
 * // => 1
 *
 * // The `_.matchesProperty` iteratee shorthand.
 * _.findIndex(users, ['active', false]);
 * // => 0
 *
 * // The `_.property` iteratee shorthand.
 * _.findIndex(users, 'active');
 * // => 2
 */ function findIndex(array, predicate, fromIndex) {
    var length = array == null ? 0 : array.length;
    if (!length) {
        return -1;
    }
    var index = fromIndex == null ? 0 : toInteger(fromIndex);
    if (index < 0) {
        index = nativeMax(length + index, 0);
    }
    return baseFindIndex(array, baseIteratee(predicate, 3), index);
}
module.exports = findIndex;
}),
"[project]/coding/projects/LangBot/web/node_modules/lodash/find.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var createFind = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/_createFind.js [app-client] (ecmascript)"), findIndex = __turbopack_context__.r("[project]/coding/projects/LangBot/web/node_modules/lodash/findIndex.js [app-client] (ecmascript)");
/**
 * Iterates over elements of `collection`, returning the first element
 * `predicate` returns truthy for. The predicate is invoked with three
 * arguments: (value, index|key, collection).
 *
 * @static
 * @memberOf _
 * @since 0.1.0
 * @category Collection
 * @param {Array|Object} collection The collection to inspect.
 * @param {Function} [predicate=_.identity] The function invoked per iteration.
 * @param {number} [fromIndex=0] The index to search from.
 * @returns {*} Returns the matched element, else `undefined`.
 * @example
 *
 * var users = [
 *   { 'user': 'barney',  'age': 36, 'active': true },
 *   { 'user': 'fred',    'age': 40, 'active': false },
 *   { 'user': 'pebbles', 'age': 1,  'active': true }
 * ];
 *
 * _.find(users, function(o) { return o.age < 40; });
 * // => object for 'barney'
 *
 * // The `_.matches` iteratee shorthand.
 * _.find(users, { 'age': 1, 'active': true });
 * // => object for 'pebbles'
 *
 * // The `_.matchesProperty` iteratee shorthand.
 * _.find(users, ['active', false]);
 * // => object for 'fred'
 *
 * // The `_.property` iteratee shorthand.
 * _.find(users, 'active');
 * // => object for 'barney'
 */ var find = createFind(findIndex);
module.exports = find;
}),
]);

//# sourceMappingURL=a2e30_lodash_1c6cb255._.js.map