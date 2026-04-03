module.exports = [
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/blank-line.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "blankLine",
    ()=>blankLine
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
const blankLine = {
    partial: true,
    tokenize: tokenizeBlankLine
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeBlankLine(effects, ok, nok) {
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of blank line.
   *
   * > 👉 **Note**: `␠` represents a space character.
   *
   * ```markdown
   * > | ␠␠␊
   *     ^
   * > | ␊
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, after, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix)(code) : after(code);
    }
    /**
   * At eof/eol, after optional whitespace.
   *
   * > 👉 **Note**: `␠` represents a space character.
   *
   * ```markdown
   * > | ␠␠␊
   *       ^
   * > | ␊
   *     ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code) ? ok(code) : nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/content.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "content",
    ()=>content
]);
/**
 * @import {
 *   Construct,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer,
 *   Token
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$subtokenize$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-subtokenize/dev/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
;
const content = {
    resolve: resolveContent,
    tokenize: tokenizeContent
};
/** @type {Construct} */ const continuationConstruct = {
    partial: true,
    tokenize: tokenizeContinuation
};
/**
 * Content is transparent: it’s parsed right now. That way, definitions are also
 * parsed right now: before text in paragraphs (specifically, media) are parsed.
 *
 * @type {Resolver}
 */ function resolveContent(events) {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$subtokenize$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["subtokenize"])(events);
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeContent(effects, ok) {
    /** @type {Token | undefined} */ let previous;
    return chunkStart;
    //TURBOPACK unreachable
    ;
    /**
   * Before a content chunk.
   *
   * ```markdown
   * > | abc
   *     ^
   * ```
   *
   * @type {State}
   */ function chunkStart(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected no eof or eol');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].content);
        previous = effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkContent, {
            contentType: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].contentTypeContent
        });
        return chunkInside(code);
    }
    /**
   * In a content chunk.
   *
   * ```markdown
   * > | abc
   *     ^^^
   * ```
   *
   * @type {State}
   */ function chunkInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return contentEnd(code);
        }
        // To do: in `markdown-rs`, each line is parsed on its own, and everything
        // is stitched together resolving.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return effects.check(continuationConstruct, contentContinue, contentEnd)(code);
        }
        // Data.
        effects.consume(code);
        return chunkInside;
    }
    /**
   *
   *
   * @type {State}
   */ function contentEnd(code) {
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkContent);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].content);
        return ok(code);
    }
    /**
   *
   *
   * @type {State}
   */ function contentContinue(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkContent);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(previous, 'expected previous token');
        previous.next = effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkContent, {
            contentType: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].contentTypeContent,
            previous
        });
        previous = previous.next;
        return chunkInside;
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeContinuation(effects, ok, nok) {
    const self = this;
    return startLookahead;
    //TURBOPACK unreachable
    ;
    /**
   *
   *
   * @type {State}
   */ function startLookahead(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected a line ending');
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkContent);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, prefixed, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix);
    }
    /**
   *
   *
   * @type {State}
   */ function prefixed(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return nok(code);
        }
        // Always populated by defaults.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.parser.constructs.disable.null, 'expected `disable.null` to be populated');
        const tail = self.events[self.events.length - 1];
        if (!self.parser.constructs.disable.null.includes('codeIndented') && tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix && tail[2].sliceSerialize(tail[1], true).length >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize) {
            return ok(code);
        }
        return effects.interrupt(self.parser.constructs.flow, nok, ok)(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/attention.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "attention",
    ()=>attention
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   Event,
 *   Point,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer,
 *   Token
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-chunked/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$classify$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-classify-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$resolve$2d$all$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-resolve-all/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
;
const attention = {
    name: 'attention',
    resolveAll: resolveAllAttention,
    tokenize: tokenizeAttention
};
/**
 * Take all events and resolve attention to emphasis or strong.
 *
 * @type {Resolver}
 */ // eslint-disable-next-line complexity
function resolveAllAttention(events, context) {
    let index = -1;
    /** @type {number} */ let open;
    /** @type {Token} */ let group;
    /** @type {Token} */ let text;
    /** @type {Token} */ let openingSequence;
    /** @type {Token} */ let closingSequence;
    /** @type {number} */ let use;
    /** @type {Array<Event>} */ let nextEvents;
    /** @type {number} */ let offset;
    // Walk through all events.
    //
    // Note: performance of this is fine on an mb of normal markdown, but it’s
    // a bottleneck for malicious stuff.
    while(++index < events.length){
        // Find a token that can close.
        if (events[index][0] === 'enter' && events[index][1].type === 'attentionSequence' && events[index][1]._close) {
            open = index;
            // Now walk back to find an opener.
            while(open--){
                // Find a token that can open the closer.
                if (events[open][0] === 'exit' && events[open][1].type === 'attentionSequence' && events[open][1]._open && // If the markers are the same:
                context.sliceSerialize(events[open][1]).charCodeAt(0) === context.sliceSerialize(events[index][1]).charCodeAt(0)) {
                    // If the opening can close or the closing can open,
                    // and the close size *is not* a multiple of three,
                    // but the sum of the opening and closing size *is* multiple of three,
                    // then don’t match.
                    if ((events[open][1]._close || events[index][1]._open) && (events[index][1].end.offset - events[index][1].start.offset) % 3 && !((events[open][1].end.offset - events[open][1].start.offset + events[index][1].end.offset - events[index][1].start.offset) % 3)) {
                        continue;
                    }
                    // Number of markers to use from the sequence.
                    use = events[open][1].end.offset - events[open][1].start.offset > 1 && events[index][1].end.offset - events[index][1].start.offset > 1 ? 2 : 1;
                    const start = {
                        ...events[open][1].end
                    };
                    const end = {
                        ...events[index][1].start
                    };
                    movePoint(start, -use);
                    movePoint(end, use);
                    openingSequence = {
                        type: use > 1 ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].strongSequence : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].emphasisSequence,
                        start,
                        end: {
                            ...events[open][1].end
                        }
                    };
                    closingSequence = {
                        type: use > 1 ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].strongSequence : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].emphasisSequence,
                        start: {
                            ...events[index][1].start
                        },
                        end
                    };
                    text = {
                        type: use > 1 ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].strongText : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].emphasisText,
                        start: {
                            ...events[open][1].end
                        },
                        end: {
                            ...events[index][1].start
                        }
                    };
                    group = {
                        type: use > 1 ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].strong : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].emphasis,
                        start: {
                            ...openingSequence.start
                        },
                        end: {
                            ...closingSequence.end
                        }
                    };
                    events[open][1].end = {
                        ...openingSequence.start
                    };
                    events[index][1].start = {
                        ...closingSequence.end
                    };
                    nextEvents = [];
                    // If there are more markers in the opening, add them before.
                    if (events[open][1].end.offset - events[open][1].start.offset) {
                        nextEvents = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(nextEvents, [
                            [
                                'enter',
                                events[open][1],
                                context
                            ],
                            [
                                'exit',
                                events[open][1],
                                context
                            ]
                        ]);
                    }
                    // Opening.
                    nextEvents = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(nextEvents, [
                        [
                            'enter',
                            group,
                            context
                        ],
                        [
                            'enter',
                            openingSequence,
                            context
                        ],
                        [
                            'exit',
                            openingSequence,
                            context
                        ],
                        [
                            'enter',
                            text,
                            context
                        ]
                    ]);
                    // Always populated by defaults.
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(context.parser.constructs.insideSpan.null, 'expected `insideSpan` to be populated');
                    // Between.
                    nextEvents = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(nextEvents, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$resolve$2d$all$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveAll"])(context.parser.constructs.insideSpan.null, events.slice(open + 1, index), context));
                    // Closing.
                    nextEvents = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(nextEvents, [
                        [
                            'exit',
                            text,
                            context
                        ],
                        [
                            'enter',
                            closingSequence,
                            context
                        ],
                        [
                            'exit',
                            closingSequence,
                            context
                        ],
                        [
                            'exit',
                            group,
                            context
                        ]
                    ]);
                    // If there are more markers in the closing, add them after.
                    if (events[index][1].end.offset - events[index][1].start.offset) {
                        offset = 2;
                        nextEvents = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(nextEvents, [
                            [
                                'enter',
                                events[index][1],
                                context
                            ],
                            [
                                'exit',
                                events[index][1],
                                context
                            ]
                        ]);
                    } else {
                        offset = 0;
                    }
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["splice"])(events, open - 1, index - open + 3, nextEvents);
                    index = open + nextEvents.length - offset - 2;
                    break;
                }
            }
        }
    }
    // Remove remaining sequences.
    index = -1;
    while(++index < events.length){
        if (events[index][1].type === 'attentionSequence') {
            events[index][1].type = 'data';
        }
    }
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeAttention(effects, ok) {
    const attentionMarkers = this.parser.constructs.attentionMarkers.null;
    const previous = this.previous;
    const before = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$classify$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["classifyCharacter"])(previous);
    /** @type {NonNullable<Code>} */ let marker;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Before a sequence.
   *
   * ```markdown
   * > | **
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].asterisk || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].underscore, 'expected asterisk or underscore');
        marker = code;
        effects.enter('attentionSequence');
        return inside(code);
    }
    /**
   * In a sequence.
   *
   * ```markdown
   * > | **
   *     ^^
   * ```
   *
   * @type {State}
   */ function inside(code) {
        if (code === marker) {
            effects.consume(code);
            return inside;
        }
        const token = effects.exit('attentionSequence');
        // To do: next major: move this to resolver, just like `markdown-rs`.
        const after = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$classify$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["classifyCharacter"])(code);
        // Always populated by defaults.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(attentionMarkers, 'expected `attentionMarkers` to be populated');
        const open = !after || after === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].characterGroupPunctuation && before || attentionMarkers.includes(code);
        const close = !before || before === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].characterGroupPunctuation && after || attentionMarkers.includes(previous);
        token._open = Boolean(marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].asterisk ? open : open && (before || !close));
        token._close = Boolean(marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].asterisk ? close : close && (after || !open));
        return ok(code);
    }
}
/**
 * Move a point a bit.
 *
 * Note: `move` only works inside lines! It’s not possible to move past other
 * chunks (replacement characters, tabs, or line endings).
 *
 * @param {Point} point
 *   Point.
 * @param {number} offset
 *   Amount to move.
 * @returns {undefined}
 *   Nothing.
 */ function movePoint(point, offset) {
    point.column += offset;
    point.offset += offset;
    point._bufferIndex += offset;
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/autolink.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "autolink",
    ()=>autolink
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
const autolink = {
    name: 'autolink',
    tokenize: tokenizeAutolink
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeAutolink(effects, ok, nok) {
    let size = 0;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of an autolink.
   *
   * ```markdown
   * > | a<https://example.com>b
   *      ^
   * > | a<user@example.com>b
   *      ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan, 'expected `<`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolink);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkMarker);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkProtocol);
        return open;
    }
    /**
   * After `<`, at protocol or atext.
   *
   * ```markdown
   * > | a<https://example.com>b
   *       ^
   * > | a<user@example.com>b
   *       ^
   * ```
   *
   * @type {State}
   */ function open(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            return schemeOrEmailAtext;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].atSign) {
            return nok(code);
        }
        return emailAtext(code);
    }
    /**
   * At second byte of protocol or atext.
   *
   * ```markdown
   * > | a<https://example.com>b
   *        ^
   * > | a<user@example.com>b
   *        ^
   * ```
   *
   * @type {State}
   */ function schemeOrEmailAtext(code) {
        // ASCII alphanumeric and `+`, `-`, and `.`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].plusSign || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dot || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) {
            // Count the previous alphabetical from `open` too.
            size = 1;
            return schemeInsideOrEmailAtext(code);
        }
        return emailAtext(code);
    }
    /**
   * In ambiguous protocol or atext.
   *
   * ```markdown
   * > | a<https://example.com>b
   *        ^
   * > | a<user@example.com>b
   *        ^
   * ```
   *
   * @type {State}
   */ function schemeInsideOrEmailAtext(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].colon) {
            effects.consume(code);
            size = 0;
            return urlInside;
        }
        // ASCII alphanumeric and `+`, `-`, and `.`.
        if ((code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].plusSign || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dot || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) && size++ < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].autolinkSchemeSizeMax) {
            effects.consume(code);
            return schemeInsideOrEmailAtext;
        }
        size = 0;
        return emailAtext(code);
    }
    /**
   * After protocol, in URL.
   *
   * ```markdown
   * > | a<https://example.com>b
   *             ^
   * ```
   *
   * @type {State}
   */ function urlInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkProtocol);
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkMarker);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolink);
            return ok;
        }
        // ASCII control, space, or `<`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].space || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiControl"])(code)) {
            return nok(code);
        }
        effects.consume(code);
        return urlInside;
    }
    /**
   * In email atext.
   *
   * ```markdown
   * > | a<user.name@example.com>b
   *              ^
   * ```
   *
   * @type {State}
   */ function emailAtext(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].atSign) {
            effects.consume(code);
            return emailAtSignOrDot;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAtext"])(code)) {
            effects.consume(code);
            return emailAtext;
        }
        return nok(code);
    }
    /**
   * In label, after at-sign or dot.
   *
   * ```markdown
   * > | a<user.name@example.com>b
   *                 ^       ^
   * ```
   *
   * @type {State}
   */ function emailAtSignOrDot(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code) ? emailLabel(code) : nok(code);
    }
    /**
   * In label, where `.` and `>` are allowed.
   *
   * ```markdown
   * > | a<user.name@example.com>b
   *                   ^
   * ```
   *
   * @type {State}
   */ function emailLabel(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dot) {
            effects.consume(code);
            size = 0;
            return emailAtSignOrDot;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            // Exit, then change the token type.
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkProtocol).type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkEmail;
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolinkMarker);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].autolink);
            return ok;
        }
        return emailValue(code);
    }
    /**
   * In label, where `.` and `>` are *not* allowed.
   *
   * Though, this is also used in `emailLabel` to parse other values.
   *
   * ```markdown
   * > | a<user.name@ex-ample.com>b
   *                    ^
   * ```
   *
   * @type {State}
   */ function emailValue(code) {
        // ASCII alphanumeric or `-`.
        if ((code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) && size++ < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].autolinkDomainSizeMax) {
            const next = code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash ? emailValue : emailLabel;
            effects.consume(code);
            return next;
        }
        return nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/block-quote.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "blockQuote",
    ()=>blockQuote
]);
/**
 * @import {
 *   Construct,
 *   Exiter,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const blockQuote = {
    continuation: {
        tokenize: tokenizeBlockQuoteContinuation
    },
    exit,
    name: 'blockQuote',
    tokenize: tokenizeBlockQuoteStart
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeBlockQuoteStart(effects, ok, nok) {
    const self = this;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of block quote.
   *
   * ```markdown
   * > | > a
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            const state = self.containerState;
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(state, 'expected `containerState` to be defined in container');
            if (!state.open) {
                effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuote, {
                    _container: true
                });
                state.open = true;
            }
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuotePrefix);
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuoteMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuoteMarker);
            return after;
        }
        return nok(code);
    }
    /**
   * After `>`, before optional whitespace.
   *
   * ```markdown
   * > | > a
   *      ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuotePrefixWhitespace);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuotePrefixWhitespace);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuotePrefix);
            return ok;
        }
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuotePrefix);
        return ok(code);
    }
}
/**
 * Start of block quote continuation.
 *
 * ```markdown
 *   | > a
 * > | > b
 *     ^
 * ```
 *
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeBlockQuoteContinuation(effects, ok, nok) {
    const self = this;
    return contStart;
    //TURBOPACK unreachable
    ;
    /**
   * Start of block quote continuation.
   *
   * Also used to parse the first block quote opening.
   *
   * ```markdown
   *   | > a
   * > | > b
   *     ^
   * ```
   *
   * @type {State}
   */ function contStart(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            // Always populated by defaults.
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.parser.constructs.disable.null, 'expected `disable.null` to be populated');
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, contBefore, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, self.parser.constructs.disable.null.includes('codeIndented') ? undefined : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize)(code);
        }
        return contBefore(code);
    }
    /**
   * At `>`, after optional whitespace.
   *
   * Also used to parse the first block quote opening.
   *
   * ```markdown
   *   | > a
   * > | > b
   *     ^
   * ```
   *
   * @type {State}
   */ function contBefore(code) {
        return effects.attempt(blockQuote, ok, nok)(code);
    }
}
/** @type {Exiter} */ function exit(effects) {
    effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].blockQuote);
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/character-escape.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "characterEscape",
    ()=>characterEscape
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
const characterEscape = {
    name: 'characterEscape',
    tokenize: tokenizeCharacterEscape
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeCharacterEscape(effects, ok, nok) {
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of character escape.
   *
   * ```markdown
   * > | a\*b
   *      ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].backslash, 'expected `\\`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterEscape);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].escapeMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].escapeMarker);
        return inside;
    }
    /**
   * After `\`, at punctuation.
   *
   * ```markdown
   * > | a\*b
   *       ^
   * ```
   *
   * @type {State}
   */ function inside(code) {
        // ASCII punctuation.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiPunctuation"])(code)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterEscapeValue);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterEscapeValue);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterEscape);
            return ok;
        }
        return nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/character-reference.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "characterReference",
    ()=>characterReference
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$decode$2d$named$2d$character$2d$reference$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/decode-named-character-reference/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const characterReference = {
    name: 'characterReference',
    tokenize: tokenizeCharacterReference
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeCharacterReference(effects, ok, nok) {
    const self = this;
    let size = 0;
    /** @type {number} */ let max;
    /** @type {(code: Code) => boolean} */ let test;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of character reference.
   *
   * ```markdown
   * > | a&amp;b
   *      ^
   * > | a&#123;b
   *      ^
   * > | a&#x9;b
   *      ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].ampersand, 'expected `&`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReference);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarker);
        return open;
    }
    /**
   * After `&`, at `#` for numeric references or alphanumeric for named
   * references.
   *
   * ```markdown
   * > | a&amp;b
   *       ^
   * > | a&#123;b
   *       ^
   * > | a&#x9;b
   *       ^
   * ```
   *
   * @type {State}
   */ function open(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].numberSign) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarkerNumeric);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarkerNumeric);
            return numeric;
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceValue);
        max = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].characterReferenceNamedSizeMax;
        test = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"];
        return value(code);
    }
    /**
   * After `#`, at `x` for hexadecimals or digit for decimals.
   *
   * ```markdown
   * > | a&#123;b
   *        ^
   * > | a&#x9;b
   *        ^
   * ```
   *
   * @type {State}
   */ function numeric(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].uppercaseX || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lowercaseX) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarkerHexadecimal);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarkerHexadecimal);
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceValue);
            max = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].characterReferenceHexadecimalSizeMax;
            test = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiHexDigit"];
            return value;
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceValue);
        max = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].characterReferenceDecimalSizeMax;
        test = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiDigit"];
        return value(code);
    }
    /**
   * After markers (`&#x`, `&#`, or `&`), in value, before `;`.
   *
   * The character reference kind defines what and how many characters are
   * allowed.
   *
   * ```markdown
   * > | a&amp;b
   *       ^^^
   * > | a&#123;b
   *        ^^^
   * > | a&#x9;b
   *         ^
   * ```
   *
   * @type {State}
   */ function value(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].semicolon && size) {
            const token = effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceValue);
            if (test === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"] && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$decode$2d$named$2d$character$2d$reference$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["decodeNamedCharacterReference"])(self.sliceSerialize(token))) {
                return nok(code);
            }
            // To do: `markdown-rs` uses a different name:
            // `CharacterReferenceMarkerSemi`.
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReferenceMarker);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterReference);
            return ok;
        }
        if (test(code) && size++ < max) {
            effects.consume(code);
            return value;
        }
        return nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/code-fenced.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "codeFenced",
    ()=>codeFenced
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
/** @type {Construct} */ const nonLazyContinuation = {
    partial: true,
    tokenize: tokenizeNonLazyContinuation
};
const codeFenced = {
    concrete: true,
    name: 'codeFenced',
    tokenize: tokenizeCodeFenced
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeCodeFenced(effects, ok, nok) {
    const self = this;
    /** @type {Construct} */ const closeStart = {
        partial: true,
        tokenize: tokenizeCloseStart
    };
    let initialPrefix = 0;
    let sizeOpen = 0;
    /** @type {NonNullable<Code>} */ let marker;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of code.
   *
   * ```markdown
   * > | ~~~js
   *     ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function start(code) {
        // To do: parse whitespace like `markdown-rs`.
        return beforeSequenceOpen(code);
    }
    /**
   * In opening fence, after prefix, at sequence.
   *
   * ```markdown
   * > | ~~~js
   *     ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function beforeSequenceOpen(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].tilde, 'expected `` ` `` or `~`');
        const tail = self.events[self.events.length - 1];
        initialPrefix = tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix ? tail[2].sliceSerialize(tail[1], true).length : 0;
        marker = code;
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFenced);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFence);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceSequence);
        return sequenceOpen(code);
    }
    /**
   * In opening fence sequence.
   *
   * ```markdown
   * > | ~~~js
   *      ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function sequenceOpen(code) {
        if (code === marker) {
            sizeOpen++;
            effects.consume(code);
            return sequenceOpen;
        }
        if (sizeOpen < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].codeFencedSequenceSizeMin) {
            return nok(code);
        }
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceSequence);
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, infoBefore, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code) : infoBefore(code);
    }
    /**
   * In opening fence, after the sequence (and optional whitespace), before info.
   *
   * ```markdown
   * > | ~~~js
   *        ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function infoBefore(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFence);
            return self.interrupt ? ok(code) : effects.check(nonLazyContinuation, atNonLazyBreak, after)(code);
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceInfo);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkString, {
            contentType: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].contentTypeString
        });
        return info(code);
    }
    /**
   * In info.
   *
   * ```markdown
   * > | ~~~js
   *        ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function info(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkString);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceInfo);
            return infoBefore(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkString);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceInfo);
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, metaBefore, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent && code === marker) {
            return nok(code);
        }
        effects.consume(code);
        return info;
    }
    /**
   * In opening fence, after info and whitespace, before meta.
   *
   * ```markdown
   * > | ~~~js eval
   *           ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function metaBefore(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return infoBefore(code);
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceMeta);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkString, {
            contentType: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].contentTypeString
        });
        return meta(code);
    }
    /**
   * In meta.
   *
   * ```markdown
   * > | ~~~js eval
   *           ^
   *   | alert(1)
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function meta(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkString);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceMeta);
            return infoBefore(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent && code === marker) {
            return nok(code);
        }
        effects.consume(code);
        return meta;
    }
    /**
   * At eol/eof in code, before a non-lazy closing fence or content.
   *
   * ```markdown
   * > | ~~~js
   *          ^
   * > | alert(1)
   *             ^
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function atNonLazyBreak(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
        return effects.attempt(closeStart, after, contentBefore)(code);
    }
    /**
   * Before code content, not a closing fence, at eol.
   *
   * ```markdown
   *   | ~~~js
   * > | alert(1)
   *             ^
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function contentBefore(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return contentStart;
    }
    /**
   * Before code content, not a closing fence.
   *
   * ```markdown
   *   | ~~~js
   * > | alert(1)
   *     ^
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function contentStart(code) {
        return initialPrefix > 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, beforeContentChunk, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, initialPrefix + 1)(code) : beforeContentChunk(code);
    }
    /**
   * Before code content, after optional prefix.
   *
   * ```markdown
   *   | ~~~js
   * > | alert(1)
   *     ^
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function beforeContentChunk(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return effects.check(nonLazyContinuation, atNonLazyBreak, after)(code);
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFlowValue);
        return contentChunk(code);
    }
    /**
   * In code content.
   *
   * ```markdown
   *   | ~~~js
   * > | alert(1)
   *     ^^^^^^^^
   *   | ~~~
   * ```
   *
   * @type {State}
   */ function contentChunk(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFlowValue);
            return beforeContentChunk(code);
        }
        effects.consume(code);
        return contentChunk;
    }
    /**
   * After code.
   *
   * ```markdown
   *   | ~~~js
   *   | alert(1)
   * > | ~~~
   *        ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFenced);
        return ok(code);
    }
    /**
   * @this {TokenizeContext}
   *   Context.
   * @type {Tokenizer}
   */ function tokenizeCloseStart(effects, ok, nok) {
        let size = 0;
        return startBefore;
        //TURBOPACK unreachable
        ;
        /**
     *
     *
     * @type {State}
     */ function startBefore(code) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            return start;
        }
        /**
     * Before closing fence, at optional whitespace.
     *
     * ```markdown
     *   | ~~~js
     *   | alert(1)
     * > | ~~~
     *     ^
     * ```
     *
     * @type {State}
     */ function start(code) {
            // Always populated by defaults.
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.parser.constructs.disable.null, 'expected `disable.null` to be populated');
            // To do: `enter` here or in next state?
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFence);
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, beforeSequenceClose, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, self.parser.constructs.disable.null.includes('codeIndented') ? undefined : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize)(code) : beforeSequenceClose(code);
        }
        /**
     * In closing fence, after optional whitespace, at sequence.
     *
     * ```markdown
     *   | ~~~js
     *   | alert(1)
     * > | ~~~
     *     ^
     * ```
     *
     * @type {State}
     */ function beforeSequenceClose(code) {
            if (code === marker) {
                effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceSequence);
                return sequenceClose(code);
            }
            return nok(code);
        }
        /**
     * In closing fence sequence.
     *
     * ```markdown
     *   | ~~~js
     *   | alert(1)
     * > | ~~~
     *     ^
     * ```
     *
     * @type {State}
     */ function sequenceClose(code) {
            if (code === marker) {
                size++;
                effects.consume(code);
                return sequenceClose;
            }
            if (size >= sizeOpen) {
                effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFenceSequence);
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, sequenceCloseAfter, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code) : sequenceCloseAfter(code);
            }
            return nok(code);
        }
        /**
     * After closing fence sequence, after optional whitespace.
     *
     * ```markdown
     *   | ~~~js
     *   | alert(1)
     * > | ~~~
     *        ^
     * ```
     *
     * @type {State}
     */ function sequenceCloseAfter(code) {
            if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
                effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFencedFence);
                return ok(code);
            }
            return nok(code);
        }
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeNonLazyContinuation(effects, ok, nok) {
    const self = this;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   *
   *
   * @type {State}
   */ function start(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return nok(code);
        }
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return lineStart;
    }
    /**
   *
   *
   * @type {State}
   */ function lineStart(code) {
        return self.parser.lazy[self.now().line] ? nok(code) : ok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/code-indented.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "codeIndented",
    ()=>codeIndented
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const codeIndented = {
    name: 'codeIndented',
    tokenize: tokenizeCodeIndented
};
/** @type {Construct} */ const furtherStart = {
    partial: true,
    tokenize: tokenizeFurtherStart
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeCodeIndented(effects, ok, nok) {
    const self = this;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of code (indented).
   *
   * > **Parsing note**: it is not needed to check if this first line is a
   * > filled line (that it has a non-whitespace character), because blank lines
   * > are parsed already, so we never run into that.
   *
   * ```markdown
   * > |     aaa
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        // To do: manually check if interrupting like `markdown-rs`.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code));
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeIndented);
        // To do: use an improved `space_or_tab` function like `markdown-rs`,
        // so that we can drop the next state.
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, afterPrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize + 1)(code);
    }
    /**
   * At start, after 1 or 4 spaces.
   *
   * ```markdown
   * > |     aaa
   *         ^
   * ```
   *
   * @type {State}
   */ function afterPrefix(code) {
        const tail = self.events[self.events.length - 1];
        return tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix && tail[2].sliceSerialize(tail[1], true).length >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize ? atBreak(code) : nok(code);
    }
    /**
   * At a break.
   *
   * ```markdown
   * > |     aaa
   *         ^  ^
   * ```
   *
   * @type {State}
   */ function atBreak(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return after(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return effects.attempt(furtherStart, atBreak, after)(code);
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFlowValue);
        return inside(code);
    }
    /**
   * In code content.
   *
   * ```markdown
   * > |     aaa
   *         ^^^^
   * ```
   *
   * @type {State}
   */ function inside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeFlowValue);
            return atBreak(code);
        }
        effects.consume(code);
        return inside;
    }
    /** @type {State} */ function after(code) {
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeIndented);
        // To do: allow interrupting like `markdown-rs`.
        // Feel free to interrupt.
        // tokenizer.interrupt = false
        return ok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeFurtherStart(effects, ok, nok) {
    const self = this;
    return furtherStart;
    //TURBOPACK unreachable
    ;
    /**
   * At eol, trying to parse another indent.
   *
   * ```markdown
   * > |     aaa
   *            ^
   *   |     bbb
   * ```
   *
   * @type {State}
   */ function furtherStart(code) {
        // To do: improve `lazy` / `pierce` handling.
        // If this is a lazy line, it can’t be code.
        if (self.parser.lazy[self.now().line]) {
            return nok(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            return furtherStart;
        }
        // To do: the code here in `micromark-js` is a bit different from
        // `markdown-rs` because there it can attempt spaces.
        // We can’t yet.
        //
        // To do: use an improved `space_or_tab` function like `markdown-rs`,
        // so that we can drop the next state.
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, afterPrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize + 1)(code);
    }
    /**
   * At start, after 1 or 4 spaces.
   *
   * ```markdown
   * > |     aaa
   *         ^
   * ```
   *
   * @type {State}
   */ function afterPrefix(code) {
        const tail = self.events[self.events.length - 1];
        return tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix && tail[2].sliceSerialize(tail[1], true).length >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize ? ok(code) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code) ? furtherStart(code) : nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/code-text.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "codeText",
    ()=>codeText
]);
/**
 * @import {
 *   Construct,
 *   Previous,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer,
 *   Token
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
const codeText = {
    name: 'codeText',
    previous,
    resolve: resolveCodeText,
    tokenize: tokenizeCodeText
};
// To do: next major: don’t resolve, like `markdown-rs`.
/** @type {Resolver} */ function resolveCodeText(events) {
    let tailExitIndex = events.length - 4;
    let headEnterIndex = 3;
    /** @type {number} */ let index;
    /** @type {number | undefined} */ let enter;
    // If we start and end with an EOL or a space.
    if ((events[headEnterIndex][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding || events[headEnterIndex][1].type === 'space') && (events[tailExitIndex][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding || events[tailExitIndex][1].type === 'space')) {
        index = headEnterIndex;
        // And we have data.
        while(++index < tailExitIndex){
            if (events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextData) {
                // Then we have padding.
                events[headEnterIndex][1].type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextPadding;
                events[tailExitIndex][1].type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextPadding;
                headEnterIndex += 2;
                tailExitIndex -= 2;
                break;
            }
        }
    }
    // Merge adjacent spaces and data.
    index = headEnterIndex - 1;
    tailExitIndex++;
    while(++index <= tailExitIndex){
        if (enter === undefined) {
            if (index !== tailExitIndex && events[index][1].type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding) {
                enter = index;
            }
        } else if (index === tailExitIndex || events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding) {
            events[enter][1].type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextData;
            if (index !== enter + 2) {
                events[enter][1].end = events[index - 1][1].end;
                events.splice(enter + 2, index - enter - 2);
                tailExitIndex -= index - enter - 2;
                index = enter + 2;
            }
            enter = undefined;
        }
    }
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Previous}
 */ function previous(code) {
    // If there is a previous code, there will always be a tail.
    return code !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent || this.events[this.events.length - 1][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].characterEscape;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeCodeText(effects, ok, nok) {
    const self = this;
    let sizeOpen = 0;
    /** @type {number} */ let size;
    /** @type {Token} */ let token;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of code (text).
   *
   * ```markdown
   * > | `a`
   *     ^
   * > | \`a`
   *      ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent, 'expected `` ` ``');
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(previous.call(self, self.previous), 'expected correct previous');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeText);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextSequence);
        return sequenceOpen(code);
    }
    /**
   * In opening sequence.
   *
   * ```markdown
   * > | `a`
   *     ^
   * ```
   *
   * @type {State}
   */ function sequenceOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent) {
            effects.consume(code);
            sizeOpen++;
            return sequenceOpen;
        }
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextSequence);
        return between(code);
    }
    /**
   * Between something and something else.
   *
   * ```markdown
   * > | `a`
   *      ^^
   * ```
   *
   * @type {State}
   */ function between(code) {
        // EOF.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return nok(code);
        }
        // To do: next major: don’t do spaces in resolve, but when compiling,
        // like `markdown-rs`.
        // Tabs don’t work, and virtual spaces don’t make sense.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].space) {
            effects.enter('space');
            effects.consume(code);
            effects.exit('space');
            return between;
        }
        // Closing fence? Could also be data.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent) {
            token = effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextSequence);
            size = 0;
            return sequenceClose(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            return between;
        }
        // Data.
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextData);
        return data(code);
    }
    /**
   * In data.
   *
   * ```markdown
   * > | `a`
   *      ^
   * ```
   *
   * @type {State}
   */ function data(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].space || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextData);
            return between(code);
        }
        effects.consume(code);
        return data;
    }
    /**
   * In closing sequence.
   *
   * ```markdown
   * > | `a`
   *       ^
   * ```
   *
   * @type {State}
   */ function sequenceClose(code) {
        // More.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent) {
            effects.consume(code);
            size++;
            return sequenceClose;
        }
        // Done!
        if (size === sizeOpen) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextSequence);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeText);
            return ok(code);
        }
        // More or less accents: mark as data.
        token.type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].codeTextData;
        return data(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/definition.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "definition",
    ()=>definition
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$destination$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-destination/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$label$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-label/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$title$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-title/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-whitespace/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$normalize$2d$identifier$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-normalize-identifier/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
;
;
;
;
;
const definition = {
    name: 'definition',
    tokenize: tokenizeDefinition
};
/** @type {Construct} */ const titleBefore = {
    partial: true,
    tokenize: tokenizeTitleBefore
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeDefinition(effects, ok, nok) {
    const self = this;
    /** @type {string} */ let identifier;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * At start of a definition.
   *
   * ```markdown
   * > | [a]: b "c"
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        // Do not interrupt paragraphs (but do follow definitions).
        // To do: do `interrupt` the way `markdown-rs` does.
        // To do: parse whitespace the way `markdown-rs` does.
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definition);
        return before(code);
    }
    /**
   * After optional whitespace, at `[`.
   *
   * ```markdown
   * > | [a]: b "c"
   *     ^
   * ```
   *
   * @type {State}
   */ function before(code) {
        // To do: parse whitespace the way `markdown-rs` does.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket, 'expected `[`');
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$label$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryLabel"].call(self, effects, labelAfter, // Note: we don’t need to reset the way `markdown-rs` does.
        nok, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionLabel, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionLabelMarker, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionLabelString)(code);
    }
    /**
   * After label.
   *
   * ```markdown
   * > | [a]: b "c"
   *        ^
   * ```
   *
   * @type {State}
   */ function labelAfter(code) {
        identifier = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$normalize$2d$identifier$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["normalizeIdentifier"])(self.sliceSerialize(self.events[self.events.length - 1][1]).slice(1, -1));
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].colon) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionMarker);
            return markerAfter;
        }
        return nok(code);
    }
    /**
   * After marker.
   *
   * ```markdown
   * > | [a]: b "c"
   *         ^
   * ```
   *
   * @type {State}
   */ function markerAfter(code) {
        // Note: whitespace is optional.
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryWhitespace"])(effects, destinationBefore)(code) : destinationBefore(code);
    }
    /**
   * Before destination.
   *
   * ```markdown
   * > | [a]: b "c"
   *          ^
   * ```
   *
   * @type {State}
   */ function destinationBefore(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$destination$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryDestination"])(effects, destinationAfter, // Note: we don’t need to reset the way `markdown-rs` does.
        nok, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionDestination, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionDestinationLiteral, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionDestinationLiteralMarker, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionDestinationRaw, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionDestinationString)(code);
    }
    /**
   * After destination.
   *
   * ```markdown
   * > | [a]: b "c"
   *           ^
   * ```
   *
   * @type {State}
   */ function destinationAfter(code) {
        return effects.attempt(titleBefore, after, after)(code);
    }
    /**
   * After definition.
   *
   * ```markdown
   * > | [a]: b
   *           ^
   * > | [a]: b "c"
   *               ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, afterWhitespace, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code) : afterWhitespace(code);
    }
    /**
   * After definition, after optional whitespace.
   *
   * ```markdown
   * > | [a]: b
   *           ^
   * > | [a]: b "c"
   *               ^
   * ```
   *
   * @type {State}
   */ function afterWhitespace(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definition);
            // Note: we don’t care about uniqueness.
            // It’s likely that that doesn’t happen very frequently.
            // It is more likely that it wastes precious time.
            self.parser.defined.push(identifier);
            // To do: `markdown-rs` interrupt.
            // // You’d be interrupting.
            // tokenizer.interrupt = true
            return ok(code);
        }
        return nok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeTitleBefore(effects, ok, nok) {
    return titleBefore;
    //TURBOPACK unreachable
    ;
    /**
   * After destination, at whitespace.
   *
   * ```markdown
   * > | [a]: b
   *           ^
   * > | [a]: b "c"
   *           ^
   * ```
   *
   * @type {State}
   */ function titleBefore(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryWhitespace"])(effects, beforeMarker)(code) : nok(code);
    }
    /**
   * At title.
   *
   * ```markdown
   *   | [a]: b
   * > | "c"
   *     ^
   * ```
   *
   * @type {State}
   */ function beforeMarker(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$title$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryTitle"])(effects, titleAfter, nok, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionTitle, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionTitleMarker, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definitionTitleString)(code);
    }
    /**
   * After title.
   *
   * ```markdown
   * > | [a]: b "c"
   *               ^
   * ```
   *
   * @type {State}
   */ function titleAfter(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, titleAfterOptionalWhitespace, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code) : titleAfterOptionalWhitespace(code);
    }
    /**
   * After title, after optional whitespace.
   *
   * ```markdown
   * > | [a]: b "c"
   *               ^
   * ```
   *
   * @type {State}
   */ function titleAfterOptionalWhitespace(code) {
        return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code) ? ok(code) : nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/hard-break-escape.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "hardBreakEscape",
    ()=>hardBreakEscape
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
const hardBreakEscape = {
    name: 'hardBreakEscape',
    tokenize: tokenizeHardBreakEscape
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeHardBreakEscape(effects, ok, nok) {
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of a hard break (escape).
   *
   * ```markdown
   * > | a\
   *      ^
   *   | b
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].backslash, 'expected `\\`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].hardBreakEscape);
        effects.consume(code);
        return after;
    }
    /**
   * After `\`, at eol.
   *
   * ```markdown
   * > | a\
   *       ^
   *   | b
   * ```
   *
   *  @type {State}
   */ function after(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].hardBreakEscape);
            return ok(code);
        }
        return nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/heading-atx.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "headingAtx",
    ()=>headingAtx
]);
/**
 * @import {
 *   Construct,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer,
 *   Token
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-chunked/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
;
const headingAtx = {
    name: 'headingAtx',
    resolve: resolveHeadingAtx,
    tokenize: tokenizeHeadingAtx
};
/** @type {Resolver} */ function resolveHeadingAtx(events, context) {
    let contentEnd = events.length - 2;
    let contentStart = 3;
    /** @type {Token} */ let content;
    /** @type {Token} */ let text;
    // Prefix whitespace, part of the opening.
    if (events[contentStart][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace) {
        contentStart += 2;
    }
    // Suffix whitespace, part of the closing.
    if (contentEnd - 2 > contentStart && events[contentEnd][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace) {
        contentEnd -= 2;
    }
    if (events[contentEnd][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingSequence && (contentStart === contentEnd - 1 || contentEnd - 4 > contentStart && events[contentEnd - 2][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)) {
        contentEnd -= contentStart + 1 === contentEnd ? 2 : 4;
    }
    if (contentEnd > contentStart) {
        content = {
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingText,
            start: events[contentStart][1].start,
            end: events[contentEnd][1].end
        };
        text = {
            type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].chunkText,
            start: events[contentStart][1].start,
            end: events[contentEnd][1].end,
            contentType: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].contentTypeText
        };
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["splice"])(events, contentStart, contentEnd - contentStart + 1, [
            [
                'enter',
                content,
                context
            ],
            [
                'enter',
                text,
                context
            ],
            [
                'exit',
                text,
                context
            ],
            [
                'exit',
                content,
                context
            ]
        ]);
    }
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeHeadingAtx(effects, ok, nok) {
    let size = 0;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of a heading (atx).
   *
   * ```markdown
   * > | ## aa
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        // To do: parse indent like `markdown-rs`.
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeading);
        return before(code);
    }
    /**
   * After optional whitespace, at `#`.
   *
   * ```markdown
   * > | ## aa
   *     ^
   * ```
   *
   * @type {State}
   */ function before(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].numberSign, 'expected `#`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingSequence);
        return sequenceOpen(code);
    }
    /**
   * In opening sequence.
   *
   * ```markdown
   * > | ## aa
   *     ^
   * ```
   *
   * @type {State}
   */ function sequenceOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].numberSign && size++ < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].atxHeadingOpeningFenceSizeMax) {
            effects.consume(code);
            return sequenceOpen;
        }
        // Always at least one `#`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingSequence);
            return atBreak(code);
        }
        return nok(code);
    }
    /**
   * After something, before something else.
   *
   * ```markdown
   * > | ## aa
   *       ^
   * ```
   *
   * @type {State}
   */ function atBreak(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].numberSign) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingSequence);
            return sequenceFurther(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeading);
            // To do: interrupt like `markdown-rs`.
            // // Feel free to interrupt.
            // tokenizer.interrupt = false
            return ok(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, atBreak, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code);
        }
        // To do: generate `data` tokens, add the `text` token later.
        // Needs edit map, see: `markdown.rs`.
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingText);
        return data(code);
    }
    /**
   * In further sequence (after whitespace).
   *
   * Could be normal “visible” hashes in the heading or a final sequence.
   *
   * ```markdown
   * > | ## aa ##
   *           ^
   * ```
   *
   * @type {State}
   */ function sequenceFurther(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].numberSign) {
            effects.consume(code);
            return sequenceFurther;
        }
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingSequence);
        return atBreak(code);
    }
    /**
   * In text.
   *
   * ```markdown
   * > | ## aa
   *        ^
   * ```
   *
   * @type {State}
   */ function data(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].numberSign || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].atxHeadingText);
            return atBreak(code);
        }
        effects.consume(code);
        return data;
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/html-flow.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "htmlFlow",
    ()=>htmlFlow
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$html$2d$tag$2d$name$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-html-tag-name/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$blank$2d$line$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/blank-line.js [app-ssr] (ecmascript)");
;
;
;
;
;
const htmlFlow = {
    concrete: true,
    name: 'htmlFlow',
    resolveTo: resolveToHtmlFlow,
    tokenize: tokenizeHtmlFlow
};
/** @type {Construct} */ const blankLineBefore = {
    partial: true,
    tokenize: tokenizeBlankLineBefore
};
const nonLazyContinuationStart = {
    partial: true,
    tokenize: tokenizeNonLazyContinuationStart
};
/** @type {Resolver} */ function resolveToHtmlFlow(events) {
    let index = events.length;
    while(index--){
        if (events[index][0] === 'enter' && events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlow) {
            break;
        }
    }
    if (index > 1 && events[index - 2][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix) {
        // Add the prefix start to the HTML token.
        events[index][1].start = events[index - 2][1].start;
        // Add the prefix start to the HTML line token.
        events[index + 1][1].start = events[index - 2][1].start;
        // Remove the line prefix.
        events.splice(index - 2, 2);
    }
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeHtmlFlow(effects, ok, nok) {
    const self = this;
    /** @type {number} */ let marker;
    /** @type {boolean} */ let closingTag;
    /** @type {string} */ let buffer;
    /** @type {number} */ let index;
    /** @type {Code} */ let markerB;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of HTML (flow).
   *
   * ```markdown
   * > | <x />
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        // To do: parse indent like `markdown-rs`.
        return before(code);
    }
    /**
   * At `<`, after optional whitespace.
   *
   * ```markdown
   * > | <x />
   *     ^
   * ```
   *
   * @type {State}
   */ function before(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan, 'expected `<`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlow);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlowData);
        effects.consume(code);
        return open;
    }
    /**
   * After `<`, at tag name or other stuff.
   *
   * ```markdown
   * > | <x />
   *      ^
   * > | <!doctype>
   *      ^
   * > | <!--xxx-->
   *      ^
   * ```
   *
   * @type {State}
   */ function open(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].exclamationMark) {
            effects.consume(code);
            return declarationOpen;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash) {
            effects.consume(code);
            closingTag = true;
            return tagCloseStart;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].questionMark) {
            effects.consume(code);
            marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlInstruction;
            // To do:
            // tokenizer.concrete = true
            // To do: use `markdown-rs` style interrupt.
            // While we’re in an instruction instead of a declaration, we’re on a `?`
            // right now, so we do need to search for `>`, similar to declarations.
            return self.interrupt ? ok : continuationDeclarationInside;
        }
        // ASCII alphabetical.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code !== null); // Always the case.
            effects.consume(code);
            buffer = String.fromCharCode(code);
            return tagName;
        }
        return nok(code);
    }
    /**
   * After `<!`, at declaration, comment, or CDATA.
   *
   * ```markdown
   * > | <!doctype>
   *       ^
   * > | <!--xxx-->
   *       ^
   * > | <![CDATA[>&<]]>
   *       ^
   * ```
   *
   * @type {State}
   */ function declarationOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlComment;
            return commentOpenInside;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket) {
            effects.consume(code);
            marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlCdata;
            index = 0;
            return cdataOpenInside;
        }
        // ASCII alphabetical.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlDeclaration;
            // // Do not form containers.
            // tokenizer.concrete = true
            return self.interrupt ? ok : continuationDeclarationInside;
        }
        return nok(code);
    }
    /**
   * After `<!-`, inside a comment, at another `-`.
   *
   * ```markdown
   * > | <!--xxx-->
   *        ^
   * ```
   *
   * @type {State}
   */ function commentOpenInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            // // Do not form containers.
            // tokenizer.concrete = true
            return self.interrupt ? ok : continuationDeclarationInside;
        }
        return nok(code);
    }
    /**
   * After `<![`, inside CDATA, expecting `CDATA[`.
   *
   * ```markdown
   * > | <![CDATA[>&<]]>
   *        ^^^^^^
   * ```
   *
   * @type {State}
   */ function cdataOpenInside(code) {
        const value = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].cdataOpeningString;
        if (code === value.charCodeAt(index++)) {
            effects.consume(code);
            if (index === value.length) {
                // // Do not form containers.
                // tokenizer.concrete = true
                return self.interrupt ? ok : continuation;
            }
            return cdataOpenInside;
        }
        return nok(code);
    }
    /**
   * After `</`, in closing tag, at tag name.
   *
   * ```markdown
   * > | </x>
   *       ^
   * ```
   *
   * @type {State}
   */ function tagCloseStart(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code !== null); // Always the case.
            effects.consume(code);
            buffer = String.fromCharCode(code);
            return tagName;
        }
        return nok(code);
    }
    /**
   * In tag name.
   *
   * ```markdown
   * > | <ab>
   *      ^^
   * > | </ab>
   *       ^^
   * ```
   *
   * @type {State}
   */ function tagName(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            const slash = code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash;
            const name = buffer.toLowerCase();
            if (!slash && !closingTag && __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$html$2d$tag$2d$name$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["htmlRawNames"].includes(name)) {
                marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlRaw;
                // // Do not form containers.
                // tokenizer.concrete = true
                return self.interrupt ? ok(code) : continuation(code);
            }
            if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$html$2d$tag$2d$name$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["htmlBlockNames"].includes(buffer.toLowerCase())) {
                marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlBasic;
                if (slash) {
                    effects.consume(code);
                    return basicSelfClosing;
                }
                // // Do not form containers.
                // tokenizer.concrete = true
                return self.interrupt ? ok(code) : continuation(code);
            }
            marker = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlComplete;
            // Do not support complete HTML when interrupting.
            return self.interrupt && !self.parser.lazy[self.now().line] ? nok(code) : closingTag ? completeClosingTagAfter(code) : completeAttributeNameBefore(code);
        }
        // ASCII alphanumerical and `-`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) {
            effects.consume(code);
            buffer += String.fromCharCode(code);
            return tagName;
        }
        return nok(code);
    }
    /**
   * After closing slash of a basic tag name.
   *
   * ```markdown
   * > | <div/>
   *          ^
   * ```
   *
   * @type {State}
   */ function basicSelfClosing(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            effects.consume(code);
            // // Do not form containers.
            // tokenizer.concrete = true
            return self.interrupt ? ok : continuation;
        }
        return nok(code);
    }
    /**
   * After closing slash of a complete tag name.
   *
   * ```markdown
   * > | <x/>
   *        ^
   * ```
   *
   * @type {State}
   */ function completeClosingTagAfter(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return completeClosingTagAfter;
        }
        return completeEnd(code);
    }
    /**
   * At an attribute name.
   *
   * At first, this state is used after a complete tag name, after whitespace,
   * where it expects optional attributes or the end of the tag.
   * It is also reused after attributes, when expecting more optional
   * attributes.
   *
   * ```markdown
   * > | <a />
   *        ^
   * > | <a :b>
   *        ^
   * > | <a _b>
   *        ^
   * > | <a b>
   *        ^
   * > | <a >
   *        ^
   * ```
   *
   * @type {State}
   */ function completeAttributeNameBefore(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash) {
            effects.consume(code);
            return completeEnd;
        }
        // ASCII alphanumerical and `:` and `_`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].colon || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].underscore || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            return completeAttributeName;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return completeAttributeNameBefore;
        }
        return completeEnd(code);
    }
    /**
   * In attribute name.
   *
   * ```markdown
   * > | <a :b>
   *         ^
   * > | <a _b>
   *         ^
   * > | <a b>
   *         ^
   * ```
   *
   * @type {State}
   */ function completeAttributeName(code) {
        // ASCII alphanumerical and `-`, `.`, `:`, and `_`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dot || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].colon || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].underscore || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) {
            effects.consume(code);
            return completeAttributeName;
        }
        return completeAttributeNameAfter(code);
    }
    /**
   * After attribute name, at an optional initializer, the end of the tag, or
   * whitespace.
   *
   * ```markdown
   * > | <a b>
   *         ^
   * > | <a b=c>
   *         ^
   * ```
   *
   * @type {State}
   */ function completeAttributeNameAfter(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo) {
            effects.consume(code);
            return completeAttributeValueBefore;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return completeAttributeNameAfter;
        }
        return completeAttributeNameBefore(code);
    }
    /**
   * Before unquoted, double quoted, or single quoted attribute value, allowing
   * whitespace.
   *
   * ```markdown
   * > | <a b=c>
   *          ^
   * > | <a b="c">
   *          ^
   * ```
   *
   * @type {State}
   */ function completeAttributeValueBefore(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent) {
            return nok(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].quotationMark || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].apostrophe) {
            effects.consume(code);
            markerB = code;
            return completeAttributeValueQuoted;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return completeAttributeValueBefore;
        }
        return completeAttributeValueUnquoted(code);
    }
    /**
   * In double or single quoted attribute value.
   *
   * ```markdown
   * > | <a b="c">
   *           ^
   * > | <a b='c'>
   *           ^
   * ```
   *
   * @type {State}
   */ function completeAttributeValueQuoted(code) {
        if (code === markerB) {
            effects.consume(code);
            markerB = null;
            return completeAttributeValueQuotedAfter;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return nok(code);
        }
        effects.consume(code);
        return completeAttributeValueQuoted;
    }
    /**
   * In unquoted attribute value.
   *
   * ```markdown
   * > | <a b=c>
   *          ^
   * ```
   *
   * @type {State}
   */ function completeAttributeValueUnquoted(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].quotationMark || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].apostrophe || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            return completeAttributeNameAfter(code);
        }
        effects.consume(code);
        return completeAttributeValueUnquoted;
    }
    /**
   * After double or single quoted attribute value, before whitespace or the
   * end of the tag.
   *
   * ```markdown
   * > | <a b="c">
   *            ^
   * ```
   *
   * @type {State}
   */ function completeAttributeValueQuotedAfter(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            return completeAttributeNameBefore(code);
        }
        return nok(code);
    }
    /**
   * In certain circumstances of a complete tag where only an `>` is allowed.
   *
   * ```markdown
   * > | <a b="c">
   *             ^
   * ```
   *
   * @type {State}
   */ function completeEnd(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            effects.consume(code);
            return completeAfter;
        }
        return nok(code);
    }
    /**
   * After `>` in a complete tag.
   *
   * ```markdown
   * > | <x>
   *        ^
   * ```
   *
   * @type {State}
   */ function completeAfter(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            // // Do not form containers.
            // tokenizer.concrete = true
            return continuation(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return completeAfter;
        }
        return nok(code);
    }
    /**
   * In continuation of any HTML kind.
   *
   * ```markdown
   * > | <!--xxx-->
   *          ^
   * ```
   *
   * @type {State}
   */ function continuation(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash && marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlComment) {
            effects.consume(code);
            return continuationCommentInside;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan && marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlRaw) {
            effects.consume(code);
            return continuationRawTagOpen;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan && marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlDeclaration) {
            effects.consume(code);
            return continuationClose;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].questionMark && marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlInstruction) {
            effects.consume(code);
            return continuationDeclarationInside;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket && marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlCdata) {
            effects.consume(code);
            return continuationCdataInside;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code) && (marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlBasic || marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlComplete)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlowData);
            return effects.check(blankLineBefore, continuationAfter, continuationStart)(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlowData);
            return continuationStart(code);
        }
        effects.consume(code);
        return continuation;
    }
    /**
   * In continuation, at eol.
   *
   * ```markdown
   * > | <x>
   *        ^
   *   | asd
   * ```
   *
   * @type {State}
   */ function continuationStart(code) {
        return effects.check(nonLazyContinuationStart, continuationStartNonLazy, continuationAfter)(code);
    }
    /**
   * In continuation, at eol, before non-lazy content.
   *
   * ```markdown
   * > | <x>
   *        ^
   *   | asd
   * ```
   *
   * @type {State}
   */ function continuationStartNonLazy(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code));
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return continuationBefore;
    }
    /**
   * In continuation, before non-lazy content.
   *
   * ```markdown
   *   | <x>
   * > | asd
   *     ^
   * ```
   *
   * @type {State}
   */ function continuationBefore(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            return continuationStart(code);
        }
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlowData);
        return continuation(code);
    }
    /**
   * In comment continuation, after one `-`, expecting another.
   *
   * ```markdown
   * > | <!--xxx-->
   *             ^
   * ```
   *
   * @type {State}
   */ function continuationCommentInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            return continuationDeclarationInside;
        }
        return continuation(code);
    }
    /**
   * In raw continuation, after `<`, at `/`.
   *
   * ```markdown
   * > | <script>console.log(1)</script>
   *                            ^
   * ```
   *
   * @type {State}
   */ function continuationRawTagOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash) {
            effects.consume(code);
            buffer = '';
            return continuationRawEndTag;
        }
        return continuation(code);
    }
    /**
   * In raw continuation, after `</`, in a raw tag name.
   *
   * ```markdown
   * > | <script>console.log(1)</script>
   *                             ^^^^^^
   * ```
   *
   * @type {State}
   */ function continuationRawEndTag(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            const name = buffer.toLowerCase();
            if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$html$2d$tag$2d$name$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["htmlRawNames"].includes(name)) {
                effects.consume(code);
                return continuationClose;
            }
            return continuation(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code) && buffer.length < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlRawSizeMax) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code !== null); // Always the case.
            effects.consume(code);
            buffer += String.fromCharCode(code);
            return continuationRawEndTag;
        }
        return continuation(code);
    }
    /**
   * In cdata continuation, after `]`, expecting `]>`.
   *
   * ```markdown
   * > | <![CDATA[>&<]]>
   *                  ^
   * ```
   *
   * @type {State}
   */ function continuationCdataInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket) {
            effects.consume(code);
            return continuationDeclarationInside;
        }
        return continuation(code);
    }
    /**
   * In declaration or instruction continuation, at `>`.
   *
   * ```markdown
   * > | <!-->
   *         ^
   * > | <?>
   *       ^
   * > | <!q>
   *        ^
   * > | <!--ab-->
   *             ^
   * > | <![CDATA[>&<]]>
   *                   ^
   * ```
   *
   * @type {State}
   */ function continuationDeclarationInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            effects.consume(code);
            return continuationClose;
        }
        // More dashes.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash && marker === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].htmlComment) {
            effects.consume(code);
            return continuationDeclarationInside;
        }
        return continuation(code);
    }
    /**
   * In closed continuation: everything we get until the eol/eof is part of it.
   *
   * ```markdown
   * > | <!doctype>
   *               ^
   * ```
   *
   * @type {State}
   */ function continuationClose(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlowData);
            return continuationAfter(code);
        }
        effects.consume(code);
        return continuationClose;
    }
    /**
   * Done.
   *
   * ```markdown
   * > | <!doctype>
   *               ^
   * ```
   *
   * @type {State}
   */ function continuationAfter(code) {
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlFlow);
        // // Feel free to interrupt.
        // tokenizer.interrupt = false
        // // No longer concrete.
        // tokenizer.concrete = false
        return ok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeNonLazyContinuationStart(effects, ok, nok) {
    const self = this;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * At eol, before continuation.
   *
   * ```markdown
   * > | * ```js
   *            ^
   *   | b
   * ```
   *
   * @type {State}
   */ function start(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
            return after;
        }
        return nok(code);
    }
    /**
   * A continuation.
   *
   * ```markdown
   *   | * ```js
   * > | b
   *     ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        return self.parser.lazy[self.now().line] ? nok(code) : ok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeBlankLineBefore(effects, ok, nok) {
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Before eol, expecting blank line.
   *
   * ```markdown
   * > | <div>
   *          ^
   *   |
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected a line ending');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return effects.attempt(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$blank$2d$line$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["blankLine"], ok, nok);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/html-text.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "htmlText",
    ()=>htmlText
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const htmlText = {
    name: 'htmlText',
    tokenize: tokenizeHtmlText
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeHtmlText(effects, ok, nok) {
    const self = this;
    /** @type {NonNullable<Code> | undefined} */ let marker;
    /** @type {number} */ let index;
    /** @type {State} */ let returnState;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of HTML (text).
   *
   * ```markdown
   * > | a <b> c
   *       ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan, 'expected `<`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlText);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlTextData);
        effects.consume(code);
        return open;
    }
    /**
   * After `<`, at tag name or other stuff.
   *
   * ```markdown
   * > | a <b> c
   *        ^
   * > | a <!doctype> c
   *        ^
   * > | a <!--b--> c
   *        ^
   * ```
   *
   * @type {State}
   */ function open(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].exclamationMark) {
            effects.consume(code);
            return declarationOpen;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash) {
            effects.consume(code);
            return tagCloseStart;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].questionMark) {
            effects.consume(code);
            return instruction;
        }
        // ASCII alphabetical.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            return tagOpen;
        }
        return nok(code);
    }
    /**
   * After `<!`, at declaration, comment, or CDATA.
   *
   * ```markdown
   * > | a <!doctype> c
   *         ^
   * > | a <!--b--> c
   *         ^
   * > | a <![CDATA[>&<]]> c
   *         ^
   * ```
   *
   * @type {State}
   */ function declarationOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            return commentOpenInside;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket) {
            effects.consume(code);
            index = 0;
            return cdataOpenInside;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            return declaration;
        }
        return nok(code);
    }
    /**
   * In a comment, after `<!-`, at another `-`.
   *
   * ```markdown
   * > | a <!--b--> c
   *          ^
   * ```
   *
   * @type {State}
   */ function commentOpenInside(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            return commentEnd;
        }
        return nok(code);
    }
    /**
   * In comment.
   *
   * ```markdown
   * > | a <!--b--> c
   *           ^
   * ```
   *
   * @type {State}
   */ function comment(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return nok(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            return commentClose;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = comment;
            return lineEndingBefore(code);
        }
        effects.consume(code);
        return comment;
    }
    /**
   * In comment, after `-`.
   *
   * ```markdown
   * > | a <!--b--> c
   *             ^
   * ```
   *
   * @type {State}
   */ function commentClose(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash) {
            effects.consume(code);
            return commentEnd;
        }
        return comment(code);
    }
    /**
   * In comment, after `--`.
   *
   * ```markdown
   * > | a <!--b--> c
   *              ^
   * ```
   *
   * @type {State}
   */ function commentEnd(code) {
        return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan ? end(code) : code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash ? commentClose(code) : comment(code);
    }
    /**
   * After `<![`, in CDATA, expecting `CDATA[`.
   *
   * ```markdown
   * > | a <![CDATA[>&<]]> b
   *          ^^^^^^
   * ```
   *
   * @type {State}
   */ function cdataOpenInside(code) {
        const value = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].cdataOpeningString;
        if (code === value.charCodeAt(index++)) {
            effects.consume(code);
            return index === value.length ? cdata : cdataOpenInside;
        }
        return nok(code);
    }
    /**
   * In CDATA.
   *
   * ```markdown
   * > | a <![CDATA[>&<]]> b
   *                ^^^
   * ```
   *
   * @type {State}
   */ function cdata(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return nok(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket) {
            effects.consume(code);
            return cdataClose;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = cdata;
            return lineEndingBefore(code);
        }
        effects.consume(code);
        return cdata;
    }
    /**
   * In CDATA, after `]`, at another `]`.
   *
   * ```markdown
   * > | a <![CDATA[>&<]]> b
   *                    ^
   * ```
   *
   * @type {State}
   */ function cdataClose(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket) {
            effects.consume(code);
            return cdataEnd;
        }
        return cdata(code);
    }
    /**
   * In CDATA, after `]]`, at `>`.
   *
   * ```markdown
   * > | a <![CDATA[>&<]]> b
   *                     ^
   * ```
   *
   * @type {State}
   */ function cdataEnd(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            return end(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket) {
            effects.consume(code);
            return cdataEnd;
        }
        return cdata(code);
    }
    /**
   * In declaration.
   *
   * ```markdown
   * > | a <!b> c
   *          ^
   * ```
   *
   * @type {State}
   */ function declaration(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            return end(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = declaration;
            return lineEndingBefore(code);
        }
        effects.consume(code);
        return declaration;
    }
    /**
   * In instruction.
   *
   * ```markdown
   * > | a <?b?> c
   *         ^
   * ```
   *
   * @type {State}
   */ function instruction(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return nok(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].questionMark) {
            effects.consume(code);
            return instructionClose;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = instruction;
            return lineEndingBefore(code);
        }
        effects.consume(code);
        return instruction;
    }
    /**
   * In instruction, after `?`, at `>`.
   *
   * ```markdown
   * > | a <?b?> c
   *           ^
   * ```
   *
   * @type {State}
   */ function instructionClose(code) {
        return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan ? end(code) : instruction(code);
    }
    /**
   * After `</`, in closing tag, at tag name.
   *
   * ```markdown
   * > | a </b> c
   *         ^
   * ```
   *
   * @type {State}
   */ function tagCloseStart(code) {
        // ASCII alphabetical.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            return tagClose;
        }
        return nok(code);
    }
    /**
   * After `</x`, in a tag name.
   *
   * ```markdown
   * > | a </b> c
   *          ^
   * ```
   *
   * @type {State}
   */ function tagClose(code) {
        // ASCII alphanumerical and `-`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) {
            effects.consume(code);
            return tagClose;
        }
        return tagCloseBetween(code);
    }
    /**
   * In closing tag, after tag name.
   *
   * ```markdown
   * > | a </b> c
   *          ^
   * ```
   *
   * @type {State}
   */ function tagCloseBetween(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = tagCloseBetween;
            return lineEndingBefore(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return tagCloseBetween;
        }
        return end(code);
    }
    /**
   * After `<x`, in opening tag name.
   *
   * ```markdown
   * > | a <b> c
   *         ^
   * ```
   *
   * @type {State}
   */ function tagOpen(code) {
        // ASCII alphanumerical and `-`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) {
            effects.consume(code);
            return tagOpen;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            return tagOpenBetween(code);
        }
        return nok(code);
    }
    /**
   * In opening tag, after tag name.
   *
   * ```markdown
   * > | a <b> c
   *         ^
   * ```
   *
   * @type {State}
   */ function tagOpenBetween(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash) {
            effects.consume(code);
            return end;
        }
        // ASCII alphabetical and `:` and `_`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].colon || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].underscore || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlpha"])(code)) {
            effects.consume(code);
            return tagOpenAttributeName;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = tagOpenBetween;
            return lineEndingBefore(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return tagOpenBetween;
        }
        return end(code);
    }
    /**
   * In attribute name.
   *
   * ```markdown
   * > | a <b c> d
   *          ^
   * ```
   *
   * @type {State}
   */ function tagOpenAttributeName(code) {
        // ASCII alphabetical and `-`, `.`, `:`, and `_`.
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dot || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].colon || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].underscore || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiAlphanumeric"])(code)) {
            effects.consume(code);
            return tagOpenAttributeName;
        }
        return tagOpenAttributeNameAfter(code);
    }
    /**
   * After attribute name, before initializer, the end of the tag, or
   * whitespace.
   *
   * ```markdown
   * > | a <b c> d
   *           ^
   * ```
   *
   * @type {State}
   */ function tagOpenAttributeNameAfter(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo) {
            effects.consume(code);
            return tagOpenAttributeValueBefore;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = tagOpenAttributeNameAfter;
            return lineEndingBefore(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return tagOpenAttributeNameAfter;
        }
        return tagOpenBetween(code);
    }
    /**
   * Before unquoted, double quoted, or single quoted attribute value, allowing
   * whitespace.
   *
   * ```markdown
   * > | a <b c=d> e
   *            ^
   * ```
   *
   * @type {State}
   */ function tagOpenAttributeValueBefore(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent) {
            return nok(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].quotationMark || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].apostrophe) {
            effects.consume(code);
            marker = code;
            return tagOpenAttributeValueQuoted;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = tagOpenAttributeValueBefore;
            return lineEndingBefore(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.consume(code);
            return tagOpenAttributeValueBefore;
        }
        effects.consume(code);
        return tagOpenAttributeValueUnquoted;
    }
    /**
   * In double or single quoted attribute value.
   *
   * ```markdown
   * > | a <b c="d"> e
   *             ^
   * ```
   *
   * @type {State}
   */ function tagOpenAttributeValueQuoted(code) {
        if (code === marker) {
            effects.consume(code);
            marker = undefined;
            return tagOpenAttributeValueQuotedAfter;
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof) {
            return nok(code);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            returnState = tagOpenAttributeValueQuoted;
            return lineEndingBefore(code);
        }
        effects.consume(code);
        return tagOpenAttributeValueQuoted;
    }
    /**
   * In unquoted attribute value.
   *
   * ```markdown
   * > | a <b c=d> e
   *            ^
   * ```
   *
   * @type {State}
   */ function tagOpenAttributeValueUnquoted(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].quotationMark || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].apostrophe || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].lessThan || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].graveAccent) {
            return nok(code);
        }
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            return tagOpenBetween(code);
        }
        effects.consume(code);
        return tagOpenAttributeValueUnquoted;
    }
    /**
   * After double or single quoted attribute value, before whitespace or the end
   * of the tag.
   *
   * ```markdown
   * > | a <b c="d"> e
   *               ^
   * ```
   *
   * @type {State}
   */ function tagOpenAttributeValueQuotedAfter(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].slash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code)) {
            return tagOpenBetween(code);
        }
        return nok(code);
    }
    /**
   * In certain circumstances of a tag where only an `>` is allowed.
   *
   * ```markdown
   * > | a <b c="d"> e
   *               ^
   * ```
   *
   * @type {State}
   */ function end(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].greaterThan) {
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlTextData);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlText);
            return ok;
        }
        return nok(code);
    }
    /**
   * At eol.
   *
   * > 👉 **Note**: we can’t have blank lines in text, so no need to worry about
   * > empty tokens.
   *
   * ```markdown
   * > | a <!--a
   *            ^
   *   | b-->
   * ```
   *
   * @type {State}
   */ function lineEndingBefore(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(returnState, 'expected return state');
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlTextData);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return lineEndingAfter;
    }
    /**
   * After eol, at optional whitespace.
   *
   * > 👉 **Note**: we can’t have blank lines in text, so no need to worry about
   * > empty tokens.
   *
   * ```markdown
   *   | a <!--a
   * > | b-->
   *     ^
   * ```
   *
   * @type {State}
   */ function lineEndingAfter(code) {
        // Always populated by defaults.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.parser.constructs.disable.null, 'expected `disable.null` to be populated');
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, lineEndingAfterPrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, self.parser.constructs.disable.null.includes('codeIndented') ? undefined : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize)(code) : lineEndingAfterPrefix(code);
    }
    /**
   * After eol, after optional whitespace.
   *
   * > 👉 **Note**: we can’t have blank lines in text, so no need to worry about
   * > empty tokens.
   *
   * ```markdown
   *   | a <!--a
   * > | b-->
   *     ^
   * ```
   *
   * @type {State}
   */ function lineEndingAfterPrefix(code) {
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].htmlTextData);
        return returnState(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/label-end.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "labelEnd",
    ()=>labelEnd
]);
/**
 * @import {
 *   Construct,
 *   Event,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer,
 *   Token
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$destination$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-destination/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$label$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-label/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$title$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-title/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-whitespace/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-chunked/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$normalize$2d$identifier$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-normalize-identifier/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$resolve$2d$all$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-resolve-all/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
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
const labelEnd = {
    name: 'labelEnd',
    resolveAll: resolveAllLabelEnd,
    resolveTo: resolveToLabelEnd,
    tokenize: tokenizeLabelEnd
};
/** @type {Construct} */ const resourceConstruct = {
    tokenize: tokenizeResource
};
/** @type {Construct} */ const referenceFullConstruct = {
    tokenize: tokenizeReferenceFull
};
/** @type {Construct} */ const referenceCollapsedConstruct = {
    tokenize: tokenizeReferenceCollapsed
};
/** @type {Resolver} */ function resolveAllLabelEnd(events) {
    let index = -1;
    /** @type {Array<Event>} */ const newEvents = [];
    while(++index < events.length){
        const token = events[index][1];
        newEvents.push(events[index]);
        if (token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImage || token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink || token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelEnd) {
            // Remove the marker.
            const offset = token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImage ? 4 : 2;
            token.type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].data;
            index += offset;
        }
    }
    // If the events are equal, we don't have to copy newEvents to events
    if (events.length !== newEvents.length) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["splice"])(events, 0, events.length, newEvents);
    }
    return events;
}
/** @type {Resolver} */ function resolveToLabelEnd(events, context) {
    let index = events.length;
    let offset = 0;
    /** @type {Token} */ let token;
    /** @type {number | undefined} */ let open;
    /** @type {number | undefined} */ let close;
    /** @type {Array<Event>} */ let media;
    // Find an opening.
    while(index--){
        token = events[index][1];
        if (open) {
            // If we see another link, or inactive link label, we’ve been here before.
            if (token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].link || token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink && token._inactive) {
                break;
            }
            // Mark other link openings as inactive, as we can’t have links in
            // links.
            if (events[index][0] === 'enter' && token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink) {
                token._inactive = true;
            }
        } else if (close) {
            if (events[index][0] === 'enter' && (token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImage || token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink) && !token._balanced) {
                open = index;
                if (token.type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink) {
                    offset = 2;
                    break;
                }
            }
        } else if (token.type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelEnd) {
            close = index;
        }
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(open !== undefined, '`open` is supposed to be found');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(close !== undefined, '`close` is supposed to be found');
    const group = {
        type: events[open][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].link : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].image,
        start: {
            ...events[open][1].start
        },
        end: {
            ...events[events.length - 1][1].end
        }
    };
    const label = {
        type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].label,
        start: {
            ...events[open][1].start
        },
        end: {
            ...events[close][1].end
        }
    };
    const text = {
        type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelText,
        start: {
            ...events[open + offset + 2][1].end
        },
        end: {
            ...events[close - 2][1].start
        }
    };
    media = [
        [
            'enter',
            group,
            context
        ],
        [
            'enter',
            label,
            context
        ]
    ];
    // Opening marker.
    media = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(media, events.slice(open + 1, open + offset + 3));
    // Text open.
    media = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(media, [
        [
            'enter',
            text,
            context
        ]
    ]);
    // Always populated by defaults.
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(context.parser.constructs.insideSpan.null, 'expected `insideSpan.null` to be populated');
    // Between.
    media = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(media, (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$resolve$2d$all$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["resolveAll"])(context.parser.constructs.insideSpan.null, events.slice(open + offset + 4, close - 3), context));
    // Text close, marker close, label close.
    media = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(media, [
        [
            'exit',
            text,
            context
        ],
        events[close - 2],
        events[close - 1],
        [
            'exit',
            label,
            context
        ]
    ]);
    // Reference, resource, or so.
    media = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(media, events.slice(close + 1));
    // Media close.
    media = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["push"])(media, [
        [
            'exit',
            group,
            context
        ]
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$chunked$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["splice"])(events, open, events.length, media);
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeLabelEnd(effects, ok, nok) {
    const self = this;
    let index = self.events.length;
    /** @type {Token} */ let labelStart;
    /** @type {boolean} */ let defined;
    // Find an opening.
    while(index--){
        if ((self.events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImage || self.events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink) && !self.events[index][1]._balanced) {
            labelStart = self.events[index][1];
            break;
        }
    }
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of label end.
   *
   * ```markdown
   * > | [a](b) c
   *       ^
   * > | [a][b] c
   *       ^
   * > | [a][] b
   *       ^
   * > | [a] b
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket, 'expected `]`');
        // If there is not an okay opening.
        if (!labelStart) {
            return nok(code);
        }
        // If the corresponding label (link) start is marked as inactive,
        // it means we’d be wrapping a link, like this:
        //
        // ```markdown
        // > | a [b [c](d) e](f) g.
        //                  ^
        // ```
        //
        // We can’t have that, so it’s just balanced brackets.
        if (labelStart._inactive) {
            return labelEndNok(code);
        }
        defined = self.parser.defined.includes((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$normalize$2d$identifier$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["normalizeIdentifier"])(self.sliceSerialize({
            start: labelStart.end,
            end: self.now()
        })));
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelEnd);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelMarker);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelEnd);
        return after;
    }
    /**
   * After `]`.
   *
   * ```markdown
   * > | [a](b) c
   *       ^
   * > | [a][b] c
   *       ^
   * > | [a][] b
   *       ^
   * > | [a] b
   *       ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        // Note: `markdown-rs` also parses GFM footnotes here, which for us is in
        // an extension.
        // Resource (`[asd](fgh)`)?
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftParenthesis) {
            return effects.attempt(resourceConstruct, labelEndOk, defined ? labelEndOk : labelEndNok)(code);
        }
        // Full (`[asd][fgh]`) or collapsed (`[asd][]`) reference?
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket) {
            return effects.attempt(referenceFullConstruct, labelEndOk, defined ? referenceNotFull : labelEndNok)(code);
        }
        // Shortcut (`[asd]`) reference?
        return defined ? labelEndOk(code) : labelEndNok(code);
    }
    /**
   * After `]`, at `[`, but not at a full reference.
   *
   * > 👉 **Note**: we only get here if the label is defined.
   *
   * ```markdown
   * > | [a][] b
   *        ^
   * > | [a] b
   *        ^
   * ```
   *
   * @type {State}
   */ function referenceNotFull(code) {
        return effects.attempt(referenceCollapsedConstruct, labelEndOk, labelEndNok)(code);
    }
    /**
   * Done, we found something.
   *
   * ```markdown
   * > | [a](b) c
   *           ^
   * > | [a][b] c
   *           ^
   * > | [a][] b
   *          ^
   * > | [a] b
   *        ^
   * ```
   *
   * @type {State}
   */ function labelEndOk(code) {
        // Note: `markdown-rs` does a bunch of stuff here.
        return ok(code);
    }
    /**
   * Done, it’s nothing.
   *
   * There was an okay opening, but we didn’t match anything.
   *
   * ```markdown
   * > | [a](b c
   *        ^
   * > | [a][b c
   *        ^
   * > | [a] b
   *        ^
   * ```
   *
   * @type {State}
   */ function labelEndNok(code) {
        labelStart._balanced = true;
        return nok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeResource(effects, ok, nok) {
    return resourceStart;
    //TURBOPACK unreachable
    ;
    /**
   * At a resource.
   *
   * ```markdown
   * > | [a](b) c
   *        ^
   * ```
   *
   * @type {State}
   */ function resourceStart(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftParenthesis, 'expected left paren');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resource);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceMarker);
        return resourceBefore;
    }
    /**
   * In resource, after `(`, at optional whitespace.
   *
   * ```markdown
   * > | [a](b) c
   *         ^
   * ```
   *
   * @type {State}
   */ function resourceBefore(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryWhitespace"])(effects, resourceOpen)(code) : resourceOpen(code);
    }
    /**
   * In resource, after optional whitespace, at `)` or a destination.
   *
   * ```markdown
   * > | [a](b) c
   *         ^
   * ```
   *
   * @type {State}
   */ function resourceOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightParenthesis) {
            return resourceEnd(code);
        }
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$destination$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryDestination"])(effects, resourceDestinationAfter, resourceDestinationMissing, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceDestination, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceDestinationLiteral, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceDestinationLiteralMarker, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceDestinationRaw, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceDestinationString, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].linkResourceDestinationBalanceMax)(code);
    }
    /**
   * In resource, after destination, at optional whitespace.
   *
   * ```markdown
   * > | [a](b) c
   *          ^
   * ```
   *
   * @type {State}
   */ function resourceDestinationAfter(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryWhitespace"])(effects, resourceBetween)(code) : resourceEnd(code);
    }
    /**
   * At invalid destination.
   *
   * ```markdown
   * > | [a](<<) b
   *         ^
   * ```
   *
   * @type {State}
   */ function resourceDestinationMissing(code) {
        return nok(code);
    }
    /**
   * In resource, after destination and whitespace, at `(` or title.
   *
   * ```markdown
   * > | [a](b ) c
   *           ^
   * ```
   *
   * @type {State}
   */ function resourceBetween(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].quotationMark || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].apostrophe || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftParenthesis) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$title$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryTitle"])(effects, resourceTitleAfter, nok, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceTitle, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceTitleMarker, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceTitleString)(code);
        }
        return resourceEnd(code);
    }
    /**
   * In resource, after title, at optional whitespace.
   *
   * ```markdown
   * > | [a](b "c") d
   *              ^
   * ```
   *
   * @type {State}
   */ function resourceTitleAfter(code) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEndingOrSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$whitespace$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryWhitespace"])(effects, resourceEnd)(code) : resourceEnd(code);
    }
    /**
   * In resource, at `)`.
   *
   * ```markdown
   * > | [a](b) d
   *          ^
   * ```
   *
   * @type {State}
   */ function resourceEnd(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightParenthesis) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resourceMarker);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].resource);
            return ok;
        }
        return nok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeReferenceFull(effects, ok, nok) {
    const self = this;
    return referenceFull;
    //TURBOPACK unreachable
    ;
    /**
   * In a reference (full), at the `[`.
   *
   * ```markdown
   * > | [a][b] d
   *        ^
   * ```
   *
   * @type {State}
   */ function referenceFull(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket, 'expected left bracket');
        return __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$label$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factoryLabel"].call(self, effects, referenceFullAfter, referenceFullMissing, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].reference, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].referenceMarker, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].referenceString)(code);
    }
    /**
   * In a reference (full), after `]`.
   *
   * ```markdown
   * > | [a][b] d
   *          ^
   * ```
   *
   * @type {State}
   */ function referenceFullAfter(code) {
        return self.parser.defined.includes((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$normalize$2d$identifier$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["normalizeIdentifier"])(self.sliceSerialize(self.events[self.events.length - 1][1]).slice(1, -1))) ? ok(code) : nok(code);
    }
    /**
   * In reference (full) that was missing.
   *
   * ```markdown
   * > | [a][b d
   *        ^
   * ```
   *
   * @type {State}
   */ function referenceFullMissing(code) {
        return nok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeReferenceCollapsed(effects, ok, nok) {
    return referenceCollapsedStart;
    //TURBOPACK unreachable
    ;
    /**
   * In reference (collapsed), at `[`.
   *
   * > 👉 **Note**: we only get here if the label is defined.
   *
   * ```markdown
   * > | [a][] d
   *        ^
   * ```
   *
   * @type {State}
   */ function referenceCollapsedStart(code) {
        // We only attempt a collapsed label if there’s a `[`.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket, 'expected left bracket');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].reference);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].referenceMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].referenceMarker);
        return referenceCollapsedOpen;
    }
    /**
   * In reference (collapsed), at `]`.
   *
   * > 👉 **Note**: we only get here if the label is defined.
   *
   * ```markdown
   * > | [a][] d
   *         ^
   * ```
   *
   *  @type {State}
   */ function referenceCollapsedOpen(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightSquareBracket) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].referenceMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].referenceMarker);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].reference);
            return ok;
        }
        return nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/label-start-image.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "labelStartImage",
    ()=>labelStartImage
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$label$2d$end$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/label-end.js [app-ssr] (ecmascript)");
;
;
;
const labelStartImage = {
    name: 'labelStartImage',
    resolveAll: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$label$2d$end$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["labelEnd"].resolveAll,
    tokenize: tokenizeLabelStartImage
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeLabelStartImage(effects, ok, nok) {
    const self = this;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of label (image) start.
   *
   * ```markdown
   * > | a ![b] c
   *       ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].exclamationMark, 'expected `!`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImage);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImageMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImageMarker);
        return open;
    }
    /**
   * After `!`, at `[`.
   *
   * ```markdown
   * > | a ![b] c
   *        ^
   * ```
   *
   * @type {State}
   */ function open(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelMarker);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelMarker);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelImage);
            return after;
        }
        return nok(code);
    }
    /**
   * After `![`.
   *
   * ```markdown
   * > | a ![b] c
   *         ^
   * ```
   *
   * This is needed in because, when GFM footnotes are enabled, images never
   * form when started with a `^`.
   * Instead, links form:
   *
   * ```markdown
   * ![^a](b)
   *
   * ![^a][b]
   *
   * [b]: c
   * ```
   *
   * ```html
   * <p>!<a href=\"b\">^a</a></p>
   * <p>!<a href=\"c\">^a</a></p>
   * ```
   *
   * @type {State}
   */ function after(code) {
        // To do: use a new field to do this, this is still needed for
        // `micromark-extension-gfm-footnote`, but the `label-start-link`
        // behavior isn’t.
        // Hidden footnotes hook.
        /* c8 ignore next 3 */ return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].caret && '_hiddenFootnoteSupport' in self.parser.constructs ? nok(code) : ok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/label-start-link.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "labelStartLink",
    ()=>labelStartLink
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$label$2d$end$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/label-end.js [app-ssr] (ecmascript)");
;
;
;
const labelStartLink = {
    name: 'labelStartLink',
    resolveAll: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$label$2d$end$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["labelEnd"].resolveAll,
    tokenize: tokenizeLabelStartLink
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeLabelStartLink(effects, ok, nok) {
    const self = this;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of label (link) start.
   *
   * ```markdown
   * > | a [b] c
   *       ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].leftSquareBracket, 'expected `[`');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink);
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelMarker);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].labelLink);
        return after;
    }
    /** @type {State} */ function after(code) {
        // To do: this isn’t needed in `micromark-extension-gfm-footnote`,
        // remove.
        // Hidden footnotes hook.
        /* c8 ignore next 3 */ return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].caret && '_hiddenFootnoteSupport' in self.parser.constructs ? nok(code) : ok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/line-ending.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "lineEnding",
    ()=>lineEnding
]);
/**
 * @import {
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const lineEnding = {
    name: 'lineEnding',
    tokenize: tokenizeLineEnding
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeLineEnding(effects, ok) {
    return start;
    //TURBOPACK unreachable
    ;
    /** @type {State} */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code), 'expected eol');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding);
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, ok, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/thematic-break.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "thematicBreak",
    ()=>thematicBreak
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const thematicBreak = {
    name: 'thematicBreak',
    tokenize: tokenizeThematicBreak
};
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeThematicBreak(effects, ok, nok) {
    let size = 0;
    /** @type {NonNullable<Code>} */ let marker;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * Start of thematic break.
   *
   * ```markdown
   * > | ***
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].thematicBreak);
        // To do: parse indent like `markdown-rs`.
        return before(code);
    }
    /**
   * After optional whitespace, at marker.
   *
   * ```markdown
   * > | ***
   *     ^
   * ```
   *
   * @type {State}
   */ function before(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].asterisk || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].underscore, 'expected `*`, `-`, or `_`');
        marker = code;
        return atBreak(code);
    }
    /**
   * After something, before something else.
   *
   * ```markdown
   * > | ***
   *     ^
   * ```
   *
   * @type {State}
   */ function atBreak(code) {
        if (code === marker) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].thematicBreakSequence);
            return sequence(code);
        }
        if (size >= __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].thematicBreakMarkerCountMin && (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code))) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].thematicBreak);
            return ok(code);
        }
        return nok(code);
    }
    /**
   * In sequence.
   *
   * ```markdown
   * > | ***
   *     ^
   * ```
   *
   * @type {State}
   */ function sequence(code) {
        if (code === marker) {
            effects.consume(code);
            size++;
            return sequence;
        }
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].thematicBreakSequence);
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, atBreak, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].whitespace)(code) : atBreak(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/list.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "list",
    ()=>list
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   Exiter,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/constants.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$blank$2d$line$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/blank-line.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$thematic$2d$break$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/thematic-break.js [app-ssr] (ecmascript)");
;
;
;
;
;
;
const list = {
    continuation: {
        tokenize: tokenizeListContinuation
    },
    exit: tokenizeListEnd,
    name: 'list',
    tokenize: tokenizeListStart
};
/** @type {Construct} */ const listItemPrefixWhitespaceConstruct = {
    partial: true,
    tokenize: tokenizeListItemPrefixWhitespace
};
/** @type {Construct} */ const indentConstruct = {
    partial: true,
    tokenize: tokenizeIndent
};
// To do: `markdown-rs` parses list items on their own and later stitches them
// together.
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeListStart(effects, ok, nok) {
    const self = this;
    const tail = self.events[self.events.length - 1];
    let initialSize = tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix ? tail[2].sliceSerialize(tail[1], true).length : 0;
    let size = 0;
    return start;
    //TURBOPACK unreachable
    ;
    /** @type {State} */ function start(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        const kind = self.containerState.type || (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].asterisk || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].plusSign || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listUnordered : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listOrdered);
        if (kind === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listUnordered ? !self.containerState.marker || code === self.containerState.marker : (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiDigit"])(code)) {
            if (!self.containerState.type) {
                self.containerState.type = kind;
                effects.enter(kind, {
                    _container: true
                });
            }
            if (kind === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listUnordered) {
                effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefix);
                return code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].asterisk || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash ? effects.check(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$thematic$2d$break$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["thematicBreak"], nok, atMarker)(code) : atMarker(code);
            }
            if (!self.interrupt || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].digit1) {
                effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefix);
                effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemValue);
                return inside(code);
            }
        }
        return nok(code);
    }
    /** @type {State} */ function inside(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["asciiDigit"])(code) && ++size < __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].listItemValueSizeMax) {
            effects.consume(code);
            return inside;
        }
        if ((!self.interrupt || size < 2) && (self.containerState.marker ? code === self.containerState.marker : code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].rightParenthesis || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dot)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemValue);
            return atMarker(code);
        }
        return nok(code);
    }
    /**
   * @type {State}
   **/ function atMarker(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof, 'eof (`null`) is not a marker');
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemMarker);
        effects.consume(code);
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemMarker);
        self.containerState.marker = self.containerState.marker || code;
        return effects.check(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$blank$2d$line$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["blankLine"], // Can’t be empty when interrupting.
        self.interrupt ? nok : onBlank, effects.attempt(listItemPrefixWhitespaceConstruct, endOfPrefix, otherPrefix));
    }
    /** @type {State} */ function onBlank(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        self.containerState.initialBlankLine = true;
        initialSize++;
        return endOfPrefix(code);
    }
    /** @type {State} */ function otherPrefix(code) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefixWhitespace);
            effects.consume(code);
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefixWhitespace);
            return endOfPrefix;
        }
        return nok(code);
    }
    /** @type {State} */ function endOfPrefix(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        self.containerState.size = initialSize + self.sliceSerialize(effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefix), true).length;
        return ok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeListContinuation(effects, ok, nok) {
    const self = this;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
    self.containerState._closeFlow = undefined;
    return effects.check(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$core$2d$commonmark$2f$dev$2f$lib$2f$blank$2d$line$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["blankLine"], onBlank, notBlank);
    //TURBOPACK unreachable
    ;
    /** @type {State} */ function onBlank(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(typeof self.containerState.size === 'number', 'expected size');
        self.containerState.furtherBlankLines = self.containerState.furtherBlankLines || self.containerState.initialBlankLine;
        // We have a blank line.
        // Still, try to consume at most the items size.
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, ok, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemIndent, self.containerState.size + 1)(code);
    }
    /** @type {State} */ function notBlank(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        if (self.containerState.furtherBlankLines || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code)) {
            self.containerState.furtherBlankLines = undefined;
            self.containerState.initialBlankLine = undefined;
            return notInCurrentItem(code);
        }
        self.containerState.furtherBlankLines = undefined;
        self.containerState.initialBlankLine = undefined;
        return effects.attempt(indentConstruct, ok, notInCurrentItem)(code);
    }
    /** @type {State} */ function notInCurrentItem(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        // While we do continue, we signal that the flow should be closed.
        self.containerState._closeFlow = true;
        // As we’re closing flow, we’re no longer interrupting.
        self.interrupt = undefined;
        // Always populated by defaults.
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.parser.constructs.disable.null, 'expected `disable.null` to be populated');
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, effects.attempt(list, ok, nok), __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix, self.parser.constructs.disable.null.includes('codeIndented') ? undefined : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize)(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeIndent(effects, ok, nok) {
    const self = this;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(typeof self.containerState.size === 'number', 'expected size');
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, afterPrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemIndent, self.containerState.size + 1);
    //TURBOPACK unreachable
    ;
    /** @type {State} */ function afterPrefix(code) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.containerState, 'expected state');
        const tail = self.events[self.events.length - 1];
        return tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemIndent && tail[2].sliceSerialize(tail[1], true).length === self.containerState.size ? ok(code) : nok(code);
    }
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Exiter}
 */ function tokenizeListEnd(effects) {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(this.containerState, 'expected state');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(typeof this.containerState.type === 'string', 'expected type');
    effects.exit(this.containerState.type);
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeListItemPrefixWhitespace(effects, ok, nok) {
    const self = this;
    // Always populated by defaults.
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(self.parser.constructs.disable.null, 'expected `disable.null` to be populated');
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, afterPrefix, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefixWhitespace, self.parser.constructs.disable.null.includes('codeIndented') ? undefined : __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$constants$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["constants"].tabSize + 1);
    //TURBOPACK unreachable
    ;
    /** @type {State} */ function afterPrefix(code) {
        const tail = self.events[self.events.length - 1];
        return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) && tail && tail[1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].listItemPrefixWhitespace ? ok(code) : nok(code);
    }
}
}),
"[project]/coding/projects/LangBot/web/node_modules/micromark-core-commonmark/dev/lib/setext-underline.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "setextUnderline",
    ()=>setextUnderline
]);
/**
 * @import {
 *   Code,
 *   Construct,
 *   Resolver,
 *   State,
 *   TokenizeContext,
 *   Tokenizer
 * } from 'micromark-util-types'
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/devlop/lib/development.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-factory-space/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-character/dev/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/codes.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/micromark-util-symbol/lib/types.js [app-ssr] (ecmascript)");
;
;
;
;
const setextUnderline = {
    name: 'setextUnderline',
    resolveTo: resolveToSetextUnderline,
    tokenize: tokenizeSetextUnderline
};
/** @type {Resolver} */ function resolveToSetextUnderline(events, context) {
    // To do: resolve like `markdown-rs`.
    let index = events.length;
    /** @type {number | undefined} */ let content;
    /** @type {number | undefined} */ let text;
    /** @type {number | undefined} */ let definition;
    // Find the opening of the content.
    // It’ll always exist: we don’t tokenize if it isn’t there.
    while(index--){
        if (events[index][0] === 'enter') {
            if (events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].content) {
                content = index;
                break;
            }
            if (events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].paragraph) {
                text = index;
            }
        } else {
            if (events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].content) {
                // Remove the content end (if needed we’ll add it later)
                events.splice(index, 1);
            }
            if (!definition && events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].definition) {
                definition = index;
            }
        }
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(text !== undefined, 'expected a `text` index to be found');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(content !== undefined, 'expected a `text` index to be found');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(events[content][2] === context, 'enter context should be same');
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(events[events.length - 1][2] === context, 'enter context should be same');
    const heading = {
        type: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].setextHeading,
        start: {
            ...events[content][1].start
        },
        end: {
            ...events[events.length - 1][1].end
        }
    };
    // Change the paragraph to setext heading text.
    events[text][1].type = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].setextHeadingText;
    // If we have definitions in the content, we’ll keep on having content,
    // but we need move it.
    if (definition) {
        events.splice(text, 0, [
            'enter',
            heading,
            context
        ]);
        events.splice(definition + 1, 0, [
            'exit',
            events[content][1],
            context
        ]);
        events[content][1].end = {
            ...events[definition][1].end
        };
    } else {
        events[content][1] = heading;
    }
    // Add the heading exit at the end.
    events.push([
        'exit',
        heading,
        context
    ]);
    return events;
}
/**
 * @this {TokenizeContext}
 *   Context.
 * @type {Tokenizer}
 */ function tokenizeSetextUnderline(effects, ok, nok) {
    const self = this;
    /** @type {NonNullable<Code>} */ let marker;
    return start;
    //TURBOPACK unreachable
    ;
    /**
   * At start of heading (setext) underline.
   *
   * ```markdown
   *   | aa
   * > | ==
   *     ^
   * ```
   *
   * @type {State}
   */ function start(code) {
        let index = self.events.length;
        /** @type {boolean | undefined} */ let paragraph;
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$devlop$2f$lib$2f$development$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["ok"])(code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].dash || code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].equalsTo, 'expected `=` or `-`');
        // Find an opening.
        while(index--){
            // Skip enter/exit of line ending, line prefix, and content.
            // We can now either have a definition or a paragraph.
            if (self.events[index][1].type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineEnding && self.events[index][1].type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].linePrefix && self.events[index][1].type !== __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].content) {
                paragraph = self.events[index][1].type === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].paragraph;
                break;
            }
        }
        // To do: handle lazy/pierce like `markdown-rs`.
        // To do: parse indent like `markdown-rs`.
        if (!self.parser.lazy[self.now().line] && (self.interrupt || paragraph)) {
            effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].setextHeadingLine);
            marker = code;
            return before(code);
        }
        return nok(code);
    }
    /**
   * After optional whitespace, at `-` or `=`.
   *
   * ```markdown
   *   | aa
   * > | ==
   *     ^
   * ```
   *
   * @type {State}
   */ function before(code) {
        effects.enter(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].setextHeadingLineSequence);
        return inside(code);
    }
    /**
   * In sequence.
   *
   * ```markdown
   *   | aa
   * > | ==
   *     ^
   * ```
   *
   * @type {State}
   */ function inside(code) {
        if (code === marker) {
            effects.consume(code);
            return inside;
        }
        effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].setextHeadingLineSequence);
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownSpace"])(code) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$factory$2d$space$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["factorySpace"])(effects, after, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].lineSuffix)(code) : after(code);
    }
    /**
   * After sequence, after optional whitespace.
   *
   * ```markdown
   *   | aa
   * > | ==
   *       ^
   * ```
   *
   * @type {State}
   */ function after(code) {
        if (code === __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$codes$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["codes"].eof || (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$character$2f$dev$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["markdownLineEnding"])(code)) {
            effects.exit(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$micromark$2d$util$2d$symbol$2f$lib$2f$types$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["types"].setextHeadingLine);
            return ok(code);
        }
        return nok(code);
    }
}
}),
];

//# sourceMappingURL=a2e30_micromark-core-commonmark_dev_lib_f77537f0._.js.map